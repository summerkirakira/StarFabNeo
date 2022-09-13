from qtpy import uic

from starfab.gui.widgets.dock_widgets.datacore_widget import DCBTreeWidget
from starfab.gui.widgets.dock_widgets.tagdatabase_widget import TagDatabaseView
from starfab.gui.widgets.dock_widgets.p4k_widget import P4KView
from starfab.gui.widgets.localization import LocalizationView
from starfab.gui.widgets.action_map import ActionMapView

from starfab.gui import qtg, qtw, qtc
from starfab.resources import RES_PATH


class NavView(qtw.QWidget):
    def __init__(self, starfab):
        super().__init__(parent=None)
        self.starfab = starfab
        #uic.loadUi(str(RES_PATH / "ui" / "NavView.ui"), self)  # Load the ui into self

