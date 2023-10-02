import sys
from functools import partial

from starfab.gui import qtc, qtw, qtg
from starfab.gui.widgets.dock_widgets.common import StarFabSearchableTreeWidget
from starfab.log import getLogger
from starfab.models.tag_database import TagDatabaseSortFilterProxyModel

logger = getLogger(__name__)


class TagDatabaseView(StarFabSearchableTreeWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(proxy_model=TagDatabaseSortFilterProxyModel, *args, **kwargs)

        self.starfab.sc_manager.tag_database_model.loaded.connect(
            self.handle_tagdatabase_loaded
        )
        self.handle_tagdatabase_loaded()

        self.ctx_manager.default_menu.addSeparator()
        copy = self.ctx_manager.menus[""].addAction("Copy Tag Name")
        copy.triggered.connect(partial(self.ctx_manager.handle_action, "copy_tag"))

        self.proxy_model.setFilterKeyColumn(0)
        self.proxy_model.setRecursiveFilteringEnabled(True)
        self.proxy_model.setFilterCaseSensitivity(qtc.Qt.CaseInsensitive)
        self.proxy_model.setSortCaseSensitivity(qtc.Qt.CaseInsensitive)

    def _copy_tag_name(self, item):
        cb = qtw.QApplication.clipboard()
        cb.clear(mode=cb.Clipboard)
        cb.setText(str(item.tag), mode=cb.Clipboard)
        self.starfab.statusBar.showMessage(f"Tag {item.tag} copied to the clipboard")

    def keyPressEvent(self, event) -> None:
        if event.key() == qtc.Qt.Key_C:
            if (
                sys.platform == "darwin"
                and qtg.QGuiApplication.keyboardModifiers() == qtc.Qt.MetaModifier
            ) or qtg.QGuiApplication.keyboardModifiers() == qtc.Qt.ControlModifier:
                items = self.get_selected_items()
                if len(items) == 1:
                    self._copy_tag_name(items[0])

    def _handle_item_action(self, item, model, index):
        pass  # TODO: what do we want to do here?

    @qtc.Slot(str)
    def _on_ctx_triggered(self, action):
        if action == "copy_tag":
            items = self.get_selected_items()
            if len(items) == 1:
                return self._copy_tag_name(items[0])
        return super()._on_ctx_triggered(action)

    def handle_tagdatabase_loaded(self):
        if (
            self.starfab.sc_manager.tag_database_model.is_loaded
            and self.sc_tree_model is None
        ):
            self.proxy_model.setSourceModel(self.starfab.sc_manager.tag_database_model)
            self.sc_tree.setModel(self.proxy_model)
            self.proxy_model.sort(0, qtc.Qt.SortOrder.AscendingOrder)

            header = self.sc_tree.header()
            header.setSectionResizeMode(qtw.QHeaderView.ResizeToContents)
            header.setStretchLastSection(False)
            header.setSectionResizeMode(0, qtw.QHeaderView.Stretch)
            self._sync_tree_header()
