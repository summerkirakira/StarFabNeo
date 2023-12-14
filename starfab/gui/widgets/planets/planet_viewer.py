from typing import cast

import PySide6
from PIL.ImageQt import ImageQt
from PySide6.QtCore import QPointF, QRectF, Signal
from PySide6.QtGui import QPainterPath, QColor, QPen, Qt, QMouseEvent, QPixmap
from PySide6.QtWidgets import QGraphicsPathItem

from starfab.gui import qtw
from starfab.gui.widgets.planets.crosshair_overlay import CrosshairOverlay
from starfab.gui.widgets.planets.grid_overlay import GridOverlay

from starfab.gui.widgets.planets.effect_overlay import EffectOverlay
from starfab.planets.planet_renderer import RenderResult


class QPlanetViewer(qtw.QGraphicsView):
    crosshair_moved: Signal = Signal(QPointF)
    render_window_moved: Signal = Signal(QRectF)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            # Image-space coordinates are always 0-360,000 (* 1000 to map closer to pixel sizes generally)
            self._scale_factor: int = 100
            self._outer_perimeter: QRectF = QRectF()
            self._render_perimeter: QRectF = QRectF()
            self._crosshair_position: QPointF = QPointF()
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

            self.lyr_grid: EffectOverlay = EffectOverlay(
                lambda: GridOverlay(self._major_grid_pen, self._minor_grid_pen,
                                    self._scale_factor, self._outer_perimeter))
            self.lyr_grid.setZValue(1000)
            self.scene.addItem(self.lyr_grid)

            self.lyr_crosshair: EffectOverlay = EffectOverlay(
                lambda: CrosshairOverlay(self._crosshair_pen, self._outer_perimeter))
            self.lyr_crosshair.setZValue(2000)
            self.scene.addItem(self.lyr_crosshair)

            self.lyr_render: EffectOverlay = EffectOverlay(lambda: None)
            self.lyr_render.setPen(QPen(QColor(0, 255, 0, 255), 20))
            self.lyr_render.setZValue(3000)
            self.scene.addItem(self.lyr_render)

            self.update_bounds(QRectF(0, -90, 360, 180), QRectF(0, -90, 360, 180))

            self.render_window_dragging: bool = False
            self.render_window_drag_pos: None | QPointF = None

            self.lyr_grid.set_enabled(True)
            self.lyr_crosshair.set_enabled(True)
            self.lyr_render.set_enabled(True)

            self.setMouseTracking(True)
            self.image.setCursor(Qt.CrossCursor)
            self.lyr_render.setCursor(Qt.SizeAllCursor)
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

        # Add some extra padding around the planet bounds.
        image_padding = 10 * self._scale_factor
        scene_area = QRectF(self._outer_perimeter.x() - image_padding,
                            self._outer_perimeter.y() - image_padding,
                            self._outer_perimeter.width() + 2 * image_padding,
                            self._outer_perimeter.height() + 2 * image_padding)
        self.scene.setSceneRect(scene_area)

        self.lyr_grid.update_bounds(self._outer_perimeter)
        self.lyr_crosshair.update_bounds(self._outer_perimeter)
        self.lyr_render.update_bounds(self._render_perimeter)
        self.scene.update()
        self.update()

    def get_render_coords(self):
        return QRectF(self._render_perimeter.topLeft() / self._scale_factor,
                      self._render_perimeter.size() / self._scale_factor)

    def get_crosshair_coords(self) -> QPointF:
        return self._crosshair_position

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

            self.lyr_render.update_bounds(self._render_perimeter)
            self.render_window_moved.emit(self._render_perimeter)
        else:
            super().mouseMoveEvent(event)

        self._crosshair_position = global_coordinates
        self.crosshair_moved.emit(self._crosshair_position)

        crosshair_overlay: CrosshairOverlay = cast(CrosshairOverlay, self.lyr_crosshair.effect_instance())
        if crosshair_overlay:
            crosshair_overlay.update_mouse_position(image_space_pos)
            self.lyr_crosshair.invalidate()

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
