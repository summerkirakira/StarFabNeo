import json

from qtpy import uic

from scdatatools.engine.chunkfile import chunks, load_chunk_file, GeometryChunkFile

from starfab import get_starfab
from starfab.gui import qtc, qtw, qtg
from starfab.resources import RES_PATH
from starfab.models.common import ContentItem
from starfab.gui.widgets.editor import Editor
from starfab.gui.widgets.common import CollapsableWidget
from starfab.plugins import plugin_manager
from starfab.hooks import COLLAPSABLE_GEOMETRY_PREVIEW_WIDGET


SUPPORTED_CHUNK_FILE_FORMATS = [
    ".cga",
    ".cgam",
    ".cgf",
    ".cgfm",
    ".chr",
    ".soc",
    ".dba",
    ".skin",
    ".skinm",
]


def widget_for_chunk(info, obj, chunk, inline=False):
    widget = qtw.QWidget()
    layout = qtw.QHBoxLayout()

    if isinstance(chunk, (chunks.CryXMLBChunk, chunks.JSONChunk)):
        e = Editor(
            ContentItem(
                f"{info.path.name}:{chunk.chunk_header.id}.json",
                info.path,
                json.dumps(chunk.dict(), indent=2),
            ),
            parent=widget,
        )
        e.setMinimumHeight(600)
        layout.addWidget(e)
    elif isinstance(chunk, chunks.SourceInfoChunk):
        e = Editor(
            ContentItem(
                f"{info.path.name}:{chunk.chunk_header.id}.txt",
                info.path,
                chunk.chunk_data.data,
            ),
            parent=widget,
        )
        e.setMinimumHeight(400)
        layout.addWidget(e)
    else:
        try:
            l = qtw.QLabel(str(chunk))
        except Exception as e:
            l = qtw.QLabel(f"Exception reading {repr(chunk)}: {repr(e)}")
        l.setFrameStyle(qtw.QFrame.StyledPanel | qtw.QFrame.Sunken)
        l.setTextInteractionFlags(qtc.Qt.TextSelectableByMouse)
        layout.addWidget(l)

    widget.setSizePolicy(qtw.QSizePolicy.Expanding, qtw.QSizePolicy.Preferred)
    widget.setLayout(layout)
    return widget


class ChunkedObjWidget(qtw.QWidget):
    def __init__(self, info, obj, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.info = info
        self.obj = obj

        layout = qtw.QVBoxLayout()

        for chunkid, chunk in sorted(self.obj.chunks.items(), key=lambda x: str(x[0])):
            section = CollapsableWidget(
                f"{chunkid} - {chunk.chunk_header.type.name}", layout=qtw.QVBoxLayout
            )
            section.content.layout().addWidget(
                widget_for_chunk(self.info, self.obj, chunk)
            )
            layout.addWidget(section)

        self.setLayout(layout)


class LazyChunkDetailsWidget(CollapsableWidget):
    def __init__(self, info, obj, *args, **kwargs):
        super().__init__(f"Chunk Details", expand=False, *args, **kwargs)
        self._loaded = False
        self.content.setLayout(qtw.QVBoxLayout())
        self.obj = obj
        self.info = info
        self.obj_widget = None

    def expand(self):
        if not self._loaded:
            self.obj_widget = ChunkedObjWidget(self.info, self.obj, parent=self)
            self.content.layout().addWidget(self.obj_widget)
            self._loaded = True
        super().expand()


class ChunkedObjView(qtw.QWidget):
    def __init__(self, info, *args, **kwargs):
        super().__init__(*args, **kwargs)

        uic.loadUi(str(RES_PATH / "ui" / "ChunkedObjView.ui"), self)

        self.starfab = get_starfab()
        self.info = info

        self.obj = load_chunk_file(info.info, auto_load_mesh=True)

        l = qtw.QLineEdit(info.name)
        l.setReadOnly(True)
        self.obj_info.addRow("Name", l)

        l = qtw.QLineEdit(info.path.as_posix())
        l.setReadOnly(True)
        self.obj_info.addRow("Path", l)

        l = qtw.QLineEdit(self.obj.header.file_type)
        l.setReadOnly(True)
        self.obj_info.addRow("Type", l)

        self.scrollArea.setWidgetResizable(True)

        # TODO: support dynamically adding actions for chunked objects from plugins
        self.obj_actions_frame.setVisible(False)

        # self.obj_widget = ChunkedObjWidget(self.info, self.obj, parent=self)
        self.obj_widget = LazyChunkDetailsWidget(self.info, self.obj)
        self.obj_content.insertWidget(self.obj_content.count() - 1, self.obj_widget)

        self.extra_widgets = []

        if isinstance(self.obj, GeometryChunkFile):
            try:
                self.extra_widgets.append(
                    plugin_manager.handle_hook(
                        COLLAPSABLE_GEOMETRY_PREVIEW_WIDGET, self.obj, parent=self
                    )
                )
            except plugin_manager.HandlerNotAvailable:
                pass

        # TODO: add hooks to let other widget types to get in here

        for widget in reversed(self.extra_widgets):
            self.obj_widget.layout().insertWidget(0, widget)

        self.obj_widget.show()

    def deleteLater(self) -> None:
        self.obj_widget.deleteLater()
        for w in self.extra_widgets:
            w.deleteLater()
        super().deleteLater()
