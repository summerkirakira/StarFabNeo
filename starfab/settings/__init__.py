import shutil
import sys
import typing
from pathlib import Path

from starfab import CONTRIB_DIR
from starfab.gui import qtc

settings_defaults = {
    "theme": "Monokai Dimmed",
    "tree_view_folders_first": "true",
    "defaultWorkspace": "data",
    "checkForUpdates": "true",
    "enableErrorReporting": "true",
    "ignoreUpdate": "",
    "updateRemindLater": "",
    "autoOpenRecent": "false",

    # external tools
    "external_tools/cgf-converter": "",
    "external_tools/texconv": "",

    # conversion
    "convert/cryxml_fmt": "xml",
    "convert/img_fmt": "png",

    # exporting
    "exportDirectory": str(qtc.QDir.homePath() + "/Desktop/StarFab_Exports"),
    "extract/auto_open_folder": "true",

    # editor
    "editor/theme": "Monokai",
    "editor/key_bindings": "Default",
    "editor/word_wrap": "Off",
    "editor/line_numbers": "true",

    # extract
    "extract/extract_model_assets": "false",
    "extract/auto_unsplit_textures": "true",
    "extract/auto_convert_textures": "true",
    "extract/auto_convert_sounds": "true",
    "extract/auto_convert_models": "false",
    "extract/create_sub_folder": "false",
    "extract/gen_model_log": "false",
    "extract/overwrite_existing": "false",
    "extract/verbose": "false",

}


first_run_flags = {
    (1, "success"),  # no action needed
    (2, "check_update"),  # program or user requires an update
}


class StarFabSettings(qtc.QSettings):
    settings_updated = qtc.Signal()

    def __init__(self, *args, **kwargs):
        self._debounce = qtc.QTimer()
        self._debounce.setInterval(500)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._settings_updated)

        super().__init__(*args, **kwargs)

        # TODO: combine first run flags with settings init to better serve initial interactions as needed,
        #       for example check for updates, create default config, etc.
        if self.value("first_run") is None:
            self.configure_defaults()
            self.setValue("first_run", "1")

    def _settings_updated(self):
        self.settings_updated.emit()

    def value(self, key: str, defaultValue: typing.Optional[typing.Any] = None, *args, **kwargs) -> object:
        default = settings_defaults.get(key) if defaultValue is None else defaultValue
        return super().value(key, default, *args, **kwargs)

    def setValue(self, key: str, value: typing.Any) -> None:
        super().setValue(key, value)
        self._debounce.start()

    def configure_defaults(self):
        for key, value in settings_defaults.items():
            self.setValue(key, value)


def _get_exec(name, settings_name):
    exe = settings.value(settings_name, "")
    if exe:
        return exe
    exe = shutil.which(name)
    if exe is not None:
        return exe

    name = name + ".exe" if sys.platform == "win32" else name
    if (CONTRIB_DIR / name).is_file():
        return Path(CONTRIB_DIR / name)
    # TODO: perform some validation of the converter and throw an error dialog if it's not valid
    #       Related note: define validation, possibly create tests for it
    return ""


def get_ww2ogg():
    return _get_exec("ww2ogg", "external_tools/ww2ogg")


def get_revorb():
    return _get_exec("revorb", "external_tools/revorb")


def get_cgf_converter():
    return _get_exec("cgf-converter", "external_tools/cgf-converter")


def get_texconv():
    return _get_exec("texconv", "external_tools/texconv")


def get_compressonatorcli():
    return _get_exec("compressonatorcli", "external_tools/compressonatorcli")


settings = StarFabSettings("SCModding", "StarFab")


def get_settings():
    global settings
    return settings
