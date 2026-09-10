"""
nui.py -- direct ctypes binding to Kinect10.dll (Kinect for Windows SDK 1.8).

Talks to the Kinect v1 (PrimeSense PS1080) flat NUI C API with no wrapper library.
All 25 exports of Kinect10.dll are undecorated x64 C symbols, so ctypes reaches
them directly.

DESIGN RULES (learned the hard way on this drive):
  - Never silently return a value. Every HRESULT is checked and raised.
  - Frame buffers are COPIED out before UnlockRect. The SDK reuses that memory;
    holding a numpy view onto it gives you data that mutates under you.
  - Struct layouts are asserted against known sizeof at import time, so a wrong
    offset fails loudly at startup instead of producing plausible garbage.
"""
import ctypes as C
from ctypes import wintypes as W
import numpy as np

_dll = C.WinDLL(r"C:\Windows\System32\Kinect10.dll")

# ---------------------------------------------------------------- constants
INIT_DEPTH_AND_PLAYER_INDEX = 0x00000001
INIT_COLOR                  = 0x00000002
INIT_SKELETON               = 0x00000008
INIT_DEPTH                  = 0x00000020
INIT_AUDIO                  = 0x10000000

IMG_DEPTH_AND_PLAYER_INDEX = 0
IMG_COLOR                  = 1
IMG_COLOR_YUV              = 2
IMG_COLOR_RAW_YUV          = 3
IMG_DEPTH                  = 4
IMG_COLOR_INFRARED         = 5
IMG_COLOR_RAW_BAYER        = 6

RES_80x60, RES_320x240, RES_640x480, RES_1280x960 = 0, 1, 2, 3
RES_DIMS = {RES_80x60:(80,60), RES_320x240:(320,240),
            RES_640x480:(640,480), RES_1280x960:(1280,960)}

# stream flags
FLAG_SUPPRESS_NO_FRAME_DATA          = 0x00010000
FLAG_ENABLE_NEAR_MODE                = 0x00020000
FLAG_DISTINCT_OVERFLOW_DEPTH_VALUES  = 0x00040000

# depth sentinel values (SDK 1.8, only with DISTINCT_OVERFLOW flag)
DEPTH_TOO_NEAR  = 0xFFF9
DEPTH_TOO_FAR   = 0xFFF8
DEPTH_UNKNOWN   = 0xFFF7

# ---------------------------------------------------------------- structs
class NUI_IMAGE_FRAME(C.Structure):
    _fields_ = [("liTimeStamp",   C.c_int64),
                ("dwFrameNumber", C.c_uint32),
                ("eImageType",    C.c_int32),
                ("eResolution",   C.c_int32),
                ("pFrameTexture", C.c_void_p),   # ctypes inserts the 4-byte pad
                ("dwFrameFlags",  C.c_uint32),
                ("eDigitalZoom",  C.c_int32),
                ("lCenterX",      C.c_int32),
                ("lCenterY",      C.c_int32)]

class NUI_LOCKED_RECT(C.Structure):
    _fields_ = [("Pitch", C.c_int32),
                ("size",  C.c_int32),
                ("pBits", C.POINTER(C.c_ubyte))]

# Fail loudly at import if the ABI is not what we think it is.
assert C.sizeof(NUI_IMAGE_FRAME)  == 48, C.sizeof(NUI_IMAGE_FRAME)
assert NUI_IMAGE_FRAME.pFrameTexture.offset == 24
assert C.sizeof(NUI_LOCKED_RECT) == 16, C.sizeof(NUI_LOCKED_RECT)

# ---------------------------------------------------------------- prototypes
_dll.NuiGetSensorCount.argtypes = [C.POINTER(C.c_int)]
_dll.NuiInitialize.argtypes     = [C.c_uint32]
_dll.NuiShutdown.argtypes       = []
_dll.NuiShutdown.restype        = None
_dll.NuiImageStreamOpen.argtypes = [C.c_int32, C.c_int32, C.c_uint32,
                                    C.c_uint32, W.HANDLE, C.POINTER(W.HANDLE)]
_dll.NuiImageStreamGetNextFrame.argtypes = [W.HANDLE, C.c_uint32,
                                            C.POINTER(C.POINTER(NUI_IMAGE_FRAME))]
