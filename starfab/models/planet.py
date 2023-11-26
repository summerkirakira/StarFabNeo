import io
import json
import math
import random
import struct
from os import listdir
from os.path import join, isfile
from pathlib import Path
from struct import unpack
from typing import Callable, Union

import compushady
from PIL import Image
from compushady import Texture2D, Buffer, HEAP_UPLOAD, Compute, HEAP_READBACK, Resource, HEAP_DEFAULT
from compushady.backends.vulkan import Device
from compushady.formats import R8G8B8A8_UINT, R16_UINT, R8_UINT
from compushady.shaders import hlsl
from scdatatools import StarCitizen
from scdatatools.engine.chunkfile import ChunkFile, Chunk, JSONChunk
from scdatatools.engine.textures import unsplit_dds
from scdatatools.p4k import P4KInfo
from scdatatools.sc.object_container import ObjectContainer, ObjectContainerInstance

from starfab.utils import image_converter


class RenderSettings:
    def __init__(self, gpu: bool, resolution: int, coordinate_mode: str, hlsl: str):
        self.gpu = gpu
        self.resolution = resolution
        self.coordinate_mode = coordinate_mode
        self.hlsl = hlsl


class LocalClimateData:
    def __init__(self, x: float, y: float):
        self.x: float = x
        self.y: float = y

        self.temperature: int = 0
        self.humidity: int = 0
        self.eco_id: int = 0

        self.elevation: float = 0
        self.random_offset: float = 0

        self.normal_x: float = 0
        self.normal_y: float = 0
        self.normal_z: float = 0

        self.surfaceTextureMap: int = 0
        self.oprBlendIndex: int = 0

    @staticmethod
    def create_packed_bytes(climate_records: list[list]):
        pack_string = "2f2I"
        pack_size = struct.calcsize(pack_string)
        pack_index = 0
        pack_data = bytearray(pack_size * len(climate_records) * len(climate_records[0]))
        # TODO: There has to be a better way to do this :^)
        print("Packing")
        for y in range(len(climate_records[0])):
            print(f"{y}/{len(climate_records[0])}")
            for x in range(len(climate_records)):
                clim: LocalClimateData = climate_records[x][y]
                struct.pack_into(pack_string, pack_data, pack_index,
                                 clim.elevation, clim.random_offset,
                                 clim.surfaceTextureMap, clim.oprBlendIndex)
                pack_index += pack_size
        print("Done Packing")
        return pack_data


class Brush:
    def __init__(self, record):
        self.record = record
        self.bedrockGradientColorA = self.record["bedrockBrush"]["colorGradient"]["gradientColorA"]
        self.bedrockGradientColorB = self.record["bedrockBrush"]["colorGradient"]["gradientColorB"]
        self.surfaceGradientColorA = self.record["surfaceBrush"]["colorGradient"]["gradientColorA"]
        self.surfaceGradientColorB = self.record["surfaceBrush"]["colorGradient"]["gradientColorB"]
        self.tMin = self.record["tMin"]
        self.tMax = self.record["tMax"]
        self.hMin = self.record["hMin"]
        self.hMax = self.record["hMax"]


class LUTData:
    def __init__(self):
        self.bedrockGloss: list = []
        self.surfaceGloss: list = []
        self.bedrockColor: list = []
        self.surfaceColor: list = []
        self.brush_id: int = 0
        self.ground_texture_id: int = 0
        self.object_preset_id: int = 0
        self.bd_gradient_val_bedrock: int = 0
        self.bd_gradient_val_surface: int = 0
        self.bd_value_offset_bedrock: float = 0
        self.bd_value_offset_surface: float = 0
        self.bd_saturation_offset_bedrock: float = 0
        self.bd_saturation_offset_surface: float = 0
        self.bd_orp_blend_index: int = 0
        self.bd_texture_layer_index: int = 0
        self.brush_obj: Brush = None


