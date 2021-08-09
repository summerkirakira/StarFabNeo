import shutil
from pathlib import Path
from functools import partial
from distutils.util import strtobool

from qtpy import uic

from scdv import CONTRIB_DIR
from scdv.ui import qtg, qtw, qtc
from scdv.resources import RES_PATH


class SettingsDialog(qtw.QDialog):
    def __init__(self, scdv):
        super().__init__(parent=None)
        self.scdv = scdv
        uic.loadUi(str(RES_PATH / 'ui' / 'SCDVSettingsDialog.ui'), self)  # Load the ui into self

        open_dir_icon = qtw.QApplication.style().standardIcon(qtw.QStyle.SP_DirIcon)
        cgfconvfind = self.cgfconverterPath.addAction(open_dir_icon, qtw.QLineEdit.TrailingPosition)
        cgfconvfind.triggered.connect(partial(self._handle_path_chooser, self.cgfconverterPath))

        texconvfind = self.texconvPath.addAction(open_dir_icon, qtw.QLineEdit.TrailingPosition)
        texconvfind.triggered.connect(partial(self._handle_path_chooser, self.texconvPath))

        self.autoOpenMostRecent.setChecked(strtobool(self.scdv.settings.value('autoOpenRecent', 'false')))
        self.autoOpenMostRecent.stateChanged.connect(self._save_settings)

        self.theme.setCurrentText(self.scdv.settings.value('theme', 'dark'))
        self.theme.currentTextChanged.connect(self._save_settings)

        self.cryxmlbFormat.setCurrentText(self.scdv.settings.value('cryxmlbConversionFormat', 'xml'))
        self.cryxmlbFormat.currentTextChanged.connect(self._save_settings)

        self.cgfconverterPath.setText(self.scdv.settings.value('cgfconverter', ''))
        self.cgfconverterPath.textChanged.connect(self._save_settings)

        self.texconvPath.setText(self.scdv.settings.value('texconv', ''))
        self.texconvPath.textChanged.connect(self._save_settings)

        self.helpButton.clicked.connect(lambda: qtg.QDesktopServices.openUrl('https://gitlab.com/scmodding/tools/scdv'))

        self.buttonBox.rejected.connect(self.close)

    def _save_settings(self, *args, **kwargs):
        print('Saving settings')
        self.scdv.settings.setValue('autoOpenRecent', self.autoOpenMostRecent.isChecked())
        self.scdv.settings.setValue('theme', self.theme.currentText().lower())
        if theme_setter := getattr(self.scdv, f'set_{self.theme.currentText().lower()}_theme'):
            theme_setter()
        self.scdv.settings.setValue('cyxmlbConversionFormat', self.cryxmlbFormat.currentText())
        self.scdv.settings.setValue('cgfconverter', self.cgfconverterPath.text())
        self.scdv.settings.setValue('texconv', self.texconvPath.text())

    def _handle_path_chooser(self, option):
        cur_value = Path(option.text())
        if cur_value.is_file():
            cur_value = cur_value.parent
        else:
            cur_value = Path('~').expanduser().parent
        new_path = qtw.QFileDialog.getOpenFileName(self, 'Choose a file', cur_value.as_posix())
        if new_path:
            option.setText(new_path[0])
