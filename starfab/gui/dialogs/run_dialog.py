import sys
from pathlib import Path

from qtpy import uic

from scdatatools.launcher import get_installed_sc_versions, get_library_folder
from scdatatools.utils import parse_bool
from starfab.gui import qtg, qtw, qtc
from starfab.resources import RES_PATH


class RunDialog(qtw.QDialog):
    def __init__(self, starfab):
        super().__init__(parent=None)
        self.starfab = starfab

        uic.loadUi(str(RES_PATH / "ui" / "RunDialog.ui"), self)  # Load the ui into self
        icon = qtg.QIcon()
        icon.addFile(
            str(RES_PATH / "starfab.ico"), qtc.QSize(), qtg.QIcon.Normal, qtg.QIcon.Off
        )
        self.setWindowIcon(icon)

        self.label_PixLogo.setPixmap(qtg.QPixmap(str(RES_PATH / "starfab_v.png")))

        self._ptu_data = ""
        self._live_data = ""
        self._handle_quick_load()

        self._browse_path = get_library_folder()
        self.lineEdit_BrowsePath.setText(str(self._browse_path))

        self.buttonBrowse.clicked.connect(self._handle_browse_file)
        self.buttonSettings.clicked.connect(self.starfab.show_settings_dialog)
        self.buttonBox.rejected.connect(self._handle_closed_event)
        self.buttonBox.accepted.connect(self._handle_load_browse)

        self.autoOpenMostRecent.setChecked(
            parse_bool(self.starfab.settings.value("autoOpenRecent", False))
        )
        self.autoOpenMostRecent.stateChanged.connect(self._save_settings)

        recent = self.starfab.settings.value("recent", [])
        self.recentList.addItems(recent)
        self.recentList.itemClicked.connect(self._handle_recent_clicked)
        self.recentList.itemDoubleClicked.connect(self._handle_recent_double_clicked)

    def _set_found_paths(self):
        sc_ver = get_installed_sc_versions()
        if sc_ver.get("PTU"):
            self.pushButton_quick_sc_ptu.setEnabled(True)
            self._ptu_data = Path(str(sc_ver["PTU"] / "Data.p4k"))
        if sc_ver.get("LIVE"):
            self.pushButton_quick_sc_live.setEnabled(True)
            self._live_data = Path(str(sc_ver["LIVE"] / "Data.p4k"))

    def handle_browse_path(self):
        if sys.platform == "win32":
            browse_path = get_library_folder()
        else:
            browse_path = qtc.QDir.homePath()
        return browse_path

    def _handle_recent_clicked(self):
        self.lineEdit_BrowsePath.setText(self.recentList.currentItem().text())

    def _handle_recent_double_clicked(self):
        self._handle_load(self.recentList.currentItem().text())

    def _handle_quick_load(self):
        self._set_found_paths()
        if self._ptu_data:
            self.pushButton_quick_sc_ptu.clicked.connect(
                lambda: self._handle_load(self._ptu_data)
            )
        if self._live_data:
            self.pushButton_quick_sc_live.clicked.connect(
                lambda: self._handle_load(self._live_data)
            )

    def _handle_load(self, p4k_file_or_scdir):
        if p4k_file_or_scdir:
            p4k_file_or_scdir = Path(p4k_file_or_scdir)
            if p4k_file_or_scdir.suffix.casefold() == ".p4k":
                scdir = p4k_file_or_scdir.parent.absolute()
            else:
                scdir = p4k_file_or_scdir.absolute()

            # if scdir.is_dir() and (scdir / "Data.p4k").is_file():
            #     self.hide()
            self.starfab.handle_file_open(scdir)
            self.destroy()
        else:
            return

    def _handle_load_browse(self):
        self._handle_load(Path(self.lineEdit_BrowsePath.text()))

    def _handle_closed_event(self):
        self.starfab.show()
        self.close()

    def _handle_browse_file(self):
        p4k_file, _ = qtw.QFileDialog.getOpenFileName(
            self, "Select Star Citizen Data.p4k", f"{self._browse_path}", "P4K (*.p4k)"
        )
        self._handle_load(p4k_file)

    def _save_settings(self, *args, **kwargs):
        self.starfab.settings.setValue(
            "autoOpenRecent", self.autoOpenMostRecent.isChecked()
        )

    ##TODO: evaluate if mainwindow, dialogs are correctly focusing as intended (https://stackoverflow.com/questions/12280815/pyqt-window-focus for coding insights)

    def closeEvent(self, event):
        self._handle_closed_event()

    def keyPressEvent(self, event):
        if event.key() == qtc.Qt.Key_Escape:
            self._handle_closed_event()
