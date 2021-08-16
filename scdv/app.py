import os
import sys
import time
from pathlib import Path
from functools import partial
from distutils.util import strtobool

from qtpy import uic
from qtpy.QtCore import Signal, Slot
from qtpy.QtWidgets import QApplication, QMainWindow

import qtmodern.styles
import qtmodern.windows

from scdatatools.sc import StarCitizen

import scdv.ui.widgets.dock_widgets.file_view
import scdv.ui.widgets.dock_widgets.datacore_widget


from .ui import qtg, qtw, qtc
from .settings import settings
from .resources import RES_PATH
from .blender import BlenderManager
from .ui.widgets import dock_widgets
from .utils import reload_scdv_modules
from .ui.dialogs.settings_dialog import SettingsDialog
from .ui.dialogs.entity_exporter import EntityExporterDialog


class _SCLoader(qtc.QRunnable):
    def __init__(self, scdv, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scdv = scdv

    def run(self):
        self.scdv.statusBar.showMessage(f'Opening StarCitizen {self.scdv.sc.version_label}')
        self.scdv.task_started.emit('load_scdir', 'Initializing Data.p4k', 0, 5)
        # prog = qtw.QProgressDialog("Opening Data.p4k", "", 0, 2)
        # prog.setWindowModality(qtc.Qt.WindowModal)
        # prog.setCancelButton(None)
        # prog.forceShow()
        # prog.setValue(1)
        # prog.setLabelText("Reading DataCore")
        # prog.setValue(2)

        t = time.time()
        def p4k_load_monitor(msg, progress, total):
            nonlocal t
            if (time.time() - t) > 1:
                self.scdv.update_status_progress.emit('load_p4k', progress/1024//1024, None, total/1024//1024, None)
                t = time.time()
        self.scdv.task_started.emit('load_p4k', '', 0, 1)
        self.scdv.sc._p4k_load_monitor = p4k_load_monitor
        assert(self.scdv.sc.p4k is not None)
        self.scdv.task_finished.emit('load_p4k', True, '')
        self.scdv.p4k_loaded.emit()

        self.scdv.update_status_progress.emit('load_scdir', 1, 0, 0, 'Initializing DataCore')
        assert(self.scdv.sc.datacore is not None)
        self.scdv.datacore_loaded.emit()

        self.scdv.update_status_progress.emit('load_scdir', 2, 0, 0, 'Initializing Localization')
        assert(self.scdv.sc.localization is not None)
        self.scdv.localization_loaded.emit()

        self.scdv.update_status_progress.emit('load_scdir', 4, 0, 0, 'Initializing Tag Database')
        assert(self.scdv.sc.tag_database is not None)
        self.scdv.tagdatabase_loaded.emit()

        self.scdv.update_status_progress.emit('load_scdir', 3, 0, 0, 'Initializing Game Audio')
        assert(self.scdv.sc.wwise is not None)
        self.scdv.audio_loaded.emit()

        self.scdv.actionClose.setEnabled(True)
        self.scdv.task_finished.emit('load_scdir', True, '')
        self.scdv.statusBar.showMessage(f'Finished Loading StarCitizen {self.scdv.sc.version_label}')


class MainWindow(QMainWindow):
    task_started = Signal(str, str, int, int)
    update_status_progress = Signal(str, int, int, int, str)
    task_finished = Signal(str, bool, str)

    open_scdir = Signal(str)

    opened = Signal(str)
    p4k_opened = Signal()
    p4k_loaded = Signal()
    audio_loaded = Signal()
    datacore_loaded = Signal()
    tagdatabase_loaded = Signal()
    localization_loaded = Signal()

    def __init__(self):
        QMainWindow.__init__(self)

        uic.loadUi(str(RES_PATH / 'ui' / 'mainwindow.ui'), self)  # Load the ui into self
        self.setWindowTitle('SCDV')
        self.setWindowIcon(qtg.QIcon(str(RES_PATH / 'scdv.png')))

        self.settings = settings
        self._refresh_recent()

        self.task_started.connect(self._handle_task_started)
        self.update_status_progress.connect(self._handle_update_statusbar_progress)
        self.task_finished.connect(self._handle_task_finished)
        self.open_scdir.connect(self._handle_open_scdir)

        self.resize(1900, 900)

        self.actionSettings.triggered.connect(self.show_settings_dialog)

        self.actionOpen.triggered.connect(self.handle_file_open)
        self.actionClose.triggered.connect(self.handle_file_close)
        self.actionClose.setEnabled(False)
        self.actionQuit.triggered.connect(self.close)

        self.actionAudio.triggered.connect(self.show_audio)
        self.actionConsole.triggered.connect(self.show_console)
        self.actionDatacore.triggered.connect(self.show_dcb_view)
        self.actionLocal_Files.triggered.connect(self.show_local_files)
        self.actionP4K.triggered.connect(self.show_p4k_view)
        self.actionTag_Database.triggered.connect(self.show_tag_database)

        self.actionExportEntity.triggered.connect(self.show_export_ship_entity_dialog)
        self.actionAbout.triggered.connect(lambda: qtg.QDesktopServices.openUrl('https://gitlab.com/scmodding/tools/scdv'))
        self.actionClear_Recent.triggered.connect(self.clear_recent)

        self.datacore_loaded.connect(lambda: self.actionExportEntity.setEnabled(True))

        self.status_bar_progress = qtw.QProgressBar(self)
        self.statusBar.addPermanentWidget(self.status_bar_progress)
        self.status_bar_progress.setFormat('%v / %m - %p%')
        self.status_bar_progress.hide()

        self._open_tabs = {}
        self.sc_tabs.tabCloseRequested.connect(self._handle_close_tab)
        self.sc_tabs.tabBar().setContextMenuPolicy(qtc.Qt.CustomContextMenu)
        self.sc_tabs.tabBar().customContextMenuRequested.connect(self._handle_tab_ctx_menu)
        self._sc_tab_ctx = None
        self.sc_tabs_ctx_menu = qtw.QMenu()
        self.sc_tabs_ctx_menu.addAction('Close').triggered.connect(self._handle_tab_ctx_close)
        self.sc_tabs_ctx_menu.addAction('Close All').triggered.connect(self._handle_tab_ctx_close_all)

        self.sc_tree_model = None
        self.sc = None

        self.blender_manager = BlenderManager(self)
        self.actionOpenBlender.triggered.connect(self.open_blender)
        self.actionStartBlenderLink.triggered.connect(self.blender_manager.start_blenderlink)
        self.actionStopBlenderLink.triggered.connect(self.blender_manager.stop_blenderlink)
        self.actionBlenderLinkStatus.triggered.connect(self.blender_manager.show_blenderlink_status)

        self.dock_widgets = {}
        self.setup_dock_widgets()
        self._progress_tasks = {}

    def show(self):
        super().show()

        self.restoreGeometry(settings.value("windowGeometry"))
        self.restoreState(settings.value("windowState"))

        if self.settings.value('theme', 'dark').lower() == 'light':
            self.set_light_theme()
        else:
            self.set_dark_theme()

        if os.environ.get('SCDV_SC_PATH'):
            self.open_scdir.emit(os.environ['SCDV_SC_PATH'])
        elif len(sys.argv) > 1:
            arg_dir = Path(sys.argv[-1])
            if arg_dir.is_dir():
                self.open_scdir.emit(str(arg_dir))
        elif strtobool(self.settings.value('autoOpenRecent', 'false')):
            recent = self.settings.value('recent', [])
            if recent:
                self.open_scdir.emit(recent[0])

    def closeEvent(self, event) -> None:
        self.settings.setValue("windowGeometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        super().closeEvent(event)

    def _refresh_recent(self, recent=None):
        if recent is None:
            recent = self.settings.value('recent', [])

        recent = list({_: '' for _ in recent}.keys())  # remove duplicates without loosing the order

        prev_actions = self.menuRecent.actions()
        for a in prev_actions[:-2]:
            self.menuRecent.removeAction(a)
        prev_actions = prev_actions[-2:]

        labels = []
        for r in recent[:10]:
            label = Path(r).name if Path(r).name not in labels else str(r)
            a = qtw.QAction(label)
            a.triggered.connect(partial(self._handle_recent_selected, r))
            labels.append(label)
            self.menuRecent.insertAction(prev_actions[0], a)
        self.settings.setValue('recent', recent[:10])

    def _handle_recent_selected(self, scdir):
        self.open_scdir.emit(scdir)

    def setup_dock_widgets(self):
        fv = scdv.ui.widgets.dock_widgets.file_view.FileViewDock(self)
        fv.setObjectName('file_view')
        fv.setAllowedAreas(qtc.Qt.LeftDockWidgetArea | qtc.Qt.RightDockWidgetArea)
        self.dock_widgets['file_view'] = fv
        self.addDockWidget(qtc.Qt.LeftDockWidgetArea, fv)

    def open_blender(self, *args, **kwargs):
        self.blender_manager.launch_blender(*args, **kwargs)

    def show_export_ship_entity_dialog(self):
        dlg = EntityExporterDialog(self)
        dlg.exec_()

    def show_settings_dialog(self):
        dlg = SettingsDialog(self)
        dlg.exec_()

    def show_p4k_view(self):
        if 'p4k_view' not in self.dock_widgets:
            pv = scdv.ui.widgets.dock_widgets.p4k_widget.P4KViewDock(self)
            pv.setObjectName('p4k_view')
            pv.setAllowedAreas(qtc.Qt.LeftDockWidgetArea | qtc.Qt.RightDockWidgetArea)
            self.dock_widgets['p4k_view'] = pv
            self.addDockWidget(qtc.Qt.LeftDockWidgetArea, pv)
            self.resizeDocks([pv], [950], qtc.Qt.Horizontal)
            if 'file_view' in self.dock_widgets:
                self.tabifyDockWidget(pv, self.dock_widgets['file_view'])
        self.dock_widgets['p4k_view'].show()
        self.dock_widgets['p4k_view'].raise_()

    def show_dcb_view(self):
        if os.environ.get('SCDV_RELOAD_MODULES') and 'dcb_view' in self.dock_widgets:
            print('Reloading datacore widget')
            reload_scdv_modules('scdv.ui.widgets.dock_widgets.datacore_widget')
            # reload_scdv_modules('scdv.ui.widgets.dock_widgets.common')
            # reload_scdv_modules('scdv.ui.widgets.common')
            self.dock_widgets['dcb_view'].setParent(None)
            self.dock_widgets['dcb_view'].deleteLater()
            del self.dock_widgets['dcb_view']
        if 'dcb_view' not in self.dock_widgets:
            dv = scdv.ui.widgets.dock_widgets.datacore_widget.DCBViewDock(self)
            dv.setObjectName('dcb_view')
            dv.setAllowedAreas(qtc.Qt.LeftDockWidgetArea | qtc.Qt.RightDockWidgetArea)
            self.dock_widgets['dcb_view'] = dv
            self.addDockWidget(qtc.Qt.LeftDockWidgetArea, dv)
            self.resizeDocks([dv], [950], qtc.Qt.Horizontal)
        self.dock_widgets['dcb_view'].show()
        self.dock_widgets['dcb_view'].raise_()

    def show_local_files(self):
        self.dock_widgets['file_view'].show()
        self.dock_widgets['file_view'].raise_()

    def show_audio(self):
        if 'audio_view' not in self.dock_widgets:
            d = scdv.ui.widgets.dock_widgets.audio_widget.AudioViewDock(self)
            d.setObjectName('audio_view')
            d.setAllowedAreas(qtc.Qt.LeftDockWidgetArea | qtc.Qt.RightDockWidgetArea)
            self.dock_widgets['audio_view'] = d
            self.addDockWidget(qtc.Qt.RightDockWidgetArea, d)
            self.resizeDocks([d], [500], qtc.Qt.Horizontal)

        self.dock_widgets['audio_view'].show()
        self.dock_widgets['audio_view'].raise_()

    def show_tag_database(self):
        if 'tagdatabase_view' not in self.dock_widgets:
            dv = scdv.ui.widgets.dock_widgets.tagdatabase_widget.TagDatabaseViewDock(self)
            dv.setObjectName('tagdatabase_view')
            dv.setAllowedAreas(qtc.Qt.LeftDockWidgetArea | qtc.Qt.RightDockWidgetArea)
            self.dock_widgets['tagdatabase_view'] = dv
            self.addDockWidget(qtc.Qt.RightDockWidgetArea, dv)
            self.resizeDocks([dv], [500], qtc.Qt.Horizontal)
        self.dock_widgets['tagdatabase_view'].show()
        self.dock_widgets['tagdatabase_view'].raise_()

    def play_wem(self, wem_id):
        self.show_audio()
        self.dock_widgets['audio_view'].play_wem.emit(wem_id)

    def show_console(self):
        if 'console' not in self.dock_widgets:
            cw = dock_widgets.PyConsoleDockWidget(self)
            cw.setObjectName('console')
            cw.setAllowedAreas(qtc.Qt.BottomDockWidgetArea | qtc.Qt.LeftDockWidgetArea |
                               qtc.Qt.RightDockWidgetArea | qtc.Qt.TopDockWidgetArea)
            self.dock_widgets['console'] = cw
            self.addDockWidget(qtc.Qt.BottomDockWidgetArea, cw)
        self.dock_widgets['console'].show()
        self.dock_widgets['console'].raise_()

    def _update_status_bar(self):
        min = 0
        max = 0
        value = 0
        msgs = []
        for task in self._progress_tasks.values():
            if task['msg']:
                msgs.append(task['msg'])
            value += task['value']
            min += task['min']
            max += task['max']

        msg = ', '.join(msgs).strip()
        self.status_bar_progress.setFormat(f'{msg} - %v / %m - %p%' if msg else '%v / %m - %p%')
        if min != max:
            self.status_bar_progress.setRange(min, max)
            self.status_bar_progress.setValue(value)
            if self.status_bar_progress.isHidden():
                self.status_bar_progress.show()
        elif self.status_bar_progress.isVisible():
            self.status_bar_progress.hide()

    @Slot(str, str, int, int)
    def _handle_task_started(self, task, msg, min=0, max=0):
        self._progress_tasks[task] = {'msg': msg, 'value': min, 'min': min, 'max': max}
        self._update_status_bar()

    @Slot(str, int, int, int, str)
    def _handle_update_statusbar_progress(self, task, value, min=0, max=0, msg=''):
        if task not in self._progress_tasks:
            self._handle_task_started(task, msg, min, max)
        self._progress_tasks[task]['value'] = value
        if min:
            self._progress_tasks[task]['min'] = min
        if max:
            self._progress_tasks[task]['max'] = max
        if msg:
            self._progress_tasks[task]['msg'] = msg
        self._update_status_bar()

    @Slot(str, bool, str)
    def _handle_task_finished(self, task, success=True, msg=''):
        if task in self._progress_tasks:
            if msg:
                self._progress_tasks[task]['msg'] = msg
            elif not success:
                self._progress_tasks[task]['msg'] = msg if msg else f'{self._progress_tasks[task]["msg"]} failed'
            else:
                del self._progress_tasks[task]
        self._update_status_bar()

    @Slot(qtc.QPoint)
    def _handle_tab_ctx_menu(self, pos):
        self._sc_tab_ctx = self.sc_tabs.tabBar().tabAt(pos)
        self.sc_tabs_ctx_menu.exec_(self.sc_tabs.tabBar().mapToGlobal(pos))

    @Slot()
    def _handle_tab_ctx_close(self):
        if self._sc_tab_ctx is None:
            return
        self._handle_close_tab(self._sc_tab_ctx)
        self._sc_tab_ctx = None

    @Slot()
    def _handle_tab_ctx_close_all(self):
        for i in range(self.sc_tabs.count()):
            self._handle_close_tab(0)
        self._open_tabs = {}

    @Slot(int)
    def _handle_close_tab(self, index):
        obj_ids = [k for k, v in self._open_tabs.items() if v == index]
        widget = self.sc_tabs.widget(index)
        try:
            if hasattr(widget, 'close'):
                widget.close()
            self.sc_tabs.removeTab(index)
            for obj_id in obj_ids:
                del self._open_tabs[obj_id]
        except Exception:
            pass   # this lets the widget cancel out of being closed

    def set_tab_label(self, widget, label):
        index = self.sc_tabs.indexOf(widget)
        if index >= 0:
            self.sc_tabs.setTabText(index, label)

    def add_tab_widget(self, obj_id, widget, label, tooltip=None, show_after_add=True):
        if obj_id not in self._open_tabs:
            index = self.sc_tabs.addTab(widget, label)
            self._open_tabs[obj_id] = index
            self.sc_tabs.setTabToolTip(index, tooltip if tooltip is not None else str(obj_id))
        if show_after_add:
            return self.sc_tabs.setCurrentIndex(self._open_tabs[obj_id])

    @Slot(str)
    def _handle_open_scdir(self, scdir):
        if self.sc is not None:
            # TODO: handle asking if we want to close the current one first
            qm = qtw.QMessageBox(self)
            ret = qm.question(self, '', "This will close the current environment, continue?", qm.Yes | qm.No)
            if ret == qm.No:
                return
            self.handle_file_close()

        try:
            self.sc = StarCitizen(scdir)
            self._refresh_recent([scdir] + self.settings.value('recent', []))
            self.opened.emit(str(scdir))
            self.setWindowTitle(f'{scdir} ({self.sc.version_label})')
            loader = _SCLoader(self)
            qtc.QThreadPool.globalInstance().start(loader)
        except Exception as e:
            dlg = qtw.QErrorMessage(self)
            dlg.setWindowTitle('Could not open Star Citizen directory')
            dlg.showMessage(f'Could not open {scdir}: {e}')

    def clear_recent(self):
        self._refresh_recent([])

    def handle_file_open(self):
        def_dir = qtc.QDir.homePath()
        p4k_file, _ = qtw.QFileDialog.getOpenFileName(self, "Select Star Citizen Data.p4k", def_dir, "P4K (*.p4k)")

        if p4k_file:
            scdir = Path(p4k_file).parent.absolute()
        else:
            return

        self.open_scdir.emit(str(scdir))

    def handle_file_close(self):
        if self.sc is not None:
            self._handle_tab_ctx_close_all()
            for w in self.dock_widgets.values():
                self.removeDockWidget(w)
                w.deleteLater()
            self.dock_widgets = {}
            self.setup_dock_widgets()
            self.setWindowTitle('SCDV')
            self.status_bar_progress.hide()
            self.sc = None
            self.actionClose.setEnabled(False)
            qtg.QGuiApplication.processEvents()

    def set_light_theme(self):
        qtmodern.styles.light(QApplication.instance())

    def set_dark_theme(self):
        qtmodern.styles.dark(QApplication.instance())
