from pathlib import Path
from qtpy import uic

from scdatatools.forge import dftypes
from scdatatools.forge.dco import DataCoreRecordObject
from scdatatools.sc.object_container import ObjectContainerInstance, ObjectContainer
from scdatatools.sc.object_container.plotter import ObjectContainerPlotter
from starfab import get_starfab
from starfab.gui import qtw
from starfab.gui.widgets.common import CollapsableWidget
from starfab.gui.widgets.dcbrecord import DCBLazyCollapsableObjWidget
from starfab.gui.widgets.preview3d import LazyCollapsablePreviewWidget
from starfab.hooks import COLLAPSABLE_OBJECT_CONTAINER_WIDGET
from starfab.plugins import plugin_manager
from starfab.resources import RES_PATH

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
    elif isinstance(
            value,
            (
                    dftypes.StructureInstance,
                    dftypes.WeakPointer,
                    dftypes.ClassReference,
                    dftypes.Record,
                    dftypes.StrongPointer,
                    DataCoreObject,
            ),
    ):
        if isinstance(value, DataCoreObject):
            value = value.object
        layout = qtw.QVBoxLayout()
        c = DCBLazyCollapsableObjWidget(name, value)
        layout.addWidget(c)
    else:
        layout = qtw.QVBoxLayout()
        l = qtw.QLineEdit(str(value))
        l.setReadOnly(True)
        layout.addWidget(l)
    layout.setContentsMargins(0, 0, 0, 0)
    widget.setLayout(layout)
    return widget


# class ObjectContainerViewer(qtw.QWidget):
#     def __init__(self, object_container, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.object_container = object_container
#         self.plotter = None
#
#         layout = qtw.QHBoxLayout(self)
#         show_btn = qtw.QPushButton(f'View Object Container')
#         show_btn.clicked.connect(self._show_plotter)
#         layout.addWidget(show_btn)
#
#     def deleteLater(self) -> None:
#         if self.plotter is not None:
#             self.plotter.plotter.clear()
#             self.plotter.plotter.close()
#         super().deleteLater()
#
#     def _show_plotter(self):
#         layout = self.layout()
#         btn = layout.takeAt(0)  # remove the button
#         btn.widget().deleteLater()
#         del btn
#
#         self.setMinimumHeight(480)
#         self.plotter = ObjectContainerPlotter(
#             self.object_container, plotter=QtInteractor(), label_font_size=24, point_max_size=24
#         )
#         layout.addWidget(self.plotter.plotter)


class LazyObjectContainerWidget(CollapsableWidget):
    def __init__(self, child: ObjectContainerInstance, *args, **kwargs):
        self.child = child
        super().__init__(child.label, expand=False, layout=qtw.QVBoxLayout, *args, **kwargs)
        self._loaded = False

    def expand(self):
        if not self._loaded:
            self.obj_widget = ObjectContainerView(self.child, no_scroll=True, parent=self)
            self.content.layout().addWidget(self.obj_widget)
            self._loaded = True
        super().expand()


class LazyContainerChildrenWidget(CollapsableWidget):
    def __init__(self, object_container, label='Children', children_attr='children', *args, **kwargs):
        super().__init__(str(label), expand=False, layout=qtw.QVBoxLayout, *args, **kwargs)
        self.object_container = object_container
        self.children_attr = children_attr
        self._loaded = False

    def expand(self):
        if not self._loaded:
            children = getattr(self.object_container, self.children_attr).items()
            for child_label, child in sorted(children, key=lambda v: v[1].label.lower()):
                child_widget = LazyObjectContainerWidget(child=child)
                self.content.layout().addWidget(child_widget)
            self._loaded = True
        super().expand()


class ObjectContainerView(qtw.QWidget):
    def __init__(self, info_or_path_or_container, extra_attrs=None, no_scroll=False, *args, **kwargs):
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

        self.info = None
        self.object_container = None
        self.name = None

        if isinstance(info_or_path_or_container, (str, Path)):
            self.path = Path(info_or_path_or_container)
            self.name = Path(info_or_path_or_container)
        elif isinstance(info_or_path_or_container, (ObjectContainer, ObjectContainerInstance)):
            self.object_container = info_or_path_or_container
            self.path = Path(
                self.object_container.socpak.filename) if self.object_container.socpak is not None else Path()
            self.name = self.object_container.name
        else:
            self.info = info_or_path_or_container
            self.path = self.info.path
            self.name = self.info.name

        try:
            if self.object_container is None:
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

        attrs = self.object_container.as_dict().copy()
        l = qtw.QLineEdit(attrs.get('name', self.name))
        l.setReadOnly(True)
        self.obj_info.addRow("Name", l)

        l = qtw.QLineEdit(self.path.as_posix())
        l.setReadOnly(True)
        self.obj_info.addRow("Path", l)

        attrs.update(self.extra_attrs)
        attrs_to_show = sorted(attrs.keys(), key=str.casefold)
        attrs_to_show.remove('name')  # name comes first ^

        for attr in attrs_to_show:
            self.obj_info.addRow(attr, widget_for_attr(attr, attrs[attr]))

        try:
            # self.oc_viewer = ObjectContainerViewer(self.object_container)
            self.oc_viewer = LazyCollapsablePreviewWidget(
                preview_kwargs={
                    'plotter_class': ObjectContainerPlotter,
                    'plotter_kwargs': {
                        'object_container': self.object_container,
                        'label_font_size': 24,
                        'point_max_size': 24,
                    }
                }
            )
            self.obj_content.insertWidget(self.obj_content.count() - 1, self.oc_viewer)
        except ImportError:
            pass  # not available

        if isinstance(self.object_container, ObjectContainerInstance):
            self.inserted_children_widget = LazyContainerChildrenWidget(self.object_container,
                                                                        label='Inserted Children',
                                                                        children_attr='inserted_children',
                                                                        parent=self.obj_content_widget)
            self.obj_content.insertWidget(self.obj_content.count() - 1, self.inserted_children_widget)
            self.children_widget = LazyContainerChildrenWidget(self.object_container,
                                                                         label='Children',
                                                                         children_attr='container_children',
                                                                         parent=self.obj_content_widget)
            self.obj_content.insertWidget(self.obj_content.count() - 1, self.children_widget)
            self.inserted_children_widget.show()
        else:
            self.children_widget = LazyContainerChildrenWidget(self.object_container,
                                                               label='Children',
                                                               children_attr='children',
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
