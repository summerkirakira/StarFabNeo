import io
from functools import cached_property

from starfab import get_starfab
from starfab.gui import qtc
from starfab.gui.utils import icon_provider
from starfab.log import getLogger

from starfab.models.common import (
    PathArchiveTreeSortFilterProxyModel,
    PathArchiveTreeModelLoader,
    ThreadLoadedPathArchiveTreeModel,
    PathArchiveTreeItem,
    ContentItem,
    SKIP_MODELS,
)

logger = getLogger(__name__)
DCBVIEW_COLUMNS = ["Name", "Type"]
RECORDS_ROOT_PATH = "libs/foundry/records/"


class DCBSortFilterProxyModel(PathArchiveTreeSortFilterProxyModel):
    def filterAcceptsRow(self, source_row, source_parent: qtc.QModelIndex) -> bool:
        if not self._filter and not self.additional_filters:
            return True

        if (parent := source_parent.internalPointer()) is None:
            parent = getattr(self.sourceModel(), 'root_item')
        if parent:
            try:
                item = parent.children[source_row]
            except IndexError:
                return False
            if not self.checkAdditionFilters(item):
                return False
            if not self._filter and item.record is not None:
                return True  # additional filters true and not a folder
            if self._filter:
                if self.filterCaseSensitivity() == qtc.Qt.CaseInsensitive:
                    return (
                        self._filter.lower() in item._path.lower()
                        or self._filter.lower() in item.guid
                    )
                else:
                    return self._filter in item._path or self._filter in item.guid
        return False


class DCBLoader(PathArchiveTreeModelLoader):
    def items_to_load(self):
        # trigger datacore to load here
        # TODO: there is probably a better place to trigger the ac_manager to load, but meh
        self.model.archive.attachable_component_manager.load_attachable_components()
        self.model.archive = self.model.archive.datacore
        if 'datacore' in SKIP_MODELS:
            logger.debug(f'Skipping loading the datacore model')
            return []
        return self.model.archive.records

    def load_item(self, item):
        path = item.filename.replace(RECORDS_ROOT_PATH, "")
        parent_path, _ = path.rsplit("/", maxsplit=1) if "/" in path else ("", path)
        parent = self.model.parentForPath(parent_path)

        # name = name.replace(".xml", "")
        name = item.name
        if name in parent.children_by_name:
            name = f"{name}.{item.id.value}"

        new_item = self._item_cls(
            f"{parent_path}/{name}", model=self.model, record=item, parent=parent
        )
        self.model._guid_cache[new_item.guid] = new_item


class DCBItem(PathArchiveTreeItem, ContentItem):
    _cached_properties_ = PathArchiveTreeItem._cached_properties_ + ["guid", "type"]

    def __init__(self, path, model, record=None, parent=None):
        super().__init__(path, model, parent)
        self.record = record

    @cached_property
    def icon(self):
        if self.children:
            return icon_provider.icon(icon_provider.IconType.Folder)
        return icon_provider.icon(icon_provider.IconType.File)

    @cached_property
    def guid(self):
        if self.record is not None:
            return self.record.id.value
        return ""

    @cached_property
    def type(self):
        if self.record is not None:
            return self.record.type
        return ""

    def contents(self, mode=None):
        if self.guid is not None:
            mode = (
                mode
                if mode is not None
                else get_starfab().settings.value("cryxmlbConversionFormat", "xml")
            )
            if mode == "xml":
                return io.BytesIO(
                    self.model.archive.dump_record_xml(
                        self.model.archive.records_by_guid[self.guid]
                    ).encode("utf-8")
                )
            return io.BytesIO(
                self.model.archive.dump_record_json(
                    self.model.archive.records_by_guid[self.guid]
                ).encode("utf-8")
            )
        return io.BytesIO(b"")

    def data(self, column, role):
        if role == qtc.Qt.DisplayRole:
            if column == 0:
                return self.name
            elif column == 1:
                return self.type
            elif column == 2:
                return self.guid
            else:
                return ""
        return super().data(column, role)

    def __repr__(self):
        return f'<DCBTreeItem {self.name} [{self.guid}] "{self._path}">'


class DCBModel(ThreadLoadedPathArchiveTreeModel):
    def __init__(self, sc_manager, loader_cls=DCBLoader):
        self._sc_manager = sc_manager
        super().__init__(
            archive=None,
            columns=DCBVIEW_COLUMNS,
            item_cls=DCBItem,
            parent=sc_manager,
            loader_cls=loader_cls,
            loader_task_name="load_datacore_model",
            loader_task_status_msg="Processing DataCore",
        )
        self._guid_cache = {}

    def itemForGUID(self, guid):
        return self._guid_cache.get(guid)
