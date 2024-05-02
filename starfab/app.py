import os
import sys
import time
from os import path
from pathlib import Path
from functools import partial

import qtawesome as qta
from qtpy import uic
from qtpy.QtCore import Signal, Slot, QTimer, Qt
from qtpy.QtGui import QKeySequence, QKeyEvent, QPixmap
from qtpy.QtWidgets import QMainWindow


import starfab.gui.widgets.dock_widgets.datacore_widget
import starfab.gui.widgets.dock_widgets.file_view

from scdatatools.sc import StarCitizen
from starfab.gui.widgets.pages.content import ContentView
from starfab.planets import HAS_COMPUSHADY
from . import __version__, updates
from .blender import BlenderManager
from .gui import qtg, qtw, qtc
from .gui.RibbonButton import RibbonButton
from .gui.RibbonTextbox import RibbonTextbox
from .gui.RibbonWidget import *
from .gui.dialogs.run_dialog import RunDialog
from .gui.dialogs.settings_dialog import SettingsDialog
from .gui.dialogs.splash_screen import StarFabSplashScreen
from .gui.utils import icon_for_path
from .gui.widgets import dock_widgets
from starfab.gui.widgets.pages import *
from .log import getLogger
from .models import StarCitizenManager
from .resources import RES_PATH
from .settings import settings
from .utils import reload_starfab_modules, parsebool

logger = getLogger(__name__)


