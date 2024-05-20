#define PI radians(180)
#define MODE_NN 0
#define MODE_BI_LINEAR 1
#define MODE_BI_CUBIC 2

struct RenderJobSettings
{
    float2 offset;
    float2 size;
    float planet_radius;
    int interpolation;
    int2 render_scale;

    float local_humidity_influence;
    float local_temperature_influence;
    float global_terrain_height_influence;
    float ecosystem_terrain_height_influence;

    bool ocean_enabled;
    bool ocean_mask_binary;
    bool ocean_heightmap_flat;
    float ocean_depth;
    uint4 ocean_color;

    bool blending_enabled;

    bool hillshade_enabled;
    float hillshade_zenith;
    float hillshade_azimuth;

    int heightmap_bit_depth;
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
Texture2D<uint> planet_heightmap : register(t4);
Texture3D<uint4> ecosystem_climates: register(t5);
Texture3D<uint> ecosystem_heightmaps: register(t6);

ConstantBuffer<RenderJobSettings> jobSettings : register(b0);

RWTexture2D<uint4> output_color : register(u0);
RWTexture2D<uint4> output_heightmap: register(u1);
RWTexture2D<uint> output_ocean_mask: register(u2);

uint4 lerp2d(uint4 ul, uint4 ur, uint4 bl, uint4 br, float2 value)
{
    float4 topRow = lerp(ul, ur, value.x);
    float4 bottomRow = lerp(bl, br, value.x);

    return lerp(topRow, bottomRow, value.y);
}

uint lerp2d(uint ul, uint ur, uint bl, uint br, float2 value)
{
    float topRow = lerp(ul, ur, value.x);
    float bottomRow = lerp(bl, br, value.x);

    return lerp(topRow, bottomRow, value.y);
}

uint4 interpolate_cubic(float4 v0, float4 v1, float4 v2, float4 v3, float fraction)
{
    float4 p = (v3 - v2) - (v0 - v1);
    float4 q = (v0 - v1) - p;
    float4 r = v2 - v0;

    return (fraction * ((fraction * ((fraction * p) + q)) + r)) + v1;
}

uint interpolate_cubic_uint(float v0, float v1, float v2, float v3, float fraction)
{
    float p = (v3 - v2) - (v0 - v1);
    float q = (v0 - v1) - p;
    float r = v2 - v0;

    return (fraction * ((fraction * ((fraction * p) + q)) + r)) + v1;
}

/* Texture2D<uint4> implementations */

uint4 take_sample_nn(Texture2D<uint4> texture, float2 position, int2 dimensions)
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

uint4 take_sample(Texture2D<uint4> texture, float2 position, int2 dimensions, int mode)
{
    if(mode == MODE_NN) {
        return take_sample_nn(texture, position, dimensions);
    } else if (mode == MODE_BI_LINEAR) {
        return take_sample_bilinear(texture, position, dimensions);
    } else if (mode == MODE_BI_CUBIC) {
        return take_sample_bicubic(texture, position, dimensions);
    } else {
        return uint4(0, 0, 0, 0);
    }
}

/* Texture2D<uint> implementations */

uint take_sample_nn(Texture2D<uint> texture, float2 position, int2 dimensions)
{
    return texture[position % dimensions];
}

uint take_sample_bilinear(Texture2D<uint> texture, float2 position, int2 dimensions)
{
    float2 offset = position - floor(position);
    uint tl = take_sample_nn(texture, position, dimensions);
    uint tr = take_sample_nn(texture, position + int2(1, 0), dimensions);
    uint bl = take_sample_nn(texture, position + int2(0, 1), dimensions);
    uint br = take_sample_nn(texture, position + int2(1, 1), dimensions);
    return lerp2d(tl, tr, bl, br, offset);
}

uint take_sample_bicubic(Texture2D<uint> texture, float2 position, int2 dimensions)
{
    float2 offset = position - floor(position);
    uint samples[4];

    for (int i = 0; i < 4; ++i)
    {
        float ll = take_sample_nn(texture, position + int2(-1, i - 1), dimensions);
        float ml = take_sample_nn(texture, position + int2( 0, i - 1), dimensions);
        float mr = take_sample_nn(texture, position + int2( 1, i - 1), dimensions);
        float rr = take_sample_nn(texture, position + int2( 2, i - 1), dimensions);
        samples[i] = interpolate_cubic_uint(ll, ml, mr, rr, offset.x);
    }

    return interpolate_cubic_uint(samples[0], samples[1], samples[2], samples[3], offset.y);
}

uint take_sample(Texture2D<uint> texture, float2 position, int2 dimensions, int mode)
{
    if(mode == 0) {
        return take_sample_nn(texture, position, dimensions);
    } else if (mode == 1) {
        return take_sample_bilinear(texture, position, dimensions);
    } else if (mode == 2) {
        return take_sample_bicubic(texture, position, dimensions);
    } else {
        return uint(0);
    }
}

/* Texture3D<uint> implementations */

uint take_sample_nn_3d(Texture3D<uint> texture, float2 position, int2 dimensions, int layer)
{
    uint3 read_pos;
    read_pos.xy = uint2(position % dimensions);
    read_pos.z = layer;
    return texture[read_pos];
}

/* Texture3D<uint4> implementations */

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

ProjectedTerrainInfluence calculate_projected_tiles(float2 normal_position, float2 projected_size, float2 terrain_size)
{
    uint2 out_sz; output_color.GetDimensions(out_sz.x, out_sz.y);
    uint2 clim_sz; planet_climate.GetDimensions(clim_sz.x, clim_sz.y);
    uint2 off_sz; planet_offsets.GetDimensions(off_sz.x, off_sz.y);
    uint2 hm_sz; planet_heightmap.GetDimensions(hm_sz.x, hm_sz.y);
    uint3 eco_sz; ecosystem_climates.GetDimensions(eco_sz.x, eco_sz.y, eco_sz.z);

    ProjectedTerrainInfluence result = {
        float2(0, 0),   //float2 temp_humidity
        0.0f,           //float elevation;
        0.0f,           //float mask_total;
        0,              //int num_influences;
        false,          //bool is_override;
        uint3(0,0,0)    //uint3 override;
    };

    // NOTE: These pixel dimensions are relative to the climate image
    float2 position_px = normal_position * clim_sz;
    float2 position_m = pixels_to_meters(position_px, clim_sz);

    LocalizedWarping projection_warping = get_local_image_warping(position_m, projected_size);
    LocalizedWarping physical_warping = get_local_image_warping(position_m, terrain_size);

    //upper_bound will be the lower number here because image is 0,0 top-left
    float upper_bound = position_px.y - (projection_warping.vertical_delta * clim_sz.y);
    float lower_bound = position_px.y + (projection_warping.vertical_delta * clim_sz.y);

    //No wrapping for Y-axis
    float search_y_start = clamp(floor(upper_bound), 0, clim_sz.y - 1);
    float search_y_end   = clamp(ceil(lower_bound), 0, clim_sz.y - 1);

    int terrain_step = 1;
    int pole_distance = clim_sz.y / 16;

    //TODO Vary terrain step from 1 at pole_distance to TileCount at the pole
    if (position_px.y < pole_distance / 2 || position_px.y >= clim_sz.y - pole_distance / 2) {
        terrain_step = 8;
    }else if(position_px.y < pole_distance || position_px.y >= clim_sz.y - pole_distance) {
        terrain_step = 4;
    }

    //Search vertically all cells that our projection overlaps with
    for(float search_y_px = search_y_start; search_y_px <= search_y_end; search_y_px += 1.0f)
    {
        //Turn this cells position back into meters, and calculate local distortion size for this row specifically
        float2 search_meters = pixels_to_meters(float2(0, search_y_px), clim_sz);
        float search_circumference = circumference_at_distance_from_equator(search_meters.y);
        float half_projected_width_px = (projected_size.x / 2 / search_circumference) * clim_sz.y;

        //Break if the circumference at this pixel is less than a single projection, ie: directly at poles
        if(search_circumference < projected_size.x)
            continue;

        float row_left_bound = position_px.x - half_projected_width_px;
        float row_right_bound = position_px.x + half_projected_width_px;
        float search_x_start = floor(row_left_bound);
        float search_x_end = ceil(row_right_bound);

        //Now search horizontally all cells that out projection (at this vertical position) overlaps with
        for (float search_x_px = search_x_start; search_x_px <= search_x_end; search_x_px += 1.0f)
        {
            if ((int)search_x_px % terrain_step != 0) continue;

            //We can use NN here since we are just looking for the ecosystem data
            uint2 search_pos = uint2(search_x_px, search_y_px);
            float2 search_pos_normal = search_pos / float2(clim_sz);

            // Only needed to extract the ecosystem ID at the location we are testing
            // This lets us determine which texture we blend with the ground, projecting from this grid position
            uint4 local_climate_data = take_sample(planet_climate, search_pos, clim_sz, 0);
            uint ecosystem_id = uint(local_climate_data.z / 16);

            // TODO: Use global random offset data
            float offset = take_sample_nn(planet_offsets, search_pos_normal * off_sz, off_sz) / 256.0f;
            float2 terrain_center = float2(search_x_px, search_y_px) + offset;

            //Now finally calculate the local distortion at the center of the terrain
            float2 terrain_center_m = pixels_to_meters(terrain_center, clim_sz.y);
            float terrain_circumference = circumference_at_distance_from_equator(terrain_center_m.y);
            float half_terrain_width_projected_px = (projected_size.x / 2 / terrain_circumference) * clim_sz.y;
            float half_terrain_width_physical_px = (terrain_size.x / 2 / terrain_circumference) * clim_sz.y;

            float terrain_left_edge = terrain_center.x - half_terrain_width_projected_px;
            float terrain_right_edge = terrain_center.x + half_terrain_width_projected_px;
            float terrain_top_edge = terrain_center.y - (projection_warping.vertical_delta * clim_sz.y);
            float terrain_bottom_edge = terrain_center.y + (projection_warping.vertical_delta * clim_sz.y);

            //Reject pixels outside of the terrains projected pixel borders
            if (position_px.x < terrain_left_edge || position_px.x > terrain_right_edge)
                continue;
            if (position_px.y < terrain_top_edge || position_px.y > terrain_bottom_edge)
                continue;

            //Finally calculate UV coordinates and return result
            float terrain_u = ((position_px.x - terrain_center.x) / half_terrain_width_physical_px / 2) + 0.5f;
            float terrain_v = ((position_px.y - terrain_center.y) / (physical_warping.vertical_delta * clim_sz.y * 2)) + 0.5f;
            float patch_u = ((position_px.x - terrain_left_edge) / (half_terrain_width_projected_px * 2));
            float patch_v = ((position_px.y - terrain_top_edge) / (projection_warping.vertical_delta * clim_sz.y * 2));

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

            int4 local_eco_data = take_sample_nn_3d(ecosystem_climates, terrain_uv * eco_sz.xy, eco_sz.xy, ecosystem_id);
            float4 local_eco_normalized = (local_eco_data - 127) / 127.0f;
            // TODO: Heightmaps
            float local_eco_height = take_sample_nn_3d(ecosystem_heightmaps, terrain_uv * eco_sz.xy, eco_sz.xy, ecosystem_id);
	        local_eco_height = (local_eco_height - 32767) / 32767.0f;

            if (false && (round(search_x_px % 20) == 0 && round(search_y_px % 20) == 0)) {
                result.is_override = true;
                //result.override = uint3(255 * terrain_uv.x, 255 * terrain_uv.y, 0) * local_mask_value;
                result.override = uint3(offset * 256, 0, 0);
                return result;
            }

            result.temp_humidity += local_eco_normalized.xy * local_mask_value;
            result.elevation += local_eco_height * local_mask_value;
            result.mask_total += local_mask_value;
            result.num_influences += 1;
        }
    }

    result.temp_humidity = min(float2(1, 1), max(float2(-1, -1), result.temp_humidity));
    result.elevation = min(1, max(-1, result.elevation));

    result.temp_humidity /= result.mask_total;
    result.elevation /= result.mask_total;

    return result;
}

uint4 PackFloatToUInt4(float value, int bit_depth)
{
    if (bit_depth != 8 && bit_depth != 16 && bit_depth != 24 && bit_depth != 32)
        return uint4(0, 0, 0, 0);

    // Clamp the input value to the range [-1.0, 1.0]
    value = clamp(value, -1.0f, 1.0f);

    // Map the range [-1.0, 1.0] to the range [0.0, 1.0]
    value = value * 0.5f + 0.5f;

    // Convert the float value to 32-bit unsigned integer
    float factor = (1 << bit_depth) - 1.0f;
    uint intValue = uint(value * factor);

    // Pack the unsigned integer value into a uint4
    uint4 packedValue;

    packedValue.x = (intValue >> 0) & 0xFF;

    if (bit_depth == 8) { //Render as greyscale
        packedValue.y = (intValue >> 0) & 0xFF;
        packedValue.z = (intValue >> 0) & 0xFF;
        packedValue.w = 255;
    } else {
        //Valid for 16, 24 and 32 bit
        packedValue.y = (intValue >> 8) & 0xFF;
        packedValue.z = (intValue >> 16) & 0xFF;

        if (bit_depth == 32) {
            packedValue.w = (intValue >> 24) & 0xFF;
        } else {
            packedValue.w = 255;
        }
    }

    return packedValue;
}

// TODO: Use the z-thread ID for doing sub-pixel searching
[numthreads(8,8,1)]
void main(uint3 tid : SV_DispatchThreadID)
{
    uint2 out_sz; output_color.GetDimensions(out_sz.x, out_sz.y);
    uint2 clim_sz; planet_climate.GetDimensions(clim_sz.x, clim_sz.y);
    uint2 off_sz; planet_offsets.GetDimensions(off_sz.x, off_sz.y);
    uint2 hm_sz; planet_heightmap.GetDimensions(hm_sz.x, hm_sz.y);

    float terrain_scaling = 1;
    float2 projected_size = float2(6000, 6000) * terrain_scaling;
    float2 physical_size = float2(4000, 4000) * terrain_scaling;
    float2 local_influence = float2(jobSettings.local_temperature_influence, jobSettings.local_humidity_influence);
    float max_deformation = jobSettings.global_terrain_height_influence + jobSettings.ecosystem_terrain_height_influence;

    // Calculate normalized position in the world (ie: 0,0 = top-left, 1,1 = bottom-right)
	float2 normalized_position = tid.xy / float2(clim_sz) / jobSettings.render_scale;
	normalized_position.xy += jobSettings.offset;
	//normalized_position.y += 0.25f;
	normalized_position = normalized_position % 1;

    // Sample global data
	uint4 global_climate = take_sample(planet_climate, normalized_position * clim_sz, clim_sz, jobSettings.interpolation);
	float global_height = take_sample(planet_heightmap, normalized_position * hm_sz, hm_sz, jobSettings.interpolation);
	uint global_offset = take_sample_nn(planet_offsets, normalized_position * off_sz, off_sz);

	global_height = (global_height - 32767) / 32767.0f;
    global_climate = uint4(global_climate.xy / 2, 0, 0);

	uint4 out_color = uint4(0, 0, 0, 255);
	float out_height = global_height * jobSettings.global_terrain_height_influence; // Value
	float out_ocean_mask = 0;

    if (jobSettings.blending_enabled) {
        // Calculate influence of all neighboring terrain
        ProjectedTerrainInfluence eco_influence = calculate_projected_tiles(normalized_position, projected_size, physical_size);

        if (eco_influence.is_override) {
            out_color.xyz = eco_influence.override;
        } else {
            if(eco_influence.mask_total > 0) {
                global_climate.yx += eco_influence.temp_humidity * local_influence;
                out_height += eco_influence.elevation * jobSettings.ecosystem_terrain_height_influence;
            }

            uint4 surface_color = take_sample(surface, global_climate.yx, int2(128, 128), jobSettings.interpolation);
            out_color.xyz = surface_color.xyz;
        }
    } else {
        uint4 surface_color = take_sample(surface, global_climate.yx, int2(128, 128), jobSettings.interpolation);
        out_color.xyz = surface_color.xyz;
    }

    if (jobSettings.ocean_enabled && out_height < jobSettings.ocean_depth) {

        out_color.xyz = jobSettings.ocean_color.xyz;

        if (jobSettings.ocean_mask_binary) {
            out_ocean_mask = 1.0;
        } else {
            float ocean_bottom = -max_deformation;
            float relative_depth = jobSettings.ocean_depth - out_height;
            float ocean_max_depth = jobSettings.ocean_depth - ocean_bottom;

            out_ocean_mask = relative_depth / ocean_max_depth;
        }

        if (jobSettings.ocean_heightmap_flat) {
            out_height = jobSettings.ocean_depth;
        }
    } else {
        //Color already applied, no need to do anything
        out_ocean_mask = 0;
    }

    // Squash out_height from meter range to normalized +/- 1.0 range
    out_height /= max_deformation;

	// DEBUG: Grid rendering
	int2 cell_position = int2(normalized_position * out_sz * jobSettings.render_scale) % jobSettings.render_scale;
	if(false && (cell_position.x == 0 || cell_position.y == 0))
	{
	    out_color.xyz = uint3(255, 0, 0);
	}

	output_color[tid.xy] = out_color;

	output_heightmap[tid.xy] = PackFloatToUInt4(out_height, jobSettings.heightmap_bit_depth);
	output_ocean_mask[tid.xy] = min(max(out_ocean_mask * 255, 0), 255);
}