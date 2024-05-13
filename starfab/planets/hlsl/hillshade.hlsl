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

    bool hillshade_enabled;
    float hillshade_zenith;
    float hillshade_azimuth;

    int heightmap_bit_depth;
};

Texture2D<uint4> input_color : register(t0);
Texture2D<uint4> input_heightmap: register(t1);
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

float UnpackUInt4ToFloat(uint4 packedValue, int bit_depth)
{
    // Ensure the bit depth is valid
    if (bit_depth != 8 && bit_depth != 16 && bit_depth != 24 && bit_depth != 32)
        return 0.0;

    // Combine the components of packedValue to reconstruct the float value
    float factor = (1L << bit_depth) - 1.0f;
    float reconstructedValue = 0.0;

    if (bit_depth == 8) { // Greyscale
        reconstructedValue = packedValue.x / factor;
    } else {
        // Combine components based on bit depth
        reconstructedValue += packedValue.x / factor;
        reconstructedValue += packedValue.y / factor * 256.0;
        reconstructedValue += packedValue.z / factor * 65536.0;

        if (bit_depth == 32) {
            reconstructedValue += packedValue.w / factor * 16777216.0;
        }
    }

    // Map the range [0.0, 1.0] back to [-1.0, 1.0]
    reconstructedValue = reconstructedValue * 2.0f - 1.0f;

    return reconstructedValue;
}

float read_height(uint2 coordinate, int2 relative, int2 dimensions)
{
    uint4 samp = take_sample_nn(input_heightmap, coordinate + relative, dimensions);
    float max_deform = jobSettings.global_terrain_height_influence + jobSettings.ecosystem_terrain_height_influence;
    return UnpackUInt4ToFloat(samp, jobSettings.heightmap_bit_depth) * max_deform;
}



[numthreads(8,8,1)]
void main(uint3 tid : SV_DispatchThreadID)
{
    uint2 hm_sz; input_heightmap.GetDimensions(hm_sz.x, hm_sz.y);

    if(input_ocean_mask[tid.xy] != 0)
        return;

    float ZFactor = 1.0f;

    float a = read_height(tid.xy, int2(1, 1), hm_sz);
    float b = read_height(tid.xy, int2(0, -1), hm_sz);
    float c = read_height(tid.xy, int2(1, -1), hm_sz);
    float d = read_height(tid.xy, int2(-1, 0), hm_sz);
    float f = read_height(tid.xy, int2(1, 0), hm_sz);
    float g = read_height(tid.xy, int2(-1, 1), hm_sz);
    float h = read_height(tid.xy, int2(0, 1), hm_sz);
    float i = read_height(tid.xy, int2(1, 1), hm_sz);

    //Cellsize needs to be the same scale as the X/Y distance
    //This calculation does not take into account projection warping at all
    float planet_circ_m = PI * 2 * jobSettings.planet_radius;
    float cellsize_m = planet_circ_m / (hm_sz.x * jobSettings.render_scale * 2);

    float dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * cellsize_m);
    float dzdy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * cellsize_m);
    float aspect = 0.0;

    float slope = atan(ZFactor * sqrt(dzdx * dzdx + dzdy * dzdy));

    if (dzdx != 0)
    {
        aspect = atan2(dzdy, -dzdx);
        if (aspect < 0)
            aspect += PI * 2;
    }
    else
    {
        if (dzdy > 0)
            aspect = PI / 2;
        else if (dzdy < 0)
            aspect = (PI * 2) - (PI / 2);
    }

    //Normalize slope to +/- 1
    slope = min(PI, max(-PI, slope)) / PI;

    int hillshade_amount = 255 * (
        (cos(jobSettings.hillshade_zenith) * cos(slope)) +
        (sin(jobSettings.hillshade_zenith) * sin(slope) * cos(jobSettings.hillshade_azimuth - aspect)));
    //Tone down hillshade, and make centered around 0
    hillshade_amount = (hillshade_amount - 127) / 4;

    uint3 final_color = output_color[tid.xy].xyz;

    final_color.x = max(0, min(255, final_color.x + hillshade_amount));
    final_color.y = max(0, min(255, final_color.y + hillshade_amount));
    final_color.z = max(0, min(255, final_color.z + hillshade_amount));

	output_color[tid.xy].xyz = final_color;
}