class EcoSystem:
    _cache = {}
    _tex_root = Path("Data/Textures/planets/terrain")
    _sc: Union[None, StarCitizen] = None

    @staticmethod
    def find_in_cache_(guid: str):
        return EcoSystem._cache[guid] if guid in EcoSystem._cache else None

    @staticmethod
    def read_eco_headers(sc: StarCitizen):
        if len(EcoSystem._cache) != 0:
            return EcoSystem._cache
        EcoSystem._sc = sc
        p4k_results = EcoSystem._sc.p4k.search(".eco", mode="endswith")
        for result in p4k_results:
            eco = EcoSystem(json.loads(result.open().read()))
            EcoSystem._cache[eco.id] = eco
        return EcoSystem._cache

    def __init__(self, eco_data: dict):
        self.id = eco_data["GUID"]
        self.name = eco_data["name"]
        self.offset = eco_data["fOffsetH"]
        self.tex_path: str = eco_data["Textures"]["ecoSystemAlbedoTexture"].replace(".tif", ".dds")
        self.norm_path: str = eco_data["Textures"]["ecoSystemNormalTexture"].replace(".tif", ".dds")
        self.elevation_path: str = eco_data["Textures"]["elevationTexture"]

        self.climate_data: list[list[LocalClimateData]] = None
        self.climate_texture: Image = None
        self.normal_texture: Image = None
        self.elevation_bytes: bytearray = None
        self.elevation_size: int = 0

    def read_full_data(self):
        if self.climate_data:
            return

        def _read_texture(subpath: str) -> bytes:
            texture_path = (EcoSystem._tex_root / subpath).as_posix().lower()

            p4k_dds_files = EcoSystem._sc.p4k.search(texture_path, mode="startswith")
            dds_files = {record.orig_filename: record
                         for record
                         in p4k_dds_files
                         if not record.orig_filename.endswith("a")}
            res: bytes = unsplit_dds(dds_files)
            return image_converter.convert_buffer(res, "dds", "png")

        climate_texture = Image.open(io.BytesIO(_read_texture(self.tex_path)))
        normal_texture = Image.open(io.BytesIO(_read_texture(self.norm_path)))

        self.climate_texture = climate_texture
        self.normal_texture = normal_texture

        # Addressed as [x][y]
        self.climate_data = [[LocalClimateData(x, y)
                              for y in range(climate_texture.height)]
                             for x in range(climate_texture.width)]

        elevation_path = (EcoSystem._tex_root / self.elevation_path).as_posix().lower()
        elevation_info: P4KInfo = EcoSystem._sc.p4k.NameToInfoLower[elevation_path]
        with elevation_info.open() as o:
            self.elevation_bytes = bytearray(o.read())
            self.elevation_size = int(math.sqrt(len(self.elevation_bytes) / 2))

        print(f"Textures loaded for {self.name}")


