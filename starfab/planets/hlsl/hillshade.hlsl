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

[numthreads(8,8,1)]
void main(uint3 tid : SV_DispatchThreadID)
{
    uint4 out_color = uint4(input_ocean_mask[tid.xy], 0, 0, 255);

    if(input_ocean_mask[tid.xy] != 0)
        return;

	//output_color[tid.xy] = out_color;
}