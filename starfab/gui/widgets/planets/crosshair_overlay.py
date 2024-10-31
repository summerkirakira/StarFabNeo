from typing import Union

from PySide6.QtCore import QRectF, QPointF
from PySide6.QtGui import QPen, QPainter
from PySide6.QtWidgets import QGraphicsEffect


class CrosshairOverlay(QGraphicsEffect):
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
