#define PI radians(180)

struct RenderJobSettings
{
    float2 offset;
    float2 size;
    float planet_radius;
    int interpolation;
    int2 render_scale;
    float local_humidity_influence;
    float local_temperature_influence;
};

struct LocalizedWarping
{
    float2 center;
    float vertical_delta;
    float upper_width;
    float lower_width;
};

struct ProjectedTerrainInfluence
{
    float2 temp_humidity;
    float elevation;
    float mask_total;
    int num_influences;

    bool is_override;
    uint3 override;
};

Texture2D<uint4> bedrock : register(t0);
Texture2D<uint4> surface : register(t1);
Texture2D<uint4> planet_climate : register(t2);
Texture2D<uint> planet_offsets : register(t3);
Texture2D<min16uint> planet_heightmap : register(t4);
Texture3D<uint4> ecosystem_climates: register(t5);

RWTexture2D<uint4> destination : register(u0);

ConstantBuffer<RenderJobSettings> jobSettings : register(b0);

uint4 lerp2d(uint4 ul, uint4 ur, uint4 bl, uint4 br, float2 value)
{
    float4 topRow = lerp(ul, ur, value.x);
    float4 bottomRow = lerp(bl, br, value.x);

    return lerp(topRow, bottomRow, value.y);
}

uint4 interpolate_cubic(float4 v0, float4 v1, float4 v2, float4 v3, float fraction)
{
    float4 p = (v3 - v2) - (v0 - v1);
    float4 q = (v0 - v1) - p;
    float4 r = v2 - v0;

    return (fraction * ((fraction * ((fraction * p) + q)) + r)) + v1;
}

uint4 take_sample_nn(Texture2D<uint4> texture, float2 position, int2 dimensions)
{
    return texture[position % dimensions];
}

uint take_sample_nn(Texture2D<uint> texture, float2 position, int2 dimensions)
{
    return texture[position % dimensions];
}

uint4 take_sample_bilinear(Texture2D<uint4> texture, float2 position, int2 dimensions)
{
    float2 offset = position - floor(position);
    uint4 tl = take_sample_nn(texture, position, dimensions);
    uint4 tr = take_sample_nn(texture, position + int2(1, 0), dimensions);
    uint4 bl = take_sample_nn(texture, position + int2(0, 1), dimensions);
    uint4 br = take_sample_nn(texture, position + int2(1, 1), dimensions);
    return lerp2d(tl, tr, bl, br, offset);
}

uint4 take_sample_bicubic(Texture2D<uint4> texture, float2 position, int2 dimensions)
{
    float2 offset = position - floor(position);
    uint4 samples[4];

    for (int i = 0; i < 4; ++i)
    {
        float4 ll = take_sample_nn(texture, position + int2(-1, i - 1), dimensions);
        float4 ml = take_sample_nn(texture, position + int2( 0, i - 1), dimensions);
        float4 mr = take_sample_nn(texture, position + int2( 1, i - 1), dimensions);
        float4 rr = take_sample_nn(texture, position + int2( 2, i - 1), dimensions);
        samples[i] = interpolate_cubic(ll, ml, mr, rr, offset.x);
    }

    return interpolate_cubic(samples[0], samples[1], samples[2], samples[3], offset.y);
}

uint4 take_sample_nn_3d(Texture3D<uint4> texture, float2 position, int2 dimensions, int layer)
{
    uint3 read_pos;
    read_pos.xy = uint2(position % dimensions);
    read_pos.z = layer;
    return texture[read_pos];
}

int4 take_sample_bicubic_3d(Texture3D<uint4> texture, float2 position, int2 dimensions, int layer)
{
    float2 offset = position - floor(position);
    int4 samples[4];

    for (int i = 0; i < 4; ++i)
    {
        float4 ll = take_sample_nn_3d(texture, position + int2(-1, i - 1), dimensions, layer);
        float4 ml = take_sample_nn_3d(texture, position + int2( 0, i - 1), dimensions, layer);
        float4 mr = take_sample_nn_3d(texture, position + int2( 1, i - 1), dimensions, layer);
        float4 rr = take_sample_nn_3d(texture, position + int2( 2, i - 1), dimensions, layer);
        samples[i] = interpolate_cubic(ll, ml, mr, rr, offset.x);
    }

    return interpolate_cubic(samples[0], samples[1], samples[2], samples[3], offset.y);
}

