import shutil
import sys
from pathlib import Path

from starfab import CONTRIB_DIR
from starfab.gui import qtg, qtw, qtc


settings_defaults = {
    'autoOpenRecent': 'false',
    'theme': 'MONOKAI_DIMMED',
    'cryxmlbConversionFormat': 'xml',
    'external_tools/cgf-converter': '',
    'external_tools/texconv': '',
    'defaultWorkspace': 'data',
    'preloadAudioDatabase': 'false',
    'preloadLocalization': 'false',
    'preloadTagDatabase': 'true',
    'exportDirectory': str(qtc.QDir.homePath() + '/Desktop/StarFab_Exports')
}


first_run_flags = {
    (1, 'success'),  # no action needed
    (2, 'check_update')  # program or user requires an update
}


def configure_defaults(settings):
    for key, value in settings_defaults.items():
        settings.setValue(key, value)


def _get_exec(name, settings_name):
    exe = settings.value(settings_name, '')
    if exe:
        return exe
    exe = shutil.which(name)
    if exe is not None:
        return exe
    name = name + '.exe' if sys.platform == 'win32' else name
    if (CONTRIB_DIR / name).is_file():
        return Path(CONTRIB_DIR / name)
    # TODO: perform some validation of the converter and throw an error dialog if it's not valid
    return ''


def get_ww2ogg():
    return _get_exec('ww2ogg', 'external_tools/ww2ogg')


def get_revorb():
    return _get_exec('revorb', 'external_tools/revorb')


def get_cgf_converter():
    return _get_exec('cgf-converter', 'external_tools/cgf-converter')


def get_texconv():
    return _get_exec('texconv', 'external_tools/texconv')


def get_compressonatorcli():
    return _get_exec('compressonatorcli', 'external_tools/compressonatorcli')


def get_settings():
    # TODO: combine first run flags with settings init to better serve initial interactions as needed,
    #       for example check for updates, create default config, etc.
    settings = qtc.QSettings('SCTools', 'StarFab')
    if settings.value('theme') is None:
        configure_defaults(settings)

    try:
        first_run = settings.value('first_run')
    except:
        configure_defaults(settings)
    finally:
        settings.setValue('first_run', '1')

    return settings


settings = get_settings()
