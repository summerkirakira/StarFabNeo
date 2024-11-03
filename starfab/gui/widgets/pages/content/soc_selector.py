import operator

from scdatatools.sc.blueprints.generators.object_containers import blueprint_from_socpak
from starfab.gui import qtc
from starfab.models.p4k import P4KSortFilterProxyModelArchive
from .common import P4KContentSelector, AlternateRootModel
from .export_log import ExtractionItem


class SOCExporterSortFilter(P4KSortFilterProxyModelArchive):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._filters = [(operator.and_, lambda i: i.path.suffix.lower() == ".socpak")]


class SOCSelector(P4KContentSelector):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sc_tree_model = AlternateRootModel(self.starfab.sc_manager.p4k_model)
        self.proxy_model = SOCExporterSortFilter(parent=self)
        self.proxy_model.setFilterCaseSensitivity(qtc.Qt.CaseSensitivity.CaseInsensitive)
        self.sc_tree.setModel(self.proxy_model)

    def checked_items(self):
        return [
            ExtractionItem(
                name=_.name, object=_.info, bp_generator=blueprint_from_socpak
            )
            for _ in self.sc_tree_model.checked_items
            if _.info is not None
        ]

    @qtc.Slot()
    def _handle_p4k_loaded(self):
        self.sc_tree_model.root_item = self.sc_tree_model.itemForPath(
            "Data/ObjectContainers"
        )
        super()._handle_p4k_loaded()

    def _handle_item_action(self, item, model, index):
        pass  # TODO: soc preview?!
