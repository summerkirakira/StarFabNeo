import shutil
from pathlib import Path

from . import CONTRIB_DIR
from .ui import qtg, qtw, qtc


settings = qtc.QSettings('SCModding', 'SCDV')


def get_cgf_converter():
    conv = settings.value('cgfconverter', '')
    if conv:
        return conv
    conv = shutil.which('cgf-converter')
    if conv is not None:
        return conv
    if (CONTRIB_DIR / 'cgf-converter.exe').is_file():
        return Path(CONTRIB_DIR / 'cgf-converter.exe')
    # TODO: perform some validation of the converter and throw an error dialog if it's not valid
    return ''


def get_texconv():
    conv = settings.value('texconv', '')
    if conv:
        return conv
    conv = shutil.which('texconv')
    if conv is not None:
        return conv
    if (conv := CONTRIB_DIR / 'texconv.exe').is_file():
        return conv.as_posix()
    # TODO: perform some validation of the converter and throw an error dialog if it's not valid
    return ''


def get_compressonatorcli():
    conv = settings.value('compressonatorcli', '')
    if conv:
        return conv
    conv = shutil.which('compressonatorcli')
    if conv is not None:
        return conv
    if (conv := CONTRIB_DIR / 'compressonatorcli.exe').is_file():
        return conv.as_posix()
    # TODO: perform some validation of the converter and throw an error dialog if it's not valid
    return ''
