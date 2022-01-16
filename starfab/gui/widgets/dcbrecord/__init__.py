import json
import logging
from functools import partial

from qtpy import uic

from scdatatools.forge import dftypes
from scdatatools.forge.utils import geometry_for_record

from starfab import get_starfab
from starfab.gui import qtw, qtc, qtg
from starfab.resources import RES_PATH
from starfab.models.common import ContentItem
from starfab.gui.widgets.editor import Editor
from starfab.gui.widgets.common import CollapsableWidget
from starfab.plugins import plugin_manager
from starfab.hooks import COLLAPSABLE_GEOMETRY_PREVIEW_WIDGET


DCB_OBJ_WIDGETS_HOOK = 'starfab.gui.widgets.dcbrecord.dcbobjview'


def _handle_open_record(guid):
    starfab = get_starfab()
    obj = starfab.sc.datacore.records_by_guid.get(guid)
    if obj is not None:
        item = starfab.dock_widgets['dcb_view'].sc_tree_model.itemForGUID(obj.id.value)
        if item is not None:
            widget = DCBRecordItemView(item, starfab)
            objid = f'{item.guid}:{item.path.as_posix()}'
            starfab.add_tab_widget(objid, widget, item.name, tooltip=objid)


def widget_for_dcb_obj(name, obj, parent=None):
    widget = qtw.QWidget()
    layout = qtw.QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    starfab = get_starfab()
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
        c = DCBLazyCollapsableObjWidget(name, obj, parent=parent)
        layout.addWidget(c)
    elif isinstance(obj, dftypes.Reference):
        v = obj.value.value
        l = qtw.QLineEdit(v, parent=parent)
        l.setCursorPosition(0)
        l.setReadOnly(True)
        layout.addWidget(l)

        if starfab is not None and obj.value.value in obj.dcb.records_by_guid:
            ref = obj.dcb.records_by_guid[obj.value.value]
            if ref.type == 'Tag':
                l.setText(str(starfab.sc.tag_database.tags_by_guid[obj.value.value]))
                l.setCursorPosition(0)
            else:
                l.setText(f'{ref.name} ({obj.value.value})')
                l.setCursorPosition(0)
            b = qtw.QPushButton("→", parent=parent)
            b.setFixedSize(24, 24)
            b.clicked.connect(partial(_handle_open_record, obj.value.value))
            layout.addWidget(b)
    else:
        try:
            v = str(obj.value)
        except AttributeError:
            v = str(obj)
        l = qtw.QLineEdit(v, parent=parent)
        l.setCursorPosition(0)
        l.setReadOnly(True)
        layout.addWidget(l)

        if starfab is not None and isinstance(obj, dftypes.GUID) and obj.value in obj.dcb.records_by_guid:
            ref = obj.dcb.records_by_guid[obj.value]
            l.setText(f'{ref.name} ({obj.value})')
            l.setCursorPosition(0)
            b = qtw.QPushButton("→", parent=parent)
            b.setFixedSize(24, 24)
            b.clicked.connect(partial(_handle_open_record, obj.value))
            layout.addWidget(b)

    widget.setLayout(layout)
    return widget


class DCBLazyCollapsableObjWidget(CollapsableWidget):
    def __init__(self, label, obj, *args, **kwargs):
        super().__init__(f'📙 {label}', expand=False, *args, **kwargs)
        self._loaded = False
        self.content.setLayout(qtw.QVBoxLayout())
        self.obj_name = label
        self.obj = obj

    def contains(self, text):
        print(text)

    def _build_ctx_menu(self):
        menu = super()._build_ctx_menu()
        copy_json = menu.addAction('Copy as JSON')
        copy_json.triggered.connect(self.copy_as_json)
        return menu

    def copy_as_json(self):
        try:
            rec = {self.obj_name: get_starfab().sc.datacore.record_to_dict(self.obj)}

            cb = qtw.QApplication.clipboard()
            cb.clear(mode=cb.Clipboard)
            cb.setText(json.dumps(rec, indent=2, default=str, sort_keys=True), mode=cb.Clipboard)
        except Exception as e:
            get_starfab().statusBar.showMessage(f'Failed to copy object: {e}')

    def expand(self):
        if not self._loaded:
            r = DCBObjWidget(self.obj)
            self.content.layout().addWidget(r)
            self._loaded = True
        super().expand()

    def filter(self, text, ignore_case=True):
        if not text:
            _ = True
        elif ignore_case:
            _ = (super().filter(text, ignore_case) or
                 text.lower() in get_starfab().sc.datacore.dump_record_json(self.obj, depth=1).lower())
        else:
            _ = (super().filter(text, ignore_case) or
                 text in get_starfab().sc.datacore.dump_record_json(self.obj, depth=1))
        self.setVisible(_)
        return _


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
            props_layout.addRow(name, widget_for_dcb_obj(name, self.obj.properties[name], self))
        props_widget.setLayout(props_layout)
        layout.addWidget(props_widget)

        for name in sorted(list_props):
            section = CollapsableWidget(name)
            for i, item in enumerate(sorted(self.obj.properties[name], key=lambda o: getattr(o, 'name', ''))):
                section.content.layout().addRow(f"{i}", widget_for_dcb_obj(getattr(item, 'name', str(i)), item, self))
            layout.addWidget(section)

        self.setLayout(layout)

    def subObjects(self):
        subs = []
        for child in self.children():
            for cw in child.findChildren(qtw.QWidget, 'CollapseableWidget'):
                subs.append(cw)
        return subs

    def filter(self, text, ignore_case=True):
        for so in self.subObjects():
            if hasattr(so, 'filter'):
                so.filter(text, ignore_case)


class DCBRecordItemView(qtw.QWidget):
    def __init__(self, record_item, starfab, *args, **kwargs):
        super().__init__(*args, **kwargs)

        uic.loadUi(str(RES_PATH / 'ui' / 'DCBRecordView.ui'), self)

        self.starfab = starfab
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

        self.extra_widgets = []

        self.geom_file = geometry_for_record(self.record_item.record, self.starfab.sc.p4k)
        if self.geom_file is not None:
            try:
                self.extra_widgets.append(
                    plugin_manager.handle_hook(COLLAPSABLE_GEOMETRY_PREVIEW_WIDGET, self.geom_file, parent=self)
                )
            except plugin_manager.HandlerNotAvailable:
                pass

        self.record_widgets.insertWidget(0, self.record_widget)

        # TODO: add hooks to let other widget types to get in here

        for widget in reversed(self.extra_widgets):
            self.record_widgets.insertWidget(0, widget)

        self.record_widget.show()

        self.record_filter.editingFinished.connect(self._on_filter_changed)

    def _on_filter_changed(self):
        self.record_widget.filter(self.record_filter.text())

    def _on_view(self, mode):
        content_item = ContentItem(self.record_item.name, self.record_item.path, self.record_item.contents(mode=mode))
        widget = Editor(content_item)
        if widget is not None:
            self.starfab.add_tab_widget(f'{self.record_item.path}:{mode}_editor', widget,
                                        f'{self.record_item.path.name} ({mode})')

    def _on_view_xml(self):
        self._on_view('xml')

    def _on_view_json(self):
        self._on_view('json')

    def deleteLater(self) -> None:
        for w in self.extra_widgets:
            w.deleteLater()
        super().deleteLater()