uint4 take_sample_uint(Texture2D<uint4> texture, float2 position, int2 dimensions, int mode)
{
    if(mode == 0) {
        return take_sample_nn(texture, position, dimensions);
    } else if (mode == 1) {
        return take_sample_bilinear(texture, position, dimensions);
    } else if (mode == 2) {
        return take_sample_bicubic(texture, position, dimensions);
    } else {
        return uint4(0, 0, 0, 0);
    }
}

float circumference_at_distance_from_equator(float vertical_distance_meters)
{
    float half_circumference_km = PI * jobSettings.planet_radius;
    //Normalize to +/-0.5, then * pi to get +/- half_pi
    float angle = (vertical_distance_meters / half_circumference_km) * PI;
    return (float)(cos(angle) * jobSettings.planet_radius * PI * 2);
}

float2 get_normalized_location(float2 position_meters)
{
    float half_circumference_m = (float)(PI * jobSettings.planet_radius);
    float vert_normalized = ((position_meters.y / half_circumference_m) + 0.5f);
    float vert_circ = circumference_at_distance_from_equator(position_meters.y);
    float horiz_normalized = ((position_meters.x / vert_circ) + 0.5f);

    return float2(min(1.0f, max(0.0f, horiz_normalized)),
            min(1.0f, max(0.0f, vert_normalized))); //  0.0 - 1.0 for x,y
}

float2 pixels_to_meters(float2 position, int2 dimensions)
{
    if (position.x < 0) position.x += dimensions.x;
    if (position.y < 0) position.y += dimensions.y;
    if (position.x >= dimensions.x) position.x -= dimensions.x;
    if (position.y >= dimensions.y) position.y -= dimensions.y;

    float half_circumference_km = (float)(PI * jobSettings.planet_radius);

    float vert_distance = ((position.y / dimensions.y) - 0.5f) * half_circumference_km; // +/- 1/4 circumference
    float vert_circ = circumference_at_distance_from_equator(vert_distance);
    float horiz_distance = ((position.x / dimensions.x) - 0.5f) * vert_circ; // +/- 1/2 circumference

    return float2(horiz_distance, vert_distance);
}

LocalizedWarping get_local_image_warping(float2 position_meters, float2 patch_size_meters)
{
    LocalizedWarping result;

    float upper_circ = circumference_at_distance_from_equator(position_meters.y + (patch_size_meters.y / 2));
    float lower_circ = circumference_at_distance_from_equator(position_meters.y - (patch_size_meters.y / 2));

    result.center = get_normalized_location(position_meters);
    result.vertical_delta = (float)(patch_size_meters.y / 2.0f / (PI * jobSettings.planet_radius));
    result.upper_width = (patch_size_meters.x / 2.0f) / upper_circ;
    result.lower_width = (patch_size_meters.x / 2.0f) / lower_circ;

    return result;
}

