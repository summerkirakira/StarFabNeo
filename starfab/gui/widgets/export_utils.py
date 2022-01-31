from distutils.util import strtobool

from starfab.gui import qtc, qtw, qtg
from starfab.resources import RES_PATH
from starfab.gui.widgets.dock_widgets.common import StarFabStaticWidget


SETTINGS_PATH = "extractor"


class ExportOptionsWidget(StarFabStaticWidget):
    __ui_file__ = str(RES_PATH / "ui" / "ExportSettingsForm.ui")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reset_from_settings()

    def reset_from_settings(self):
        self.opt_cryxmlFmt.setCurrentText(
            self.starfab.settings.value(
                f"{SETTINGS_PATH}/convert_cryxml_fmt", "xml"
            ).lower()
        )
        self.opt_cryxmlFmt.currentTextChanged.connect(self.save_settings)
        self.opt_imgFmt.setCurrentText(
            self.starfab.settings.value(
                f"{SETTINGS_PATH}/convert_dds_fmt", "png"
            ).lower()
        )
        self.opt_imgFmt.currentTextChanged.connect(self.save_settings)
        self.opt_autoUnsplitTextures.setChecked(
            strtobool(
                self.starfab.settings.value(
                    f"{SETTINGS_PATH}/auto_unsplit_textures", "true"
                )
            )
        )
        self.opt_autoUnsplitTextures.stateChanged.connect(self.save_settings)
        self.opt_autoConvertTextures.setChecked(
            strtobool(
                self.starfab.settings.value(
                    f"{SETTINGS_PATH}/auto_convert_textures", "true"
                )
            )
        )
        self.opt_autoConvertTextures.stateChanged.connect(self.save_settings)
        self.opt_autoConvertSounds.setChecked(
            strtobool(
                self.starfab.settings.value(
                    f"{SETTINGS_PATH}/auto_convert_sounds", "true"
                )
            )
        )
        self.opt_autoConvertSounds.stateChanged.connect(self.save_settings)
        self.opt_convertModelsDAE.setChecked(
            strtobool(
                self.starfab.settings.value(
                    f"{SETTINGS_PATH}/auto_convert_models", "false"
                )
            )
        )
        self.opt_convertModelsDAE.stateChanged.connect(self.save_settings)
        self.opt_createSubFolder.setChecked(
            strtobool(
                self.starfab.settings.value(
                    f"{SETTINGS_PATH}/create_sub_folder", "false"
                )
            )
        )
        self.opt_createSubFolder.stateChanged.connect(self.save_settings)
        self.opt_genModelLog.setChecked(
            strtobool(
                self.starfab.settings.value(f"{SETTINGS_PATH}/gen_model_log", "false")
            )
        )
        self.opt_genModelLog.stateChanged.connect(self.save_settings)
        self.opt_overwriteExisting.setChecked(
            strtobool(
                self.starfab.settings.value(
                    f"{SETTINGS_PATH}/overwrite_existing", "false"
                )
            )
        )
        self.opt_overwriteExisting.stateChanged.connect(self.save_settings)

    def save_settings(self):
        for k, v in self.get_options().items():
            self.starfab.settings.setValue(f"{SETTINGS_PATH}/{k}", v)

    def get_options(self):
        opts = {
            "converters": [],
            "overwrite": self.opt_overwriteExisting.isChecked(),
            "convert_cryxml_fmt": self.opt_cryxmlFmt.currentText(),
            "convert_dds_fmt": self.opt_imgFmt.currentText(),
            "convert_dds_unsplit": self.opt_autoUnsplitTextures.isChecked(),
            "auto_convert_sounds": self.opt_autoConvertSounds.isChecked(),
            "create_sub_folder": self.opt_createSubFolder.isChecked(),
            "gen_model_log": self.opt_genModelLog.isChecked(),
            "auto_convert_textures": self.opt_autoConvertTextures.isChecked(),
            "auto_convert_models": self.opt_convertModelsDAE.isChecked(),
            "verbose": self.opt_Verbose.isChecked(),
        }

        if self.opt_cryxmlFmt.currentText().lower() != "cryxmlb":
            opts["converters"].append("cryxml_converter")
        if self.opt_autoUnsplitTextures.isChecked():
            opts["converters"].append("ddstexture_converter")
            if not self.opt_autoConvertTextures.isChecked():
                opts["convert_dds_fmt"] = "dds"
        if self.opt_convertModelsDAE.isChecked():
            opts["converters"].append("cgf_converter")

        return opts

    @qtc.Slot()
    def on_opt_autoConvertTextures_stateChanged(self):
        # this is auto-connected from the .ui
        if self.opt_autoConvertTextures.isChecked():
            self.opt_autoUnsplitTextures.setChecked(True)
            self.opt_autoUnsplitTextures.setEnabled(False)
        else:
            self.opt_autoUnsplitTextures.setEnabled(True)
