import struct
from typing import Tuple

from . import *


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


class RenderJobSettings:
    PACK_STRING: str = "5f3i5f4i"
    PACK_LENGTH: int = struct.calcsize(PACK_STRING)

    def __init__(self):
        self.offset_x: float = 0
        self.offset_y: float = 0

        self.size_x: float = 1
        self.size_y: float = 1

        self.planet_radius: float = 0
        self.interpolation: int = 0
        self.render_scale_x: int = 0
        self.render_scale_y: int = 0

        self.local_humidity_influence: float = 0
        self.local_temperature_influence: float = 0
        self.global_terrain_height_influence: float = 4000
        self.ecosystem_terrain_height_influence: float = 1000

        self.ocean_depth: float = -2000
        self.ocean_color: list[int] = [0, 0, 0, 255]

    def pack(self) -> bytes:
        return struct.pack(RenderJobSettings.PACK_STRING,
                           self.offset_x, self.offset_y, self.size_x, self.size_y,
                           self.planet_radius, self.interpolation,
                           self.render_scale_x, self.render_scale_y,
                           self.local_humidity_influence, self.local_temperature_influence,
                           self.global_terrain_height_influence, self.ecosystem_terrain_height_influence,
                           self.ocean_depth, *self.ocean_color)

    def update_buffer(self, buffer_gpu: Buffer):
        data = self.pack()
        buffer = Buffer(RenderJobSettings.PACK_LENGTH, HEAP_UPLOAD)
        buffer.upload(data)
        buffer.copy_to(buffer_gpu)


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


class RenderSettings:
    def __init__(self, gpu: bool, resolution: int, coordinate_mode: str, hlsl: str,
                 interpolation: int, output_resolution: Tuple[int, int]):
        self.gpu = gpu
        self.resolution = resolution
        self.coordinate_mode = coordinate_mode
        self.hlsl = hlsl
        self.interpolation = interpolation
        self.output_resolution = output_resolution
