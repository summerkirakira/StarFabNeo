from typing import Union, cast

import PySide6
from PIL import Image
from PIL.ImageQt import ImageQt
from PySide6.QtCore import QPointF, QRect, QRectF, QPoint, Signal, QSizeF
from PySide6.QtGui import QPainterPath, QColor, QTransform, QBrush, QPen, Qt, QPainter, QMouseEvent, QPixmap, QImage
from PySide6.QtWidgets import QGraphicsPathItem, QGraphicsEffect

from starfab.gui import qtc, qtg, qtw
from starfab.gui.widgets.image_viewer import QImageViewer
from starfab.planets.planet_renderer import RenderResult


class QPlanetViewer(qtw.QGraphicsView):
    mouse_moved: Signal = Signal(QPointF)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            # Image-space coordinates are always 0-360,000 (* 1000 to map closer to pixel sizes generally)
            self._scale_factor: int = 100
            self._outer_perimeter: QRectF = QRectF()
            self._render_perimeter: QRectF = QRectF()
            self._render_result: None | RenderResult = None

            self._empty = True
            self._zoom = 0
            self._zoom_factor = 1.25
            # we start at a 0 zoom level when the image is changed and we fill the view with it
            self._min_zoom = -2
            self._max_zoom = 50

            self._major_grid_pen = QPen(QColor(255, 255, 255, 255), 50)
            self._minor_grid_pen = QPen(QColor(200, 200, 200, 255), 20)
            self._crosshair_pen = QPen(QColor(255, 0, 0, 255), 20)

            self.setCursor(Qt.CrossCursor)

            self.scene = qtw.QGraphicsScene()
            self.scene.setBackgroundBrush(QColor(0, 0, 0, 255))
            self.setScene(self.scene)

            self.setTransformationAnchor(qtw.QGraphicsView.AnchorUnderMouse)
            self.setResizeAnchor(qtw.QGraphicsView.AnchorUnderMouse)
            self.setFrameShape(qtw.QFrame.NoFrame)
            self.setDragMode(qtw.QGraphicsView.ScrollHandDrag)

            self.image: qtw.QGraphicsPixmapItem = qtw.QGraphicsPixmapItem()
            self.scene.addItem(self.image)

            self.perimeter_path: QPainterPath = QPainterPath()
            self.render_outline: QPainterPath = QPainterPath()
            self.perimeter_rect: QGraphicsPathItem = QGraphicsPathItem(self.perimeter_path)
            self.crosshair_overlay: QGraphicsPathItem = QGraphicsPathItem(self.perimeter_path)
            self.render_window: QGraphicsPathItem = QGraphicsPathItem(self.render_outline)
            self.perimeter_effect: None | GridEffect = None
            self.crosshair_overlay_effect: None | CrosshairEffect = None
            self.update_bounds(QRectF(0, -90, 360, 180), QRectF(0, -90, 180, 90))

            self._grid_enabled = False
            self.perimeter_rect.setZValue(1000)
            self.set_grid_enabled(True)
            self.scene.addItem(self.perimeter_rect)

            self._crosshair_enabled = False
            self.crosshair_overlay.setZValue(2000)
            self.set_crosshair_enabled(True)
            self.scene.addItem(self.crosshair_overlay)

            self.render_window.setPen(QPen(QColor(0, 255, 0, 255), 20))
            self.render_window.setZValue(3000)
            self.scene.addItem(self.render_window)
            self.render_window_dragging: bool = False
            self.render_window_drag_pos: None | QPointF = None

            self.setMouseTracking(True)
            self.image.setCursor(Qt.CrossCursor)
            self.render_window.setCursor(Qt.SizeAllCursor)
            self.fitInView(self._render_perimeter, Qt.KeepAspectRatio)
            self.ensureVisible(QRectF(0, 0, 100, 100))
            self.setDragMode(qtw.QGraphicsView.ScrollHandDrag)
        except Exception as ex:
            print(ex)
            raise ex

    def update_bounds(self, bounding_rect: QRectF, render_rect: QRectF):
        self._outer_perimeter: QRectF = QRectF(bounding_rect.topLeft() * self._scale_factor,
                                               bounding_rect.size() * self._scale_factor)
        self._render_perimeter: QRectF = QRectF(render_rect.topLeft() * self._scale_factor,
                                                render_rect.size() * self._scale_factor)

        # Update paths
        self.perimeter_path.clear()
        self.perimeter_path.addRect(self._outer_perimeter)
        self.render_outline.clear()
        self.render_outline.addRect(self._render_perimeter)

        # Add some extra padding around the planet bounds.
        image_padding = 10 * self._scale_factor
        scene_area = QRectF(self._outer_perimeter.x() - image_padding,
                            self._outer_perimeter.y() - image_padding,
                            self._outer_perimeter.width() + 2 * image_padding,
                            self._outer_perimeter.height() + 2 * image_padding)
        self.scene.setSceneRect(scene_area)

        if self.perimeter_effect:
            self.perimeter_effect.planet_bounds = self._outer_perimeter
        if self.crosshair_overlay_effect:
            self.crosshair_overlay_effect.planet_bounds = self._outer_perimeter
        self.perimeter_rect.setPath(self.perimeter_path)
        self.crosshair_overlay.setPath(self.perimeter_path)
        self.render_window.setPath(self.render_outline)
        self.perimeter_rect.update()
        self.crosshair_overlay.update()
        self.scene.update()
        self.update()

    def get_render_coords(self):
        return QRectF(self._render_perimeter.topLeft() / self._scale_factor,
                      self._render_perimeter.size() / self._scale_factor)

    def mousePressEvent(self, event: PySide6.QtGui.QMouseEvent) -> None:
        image_space_pos = self.mapToScene(event.pos())
        global_coordinates = self.image_to_coordinates(image_space_pos)

        if event.button() == Qt.RightButton and \
                self._render_perimeter.contains(image_space_pos):
            self.render_window_dragging = True
            self.render_window_drag_pos = image_space_pos
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        image_space_pos = self.mapToScene(event.pos())
        global_coordinates = self.image_to_coordinates(image_space_pos)

        if self.render_window_dragging:
            delta = image_space_pos - self.render_window_drag_pos
            drag_bounds = QRectF(self._outer_perimeter.topLeft(),
                                 self._outer_perimeter.size() - self._render_perimeter.size())

            self.render_window_drag_pos = image_space_pos
            self._render_perimeter.translate(delta)

            final_position_x = max(drag_bounds.left(), min(drag_bounds.right(), self._render_perimeter.x()))
            final_position_y = max(drag_bounds.top(), min(drag_bounds.bottom(), self._render_perimeter.y()))
            self._render_perimeter.setRect(final_position_x, final_position_y,
                                           self._render_perimeter.width(), self._render_perimeter.height())

            self.render_outline.clear()
            self.render_outline.addRect(self._render_perimeter)
            self.render_window.setPath(self.render_outline)
        else:
            super().mouseMoveEvent(event)

        self.mouse_moved.emit(global_coordinates)
        if self.crosshair_overlay_effect:
            self.crosshair_overlay_effect.update_mouse_position(image_space_pos)
            self.crosshair_overlay.update(self._outer_perimeter)

    def mouseReleaseEvent(self, event: PySide6.QtGui.QMouseEvent) -> None:
        image_space_pos = self.mapToScene(event.pos())
        global_coordinates = self.image_to_coordinates(image_space_pos)

        self.render_window_dragging = False

        super().mouseReleaseEvent(event)

    def image_to_coordinates(self, image_position: QPointF) -> QPointF:
        return QPointF(image_position.x() / self._scale_factor, image_position.y() / self._scale_factor)

    def update_render(self, new_render: RenderResult, layer: str):
        self._render_result = new_render
        self.update_visible_layer(layer)

    def update_visible_layer(self, layer: str):
        if not self._render_result:
            return

        s = self._scale_factor
        img = None
        if layer == "surface":
            img = self._render_result.tex_color
        elif layer == "heightmap":
            img = self._render_result.tex_heightmap
        else:
            raise Exception(f"Unknown layer: {layer}")

        qt_image: QPixmap = QPixmap.fromImage(ImageQt(img))
        width_scale = self._render_result.coordinate_bounds.width() / qt_image.width()
        self.image.setPixmap(qt_image)
        self.image.setPos(self._render_result.coordinate_bounds.left() * s,
                          self._render_result.coordinate_bounds.top() * s)
        # TODO: Better support non-standard render sizes
        self.image.setScale(width_scale * s)

    def set_grid_enabled(self, enabled: bool):
        self._grid_enabled = enabled
        if enabled:
            # Need to rebuild each time as it gets disposed of
            self.perimeter_effect = GridEffect(self._major_grid_pen, self._minor_grid_pen,
                                               self._scale_factor, self._outer_perimeter)
            self.perimeter_rect.setGraphicsEffect(self.perimeter_effect)
        else:
            self.perimeter_rect.setGraphicsEffect(None)
            self.perimeter_effect = None
        self.update()
        self.scene.update()

    def set_crosshair_enabled(self, enabled: bool):
        self._crosshair_enabled = enabled
        if enabled:
            # Need to rebuild each time as it gets disposed of
            self.crosshair_overlay_effect = CrosshairEffect(self._crosshair_pen, self._outer_perimeter)
            self.crosshair_overlay.setGraphicsEffect(self.crosshair_overlay_effect)
        else:
            self.crosshair_overlay.setGraphicsEffect(None)
            self.crosshair_overlay_effect = None
        self.update()
        self.scene.update()

    def wheelEvent(self, event):
        factor = 0
        if event.angleDelta().y() > 0:
            if self._zoom < self._max_zoom:
                factor = self._zoom_factor
                self._zoom += 1
        else:
            if self._zoom > self._min_zoom:
                factor = 1 / self._zoom_factor
                self._zoom -= 1
        if factor:
            self.scale(factor, factor)


