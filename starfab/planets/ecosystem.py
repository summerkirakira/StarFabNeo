import io
import json
import math
import os
from pathlib import Path
from typing import Union

from PIL import Image
from scdatatools import StarCitizen
from scdatatools.engine.textures import unsplit_dds
from scdatatools.p4k import P4KInfo

from starfab.log import getLogger
from starfab.planets.data import LocalClimateData
from starfab.utils import image_converter


logger = getLogger(__name__)

CACHE_DIR = Path('.cache')


class EcoSystem:
    _cache = {}
    _tex_root = Path("Data/Textures/planets/terrain")
    _sc: Union[None, StarCitizen] = None

    @staticmethod
    def find_in_cache_(guid: str):
        if guid in EcoSystem._cache:
            return EcoSystem._cache[guid]
        else:
            logger.error("Could not find EcoSystem with guid %r", guid)
            return None

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
        self.climate_image: Image = None
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

        # TODO: Use settings to define a cache directory to store these in
        def _read_with_cache(subpath: str) -> Image:
            check_path = (CACHE_DIR / subpath).with_suffix(".png")
            if not os.path.exists(check_path.parent):
                os.makedirs(check_path.parent)
            if check_path.exists():
                return Image.open(check_path)
            else:
                img = Image.open(io.BytesIO(_read_texture(subpath)))
                img.save(check_path, "png")
                return img

        self.climate_image = _read_with_cache(self.tex_path)
        self.normal_texture = _read_with_cache(self.norm_path)

        elevation_path = (EcoSystem._tex_root / self.elevation_path).as_posix().lower()
        elevation_info: P4KInfo = EcoSystem._sc.p4k.NameToInfoLower[elevation_path]
        with elevation_info.open() as o:
            self.elevation_bytes = bytearray(o.read())
            self.elevation_size = int(math.sqrt(len(self.elevation_bytes) / 2))

        logger.info(f"Textures loaded for {self.name}")
