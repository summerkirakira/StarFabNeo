import os
from pathlib import Path
from qtpy import QtWebChannel
from qtpy import QtWebEngineWidgets

from starfab.gui import qtc, qtw, qtg


from .resources import markdownrc


class Document(qtc.QObject):
    textChanged = qtc.Signal(str)
    ready = qtc.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._text = ''

    @qtc.Slot()
    def document_ready(self):
        self.ready.emit()

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, text):
        if self._text == text:
            return
        self._text = text
        self.textChanged.emit(text)


class WebEnginePage(QtWebEngineWidgets.QWebEnginePage):
    def acceptNavigationRequest(self, url, _type, isMainFrame):
        if _type == QtWebEngineWidgets.QWebEnginePage.NavigationTypeLinkClicked:
            qtg.QDesktopServices.openUrl(url)
            return False
        return True


class MarkdownView(QtWebEngineWidgets.QWebEngineView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._load_finished = False
        self._preload_text = ''

        self.setPage(WebEnginePage(self))
        self.document = Document()

        self.document.ready.connect(self._handle_load_finished)

        self.channel = QtWebChannel.QWebChannel()
        self.channel.registerObject("content", self.document)

        self.dev_view = QtWebEngineWidgets.QWebEngineView()
        self.page().setDevToolsPage(self.dev_view.page())
        self.dev_view.show()

        self.page().setWebChannel(self.channel)
        self.setUrl(qtc.QUrl("qrc:/markdown/index.html"))

    def _handle_load_finished(self):
        self._load_finished = True
        if self._preload_text:
            self.document.text = self._preload_text

    def setMarkdown(self, text):
        if not self._load_finished:
            self._preload_text = text
        else:
            self.document.text = text
