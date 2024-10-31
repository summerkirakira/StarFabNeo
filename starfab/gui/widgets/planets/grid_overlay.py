from PySide6.QtCore import QRectF
from PySide6.QtGui import QPen, QPainter
from PySide6.QtWidgets import QGraphicsEffect


class GridOverlay(QGraphicsEffect):
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
