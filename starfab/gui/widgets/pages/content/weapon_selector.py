from starfab.gui import qtc

from .entity_selector import EntitySelector


class WeaponSelector(EntitySelector):
    @qtc.Slot()
    def _handle_datacore_loaded(self):
        super()._handle_datacore_loaded()
        self.sc_tree.setRootIndex(
            self.proxy_model.mapFromSource(
                self.sc_tree_model.indexForPath("entities/scitem/weapons")
            )
        )
