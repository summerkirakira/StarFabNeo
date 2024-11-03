import time
from pathlib import Path

from starfab.gui import qtc, qtw


def seconds_to_str(secs):
    return time.strftime("%M:%S" if secs < 60 * 60 else "%H:%M:%S", time.gmtime(secs))


class ScrollMessageBox(qtw.QMessageBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        chldn = self.children()
        scrll = qtw.QScrollArea(self)
        scrll.setWidgetResizable(True)
        grd = self.findChild(qtw.QGridLayout)
        lbl = qtw.QLabel(chldn[1].text(), self)
        lbl.setWordWrap(True)
        scrll.setWidget(lbl)
        scrll.setFixedSize(400, 200)
        grd.addWidget(scrll, 0, 1)
        chldn[1].setText("")
        self.exec_()


_icon_cache = {}
icon_provider = qtw.QFileIconProvider()
ZIP_ICON_EXTS = ['dcb', 'p4k', 'pak', 'socpak']


def icon_for_path(path: str, default=False):
    if not isinstance(path, str):
        path = str(path)
    path = path.lower()
    if "." in path:
        ext = path.rsplit(".", maxsplit=1)[-1]
        if ext in ZIP_ICON_EXTS:
            path = path.replace(ext, "zip")
        return _icon_cache.setdefault(ext, icon_provider.icon(qtc.QFileInfo(Path(path).absolute().as_posix())))
    if default:
        return _icon_cache.setdefault(
            ".default", qtw.QApplication.style().standardIcon(qtw.QStyle.StandardPixmap.SP_FileIcon)
        )
    return None
