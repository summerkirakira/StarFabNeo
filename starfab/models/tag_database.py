from functools import cached_property

from starfab.gui import qtc
from starfab.log import getLogger
from starfab.models.common import (
    PathArchiveTreeSortFilterProxyModel,
    PathArchiveTreeModel,
    PathArchiveTreeModelLoader,
    SKIP_MODELS,
)

logger = getLogger(__name__)
TAG_DATABASE_COLUMNS = ["Name"]


class TagDatabaseLoader(PathArchiveTreeModelLoader):
    def items_to_load(self):
        self.model.archive = self.model.archive.tag_database
        return self.model.archive.tags_by_guid.values()

    def load_item(self, tag):
        if tag.guid not in self.model._guid_cache:
            self.model._guid_cache[tag.guid] = self._item_cls(tag, self.model)


class TagDatabaseSortFilterProxyModel(PathArchiveTreeSortFilterProxyModel):
    def filterAcceptsRow(self, source_row, source_parent: qtc.QModelIndex) -> bool:
        if self._filter:
            if parent := source_parent.internalPointer():
                try:
                    item = parent.child(source_row)
                    if self.filterCaseSensitivity() == qtc.Qt.CaseSensitivity.CaseInsensitive:
                        return (
                            self._filter.lower() in item.name.lower()
                            or self._filter.lower() in item.guid
                        )
                    else:
                        return self._filter in item.name or self._filter in item.guid
                except IndexError:
                    pass
            return False
        else:
            return True


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

    def has_children(self):
        return bool(self.tag.children)

    @property
    def children(self):
        return self.model.itemForGUID(self.tag.chilren)

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
        if role == qtc.Qt.ItemDataRole.DisplayRole:
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
        return f"<TagTreeItem {repr(self.tag)[1:]}"


class TagDatabaseModel(PathArchiveTreeModel):
    loaded = qtc.Signal()
    unloading = qtc.Signal()
    cancel_loading = qtc.Signal()

    def __init__(self, sc_manager):
        self._guid_cache = {}
        self._sc_manager = sc_manager
        self._loader = None
        self.is_loaded = False

        super().__init__(
            None,
            columns=TAG_DATABASE_COLUMNS,
            item_cls=TagDatabaseTreeItem,
            parent=sc_manager,
        )

        if 'tag_database' in SKIP_MODELS:
            logger.debug(f'Skipping loading the tag_database model')
        else:
            self._sc_manager.datacore_model.loaded.connect(self._on_datacore_loaded)
            self._sc_manager.datacore_model.unloading.connect(
                self._on_datacore_unloading,  # qtc.Qt.BlockingQueuedConnection
            )

    @qtc.Slot()
    def _on_datacore_loaded(self):
        self.load(self._sc_manager.sc)

    @qtc.Slot()
    def _on_datacore_unloading(self):
        self.unload()

    def _setup_root(self):
        if self.archive is not None:
            self.root_item = self._item_cls(self.archive.root_tag, self)
            self._guid_cache[self.root_item.guid] = self.root_item
        else:
            super()._setup_root()

    def itemForName(self, tag_name):
        tag = self.archive.tag(tag_name)
        if tag is not None:
            return self.itemForGUID(tag.guid)
        return None

    def itemForGUID(self, guid):
        return self._guid_cache.get(guid)

    def itemForTag(self, tag):
        return self.itemForGUID(tag.guid)

    def unload(self):
        if self._loader is not None:
            self._loader.cancel.emit()
        self.clear()
        self.is_loaded = False

    def _loaded(self):
        self._setup_root()
        del self._loader
        self._loader = None
        self.is_loaded = True
        self.loaded.emit()

    def load(self, sc):
        if self.is_loaded:
            self.unload()
        self.archive = sc
        self._loader = TagDatabaseLoader(
            self,
            item_cls=TagDatabaseTreeItem,
            task_name="load_tag_db_model",
            task_status_msg="Processing Tag Database",
        )
        self._loader.signals.finished.connect(self._loaded)
        qtc.QThreadPool.globalInstance().start(self._loader)
