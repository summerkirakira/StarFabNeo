import importlib
import subprocess
import sys
from io import BytesIO

from PIL import Image

from distutils.util import strtobool

from scdatatools.engine.textures.converter import (
    ConversionError,
)
from starfab.gui import qtw


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


def convert_image_buffer(inbuf, in_format: str, out_format="tif") -> bytes:
    """Converts a buffer `inbuf` to the output format `out_format`"""

    try:
        image: Image = Image.open(BytesIO(inbuf), formats=[in_format.upper()])
        image_rgba: Image = image.convert("RGBA")
        out_buffer = BytesIO()
        image_rgba.save(out_buffer, format=out_format.upper())
        out_buffer.seek(0)
        del image, image_rgba
    except ConversionError as e:
        raise RuntimeError(f"Failed to convert buffer: {e}")

    return out_buffer.read()
