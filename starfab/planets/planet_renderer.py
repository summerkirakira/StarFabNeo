import gc
import math
from typing import Union, Callable, Tuple, cast, Literal

from PIL import Image
from PySide6.QtCore import QRectF, QPointF, QSizeF, QSize

from . import *
from starfab.log import getLogger
from starfab.planets.planet import Planet
from starfab.planets.data import LUTData, RenderJobSettings, RenderSettings
from starfab.planets.ecosystem import EcoSystem


logger = getLogger(__name__)


class RenderResult:
    def __init__(self,
                 settings: RenderJobSettings,
                 tex_color: Image.Image,
                 tex_heightmap: Image.Image,
                 tex_oceanmask: Image.Image,
                 splat_dimensions: Tuple[float, float],
                 coordinate_bounds_planet: QRectF,
                 coordinate_bounds: QRectF):
        self.settings = settings
        self.tex_color: Image.Image = tex_color
        self.tex_heightmap: Image.Image = tex_heightmap
        self.tex_oceanmask: Image.Image = tex_oceanmask
        self.splat_resolution = splat_dimensions
        self.coordinate_bounds = coordinate_bounds
        self.coordinate_bounds_planet = coordinate_bounds_planet
        start_norm_x = (coordinate_bounds.left() - coordinate_bounds_planet.left()) / coordinate_bounds_planet.width()
        start_norm_y = (coordinate_bounds.top() - coordinate_bounds_planet.top()) / coordinate_bounds_planet.height()
        size_norm = coordinate_bounds.height() / coordinate_bounds_planet.height()
        self.coordinate_normalized = QRectF(QPointF(start_norm_x, start_norm_y), QSizeF(size_norm, size_norm))


