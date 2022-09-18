import typing
from functools import partial

import qtawesome as qta
from pyvistaqt import QtInteractor
from vtkmodules.vtkInteractionWidgets import vtkCameraOrientationWidget

from starfab.gui import qtg, qtw, qtc
from starfab.gui.widgets.common import CollapsableWidget
from starfab.gui.widgets.dock_widgets.common import StarFabStaticWidget
from starfab.log import getLogger

logger = getLogger(__name__)


def _add_toggle_action(toolbar, icon, text, callable, checked=False):
    a = toolbar.addAction(icon, text)
    a.triggered.connect(callable)
    a.setCheckable(True)
    a.setChecked(checked)
    return a


class PreviewPopOut(qtw.QDialog):
    def __init__(self, preview, title=''):
        super().__init__(
            parent=None,
            f=(qtc.Qt.WindowTitleHint | qtc.Qt.WindowSystemMenuHint | qtc.Qt.WindowMinimizeButtonHint
               | qtc.Qt.WindowMaximizeButtonHint | qtc.Qt.WindowCloseButtonHint)
        )
        self.setWindowTitle('Preview' if not title else f'Preview - {title}')
        self.preview = preview
        layout = qtw.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(preview.preview_widget)
        self.setLayout(layout)

    def closeEvent(self, event):
        event.ignore()
        self.preview.pop_in()


class Preview3D(StarFabStaticWidget):
    def __init__(self, title='', resize_grip=True, allow_popout=True, hide_buttons: typing.List[str] = None,
                 tabs: typing.Dict[str, str] = None, plotter=None, plotter_class=QtInteractor, plotter_kwargs=None,
                 parent=None):
        super().__init__(parent)

        self.layout = qtw.QVBoxLayout(self)

        self.title = title
        self.preview_widget = qtw.QWidget(self)

        self.tabs = {}
        self.tabbar = qtw.QTabBar()
        self.layout.addWidget(self.tabbar)
        self.tabbar.tabBarClicked.connect(self._handle_tab_changed)

        preview_layout = qtw.QHBoxLayout()
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)

        self.toolbar = qtw.QToolBar(self)
        self.toolbar.setOrientation(qtc.Qt.Vertical)
        preview_layout.addWidget(self.toolbar)

        self.plotter_class = plotter_class
        self.plotter_kwargs = plotter_kwargs or {}
        self.plotter_kwargs.setdefault('parent', self)
        self.plotter = plotter or self.plotter_class(**self.plotter_kwargs)
        self.cam_orient_widget = vtkCameraOrientationWidget()
        self.cam_orient_widget.SetParentRenderer(self.plotter.renderer)

        preview_layout.addWidget(self.plotter)
        self.preview_widget.setLayout(preview_layout)
        self.layout.addWidget(self.preview_widget)

        # region toolbar actions
        self._orientation_widget_action = _add_toggle_action(
            self.toolbar, qta.icon('ph.globe-simple'), 'Toggle Orientation Widget', self.enable_orientation_widget,
        )
        self._axes_widget_action = _add_toggle_action(
            self.toolbar, qta.icon('ph.asterisk'), 'Toggle Axes', self.enable_axes,
        )
        self._parallel_projection_action = _add_toggle_action(
            self.toolbar, qta.icon('ph.equals'), "Toggle Parallel Projection", self.enable_parallel_projection
        )

        self.toolbar.addSeparator()

        self._bounds_grid_action = _add_toggle_action(
            self.toolbar, qta.icon('ph.grid-four'), "Toggle Bounds Grid", self.enable_bounds_grid
        )
        self._bounding_box_action = _add_toggle_action(
            self.toolbar, qta.icon('ph.cube'), "Toggle Bounding Box", self.enable_bounding_box
        )

        self.toolbar.addSeparator()

        self.toolbar.addAction(qta.icon('ph.arrow-clockwise'), 'Reset Camera', self.reset_view)

        self._pop_out_action = self.toolbar.addAction(qta.icon('ph.arrows-out'), 'Pop-out', self.pop_out)
        self._pop_in_action = self.toolbar.addAction(qta.icon('ph.arrows-in'), 'Pop-in', self.pop_in)
        self._pop_in_action.setVisible(False)

        self._clear_action = self.toolbar.addAction(qta.icon('ph.x-circle'), 'Clear', partial(self.clear, tabs=True))

        self.set_allow_popout(allow_popout)
        self.hide_buttons(hide_buttons or [])
        # endregion toolbar actions

        self._pop_out_dlg = None
        self.grip_size = qtc.QPoint(10, 10)
        self.resize_grip = resize_grip
        self._resizing = True
        self._old_pos = None

        self.set_tabs(tabs)

    def set_plotter(self, new_plotter: QtInteractor):
        self.clear()
        self.preview_widget.layout().replaceWidget(self.plotter, new_plotter)
        del self.plotter
        self.plotter = new_plotter

    def set_tabs(self, tabs: typing.Dict[str, str] = None):
        for i in range(self.tabbar.count()):
            self.tabbar.removeTab(0)
        self.tabs = tabs or {}
        if len(self.tabs) == 1:
            # only one tab, dont show the tab bar
            self._handle_tab_changed(0)
            self.tabs = {}
        for label, mesh in self.tabs.items():
            self.tabbar.addTab(label or 'Base')
        if self.tabs:
            self._handle_tab_changed(0)

    def _handle_tab_changed(self, index):
        self.clear()
        self.load_tab(index)
        self.reset_view()

    def hide_buttons(self, buttons_to_hide: typing.List[str]):
        for _ in buttons_to_hide:
            if btn := getattr(self, f'_{_}_action'):
                btn.setVisible(False)

    def load_tab(self, index):
        pass

    def set_allow_popout(self, allowed):
        self._pop_out_action.setVisible(allowed)
        self._pop_in_action.setVisible(allowed)

    @qtc.Slot()
    def pop_out(self):
        if self._pop_out_dlg is not None:
            return

        self.layout.removeWidget(self.preview_widget)
        self._pop_out_dlg = PreviewPopOut(self, self.title)
        self._pop_out_dlg.show()

        self._pop_in_action.setVisible(True)
        self._pop_out_action.setVisible(False)

    @qtc.Slot()
    def pop_in(self):
        if self._pop_out_dlg is None:
            return

        self._pop_out_dlg.hide()
        self._pop_out_dlg.deleteLater()
        self._pop_out_dlg = None
        self.layout.addWidget(self.preview_widget)
        self._pop_in_action.setVisible(False)
        self._pop_out_action.setVisible(True)

    @qtc.Slot()
    def reset_view(self):
        self.plotter.reset_camera()
        self.plotter.view_vector((1, 1, 1), (0, 0, 1))

    @qtc.Slot(bool)
    def enable_orientation_widget(self, enabled=True):
        if enabled:
            self.cam_orient_widget.On()
        else:
            self.cam_orient_widget.Off()
        self._orientation_widget_action.setChecked(enabled)

    @qtc.Slot(bool)
    def enable_axes(self, enabled=True):
        if enabled:
            self.plotter.add_axes(labels_off=True)
        else:
            self.plotter.hide_axes()
        self._axes_widget_action.setChecked(enabled)

    @qtc.Slot(bool)
    def enable_parallel_projection(self, enabled=True):
        if enabled:
            self.plotter.enable_parallel_projection()
        else:
            self.plotter.disable_parallel_projection()
        self._parallel_projection_action.setChecked(enabled)

    @qtc.Slot(bool)
    def enable_bounds_grid(self, enabled=True):
        if enabled:
            self.plotter.show_grid()
        else:
            self.plotter.remove_bounds_axes()
        self._bounds_grid_action.setChecked(enabled)

    @qtc.Slot(bool)
    def enable_bounding_box(self, enabled=True):
        if enabled:
            self.plotter.add_bounding_box()
        else:
            self.plotter.remove_bounding_box()
        self._bounding_box_action.setChecked(enabled)

    def mouseInGrip(self, pos: qtc.QPoint):
        return (
                pos.x() > (self.width() - self.grip_size.x()) and
                pos.y() > (self.height() - self.grip_size.y())
        )

    def mousePressEvent(self, event):
        if self.resize_grip and self.mouseInGrip(event.pos()):
            self._old_pos = event.pos()
            self._resizing = True
            return None
        else:
            self._resizing = False
        return super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing:
            delta = event.pos() - self._old_pos
            self._old_pos = event.pos()
            self.setMinimumSize(self.width() + delta.x(), self.height() + delta.y())
            self.updateGeometry()
            return None
        return super().mouseMoveEvent(event)

    def hideEvent(self, event):
        self.pop_in()
        return super().hideEvent(event)

    def _close(self):
        self.pop_in()
        self.plotter.close()

    def closeEvent(self, event):
        self._close()
        return super().closeEvent(event)

    def deleteLater(self) -> None:
        self._close()
        return super().deleteLater()

    def close(self):
        self._close()
        return super().close()

    def clear(self, tabs=False):
        for actor in list(self.plotter.renderer.actors.keys()):
            self.plotter.remove_actor(actor)
        # self.plotter.clear()   # this doesnt do what we'd expect, so just clear all the actors
        if tabs:
            self.set_tabs(None)
        self.reset_view()


