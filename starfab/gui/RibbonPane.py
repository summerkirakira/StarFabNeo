from qtpy import QtGui
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QGridLayout,
    QButtonGroup,
)
from . import gui_scale
from starfab.resources.StyleSheets import get_stylesheet


class RibbonPane(QWidget):
    def __init__(self, parent, name):
        QWidget.__init__(self, parent)
        # self.setStyleSheet(get_stylesheet("ribbonPane"))
        horizontal_layout = QHBoxLayout()
        horizontal_layout.setSpacing(2)
        horizontal_layout.setContentsMargins(1, 2, 1, 0)
        self.setLayout(horizontal_layout)
        vertical_widget = QWidget(self)
        horizontal_layout.addWidget(vertical_widget)
        horizontal_layout.addWidget(RibbonSeparator(self))
        vertical_layout = QVBoxLayout()
        vertical_layout.setSpacing(0)
        vertical_layout.setContentsMargins(1, 2, 1, 0)
        vertical_widget.setLayout(vertical_layout)
        label = QLabel(name)
        label.setAlignment(Qt.AlignCenter)
        content_widget = QWidget(self)
        vertical_layout.addWidget(content_widget)
        vertical_layout.addWidget(label)
        content_layout = QHBoxLayout()
        content_layout.setAlignment(Qt.AlignLeft)
        content_layout.setSpacing(2)
        content_layout.setContentsMargins(4, 0, 4, 1)
        self.contentLayout = content_layout
        content_widget.setLayout(content_layout)

    def add_ribbon_widget(self, widget):
        self.contentLayout.addWidget(widget, 0, Qt.AlignTop)

    def add_grid_widget(self, width):
        widget = QWidget()
        widget.setMaximumWidth(width)
        grid_layout = QGridLayout()
        widget.setLayout(grid_layout)
        grid_layout.setSpacing(4)
        grid_layout.setContentsMargins(4, 4, 4, 4)
        self.contentLayout.addWidget(widget)
        grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        return grid_layout


class RibbonSeparator(QWidget):
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.setMinimumHeight(gui_scale() * 80)
        self.setMaximumHeight(gui_scale() * 80)
        self.setMinimumWidth(1)
        self.setMaximumWidth(1)
        self.setLayout(QHBoxLayout())

    def paintEvent(self, event):
        qp = QtGui.QPainter()
        qp.begin(self)
        qp.fillRect(event.rect(), Qt.lightGray)
        qp.end()
