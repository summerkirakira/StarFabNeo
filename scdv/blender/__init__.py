import os
import sys
import time
import json
import shutil
import logging
import secrets
import subprocess
from pathlib import Path

import rpyc
from rpyc import ThreadedServer
from rpyc.utils.authenticators import AuthenticationError

from scdv import get_scdv
from scdv.ui import qtc, qtw, qtg
from qtpy.QtCore import QObject, Signal, Slot, QThread

from scdatatools.blender import addon as scdt_blender_addon
from scdatatools.blender.utils import available_blender_installations

from . import addon as scdv_blender_addon
from .status_dialog import BlenderLinkStatusDialog
from .utils import find_free_port, parse_auth_token
from .conf import LINK_SECRET_LEN, LINK_TOKEN_LEN, BLENDERLINK_CONFIG

logger = logging.getLogger(__name__)


class BlenderLink(QObject):
    start = Signal()
    stop = Signal()

    stopped = Signal()
    started = Signal()

    connection_approval_requested = Signal(str)

    port_update = Signal(int)

    client_connected = Signal(str)
    client_disconnected = Signal(str)
    # TODO: handle client disconnected

    # TODO: manage connections? kill/etc.

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.port = -1

        self.start.connect(self._start)
        self.stop.connect(self._stop)

        self._service = None
        self._auth_tokens = {}
        self._connected_clients = []
        self._connection_requests = {}

    def connection_approved(self, req_id, token):
        self._connection_requests[req_id] = token

    def connection_denied(self, req_id):
        self._connection_requests[req_id] = ''

    def authenticate_client(self, sock):
        token = sock.recv(LINK_TOKEN_LEN).decode('utf-8')
        if token:
            procid, secret = parse_auth_token(token)
            logger.debug(f'new blenderlink connection: {token}')
            if secret[0] == '*':  # initiated new connection from blenderlink, ask if we want to accept the connection
                self.connection_approval_requested.emit(procid)
                while self._connection_requests.get(procid) is None:
                    qtg.QGuiApplication.processEvents()
                    time.sleep(1)

                token = self._connection_requests.get(procid)
                if token:
                    procid, secret = parse_auth_token(token)
                    self.add_auth_token(token)
                else:
                    raise AuthenticationError(f'Invalid authentication token: {repr(token)}')

            if secret == self._auth_tokens.get(procid):
                self._connected_clients.append(procid)
                sock.send(token.encode('utf-8'))
                self.client_connected.emit(token)
                qtg.QGuiApplication.processEvents()
                return sock, token
        # TODO: ask the user if they want to allow the new connection
        raise AuthenticationError(f'Invalid authentication token: {repr(token)}')

    def add_auth_token(self, token):
        procid, secret = parse_auth_token(token)
        self._auth_tokens[procid] = secret

    def del_auth_token(self, token):
        procid, secret = parse_auth_token(token)
        self._auth_tokens[procid] = secret
        if procid in self._auth_tokens:
            del self._auth_tokens[procid]

    @Slot()
    def _start(self):
        if self._service is None:
            self.port = find_free_port()
            self._service = ThreadedServer(rpyc.SlaveService, hostname='localhost', port=self.port, reuse_addr=True,
                                           authenticator=self.authenticate_client)
            self.port_update.emit(self.port)
            self.started.emit()
            qtg.QGuiApplication.processEvents()
            self._service.start()

    @Slot()
    def _stop(self):
        if self._service is not None:
            self.port = -1
            self.port_update.emit(self.port)
            self.stopped.emit()
            self._auth_tokens = {}
            self._connected_clients = []
            self._connection_requests = {}
            qtg.QGuiApplication.processEvents()
            self._service.close()
            self._service = None


