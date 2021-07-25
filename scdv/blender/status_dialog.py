from qtpy import uic
from qtpy.QtCore import Slot

from scdv import get_scdv
from scdv.ui import qtg, qtw, qtc
from scdv.resources import RES_PATH


class BlenderLinkStatusDialog(qtw.QDialog):
    def __init__(self, blender_manager):
        super().__init__()
        self.blender_manager = blender_manager
        uic.loadUi(str(RES_PATH / 'ui' / 'BlenderLinkStatusDialog.ui'), self)  # Load the ui into self

        self.connections_layout = qtw.QFormLayout()
        self.linkConnections.setLayout(self.connections_layout)

        self.disconnectAllButton.clicked.connect(self.blender_manager.blenderlink_disconnect_all)
        self.startButton.clicked.connect(self.blender_manager.start_blenderlink)
        self.stopButton.clicked.connect(self.blender_manager.stop_blenderlink)

        self.blender_manager.blenderlink.started.connect(self._update_status)
        self.blender_manager.blenderlink.stopped.connect(self._update_status)
        self.blender_manager.blenderlink.client_connected.connect(self._update_status)
        self.blender_manager.blenderlink.client_disconnected.connect(self._update_status)

        self.status_timer = qtc.QTimer(self)
        self.status_timer.setInterval(1000)

        self._update_status()

    def _update_status(self):
        port = self.blender_manager.blenderlink_port()
        if port > 0:
            # is running
            self.statusLabel.setText(f'Running on port {port}')
            self.statusLabel.setStyleSheet("color: green")
            self.disconnectAllButton.show()
            self.startButton.hide()
            self.stopButton.show()
        else:
            self.statusLabel.setText(f'Not Running')
            self.statusLabel.setStyleSheet("color: red")
            self.disconnectAllButton.hide()
            self.startButton.show()
            self.stopButton.hide()

        self.disconnectAllButton.hide()  # TODO: remove this when client management added

        for i in reversed(range(self.connections_layout.rowCount())):
            self.connections_layout.removeRow(i)
        for conn, token in sorted(self.blender_manager.blenderlink_connections.items(), key=lambda o: o[0]):
            self.connections_layout.addRow(conn, qtw.QLabel(str(token)))