ProjectedTerrainInfluence calculate_projected_tiles(float2 position, int2 dimensions, float2 projected_size, float2 terrain_size)
{
    uint off_w, off_h;
    planet_offsets.GetDimensions(off_w, off_h);
    uint2 off_sz = uint2(off_w, off_h);

    ProjectedTerrainInfluence result = {
        float2(0, 0),   //float2 temp_humidity
        0.0f,           //float elevation;
        0.0f,           //float mask_total;
        0,              //int num_influences;
        false,          //bool is_override;
        uint3(0,0,0)    //uint3 override;
    };

    float2 pos_meters = pixels_to_meters(position, dimensions);

    LocalizedWarping projection_warping = get_local_image_warping(pos_meters, projected_size);
    LocalizedWarping physical_warping = get_local_image_warping(pos_meters, terrain_size);

    //upper_bound will be the lower number here because image is 0,0 top-left
    float upper_bound = position.y - (projection_warping.vertical_delta * dimensions.y);
    float lower_bound = position.y + (projection_warping.vertical_delta * dimensions.y);

    //No wrapping for Y-axis
    float search_y_start = clamp(floor(upper_bound), 0, dimensions.y - 1);
    float search_y_end   = clamp(ceil(lower_bound), 0, dimensions.y - 1);

    int terrain_step = 1;
    int pole_distance = dimensions.y / 16;

    //TODO Vary terrain step from 1 at pole_distance to TileCount at the pole
    if (position.y < pole_distance / 2 || position.y >= dimensions.y - pole_distance / 2) {
        terrain_step = 8;
    }else if(position.y < pole_distance || position.y >= dimensions.y - pole_distance) {
        terrain_step = 4;
    }

    if (round(position.x - 0.5f) == 40 && round(position.y - 0.5f) == 40) {
        result.is_override = true;
        result.override = uint3(0, 255, 0);
        return result;
    }

    //Search vertically all cells that our projection overlaps with
    for(float search_y_px = search_y_start; search_y_px <= search_y_end; search_y_px += 1.0f)
    {
        //Turn this cells position back into meters, and calculate local distortion size for this row specifically
        float2 search_meters = pixels_to_meters(float2(0, search_y_px), dimensions);
        float search_circumference = circumference_at_distance_from_equator(search_meters.y);
        float half_projected_width_px = (projected_size.x / 2 / search_circumference) * dimensions.y;

        //Break if the circumference at this pixel is less than a single projection, ie: directly at poles
        if(search_circumference < projected_size.x)
            continue;

        float row_left_bound = position.x - half_projected_width_px;
        float row_right_bound = position.x + half_projected_width_px;
        float search_x_start = floor(row_left_bound);
        float search_x_end = ceil(row_right_bound);

        //Now search horizontally all cells that out projection (at this vertical position) overlaps with
        for (float search_x_px = search_x_start; search_x_px <= search_x_end; search_x_px += 1.0f)
        {
            if ((int)search_x_px % terrain_step != 0) continue;

            //We can use NN here since we are just looking for the ecosystem data
            uint2 search_pos = uint2(search_x_px, search_y_px);

            uint4 global_climate = take_sample_uint(planet_climate, search_pos, dimensions, 0);
            uint ecosystem_id = uint(global_climate.z / 16);

            // TODO: Use global random offset data
            float offset = take_sample_nn(planet_offsets, float2(search_pos) / dimensions * off_sz, off_sz) / 256.0f;
            float2 terrain_center = float2(search_x_px, search_y_px) + offset;

            //Now finally calculate the local distortion at the center of the terrain
            float2 terrain_center_m = pixels_to_meters(terrain_center, dimensions.y);
            float terrain_circumference = circumference_at_distance_from_equator(terrain_center_m.y);
            float half_terrain_width_projected_px = (projected_size.x / 2 / terrain_circumference) * dimensions.y;
            float half_terrain_width_physical_px = (terrain_size.x / 2 / terrain_circumference) * dimensions.y;

            float terrain_left_edge = terrain_center.x - half_terrain_width_projected_px;
            float terrain_right_edge = terrain_center.x + half_terrain_width_projected_px;
            float terrain_top_edge = terrain_center.y - (projection_warping.vertical_delta * dimensions.y);
            float terrain_bottom_edge = terrain_center.y + (projection_warping.vertical_delta * dimensions.y);

            //Reject pixels outside of the terrains projected pixel borders
            if (position.x < terrain_left_edge || position.x > terrain_right_edge)
                continue;
            if (position.y < terrain_top_edge || position.y > terrain_bottom_edge)
                continue;

            //Finally calculate UV coordinates and return result
            float terrain_u = ((position.x - terrain_center.x) / half_terrain_width_physical_px / 2) + 0.5f;
            float terrain_v = ((position.y - terrain_center.y) / (physical_warping.vertical_delta * dimensions.y * 2)) + 0.5f;
            float patch_u = ((position.x - terrain_left_edge) / (half_terrain_width_projected_px * 2));
            float patch_v = ((position.y - terrain_top_edge) / (projection_warping.vertical_delta * dimensions.y * 2));

            if (terrain_u < 0) terrain_u += 1;
            if (terrain_v < 0) terrain_v += 1;
            if (terrain_u >= 1) terrain_u -= 1;
            if (terrain_v >= 1) terrain_v -= 1;

            if (patch_u < 0) patch_u += 1;
            if (patch_v < 0) patch_v += 1;
            if (patch_u >= 1) patch_u -= 1;
            if (patch_v >= 1) patch_v -= 1;

            float2 terrain_uv = float2(terrain_u, terrain_v);
            float2 patch_uv = float2(patch_u, patch_v);

            float2 delta = patch_uv - float2(0.5f, 0.5f);
            float center_distance = sqrt(delta.x * delta.x + delta.y * delta.y) * 1;
            float local_mask_value = (float)(center_distance > 0.5f ? 0 : cos(center_distance * PI));

            uint2 size = uint2(1024, 1024);
            int4 local_eco_data = take_sample_nn_3d(ecosystem_climates, terrain_uv * size, size, ecosystem_id);
            float4 local_eco_normalized = (local_eco_data - 127) / 127.0f;
            // TODO: Heightmaps

            if (false && (round(search_x_px % 20) == 0 && round(search_y_px % 20) == 0)) {
                result.is_override = true;
                //result.override = uint3(255 * terrain_uv.x, 255 * terrain_uv.y, 0) * local_mask_value;
                result.override = uint3(planet_offsets[search_pos], 0, 0);
                return result;
            }

            result.temp_humidity += local_eco_normalized * local_mask_value;
            result.mask_total += local_mask_value;
            result.num_influences += 1;
        }
    }

    return result;
}

