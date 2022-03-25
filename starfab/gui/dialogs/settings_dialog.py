import typing
from functools import partial
from pathlib import Path

import qtawesome as qta
from qtpy import uic

import qtvscodestyle as qtvsc
from scdatatools.utils import parse_bool
from starfab.gui import qtw
from starfab.gui.dialogs import list_dialog
from starfab.gui.widgets import editor
from starfab.log import getLogger
from starfab.resources import RES_PATH

if typing.TYPE_CHECKING:
    from starfab.app import StarFab

button_group_2 = {"0": "data", "1": "content", "2": "toolbox"}

logger = getLogger(__name__)


class SettingsDialog(qtw.QDialog):
    def __init__(self, starfab):
        super().__init__(parent=None)
        self.starfab: StarFab = starfab
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
        self.editorTheme.clear()
        self.editorTheme.addItems(list(sorted(editor.THEMES.keys())))

        self._parse_settings()

        # left side
        self.theme.currentTextChanged.connect(self._save_settings)
        self.workspaceBtnGroup.buttonClicked.connect(self._save_settings)
        self.checkForUpdates.stateChanged.connect(self._save_settings)
        self.enableErrorReporting.stateChanged.connect(self._save_settings)
        self.autoOpenMostRecent.stateChanged.connect(self._save_settings)

        # external tools
        open_dir_icon = qtw.QApplication.style().standardIcon(qtw.QStyle.SP_DirIcon)
        cgfconvfind = self.cgfconverterPath.addAction(open_dir_icon, qtw.QLineEdit.TrailingPosition)
        cgfconvfind.triggered.connect(partial(self._handle_path_chooser, self.cgfconverterPath))
        texconvfind = self.texconvPath.addAction(open_dir_icon, qtw.QLineEdit.TrailingPosition)
        texconvfind.triggered.connect(partial(self._handle_path_chooser, self.texconvPath))

        self.starfab.blender_manager.updated.connect(self._sync_blender)
        self.blenderConfigButton.setIcon(qta.icon("msc.settings-gear"))
        self.blenderConfigButton.clicked.connect(self._config_blender_paths)
        self.blenderComboBox.activated.connect(self._update_blender)

        self.cgfconverterPath.textChanged.connect(self._save_settings)
        self.texconvPath.textChanged.connect(self._save_settings)

        # conversion
        self.opt_cryxmlbFmt.currentTextChanged.connect(self._save_settings)
        self.opt_imgFmt.currentTextChanged.connect(self._save_settings)

        # export
        self.opt_Exports_Directory.textChanged.connect(self._save_settings)
        exportsdirfind = self.opt_Exports_Directory.addAction(open_dir_icon, qtw.QLineEdit.TrailingPosition)
        exportsdirfind.triggered.connect(
            partial(self._handle_path_chooser, self.opt_Exports_Directory, dir=True)
        )
        self.opt_autoOpenExportFolder.stateChanged.connect(self._save_settings)

        # editor
        self.editorTheme.currentTextChanged.connect(self._save_settings)
        self.editorKeybindings.currentTextChanged.connect(self._save_settings)
        self.editorWordWrap.currentTextChanged.connect(self._save_settings)
        self.editorShowLineNumbers.stateChanged.connect(self._save_settings)

        self.buttonBox.button(qtw.QDialogButtonBox.RestoreDefaults).clicked.connect(self._reset_settings)
        self.buttonBox.accepted.connect(self.close)

    def _parse_settings(self):
        # left side
        theme = self.starfab.settings.value("theme")
        if theme in list(self.themes.values()):
            self.theme.setCurrentText(next(iter(n for n, f in self.themes.items() if f == theme)))
        elif theme in self.themes:
            self.theme.setCurrentText(theme)
        default_ws = self.starfab.settings.value('defaultWorkspace')
        self.defaultWS_Data.setChecked(default_ws == 'data')
        self.defaultWS_Content.setChecked(default_ws == 'content')

        self.checkForUpdates.setChecked(parse_bool(self.starfab.settings.value("checkForUpdates")))
        self.enableErrorReporting.setChecked(parse_bool(self.starfab.settings.value("enableErrorReporting")))
        self.autoOpenMostRecent.setChecked(parse_bool(self.starfab.settings.value("autoOpenRecent")))

        # external tools
        self.cgfconverterPath.setText(self.starfab.settings.value("external_tools/cgf-converter"))
        self.texconvPath.setText(self.starfab.settings.value("external_tools/texconv"))

        # conversion
        self.opt_cryxmlbFmt.setCurrentText(self.starfab.settings.value("convert/cryxml_fmt"))
        self.opt_imgFmt.setCurrentText(self.starfab.settings.value("convert/img_fmt"))

        # exporting
        self.opt_Exports_Directory.setText(self.starfab.settings.value("exportDirectory"))
        self.opt_autoOpenExportFolder.setChecked(
            parse_bool(self.starfab.settings.value("extract/auto_open_folder"))
        )

        # editor
        self.editorTheme.setCurrentText(self.starfab.settings.value("editor/theme"))
        self.editorKeybindings.setCurrentText(self.starfab.settings.value("editor/key_bindings"))
        self.editorWordWrap.setCurrentText(self.starfab.settings.value("editor/word_wrap"))
        self.editorShowLineNumbers.setChecked(parse_bool(self.starfab.settings.value("editor/line_numbers")))

        self._sync_blender()

    def _config_blender_paths(self):
        paths = [
            _['path'].parent.as_posix() for _ in self.starfab.blender_manager.available_versions.values()
        ]
        dlg = list_dialog.QListDialog('Blender Paths', items=paths, parent=self)
        try:
            if dlg.exec_() == qtw.QDialog.Accepted:
                paths = [Path(_) for _ in dlg.items()]
                self.starfab.blender_manager.set_additional_paths.emit(paths)
                self.blenderComboBox.clear()
                self.blenderComboBox.setEnabled(False)
                self.blenderComboBox.addItems('...checking')
        except KeyboardInterrupt:
            pass
        finally:
            dlg.destroy()

    def _update_blender(self):
        preferred = self.blenderComboBox.currentText()
        self.starfab.blender_manager.set_preferred_blender.emit('' if preferred == 'auto' else preferred)

    def _sync_blender(self):
        preferred = self.starfab.blender_manager.preferred_blender
        options = set(self.starfab.blender_manager.available_versions.keys())
        if preferred:
            options.add(preferred)

        self.blenderComboBox.clear()
        self.blenderComboBox.addItems(['auto'] + sorted(options))
        self.blenderComboBox.setCurrentText(preferred if preferred else 'auto')
        if preferred and preferred != 'auto' and preferred not in self.starfab.blender_manager.available_versions:
            self.blenderComboBox.setStyleSheet("color: #ff0000")
        else:
            self.blenderComboBox.setStyleSheet("")
        self.blenderComboBox.setEnabled(True)
        width = self.blenderComboBox.minimumSizeHint().width()
        self.blenderComboBox.view().setMinimumWidth(width)

    def _reset_settings(self):
        self.starfab.settings.configure_defaults()
        self.close()

    def _save_settings(self, *args, **kwargs):
        logger.debug("Saving settings")

        # left side
        if self.theme.currentText() != self.starfab.settings.value("theme", "Monokai Dimmed"):
            self._update_theme(self.theme.currentText())
        self.starfab.settings.setValue("defaultWorkspace", 'data' if self.defaultWS_Data.isChecked() else 'content')
        self.starfab.settings.setValue("checkForUpdates", self.checkForUpdates.isChecked())
        self.starfab.settings.setValue("enableErrorReporting", self.enableErrorReporting.isChecked())
        self.starfab.settings.setValue("autoOpenRecent", self.autoOpenMostRecent.isChecked())

        # external tools
        self.starfab.settings.setValue("external_tools/cgf-converter", self.cgfconverterPath.text())
        self.starfab.settings.setValue("external_tools/texconv", self.texconvPath.text())

        # conversion
        self.starfab.settings.setValue("convert/cryxml_fmt", self.opt_cryxmlbFmt.currentText())
        self.starfab.settings.setValue("convert/img_fmt", self.opt_imgFmt.currentText())

        # exporting
        self.starfab.settings.setValue("exportDirectory", self.opt_Exports_Directory.text())
        self.starfab.settings.setValue("export/auto_open_folder", self.opt_autoOpenExportFolder.isChecked())

        # editor
        self.starfab.settings.setValue("editor/theme", self.editorTheme.currentText())
        self.starfab.settings.setValue("editor/key_bindings", self.editorKeybindings.currentText())
        self.starfab.settings.setValue("editor/word_wrap", self.editorWordWrap.currentText())
        self.starfab.settings.setValue("editor/line_numbers", self.editorShowLineNumbers.isChecked())

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
