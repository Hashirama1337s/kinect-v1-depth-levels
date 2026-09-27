"""depth_filter_probe.py -- is there a depth filter installed by default? (read-only getters; ~2 s of streaming)

Public: NuiSensor.h declares INuiDepthFilter (IID 1D7C07DD-2304-49BB-9B7F-2FDC6E00C1B2) with one method
ProcessFrame(LARGE_INTEGER liTimeStamp, UINT width, UINT height, NUI_DEPTH_IMAGE_PIXEL *pixels, BOOL *pFrameModified), and
INuiSensor slots 34/35/36 NuiSetDepthFilter / NuiGetDepthFilter / NuiGetDepthFilterForTimeStamp. The SDK 1.8 documentation
says of all three only 'Reserved for future use' (parameters 'Not used', return value 'Not used').
Not public: whether the 1.8 runtime implements them, whether a filter is active by default, and what it would do.

RULES (fixed before running). Only the two GETTERS are called; NuiSetDepthFilter is NOT called here.
  G1 : NuiGetDepthFilter after NuiInitialize(DEPTH), before and after opening a depth stream:
       S_OK + NULL -> NO DEFAULT FILTER ; S_OK + non-NULL -> DEFAULT FILTER PRESENT (then QueryInterface for IID_INuiDepthFilter
       and report) ; E_NOTIMPL (0x80004001) or other failure -> NOT IMPLEMENTED / report HRESULT.
  G2 : NuiGetDepthFilterForTimeStamp with the timestamp of a real frame and with 0: same classification.
"""
import time, ctypes as C
from ctypes import wintypes as W
from atlas_common import (below_normal_priority, hr_hex, _vtbl, NUI_IMAGE_FRAME, V_GET_DEPTH_FILTER, V_GET_DEPTH_FILTER_TS)
from sensor import Sensor, V_STREAM_NEXT, V_STREAM_RELEASE, _F_next, _F_relframe

_F_get = C.WINFUNCTYPE(C.c_long, C.c_void_p, C.POINTER(C.c_void_p))
_F_get_ts = C.WINFUNCTYPE(C.c_long, C.c_void_p, C.c_int64, C.POINTER(C.c_void_p))   # LARGE_INTEGER passed by value (x64: 8-byte int)
_F_rel = C.WINFUNCTYPE(C.c_ulong, C.c_void_p)


class GUID(C.Structure):
    _fields_ = [("a", C.c_uint32), ("b", C.c_uint16), ("c", C.c_uint16), ("d", C.c_ubyte * 8)]


IID_INuiDepthFilter = GUID(0x1d7c07dd, 0x2304, 0x49bb, (C.c_ubyte * 8)(0x9b, 0x7f, 0x2f, 0xdc, 0x6e, 0x00, 0xc1, 0xb2))
_F_qi = C.WINFUNCTYPE(C.c_long, C.c_void_p, C.POINTER(GUID), C.POINTER(C.c_void_p))


def classify(label, hr, ptr):
    if hr < 0:
        out = f"FAILED {hr_hex(hr)}" + (" (E_NOTIMPL -> NOT IMPLEMENTED)" if (hr & 0xFFFFFFFF) == 0x80004001 else "")
    elif not ptr.value:
        out = f"{hr_hex(hr)} + NULL -> NO DEFAULT FILTER"
    else:
        q = C.c_void_p(); r = _vtbl(ptr, 0, _F_qi)(ptr, C.byref(IID_INuiDepthFilter), C.byref(q))
        out = f"{hr_hex(hr)} + {ptr.value:#x} -> DEFAULT FILTER PRESENT (QI INuiDepthFilter {hr_hex(r)})"
        if q.value:
            _vtbl(q, 2, _F_rel)(q)
        _vtbl(ptr, 2, _F_rel)(ptr)
    print(f"{label}: {out}")
    return out


def main():
    print("below-normal priority:", below_normal_priority())
    s = Sensor(); print("verify:", s.verify())
    s.initialize(0x00000020)
    try:
        p = C.c_void_p(); hr = s._call(V_GET_DEPTH_FILTER, _F_get)(s.p, C.byref(p)); classify("G1 before stream", hr, p)
        h = s.open_stream(4, 2); time.sleep(1.0)
        fr = NUI_IMAGE_FRAME(); r = s._call(V_STREAM_NEXT, _F_next)(s.p, h, C.c_uint32(3000), C.byref(fr))
        ts = fr.liTimeStamp if r >= 0 else 0
        if r >= 0:
            s._call(V_STREAM_RELEASE, _F_relframe)(s.p, h, C.byref(fr))
        p = C.c_void_p(); hr = s._call(V_GET_DEPTH_FILTER, _F_get)(s.p, C.byref(p)); classify("G1 with depth stream open", hr, p)
        for t in (ts, 0):
            p = C.c_void_p(); hr = s._call(V_GET_DEPTH_FILTER_TS, _F_get_ts)(s.p, C.c_int64(t), C.byref(p))
            classify(f"G2 for-timestamp ({'frame' if t else 'zero'})", hr, p)
    finally:
        s.shutdown(); s.release()


if __name__ == '__main__':
    main()
