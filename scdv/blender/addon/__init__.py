import importlib
from pathlib import Path

from scdatatools.blender.addon.utils import install_blender_addon

ADDON_TEMPLATE = """
# SCDV Add-on
# https://gitlab.com/scmodding/tools/scdv

import sys
import bpy

paths = {path}
sys.path.extend(_ for _ in paths if _ not in sys.path)

bl_info = {{
    "name": "SCDV Blender Link",
    "author": "ventorvar",
    "version": (0, 1, 0),
    "blender": (2, 93, 0),
    "location": "View3D > Panel",
    "category": "SC Modding",
    "doc_url": "https://gitlab.com/scmodding/tools/scdv",
}}

from scdv.blender.addon import *
"""


def install(version) -> Path:
    """
    Installs the SCDV add-on into the Blender version `version`.
    """
    return install_blender_addon(version, 'scdv_addon', ADDON_TEMPLATE)


def register():
    from scdv.blender import link
    importlib.reload(link)
    link.register()


def unregister():
    from scdv.blender import link
    link.unregister()