class StarFab(QMainWindow):
    task_started = Signal(str, str, int, int)
    update_status_progress = Signal(str, int, int, int, str)
    task_finished = Signal(str, bool, str)
    close = Signal()

    open_scdir = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        qta.set_defaults(color="gray")

        uic.loadUi(
            str(RES_PATH / "ui" / "mainwindow.ui"), self
        )  # Load the ui into self
        self.setWindowTitle("StarFab")
        self.setWindowIcon(qtg.QIcon(str(RES_PATH / "starfab.png")))
        self.setDockNestingEnabled(False)

        self.settings = settings
        self._refresh_recent()

        self.task_started.connect(self._handle_task_started)
        self.update_status_progress.connect(self._handle_update_statusbar_progress)
        self.task_finished.connect(self._handle_task_finished)
        self.open_scdir.connect(self._handle_open_scdir)

        self.resize(1900, 900)

        self.actionSettings.triggered.connect(self.show_settings_dialog)

        self.actionOpen.triggered.connect(self.show_run_dialog)
        self.actionClose.triggered.connect(self.handle_file_close)
        self.actionClose.setEnabled(False)
        self.actionQuit.triggered.connect(self.close)

        self.actionAudio.triggered.connect(self.show_audio)
        self.actionConsole.triggered.connect(self.show_console)
        self.actionDatacore.triggered.connect(self.show_dcb_view)
        self.actionLocal_Files.triggered.connect(self.show_local_files)
        self.actionP4K.triggered.connect(self.show_p4k_view)
        self.actionTag_Database.triggered.connect(self.show_tag_database)

        self.actionAbout.triggered.connect(
            lambda: qtg.QDesktopServices.openUrl(
                "https://gitlab.com/scmodding/tools/starfab"
            )
        )
        self.actionClear_Recent.triggered.connect(self.clear_recent)

        self.status_bar_progress = qtw.QProgressBar(self)
        self.statusBar.addPermanentWidget(self.status_bar_progress)
        self.status_bar_progress.setFormat("%v / %m - %p%")
        self.status_bar_progress.hide()

        # show/hide menubar toggle, will be obfuscated in release in favor of ribbon bar
        self.menu_toggled = QShortcut(QKeySequence("ALT+M"), self)
        self.menu_toggled.activated.connect(self.toggle_menu)

        self._open_tabs = {}

        self.sc_tree_model = None
        self.sc_manager = StarCitizenManager(self)
        self.sc_manager.loaded.connect(self._handle_sc_loaded)
        self.sc_manager.datacore_model.loaded.connect(self._handle_datacore_loaded)
        self.sc_manager.load_failed.connect(self._load_failed)
        self.sc_manager.preparing_to_load.connect(self._loading)

        self.blender_manager = BlenderManager(self)
        self.blender_manager.updated.connect(self._blender_manager_updated)
        self.blender_manager.link_started.connect(self._blender_manager_updated)
        self.blender_manager.link_stopped.connect(self._blender_manager_updated)

        self.actionOpenBlender.triggered.connect(self.open_blender)
        self.actionStartBlenderLink.triggered.connect(self.start_blender_link)
        self.actionStopBlenderLink.triggered.connect(self.stop_blender_link)
        self.actionBlenderLinkStatus.triggered.connect(
            self.blender_manager.show_blenderlink_status
        )

        self.splash = None
        self.data_page_btn = None
        self.content_page_btn = None
        self.nav_page_btn = None
        self.planets_page_btn = None

        # -------------      actions       -----------------
        # keyboard shortcuts, for QKeySequence see https://doc.qt.io/qtforpython-5/PySide2/QtGui/QKeySequence.html

        self._open_action = self.actionOpen
        self.actionOpen.setIcon(qta.icon("ph.folder-open"))
        self._close_action = self.actionClose
        self._open_blender_action = self.actionOpenBlender
        self.actionOpenBlender.setIcon(qta.icon("mdi.blender-software"))
        self._start_blender_link = self.actionStartBlenderLink
        self.actionStartBlenderLink.setIcon(qta.icon("msc.debug-start"))
        self._stop_blender_link = self.actionStopBlenderLink
        self.actionStopBlenderLink.setIcon(qta.icon("msc.debug-stop"))
        self._blender_install_addon = self.actionInstall_Blender_Add_on
        self.actionInstall_Blender_Add_on.setIcon(qta.icon("ri.install-line"))
        self.actionDataView.setIcon(qta.icon("ph.tree-structure"))
        self.actionDataView.triggered.connect(self._handle_workspace_action)
        self.actionContentView.setIcon(qta.icon("ph.package"))
        self.actionContentView.triggered.connect(self._handle_workspace_action)
        self.actionNavView.setIcon(qta.icon("mdi6.map-marker-path"))
        self.actionNavView.triggered.connect(self._handle_workspace_action)
        if HAS_COMPUSHADY:
            self.actionPlanetView.setIcon(qta.icon("ph.planet"))
            self.actionPlanetView.triggered.connect(self._handle_workspace_action)

        self._open_settings = self.actionSettings
        self.actionSettings.setIcon(qta.icon("msc.settings-gear"))
        self._show_console = self.actionConsole
        self.actionSettings.setIcon(qta.icon("msc.settings-gear"))

        self.actionConsole.setIcon(qta.icon("msc.debug-console"))
        self._about_action = self.add_action(
            "About", "ph.question", "About QupyRibbon", True, self.on_about
        )
        self._license_action = self.add_action(
            "License",
            "ph.newspaper-clipping",
            "Licence for this software",
            True,
            self.on_license,
        )

        # -------------      textboxes       -----------------
        self.lineEdit_BlenderPath = RibbonTextbox("", 200, 400)
        self.lineEdit_BlenderVersion = RibbonTextbox("", 80, 100)
        self.lineEdit_LinkStatus = RibbonTextbox("", 80, 100)

        # Ribbon

        self._ribbon = RibbonWidget(self)
        self.addToolBar(self._ribbon)
        self.menuBar.hide()
        self.init_ribbon()

        self.actionDataView.triggered.connect(self.handle_workspace)
        self.actionContentView.triggered.connect(self.handle_workspace)
        self.actionNavView.triggered.connect(self.handle_workspace)

        self.page_DataView = DataView(self)
        self.stackedWidgetWorkspace.addWidget(self.page_DataView)

        self.page_ContentView = ContentView(self)
        self.stackedWidgetWorkspace.addWidget(self.page_ContentView)

        self.page_NavView = NavView(self)
        self.stackedWidgetWorkspace.addWidget(self.page_NavView)

        if HAS_COMPUSHADY:
            self.page_PlanetView = PlanetView(self)
            self.stackedWidgetWorkspace.addWidget(self.page_PlanetView)

        self.dock_widgets = {}
        self.setup_dock_widgets()
        self._progress_tasks = {}

    def _blender_manager_updated(self):
        self.lineEdit_BlenderPath.setText(str(self.blender_manager.blender))
        self.lineEdit_BlenderVersion.setText(str(self.blender_manager.blender_version))
        if self.blender_manager.is_blenderlink_running():
            self.lineEdit_LinkStatus.setText(
                str(self.blender_manager.blenderlink_port())
            )
            self.lineEdit_LinkStatus.setStyleSheet("color: green")
        else:
            self.lineEdit_LinkStatus.setText("Not Running")
            self.lineEdit_LinkStatus.setStyleSheet("color: red")

    @property
    def sc(self) -> StarCitizen:
        return self.sc_manager.sc

    def add_action(
        self, caption, icon_name, status_tip, icon_visible, connection, shortcut=None
    ):
        # example '''self._open_action = self.add_action("Open", "copy", "Open file", True, self.on_open_file, QKeySequence.Open)'''
        action = QAction(qta.icon(icon_name), caption, self)
        action.setStatusTip(status_tip)
        action.triggered.connect(connection)
        action.setIconVisibleInMenu(icon_visible)
        if shortcut is not None:
            action.setShortcuts(shortcut)
        self.addAction(action)
        return action

    def init_ribbon(self):
        # tab > pane > button(s)
        # create home tab
        self.home_tab = self._ribbon.add_ribbon_tab("Home")
        # create pane "file" within the first home tab
        self.file_pane = self.home_tab.add_ribbon_pane("File")
        # add buttons to the file pane in the home tab
        self.file_pane.add_ribbon_widget(RibbonButton(self, self._open_action, True))
        # file_pane.add_ribbon_widget(RibbonButton(self, self._close_action, True)) ##removed for now, may not keep in workflow as ribbon button

        self.workspace_panel = self.home_tab.add_ribbon_pane("Workspace")
        self.data_page_btn = RibbonButton(self, self.actionDataView, True)
        self.data_page_btn.setAutoExclusive(True)
        self.data_page_btn.released.connect(self.handle_workspace)
        self.workspace_panel.add_ribbon_widget(self.data_page_btn)

        self.content_page_btn = RibbonButton(self, self.actionContentView, True)
        self.content_page_btn.setAutoExclusive(True)
        self.content_page_btn.released.connect(self.handle_workspace)
        self.workspace_panel.add_ribbon_widget(self.content_page_btn)

        self.nav_page_btn = RibbonButton(self, self.actionNavView, True)
        self.nav_page_btn.setAutoExclusive(True)
        self.nav_page_btn.released.connect(self.handle_workspace)
        self.workspace_panel.add_ribbon_widget(self.nav_page_btn)

        if HAS_COMPUSHADY:
            self.planets_page_btn = RibbonButton(self, self.actionPlanetView, True)
            self.planets_page_btn.setAutoExclusive(True)
            self.planets_page_btn.released.connect(self.handle_workspace)
            self.workspace_panel.add_ribbon_widget(self.planets_page_btn)

        self.options_panel = self.home_tab.add_ribbon_pane("Options")
        self.options_panel.add_ribbon_widget(
            RibbonButton(self, self._open_settings, True)
        )

        self.debug_panel = self.home_tab.add_ribbon_pane("Debug")
        self.debug_panel.add_ribbon_widget(RibbonButton(self, self._show_console, True))

        self.home_tab.add_spacer()

        self.blender_tab = self._ribbon.add_ribbon_tab("Blender")
        self.blender_panel = self.blender_tab.add_ribbon_pane("Blender")
        self.blender_panel.add_ribbon_widget(
            RibbonButton(self, self._open_blender_action, True)
        )
        self.blender_panel.add_ribbon_widget(
            RibbonButton(self, self._start_blender_link, True)
        )
        self.blender_panel.add_ribbon_widget(
            RibbonButton(self, self._stop_blender_link, True)
        )
        self.blender_info = self.blender_tab.add_ribbon_pane("Blender Info")
        grid = self.blender_info.add_grid_widget(500)
        grid.addWidget(QLabel("Blender Path"), 0, 0, 1, 1)
        grid.addWidget(QLabel("Link Status"), 1, 2, 1, 1)
        grid.addWidget(QLabel("Blender Version"), 1, 0, 1, 1)
        grid.addWidget(self.lineEdit_BlenderPath, 0, 1, 1, 3)
        grid.addWidget(self.lineEdit_LinkStatus, 1, 3, 1, 1)
        grid.addWidget(self.lineEdit_BlenderVersion, 1, 1, 1, 1)
        grid.addWidget(
            RibbonButton(self, self._blender_install_addon, False), 2, 0, 1, 2
        )
        self.blender_tab.add_spacer()

        self.about_tab = self._ribbon.add_ribbon_tab("About")
        self.info_panel = self.about_tab.add_ribbon_pane("Info")
        self.info_panel.add_ribbon_widget(RibbonButton(self, self._about_action, True))
        # self.info_panel.add_ribbon_widget(RibbonButton(self, self._license_action, True))
        self.about_tab.add_spacer()

    def on_open_file(self):
        pass

    def on_save_to_excel(self):
        pass

    def on_save(self):
        pass

    def on_copy(self):
        pass

    def on_paste(self):
        pass

    def on_zoom(self):
        pass

    def toggle_menu(self):
        if self.menuBar.isHidden():
            self.menuBar.show()
        else:
            self.menuBar.hide()

    def on_about(self):
        text = f"""<pre>StarFab {__version__}
        
Crafted by the community, shaped by visionaries.

<a href="https://gitlab.com/scmodding/tools/starfab"
    style="color: red; text-decoration: none"
>https://gitlab.com/scmodding/tools/starfab</a>

Contributors:
    ventorvar
    vmxeo
    th3st0rmtr00p3r
</pre>
"""
        msg = QMessageBox(self)
        msg.setTextFormat(qtc.Qt.RichText)
        msg.setStyleSheet(
            """
        QMessageBox QLabel {
        }
        """
        )
        msg.setText(text)
        msg.setStandardButtons(qtw.QMessageBox.Ok)
        msg.show()

    def on_license(self):
        pass
        ##TODO, implement
        """
        file = open('LICENSE', 'r')
        lic = file.read()
        QMessageBox().information(self, "License", lic)
        """

    def startup(self):
        self.restoreGeometry(settings.value("windowGeometry"))
        self.restoreState(settings.value("windowState"))

        updates.check_and_notify()
        if os.environ.get("STARFAB_SC_PATH"):
            self.open_scdir.emit(os.environ["STARFAB_SC_PATH"])
        elif len(sys.argv) > 1:
            arg_dir = Path(sys.argv[-1])
            if arg_dir.is_dir():
                self.open_scdir.emit(str(arg_dir))
        elif parsebool(self.settings.value("autoOpenRecent", "false")):
            recent = self.settings.value("recent", [])
            if recent:
                self.open_scdir.emit(recent[0])
        else:
            self.hide()
            self.show_run_dialog()

    def show(self):
        super().show()
        if self.splash is not None:
            self.splash.hide()
            self.splash.deleteLater()
            self.splash = None
        self.handle_workspace(settings.value("defaultWorkspace", "data"))

    def closeEvent(self, event) -> None:
        try:
            self.settings.setValue("windowGeometry", self.saveGeometry())
            self.settings.setValue("windowState", self.saveState())
            self.handle_file_close()
            self.hide()
            self.close.emit()
        finally:
            print("closing!")
            #sys.exit(0)

    def _refresh_recent(self, recent=None):
        if recent is None:
            recent = self.settings.value("recent", [])

        recent = list(
            {_: "" for _ in recent}.keys()
        )  # remove duplicates without loosing the order

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
        self.settings.setValue("recent", recent[:10])

    def _handle_recent_selected(self, scdir):
        self.open_scdir.emit(scdir)

    def setup_dock_widgets(self):
        self.handle_workspace("data")
        """
        fv = starfab.gui.widgets.dock_widgets.file_view.FileViewDock(self)
        fv.setObjectName('file_view')
        fv.setAllowedAreas(qtc.Qt.LeftDockWidgetArea | qtc.Qt.RightDockWidgetArea)
        self.dock_widgets['file_view'] = fv
        self.addDockWidget(qtc.Qt.LeftDockWidgetArea, fv)
        """

    def open_blender(self, *args, **kwargs):
        self.blender_manager.launch_blender(*args, **kwargs)

    def start_blender_link(self):
        self.blender_manager.start_blenderlink()

    def stop_blender_link(self):
        self.blender_manager.stop_blenderlink()

    def splash_screen(self):
        self.splash = StarFabSplashScreen(self)
        self.splash.show()
        self.splash.raise_()

        # QTimer.singleShot(2000, self.show_run_dialog)

    def show_run_dialog(self):
        self.hide()
        dlg = RunDialog(self)
        dlg.show()
        return dlg

    def show_settings_dialog(self):
        dlg = SettingsDialog(self)
        dlg.exec_()

    def show_p4k_view(self):
        if "p4k_view" not in self.dock_widgets:
            pv = starfab.gui.widgets.dock_widgets.p4k_widget.P4KViewDock(self)
            pv.setObjectName("p4k_view")
            # pv.setAllowedAreas(qtc.Qt.LeftDockWidgetArea | qtc.Qt.RightDockWidgetArea)
            self.dock_widgets["p4k_view"] = pv
            # self.addDockWidget(qtc.Qt.LeftDockWidgetArea, pv)
            # self.resizeDocks([pv], [500], qtc.Qt.Horizontal)
            if "file_view" in self.dock_widgets:
                self.tabifyDockWidget(pv, self.dock_widgets["file_view"])
        self.dock_widgets["p4k_view"].show()
        self.dock_widgets["p4k_view"].raise_()

    def show_dcb_view(self):
        if os.environ.get("STARFAB_RELOAD_MODULES") and "dcb_view" in self.dock_widgets:
            print("Reloading datacore widget")
            reload_starfab_modules("starfab.gui.widgets.dock_widgets.datacore_widget")
            # reload_starfab_modules('starfab.gui.widgets.dock_widgets.common')
            # reload_starfab_modules('starfab.gui.widgets.common')
            self.dock_widgets["dcb_view"].setParent(None)
            self.dock_widgets["dcb_view"].deleteLater()
            del self.dock_widgets["dcb_view"]
        if "dcb_view" not in self.dock_widgets:
            dv = starfab.gui.widgets.dock_widgets.datacore_widget.DCBTreeWidget(self)
            dv.setObjectName("dcb_view")
            # dv.setAllowedAreas(qtc.Qt.LeftDockWidgetArea | qtc.Qt.RightDockWidgetArea)
            self.dock_widgets["dcb_view"] = dv
            # self.addDockWidget(qtc.Qt.LeftDockWidgetArea, dv)
            # self.resizeDocks([dv], [500], qtc.Qt.Horizontal)
        self.dock_widgets["dcb_view"].show()
        self.dock_widgets["dcb_view"].raise_()

    def show_local_files(self):
        if "file_view" not in self.dock_widgets:
            fv = starfab.gui.widgets.dock_widgets.file_view.FileViewDock(self)
            fv.setObjectName("file_view")
            fv.setAllowedAreas(qtc.Qt.LeftDockWidgetArea | qtc.Qt.RightDockWidgetArea)
            self.dock_widgets["file_view"] = fv
            self.addDockWidget(qtc.Qt.LeftDockWidgetArea, fv)
        self.dock_widgets["file_view"].show()
        self.dock_widgets["file_view"].raise_()

    def show_audio(self):
        if "audio_view" not in self.dock_widgets:
            d = starfab.gui.widgets.dock_widgets.audio_widget.AudioViewDock(self)
            d.setObjectName("audio_view")
            d.setAllowedAreas(qtc.Qt.LeftDockWidgetArea | qtc.Qt.RightDockWidgetArea)
            self.dock_widgets["audio_view"] = d
            self.addDockWidget(qtc.Qt.RightDockWidgetArea, d)
            self.resizeDocks([d], [500], qtc.Qt.Horizontal)

        self.dock_widgets["audio_view"].show()
        self.dock_widgets["audio_view"].raise_()

    def show_tag_database(self):
        if "tagdatabase_view" not in self.dock_widgets:
            dv = (
                starfab.gui.widgets.dock_widgets.tagdatabase_widget.TagDatabaseViewDock(
                    self
                )
            )
            dv.setObjectName("tagdatabase_view")
            # dv.setAllowedAreas(qtc.Qt.LeftDockWidgetArea | qtc.Qt.RightDockWidgetArea)
            self.dock_widgets["tagdatabase_view"] = dv
            # self.addDockWidget(qtc.Qt.RightDockWidgetArea, dv)
            # self.resizeDocks([dv], [500], qtc.Qt.Horizontal)
        self.dock_widgets["tagdatabase_view"].show()
        self.dock_widgets["tagdatabase_view"].raise_()

    def play_wem(self, wem_id):
        self.show_audio()
        self.dock_widgets["audio_view"].play_wem.emit(wem_id)

    def show_console(self):
        if "console" not in self.dock_widgets:
            cw = dock_widgets.PyConsoleDockWidget(self)
            cw.setObjectName("console")
            self.dock_widgets["console"] = cw
            self.addDockWidget(qtc.Qt.BottomDockWidgetArea, cw)
            self.dock_widgets["console"].show()
            self.dock_widgets["console"].raise_()

        elif self.actionConsole.isChecked():
            self.dock_widgets["console"].show()

        else:
            self.dock_widgets["console"].hide()

    def _update_status_bar(self):
        if self.splash is not None:
            self.splash.update_status_bar(self._progress_tasks)

        min = 0
        max = 0
        value = 0
        msgs = []
        for task in self._progress_tasks.values():
            if task["msg"]:
                msgs.append(task["msg"])
            value += task["value"]
            min += task["min"]
            max += task["max"]

        msg = ", ".join(msgs).strip()
        self.status_bar_progress.setFormat(
            f"{msg} - %v / %m - %p%" if msg else "%v / %m - %p%"
        )
        if min != max:
            self.status_bar_progress.setRange(min, max)
            self.status_bar_progress.setValue(value)
            if self.status_bar_progress.isHidden():
                self.status_bar_progress.show()
        elif self.status_bar_progress.isVisible():
            self.status_bar_progress.hide()

    def _handle_datacore_loaded(self):
        self.actionExportEntity.setEnabled(True)
        self.show()

    @Slot(str, str, int, int)
    def _handle_task_started(self, task, msg, min=0, max=0):
        self._progress_tasks[task] = {"msg": msg, "value": min, "min": min, "max": max}
        self._update_status_bar()

    @Slot(str, int, int, int, str)
    def _handle_update_statusbar_progress(self, task, value, min=0, max=0, msg=""):
        if task not in self._progress_tasks:
            self._handle_task_started(task, msg, min, max)
        self._progress_tasks[task]["value"] = value
        if min:
            self._progress_tasks[task]["min"] = min
        if max:
            self._progress_tasks[task]["max"] = max
        if msg:
            self._progress_tasks[task]["msg"] = msg
        self._update_status_bar()

    @Slot(str, bool, str)
    def _handle_task_finished(self, task, success=True, msg=""):
        if task in self._progress_tasks:
            if msg:
                QMessageBox.information(None, "Task Completed", msg)
                self._progress_tasks[task]["msg"] = msg
            elif not success:
                msg = msg if msg else f'{self._progress_tasks[task]["msg"]} failed'
                QMessageBox.warning(None, "Task Failed", msg)
            del self._progress_tasks[task]
        self._update_status_bar()

    @Slot(qtc.QPoint)
    def _handle_tab_ctx_menu(self, pos):
        self._sc_tab_ctx = self.page_DataView.sc_tabs.tabBar().tabAt(pos)
        self.page_DataView.sc_tabs_ctx_menu.exec_(
            self.page_DataView.sc_tabs.tabBar().mapToGlobal(pos)
        )

    @Slot()
    def _handle_tab_ctx_close(self):
        if self._sc_tab_ctx is None:
            return
        self._handle_close_tab(self._sc_tab_ctx)
        self._sc_tab_ctx = None

    @Slot()
    def _handle_tab_ctx_close_other(self):
        if self._sc_tab_ctx is None:
            return
        self._handle_tab_ctx_close_left()
        self._sc_tab_ctx = 0
        self._handle_tab_ctx_close_right()

    @Slot()
    def _handle_tab_ctx_close_left(self):
        if (widget := self.page_DataView.sc_tabs.widget(self._sc_tab_ctx)) is None:
            return
        while self.page_DataView.sc_tabs.indexOf(widget) > 0:
            self._handle_close_tab(0)
        self._sc_tab_ctx = None

    @Slot()
    def _handle_tab_ctx_close_right(self):
        if (widget := self.page_DataView.sc_tabs.widget(self._sc_tab_ctx)) is None:
            return
        while self.page_DataView.sc_tabs.indexOf(widget) < (
            self.page_DataView.sc_tabs.count() - 1
        ):
            self._handle_close_tab(self._sc_tab_ctx + 1)
        self._sc_tab_ctx = None

    @Slot()
    def _handle_tab_ctx_close_all(self):
        while self._open_tabs:
            self._handle_close_tab(
                self.page_DataView.sc_tabs.indexOf(next(iter(self._open_tabs.values())))
            )
        assert len(self._open_tabs) == 0
        self._sc_tab_ctx = None

    @Slot(int)
    def _handle_close_tab(self, index):
        if (widget := self.page_DataView.sc_tabs.widget(index)) is None:
            return

        obj_ids = [k for k, v in self._open_tabs.items() if v == widget]
        try:
            if hasattr(widget, "close"):
                widget.close()
            widget.deleteLater()
            self.page_DataView.sc_tabs.removeTab(index)
            for obj_id in obj_ids:
                del self._open_tabs[obj_id]
        except Exception:
            pass  # this lets the widget cancel out of being closed

    def set_tab_label(self, widget, label):
        if (index := self.page_DataView.sc_tabs.indexOf(widget)) >= 0:
            self.page_DataView.sc_tabs.setTabText(index, label)

    def switch_to_tab_widget(self, obj_id) -> bool:
        """Switch to the tab for `obj_id` if it exists. Returns True if switched, or False if the tab doesnt exist"""
        if obj_id in self._open_tabs:
            self.page_DataView.sc_tabs.setCurrentWidget(self._open_tabs[obj_id])
            return True
        return False

    def add_tab_widget(self, obj_id, widget, label, tooltip=None, show_after_add=True):
        if obj_id not in self._open_tabs:
            index = self.page_DataView.sc_tabs.addTab(
                widget, icon_for_path(obj_id, default=True), label
            )
            self._open_tabs[obj_id] = widget
            self.page_DataView.sc_tabs.setTabToolTip(
                index, tooltip if tooltip is not None else str(obj_id)
            )
            if (btn := self.page_DataView.sc_tabs.tabBar().tabButton(index, qtw.QTabBar.RightSide)) is not None:
                btn.setFixedSize(14, 14)
        if show_after_add:
            return self.page_DataView.sc_tabs.setCurrentWidget(self._open_tabs[obj_id])

    @Slot()
    def _handle_sc_loaded(self):
        self.setWindowTitle(f"{self.sc.game_folder} ({self.sc.version_label})")

    @Slot(str)
    def _handle_open_scdir(self, scdir):
        if self.sc_manager.sc is not None:
            # TODO: handle asking if we want to close the current one first
            qm = qtw.QMessageBox(self)
            ret = qm.question(
                self,
                "",
                "This will close the current environment, continue?",
                qm.Yes | qm.No,
            )
            if ret == qm.No:
                return
            self.handle_file_close()

        try:
            self.hide()
            self._refresh_recent([scdir] + self.settings.value("recent", []))
            self.sc_manager.load_sc.emit(scdir)
            self.actionDataView.setChecked(True)
            self.actionClose.setEnabled(True)
        except Exception as e:
            self._load_failed(str(e), exc_info=e)

    def _loading(self):
        self.splash_screen()

    def _load_failed(self, msg, exc_info=None):
        logger.exception(f'Failed to load Star Citizen', exc_info=exc_info)
        run = self.show_run_dialog()
        dlg = qtw.QErrorMessage(parent=run)
        dlg.setWindowTitle("Could not open Star Citizen directory")
        dlg.showMessage(f"Could not open Star Citizen: {msg}")
        dlg.raise_()

    def clear_recent(self):
        self._refresh_recent([])

    def handle_file_open(self, scdir):
        self.show()
        self.open_scdir.emit(str(scdir))

    def handle_file_close(self):
        if self.sc is not None:
            self._handle_tab_ctx_close_all()
            for w in self.dock_widgets.values():
                self.removeDockWidget(w)
                w.deleteLater()
            self.dock_widgets = {}
            self.setup_dock_widgets()
            self.setWindowTitle("StarFab")
            self.status_bar_progress.hide()
            self.sc_manager.unload.emit()
            self.actionClose.setEnabled(False)
            qtg.QGuiApplication.processEvents()
            # self.show_run_dialog()

    def _handle_workspace_action(self):
        view = self.sender().text().casefold()
        self.handle_workspace(view)

    @Slot()
    def handle_workspace(self, view=None, *args, **kwargs):
        self.workspace_btns = [self.data_page_btn,
                               self.content_page_btn,
                               self.nav_page_btn]

        if HAS_COMPUSHADY:
            self.workspace_btns.append(self.planets_page_btn)

        def _clear_checked(self):
            for btn in self.workspace_btns:
                btn.setChecked(False)

        _clear_checked(self)

        if view is None:
            return

        else:
            self.stackedWidgetWorkspace.setCurrentWidget(self.page_OpenView)

        logger.info(f"Switching to workspace: {view}")

        if self.sc is None:
            _clear_checked(self)
        elif view == "data":
            self.data_page_btn.setChecked(True)
            self.stackedWidgetWorkspace.setCurrentWidget(self.page_DataView)
        elif view == "content":
            self.content_page_btn.setChecked(True)
            self.stackedWidgetWorkspace.setCurrentWidget(self.page_ContentView)
        elif view == "nav":
            self.nav_page_btn.setChecked(True)
            self.stackedWidgetWorkspace.setCurrentWidget(self.page_NavView)
        elif view == "planets":
            self.planets_page_btn.setChecked(True)
            self.stackedWidgetWorkspace.setCurrentWidget(self.page_PlanetView)