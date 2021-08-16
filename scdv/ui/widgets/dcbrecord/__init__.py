from functools import partial

from qtpy import uic

from scdatatools.forge import dftypes

from scdv import get_scdv
from scdv.ui import qtw, qtc, qtg
from scdv.resources import RES_PATH
from scdv.ui.common import ContentItem
from scdv.ui.widgets.common import CollapseableWidget
from scdv.ui.widgets.editor import Editor


def _handle_open_record(guid):
    scdv = get_scdv()
    obj = scdv.sc.datacore.records_by_guid.get(guid)
    if obj is not None:
        item = scdv.dock_widgets['dcb_view'].sc_tree_model.itemForGUID(obj.id.value)
        if item is not None:
            widget = DCBRecordItemView(item, scdv)
            objid = f'{item.guid}:{item.path.as_posix()}'
            scdv.add_tab_widget(objid, widget, item.name, tooltip=objid)


def widget_for_dcb_obj(name, obj):
    widget = qtw.QWidget()
    layout = qtw.QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    scdv = get_scdv()
    if isinstance(
            obj,
            (
                    dftypes.StructureInstance,
                    dftypes.WeakPointer,
                    dftypes.ClassReference,
                    dftypes.Record,
                    dftypes.StrongPointer,
            ),
    ):
        c = DCBLazyCollapsableObjWidget(name, obj)
        layout.addWidget(c)
    elif isinstance(obj, dftypes.Reference):
        v = obj.value.value
        l = qtw.QLineEdit(v)
        l.setCursorPosition(0)
        l.setReadOnly(True)
        layout.addWidget(l)

        if scdv is not None and obj.value.value in obj.dcb.records_by_guid:
            ref = obj.dcb.records_by_guid[obj.value.value]
            if ref.type == 'Tag':
                l.setText(str(scdv.sc.tag_database.tags_by_guid[obj.value.value]))
                l.setCursorPosition(0)
            else:
                l.setText(f'{ref.name} ({obj.value.value})')
                l.setCursorPosition(0)
            b = qtw.QPushButton("→")
            b.setFixedSize(24, 24)
            b.clicked.connect(partial(_handle_open_record, obj.value.value))
            layout.addWidget(b)
    else:
        try:
            v = str(obj.value)
        except AttributeError:
            v = str(obj)
        l = qtw.QLineEdit(v)
        l.setCursorPosition(0)
        l.setReadOnly(True)
        layout.addWidget(l)

        if scdv is not None and isinstance(obj, dftypes.GUID) and obj.value in obj.dcb.records_by_guid:
            ref = obj.dcb.records_by_guid[obj.value]
            l.setText(f'{ref.name} ({obj.value})')
            l.setCursorPosition(0)
            b = qtw.QPushButton("→")
            b.setFixedSize(24, 24)
            b.clicked.connect(partial(_handle_open_record, obj.value))
            layout.addWidget(b)

    widget.setLayout(layout)
    return widget


class DCBLazyCollapsableObjWidget(CollapseableWidget):
    def __init__(self, label, obj, *args, **kwargs):
        super().__init__(label, expand=False, *args, **kwargs)
        self._loaded = False
        self.content.setLayout(qtw.QVBoxLayout())
        self.obj = obj

    def expand(self):
        if not self._loaded:
            r = DCBObjWidget(self.obj)
            self.content.layout().addWidget(r)
            self._loaded = True
        super().expand()


class DCBObjWidget(qtw.QWidget):
    def __init__(self, obj, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.obj = obj

        layout = qtw.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        list_props = []
        props = []
        for name, value in sorted(self.obj.properties.items()):
            if isinstance(value, list):
                list_props.append(name)
            else:
                props.append(name)

        props_widget = qtw.QWidget(parent=self)
        props_layout = qtw.QFormLayout()
        props_layout.setContentsMargins(0, 0, 0, 0)
        props_layout.setLabelAlignment(qtc.Qt.AlignLeft | qtc.Qt.AlignTop)

        for name in sorted(props):
            props_layout.addRow(name, widget_for_dcb_obj(name, self.obj.properties[name]))
        props_widget.setLayout(props_layout)
        layout.addWidget(props_widget)

        for name in sorted(list_props):
            section = CollapseableWidget(name)
            for i, item in enumerate(sorted(self.obj.properties[name], key=lambda o: getattr(o, 'name', ''))):
                section.content.layout().addRow(f"{i}", widget_for_dcb_obj(item.name, item))
            layout.addWidget(section)

        self.setLayout(layout)


class DCBRecordItemView(qtw.QWidget):
    def __init__(self, record_item, scdv, *args, **kwargs):
        super().__init__(*args, **kwargs)

        uic.loadUi(str(RES_PATH / 'ui' / 'DCBRecordView.ui'), self)

        self.scdv = scdv
        self.record_item = record_item
        self.datacore = record_item.archive

        l = qtw.QLineEdit(record_item.record.name)
        l.setReadOnly(True)
        self.record_info.addRow('Name', l)

        l = qtw.QLineEdit(record_item.record.type)
        l.setReadOnly(True)
        self.record_info.addRow('Type', l)

        l = qtw.QLineEdit(record_item.record.id.value)
        l.setReadOnly(True)
        self.record_info.addRow('GUID', l)

        l = qtw.QLineEdit(record_item.record.filename)
        l.setReadOnly(True)
        self.record_info.addRow('Path', l)

        b = qtw.QPushButton('View XML')
        b.clicked.connect(self._on_view_xml)
        self.record_actions.insertWidget(self.record_actions.count() - 1, b)

        b = qtw.QPushButton('View JSON')
        b.clicked.connect(self._on_view_json)
        self.record_actions.insertWidget(self.record_actions.count() - 1, b)

        self.scrollArea.setWidgetResizable(True)
        self.record_widget = DCBObjWidget(self.record_item.record, parent=self)
        self.record_content.insertWidget(self.record_content.count() - 1, self.record_widget)
        self.record_widget.show()

    def _on_view(self, mode):
        content_item = ContentItem(self.record_item.name, self.record_item.path, self.record_item.contents(mode=mode))
        widget = Editor(content_item)
        if widget is not None:
            self.scdv.add_tab_widget(f'{self.record_item.path}:{mode}_editor', widget, self.record_item.path.name)

    def _on_view_xml(self):
        self._on_view('xml')

    def _on_view_json(self):
        self._on_view('json')