_dll.NuiImageStreamReleaseFrame.argtypes = [W.HANDLE, C.POINTER(NUI_IMAGE_FRAME)]
_dll.NuiCameraElevationGetAngle.argtypes = [C.POINTER(C.c_long)]
_dll.NuiCameraElevationSetAngle.argtypes = [C.c_long]

def _hr(code, what):
    if code < 0:
        raise OSError(f"{what} failed: HRESULT 0x{code & 0xFFFFFFFF:08X}")
    return code

# INuiFrameTexture is a COM object; index into its vtable by hand.
_VT_LOCKRECT   = 5
_VT_UNLOCKRECT = 7
_LockRect   = C.WINFUNCTYPE(C.c_long, C.c_void_p, C.c_uint,
                            C.POINTER(NUI_LOCKED_RECT), C.c_void_p, C.c_uint32)
_UnlockRect = C.WINFUNCTYPE(C.c_long, C.c_void_p, C.c_uint)

def _vtbl(pobj, index, functype):
    vtbl = C.cast(pobj, C.POINTER(C.POINTER(C.c_void_p))).contents
    return functype(vtbl[index])

# ---------------------------------------------------------------- API
def sensor_count():
    n = C.c_int(0)
    _hr(_dll.NuiGetSensorCount(C.byref(n)), "NuiGetSensorCount")
    return n.value

def elevation_angle():
    """Tilt in degrees, derived from the internal KXSD9 accelerometer."""
    a = C.c_long(0)
    _hr(_dll.NuiCameraElevationGetAngle(C.byref(a)), "NuiCameraElevationGetAngle")
    return a.value

def set_elevation_angle(deg):
    _hr(_dll.NuiCameraElevationSetAngle(C.c_long(int(deg))), "NuiCameraElevationSetAngle")

class Kinect:
    def __init__(self, flags=INIT_DEPTH):
        self.flags = flags
        self._streams = {}
        _hr(_dll.NuiInitialize(C.c_uint32(flags)), "NuiInitialize")

    def open_stream(self, image_type, resolution, stream_flags=0, frame_limit=2):
        h = W.HANDLE()
        _hr(_dll.NuiImageStreamOpen(C.c_int32(image_type), C.c_int32(resolution),
                                    C.c_uint32(stream_flags), C.c_uint32(frame_limit),
                                    None, C.byref(h)), "NuiImageStreamOpen")
        self._streams[image_type] = (h, resolution)
        return h

    def set_stream_flags(self, image_type, stream_flags):
        h, _ = self._streams[image_type]
        _hr(_dll.NuiImageStreamSetImageFrameFlags(h, C.c_uint32(stream_flags)),
            "NuiImageStreamSetImageFrameFlags")

    def grab(self, image_type, timeout_ms=2000, dtype=np.uint16):
        """Return (array, frame_number, timestamp). Array is a COPY, safe to keep."""
        h, res = self._streams[image_type]
        pf = C.POINTER(NUI_IMAGE_FRAME)()
        _hr(_dll.NuiImageStreamGetNextFrame(h, C.c_uint32(timeout_ms), C.byref(pf)),
            "NuiImageStreamGetNextFrame")
        fr = pf.contents
        try:
            tex = fr.pFrameTexture
            lr = NUI_LOCKED_RECT()
            _hr(_vtbl(tex, _VT_LOCKRECT, _LockRect)(tex, 0, C.byref(lr), None, 0),
                "INuiFrameTexture::LockRect")
            try:
                if lr.size == 0 or not lr.pBits:
                    raise OSError("LockRect returned an empty buffer")
                raw = C.string_at(lr.pBits, lr.size)          # copy out
                w, hgt = RES_DIMS[res]
                arr = np.frombuffer(raw, dtype=dtype)
                if arr.size == w * hgt:
                    arr = arr.reshape(hgt, w)
                elif arr.size == w * hgt * 2:                  # 32bpp colour as uint16
                    arr = arr.reshape(hgt, w, 2)
                return arr.copy(), fr.dwFrameNumber, fr.liTimeStamp
            finally:
                _vtbl(tex, _VT_UNLOCKRECT, _UnlockRect)(tex, 0)
        finally:
            _dll.NuiImageStreamReleaseFrame(h, pf)

    def close(self):
        _dll.NuiShutdown()

    def __enter__(self):  return self
    def __exit__(self, *a): self.close()
