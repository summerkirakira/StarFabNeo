import time

from scdv.ui import qtc, qtw


def seconds_to_str(secs):
    return time.strftime("%M:%S" if secs < 60*60 else "%H:%M:%S", time.gmtime(secs))


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
        chldn[1].setText('')
        self.exec_()


_icon_cache = {}
icon_provider = qtw.QFileIconProvider()


def icon_for_path(path: str):
    if not isinstance(path, str):
        path = str(path)
    if '.' in path:
        return _icon_cache.setdefault(
            path.rsplit('.', maxsplit=1)[-1], icon_provider.icon(qtc.QFileInfo(path))
        )
    return None
