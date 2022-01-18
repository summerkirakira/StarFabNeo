from qtpy.QtCore import QSize, Qt
from qtpy.QtWidgets import QToolButton, QPushButton

from . import gui_scale
from starfab.resources.StyleSheets import get_stylesheet


class RibbonButton(QToolButton):
    def __init__(self, owner, action, is_large=False, link_action=False):
        QToolButton.__init__(self)
        # sc = 1
        sc = gui_scale()

        self._actionOwner = action
        self.update_button_status_from_action()

        if self._actionOwner is not None:
            self.clicked.connect(self._actionOwner.trigger)
            self._actionOwner.changed.connect(self.update_button_status_from_action)

        if is_large:
            self.setMaximumWidth(80 * sc)
            self.setMinimumWidth(50 * sc)
            self.setMinimumHeight(75 * sc)
            self.setMaximumHeight(80 * sc)
            # self.setStyleSheet(get_stylesheet("ribbonButton"))
            self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            self.setIconSize(QSize(32 * sc, 32 * sc))
        else:
            self.setMaximumWidth(180 * sc)
            self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            self.setIconSize(QSize(16 * sc, 16 * sc))
            # self.setStyleSheet(get_stylesheet("ribbonSmallButton"))

        ##TODO: break out another size template to allow for medium sized buttons with 24x24 icon

    def update_button_status_from_action(self):
        self.setText(self._actionOwner.text())
        self.setStatusTip(self._actionOwner.statusTip())
        self.setToolTip(self._actionOwner.toolTip())
        self.setIcon(self._actionOwner.icon())
        self.setEnabled(self._actionOwner.isEnabled())
        self.setCheckable(self._actionOwner.isCheckable())
        self.setChecked(self._actionOwner.isChecked())
