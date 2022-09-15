from scdatatools.forge.utils import geometry_for_record

from starfab.gui import qtc
from .entity_selector import EntitySelector


class CharacterSelector(EntitySelector):
    @qtc.Slot()
    def _handle_datacore_loaded(self):
        super()._handle_datacore_loaded()
        self.sc_tree.setRootIndex(
            self.proxy_model.mapFromSource(
                self.sc_tree_model.indexForPath("entities/scitem/characters/human")
            )
        )

    def _handle_item_action(self, item, model, index):
        if (
                self.content_page is not None
                and (g := geometry_for_record(item.record, self.starfab.sc.p4k)) is not None
        ):
            f = {k: v for k, v in g.items() if k.casefold() in ['female', 'male']}
            self.content_page.preview_chunkfile(f or g)
