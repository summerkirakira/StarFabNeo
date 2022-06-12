from scdatatools.sc.blueprints.generators.datacore_entity import (
    blueprint_from_datacore_entity,
)
from starfab.gui import qtc, qtw
from starfab.gui.widgets.dock_widgets.datacore_widget import DCBSortFilterProxyModel
from starfab.models.common import CheckableModelWrapper
from starfab.models.datacore import DCBModel, DCBLoader, RECORDS_ROOT_PATH
from .common import DCBContentSelector
from .export_log import ExtractionItem

VEHICLES_CATEGORY = "Vehicles"
SHIPS_CATEGORY = "Ships"
VEHICLES_ROOT = f"{RECORDS_ROOT_PATH}entities/groundvehicles"
SHIPS_ROOT = f"{RECORDS_ROOT_PATH}entities/spaceships"
FILTER_TAGS = [
    "c08564a2-68d2-4eb1-903b-e3c3ecf12ac1",  # 'TagDatabase.AI.Spawning.GameMode.PU'
    "5a9670c9-d060-4bad-b042-e538f90e24e3",  # 'TagDatabase.AI.Spawning.GameMode.AC'
]


class VehiclesLoader(DCBLoader):
    def items_to_load(self):
        # trigger datacore to load here
        self.model.archive = self.model.archive.datacore

        items = []
        for r in self.model.archive.records:
            if r.type != 'EntityClassDefinition':
                continue

            category = ""
            if r.filename.startswith(VEHICLES_ROOT):
                category = VEHICLES_CATEGORY
            elif r.filename.startswith(SHIPS_ROOT):
                category = SHIPS_CATEGORY

            if not category:
                continue

            # try:
            #     e = next(iter(_ for _ in r.properties['StaticEntityClassData']
            #                   if _.name == 'DefaultEntitlementEntityParams'))
            #     if e.properties.get('canEntitleThroughWebsite', False):
            #         items.append((category, r))
            # except StopIteration:
            #     if not any(_.name in FILTER_TAGS for _ in r.properties.get('tags', [])):
            #         items.append((category, r))
            if not any(_.name in FILTER_TAGS for _ in r.properties.get("tags", [])):
                items.append((category, r))

        return items

    def load_item(self, item):
        category, item = item
        if category == VEHICLES_CATEGORY:
            path = item.filename.replace(VEHICLES_ROOT, "")
        else:
            path = item.filename.replace(SHIPS_ROOT, "")

        parent_path, name = path.rsplit("/", maxsplit=1) if "/" in path else ("", path)
        parent_path = f"{category} / {parent_path}" if parent_path else category
        parent = self.model.parentForPath(parent_path)
        # name = name.replace(".xml", "")
        name = item.name
        if name in parent.children_by_name:
            name = f"{name}.{item.id.value}"
        new_item = self._item_cls(
            f"{parent_path}/{name}", model=self.model, record=item, parent=parent
        )
        self.model._guid_cache[new_item.guid] = new_item


class VehicleSelector(DCBContentSelector):
    def _create_filter(self):
        pass

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = DCBModel(self, loader_cls=VehiclesLoader)
        self.model.loaded.connect(self._loaded)
        self.sc_tree_model = CheckableModelWrapper(self.model)
        self.proxy_model = DCBSortFilterProxyModel(parent=self)
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
        self.model.load(self.starfab.sc, task_status_msg="")

    @qtc.Slot()
    def _loaded(self):
        self.proxy_model.setSourceModel(self.sc_tree_model)
        self.sc_tree.setModel(self.proxy_model)
        self.proxy_model.sort(0, qtc.Qt.SortOrder.AscendingOrder)

        header = self.sc_tree.header()
        header.setSectionResizeMode(qtw.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(0, qtw.QHeaderView.Stretch)
        self.sc_tree.hideColumn(1)
