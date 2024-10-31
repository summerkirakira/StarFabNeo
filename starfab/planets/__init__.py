
try:
    from compushady import Texture2D, Compute, Resource, HEAP_UPLOAD, Buffer, Texture3D, HEAP_READBACK
    from compushady.formats import R8G8B8A8_UINT, R8_UINT, R16_UINT, R32_SINT
    from compushady.shaders import hlsl
    HAS_COMPUSHADY = True
except ImportError as e:
    HAS_COMPUSHADY = False
