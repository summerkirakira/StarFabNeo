import os
from qtpy.QtCore import Slot, Signal, QObject
from qtpy.QtWebChannel import QWebChannel
from qtpy.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings

from . import embedrc
from starfab.gui import qtc, qtw, qtg
from starfab.settings import settings
from scdatatools.utils import parse_bool


WRAP_MODES = {
    'off': 'off',
    'view': 'free',
    'margin': 'printMargin'
}

THEMES = {
    "Chrome": "ace/theme/chrome",
    "Clouds": "ace/theme/clouds",
    "Crimson Editor": "ace/theme/crimson_editor",
    "Dawn": "ace/theme/dawn",
    "Dreamweaver": "ace/theme/dreamweaver",
    "Eclipse": "ace/theme/eclipse",
    "GitHub": "ace/theme/github",
    "IPlastic": "ace/theme/iplastic",
    "Solarized Light": "ace/theme/solarized_light",
    "TextMate": "ace/theme/textmate",
    "Tomorrow": "ace/theme/tomorrow",
    "Xcode": "ace/theme/xcode",
    "Kuroir": "ace/theme/kuroir",
    "KatzenMilch": "ace/theme/katzenmilch",
    "SQL Server": "ace/theme/sqlserver",
    "Ambiance": "ace/theme/ambiance",
    "Chaos": "ace/theme/chaos",
    "Clouds Midnight": "ace/theme/clouds_midnight",
    "Dracula": "ace/theme/dracula",
    "Cobalt": "ace/theme/cobalt",
    "Gruvbox": "ace/theme/gruvbox",
    "Green on Black": "ace/theme/gob",
    "idle Fingers": "ace/theme/idle_fingers",
    "krTheme": "ace/theme/kr_theme",
    "Merbivore": "ace/theme/merbivore",
    "Merbivore Soft": "ace/theme/merbivore_soft",
    "Mono Industrial": "ace/theme/mono_industrial",
    "Monokai": "ace/theme/monokai",
    "Nord Dark": "ace/theme/nord_dark",
    "One Dark": "ace/theme/one_dark",
    "Pastel on dark": "ace/theme/pastel_on_dark",
    "Solarized Dark": "ace/theme/solarized_dark",
    "Terminal": "ace/theme/terminal",
    "Tomorrow Night": "ace/theme/tomorrow_night",
    "Tomorrow Night Blue": "ace/theme/tomorrow_night_blue",
    "Tomorrow Night Bright": "ace/theme/tomorrow_night_bright",
    "Tomorrow Night 80s": "ace/theme/tomorrow_night_eighties",
    "Twilight": "ace/theme/twilight",
    "Vibrant Ink": "ace/theme/vibrant_ink",
}


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
        
        starfab.set_key_bindings.connect(function(keyboard_handler) {
            if (keyboard_handler.toLowerCase() == 'default') {
                editor.setKeyboardHandler(null);
            } else {
                editor.setKeyboardHandler('ace/keyboard/' + keyboard_handler.toLowerCase());
            }
        })
        
        starfab.set_str_option.connect(function(path, value) {
            editor.setOption(path, value);
        })
        
        starfab.set_bool_option.connect(function(path, value) {
            editor.setOption(path, value);
        })
        
        starfab.set_theme.connect(function(theme) {
            editor.setTheme(theme);
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

    set_bool_option = Signal(str, bool)
    set_str_option = Signal(str, str)
    set_theme = Signal(str)
    set_key_bindings = Signal(str)

    @Slot(str)
    def session_change(self, message):
        self.changed.emit()

    @Slot()
    def ace_ready(self):
        self.ready.emit()


DEFAULT_THEME = "Monokai"


class Editor(QWebEngineView):
    changed = Signal()

    def __init__(self, editor_item, theme=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.editor_item = editor_item

        we_settings = self.settings()
        we_settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        we_settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        we_settings.setAttribute(QWebEngineSettings.ErrorPageEnabled, True)
        we_settings.setAttribute(QWebEngineSettings.PluginsEnabled, True)

        if parse_bool(os.environ.get('STARFAB_DEBUG_EDITOR', False)):
            self.setContextMenuPolicy(qtc.Qt.CustomContextMenu)

            self.dev_view = QWebEngineView()
            self.page().setDevToolsPage(self.dev_view.page())
            self.dev_view.show()

        self.ace = AceChannel()
        self.channel = QWebChannel()
        self.channel.registerObject("starfab", self.ace)
        self.page().profile().downloadRequested.connect(self._on_download_requested)

        self.ace.ready.connect(self._on_ace_ready)
        self.changed = self.ace.changed

        page = self.page()
        page.setWebChannel(self.channel)
        js = init_js.replace("FILENAME", self.editor_item.name)
        js = js.replace("THEME", theme or settings.value('editor/theme', DEFAULT_THEME))
        h = html.replace("JSJSJS", js)
        page.setHtml(h, qtc.QUrl("qrc:/index.html"))

        settings.settings_updated.connect(self._update_settings)

    def _update_settings(self):
        self.ace.set_theme.emit(THEMES.get(settings.value('editor/theme'), DEFAULT_THEME))
        self.ace.set_key_bindings.emit(settings.value('editor/key_bindings'))
        self.ace.set_str_option.emit('wrap', WRAP_MODES.get(settings.value('editor/word_wrap').lower(), 'off'))
        self.ace.set_bool_option.emit('showLineNumbers', parse_bool(settings.value('editor/line_numbers')))

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
            self._update_settings()
            self.ace.set_value.emit(
                self.editor_item.contents().read().decode("utf-8").replace("\x00", "")
            )
        except Exception as e:
            self.ace.set_value.emit(f"Failed to open {self.editor_item.name}: {e}")
