from typing import Type, Callable, Any, Union

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainterPath
from PySide6.QtWidgets import QGraphicsPathItem, QGraphicsEffect


class EffectOverlay(QGraphicsPathItem):
    def __init__(self, fn_make_effect: Callable[[], Union[None | QGraphicsEffect]]):
        self._bounds: QRectF = QRectF()
        self._bounds_path = QPainterPath()
        self._overlay_effect: Union[None, QGraphicsEffect] = None
        self._enabled: bool = False
        self._fn_make_effect: Callable = fn_make_effect
        super().__init__(self._bounds_path)
        # self.set_enabled(True)

    def update_bounds(self, new_bounds: QRectF):
        self._bounds = new_bounds
        self._bounds_path.clear()
        self._bounds_path.addRect(self._bounds)
        self.setPath(self._bounds_path)
        self.invalidate()
        print(new_bounds)
        print(self._bounds_path.boundingRect())

    def invalidate(self):
        self.update(self._bounds)

    def set_enabled(self, enabled: bool):
        self._enabled = enabled
        if self._enabled:
            # Need to rebuild each time as it gets disposed of
            self._overlay_effect = self._fn_make_effect()
            self.setGraphicsEffect(self._overlay_effect)
        else:
            self.setGraphicsEffect(None)
            self._overlay_effect = None
        self.invalidate()

    def effect_instance(self) -> Union[None, QGraphicsEffect]:
        return self._overlay_effect
