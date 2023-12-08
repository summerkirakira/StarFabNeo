import PySide6
from PIL import Image
from PIL.ImageQt import ImageQt
from PySide6.QtCore import QPointF, QRect, QRectF, QPoint
from PySide6.QtGui import QPainterPath, QColor, QTransform, QBrush, QPen, Qt, QPainter
from PySide6.QtWidgets import QGraphicsPathItem, QGraphicsEffect

from starfab.gui import qtc, qtg, qtw
from starfab.gui.widgets.image_viewer import QImageViewer
from starfab.planets.planet_renderer import RenderResult


class QPlanetViewer(qtw.QGraphicsView):
    def __init__(self, *args, **kwargs):
        # Image-space coordinates are always 0-360,000 (* 1000 to map closer to pixel sizes generally)
        self._outer_perimeter: QRectF = QRectF(0, 0, 360 * 100, 180 * 100)

        super().__init__(*args, **kwargs)
        self._empty = True

        self._zoom = 0
        self._zoom_factor = 1.25
        # we start at a 0 zoom level when the image is changed and we fill the view with it
        self._min_zoom = -2
        self._max_zoom = 50

        self._major_grid_pen = QPen(QColor(255, 255, 255, 255), 50)
        self._minor_grid_pen = QPen(QColor(200, 200, 200, 255), 20)

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
        self._update_perimeter()

        self.perimeter_rect: QGraphicsPathItem = QGraphicsPathItem(self.perimeter_path)
        self.perimeter_rect.setZValue(1000)
        self.perimeter_rect.setGraphicsEffect(GridEffect(self._major_grid_pen, self._minor_grid_pen))
        self.scene.addItem(self.perimeter_rect)

        image_padding = 10000
        # Add some extra padding around the planet bounds.
        scene_area = QRectF(self._outer_perimeter.x() - image_padding,
                            self._outer_perimeter.y() - image_padding,
                            self._outer_perimeter.width() + 2 * image_padding,
                            self._outer_perimeter.height() + 2 * image_padding)
        self.scene.setSceneRect(scene_area)
        self.fitInView(self.image)

    def update_render(self, new_render: RenderResult):
        image: Image = new_render.tex_color
        self.setImage(ImageQt(image))

    def _update_perimeter(self):
        self.perimeter_path.clear()
        self.perimeter_path.addRect(self._outer_perimeter)

    def setImage(self, image: Image.Image):
        """Set the scene's current image pixmap to the input QImage or QPixmap.
        Raises a RuntimeError if the input image has type other than QImage or QPixmap.
        :type image: QImage | QPixmap
        :type fit: bool
        """
        self._zoom = 0
        if isinstance(image, qtg.QPixmap):
            pixmap = image
        elif isinstance(image, qtg.QImage):
            pixmap = qtg.QPixmap.fromImage(image)
        else:
            raise ValueError(
                "QImageViewer.setImage: Argument must be a QImage or QPixmap."
            )
        if pixmap and not pixmap.isNull():
            self._empty = False
            self.setDragMode(qtw.QGraphicsView.ScrollHandDrag)
            self.image.setPixmap(pixmap)
        else:
            self._empty = True
            self.setDragMode(qtw.QGraphicsView.NoDrag)
            self.image.setPixmap(qtg.QPixmap())
        width_scale = self._outer_perimeter.width() / image.width()
        height_scale = self._outer_perimeter.height() / image.height()
        image_transform: QTransform = QTransform\
            .fromScale(width_scale, height_scale) \
            .translate(self._outer_perimeter.x(), self._outer_perimeter.y())
        self.image.setTransform(image_transform)

        self.fitInView(self.perimeter_rect, Qt.KeepAspectRatio)

    def hasImage(self):
        """Returns whether or not the scene contains an image pixmap."""
        return not self._empty

    def wheelEvent(self, event):
        if self.hasImage():
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


class GridEffect(QGraphicsEffect):
    def __init__(self, primary_pen: QPen, secondary_pen: QPen, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.primary_pen = primary_pen
        self.secondary_pen = secondary_pen

    def draw(self, painter: QPainter) -> None:
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Difference)
        self._draw_lines(painter, self.primary_pen, True)
        self._draw_lines(painter, self.secondary_pen, False)

    @staticmethod
    def _draw_lines(painter: QPainter, pen: QPen, primary: bool):
        painter.setPen(pen)
        for lon in range(15, 360, 15):
            is_primary = lon % 45 == 0
            if (is_primary and primary) or (not is_primary and not primary):
                painter.drawLine(lon * 100, 0, lon * 100, 180 * 100)

        for lat in range(15, 180, 15):
            is_primary = lat % 45 == 0
            if (is_primary and primary) or (not is_primary and not primary):
                painter.drawLine(0, lat * 100, 360 * 100, lat * 100)
