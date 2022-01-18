from qtpy.QtCore import Slot, Signal, QObject
from qtpy.QtWebChannel import QWebChannel
from qtpy.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings

from . import embedrc
from starfab.gui import qtc, qtw, qtg


SUPPORTED_EDITOR_FORMATS = [
    ".json",
    ".cfg",
    ".ini",
    ".txt",
    ".xml",
    ".log",
    ".id",
    ".cdf",
    ".chrparams",
    ".dpl",
    ".eco",
    ".obj",
    ".sample",
    ".opr",
    ".mtl",
    ".rmp",
    ".entxml",
    ".adb",
]
html = """
<!DOCTYPE html><html lang="en"><head><title>starfab editor</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/FileSaver.js/2.0.0/FileSaver.min.js"></script>
<script src="qrc:/qtwebchannel/qwebchannel.js" type="text/javascript"></script>
<script src="qrc:/ace-builds/src-min-noconflict/ace.js" type="text/javascript" charset="utf-8"></script>
<script src="qrc:/ace-builds/src-min-noconflict/ext-modelist.js" type="text/javascript" charset="utf-8"></script>
<style type="text/css" media="screen">
    body { background-color: #333333; }
    #editor { 
        position: absolute;
        top: 0;
        right: 0;
        bottom: 0;
        left: 0;
    }
</style>
</head>
<body><div id="editor"></div></body>

<script>
document.addEventListener("DOMContentLoaded", function () {
JSJSJS
});
</script>
</html>
"""

init_js = """
    'use strict';
    var placeholder = document.getElementById('editor');
    var modelist = ace.require("ace/ext/modelist");
    var fileName = "FILENAME";
    var mode = modelist.getModeForPath(fileName).mode;
    var editor = ace.edit("editor");
    editor.setReadOnly(true);
    editor.setTheme("THEME");
    editor.session.setMode(mode);
    
    editor.session.setMode("ace/mode/yaml");
    // https://stackoverflow.com/a/42122466/2512851
    var set_error_annotation = function(row, column, err_msg, type) {
    editor.getSession().setAnnotations([{
        row: row,
        column: column,
        text: err_msg, // Or the Json reply from the parser 
        type: type // error, warning, and information
    }]);
    }
    
    new QWebChannel(qt.webChannelTransport, function(channel) {
        var starfab = channel.objects.starfab;
        
        starfab.select_all.connect(function() {
            editor.session.selection.selectAll(); 
        })
        
        starfab.set_value.connect(function(text) {
            editor.session.setValue(text)
        })
        
        starfab.save.connect(function(filename) {
            var blob = new Blob([editor.session.getValue()], {type: "text/plain;charset=utf-8"});
            saveAs(blob, filename);
        })
        
        starfab.append_text.connect(function(text) {
            editor.session.insert({
                row: editor.session.getLength(),
                column: 0
            }, text);
        })
        
        editor.session.on('change', function(delta) {
            starfab.session_change(editor.getValue(), function(val) {});
            // Python functions return a value, even if it is None. So we need to pass a
            // dummy callback function to handle the return            
        })
        
        starfab.send_error_annotation.connect(set_error_annotation);
        
        starfab.ace_ready();
    });
"""


class AceChannel(QObject):
    set_value = Signal(str)
    append_text = Signal(str)
    send_error_annotation = Signal(int, int, str, str)
    select_all = Signal()
    changed = Signal()
    ready = Signal()
    save = Signal(str)

    @Slot(str)
    def session_change(self, message):
        self.changed.emit()

    @Slot()
    def ace_ready(self):
        self.ready.emit()


DEFAULT_THEME = "ace/theme/dracula"


class Editor(QWebEngineView):
    changed = Signal()

    def __init__(self, editor_item, theme=DEFAULT_THEME, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.theme = theme
        self.editor_item = editor_item

        self.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        self.settings().setAttribute(
            QWebEngineSettings.LocalContentCanAccessRemoteUrls, True
        )
        self.settings().setAttribute(QWebEngineSettings.ErrorPageEnabled, True)
        self.settings().setAttribute(QWebEngineSettings.PluginsEnabled, True)
        # self.setContextMenuPolicy(qtc.Qt.CustomContextMenu)

        # self.dev_view = QWebEngineView()
        # self.page().setDevToolsPage(self.dev_view.page())
        # self.dev_view.show()

        self.ace = AceChannel()
        self.channel = QWebChannel()
        self.channel.registerObject("starfab", self.ace)
        self.page().profile().downloadRequested.connect(self._on_download_requested)

        self.ace.ready.connect(self._on_ace_ready)
        self.changed = self.ace.changed

        page = self.page()
        page.setWebChannel(self.channel)
        js = init_js.replace("FILENAME", self.editor_item.name)
        js = js.replace("THEME", self.theme)
        h = html.replace("JSJSJS", js)
        page.setHtml(h, qtc.QUrl("qrc:/index.html"))

        timer = qtc.QTimer()
        timer.setSingleShot(True)
        timer.setInterval(5000)
        timer.timeout.connect(lambda x=None: self.ace.set_value.emit("Testing."))
        timer.start()

    def contextMenuEvent(self, event):
        filter_actions = ["Back", "Forward", "Reload", "Save page", "View page source"]
        menu = self.page().createStandardContextMenu()
        for action in menu.actions():
            if action.text() in filter_actions:
                menu.removeAction(action)
        for action in menu.actions():
            if action.text() == "":
                menu.removeAction(action)
            else:
                break
        select_all = menu.addAction("Select All")
        select_all.triggered.connect(lambda: self.ace.select_all.emit())
        save_as = menu.addAction("Save As...")
        save_as.triggered.connect(self._handle_save_as)
        menu.popup(event.globalPos())

    @Slot()
    def _handle_save_as(self):
        self.ace.save.emit(self.editor_item.path.name)

    def _on_download_requested(self, download):
        old_path = download.path()
        suffix = qtc.QFileInfo(old_path).suffix()
        path, _ = qtw.QFileDialog.getSaveFileName(
            self, "Save File", old_path, "*." + suffix
        )
        if path:
            download.setPath(path)
            download.accept()
        else:
            download.cancel()

    @Slot()
    def _on_ace_ready(self):
        try:
            self.ace.set_value.emit(
                self.editor_item.contents().read().decode("utf-8").replace("\x00", "")
            )
        except Exception as e:
            self.ace.set_value.emit(f"Failed to open {self.editor_item.name}: {e}")