class PlanetRenderer:

    def __init__(self, buffer_resolution: Tuple[int, int]):
        self.planet: None | Planet = None
        self.settings: None | RenderSettings = None
        self.gpu_resources: dict[str, Resource] = {}
        self.render_resolution: QSize = QSize(*buffer_resolution)

        self._create_gpu_output_resources()

    def set_planet(self, planet: Planet):
        if planet != self.planet:
            # self._cleanup_planet_gpu_resources()
            self._cleanup_planet_gpu_resources()
            self.planet = planet
            self._create_planet_gpu_resources()
            self._write_planet_input_resources()

    def set_settings(self, settings: RenderSettings):
        self._cleanup_gpu_output_resources()  # Cleanup current GPU resources
        self.settings = settings
        self._create_gpu_output_resources()   # Create new GPU resources with updated settings

    def set_resolution(self, new_dimensions: Tuple[int, int]):
        self._cleanup_gpu_output_resources()
        self.render_resolution = QSize(*new_dimensions)
        self._create_gpu_output_resources()

    def get_outer_bounds(self) -> QRectF:
        base_coordinate: QPointF = QPointF(0, -90)
        if self.settings.coordinate_mode != "NASA":
            base_coordinate.setX(-180)

        return QRectF(base_coordinate, QSize(360, 180))

    def get_bounds_for_render(self, render_coords: QPointF) -> QRectF:
        width_norm = self.render_resolution.width() / self.settings.resolution / self.planet.tile_count / 2
        height_norm = self.render_resolution.height() / self.settings.resolution / self.planet.tile_count
        render_size_degrees: QSizeF = QSizeF(width_norm * 360, height_norm * 180)

        return QRectF(render_coords, render_size_degrees)

    def get_normalized_from_coordinates(self, coordinates: QPointF) -> QPointF:
        bounds = self.get_outer_bounds()
        return QPointF((coordinates.x() - bounds.x()) / bounds.width(),
                       (coordinates.y() - bounds.y()) / bounds.height())

    def render(self, render_coords: QPointF) -> RenderResult:
        job_s = RenderJobSettings()

        if not self.planet:
            raise Exception("Planet not set yet!")

        # offset_x/y are be normalized between 0-1
        norm_coords = self.get_normalized_from_coordinates(render_coords)
        job_s.offset_x = norm_coords.x()
        job_s.offset_y = norm_coords.y()

        # In NASA Mode we are shifting only our sampling offset
        # so that [0,0] render coordinates equals [0deg, 360deg] world coordinates
        if self.settings.coordinate_mode == "NASA":
            job_s.offset_x += 0.5
        # In EarthShifted Mode we are
        elif self.settings.coordinate_mode == "EarthShifted":
            job_s.offset_x += 0.5
        elif self.settings.coordinate_mode == "EarthUnShifted":
            job_s.offset_x = 0

        job_s.offset_x = job_s.offset_x % 1.0
        job_s.interpolation = self.settings.interpolation
        job_s.render_scale_x = self.settings.resolution * 2
        job_s.render_scale_y = self.settings.resolution
        job_s.blending_enabled = self.settings.blending_enabled
        job_s.hillshade_enabled = self.settings.hillshade_enabled
        job_s.hillshade_level = self.settings.hillshade_level
        job_s.ocean_mask_binary = self.settings.ocean_mask_binary
        job_s.heightmap_bit_depth = self.settings.heightmap_bit_depth
        job_s.debug_mode = self.settings.debug_mode

        job_s.planet_radius = self.planet.radius_m
        job_s.local_humidity_influence = self.planet.humidity_influence
        job_s.local_temperature_influence = self.planet.temperature_influence
        job_s.ocean_enabled = self.planet.ocean_enabled

        job_s.update_buffer(cast(Buffer, self.gpu_resources['settings']))

        # Main render pass
        computer = self._get_computer()

        computer.dispatch(self.render_resolution.width() // 8, self.render_resolution.height() // 8, 1)
        # TODO: Keep this around and render multiple tiles with the same Compute obj

        del computer

        if job_s.hillshade_enabled:
            # Hill-shade pass
            hillshade_compute = self._get_hillshade_computer()

            hillshade_compute.dispatch(self.render_resolution.width() // 8, self.render_resolution.height() // 8, 1)

            del hillshade_compute

        out_color: Image = self._read_frame("output_color", "RGBA")

        # Check if self.settings is defined; otherwise, revert to R8_UINT
        if self.settings is None:
            out_heightmap: Image = self._read_frame("output_heightmap", "L")
        else:
            # Determine the appropriate format for the heightmap texture based on the bit depth
            if self.settings.heightmap_bit_depth == 8:
                out_heightmap: Image = self._read_frame("output_heightmap", "L")
            elif self.settings.heightmap_bit_depth == 16:
                out_heightmap: Image = self._read_frame("output_heightmap", "I;16")
            elif self.settings.heightmap_bit_depth == 32:
                out_heightmap: Image = self._read_frame("output_heightmap", "I;32")
            else:
                raise ValueError(f"Unsupported heightmap bit depth: {self.settings.heightmap_bit_depth}")

        out_oceanmask: Image = self._read_frame("output_ocean_mask", "L")

        planet_bouds = self.get_outer_bounds()
        render_bounds = self.get_bounds_for_render(render_coords)

        return RenderResult(job_s, out_color, out_heightmap, out_oceanmask,
                            self.render_resolution, planet_bouds, render_bounds)

    def _read_frame(self, resource_name: str, mode: Literal['L', 'RGBA', 'I;16', 'I;32']) -> Image:
        resource: Resource = self.gpu_resources['readback']
        readback: Buffer = cast(Buffer, resource)
        destination: Texture2D = cast(Texture2D, self.gpu_resources[resource_name])
        destination.copy_to(readback)
        output_bytes = readback.readback()
        del readback

        if mode == 'I;16':  # 16-bit unsigned integer, single channel
            return Image.frombuffer('I;16', (destination.width, destination.height), output_bytes, 'raw', 'I;16', 0, 1)
        elif mode == 'I;32':  # 32-bit signed integer, single channel
            return Image.frombuffer('I', (destination.width, destination.height), output_bytes, 'raw', 'I', 0, 1)
        else:
            return Image.frombuffer(mode,
                                    (destination.width, destination.height),
                                    output_bytes)

    def _get_computer(self) -> Compute:
        res = self.gpu_resources
        samplers = [
            res['bedrock'], res['surface'],
            res['planet_climate'], res['planet_offsets'], res['planet_heightmap'],
            res['ecosystem_climates'], res['ecosystem_heightmaps']
        ]

        constant_buffers = [
            res['settings']
        ]

        output_buffers = [
            res['output_color'], res['output_heightmap'], res['output_ocean_mask']
        ]

        return Compute(self.settings.shader_main,
                       srv=samplers,
                       cbv=constant_buffers,
                       uav=output_buffers)

    def _get_hillshade_computer(self) -> Compute:
        res = self.gpu_resources

        samplers = [
            res['output_color'], res['output_heightmap'], res['output_ocean_mask']
        ]

        constant_buffers = [
            res['settings']
        ]

        output_buffers = [
            res['output_color']
        ]

        return Compute(self.settings.shader_hillshade,
                       srv=samplers,
                       cbv=constant_buffers,
                       uav=output_buffers)

    def _do_cleanup(self, *resources):
        for res_name in resources:
            if res_name in self.gpu_resources:
                del self.gpu_resources[res_name]

        gc.collect()  # Force GC to clean up/dispose the buffers we just del'd

    def _cleanup_planet_gpu_resources(self):
        self._do_cleanup('bedrock', 'surface',
                         'planet_climate', 'planet_offsets', 'planet_heightmap',
                         'ecosystem_climates', 'ecosystem_heightmaps',
                         'settings')

    def _create_planet_gpu_resources(self):
        climate_size = int(math.sqrt(len(self.planet.climate_data) / 4))
        offset_size = int(math.sqrt(len(self.planet.offset_data)))
        heightmap_size = int(math.sqrt(len(self.planet.heightmap_data) / 2))
        ecosystem_climate_size = self.planet.ecosystems[0].climate_image.width
        ecosystem_heightmap_size = self.planet.ecosystems[0].elevation_size

        self.gpu_resources['bedrock'] = Texture2D(128, 128, R8G8B8A8_UINT)
        self.gpu_resources['surface'] = Texture2D(128, 128, R8G8B8A8_UINT)
        self.gpu_resources['planet_climate'] = Texture2D(climate_size, climate_size, R8G8B8A8_UINT)
        self.gpu_resources['planet_offsets'] = Texture2D(offset_size, offset_size, R8_UINT)
        self.gpu_resources['planet_heightmap'] = Texture2D(heightmap_size, heightmap_size, R16_UINT)
        logger.debug(f"{climate_size=} {offset_size=} {heightmap_size=}")

        self.gpu_resources['ecosystem_climates'] = Texture3D(ecosystem_climate_size, ecosystem_climate_size,
                                                     len(self.planet.ecosystems), R8G8B8A8_UINT)
        self.gpu_resources['ecosystem_heightmaps'] = Texture3D(ecosystem_heightmap_size, ecosystem_heightmap_size,
                                                     len(self.planet.ecosystems), R16_UINT)

        self.gpu_resources['settings'] = Buffer(RenderJobSettings.PACK_LENGTH)

    def _write_planet_input_resources(self):
        def _update_from_lut(gpu_resource: Resource, fn_color: Callable[[LUTData], list[int]]):
            staging = Buffer(gpu_resource.size, HEAP_UPLOAD)
            data = [0 for _ in range(128 * 128 * 4)]
            for y in range(128):
                for x in range(128):
                    color = fn_color(self.planet.lut[x][y])
                    index = 4 * (y * 128 + x)
                    data[index + 0] = color[0]
                    data[index + 1] = color[1]
                    data[index + 2] = color[2]
                    data[index + 3] = color[3]
            # TODO: Can we write directly into the buffer as we generate?
            staging.upload(bytes(data))
            staging.copy_to(gpu_resource)
            # del staging

        def _update_from_bytes(gpu_resource: Resource, data: bytearray):
            logger.debug(f"_update_from_bytes({gpu_resource.size=} {len(data)=})")
            if gpu_resource.size < len(data):
                raise ValueError(f"Resource size ({gpu_resource.size}) does not match data size ({len(data)})")
            elif gpu_resource.size > len(data):
                logger.info(f"Resource size ({gpu_resource.size}) mismatch with data size ({len(data)})")
            staging = Buffer(gpu_resource.size, HEAP_UPLOAD)
            staging.upload(data)
            staging.copy_to(gpu_resource)
            # del staging
            # return gpu_resource

        def _update_from_ecosystems(gpu_resource: Resource, fn_data: Callable[[EcoSystem], Union[bytes, Image.Image]]):
            staging = Buffer(gpu_resource.size, HEAP_UPLOAD)
            framesize = int(gpu_resource.size / len(self.planet.ecosystems))
            for i, eco in enumerate(self.planet.ecosystems):
                eco_data = fn_data(eco)
                if isinstance(eco_data, Image.Image):
                    eco_bytes = eco_data.tobytes('raw', 'RGBA')
                else:
                    eco_bytes = eco_data
                staging.upload(eco_bytes, i * framesize)
            staging.copy_to(gpu_resource)
            del staging

        _update_from_lut(self.gpu_resources['bedrock'], lambda x: x.bedrockColor)
        _update_from_lut(self.gpu_resources['surface'], lambda x: x.surfaceColor)
        _update_from_bytes(self.gpu_resources['planet_climate'], self.planet.climate_data)
        _update_from_bytes(self.gpu_resources['planet_offsets'], self.planet.offset_data)
        _update_from_bytes(self.gpu_resources['planet_heightmap'], self.planet.heightmap_data)
        _update_from_ecosystems(self.gpu_resources['ecosystem_climates'], lambda x: x.climate_image)
        _update_from_ecosystems(self.gpu_resources['ecosystem_heightmaps'], lambda x: x.elevation_bytes)

    def _cleanup_gpu_output_resources(self):
        self._do_cleanup('output_color', 'output_heightmap', 'output_ocean_mask', 'readback')

    def _create_gpu_output_resources(self):
        if 'output_color' in self.gpu_resources:
            return

        # TODO: Support variable size output buffers. For now just render to fixed size and stitch
        #       Also wasting a bit of space having the heightmap 32BPP when we only need 16
        #       but this makes things a lot easier to work with elsewhere :^)
        out_w = self.render_resolution.width()
        out_h = self.render_resolution.height()
        output_color_texture = Texture2D(out_w, out_h, R8G8B8A8_UINT)

        # Check if self.settings is defined; otherwise, revert to R8_UINT
        if self.settings is None:
            output_heightmap_texture = Texture2D(out_w, out_h, R8_UINT)
        else:
            # Determine the appropriate format for the heightmap texture based on the bit depth
            if self.settings.heightmap_bit_depth == 8:
                output_heightmap_texture = Texture2D(out_w, out_h, R8_UINT)
            elif self.settings.heightmap_bit_depth == 16:
                output_heightmap_texture = Texture2D(out_w, out_h, R16_UINT)
            elif self.settings.heightmap_bit_depth == 32:
                output_heightmap_texture = Texture2D(out_w, out_h, R32_SINT)
            else:
                raise ValueError(f"Unsupported heightmap bit depth: {self.settings.heightmap_bit_depth}")

        output_ocean_mask_texture = Texture2D(out_w, out_h, R8_UINT)

        self.gpu_resources['output_color'] = output_color_texture
        self.gpu_resources['output_heightmap'] = output_heightmap_texture
        self.gpu_resources['output_ocean_mask'] = output_ocean_mask_texture
        # NOTE: We will use the same readback buffer to read output_color and output_heightmap
        #       We take output_color's size because it will be 2x the size of the heightmap tex
        self.gpu_resources['readback'] = Buffer(output_color_texture.size, HEAP_READBACK)
