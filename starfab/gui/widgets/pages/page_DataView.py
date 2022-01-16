from qtpy import uic

from starfab.gui.widgets.dock_widgets.datacore_widget import DCBTreeWidget
from starfab.gui.widgets.dock_widgets.tagdatabase_widget import TagDatabaseView
from starfab.gui.widgets.dock_widgets.p4k_widget import P4KView
from starfab.gui.widgets.localization import LocalizationView
from starfab.gui.widgets.action_map import ActionMapView

from starfab.gui import qtg, qtw, qtc
from starfab.resources import RES_PATH


class DataView(qtw.QWidget):
    def __init__(self, starfab):
        super().__init__(parent=None)
        self.starfab = starfab
        uic.loadUi(str(RES_PATH / 'ui' / 'DataView.ui'), self)  # Load the ui into self

        self._open_tabs = {}

        self.sc_tabs.tabCloseRequested.connect(starfab._handle_close_tab)
        self.sc_tabs.tabBar().setContextMenuPolicy(qtc.Qt.CustomContextMenu)
        self.sc_tabs.tabBar().customContextMenuRequested.connect(starfab._handle_tab_ctx_menu)
        self._sc_tab_ctx = None
        self.sc_tabs_ctx_menu = qtw.QMenu()
        self.sc_tabs_ctx_menu.addAction('Close').triggered.connect(starfab._handle_tab_ctx_close)
        self.sc_tabs_ctx_menu.addAction('Close Other Tabs').triggered.connect(starfab._handle_tab_ctx_close_other)
        self.sc_tabs_ctx_menu.addAction('Close All Tabs').triggered.connect(starfab._handle_tab_ctx_close_all)
        self.sc_tabs_ctx_menu.addAction('Close Tabs to the Left').triggered.connect(starfab._handle_tab_ctx_close_left)
        self.sc_tabs_ctx_menu.addAction('Close Tabs to the Right').triggered.connect(
            starfab._handle_tab_ctx_close_right)

        self.page_Data_Datacore.layout().addWidget(DCBTreeWidget(parent=self))
        self.page_Tag_Database.layout().addWidget(TagDatabaseView(parent=self))
        self.tab_DataFiles.layout().addWidget(P4KView(parent=self))

        self._on_wide_tab = False
        self._prev_sizes = (1, 1)
        localization_tab = LocalizationView(self.starfab)
        localization_tab.setObjectName('localization')
        self.tabWidget.addTab(localization_tab, 'Localization')

        actionmap_tab = ActionMapView(self.starfab)
        actionmap_tab.setObjectName('actionmap')
        self.tabWidget.addTab(actionmap_tab, 'Action Map')
        self.tabWidget.currentChanged.connect(self._handle_tab_changed)
        self.splitter.setSizes((500, 1))  # TODO: remember this position and set on reload

    def _handle_tab_changed(self, index):
        tab = self.tabWidget.widget(index)
        if tab.objectName() in ['localization', 'actionmap']:
            if not self._on_wide_tab:
                self._on_wide_tab = True
                self._prev_sizes = self.splitter.sizes()
                self.splitter.setSizes((1, 0))
        elif self._on_wide_tab:
            self._on_wide_tab = False
            self.splitter.setSizes(self._prev_sizes)
            self._prev_sizes = (1, 1)
