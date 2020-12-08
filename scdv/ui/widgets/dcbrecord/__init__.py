from functools import partial

from qtpy import uic
from qtpy.QtCore import Slot, Signal

from scdatatools.forge import dftypes

from scdv import get_scdv
from scdv.ui import qtc, qtw, qtg
from scdv.resources import RES_PATH
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


def widget_for_dcb_obj(obj, inline=False):
    widget = qtw.QWidget()
    layout = qtw.QHBoxLayout()
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
        c = DCBLazyCollapsableObjWidget(obj.name, obj)
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
                l.setText(f'{ref.properties["tagName"]} ({obj.value.value})')
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


class CollapseableWidget(qtw.QWidget):
    def __init__(self, label, expand=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.label = label
        self.expanded = expand

        self.main_layout = qtw.QVBoxLayout()
        self.main_layout.setMargin(0)
        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.expand_button = qtw.QPushButton(label)
        self.expand_button.setStyleSheet('text-align: left; padding-left: 5px;')

        self.content = qtw.QWidget()
        self.content.setLayout(qtw.QFormLayout())
        self.main_layout.addWidget(self.expand_button, 0, qtc.Qt.AlignTop)
        self.main_layout.addWidget(self.content, 0, qtc.Qt.AlignTop)
        self.expand_button.clicked.connect(self.toggle)
        self.setLayout(self.main_layout)

        if expand:
            self.expand()
        else:
            self.collapse()

    def collapse(self):
        self.content.hide()
        self.expand_button.setText(f'▼  {self.label}')
        self.expanded = False

    def expand(self):
        self.content.show()
        self.expand_button.setText(f'▲  {self.label}')
        self.expanded = True

    @Slot()
    def toggle(self):
        if self.expanded:
            self.collapse()
        else:
            self.expand()


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
        list_props = []
        props = []
        for name, value in self.obj.properties.items():
            if isinstance(value, list):
                list_props.append(name)
            else:
                props.append(name)

        props_widget = qtw.QWidget(parent=self)
        props_layout = qtw.QFormLayout()
        for name in sorted(props):
            props_layout.addRow(name, widget_for_dcb_obj(self.obj.properties[name], True))
        props_widget.setLayout(props_layout)
        layout.addWidget(props_widget)

        for name in sorted(list_props):
            section = CollapseableWidget(name)
            for i, item in enumerate(self.obj.properties[name]):
                section.content.layout().addRow(f"{i}", widget_for_dcb_obj(item))
            layout.addWidget(section)

        self.setLayout(layout)


class DCBRecordItemView(qtw.QWidget):
    def __init__(self, record_item, scdv, *args, **kwargs):
        super().__init__(*args, **kwargs)

        uic.loadUi(str(RES_PATH / 'ui' / 'DCBRecordView.ui'), self)

        self.scdv = scdv
        self.record_item = record_item
        self.datacore = record_item.parent_archive

        l = qtw.QLineEdit(record_item.name)
        l.setReadOnly(True)
        self.record_info.addRow('Name', l)

        l = qtw.QLineEdit(record_item.type)
        l.setReadOnly(True)
        self.record_info.addRow('Type', l)

        l = qtw.QLineEdit(record_item.guid)
        l.setReadOnly(True)
        self.record_info.addRow('GUID', l)

        l = qtw.QLineEdit(record_item.path.as_posix())
        l.setReadOnly(True)
        self.record_info.addRow('Path', l)

        b = qtw.QPushButton('View JSON')
        b.clicked.connect(self._on_view_xml)
        self.record_actions.insertWidget(self.record_actions.count() - 1, b)

        self.scrollArea.setWidgetResizable(True)
        self.record_widget = DCBObjWidget(self.record_item.record, parent=self)
        self.record_content.insertWidget(self.record_content.count() - 1, self.record_widget)
        self.record_widget.show()

    def _on_view_xml(self):
        widget = Editor(self.record_item)
        if widget is not None:
            self.scdv.add_tab_widget(f'{self.record_item.path}:editor', widget, self.record_item.path.name)
