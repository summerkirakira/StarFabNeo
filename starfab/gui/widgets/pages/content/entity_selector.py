from scdatatools.forge.utils import geometry_for_record
from scdatatools.sc.blueprints.generators.datacore_entity import blueprint_from_datacore_entity

from starfab.gui import qtc, qtw
from starfab.models.common import CheckableModelWrapper
from starfab.gui.widgets.dock_widgets.datacore_widget import DCBSortFilterProxyModel, DCBItem

from .export_log import ExtractionItem
from .common import DCBContentSelector, AlternateRootModel


class EntityExporterSortFilter(DCBSortFilterProxyModel):
    def filterAcceptsRow(self, source_row, source_parent: qtc.QModelIndex) -> bool:
        if parent := source_parent.internalPointer():
            try:
                item: DCBItem = parent.children[source_row]
            except IndexError:
                return False

            if item.record is not None and item.record.type == 'EntityClassDefinition':
                return bool(geometry_for_record(item.record))
        return super().filterAcceptsRow(source_row, source_parent)


class EntitySelector(DCBContentSelector):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sc_tree_model = AlternateRootModel(self.starfab.sc_manager.datacore_model)
        self.proxy_model = EntityExporterSortFilter(parent=self)
        self.sc_tree.setModel(self.proxy_model)

    def checked_items(self):
        return [
            ExtractionItem(name=_.name, object=_.record, bp_generator=blueprint_from_datacore_entity)
            for _ in self.sc_tree_model.checked_items if _.record is not None
        ]

    @qtc.Slot()
    def _handle_datacore_loaded(self):
        self.sc_tree_model.root_item = self.sc_tree_model.itemForPath('entities')
        super()._handle_datacore_loaded()
