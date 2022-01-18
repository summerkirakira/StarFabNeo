import json
from pathlib import Path
from functools import partial

from qtpy import uic
from qtpy.QtCore import Signal, Slot
import qtawesome as qta
import qtvscodestyle as qtvsc

from starfab.log import getLogger
from starfab.settings import configure_defaults
from starfab.gui import qtw
from starfab.resources import RES_PATH
from scdatatools.utils import parse_bool

button_group_2 = {"0": "data", "1": "content", "2": "toolbox"}

logger = getLogger(__name__)


class SettingsDialog(qtw.QDialog):
    def __init__(self, starfab):
        super().__init__(parent=None)
        self.starfab = starfab
        uic.loadUi(
            str(RES_PATH / "ui" / "SettingsDialog.ui"), self
        )  # Load the ui into self

        self.themes = {}
        for theme_file in (RES_PATH / "stylesheets").glob("*.json"):
            try:
                theme = qtvsc.loads_jsonc(theme_file.open().read())
                self.themes[theme.get('name', theme_file.stem)] = theme_file
            except Exception as e:
                logger.exception(f'Failed to load theme {theme_file}')

        self.theme.addItems(list(sorted(self.themes.keys())))

        self._parse_settings()

        open_dir_icon = qtw.QApplication.style().standardIcon(qtw.QStyle.SP_DirIcon)
        cgfconvfind = self.cgfconverterPath.addAction(
            open_dir_icon, qtw.QLineEdit.TrailingPosition
        )
        cgfconvfind.triggered.connect(
            partial(self._handle_path_chooser, self.cgfconverterPath)
        )

        texconvfind = self.texconvPath.addAction(
            open_dir_icon, qtw.QLineEdit.TrailingPosition
        )
        texconvfind.triggered.connect(
            partial(self._handle_path_chooser, self.texconvPath)
        )

        exportsdirfind = self.lineEdit_Exports_Directory.addAction(
            open_dir_icon, qtw.QLineEdit.TrailingPosition
        )
        exportsdirfind.triggered.connect(
            partial(
                self._handle_path_chooser, self.lineEdit_Exports_Directory, dir=True
            )
        )
        self.buttonGroup_2.buttonClicked.connect(self.button_group)

        self.autoOpenMostRecent.stateChanged.connect(self._save_settings)
        self.preloadTagDatabase.stateChanged.connect(self._save_settings)
        self.preloadAudioDatabase.stateChanged.connect(self._save_settings)
        self.preloadLocalization.stateChanged.connect(self._save_settings)
        self.theme.currentTextChanged.connect(self._save_settings)
        self.cryxmlbFormat.currentTextChanged.connect(self._save_settings)
        self.cgfconverterPath.textChanged.connect(self._save_settings)
        self.texconvPath.textChanged.connect(self._save_settings)
        self.lineEdit_Exports_Directory.textChanged.connect(self._save_settings)

        self.buttonBox.button(qtw.QDialogButtonBox.RestoreDefaults).clicked.connect(
            self._reset_settings
        )
        self.buttonBox.accepted.connect(self.close)

    @Slot()
    def button_group(self):
        indexOfChecked = [
            self.sender().buttons()[x].isChecked()
            for x in range(len(self.sender().buttons()))
        ].index(True)
        button_key = button_group_2[f"{indexOfChecked}"]
        self.starfab.settings.setValue("defaultWorkspace", button_key)

    def _parse_settings(self):
        self.autoOpenMostRecent.setChecked(
            parse_bool(self.starfab.settings.value("autoOpenRecent"))
        )
        self.lineEdit_Exports_Directory.setText(
            self.starfab.settings.value("exportDirectory")
        )
        self.preloadTagDatabase.setChecked(
            parse_bool(self.starfab.settings.value("preloadTagDatabase"))
        )
        self.preloadAudioDatabase.setChecked(
            parse_bool(self.starfab.settings.value("preloadAudioDatabase"))
        )
        self.preloadLocalization.setChecked(
            parse_bool(self.starfab.settings.value("preloadLocalization"))
        )
        theme = self.starfab.settings.value("theme")
        if theme in list(self.themes.values()):
            self.theme.setCurrentText(next(iter(n for n, f in self.themes.items() if f == theme)))
        elif theme in self.themes:
            self.theme.setCurrentText(theme)
        self.cryxmlbFormat.setCurrentText(
            self.starfab.settings.value("cryxmlbConversionFormat")
        )
        self.cgfconverterPath.setText(
            self.starfab.settings.value("external_tools/cgf-converter")
        )
        self.texconvPath.setText(self.starfab.settings.value("external_tools/texconv"))

    def _reset_settings(self):
        configure_defaults(self.starfab.settings)
        self.close()

    def _save_settings(self, *args, **kwargs):
        logger.debug("Saving settings")
        self.starfab.settings.setValue(
            "autoOpenRecent", self.autoOpenMostRecent.isChecked()
        )
        self.starfab.settings.setValue(
            "cyxmlbConversionFormat", self.cryxmlbFormat.currentText()
        )
        self.starfab.settings.setValue(
            "preloadTagDatabase", self.preloadTagDatabase.isChecked()
        )
        self.starfab.settings.setValue(
            "preloadAudioDatabase", self.preloadAudioDatabase.isChecked()
        )
        self.starfab.settings.setValue(
            "preloadLocalization", self.preloadLocalization.isChecked()
        )
        if self.theme.currentText() != self.starfab.settings.value("theme", "Monokai Dimmed"):
            self._update_theme(self.theme.currentText())
        self.starfab.settings.setValue(
            "cryxmlbConversionFormat", self.cryxmlbFormat.currentText()
        )
        self.starfab.settings.setValue(
            "external_tools/cgf-converter", self.cgfconverterPath.text()
        )
        self.starfab.settings.setValue(
            "external_tools/texconv", self.texconvPath.text()
        )
        self.starfab.settings.setValue(
            "exportDirectory", self.lineEdit_Exports_Directory.text()
        )
        self._parse_settings()

    def _handle_path_chooser(self, option, dir=False):
        cur_value = Path(option.text())
        if cur_value.is_file():
            cur_value = cur_value.parent
        elif not cur_value.is_dir():
            cur_value = Path("~").expanduser().parent
        if not dir:
            new_path = qtw.QFileDialog.getOpenFileName(
                self, "Choose a file", cur_value.as_posix()
            )
        else:
            new_path = qtw.QFileDialog.getExistingDirectory(
                self, "Choose a directory", cur_value.as_posix()
            )
        if new_path:
            option.setText(new_path)

    def _update_theme(self, selected):
        if (theme_file := self.themes.get(selected)) is None:
            logger.error(f'Invalid theme selected {selected}')

        logger.debug(f'Loading theme {selected}')
        theme = qtvsc.loads_jsonc(theme_file.open().read())
        stylesheet = qtvsc.load_stylesheet(theme_file)
        _app = qtw.QApplication.instance()
        _app.setStyleSheet(stylesheet)
        try:
            qta.reset_cache()
            if theme.get('type', '').casefold() == "dark":
                self.qta.dark(_app)
            else:
                self.qta.light(_app)
        except:
            pass

        self.starfab.settings.setValue("theme", selected)
