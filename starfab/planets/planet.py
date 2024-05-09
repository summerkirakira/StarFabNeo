import math
import struct
from math import atan2, sqrt
from pathlib import Path
from typing import Tuple

from PySide6.QtCore import QPointF
from scdatatools.engine.chunkfile import ChunkFile, Chunk, JSONChunk, CryXMLBChunk
from scdatatools.engine.cryxml import dict_from_cryxml_file
from scdatatools.p4k import P4KInfo
from scdatatools.sc.object_container import ObjectContainer, ObjectContainerInstance

from starfab.log import getLogger
from starfab.planets.data import LUTData, Brush
from starfab.planets.ecosystem import EcoSystem

from . import *


logger = getLogger(__name__)


class WaypointData:
    def __init__(self, point: QPointF, container: ObjectContainerInstance):
        self.point: QPointF = point
        self.container: ObjectContainerInstance = container


class Planet:
    def __init__(self, oc: ObjectContainerInstance, data: JSONChunk):
        self.oc: ObjectContainerInstance = oc
        self.data: JSONChunk = data

        self.planet_data = None
        self.tile_count = None
        self.radius_m = None
        self.humidity_influence = None
        self.temperature_influence = None

        self.climate_data: bytearray = None
        self.offset_data: bytearray = None
        self.heightmap_data: bytearray = None

        self.brushes: list[Brush] = None
        self.ecosystems: list[EcoSystem] = None

        self.lut: list[list[LUTData]] = None

        self.waypoints: list[WaypointData] = []

        self.gpu_resources = {}
        self.gpu_computer: Compute = None

    @staticmethod
    def position_to_coordinates(x: float, y: float, z: float) -> Tuple[QPointF, float]:
        xy_len = sqrt(x * x + y * y)
        lat = atan2(-z, xy_len) * (180 / math.pi)
        lon = atan2(-x, y) * (180 / math.pi)
        alt = sqrt(x * x + y * y + z * z)
        # +90 if offsetting for NASA coords, gives us 0-360deg output range
        return QPointF((lon + 90 + 360) % 360, lat), alt

    def load_waypoints(self):
        # If we already loaded waypoints, don't do anything
        if len(self.waypoints) != 0:
            return

        # Need to preload *all* entities in the entdata folder to be able to map them
        # We used to be able to look up based on the guid, but that's no longer valid
        ent_paths = [p.filename for p in self.oc.socpak.filelist if "/entdata/" in p.filename]
        ent_infos = [self.oc.socpak.p4k.getinfo(p) for p in ent_paths]
        ent_data = [dict_from_cryxml_file(a.open())["Entity"] for a in ent_infos]
        ent_map = {ent["@EntityCryGUID"]: ent for ent in ent_data}

        for child_name in self.oc.children:
            child_soc: ObjectContainerInstance = self.oc.children[child_name]
            coords = self.position_to_coordinates(child_soc.position.x, child_soc.position.y, child_soc.position.z)
            self.waypoints.append(WaypointData(coords[0], child_soc))
            if child_soc.guid in ent_map:
                child_soc.entdata = ent_map[child_soc.guid]

    def load_data(self) -> object:
        if self.planet_data:
            return self.planet_data

        self.planet_data = self.data.dict()

        self.tile_count = self.planet_data["data"]["globalSplatWidth"]
        self.radius_m = self.planet_data["data"]["General"]["tSphere"]["fPlanetTerrainRadius"]
        self.humidity_influence = self.planet_data["data"]["General"]["textureLayers"]["localHumidityInfluence"]
        self.temperature_influence = self.planet_data["data"]["General"]["textureLayers"]["localTemperatureInfluence"]

        ocean_material = self.planet_data["data"]["oceanParams"]["Geometry"]["MaterialOceanPlanet"]
        ocean_path_posix = ("data" / Path(ocean_material)).as_posix().lower()
        try:
            if ocean_path_posix in self.oc.container.socpak.p4k.NameToInfoLower:
                ocean_mat_info = self.oc.container.socpak.p4k.NameToInfoLower[ocean_path_posix]
                ocean_mat_chunks = ChunkFile(ocean_mat_info)
                for chunk in ocean_mat_chunks.chunks:
                    if isinstance(chunk, CryXMLBChunk):
                        diffuse_path = chunk.dict()["Material"]
                        print(diffuse_path)
        except Exception as ex:
            print(ex)

        self.brushes = [Brush(b) for b in self.planet_data["data"]["General"]["brushes"]]

        ecosystem_ids = self.planet_data["data"]["General"]["uniqueEcoSystemsGUIDs"]
        self.ecosystems = [EcoSystem.find_in_cache_(e)
                           for e in ecosystem_ids
                           if e != "00000000-0000-0000-0000-000000000000"]

        eco: EcoSystem
        for eco in self.ecosystems:
            eco.read_full_data()

        # R = Temp, G = Humidity, B = Biome ID, A = Unused
        splat_raw = self.planet_data["data"]["splatMap"]
        self.climate_data = bytearray(splat_raw)

        offsets_raw = self.planet_data["data"]["randomOffset"]
        self.offset_data = bytearray(offsets_raw)

        hm_path = self.planet_data["data"]["General"]["tSphere"]["sHMWorld"]
        hm_path_posix = ("data" / Path(hm_path)).as_posix().lower()
        hm_data: ObjectContainer = self.oc.container
        hm_info: P4KInfo = hm_data.socpak.p4k.NameToInfoLower[hm_path_posix]
        hm_raw: bytearray = bytearray(hm_data.socpak.p4k.open(hm_info).read())
        # Flip the endian-ness of the heightmap in-place, for easier interpolation
        for offset in range(0, len(hm_raw), 2):
            struct.pack_into("<h", hm_raw, offset, struct.unpack_from(">h", hm_raw, offset)[0])

        self.heightmap_data = hm_raw

        self._build_lut()

    def _build_lut(self):
        # Addressed as [x][y]
        self.lut = [[LUTData()
                     for y in range(self.tile_count)]
                    for x in range(self.tile_count)]

        def _clamp(val, _min, _max):
            return _min if val < _min else (_max if val > _max else val)

        def _lerp_int(_min, _max, val):
            return int(((_max - _min) * val) + _min)

        def _lerp_color(a, b, val):
            return [
                _clamp(_lerp_int(a[0], b[0], val), 0, 255),
                _clamp(_lerp_int(a[1], b[1], val), 0, 255),
                _clamp(_lerp_int(a[2], b[2], val), 0, 255),
                _clamp(_lerp_int(a[3], b[3], val), 0, 255)
            ]

        brush_id_errors = []

        for y in range(128):
            for x in range(128):
                lut = self.lut[x][y]
                lut.ground_texture_id = self.planet_data["data"]["groundTexIDLUT"][y][x]
                lut.object_preset_id = self.planet_data["data"]["objectPresetLUT"][y][x]
                lut.brush_id = self.planet_data["data"]["brushIDLUT"][y][x]
                try:
                    lut.brush_obj = self.brushes[lut.brush_id]
                except IndexError as e:
                    lut.brush_obj = None
                    brush_id_errors.append((x, y, lut.brush_id))

                brush_data = self.planet_data["data"]["brushDataLUT"][y][x]

                lut.bd_gradient_val_bedrock = brush_data["gradientPosBedRock"]
                lut.bd_gradient_val_surface = brush_data["gradientPosSurface"]
                lut.bd_value_offset_bedrock = brush_data["valOffsetBedRock"]
                lut.bd_value_offset_surface = brush_data["valOffsetSurface"]
                lut.bd_saturation_offset_bedrock = brush_data["satOffsetBedRock"]
                lut.bd_saturation_offset_surface = brush_data["satOffsetSurface"]
                lut.bd_orp_blend_index = brush_data["oprBlendIndex"]
                lut.bd_texture_layer_index = brush_data["texturLayerIndex"]

                if lut.brush_obj:
                    lut.bedrockColor = _lerp_color(lut.brush_obj.bedrockGradientColorA,
                                                    lut.brush_obj.bedrockGradientColorB,
                                                    lut.bd_gradient_val_bedrock / 127)

                    lut.surfaceColor = _lerp_color(lut.brush_obj.surfaceGradientColorA,
                                                    lut.brush_obj.surfaceGradientColorB,
                                                    lut.bd_gradient_val_surface / 127)
                else:
                    lut.bedrockColor = [255, 0, 255, 255]   # purple placeholder to stand out
                    lut.surfaceColor = [255, 0, 255, 255]

        if brush_id_errors:
            logger.warning("One or more tiles with invalid brushIDLUT, used placeholder color.")
            logger.debug("brush_id_errors: %r", brush_id_errors)

    @staticmethod
    def try_create(oc: ObjectContainerInstance):
        json_chunk = Planet.find_planet_data(oc)
        if json_chunk:
            return Planet(oc, json_chunk)
        else:
            return None

    @staticmethod
    def find_planet_data(oc: ObjectContainerInstance) -> [None, JSONChunk]:
        if (not oc.container) or (not oc.container.has_additional):
            return None
        if oc.container.additional_data:
            chunkfile: ChunkFile
            for chunkfile in oc.container.additional_data:
                chunk: Chunk
                for c_id, chunk in chunkfile.chunks.items():
                    if isinstance(chunk, JSONChunk):
                        return chunk
        return None