class BlenderManager(QObject):
    def __init__(self, scdv, blender=''):
        super().__init__(parent=scdv)
        self.scdv = scdv

        available_versions = available_blender_installations()
        if not blender and available_versions:
            blender = sorted(available_versions.keys(), reverse=True)[0]

        if blender not in available_versions:
            raise ValueError(f'Cannot use Blender version {blender} '
                             f'available: {repr(available_blender_installations())}')

        self.blender_version = blender
        self.blender = available_versions[blender]['path']

        if not self.blender.is_file():
            self.blender = None

        self.blenderlink_connections = {}
        self.blenderlink = BlenderLink()

        self._blenderlink_port = -1
        self._blenderlink_thread = QThread()
        self._blenderlink_thread.setObjectName('blenderlink')
        self._blenderlink_thread.start()
        self.blenderlink.port_update.connect(self._handle_blenderlink_port)
        self.blenderlink.client_connected.connect(self._handle_client_connected)
        self.blenderlink.connection_approval_requested.connect(self._handle_connection_approval)
        self.blenderlink.started.connect(self._update_scdv)
        self.blenderlink.stopped.connect(self._update_scdv)
        self.blenderlink.moveToThread(self._blenderlink_thread)

        self._status_dlg = None
        self._statusbar_label = qtw.QPushButton('🟢')
        self._statusbar_label.setFlat(True)
        self._statusbar_label.setMaximumWidth(32)
        self._statusbar_label.clicked.connect(self._handle_statusbar_label_clicked)

        self.scdv.actionInstall_Blender_Add_on.triggered.connect(self._handle_install_addon)

        self._update_scdv()

    def _handle_install_addon(self):
        qm = qtw.QMessageBox()
        try:
            scdv_addon = scdv_blender_addon.install(version=self.blender_version)
            scdt_addon = scdt_blender_addon.install(version=self.blender_version)
            qm.information(get_scdv(), 'SCDV Blender Addon',
                           f'SCDV Blender add-on has been installed to "{scdv_addon}". You still must manually enable '
                           f'the add-on in Blender under Preferences > Add-ons.')
        except ValueError:
            qm.warning(get_scdv(), 'SCDV Blender Addon', f'Blender addon not supported on this platform')

    @Slot(str)
    def _handle_connection_approval(self, request_id):
        qm = qtw.QMessageBox()
        qm.setWindowFlag(qtc.Qt.WindowStaysOnTopHint)
        qm.raise_()
        ret = qm.question(get_scdv(), '', f"Accept new BlenderLink connection from process {request_id}?",
                          qm.Yes | qm.No)
        if ret == qm.Yes:
            procid, token = self._gen_auth_token()
            self.blenderlink.connection_approved(request_id, token)
        else:
            self.blenderlink.connection_denied(request_id)

    @Slot(int)
    def _handle_blenderlink_port(self, new_port):
        self._blenderlink_port = new_port
        BLENDERLINK_CONFIG.parent.mkdir(exist_ok=True)
        with BLENDERLINK_CONFIG.open('w') as config:
            if new_port < 0:
                json.dump({}, config)
                for bid in list(self.blenderlink_connections.keys()):
                    self.blenderlink_connections.pop(bid)
            else:
                json.dump({'port': new_port}, config)

    @Slot(str)
    def _handle_client_connected(self, token):
        procid, secret = parse_auth_token(token)
        self.blenderlink_connections[procid] = secret

    def _start_blenderlink_service(self):
        self.blenderlink.start.emit()

    def _update_scdv(self):
        if self._blenderlink_port > 0:
            self.scdv.actionStartBlenderLink.setVisible(False)
            self.scdv.actionStopBlenderLink.setVisible(True)
            self._statusbar_label.setText('🟢')
            self._statusbar_label.setToolTip(f'Blender Link is running on port {self._blenderlink_port}')
            self._statusbar_label.setEnabled(True)
            self.scdv.statusBar.addPermanentWidget(self._statusbar_label)
        else:
            self.scdv.actionStartBlenderLink.setVisible(True)
            self.scdv.actionStopBlenderLink.setVisible(False)
            self._statusbar_label.setEnabled(False)
            self._statusbar_label.setToolTip(f'Blender Link is not running')
            self._statusbar_label.setText('🔘')

    def _handle_statusbar_label_clicked(self):
        if self._blenderlink_port > 0:
            cb = qtw.QApplication.clipboard()
            cb.clear(mode=cb.Clipboard)
            cb.setText(str(self._blenderlink_port), mode=cb.Clipboard)
            self.scdv.statusBar.showMessage(f'Blender Link port {self._blenderlink_port} copied to clipboard')

    def blenderlink_disconnect_all(self):
        pass  # TODO: manage client connections

    def _handle_status_dlg_close(self):
        self._status_dlg = None

    def show_blenderlink_status(self):
        if self._status_dlg is None:
            self._status_dlg = BlenderLinkStatusDialog(self)
            self._status_dlg.finished.connect(self._handle_status_dlg_close)
            self._status_dlg.show()
        self._status_dlg.raise_()

    def stop_blenderlink(self):
        self.blenderlink._stop()

    def start_blenderlink(self):
        if self.ensure_blenderlink_is_running():
            self.scdv.statusBar.showMessage(f'Blender Link is running on port {self._blenderlink_port}')

    def blenderlink_port(self):
        return self._blenderlink_port

    def ensure_blenderlink_is_running(self):
        if self._blenderlink_port < 0:
            self._start_blenderlink_service()
            tries = 5
            while tries > 0:
                qtg.QGuiApplication.processEvents()
                if self._blenderlink_port > 0:
                    return True
                tries -= 1
                time.sleep(1)
        return self._blenderlink_thread is not None and self._blenderlink_port > 0

    def _gen_auth_token(self):
        # procid must be 5 digits for auth (total len must be LINK_TOKEN_LEN)
        procid = f'{next(_ for _ in range(0, 65535) if _ not in self.blenderlink_connections):05}'
        token = f'{procid}:{secrets.token_hex(LINK_SECRET_LEN)}'
        return procid, token

    def launch_blender(self, init_blenderlink=True):
        if not self.blender:
            raise ValueError(f'Could not find blender installation')

        cmd = f'{self.blender.name} --python-use-system-env'
        procid, token = self._gen_auth_token()

        env = os.environ.copy()
        env['PYTHONPATH'] = ';'.join(sys.path)

        if init_blenderlink:
            if self.ensure_blenderlink_is_running():
                env.update({
                    'SCDV_BLENDERLINK_PORT': str(self._blenderlink_port),
                    'SCDV_BLENDERLINK_TOKEN': token
                })
                self.blenderlink.add_auth_token(token)
                cmd += ' --python-expr "from scdv.blender.link import client_init; client_init()"'

        if sys.platform == 'win32':
            cmd = f'start cmd /c {cmd}'

        logger.info(f'Launching blender [b-{procid}] - {repr(cmd)}')
        proc = subprocess.Popen(cmd, env=env, cwd=self.blender.parent, shell=True)
        print(proc, proc.poll())

        _, secret = parse_auth_token(token)
        self.blenderlink_connections[procid] = secret
