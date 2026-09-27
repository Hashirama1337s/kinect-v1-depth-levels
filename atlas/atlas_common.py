"""atlas_common.py -- shared helpers for the depth-pipeline atlas probes (Kinect v1, SDK 1.8).

Nothing here touches hardware on import. Every probe script:
  - lowers its own process priority to BELOW_NORMAL (no system change; this process only),
  - streams for at most a few seconds,
  - never writes to the device, the driver or the registry.
Vtable indices below are read from the SDK's own NuiSensor.h (INuiSensorVtbl, INuiCoordinateMapperVtbl), not guessed.
"""
import os, sys, ctypes as C
from ctypes import wintypes as W
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))           # nui.py / sensor.py live one folder up
import nui                                             # noqa: E402
from nui import NUI_IMAGE_FRAME, NUI_LOCKED_RECT, _vtbl, _LockRect, _UnlockRect, _VT_LOCKRECT, _VT_UNLOCKRECT  # noqa: E402

# ---- header constants (NuiImageCamera.h, NuiApi.h) -------------------------------------------
PLAYER_SHIFT = 3
DEPTH_MIN_MM, DEPTH_MAX_MM = 800, 4000                 # NUI_IMAGE_DEPTH_MINIMUM / _MAXIMUM >> 3
TOO_FAR_13, UNKNOWN_13 = 0x0FFF, 0x1FFF                # NUI_IMAGE_DEPTH_TOO_FAR_VALUE / _UNKNOWN_VALUE >> 3
FLAG_SUPPRESS_NO_FRAME_DATA = 0x00010000
FLAG_ENABLE_NEAR_MODE = 0x00020000
FLAG_DISTINCT_OVERFLOW = 0x00040000
F_NOMINAL_320 = 285.63                                 # NUI_CAMERA_DEPTH_NOMINAL_FOCAL_LENGTH_IN_PIXELS
INV_F_NOMINAL_320 = 3.501e-3                           # NUI_CAMERA_DEPTH_NOMINAL_INVERSE_FOCAL_LENGTH_IN_PIXELS

# ---- INuiSensor vtable (NuiSensor.h) ----------------------------------------------------------
V_GET_FRAME_FLAGS = 8
V_GET_MAPPER = 28
V_DEPTH_PIXEL_TEXTURE = 29
V_SET_DEPTH_FILTER, V_GET_DEPTH_FILTER, V_GET_DEPTH_FILTER_TS = 34, 35, 36
# ---- INuiCoordinateMapper vtable ---------------------------------------------------------------
M_RELEASE = 2
M_DEPTH_FRAME_TO_SKELETON = 8
M_DEPTH_POINT_TO_SKELETON = 10
M_SKELETON_POINT_TO_DEPTH = 12


class NUI_DEPTH_IMAGE_POINT(C.Structure):
    _fields_ = [("x", C.c_long), ("y", C.c_long), ("depth", C.c_long), ("reserved", C.c_long)]


class NUI_DEPTH_IMAGE_PIXEL(C.Structure):
    _fields_ = [("playerIndex", C.c_ushort), ("depth", C.c_ushort)]


assert C.sizeof(NUI_DEPTH_IMAGE_POINT) == 16 and C.sizeof(NUI_DEPTH_IMAGE_PIXEL) == 4


def below_normal_priority():
    k32 = C.windll.kernel32
    k32.GetCurrentProcess.restype = W.HANDLE
    k32.SetPriorityClass.argtypes = [W.HANDLE, W.DWORD]
    ok = k32.SetPriorityClass(k32.GetCurrentProcess(), 0x00004000)   # BELOW_NORMAL_PRIORITY_CLASS
    return bool(ok)


def hr_hex(hr):
    return "0x%08X" % (hr & 0xFFFFFFFF)


# ---- the PrimeSense shift-to-depth lattice the SDK uses (phase 0, floor), see ../lattice_closure.py ----
D_LATTICE = 0.1042 / 36000.0


def lattice_levels(lo_mm=300, hi_mm=400000):   # 2026-09-27: default cap was 20000 mm -> flagged 12 genuine rungs > 20 m as
                                               # off-table in extended_depth_probe E4 (94.0 %; 98.2 % with the full table)
    n = np.arange(-2000, int((1 / 1200) / D_LATTICE))
    z = 1.0 / (1 / 1200 - n * D_LATTICE)
    mm = np.floor(z).astype(np.int64)
    return np.unique(mm[(mm >= lo_mm) & (mm <= hi_mm)])


def on_lattice(values, lo_mm=300, hi_mm=400000):
    lv = set(lattice_levels(lo_mm, hi_mm).tolist())
    return np.array([int(v) in lv for v in values], dtype=bool)


# ---- flat-API frame grab that keeps the frame metadata -------------------------------------------
nui._dll.NuiImageStreamGetImageFrameFlags.argtypes = [W.HANDLE, C.POINTER(C.c_uint32)]
nui._dll.NuiImageStreamSetImageFrameFlags.argtypes = [W.HANDLE, C.c_uint32]


def flat_get_flags(h):
    v = C.c_uint32(0)
    hr = nui._dll.NuiImageStreamGetImageFrameFlags(h, C.byref(v))
    return hr, v.value


def flat_set_flags(h, flags):
    return nui._dll.NuiImageStreamSetImageFrameFlags(h, C.c_uint32(flags))


def flat_grab(h, w, hgt, timeout_ms=2000):
    """Return (uint16 array, metadata dict). Array is a copy."""
    pf = C.POINTER(NUI_IMAGE_FRAME)()
    hr = nui._dll.NuiImageStreamGetNextFrame(h, C.c_uint32(timeout_ms), C.byref(pf))
    if hr < 0:
        raise OSError("NuiImageStreamGetNextFrame " + hr_hex(hr))
    fr = pf.contents
    meta = dict(frame=fr.dwFrameNumber, type=fr.eImageType, res=fr.eResolution, flags=fr.dwFrameFlags,
                zoom=fr.eDigitalZoom, cx=fr.lCenterX, cy=fr.lCenterY)
    try:
        tex = fr.pFrameTexture
        if not tex:
            raise OSError("null texture")
        lr = NUI_LOCKED_RECT()
        r = _vtbl(tex, _VT_LOCKRECT, _LockRect)(tex, 0, C.byref(lr), None, 0)
        if r < 0:
            raise OSError("LockRect " + hr_hex(r))
        try:
            arr = np.frombuffer(C.string_at(lr.pBits, lr.size), dtype=np.uint16).reshape(hgt, w).copy()
        finally:
            _vtbl(tex, _VT_UNLOCKRECT, _UnlockRect)(tex, 0)
    finally:
        nui._dll.NuiImageStreamReleaseFrame(h, pf)
    return arr, meta
