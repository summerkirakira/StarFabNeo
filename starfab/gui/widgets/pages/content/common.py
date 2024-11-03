from scdatatools.forge.utils import geometry_for_record
from starfab.gui import qtc, qtw
from starfab.gui.widgets.dock_widgets.common import StarFabSearchableTreeWidget
from starfab.gui.widgets.dock_widgets.datacore_widget import DCBFilterWidget
from starfab.models.common import CheckableModelWrapper


class AlternateRootModel(CheckableModelWrapper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._root_item = None

    @property
    def root_item(self):
        return self._root_item or self._model.root_item

    @root_item.setter
    def root_item(self, item):
        self._root_item = item

    def parent(self, index: qtc.QModelIndex):
        if not index.isValid():
            return qtc.QModelIndex()

        child = index.internalPointer()
        if child == self._root_item:
            return qtc.QModelIndex()
        return super().parent(index)


class ContentSelector(StarFabSearchableTreeWidget):
    def __init__(self, *args, content_page=None, **kwargs):
        super().__init__(parent=content_page, *args, **kwargs)
        self.content_page = content_page
        # self.filter_frame.setVisible(False)

        select_all = self.ctx_manager.menus[""].addAction("Select All")
        select_all.triggered.connect(self.select_all)
        deselect_all = self.ctx_manager.menus[""].addAction("Deselect All")
        deselect_all.triggered.connect(self.deselect_all)

    def _create_filter(self):
        raise NotImplementedError()

    def select_all(self):
        self.sc_tree_model.select_all()

    def deselect_all(self):
        self.sc_tree_model.deselect_all()

    def checked_items(self):
        return []

    def _handle_item_action(self, item, model, index):
        pass


class P4KContentSelector(ContentSelector):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.starfab.sc_manager.p4k_model.loaded.connect(self._handle_p4k_loaded)

    @qtc.Slot()
    def _handle_p4k_loaded(self):
        self.proxy_model.setSourceModel(self.sc_tree_model)
        self.proxy_model.sort(0, qtc.Qt.SortOrder.AscendingOrder)
        self.sc_tree.setModel(self.proxy_model)

        header = self.sc_tree.header()
        header.setSectionResizeMode(qtw.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, qtw.QHeaderView.ResizeMode.Stretch)
        self.sc_tree.hideColumn(1)
        self.sc_tree.hideColumn(2)
        self.sc_tree.hideColumn(3)


class DCBContentSelector(ContentSelector):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.starfab.sc_manager.datacore_model.loaded.connect(
            self._handle_datacore_loaded
        )

    def _create_filter(self):
        return DCBFilterWidget(self)

    @qtc.Slot()
    def _handle_datacore_loaded(self):
        self.proxy_model.setSourceModel(self.sc_tree_model)
        self.proxy_model.sort(0, qtc.Qt.SortOrder.AscendingOrder)
        self.sc_tree.setModel(self.proxy_model)

        header = self.sc_tree.header()
        header.setSectionResizeMode(qtw.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, qtw.QHeaderView.ResizeMode.Stretch)
        self.sc_tree.hideColumn(1)

    def _handle_item_action(self, item, model, index):
        if (
            self.content_page is not None
            and (g := geometry_for_record(item.record, self.starfab.sc.p4k)) is not None
        ):
            self.content_page.preview_chunkfile(g)
