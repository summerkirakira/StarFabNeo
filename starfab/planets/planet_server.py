import asyncio
from threading import Lock

from PySide6.QtCore import QPointF
from flask import Flask, send_file, request
from flask_cors import CORS
from io import BytesIO
from PIL import Image
from math import pi, atan, sinh, degrees, floor

from scdatatools import StarCitizen

from starfab.planets.data import RenderSettings
from starfab.planets.ecosystem import EcoSystem
from starfab.planets.planet_renderer import PlanetRenderer, RenderResult

app = Flask(__name__)
CORS(app)

from starfab.planets import planet_renderer
from starfab.planets.planet import Planet
from starfab.gui.widgets.pages.page_PlanetView import PlanetView

def tile_to_lon_lat(z, x, y):
    n = 2.0 ** z
    lon_deg = x / n * 360.0 - 180.0
    lat_rad = atan(sinh(pi * (1 - 2 * y / n)))
    lat_deg = degrees(lat_rad)
    return lon_deg, lat_deg


def create_gradient_tile(z, x, y):
    # Assuming each tile is 256x256 pixels
    tile_size = 256
    map_size = 2 ** z * tile_size

    # Create a gradient image
    image = Image.new('RGB', (tile_size, tile_size))
    pixels = image.load()

    for i in range(tile_size):
        for j in range(tile_size):
            u = (x * tile_size + i) / map_size  # U coordinate
            v = (y * tile_size + j) / map_size  # V coordinate

            lon = u * 360.0 - 180.0
            lat_rad = atan(sinh(pi * (1 - 2 * v)))
            lat = degrees(lat_rad)

            red = int((1 - v) * 255)  # Red based on V (inverse of latitude)
            green = int(u * 255)  # Green based on U (longitude)
            blue = 0  # No blue channel
            pixels[i, j] = (red, green, blue)

    return image


def get_rendersize_from_zoom(z):
    tile_size = 256
    map_size = 2 ** z * tile_size
    planet_size = renderer.planet.tile_count

    if map_size <= planet_size:
        return 1
    else:
        return int(map_size / planet_size)


def get_xyz_normalized(z, x, y) -> QPointF:
    tile_size = 256
    map_size = 2 ** z * tile_size

    n_x = (x * tile_size) / map_size  # U coordinate
    n_y = (y * tile_size) / map_size  # V coordinate

    return QPointF(n_x, n_y)


def find_render(z, x, y) -> RenderResult:
    for cached_result in result_stack:
        if contains_tile(cached_result[1], z, x, y):
            # print("Cache HIT!")
            cached_result[0] += 1
            return cached_result[1]

    # print("Cache MISS!")
    new_render = render_tile(z, x, y)

    if not contains_tile(new_render, z, x, y):
        #breakpoint()
        # TODO: Something still isn't quite right...
        pass

    if len(result_stack) == 10:
        # Remove the cache entry with the fewest hits
        result_stack.remove(min(result_stack, key=lambda r: r[0]))

    result_stack.append([1, new_render])

    return new_render


def render_tile(z, x, y) -> RenderResult:
    renderscale = get_rendersize_from_zoom(z)
    render_settings.resolution = renderscale
    factor = 2 ** z

    tile_norm = get_xyz_normalized(z, x, y)

    # round x and y to the nearest 2^z interval
    render_x = floor(tile_norm.x() * renderscale) / renderscale
    render_y = floor(tile_norm.y() * renderscale) / renderscale

    # print(f"x={x},y={y},z={z} => {render_x},{render_y},{tile_norm}")

    if factor * 256 <= render_settings.output_resolution[1]:
        return do_render(0, 0)

    return do_render(render_x, render_y)


