import io
import json
from functools import partial

from qtpy import uic
from qtpy.QtCore import Slot, Signal

from scdatatools.cry.model import chunks
from scdatatools.cry.model.chcr import ChCr
from scdatatools.cry.model.ivo import Ivo, IVO_FILE_SIGNATURE

from scdv import get_scdv
from scdv.ui import qtc, qtw, qtg
from scdv.resources import RES_PATH
from scdv.ui.widgets.editor import Editor
from scdv.ui.widgets.common import CollapseableWidget
from scdv.ui.utils import ContentItem


SUPPORTED_CHUNK_FILE_FORMATS = [
   'cga', 'cgam', 'cgf', 'cgfm', 'chr', 'soc', 'dba', 'skin', 'skinm'
]


def widget_for_chunk(info, obj, chunk, inline=False):
    widget = qtw.QWidget()
    layout = qtw.QHBoxLayout()
    scdv = get_scdv()

    if isinstance(chunk, (chunks.CryXMLBChunk, chunks.JSONChunk)):
        e = Editor(ContentItem(f'{info.path.name}:{chunk.header.id}', info.path, json.dumps(chunk.dict(), indent=4)),
                   parent=widget)
        e.setMinimumHeight(600)
        layout.addWidget(e)
    elif isinstance(chunk, chunks.SourceInfoChunk):
        e = Editor(ContentItem(f'{info.path.name}:{chunk.header.id}', info.path, chunk.data), parent=widget)
        e.setMinimumHeight(400)
        layout.addWidget(e)
    else:
        try:
            l = qtw.QLabel(str(chunk))
        except Exception as e:
            l = qtw.QLabel(f'Exception reading {repr(chunk)}: {repr(e)}')
        l.setFrameStyle(qtw.QFrame.StyledPanel | qtw.QFrame.Sunken)
        l.setTextInteractionFlags(qtc.Qt.TextSelectableByMouse)
        layout.addWidget(l)

    widget.setLayout(layout)
    return widget


class ChunkedObjWidget(qtw.QWidget):
    def __init__(self, info, obj, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.info = info
        self.obj = obj

        layout = qtw.QVBoxLayout()

        for chunkid, chunk in sorted(self.obj.chunks.items(), key=lambda x: x[0]):
            section = CollapseableWidget(f'{chunkid} - {chunk.header.type.name}', layout=qtw.QVBoxLayout)
            section.content.layout().addWidget(widget_for_chunk(self.info, self.obj, chunk))
            layout.addWidget(section)

        self.setLayout(layout)


class ChunkedObjView(qtw.QWidget):
    def __init__(self, info, *args, **kwargs):
        super().__init__(*args, **kwargs)

        uic.loadUi(str(RES_PATH / 'ui' / 'ChunkedObjView.ui'), self)

        self.scdv = get_scdv()
        self.info = info

        raw = info.contents()
        if isinstance(raw, io.BytesIO):
            raw = raw.read()
        if raw.startswith(IVO_FILE_SIGNATURE):
            self.obj = Ivo(raw)
            self.type = 'Ivo'
        else:
            self.type = 'ChCr'
            self.obj = ChCr(raw)

        l = qtw.QLineEdit(info.name)
        l.setReadOnly(True)
        self.obj_info.addRow('Name', l)

        l = qtw.QLineEdit(info.path.as_posix())
        l.setReadOnly(True)
        self.obj_info.addRow('Path', l)

        l = qtw.QLineEdit(self.type)
        l.setReadOnly(True)
        self.obj_info.addRow('Type', l)

        self.scrollArea.setWidgetResizable(True)
        self.obj_widget = ChunkedObjWidget(self.info, self.obj, parent=self)
        self.obj_content.insertWidget(self.obj_content.count() - 1, self.obj_widget)
        self.obj_widget.show()
