from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QComboBox, QPushButton, QPlainTextEdit
from qtpy import uic
from scdatatools import StarCitizen
from scdatatools.engine.chunkfile import ChunkFile, Chunk, JSONChunk
from scdatatools.sc.object_container import ObjectContainer, ObjectContainerInstance
from scdatatools.sc.object_container.plotter import ObjectContainerPlotter

from starfab.gui import qtw
from starfab.gui.widgets.preview3d import Preview3D
from starfab.log import getLogger
from starfab.models.datacore import DCBModel
from starfab.models.planet import Planet, RenderSettings, EcoSystem
from starfab.resources import RES_PATH
from pathlib import Path


logger = getLogger(__name__)


class PlanetView(qtw.QWidget):
    def __init__(self, sc):
        super().__init__(parent=None)

        self.renderButton: QPushButton = None
        self.planetComboBox: QComboBox = None
        self.renderResolutionComboBox: QComboBox = None
        self.coordinateSystemComboBox: QComboBox = None
        self.hlslTextBox: QPlainTextEdit = None
        uic.loadUi(str(RES_PATH / "ui" / "PlanetView.ui"), self)  # Load the ui into self

        self.starmap = None

        self.renderResolutionComboBox.setModel(self.create_model([
            ("1px per tile", 1),
            ("2px per tile", 2),
            ("4px per tile", 4),
            ("8px per tile", 8),
            ("16px per tile", 16),
            ("32px per tile", 32),
            ("64px per tile", 64),
            ("128px per tile", 128)
        ]))

        self.coordinateSystemComboBox.setModel(self.create_model([
            ("NASA Format (0/360deg) - Community Standard", "NASA"),
            ("Earth Format (-180/180deg) Shifted", "EarthShifted"),
            ("Earth Format (-180/180deg) Unshifted", "EarthUnShifted")
        ]))

        if isinstance(sc, StarCitizen):
            self.sc = sc
            self._handle_datacore_loaded()
        else:
            self.sc = sc.sc_manager
            self.sc.datacore_model.loaded.connect(self._hack_before_load)
            self.sc.datacore_model.unloading.connect(self._handle_datacore_unloading)

        self.renderButton.clicked.connect(self.clicky)

    def _hack_before_load(self):
        # Hacky method to support faster dev testing and launching directly in-app
        self.sc = self.sc.sc
        EcoSystem.read_eco_headers(self.sc)
        self._handle_datacore_loaded()

    @staticmethod
    def create_model(records):
        # Create a model
        model = QStandardItemModel()

        # Add items to the model with visible name and hidden ID
        for item_text, item_id in records:
            item = QStandardItem(item_text)
            # Set the hidden ID in the user role of the item
            item.setData(item_id, role=Qt.UserRole)
            model.appendRow(item)

        return model

    def clicky(self):
        selected_obj: Planet = self.planetComboBox.currentData(role=Qt.UserRole)
        shader = self.hlslTextBox.toPlainText()
        print(selected_obj)
        selected_obj.load_data()
        print("Done loading planet data")
        selected_obj.render(RenderSettings(True, 1, "NASA", shader))

    def _handle_datacore_unloading(self):
        if self.starmap is not None:
            del self.starmap
            self.starmap = None

    def _handle_datacore_loaded(self):
        logger.info("DataCore loaded")
        megamap_pu = self.sc.datacore.search_filename(f'libs/foundry/records/megamap/megamap.pu.xml')[0]
        pu_socpak = megamap_pu.properties['SolarSystems'][0].properties['ObjectContainers'][0].value
        try:
            pu_oc = self.sc.oc_manager.load_socpak(pu_socpak)
            bodies: list[Planet] = self._search_for_bodies(pu_oc)

            self.planetComboBox.setModel(self.create_model([
                (b.oc.entity_name, b) for b in bodies
            ]))

        except Exception as ex:
            logger.exception(ex)
            return

    @staticmethod
    def _search_for_bodies(socpak: ObjectContainer, search_depth_after_first_body: int = 1):
        results: list[Planet] = []

        def _inner_search(entry: ObjectContainerInstance, planet_depth: int, max_depth: int):
            if planet_depth > max_depth:
                return
            for subchild in entry.children.values():
                planet = Planet.try_create(subchild)
                if planet:
                    results.append(planet)
                    _inner_search(subchild, planet_depth + 1, max_depth)
                else:
                    # Only increment the next depth when we've hit a planet already
                    new_depth = planet_depth if planet_depth == 0 else planet_depth + 1
                    _inner_search(subchild, new_depth, max_depth)

        child: ObjectContainerInstance
        for child in socpak.children.values():
            _inner_search(child, 0, search_depth_after_first_body)

        return results