class LazyCollapsablePreviewWidget(CollapsableWidget):
    def __init__(self, previewer: Preview3D = Preview3D, loader: typing.Callable = None, label='Preview',
                 min_size=(1024, 768), preview_kwargs=None, *args, **kwargs):
        super().__init__(f'{label}', expand=False, *args, **kwargs)
        self._loaded = False
        self._previewer = previewer
        self.content.setLayout(qtw.QVBoxLayout())
        self._loader = loader or self.load
        self.min_size = min_size
        self._preview_kwargs = preview_kwargs or {}

        content_layout = self.content.layout()
        content_layout.setSpacing(0)
        content_layout.setContentsMargins(0, 0, 0, 0)

    def load(self, prev):
        return

    def expand(self):
        if not self._loaded:
            prev = self._previewer(hide_buttons=['clear'], **self._preview_kwargs)
            prev.setMinimumSize(*self.min_size)
            prev.setSizePolicy(
                qtw.QSizePolicy(qtw.QSizePolicy.Expanding, qtw.QSizePolicy.Expanding)
            )
            self.content.layout().addWidget(prev)
            super().expand()  # this is a workaround for the orientation widget showing up bugged
            qtg.QGuiApplication.processEvents()

            try:
                self._loader(prev)
            except Exception as e:
                prev.plotter.add_text("Failed to load preview", position='lower_left')
                logger.exception(f'Failed to generate preview: {e}')
            self._loaded = True
        super().expand()
