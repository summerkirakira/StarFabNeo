Texture2D<uint4> bedrock : register(t0);
Texture2D<uint4> surface : register(t1);

Texture2D<uint4> planet_climate : register(t2);
Texture2D<uint> planet_offsets : register(t3);
Texture2D<min16uint> planet_heightmap : register(t4);

RWTexture2D<uint4> destination : register(u0);

[numthreads(8,8,1)]
void main(uint3 tid : SV_DispatchThreadID)
{
	uint width;
	uint height;
	destination.GetDimensions(width, height);

	uint clim_w, clim_h;
	planet_climate.GetDimensions(clim_w, clim_h);
	uint2 clim_sz = uint2(clim_w, clim_h);

	float2 normalized_position = tid.xy / float2(width, height);

	uint4 local_climate = planet_climate[normalized_position * clim_sz];
	local_climate = uint4(local_climate.xy / 2, local_climate.z / 16, 0);

	uint4 surface_color = surface[local_climate.yx];
	uint4 read = uint4(0, 0, 0, 255);
	//read.xy = planetClimate[index].climate_th;
	//read.z = 0;

	read.xyz = surface_color.xyz;

	destination[tid.xy] = read;
}