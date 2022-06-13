from scdatatools.forge.utils import geometry_for_record
from scdatatools.sc.blueprints.generators.datacore_entity import (
    blueprint_from_datacore_entity,
)
from starfab.gui import qtc
from starfab.gui.widgets.dock_widgets.datacore_widget import (
    DCBSortFilterProxyModel,
    DCBItem,
)
from .common import DCBContentSelector, AlternateRootModel
from .export_log import ExtractionItem


class EntityExporterSortFilter(DCBSortFilterProxyModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._geom_cache = {}

    def filterAcceptsRow(self, source_row, source_parent: qtc.QModelIndex) -> bool:
        parent = source_parent.internalPointer() if source_parent.isValid() else self.sourceModel().root_item
        if parent:
            try:
                item: DCBItem = parent.children[source_row]
            except IndexError:
                return False

            if item.record is not None:
                if item.path not in self._geom_cache and item.record.type == "EntityClassDefinition":
                    self._geom_cache[item.path] = bool(geometry_for_record(item.record))
                if item.path in self._geom_cache:
                    return self._geom_cache[item.path] and super().filterAcceptsRow(source_row, source_parent)
            return False
        return super().filterAcceptsRow(source_row, source_parent)


class EntitySelector(DCBContentSelector):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sc_tree_model = AlternateRootModel(self.starfab.sc_manager.datacore_model)
        self.proxy_model = EntityExporterSortFilter(parent=self)
        self.proxy_model.setFilterCaseSensitivity(qtc.Qt.CaseInsensitive)
        self.sc_tree.setModel(self.proxy_model)

    def checked_items(self):
        return [
            ExtractionItem(
                name=_.name,
                object=_.record,
                bp_generator=blueprint_from_datacore_entity,
            )
            for _ in self.sc_tree_model.checked_items
            if _.record is not None
        ]

    @qtc.Slot()
    def _handle_datacore_loaded(self):
        self.sc_tree_model.root_item = self.sc_tree_model.itemForPath("entities")
        super()._handle_datacore_loaded()
