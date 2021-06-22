import io
from scdv.ui import qtc, qtg, qtw


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


class ContentItem:
    def __init__(self, name, path, contents=''):
        self._contents = io.BytesIO(contents.encode('utf-8'))
        self.name = name
        self.path = path

    def contents(self):
        return self._contents
