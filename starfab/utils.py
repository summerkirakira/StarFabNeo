import importlib
import subprocess
import sys

from scdatatools.engine.textures.converter import (
    convert_buffer,
    ConverterUtility,
    ConversionError,
)
from starfab.gui import qtw
from starfab.settings import get_texconv, get_compressonatorcli


def strtobool(val: str):
    val = val.lower()
    if val in ('y', 'yes', 't', 'true', 'on', '1'):
        return True
    elif val in ('n', 'no', 'f', 'false', 'off', '0'):
        return False
    else:
        raise ValueError(f"Invalid boolean string value: {val!r}")


def parsebool(val: any):
    if isinstance(val, bool):
        return val
    elif isinstance(val, str):
        return strtobool(val)
    return bool(val)


def open_color_dialog():
    color = qtw.QColorDialog.getColor()
    if color.isValid():
        # print(color.red(), color.blue(), color.green())
        return color.name()


def reload_starfab_modules(module=""):
    # build up the list of modules first, otherwise sys.modules will change while you iterate through it
    loaded_modules = [
        m
        for n, m in sys.modules.items()
        if (n.startswith(module) if module else n.startswith("starfab.gui"))
    ]
    for module in loaded_modules:
        importlib.reload(module)


def show_file_in_filemanager(path):
    if sys.platform == "win32":
        subprocess.Popen(["explorer", str(path)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


class ImageConverter:
    def __init__(self):
        self.compressonatorcli = get_compressonatorcli()
        self.texconv = get_texconv()
        self.converter = (
            ConverterUtility.texconv
            if self.texconv
            else ConverterUtility.compressonator
        )

    @property
    def converter_bin(self):
        return (
            self.texconv
            if self.converter == ConverterUtility.texconv
            else self.compressonatorcli
        )

    def _check_bin(self):
        if not self.converter:
            qtw.QMessageBox.information(
                None,
                "Image Converter",
                f"Missing a DDS converter. If you're on Mac/Linux use compressonatorcli. You can install it from "
                f"<a href='https://gpuopen.com/compressonator/'>https://www.steamgriddb.com/manager</a>. If you're on"
                f"windows you can use texconv, download it from "
                f"<a href='https://github.com/microsoft/DirectXTex/releases'>"
                f"https://github.com/microsoft/DirectXTex/releases</a>. Ensure whichever tool is in your system PATH.",
            )
            raise RuntimeError(f"Cannot find compressonatorcli")

    def convert_buffer(self, inbuf, in_format, out_format="tif") -> bytes:
        """Converts a buffer `inbuf` to the output format `out_format`"""
        self._check_bin()

        try:
            buf, msg = convert_buffer(
                inbuf,
                in_format=in_format,
                out_format=out_format,
                converter=self.converter,
                converter_bin=self.converter_bin,
            )
        except ConversionError as e:
            raise RuntimeError(f"Failed to convert buffer: {e}")

        return buf


image_converter = ImageConverter()
