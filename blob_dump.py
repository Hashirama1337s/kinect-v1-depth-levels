"""Calibration-blob dump (2026-09-26; stage 1 of the calibration-record decode). INuiSensor::NuiGetCoordinateMapper (vtable 28,
from NuiSensor.h) -> INuiCoordinateMapper::GetColorToDepthRelationalParameters (vtable 3) returns an opaque per-sensor parameter blob
(asked about on MSDN in 2013, never documented). Sealed reading (fixed before running): DECODED if the blob holds float32
7.5, 120.0 and 0.1042 (PrimeSense zero-plane constants) plus 2.3 or 2.4, or libfreenect's 118-byte reg_info block; otherwise it is
Microsoft's own format -> record size and structure. Saves calib_blob.bin locally (device calibration: no personal data).
usage: python blob_dump.py"""
import os, sys, struct
import ctypes as C
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from sensor import Sensor, _F_void_l
V_GET_MAPPER, M_RELEASE, M_GET_PARAMS = 28, 2, 3
_F_getmapper = C.WINFUNCTYPE(C.c_long, C.c_void_p, C.POINTER(C.c_void_p))
_F_params = C.WINFUNCTYPE(C.c_long, C.c_void_p, C.POINTER(C.c_ulong), C.POINTER(C.c_void_p))
_F_release = C.WINFUNCTYPE(C.c_ulong, C.c_void_p)
from nui import _vtbl
s = Sensor(); print("verify:", s.verify())
s.initialize(0x00000020 | 0x00000002)                     # INIT_DEPTH | INIT_COLOR
try:
    m = C.c_void_p(); hr = s._call(V_GET_MAPPER, _F_getmapper)(s.p, C.byref(m)); print(f"NuiGetCoordinateMapper hr=0x{hr & 0xFFFFFFFF:08X} mapper={m.value}")
    n = C.c_ulong(0); data = C.c_void_p(); hr = _vtbl(m, M_GET_PARAMS, _F_params)(m, C.byref(n), C.byref(data))
    print(f"GetColorToDepthRelationalParameters hr=0x{hr & 0xFFFFFFFF:08X} bytes={n.value}")
    blob = C.string_at(data, n.value) if n.value else b""
    open(os.path.join(HERE, 'calib_blob.bin'), 'wb').write(blob)
    print("head:", blob[:64].hex(" "))
    targets = {7.5: "emitter-dcmos cm", 120.0: "zero-plane dist", 0.1042: "zero-plane px size", 2.3: "2.3", 2.4: "2.4", 75.0: "baseline mm",
               1200.0: "ref dist mm", 285.63: "SDK nominal f@320", 571.26: "f@640", 575.82: "f from consts", 531.15: "SDK color f@640 x?"}
    found = []
    for off in range(0, max(0, len(blob) - 3)):
        v = struct.unpack_from('<f', blob, off)[0]
        for t, name in targets.items():
            if abs(v - t) <= 1e-4 * max(1, abs(t)): found.append((off, 'f32', v, name))
    for off in range(0, max(0, len(blob) - 7)):
        v = struct.unpack_from('<d', blob, off)[0]
        for t, name in targets.items():
            if abs(v - t) <= 1e-6 * max(1, abs(t)): found.append((off, 'f64', v, name))
    for f in found: print("  match at offset %d (%s): %r = %s" % f)
    f32 = [(o, struct.unpack_from('<f', blob, o)[0]) for o in range(0, len(blob) - 3, 4)]
    plaus = [(o, round(v, 6)) for o, v in f32 if 1e-3 < abs(v) < 1e5]
    print(f"aligned float32 words in (1e-3, 1e5): {len(plaus)} of {len(f32)}; first 40: {plaus[:40]}")
    names = {x[3] for x in found}
    dec = {"emitter-dcmos cm", "zero-plane dist", "zero-plane px size"} <= names and ({"2.3", "2.4"} & names)
    print("STAGE-1 READING:", "DECODED (PrimeSense constants present)" if dec else "NOT PrimeSense constants in plain float32 -> Microsoft format (see size/structure)")
    _vtbl(m, M_RELEASE, _F_release)(m)
finally:
    s.shutdown(); s.release()
