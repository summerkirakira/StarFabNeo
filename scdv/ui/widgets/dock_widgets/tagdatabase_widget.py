import sys
import logging
from functools import partial, cached_property

from scdv.ui import qtc, qtw, qtg
from scdv.ui.common import PathArchiveTreeModel, PathArchiveTreeSortFilterProxyModel, PathArchiveTreeItem
from scdv.ui.widgets.dock_widgets.common import SCDVSearchableTreeDockWidget

logger = logging.getLogger(__name__)

TAGDATABASEVIEW_COLUMNS = ['Name']


class TagDatabaseSortFilterProxyModel(PathArchiveTreeSortFilterProxyModel):
    def filterAcceptsRow(self, source_row, source_parent: qtc.QModelIndex) -> bool:
        if self._filter:
            if parent := source_parent.internalPointer():
                try:
                    item = parent.child(source_row)
                    if self.filterCaseSensitivity() == qtc.Qt.CaseInsensitive:
                        return self._filter.lower() in item.name.lower() or self._filter.lower() in item.guid
                    else:
                        return self._filter in item.name or self._filter in item.guid
                except IndexError:
                    pass
            return False
        else:
            return True


class TagDatabaseTreeModel(PathArchiveTreeModel):
    def __init__(self, tag_database, columns=None, item_cls=None, parent=None):
        self._guid_cache = {}

        super().__init__(archive=tag_database, columns=columns, item_cls=item_cls, parent=parent)

        for tag in self.archive.tags_by_guid.values():
            if tag.guid not in self._guid_cache:
                self._guid_cache[tag.guid] = self._item_cls(tag, self)

    def _setup_root(self):
        self.root_item = self._item_cls(self.archive.root_tag, self)
        self._guid_cache[self.root_item.guid] = self.root_item

    def itemForName(self, tag_name):
        tag = self.archive.tag(tag_name)
        if tag is not None:
            return self.itemForGUID(tag.guid)
        return None

    def itemForGUID(self, guid):
        return self._guid_cache.get(guid)

    def itemForTag(self, tag):
        return self.itemForGUID(tag.guid)


class TagDatabaseTreeItem:
    def __init__(self, tag, model):
        self.tag = tag
        self.model = model

    @property
    def name(self):
        return self.tag.name

    @property
    def guid(self):
        return self.tag.guid

    @cached_property
    def parent(self):
        if self.tag.parent is not None:
            return self.model.itemForGUID(self.tag.parent.guid)
        return None

    def row(self):
        if self.parent is not None:
            return self.parent.tag.children.index(self.tag)
        return 0

    def child(self, row):
        try:
            return self.model.itemForGUID(self.tag.children[row].guid)
        except IndexError:
            return None

    def childCount(self):
        return len(self.tag.children)

    def parentItem(self):
        return self.parent

    def data(self, column, role):
        if role == qtc.Qt.DisplayRole:
            if column == 0:
                return self.tag.name
            elif column == 1:
                return self.tag.guid
        # elif role == qtc.Qt.DecorationRole:
        #     if column == 0:
        #         return '🏷️'
        #         return self.icon
        return None

    def __repr__(self):
        return f'<TagTreeItem {repr(self.tag)[1:]}'


class TagDatabaseViewDock(SCDVSearchableTreeDockWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(proxy_model=TagDatabaseSortFilterProxyModel, *args, **kwargs)
        self.setWindowTitle(self.tr('Tag Database'))
        self.scdv.tagdatabase_loaded.connect(self.handle_tagdatabase_loaded)
        self.handle_tagdatabase_loaded()

        self.ctx_manager.default_menu.addSeparator()
        copy = self.ctx_manager.menus[''].addAction('Copy Tag Name')
        copy.triggered.connect(partial(self.ctx_manager.handle_action, 'copy_tag'))

        self.proxy_model.setFilterKeyColumn(0)
        self.proxy_model.setRecursiveFilteringEnabled(True)
        self.proxy_model.setFilterCaseSensitivity(qtc.Qt.CaseInsensitive)
        self.proxy_model.setSortCaseSensitivity(qtc.Qt.CaseInsensitive)

    def _copy_tag_name(self, item):
        cb = qtw.QApplication.clipboard()
        cb.clear(mode=cb.Clipboard)
        cb.setText(str(item.tag), mode=cb.Clipboard)
        self.scdv.statusBar.showMessage(f'Tag {item.tag} copied to the clipboard')

    def keyPressEvent(self, event) -> None:
        if event.key() == qtc.Qt.Key_C:
            if ((sys.platform == 'darwin' and qtg.QGuiApplication.keyboardModifiers() == qtc.Qt.MetaModifier) or
                    qtg.QGuiApplication.keyboardModifiers() == qtc.Qt.ControlModifier):
                items = self.get_selected_items()
                if len(items) == 1:
                    self._copy_tag_name(items[0])

    @qtc.Slot(str)
    def _on_ctx_triggered(self, action):
        if action == 'copy_tag':
            items = self.get_selected_items()
            if len(items) == 1:
                return self._copy_tag_name(items[0])
        return super()._on_ctx_triggered(action)

    def handle_tagdatabase_loaded(self):
        if self.scdv.sc is not None and self.scdv.sc.is_loaded('tag_database') and self.sc_tree_model is None:
            self.show()
            self.sc_tree_model = TagDatabaseTreeModel(tag_database=self.scdv.sc.tag_database,
                                                      columns=TAGDATABASEVIEW_COLUMNS,
                                                      item_cls=TagDatabaseTreeItem, parent=self)
            self.proxy_model.setSourceModel(self.sc_tree_model)
            self.sc_tree.setModel(self.proxy_model)
            self.proxy_model.sort(0, qtc.Qt.SortOrder.AscendingOrder)

            header = self.sc_tree.header()
            header.setSectionResizeMode(qtw.QHeaderView.ResizeToContents)
            header.setStretchLastSection(False)
            header.setSectionResizeMode(0, qtw.QHeaderView.Stretch)
            self.raise_()
