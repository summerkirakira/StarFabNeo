import io
from typing import Union, cast

from PIL import Image
from PySide6.QtCore import Qt, QPointF, QRectF, QItemSelectionModel, QItemSelection
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QComboBox, QPushButton, QLabel, QCheckBox, QListView
from qtpy import uic
from scdatatools import StarCitizen
from scdatatools.sc.object_container import ObjectContainer, ObjectContainerInstance

from starfab.gui import qtw, qtc
from starfab.gui.widgets.planets.planet_viewer import QPlanetViewer
from starfab.gui.widgets.planets.waypoint_overlay import WaypointOverlay
from starfab.log import getLogger
from starfab.planets import *
from starfab.planets.planet import Planet
from starfab.planets.data import RenderSettings
from starfab.planets.ecosystem import EcoSystem
from starfab.planets.planet_renderer import PlanetRenderer, RenderResult
from starfab.resources import RES_PATH
from starfab.settings import settings
from pathlib import Path


logger = getLogger(__name__)


class PlanetView(qtw.QWidget):
    def __init__(self, sc):
        super().__init__(parent=None)

        self.renderButton: QPushButton = None
        self.exportButton: QPushButton = None
        self.planetComboBox: QComboBox = None
        self.renderResolutionComboBox: QComboBox = None
        self.coordinateSystemComboBox: QComboBox = None
        self.sampleModeComboBox: QComboBox = None
        self.outputResolutionComboBox: QComboBox = None
        self.displayModeComboBox: QComboBox = None
        self.displayLayerComboBox: QComboBox = None
        self.renderOutput: QPlanetViewer = None
        self.enableGridCheckBox: QCheckBox = None
        self.enableCrosshairCheckBox: QCheckBox = None
        self.enableWaypointsCheckBox: QCheckBox = None
        self.enableHillshadeCheckBox: QCheckBox = None
        self.enableBinaryOceanMaskCheckBox: QCheckBox = None
        self.listWaypoints: QListView = None
        self.lbl_planetDetails: QLabel = None
        self.lbl_currentStatus: QLabel = None
        uic.loadUi(str(RES_PATH / "ui" / "PlanetView.ui"), self)  # Load the ui into self

        self.starmap = None

        self.renderer = PlanetRenderer((2048, 1024))
        self.last_render: Union[None, RenderResult] = None

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
        self.renderResolutionComboBox.currentIndexChanged.connect(self._render_scale_changed)

        self.coordinateSystemComboBox.setModel(self.create_model([
            ("NASA Format (0/360deg) - Community Standard", "NASA"),
            ("Earth Format (-180/180deg) Shifted", "EarthShifted"),
            ("Earth Format (-180/180deg) Unshifted", "EarthUnShifted")
        ]))
        self.coordinateSystemComboBox.currentIndexChanged.connect(self._display_coordinate_system_changed)

        self.sampleModeComboBox.setModel(self.create_model([
            ("Nearest Neighbor", 0),
            ("Bi-Linear", 1),
            ("Bi-Cubic", 2),
        ]))
        self.sampleModeComboBox.setCurrentIndex(1)

        self.outputResolutionComboBox.setModel(self.create_model([
            ("2MP  -  2,048  x 1,024", (2048, 1024)),
            ("8MP  -  4,096  x 2,048", (4096, 2048)),
            ("32MP -  8,192  x 4,096", (8192, 4096)),
            ("128MP - 16,384 x 8,192", (16384, 8192))
        ]))
        self.outputResolutionComboBox.currentIndexChanged.connect(self._display_resolution_changed)

        self.displayModeComboBox.setModel(self.create_model([
            ("Pixel-Perfect", qtc.Qt.FastTransformation),
            ("Smooth", qtc.Qt.SmoothTransformation)
        ]))
        self.displayModeComboBox.currentIndexChanged.connect(self._display_mode_changed)

        self.displayLayerComboBox.setModel(self.create_model([
            ("Surface", "surface"),
            ("Heightmap", "heightmap")
        ]))
        self.displayLayerComboBox.currentIndexChanged.connect(self._display_layer_changed)

        if isinstance(sc, StarCitizen):
            self.sc = sc
            self._handle_datacore_loaded()
        else:
            self.sc = sc.sc_manager
            self.sc.datacore_model.loaded.connect(self._hack_before_load)
            self.sc.datacore_model.unloading.connect(self._handle_datacore_unloading)

        self.planetComboBox.currentIndexChanged.connect(self._planet_changed)
        self.renderButton.clicked.connect(self._do_render)
        self.exportButton.clicked.connect(self._do_export)
        self.exportButton.setEnabled(False)
        self.renderOutput.crosshair_moved.connect(self._do_crosshair_moved)
        self.renderOutput.render_window_moved.connect(self._do_render_window_changed)
        self.enableGridCheckBox.stateChanged.connect(self.renderOutput.lyr_grid.set_enabled)
        self.enableCrosshairCheckBox.stateChanged.connect(self.renderOutput.lyr_crosshair.set_enabled)
        self.enableWaypointsCheckBox.stateChanged.connect(self.renderOutput.lyr_waypoints.set_enabled)

        self.renderer.set_settings(self.get_settings())
        self._planet_changed()

    def _planet_changed(self):
        # TODO: Pre-load ecosystem data here w/ progressbar
        self._update_waypoints()

    def _render_scale_changed(self):
        new_scale = self.renderResolutionComboBox.currentData(role=Qt.UserRole)
        self.renderer.settings.resolution = new_scale
        self._update_planet_viewer()

    def _display_resolution_changed(self):
        new_resolution = self.outputResolutionComboBox.currentData(role=Qt.UserRole)
        self.renderer.set_resolution(new_resolution)
        self._update_planet_viewer()

    def _display_mode_changed(self):
        new_transform = self.displayModeComboBox.currentData(role=Qt.UserRole)
        self.renderOutput.image.setTransformationMode(new_transform)

    def _display_coordinate_system_changed(self):
        new_coordinate_mode = self.coordinateSystemComboBox.currentData(role=Qt.UserRole)
        self.renderer.settings.coordinate_mode = new_coordinate_mode
        self._update_planet_viewer()

    def _update_planet_viewer(self):
        if not self.renderer.planet:
            return

        planet_bounds = self.renderer.get_outer_bounds()
        render_bounds = self.renderOutput.get_render_coords()
        self.renderOutput.update_bounds(planet_bounds,
                                        self.renderer.get_bounds_for_render(render_bounds.topLeft()))

    def _update_waypoints(self):
        planet: Planet = self.planetComboBox.currentData(role=Qt.UserRole)
        if not planet:
            return

        planet.load_waypoints()

        waypoint_records = [(wp.container.display_name, wp) for wp in planet.waypoints]
        waypoint_model = self.create_model(waypoint_records)
        waypoint_selection = QItemSelectionModel(waypoint_model)
        waypoint_selection.selectionChanged.connect(self._waypoint_changed)
        self.listWaypoints.setModel(waypoint_model)
        self.listWaypoints.setSelectionModel(waypoint_selection)
        self.renderOutput.set_waypoints(planet.waypoints)

    def _waypoint_changed(self, selected: QItemSelection, removed: QItemSelection):
        if selected.size() == 0:
            return
        waypoint = selected.indexes()[0].data(role=Qt.UserRole)
        self.renderOutput.set_selected_waypoint(waypoint)

    def _display_layer_changed(self):
        layer = self.displayLayerComboBox.currentData(role=Qt.UserRole)
        self.renderOutput.update_visible_layer(layer)

    def _update_image(self, image: Image):
        # self.renderOutput.setImage(ImageQt.ImageQt(image), fit=False)
        pass

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

    def shader_path(self, name) -> Path:
        return Path(__file__) / f'../../../../planets/hlsl/{name}'

    def _get_shader(self, name):
        with io.open(self.shader_path(name), "r") as shader:
            return hlsl.compile(shader.read())

    def get_settings(self):
        scale = self.renderResolutionComboBox.currentData(role=Qt.UserRole)
        coordinates = self.coordinateSystemComboBox.currentData(role=Qt.UserRole)
        interpolation = self.sampleModeComboBox.currentData(role=Qt.UserRole)
        resolution = self.outputResolutionComboBox.currentData(role=Qt.UserRole)
        main_shader = self._get_shader("shader.hlsl")
        hillshade_shader = self._get_shader("hillshade.hlsl")
        hillshade_enabled = self.enableHillshadeCheckBox.isChecked()
        ocean_mask_binary = self.enableBinaryOceanMaskCheckBox.isChecked()
        return RenderSettings(True, scale, coordinates,
                              main_shader, hillshade_shader,
                              interpolation, resolution,
                              hillshade_enabled, ocean_mask_binary)

    def _do_render(self):
        selected_obj: Planet = self.planetComboBox.currentData(role=Qt.UserRole)
        selected_obj.load_data()

        # TODO: Deal with buffer directly
        try:
            self.renderer.set_planet(selected_obj)
            self.renderer.set_settings(self.get_settings())

            layer = self.displayLayerComboBox.currentData(role=Qt.UserRole)
            render_bounds = self.renderOutput.get_render_coords()
            self.last_render = self.renderer.render(render_bounds.topLeft())
            self._display_layer_changed()
            self.renderOutput.update_render(self.last_render, layer)
            self.exportButton.setEnabled(True)
        except Exception as ex:
            logger.exception(ex)

    def _do_export(self):
        prev_dir = settings.value("exportDirectory")
        title = "Save Render to..."
        edir = qtw.QFileDialog.getSaveFileName(self, title,
                                               dir=f"{self.renderer.planet.oc.entity_name}.png",
                                               filter="PNG Image (*.png)")
        filename, filter = edir
        if filename:
            layer = self.displayLayerComboBox.currentData(role=Qt.UserRole)
            if layer == 'surface':
                self.last_render.tex_color.save(filename, format="png")
            elif layer == 'heightmap':
                self.last_render.tex_heightmap.save(filename, format="png")
            else:
                raise ValueError()

    def _do_crosshair_moved(self, new_position: QPointF):
        self._update_status()

    def _do_render_window_changed(self, new_window: QRectF):
        self._update_status()

    def _update_status(self):
        cross: QPointF = self.renderOutput.get_crosshair_coords()
        render_window: QRectF = self.renderOutput.get_render_coords()
        self.lbl_currentStatus.setText(f"Crosshair:\n"
                                       f"\tLat:\t\t{self.coord_to_dms(cross.x())}\n"
                                       f"\tLon:\t\t{self.coord_to_dms(cross.y())}\n"
                                       f"\n"
                                       f"Render Window:\n"
                                       f"\tLeft Lat:  \t{self.coord_to_dms(render_window.left())}\n"
                                       f"\tRight Lat: \t{self.coord_to_dms(render_window.right())}\n"
                                       f"\tTop Lat:   \t{self.coord_to_dms(render_window.top())}\n"
                                       f"\tBottom Lat:\t{self.coord_to_dms(render_window.bottom())}")

    @staticmethod
    def coord_to_dms(coord):
        degrees = int(coord)
        minutes_float = (coord - degrees) * 60
        minutes = int(minutes_float)
        seconds = (minutes_float - minutes) * 60
        return f"{degrees}° {minutes}' {seconds:.2f}"

    def _handle_datacore_unloading(self):
        if self.starmap is not None:
            del self.starmap
            self.starmap = None

    def _handle_datacore_loaded(self):
        logger.info("DataCore loaded")

        for filename in [
            'libs/foundry/records/megamap/pu_all.xml',  # Pyro Tech-Preview builds used pu_all.xml containing both Stanton and Pyro
                                                        # (however the Stanton-only megamap.pu.xml plus a Pyro-only pyro.xml were also included)
            'libs/foundry/records/megamap/megamap.pu.xml',      # default megamap record for Stanton-only builds
        ]:
            res = self.sc.datacore.search_filename(filename)
            if res:
                megamap_pu = res[0]
                break
        else:
            logger.error("No megamap record found")
            return

        # megamap_pu = self.sc.datacore.search_filename(f'libs/foundry/records/megamap/megamap.pu.xml')[0]
        # pu_socpak = megamap_pu.properties['SolarSystems'][0].properties['ObjectContainers'][0].value

        bodies: list[Planet] = []
        for solar_system in megamap_pu.properties['SolarSystems']:
            pu_socpak = solar_system.properties['ObjectContainers'][0].value
            try:
                pu_oc = self.sc.oc_manager.load_socpak(pu_socpak)
                bodies.extend(self._search_for_bodies(pu_oc))
            except Exception as ex:
                logger.exception(ex)
                return

            self.planetComboBox.setModel(self.create_model([
                (b.oc.display_name, b) for b in bodies
            ]))

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


