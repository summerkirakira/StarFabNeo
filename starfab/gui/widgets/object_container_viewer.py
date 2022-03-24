import json
import logging
from functools import partial
from pathlib import Path

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
from starfab.hooks import COLLAPSABLE_OBJECT_CONTAINER_WIDGET

SUPPORTED_OBJECT_CONTAINER_FILE_FORMATS = [
    ".socpak",
]


def widget_for_attr(name, value):
    widget = qtw.QWidget()
    if isinstance(value, dict):
        layout = qtw.QFormLayout()
        for k, v in sorted(value.items(), key=lambda _: _[0].casefold()):
            layout.addRow(k, widget_for_attr(k, v))
    elif isinstance(value, list):
        layout = qtw.QFormLayout()
        for i, v in enumerate(value):
            layout.addRow(str(i), widget_for_attr(i, v))
    else:
        layout = qtw.QVBoxLayout()
        l = qtw.QLineEdit(str(value))
        l.setReadOnly(True)
        layout.addWidget(l)
    layout.setContentsMargins(0, 0, 0, 0)
    widget.setLayout(layout)
    return widget


class LazyObjectContainerWidget(CollapsableWidget):
    def __init__(self, child_id: str, attrs: dict, *args, **kwargs):
        self.attrs = attrs.copy()
        self.attrs['child_id'] = child_id
        self.name = self.attrs['name']
        self.label = self.attrs.get('label', self.attrs.get('entityName', self.name))
        super().__init__(self.label, expand=False, layout=qtw.QVBoxLayout, *args, **kwargs)
        self._loaded = False

    def expand(self):
        if not self._loaded:
            self.obj_widget = ObjectContainerView(self.name, extra_attrs=self.attrs, no_scroll=True, parent=self)
            self.content.layout().addWidget(self.obj_widget)
            self._loaded = True
        super().expand()


class LazyContainerChildrenWidget(CollapsableWidget):
    def __init__(self, object_container, additional_children=None, *args, **kwargs):
        super().__init__(f"Children", expand=False, layout=qtw.QVBoxLayout, *args, **kwargs)
        self.additional_children = additional_children or {}
        self.object_container = object_container
        self._loaded = False

    def expand(self):
        if not self._loaded:
            children = {**self.object_container.children, **self.additional_children}
            for child_id, attrs in sorted(children.items(), key=lambda v: v[1].get('label', v[0])):
                child_widget = LazyObjectContainerWidget(child_id=child_id, attrs=attrs)
                self.content.layout().addWidget(child_widget)
            self._loaded = True
        super().expand()


class ObjectContainerView(qtw.QWidget):
    def __init__(self, info_or_path, extra_attrs=None, no_scroll=False, *args, **kwargs):
        super().__init__(*args, **kwargs)

        uic.loadUi(str(RES_PATH / "ui" / "ChunkedObjView.ui"), self)

        self.extra_attrs = extra_attrs or {}
        self.starfab = get_starfab()
        self.children_widget = None

        if no_scroll:
            self.scrollArea.takeWidget()
            self.chunked_obj_view_layout.addWidget(self.obj_content_widget)
            self.scrollArea.setVisible(False)
        else:
            self.scrollArea.setWidgetResizable(True)

        # TODO: support dynamically adding actions for object containers from plugins
        self.obj_actions_frame.setVisible(False)

        if isinstance(info_or_path, (str, Path)):
            self.info = None
            self.path = Path(info_or_path)
            self.name = Path(info_or_path)
        else:
            self.info = info_or_path
            self.path = self.info.path
            self.name = self.info.name

        try:
            self.object_container = self.starfab.sc.oc_manager.load_socpak(self.path.as_posix())
        except KeyError:
            self.object_container = None

        if self.object_container is None:
            l = qtw.QLineEdit(self.path.as_posix())
            l.setReadOnly(True)
            self.obj_info.addRow("Path", l)

            l = qtw.QLineEdit('Could not load socpak')
            l.setReadOnly(True)
            self.obj_info.addRow("Error", l)
            return

        l = qtw.QLineEdit(self.object_container.attrs.get('name', self.name))
        l.setReadOnly(True)
        self.obj_info.addRow("Name", l)

        l = qtw.QLineEdit(self.path.as_posix())
        l.setReadOnly(True)
        self.obj_info.addRow("Path", l)

        attrs = self.object_container.attrs.copy()
        attrs.update(self.extra_attrs)
        additional_children = attrs.pop('children') if 'children' in attrs else []
        attrs_to_show = sorted(attrs.keys(), key=str.casefold)
        attrs_to_show.remove('name')  # name comes first ^

        for attr in attrs_to_show:
            self.obj_info.addRow(attr, widget_for_attr(attr, attrs[attr]))

        self.children_widget = LazyContainerChildrenWidget(self.object_container,
                                                           additional_children=additional_children,
                                                           parent=self.obj_content_widget)
        self.obj_content.insertWidget(self.obj_content.count() - 1, self.children_widget)

        self.extra_widgets = []

        try:
            self.extra_widgets.append(
                plugin_manager.handle_hook(
                    COLLAPSABLE_OBJECT_CONTAINER_WIDGET, self.object_container, parent=self
                )
            )
        except plugin_manager.HandlerNotAvailable:
            pass

        for widget in reversed(self.extra_widgets):
            self.children_widget.layout().insertWidget(0, widget)

        self.children_widget.show()

    def deleteLater(self) -> None:
        if self.children_widget is not None:
            self.children_widget.deleteLater()
        for w in self.extra_widgets:
            w.deleteLater()
        super().deleteLater()
