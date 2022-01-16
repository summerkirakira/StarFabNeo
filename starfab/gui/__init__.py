from qtpy import QtGui as qtg
from qtpy import QtCore as qtc
from qtpy import QtWidgets as qtw

from . import widgets

def gui_scale():
    screen = qtw.QApplication.screens()[0];
    dpi = screen.logicalDotsPerInch()
    return dpi / 96
