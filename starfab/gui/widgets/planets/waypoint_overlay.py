from PySide6.QtCore import QRectF
from PySide6.QtGui import QPen, QPainter, QColor
from PySide6.QtWidgets import QGraphicsEffect

from starfab.planets.planet import WaypointData


class WaypointOverlay(QGraphicsEffect):
    def __init__(self, waypoints: list[WaypointData], selected_waypoint: None | WaypointData, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._waypoints: list[WaypointData] = waypoints
        self._selected_waypoint: None | WaypointData = selected_waypoint

    def draw(self, painter: QPainter) -> None:
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        for waypoint in self._waypoints:
            if self._selected_waypoint and waypoint == self._selected_waypoint:
                painter.setPen(QPen(QColor(0, 255, 0, 255), 10))
                painter.drawEllipse(waypoint.point * 100, 75, 75)
            else:
                painter.setPen(QPen(QColor(255, 0, 0, 255), 10))
                painter.drawEllipse(waypoint.point * 100, 50, 50)


    def update_waypoints(self, waypoints: list[WaypointData]):
        self._waypoints = waypoints
        self.update()

    def select_waypoint(self, waypoint: None | WaypointData):
        self._selected_waypoint = waypoint
        self.update()
