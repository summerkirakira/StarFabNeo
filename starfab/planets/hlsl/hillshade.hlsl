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
    float hillshade_level;
    float hillshade_zenith;
    float hillshade_azimuth;

    int heightmap_bit_depth;

    int debug_mode;
};

Texture2D<uint4> input_color : register(t0);
Texture2D<int> input_heightmap: register(t1);
Texture2D<uint> input_ocean_mask: register(t2);

ConstantBuffer<RenderJobSettings> jobSettings : register(b0);

RWTexture2D<uint4> output_color : register(u0);

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

/* Texture2D<uint/int> implementations */


int take_sample_nn_int(Texture2D<int> texture, float2 position, int2 dimensions)
{
    return texture[position % dimensions];
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


float UnpackIntToFloat(int packedValue, int bit_depth)
{
    // Ensure the bit depth is valid
    if (bit_depth != 8 && bit_depth != 16 && bit_depth != 32)
        return 0.0;

    float normalizedValue = 0.0;

    if (bit_depth == 8)
    {
        // Convert unsigned 8-bit to signed range [-1, 1]
        normalizedValue = (packedValue / 255.0f) * 2.0f - 1.0f;
    }
    else if (bit_depth == 16)
    {
        // Convert unsigned 16-bit to signed range [-1, 1]
        normalizedValue = (packedValue / 65535.0f) * 2.0f - 1.0f;
    }
    else if (bit_depth == 32)
    {
        // Convert signed 32-bit to signed range [-1, 1]
        normalizedValue = packedValue / 2147483647.0f; // 2^31 - 1 (maximum positive value for a 32-bit signed integer)
    }

    return normalizedValue;
}



float read_height(uint2 coordinate, int2 relative, int2 dimensions)
{
    float max_deform = jobSettings.global_terrain_height_influence + jobSettings.ecosystem_terrain_height_influence;

    int packedValue = take_sample_nn_int(input_heightmap, coordinate + relative, dimensions); //input_heightmap is uint for 8 and 16 bit!
    float height = UnpackIntToFloat(packedValue, jobSettings.heightmap_bit_depth); //UnpackIntToFloat should deal with 8 and 16 bit cases (hopefully)

    return height * max_deform;
}




// Function to read and smooth the height map
float read_and_smooth_height(uint2 tid, int2 offset, uint2 hm_sz, Texture2D<int> input_heightmap)
{

    int smoothing = 1;
    if (jobSettings.render_scale[1] == 2) {
        smoothing = 2;
    } else if (jobSettings.render_scale[1] == 4) {
        smoothing = 3;
    } else if (jobSettings.render_scale[1] == 8) {
        smoothing = 4;
    } else if (jobSettings.render_scale[1] == 16) {
        smoothing = 5;
    }

    float sum = 0.0;
    int count = 0;
    for (int y = -1 * smoothing; y <= smoothing; y++)
    {
        for (int x = -1 * smoothing; x <= smoothing; x++)
        {
            int2 sample_pos = tid + offset + int2(x, y);
            if (sample_pos.x >= 0 && sample_pos.x < hm_sz.x && sample_pos.y >= 0 && sample_pos.y < hm_sz.y)
            {
                float sample_height = input_heightmap.Load(int3(sample_pos, 0));
                sum += sample_height;
                count++;
            }
        }
    }
    return sum / count;
}

[numthreads(8, 8, 1)]
void main(uint3 tid : SV_DispatchThreadID)
{
    uint2 hm_sz;
    input_heightmap.GetDimensions(hm_sz.x, hm_sz.y);

    if (input_ocean_mask[tid.xy] != 0)
        return;

    float pi = 3.14159265359f;
    float ZFactor = 100.0f;

    // Calculating the cell size considering equirectangular projection
    float planet_circ_m = pi * 2 * jobSettings.planet_radius;
    float lat = (tid.y / (float)hm_sz.y) * pi - pi / 2; // Convert y to latitude in radians
    float cosLat = cos(lat);
    float cellsize_x = planet_circ_m * cosLat / (hm_sz.x * jobSettings.render_scale);
    float cellsize_y = planet_circ_m / (hm_sz.y * jobSettings.render_scale);

    // Slope calculations with larger feature capture
    float heights[9];
    int2 offsets[9] = { int2(-2, -2), int2(0, -2), int2(2, -2), int2(-2, 0), int2(2, 0), int2(-2, 2), int2(0, 2), int2(2, 2), int2(0, 0) };
    for (int i = 0; i < 9; i++)
    {
        heights[i] = read_and_smooth_height(tid.xy, offsets[i], hm_sz, input_heightmap);
    }

    float dzdx = ((heights[2] + 2 * heights[4] + heights[5]) - (heights[0] + 2 * heights[3] + heights[6])) / (8 * cellsize_x);
    float dzdy = ((heights[6] + 2 * heights[7] + heights[5]) - (heights[0] + 2 * heights[1] + heights[2])) / (8 * cellsize_y);
    float slope = atan(ZFactor * sqrt(dzdx * dzdx + dzdy * dzdy));

    float aspect = 0.0;
    if (dzdx != 0)
    {
        aspect = atan2(dzdy, -dzdx);
        if (aspect < 0)
            aspect += pi * 2;
    }
    else
    {
        if (dzdy > 0)
            aspect = pi / 2;
        else if (dzdy < 0)
            aspect = 3 * pi / 2;
    }

    // Normalize slope to [0, 1]
    slope = min(pi, max(0, slope)) / pi;

    // Calculate hillshade
    float cos_zenith = cos(jobSettings.hillshade_zenith);
    float sin_zenith = sin(jobSettings.hillshade_zenith);
    float cos_slope = cos(slope);
    float sin_slope = sin(slope);
    float cos_azimuth_aspect = cos(jobSettings.hillshade_azimuth - aspect);

    int hillshade_amount = (int)(255 * (cos_zenith * cos_slope + sin_zenith * sin_slope * cos_azimuth_aspect));
    hillshade_amount = (hillshade_amount - 127) / 4;

    // Ray marching for longer shadows
    float dx = cos(jobSettings.hillshade_azimuth) * cos(jobSettings.hillshade_zenith);
    float dy = sin(jobSettings.hillshade_azimuth) * cos(jobSettings.hillshade_zenith);
    float dz = sin(jobSettings.hillshade_zenith);

    float max_distance = 1000.0; // Maximum distance to march the ray
    float step_size = 1.0; // Step size for ray marching
    float shadow_intensity = 0.0; // Shadow intensity
    float current_distance = 0.0;

    float3 position = float3(tid.xy, read_and_smooth_height(tid.xy, int2(0, 0), hm_sz, input_heightmap) * ZFactor);

    while (current_distance < max_distance)
    {
        position += float3(dx * step_size, dy * step_size, dz * step_size);
        current_distance += step_size;

        int2 sample_pos = int2(position.xy);
        if (sample_pos.x < 0 || sample_pos.x >= hm_sz.x || sample_pos.y < 0 || sample_pos.y >= hm_sz.y)
            break;

        float sample_height = read_and_smooth_height(sample_pos, int2(0, 0), hm_sz, input_heightmap) * ZFactor;

        if (position.z < sample_height)
        {
            shadow_intensity = 1.0;
            break;
        }
    }

    int ray_march_shadow_amount = (int)(255 * (1.0 - shadow_intensity));
    ray_march_shadow_amount = (ray_march_shadow_amount - 127) / 16;

    // Combine hillshade and ray marching shadows
    int combined_shadow_amount = (hillshade_amount + ray_march_shadow_amount) * jobSettings.hillshade_level;

    // Apply combined shadows to color
    int3 final_color = output_color[tid.xy].xyz;

    final_color.x = max(0, min(255, final_color.x + combined_shadow_amount));
    final_color.y = max(0, min(255, final_color.y + combined_shadow_amount));
    final_color.z = max(0, min(255, final_color.z + combined_shadow_amount));

    uint3 final_color_uint;
    final_color_uint.x = (uint)final_color.x;
    final_color_uint.y = (uint)final_color.y;
    final_color_uint.z = (uint)final_color.z;

    output_color[tid.xy].xyz = final_color_uint;
}

