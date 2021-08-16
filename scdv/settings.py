import shutil
import sys
from pathlib import Path

from . import CONTRIB_DIR
from .ui import qtg, qtw, qtc


settings = qtc.QSettings('SCModding', 'SCDV')


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