class Planet:
    def __init__(self, oc: ObjectContainerInstance, data: JSONChunk):
        self.oc: ObjectContainerInstance = oc
        self.data: JSONChunk = data

        self.planet_data = None
        self.tile_count = None
        self.radius_m = None
        self.humidity_influence = None
        self.temperature_influence = None

        self.climate_texture: Image = None
        self.offset_data: bytearray = None
        self.heightmap_data: bytearray = None

        self.brushes: list[Brush] = None
        self.ecosystems: list[EcoSystem] = None

        self.lut: list[list[LUTData]] = None

        self.gpu_resources = {}
        self.gpu_computer: Compute = None

    def load_data(self) -> object:
        if self.planet_data:
            return self.planet_data

        self.planet_data = self.data.dict()

        self.tile_count = self.planet_data["data"]["globalSplatWidth"]
        self.radius_m = self.planet_data["data"]["General"]["tSphere"]["fPlanetTerrainRadius"]
        self.humidity_influence = self.planet_data["data"]["General"]["textureLayers"]["localHumidityInfluence"]
        self.temperature_influence = self.planet_data["data"]["General"]["textureLayers"]["localTemperatureInfluence"]

        self.brushes = [Brush(b) for b in self.planet_data["data"]["General"]["brushes"]]

        ecosystem_ids = self.planet_data["data"]["General"]["uniqueEcoSystemsGUIDs"]
        self.ecosystems = [EcoSystem.find_in_cache_(e)
                           for e in ecosystem_ids[0:1]
                           if e != "00000000-0000-0000-0000-000000000000"]

        eco: EcoSystem
        for eco in self.ecosystems:
            eco.read_full_data()

        # R = Temp, G = Humidity, B = Biome ID, A = Unused
        splat_raw = self.planet_data["data"]["splatMap"]
        self.climate_texture = Image.frombuffer('RGBA',
                                                (self.tile_count, self.tile_count),
                                                bytearray(splat_raw))

        offsets_raw = self.planet_data["data"]["randomOffset"]
        self.offset_data = bytearray(offsets_raw)

        hm_path = self.planet_data["data"]["General"]["tSphere"]["sHMWorld"]
        hm_path_posix = ("data" / Path(hm_path)).as_posix().lower()
        hm_data: ObjectContainer = self.oc.container
        hm_info: P4KInfo = hm_data.socpak.p4k.NameToInfoLower[hm_path_posix]
        hm_raw = bytearray(hm_data.socpak.p4k.open(hm_info).read())

        self.heightmap_data = hm_raw

        self._build_lut()

        print("Creating GPU Resources...")
        self._construct_gpu_resources()
        print("Created!")

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

        for y in range(128):
            for x in range(128):
                lut = self.lut[x][y]
                lut.ground_texture_id = self.planet_data["data"]["groundTexIDLUT"][y][x]
                lut.object_preset_id = self.planet_data["data"]["objectPresetLUT"][y][x]
                lut.brush_id = self.planet_data["data"]["brushIDLUT"][y][x]
                lut.brush_obj = self.brushes[lut.brush_id]

                brush_data = self.planet_data["data"]["brushDataLUT"][y][x]

                lut.bd_gradient_val_bedrock = brush_data["gradientPosBedRock"]
                lut.bd_gradient_val_surface = brush_data["gradientPosSurface"]
                lut.bd_value_offset_bedrock = brush_data["valOffsetBedRock"]
                lut.bd_value_offset_surface = brush_data["valOffsetSurface"]
                lut.bd_saturation_offset_bedrock = brush_data["satOffsetBedRock"]
                lut.bd_saturation_offset_surface = brush_data["satOffsetSurface"]
                lut.bd_orp_blend_index = brush_data["oprBlendIndex"]
                lut.bd_texture_layer_index = brush_data["texturLayerIndex"]

                lut.bedrockColor = _lerp_color(lut.brush_obj.bedrockGradientColorA,
                                               lut.brush_obj.bedrockGradientColorB,
                                               lut.bd_gradient_val_bedrock / 127)

                lut.surfaceColor = _lerp_color(lut.brush_obj.surfaceGradientColorA,
                                               lut.brush_obj.surfaceGradientColorB,
                                               lut.bd_gradient_val_surface / 127)

    def _construct_gpu_resources(self):
        def _buffer_from_lut_color(fn_color: Callable[[LUTData], list[int]]) -> Resource:
            texture = Texture2D(128, 128, R8G8B8A8_UINT)
            buffer = Buffer(texture.size, HEAP_UPLOAD)
            data = [0 for _ in range(128 * 128 * 4)]
            for y in range(128):
                for x in range(128):
                    color = fn_color(self.lut[x][y])
                    index = 4 * (y * 128 + x)
                    data[index + 0] = color[0]
                    data[index + 1] = color[1]
                    data[index + 2] = color[2]
                    data[index + 3] = color[3]
            # TODO: Can we write directly into the buffer as we generate?
            buffer.upload(bytes(data))
            buffer.copy_to(texture)
            return texture

        def _buffer_for_climate(climate: list[list[LocalClimateData]]) -> Resource:
            buffer_bytes = LocalClimateData.create_packed_bytes(climate)
            print(f"Allocating climate: {len(buffer_bytes)}")
            gpu_buffer = Buffer(len(buffer_bytes), HEAP_DEFAULT, stride=16)
            local_buffer = Buffer(len(buffer_bytes), HEAP_UPLOAD)
            local_buffer.upload(buffer_bytes)
            local_buffer.copy_to(gpu_buffer)
            return gpu_buffer

        def _buffer_for_image(image: Image) -> Resource:
            data = image.tobytes('raw', 'RGBA')
            texture = Texture2D(image.width, image.height, R8G8B8A8_UINT)
            buffer = Buffer(len(data), HEAP_UPLOAD)
            buffer.upload(data)
            buffer.copy_to(texture)
            return texture

        def _buffer_for_bytes(data: bytearray, bytes_per_pixel: int, format: int) -> Resource:
            dim = int(math.sqrt(len(data) / bytes_per_pixel))
            img = Texture2D(dim, dim, format)
            buffer = Buffer(len(data), HEAP_UPLOAD)
            buffer.upload(data)
            buffer.copy_to(img)
            return img

        self.gpu_resources['bedrock'] = _buffer_from_lut_color(lambda x: x.bedrockColor)
        self.gpu_resources['surface'] = _buffer_from_lut_color(lambda x: x.surfaceColor)
        self.gpu_resources['planet_climate'] = _buffer_for_image(self.climate_texture)
        self.gpu_resources['planet_offsets'] = _buffer_for_bytes(self.offset_data, 1, R8_UINT)
        self.gpu_resources['planet_heightmap'] = _buffer_for_bytes(self.heightmap_data, 2, R16_UINT)
        # self.gpu_resources['ecosystems'] = _buffer_for_climate(self.ecosystems[0].climate_data)
        # self.gpu_resources['splat'] = _buffer_for_image(self.climate_texture)

        eco_size = len(self.ecosystems[0].climate_data)
        destination_texture = Texture2D(eco_size * 2, eco_size, R8G8B8A8_UINT)

        self.gpu_resources['destination'] = destination_texture
        self.gpu_resources['readback'] = Buffer(destination_texture.size, HEAP_READBACK)

        print(f"Dest: ({destination_texture.width}, {destination_texture.height})")

    def render(self, settings: RenderSettings):
        r = self.gpu_resources
        samplers = [
            r['bedrock'], r['surface'], r['planet_climate'], r['planet_offsets'], r['planet_heightmap']
        ]

        destination_texture = self.gpu_resources['destination']
        readback_buffer = self.gpu_resources['readback']

        compute = Compute(hlsl.compile(settings.hlsl),
                          srv=samplers,
                          uav=[destination_texture])

        compute.dispatch(destination_texture.width // 8, destination_texture.height // 8, 1)
        destination_texture.copy_to(readback_buffer)

        image = Image.frombuffer('RGBA', (destination_texture.width,
                                          destination_texture.height), readback_buffer.readback())
        image.show()
        return

    def readback(self):
        destination: Texture2D = self.gpu_resources['destination']
        readback: Buffer = self.gpu_resources['readback']
        destination.copy_to(readback)

        print(f"{destination.width}, {destination.height}")

        image = Image.frombuffer('RGBA', (destination.width,
                                          destination.height), readback.readback())
        image.show()

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

