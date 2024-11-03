from qtpy.QtGui import *
from . import RES_PATH


icons_instance = None


def get_icon(name):
    global icons_instance
    if not icons_instance:
        icons_instance = Icons()
    return icons_instance.icon(name)


class Icons(object):
    def __init__(self):
        self._icons = {}
        self.make_icon("folder", str(RES_PATH / "icons" / "folder.png"))
        self.make_icon("open", str(RES_PATH / "icons" / "open.png"))
        self.make_icon("save", str(RES_PATH / "icons" / "save.png"))
        self.make_icon("icon", str(RES_PATH / "icons" / "icon.png"))
        self.make_icon("exit", str(RES_PATH / "icons" / "exit.png"))
        self.make_icon("paste", str(RES_PATH / "icons" / "paste.png"))
        self.make_icon("zoom", str(RES_PATH / "icons" / "zoom.png"))
        self.make_icon("copy", str(RES_PATH / "icons" / "copy.png"))
        self.make_icon("about", str(RES_PATH / "icons" / "about.png"))
        self.make_icon("license", str(RES_PATH / "icons" / "license.png"))
        self.make_icon("default", str(RES_PATH / "icons" / "default.png"))

    def make_icon(self, name, path):
        icon = QIcon()
        icon.addPixmap(QPixmap(path), QIcon.Mode.Normal, QIcon.State.Off)
        self._icons[name] = icon

    def icon(self, name):
        icon = self._icons["default"]
        try:
            icon = self._icons[name]
        except KeyError:
            print("icon " + name + " not found")
        return icon