def contains_tile(result: RenderResult, z, x, y):
    tile_size = 256
    map_size = 2 ** z * tile_size

    # Even the smallest buffer fits 4 tiles tall, so is good to 3 zoom levels by itself
    if result.tex_color.height >= map_size:
        return True

    planet_scale = result.coordinate_bounds_planet.height() / result.coordinate_bounds.height()
    planet_size = result.tex_color.height * planet_scale

    # If this is intended for a different zoom level
    if map_size != planet_size:
        return False

    n_r = result.coordinate_normalized
    n_x = (x * tile_size) / map_size  # U coordinate
    n_y = (y * tile_size) / map_size  # V coordinate

    if n_r.left() <= n_x < n_r.right() and \
       n_r.top() <= n_y < n_r.bottom():
        return True
    else:
        return False


def extract_tile(result: RenderResult, z, x, y, layer: str):
    tile_size = 256
    map_size = 2 ** z * tile_size
    planet_scale = result.coordinate_bounds_planet.height() / result.coordinate_bounds.height()
    planet_size = result.tex_color.height * planet_scale

    n_r = result.coordinate_normalized
    n_t = get_xyz_normalized(z, x, y)

    sample_offset_x = (n_t.x() - n_r.left()) / n_r.width() * result.tex_color.width
    sample_offset_y = (n_t.y() - n_r.top()) / n_r.height() * result.tex_color.height

    # Outermost zoom levels
    # source_box is left, upper, *right*, *bottom*
    if map_size <= planet_size:
        upscale = planet_size / map_size
        source_box = (sample_offset_x, sample_offset_y,
                      sample_offset_x + (tile_size * 2 * upscale), sample_offset_y + (tile_size * upscale))
    else:
        source_box = (sample_offset_x, sample_offset_y,
                      sample_offset_x + (tile_size * 2), sample_offset_y + tile_size)
    target_size = (tile_size, tile_size)

    # print(f"x={x},y={y},z={z}")
    # print(f"n_r={n_r}, n_t={n_t}")
    # print(f"{result.coordinate_bounds}, {result.coordinate_bounds_planet} => {result.coordinate_normalized}")
    # print(source_box)
    source_image: Image

    if layer == "surface":
        source_image = result.tex_color
    elif layer == "heightmap":
        source_image = result.tex_heightmap
    else:
        raise Exception(f"Unknown layer: {layer}")

    return source_image.resize(target_size, box=source_box)


def do_render(x, y):
    with render_lock:
        # TODO: Check the cache first
        renderer.set_settings(render_settings)
        result = renderer.render(QPointF(x * 360, -90 + y * 180))
        return result


@app.route('/<layer>/<int:z>/<int:x>/<int:y>.png')
def get_tile(layer, z, x, y):
    result: RenderResult = find_render(z, x, y)
    image = extract_tile(result, z, x, y, layer)

    # Convert the image to bytes
    img_bytes = BytesIO()
    image.save(img_bytes, format='PNG')
    img_bytes.seek(0)

    # Return the image as a PNG file
    return send_file(img_bytes, mimetype='image/png')

print("SC Init")
sc = StarCitizen("E:\\SC\\StarCitizen\\PTU", p4k_load_monitor=None)
sc.load_all()

EcoSystem.read_eco_headers(sc)

print("Megamap Load")
megamap_pu = sc.datacore.search_filename(f'libs/foundry/records/megamap/megamap.pu.xml')[0]
pu_socpak_path = megamap_pu.properties['SolarSystems'][0].properties['ObjectContainers'][0].value
pu_oc = sc.oc_manager.load_socpak(pu_socpak_path)

print("Loading Body")

bodies = PlanetView._search_for_bodies(pu_oc)
body = bodies[0]
body.load_data()


main_shader = PlanetView._get_shader("shader.hlsl")
hillshade_shader = PlanetView._get_shader("hillshade.hlsl")

renderer: PlanetRenderer = PlanetRenderer((2048, 1024))
renderer.set_planet(body)
render_lock = Lock()
render_settings = RenderSettings(True, 1, "NASA", main_shader, hillshade_shader, 1, (2048, 1024), True, False, 16)

base_render = do_render(0, 0)

result_stack: list[list[int | RenderResult]] = []

if __name__ == '__main__':
    app.run(debug=False, port=8082)