class CrosshairEffect(QGraphicsEffect):
    def __init__(self, pen: QPen, region: QRectF, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mouse_position: Union[QPointF, None] = None
        self.pen = pen
        self.planet_bounds = region

    def update_mouse_position(self, pos: QPointF):
        self.mouse_position = pos

    def remove_mouse(self):
        self.mouse_position = None

    def draw(self, painter: QPainter) -> None:
        if not self.mouse_position:
            return

        vp = self.planet_bounds
        painter.setPen(self.pen)
        painter.drawLine(vp.left(), self.mouse_position.y(), vp.right(), self.mouse_position.y())
        painter.drawLine(self.mouse_position.x(), vp.top(), self.mouse_position.x(), vp.bottom())
        painter.drawRect(vp)


class GridEffect(QGraphicsEffect):
    def __init__(self,
                 primary_pen: QPen, secondary_pen: QPen,
                 scale_factor: int, planet_bounds: QRectF,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.primary_pen = primary_pen
        self.secondary_pen = secondary_pen
        self.scale_factor = scale_factor
        self.planet_bounds = planet_bounds

    def draw(self, painter: QPainter) -> None:
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Difference)
        self._draw_lines(painter, self.primary_pen, True)
        self._draw_lines(painter, self.secondary_pen, False)

    def _draw_lines(self, painter: QPainter, pen: QPen, primary: bool):
        painter.setPen(pen)
        xoff = self.planet_bounds.x()
        yoff = self.planet_bounds.y()
        for lon in range(15, 360, 15):
            is_primary = lon % 45 == 0
            if (is_primary and primary) or (not is_primary and not primary):
                painter.drawLine(lon * self.scale_factor + xoff, self.planet_bounds.top(),
                                 lon * self.scale_factor + xoff, self.planet_bounds.bottom())

        for lat in range(15, 180, 15):
            is_primary = lat % 45 == 0
            if (is_primary and primary) or (not is_primary and not primary):
                painter.drawLine(self.planet_bounds.left(), lat * self.scale_factor + yoff,
                                 self.planet_bounds.right(), lat * self.scale_factor + yoff)
