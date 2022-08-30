import importlib
from pathlib import Path

from scdatatools.blender.addon.utils import install_blender_addon

from starfab import __version__

ADDON_TEMPLATE = """
# StarFab Add-on
# https://gitlab.com/scmodding/tools/starfab

import sys
import bpy

paths = {path}
sys.path.extend(_ for _ in paths if _ not in sys.path)

bl_info = {{
    "name": "StarFab Blender Link",
    "author": "ventorvar",
    "version": (0, 1, 0),
    "blender": (3, 1, 0),
    "location": "View3D > Panel",
    "category": "SC Modding",
    "doc_url": "https://gitlab.com/scmodding/tools/starfab",
}}

from starfab.blender.addon import *
"""


def install(version) -> Path:
    """
    Installs the StarFab add-on into the Blender version `version`.
    """
    addon_py = install_blender_addon(version, "starfab_addon", ADDON_TEMPLATE)

    # TODO: remove this in the future
    scdv_py = addon_py.parent / "scdv_addon.py"
    scdv_py.unlink(missing_ok=True)

    return addon_py


def register():
    from starfab.blender import link

    importlib.reload(link)
    link.register()


def unregister():
    from starfab.blender import link

    link.unregister()