// TODO: Use the z-thread ID for doing sub-pixel searching
[numthreads(8,8,1)]
void main(uint3 tid : SV_DispatchThreadID)
{
	uint width;
	uint height;
	destination.GetDimensions(width, height);
	uint2 out_sz = uint2(width, height);

	uint clim_w, clim_h;
	planet_climate.GetDimensions(clim_w, clim_h);
	uint2 clim_sz = uint2(clim_w, clim_h);

    uint off_w, off_h;
    planet_offsets.GetDimensions(off_w, off_h);
    uint2 off_sz = uint2(off_w, off_h);

	float2 normalized_position = tid.xy / float2(out_sz) / jobSettings.render_scale;
	normalized_position.xy += jobSettings.offset;
	normalized_position.y += 0.5f;
	normalized_position = normalized_position % 1;

    uint4 local_nn = take_sample_uint(planet_climate, normalized_position * clim_sz, clim_sz, 0);
    uint local_ecosystem = local_nn.z / 16;
    uint global_offset = take_sample_nn(planet_offsets, normalized_position * off_sz, off_sz);

	uint4 local_climate = take_sample_uint(planet_climate, normalized_position * clim_sz, clim_sz, jobSettings.interpolation);
	uint4 read = uint4(0, 0, 0, 255);
	// uint4 local_climate = planet_climate[normalized_position * clim_sz];

	local_climate = uint4(local_climate.xy, 0, 0);
    float terrain_scaling = 1.5f;
    float2 projected_size = float2(6000, 6000) * terrain_scaling;
    float2 physical_size = float2(4000, 4000) * terrain_scaling;
    float2 local_influence = float2(jobSettings.local_humidity_influence, jobSettings.local_temperature_influence);

    ProjectedTerrainInfluence eco_influence = calculate_projected_tiles(normalized_position * out_sz, out_sz, projected_size, physical_size);

    if (eco_influence.is_override) {
        read.xyz = eco_influence.override;
    } else {
        if(eco_influence.mask_total > 0) {
            eco_influence.temp_humidity /= eco_influence.mask_total;
            local_climate.yx += eco_influence.temp_humidity * local_influence;

        }

        uint4 surface_color = take_sample_uint(surface, local_climate.yx / 2, int2(128, 128), jobSettings.interpolation);

        read.xyz = surface_color.xyz;
    }

	// Grid rendering
	int2 cell_position = tid.xy % jobSettings.render_scale;
	if(false && (cell_position.x == 0 || cell_position.y == 0))
	{
	    read.x = 255;
	    read.y = 0;
	    read.z = 0;
	}

	destination[tid.xy] = read;
}