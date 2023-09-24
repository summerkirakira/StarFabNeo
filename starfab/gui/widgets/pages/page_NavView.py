from qtpy import uic

from scdatatools.sc.object_container.plotter import ObjectContainerPlotter
from starfab.gui import qtw
from starfab.gui.widgets.preview3d import Preview3D
from starfab.resources import RES_PATH


class NavView(qtw.QWidget):
    def __init__(self, starfab):
        super().__init__(parent=None)
        self.starfab = starfab
        uic.loadUi(str(RES_PATH / "ui" / "NavView.ui"), self)  # Load the ui into self

        self.starfab.sc_manager.datacore_model.loaded.connect(
            self._handle_datacore_loaded
        )
        self.starfab.sc_manager.datacore_model.unloading.connect(
            self._handle_datacore_unloading
        )

        self.starmap = None

    def _handle_datacore_unloading(self):
        if self.starmap is not None:
            self.preview_widget_layout.takeAt(0)
            del self.starmap
            self.starmap = None

    def _handle_datacore_loaded(self):
        megamap_pu = self.starfab.sc.datacore.search_filename(f'libs/foundry/records/megamap/megamap.pu.xml')[0]
        pu_socpak = megamap_pu.properties['SolarSystems'][0].properties['ObjectContainers'][0].value
        try:
            pu_oc = self.starfab.sc.oc_manager.load_socpak(pu_socpak)
        except:
            return

        # filter out the skybox and grab the root orbiting container
        root_oc = next(iter(
            v for v in pu_oc.children.values()
            if v.container_class == 'OrbitingObjectContainer'
        ))
        self.starmap = Preview3D(
            plotter_class=ObjectContainerPlotter,
            plotter_kwargs={
                'object_container': root_oc,
                'label_font_size': 24,
                'point_max_size': 24,
            }
        )
        self.preview_widget_layout.addWidget(self.starmap)
