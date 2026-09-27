"""Calibration blob, stage 2 (2026-09-27): is the SDK's depth->colour registration PrimeSense's, rebuilt from this unit's reg_info?

Stage 1 (blob_dump.py) decoded the 12 604-byte blob returned by INuiCoordinateMapper::GetColorToDepthRelationalParameters:
a 118-byte PrimeSense registration block (2-byte prefix + 29 int32 in libfreenect's freenect_reg_info order) at byte 12314, float32
120.0 (zero-plane distance) at 12532, float32 0.1042 (zero-plane pixel size) at 12536, int32 const_shift 200 at 12600.

This script
  1. ports libfreenect's src/registration.c table construction to Python, faithfully (freenect_create_dxdy_tables,
     freenect_init_registration_table, freenect_init_depth_to_rgb, the per-pixel lookup of freenect_apply_registration),
     fed with this unit's reg_info / 120 / 0.1042 / 200. Values the blob does not carry are libfreenect's own:
     dcmos_rcmos_dist = 2.4 (libfreenect hard-codes 2.4 over the 2.3 the device reports; "FIXME: OpenNI seems to use 2.4"),
     reg_pad_info.start_lines = 0 (libfreenect reads it from the device; not in the blob; 0 assumed), DEPTH_X/Y_OFFSET = 1,
     DEPTH_MIRROR_X = 0. dcmos_emitter_dist 7.5 and the raw->mm table are NOT needed: the SDK hands over millimetres.
  2. maps synthetic flat depth frames (every pixel = Z mm, Z in 800..4000) with the SDK's own
     INuiCoordinateMapper::MapDepthFrameToColorFrame (live sensor mapper; depth 640x480 -> COLOR 640x480);
  3. compares, pixel by pixel. PASS if >= 99 % of valid pixels agree within +-1 px in x and y at every distance.
     Exploratory (not the verdict): variants x-mirrored and 2.3 vs 2.4; a 1 mm depth sweep (300..9000 mm) of
     MapDepthPointToColorPoint at 5 pixels, which exposes the SDK's depth->shift function step by step; and a post-hoc
     model of the SDK's arithmetic fitted from that sweep.

Every vtable index and signature below is taken from the SDK's NuiSensor.h and re-checked against the header text at run time
(check_header()); the struct sizes are asserted. sensor.verify() runs before any hardware call.
usage: python decode_stage2.py            (writes stage2_sdk_maps.npz and stage2_results.json next to this script)
       python decode_stage2.py --offline  (re-analyse the saved SDK output; no sensor needed)
"""
import os, sys, re, json, struct
import ctypes as C
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def below_normal_priority():
    """Heavy work runs at BELOW_NORMAL_PRIORITY_CLASS (0x4000); child processes inherit it."""
    try:
        k = C.windll.kernel32
        k.SetPriorityClass(k.GetCurrentProcess(), 0x4000)
    except Exception:
        pass


# ============================================================ SDK structs (NuiSensor.h / NuiImageCamera.h)
class NUI_DEPTH_IMAGE_PIXEL(C.Structure):      # { USHORT playerIndex; USHORT depth; }  depth in mm (not << 3)
    _fields_ = [("playerIndex", C.c_ushort), ("depth", C.c_ushort)]


class NUI_DEPTH_IMAGE_POINT(C.Structure):      # { LONG x; LONG y; LONG depth; LONG reserved; }
    _fields_ = [("x", C.c_int32), ("y", C.c_int32), ("depth", C.c_int32), ("reserved", C.c_int32)]


class NUI_COLOR_IMAGE_POINT(C.Structure):      # { LONG x; LONG y; }
    _fields_ = [("x", C.c_int32), ("y", C.c_int32)]


class Vector4(C.Structure):                    # { FLOAT x, y, z, w; }
    _fields_ = [("x", C.c_float), ("y", C.c_float), ("z", C.c_float), ("w", C.c_float)]


assert C.sizeof(NUI_DEPTH_IMAGE_PIXEL) == 4
assert C.sizeof(NUI_DEPTH_IMAGE_POINT) == 16
assert C.sizeof(NUI_COLOR_IMAGE_POINT) == 8
assert C.sizeof(Vector4) == 16

# enums (NuiSensor.h): NUI_IMAGE_TYPE_COLOR = 1, NUI_IMAGE_RESOLUTION_640x480 = 2
IMG_COLOR, RES_640 = 1, 2
W, H = 640, 480

# INuiSensorVtbl / INuiCoordinateMapperVtbl slots (checked against the header text by check_header)
S_GET_MAPPER = 28
M_RELEASE, M_GET_PARAMS = 2, 3
M_DEPTHFRAME_TO_COLORFRAME, M_DEPTHFRAME_TO_SKELFRAME = 7, 8
M_DEPTHPT_TO_COLORPT, M_DEPTHPT_TO_SKELPT = 9, 10
EXPECTED = {"INuiSensorVtbl": {S_GET_MAPPER: "NuiGetCoordinateMapper"},
            "INuiCoordinateMapperVtbl": {M_RELEASE: "Release", M_GET_PARAMS: "GetColorToDepthRelationalParameters",
                                         M_DEPTHFRAME_TO_COLORFRAME: "MapDepthFrameToColorFrame",
                                         M_DEPTHFRAME_TO_SKELFRAME: "MapDepthFrameToSkeletonFrame",
                                         M_DEPTHPT_TO_COLORPT: "MapDepthPointToColorPoint",
                                         M_DEPTHPT_TO_SKELPT: "MapDepthPointToSkeletonPoint"}}

_F_getmapper = C.WINFUNCTYPE(C.c_long, C.c_void_p, C.POINTER(C.c_void_p))
_F_params = C.WINFUNCTYPE(C.c_long, C.c_void_p, C.POINTER(C.c_ulong), C.POINTER(C.c_void_p))
_F_release = C.WINFUNCTYPE(C.c_ulong, C.c_void_p)
# MapDepthFrameToColorFrame(This, eDepthResolution, cDepthPixels, pDepthPixels, eColorType, eColorResolution, cColorPoints, pColorPoints)
_F_df2cf = C.WINFUNCTYPE(C.c_long, C.c_void_p, C.c_int32, C.c_uint32, C.POINTER(NUI_DEPTH_IMAGE_PIXEL),
                         C.c_int32, C.c_int32, C.c_uint32, C.POINTER(NUI_COLOR_IMAGE_POINT))
# MapDepthFrameToSkeletonFrame(This, eDepthResolution, cDepthPixels, pDepthPixels, cSkeletonPoints, pSkeletonPoints)
_F_df2sf = C.WINFUNCTYPE(C.c_long, C.c_void_p, C.c_int32, C.c_uint32, C.POINTER(NUI_DEPTH_IMAGE_PIXEL),
                         C.c_uint32, C.POINTER(Vector4))
# MapDepthPointToColorPoint(This, eDepthResolution, pDepthPoint, eColorType, eColorResolution, pColorPoint)
_F_dp2cp = C.WINFUNCTYPE(C.c_long, C.c_void_p, C.c_int32, C.POINTER(NUI_DEPTH_IMAGE_POINT), C.c_int32, C.c_int32,
                         C.POINTER(NUI_COLOR_IMAGE_POINT))
# MapDepthPointToSkeletonPoint(This, eDepthResolution, pDepthPoint, pSkeletonPoint)
_F_dp2sp = C.WINFUNCTYPE(C.c_long, C.c_void_p, C.c_int32, C.POINTER(NUI_DEPTH_IMAGE_POINT), C.POINTER(Vector4))


def sdk_header_path():
    base = os.environ.get("KINECTSDK10_DIR") or os.path.join(os.environ.get("ProgramFiles", ""), "Microsoft SDKs", "Kinect", "v1.8")
    return os.path.join(base, "inc", "NuiSensor.h")


def check_header():
    """Re-derive every vtable index used here from the header's C vtable structs; refuse to run on a mismatch."""
    p = sdk_header_path()
    if not os.path.exists(p):
        raise RuntimeError("NuiSensor.h not found (%s); refusing to call vtable slots unchecked" % p)
    t = open(p, encoding="latin-1").read()
    for struct_name, want in EXPECTED.items():
        i = t.index("typedef struct " + struct_name)
        j = t.index("} " + struct_name + ";", i)
        fns = re.findall(r"\(\s*STDMETHODCALLTYPE\s*\*(\w+)\s*\)", t[i:j])
        for idx, name in want.items():
            if fns[idx] != name:
                raise RuntimeError("header check: %s[%d] is %s, expected %s" % (struct_name, idx, fns[idx], name))
    # NuiCreateCoordinateMapperFromParameters(ULONG dataByteCount, void* pData, INuiCoordinateMapper **ppCoordinateMapper)
    m = re.search(r"NuiCreateCoordinateMapperFromParameters\(\s*_In_ ULONG dataByteCount,\s*_In_ void\* pData,\s*"
                  r"_Out_ INuiCoordinateMapper \*\*ppCoordinateMapper\)", t)
    if not m:
        raise RuntimeError("header check: NuiCreateCoordinateMapperFromParameters prototype not as expected")
    return True


def _vtbl(pobj, index, functype):
    vtbl = C.cast(pobj, C.POINTER(C.POINTER(C.c_void_p))).contents
    return functype(vtbl[index])


def hr_ok(hr, what):
    if hr < 0:
        raise OSError("%s failed: HRESULT 0x%08X" % (what, hr & 0xFFFFFFFF))
    return hr


class Mapper:
    """INuiCoordinateMapper* wrapper. Keeps the parameter buffer alive for mappers built from parameters."""

    def __init__(self, p, keepalive=None):
        self.p = p
        self._keep = keepalive

    def params(self):
        n = C.c_ulong(0); d = C.c_void_p()
        hr_ok(_vtbl(self.p, M_GET_PARAMS, _F_params)(self.p, C.byref(n), C.byref(d)), "GetColorToDepthRelationalParameters")
        return C.string_at(d, n.value) if n.value else b""

    def depth_frame_to_color(self, depth_mm):
        """depth_mm: (480,640) uint16 millimetres -> (480,640,2) int32 colour (x, y) and the HRESULT."""
        pix = np.zeros((H * W, 2), np.uint16)
        pix[:, 1] = np.asarray(depth_mm, np.uint16).ravel()
        out = np.full((H * W, 2), -99999, np.int32)
        hr = _vtbl(self.p, M_DEPTHFRAME_TO_COLORFRAME, _F_df2cf)(
            self.p, RES_640, C.c_uint32(H * W), pix.ctypes.data_as(C.POINTER(NUI_DEPTH_IMAGE_PIXEL)),
            IMG_COLOR, RES_640, C.c_uint32(H * W), out.ctypes.data_as(C.POINTER(NUI_COLOR_IMAGE_POINT)))
        hr_ok(hr, "MapDepthFrameToColorFrame")
        return out.reshape(H, W, 2), hr

    def depth_frame_to_skeleton(self, depth_mm):
        pix = np.zeros((H * W, 2), np.uint16)
        pix[:, 1] = np.asarray(depth_mm, np.uint16).ravel()
        out = np.full((H * W, 4), np.nan, np.float32)
        hr = _vtbl(self.p, M_DEPTHFRAME_TO_SKELFRAME, _F_df2sf)(
            self.p, RES_640, C.c_uint32(H * W), pix.ctypes.data_as(C.POINTER(NUI_DEPTH_IMAGE_PIXEL)),
            C.c_uint32(H * W), out.ctypes.data_as(C.POINTER(Vector4)))
        hr_ok(hr, "MapDepthFrameToSkeletonFrame")
        return out.reshape(H, W, 4), hr

    def depth_point_to_color(self, x, y, depth):
        dp = NUI_DEPTH_IMAGE_POINT(int(x), int(y), int(depth), 0)
        cp = NUI_COLOR_IMAGE_POINT(-99999, -99999)
        hr = _vtbl(self.p, M_DEPTHPT_TO_COLORPT, _F_dp2cp)(self.p, RES_640, C.byref(dp), IMG_COLOR, RES_640, C.byref(cp))
        return (cp.x, cp.y), hr

    def depth_point_to_skeleton(self, x, y, depth):
        dp = NUI_DEPTH_IMAGE_POINT(int(x), int(y), int(depth), 0)
        v = Vector4(np.nan, np.nan, np.nan, np.nan)
        hr = _vtbl(self.p, M_DEPTHPT_TO_SKELPT, _F_dp2sp)(self.p, RES_640, C.byref(dp), C.byref(v))
        return (v.x, v.y, v.z, v.w), hr

    def release(self):
        if self.p:
            _vtbl(self.p, M_RELEASE, _F_release)(self.p)
            self.p = None


def live_mapper(sensor):
    m = C.c_void_p()
    hr_ok(sensor._call(S_GET_MAPPER, _F_getmapper)(sensor.p, C.byref(m)), "INuiSensor::NuiGetCoordinateMapper")
    if not m.value:
        raise OSError("NuiGetCoordinateMapper returned NULL")
    return Mapper(m)


def mapper_from_blob(blob):
    """NuiCreateCoordinateMapperFromParameters (flat export of Kinect10.dll). Returns (Mapper or None, HRESULT)."""
    from nui import _dll
    f = _dll.NuiCreateCoordinateMapperFromParameters
    f.argtypes = [C.c_ulong, C.c_void_p, C.POINTER(C.c_void_p)]
    f.restype = C.c_long
    buf = C.create_string_buffer(bytes(blob), len(blob))
    m = C.c_void_p()
    hr = f(C.c_ulong(len(blob)), C.cast(buf, C.c_void_p), C.byref(m))
    if hr < 0 or not m.value:
        return None, hr
    return Mapper(m, keepalive=buf), hr


# ============================================================ blob fields (stage 1 layout)
REG_OFF = 12314                      # 2-byte prefix, then 29 int32
ZPD_OFF, ZPPS_OFF, SHIFT_OFF = 12532, 12536, 12600
REG_NAMES = ("dx_center ax bx cx dx dx_start ay by cy dy dy_start dx_beta_start dy_beta_start rollout_blank rollout_size "
             "dx_beta_inc dy_beta_inc dxdx_start dxdy_start dydx_start dydy_start dxdxdx_start dydxdx_start dxdxdy_start "
             "dydxdy_start back_comp1 dydydx_start back_comp2 dydydy_start").split()
assert len(REG_NAMES) == 29


def reg_field_offset(name):
    return REG_OFF + 2 + 4 * REG_NAMES.index(name)


def parse_blob(blob):
    assert len(blob) == 12604, len(blob)
    reg = dict(zip(REG_NAMES, struct.unpack_from("<29i", blob, REG_OFF + 2)))
    zpd, zpps = struct.unpack_from("<ff", blob, ZPD_OFF)
    const_shift = struct.unpack_from("<i", blob, SHIFT_OFF)[0]
    return reg, float(zpd), float(zpps), const_shift


# ============================================================ libfreenect registration.c, ported
# Attribution: the functions in this section are a Python port of src/registration.c from libfreenect (the OpenKinect
# project, https://github.com/OpenKinect/libfreenect; Copyright (c) 2011 individual OpenKinect contributors), which is
# dual-licensed Apache License 2.0 / GPL v2. This port is used under the Apache License 2.0
# (https://www.apache.org/licenses/LICENSE-2.0); changes: translated from C to Python/numpy, mirror and start_lines exposed
# as arguments. The rest of this repository is MIT-licensed.
REG_X_VAL_SCALE = 256
S2D_PIXEL_CONST = 10
S2D_CONST_OFFSET = 0.375
DEPTH_SENSOR_X_RES = 1280
DEPTH_X_OFFSET = 1
DEPTH_Y_OFFSET = 1
DEPTH_MAX_METRIC_VALUE = 10000       # FREENECT_DEPTH_MM_MAX_VALUE


def _i32(v):
    """C int32 wrap-around (libfreenect shifts int32_t fields before widening to int64_t)."""
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v & 0x80000000 else v


def create_dxdy_tables(r, res_x=W, res_y=H):
    """freenect_create_dxdy_tables: returns (dx, dy) float64 tables, shape (res_y, res_x). Row recurrences scalar, the column
    recurrence vectorised over rows (identical integer arithmetic: int64, arithmetic right shifts)."""
    AX6, BX6, CX2, DX2 = r["ax"], r["bx"], r["cx"], r["dx"]
    AY6, BY6, CY2, DY2 = r["ay"], r["by"], r["cy"], r["dy"]
    dX0 = _i32(r["dx_start"] << 13) >> 4
    dY0 = _i32(r["dy_start"] << 13) >> 4
    dXdX0 = _i32(r["dxdx_start"] << 11) >> 3
    dXdY0 = _i32(r["dxdy_start"] << 11) >> 3
    dYdX0 = _i32(r["dydx_start"] << 11) >> 3
    dYdY0 = _i32(r["dydy_start"] << 11) >> 3
    dXdXdX0 = _i32(_i32(r["dxdxdx_start"] << 5) << 3)
    dYdXdX0 = _i32(_i32(r["dydxdx_start"] << 5) << 3)
    dYdXdY0 = _i32(_i32(r["dydxdy_start"] << 5) << 3)
    dXdXdY0 = _i32(_i32(r["dxdxdy_start"] << 5) << 3)
    dYdYdX0 = _i32(_i32(r["dydydx_start"] << 5) << 3)
    dYdYdY0 = _i32(_i32(r["dydydy_start"] << 5) << 3)
    rows = np.zeros((res_y, 6), np.int64)          # per-row starts: X0, XdX0, XdXdX0, Y0, XdY0, XdXdY0
    for row in range(res_y):
        dXdXdX0 += CX2
        dXdX0 += dYdXdX0 >> 8
        dYdXdX0 += DX2
        dX0 += dYdX0 >> 6
        dYdX0 += dYdYdX0 >> 8
        dYdYdX0 += BX6
        dXdXdY0 += CY2
        dXdY0 += dYdXdY0 >> 8
        dYdXdY0 += DY2
        dY0 += dYdY0 >> 6
        dYdY0 += dYdYdY0 >> 8
        dYdYdY0 += BY6
        rows[row] = (dX0, dXdX0, dXdXdX0, dY0, dXdY0, dXdXdY0)
    cX0, cXdX0, cXdXdX0, cY0, cXdY0, cXdXdY0 = [rows[:, k].copy() for k in range(6)]
    dx = np.empty((res_y, res_x)); dy = np.empty((res_y, res_x))
    for col in range(res_x):
        dx[:, col] = cX0 * (1.0 / (1 << 17))
        dy[:, col] = cY0 * (1.0 / (1 << 17))
        cX0 += cXdX0 >> 6
        cXdX0 += cXdXdX0 >> 8
        cXdXdX0 += AX6
        cY0 += cXdY0 >> 6
        cXdY0 += cXdXdY0 >> 8
        cXdXdY0 += AY6
    return dx, dy


def init_registration_table(r):
    """freenect_init_registration_table -> (reg_x int32 [x*256], reg_y int32), shape (480, 640)."""
    dx, dy = create_dxdy_tables(r)
    yy, xx = np.mgrid[0:H, 0:W]
    new_x = xx + dx + DEPTH_X_OFFSET
    new_y = yy + dy + DEPTH_Y_OFFSET
    bad = (new_x < 0) | (new_y < 0) | (new_x >= W) | (new_y >= H)
    new_x = np.where(bad, 2 * W, new_x)
    reg_x = np.trunc(new_x * REG_X_VAL_SCALE).astype(np.int64)     # double -> int32_t truncates toward zero
    reg_y = np.trunc(new_y).astype(np.int64)
    return reg_x, reg_y, dx, dy


def init_depth_to_rgb(reference_pixel_size, reference_distance, dcmos_rcmos_dist):
    """freenect_init_depth_to_rgb: int32 table indexed by metric depth in mm (x-shift * 256). zpi fields are C floats."""
    x_scale = DEPTH_SENSOR_X_RES // W
    rps = float(np.float32(reference_pixel_size)); rd = float(np.float32(reference_distance))
    rc = float(np.float32(dcmos_rcmos_dist))
    pixel_size = 1.0 / (rps * x_scale * S2D_PIXEL_CONST)
    pixels_between_rgb_and_ir_cmos = rc * pixel_size * S2D_PIXEL_CONST
    reference_distance_in_pixels = rd * pixel_size * S2D_PIXEL_CONST
    i = np.arange(DEPTH_MAX_METRIC_VALUE, dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        cur = i * pixel_size
        v = ((pixels_between_rgb_and_ir_cmos * (cur - reference_distance_in_pixels) / cur) + S2D_CONST_OFFSET) * REG_X_VAL_SCALE
    v[0] = 0                                                       # index 0 = no depth; never used
    return np.trunc(v).astype(np.int64)


def c_div_trunc(a, b):
    """C integer division (truncates toward zero)."""
    q = np.abs(a) // b
    return np.where(a < 0, -q, q)


def port_map(reg_x, reg_y, d2r, depth_mm, mirror_x=False, start_lines=0):
    """Per-pixel colour target of freenect_apply_registration (without the z-buffer), in SDK image coordinates.
    Returns (cx, cy, valid). mirror_x emulates DEPTH_MIRROR_X = 1 (both images mirrored)."""
    z = np.asarray(depth_mm, np.int64)
    if mirror_x:
        rx, ry = reg_x[:, ::-1], reg_y[:, ::-1]                    # reg_index = (y+1)*W - x - 1
    else:
        rx, ry = reg_x, reg_y
    nx = c_div_trunc(rx + d2r[np.clip(z, 0, DEPTH_MAX_METRIC_VALUE - 1)], REG_X_VAL_SCALE)
    ny = ry.copy()
    valid = (z > 0) & (z < DEPTH_MAX_METRIC_VALUE) & (nx >= 0) & (nx < W)   # uint32 cast: negative -> huge -> skipped
    # libfreenect subtracts target_offset = 480 * reg_pad_info.start_lines from the LINEAR target index; start_lines = 0 here.
    if start_lines:
        raise NotImplementedError("start_lines != 0 not modelled")
    if mirror_x:
        nx = (W - 1) - nx                                           # target index (ny+1)*W - nx - 1
    return nx, ny, valid


# ============================================================ comparison
DISTANCES = (800, 1000, 1500, 2000, 3000, 4000)
SWEEP_PIXELS = ((320, 240), (20, 20), (620, 460), (320, 20), (20, 460))    # SDK (mirrored) depth-pixel coordinates
SWEEP_Z = np.arange(300, 9001)                                               # 1 mm steps; > 8191 probes the 13-bit wrap


def compare(sdk_xy, port_x, port_y, port_valid):
    sx, sy = sdk_xy[..., 0].astype(np.int64), sdk_xy[..., 1].astype(np.int64)
    sdk_valid = (sx >= 0) & (sx < W) & (sy >= 0) & (sy < H)
    v = sdk_valid & port_valid
    ex = (sx - port_x)[v]; ey = (sy - port_y)[v]
    n = int(v.sum())
    out = {"n_valid": n, "n_sdk_valid": int(sdk_valid.sum()), "n_port_valid": int(port_valid.sum())}
    if not n:
        return out
    out.update({"within1": float(np.mean((np.abs(ex) <= 1) & (np.abs(ey) <= 1))),
                "exact": float(np.mean((ex == 0) & (ey == 0))),
                "exact_x": float(np.mean(ex == 0)), "exact_y": float(np.mean(ey == 0)),
                "ex_median": float(np.median(ex)), "ey_median": float(np.median(ey)),
                "ex_sd": float(ex.std()), "ey_sd": float(ey.std()),
                "ex_minmax": [int(ex.min()), int(ex.max())], "ey_minmax": [int(ey.min()), int(ey.max())]})
    mx, my = np.median(ex), np.median(ey)          # exploratory: after removing the best constant offset
    out["within1_after_offset"] = float(np.mean((np.abs(ex - mx) <= 1) & (np.abs(ey - my) <= 1)))
    return out


def shift_px(z, zpps, zpd, rc):
    """libfreenect's depth->RGB x shift in pixels (before fixed-point scaling), z in mm."""
    ps = 1.0 / (float(np.float32(zpps)) * (DEPTH_SENSOR_X_RES // W) * S2D_PIXEL_CONST)
    return float(np.float32(rc)) * S2D_PIXEL_CONST * ps * (1 - S2D_PIXEL_CONST * float(np.float32(zpd)) / z) + S2D_CONST_OFFSET


def int_shift(z, zpps, zpd, rc, scale=256, clamp_mm=None):
    """Whole-pixel shift after fixed-point conversion: trunc(scale*s) (C cast, toward zero), then floor(/scale)."""
    z = np.asarray(z, float)
    if clamp_mm is not None:
        z = np.minimum(z, clamp_mm)
    return np.floor(np.trunc(shift_px(z, zpps, zpd, rc) * scale) / scale)


def sdk_model_map(dx, dy, z, zpps, zpd):
    """EXPLORATORY, fitted post hoc from this unit's SDK output (not a libfreenect port): mirrored x, the reg_info warp floored
    to whole pixels (+1 in x), plus a whole-pixel shift from a 1/16-px table (rc 2.4) that stops growing past ~2 m."""
    yy, xx = np.mgrid[0:H, 0:W]
    wx = np.floor(xx + dx + DEPTH_X_OFFSET) + 1
    wy = np.floor(yy + dy + DEPTH_Y_OFFSET)
    nx = wx + int_shift(z, zpps, zpd, 2.4, scale=16, clamp_mm=2047)
    return ((W - 1) - nx)[:, ::-1], wy[:, ::-1]


def run_sdk(blob):
    """Live sensor mapper: flat frames and the per-pixel depth sweep. Saves stage2_sdk_maps.npz."""
    from sensor import Sensor
    s = Sensor()
    print("verify:", s.verify())
    s.initialize(0x00000020 | 0x00000002)                      # INIT_DEPTH | INIT_COLOR (as blob_dump.py)
    sdk = {}
    try:
        m = live_mapper(s)
        try:
            live_blob = m.params()
            print("live blob == calib_blob.bin:", live_blob == blob, len(live_blob))
            if live_blob != blob:
                raise RuntimeError("the sensor's blob differs from calib_blob.bin; re-run blob_dump.py first")
            for z in DISTANCES:
                xy, hr = m.depth_frame_to_color(np.full((H, W), z, np.uint16))
                sdk["z%d" % z] = xy
                print("SDK frame Z=%d hr=0x%08X centre (320,240)->(%d,%d)" % (z, hr & 0xFFFFFFFF, xy[240, 320, 0], xy[240, 320, 1]))
            # point API: depth field in mm? (must equal the frame result)
            for z in DISTANCES:
                (cx, cy), hr = m.depth_point_to_color(320, 240, z)
                assert (cx, cy) == tuple(int(v) for v in sdk["z%d" % z][240, 320]), "point API disagrees with frame API"
            for (x, y) in SWEEP_PIXELS:
                sdk["sweep_%d_%d" % (x, y)] = np.array([m.depth_point_to_color(x, y, int(z))[0] for z in SWEEP_Z], np.int32)
        finally:
            m.release()
    finally:
        s.shutdown(); s.release()
    np.savez_compressed(os.path.join(HERE, "stage2_sdk_maps.npz"), **sdk)
    return sdk


def main():
    below_normal_priority()
    check_header()
    blob = open(os.path.join(HERE, "calib_blob.bin"), "rb").read()
    reg, zpd, zpps, const_shift = parse_blob(blob)
    print("reg_info:", {k: reg[k] for k in ("ax", "bx", "cx", "dx", "dx_start", "ay", "by", "cy", "dy", "dy_start")})
    print("zero-plane distance %.4f, pixel size %.6f, const_shift %d" % (zpd, zpps, const_shift))
    if "--offline" in sys.argv:                                 # re-analyse the saved SDK output without the sensor
        sdk = dict(np.load(os.path.join(HERE, "stage2_sdk_maps.npz")))
    else:
        sdk = run_sdk(blob)

    # ---------------- port side + comparison (the verdict uses the faithful port only)
    reg_x, reg_y, dx, dy = init_registration_table(reg)
    print("port: dx table range %.3f..%.3f, dy %.3f..%.3f (px)" % (dx.min(), dx.max(), dy.min(), dy.max()))
    variants = {"faithful (2.4, no mirror)": (2.4, False), "2.3, no mirror": (2.3, False),
                "2.4, x mirrored": (2.4, True), "2.3, x mirrored": (2.3, True)}
    results = {"reg_info": reg, "zero_plane_distance": zpd, "zero_plane_pixel_size": zpps, "const_shift": const_shift,
               "variants": {}}
    fmt = "  Z=%4d valid %6d  within1 %.4f  exact x %.4f y %.4f  ex med %+.0f [%+d..%+d]  ey med %+.0f [%+d..%+d]  after-offset %.4f"
    for name, (rc, mir) in variants.items():
        d2r = init_depth_to_rgb(zpps, zpd, rc)
        res = {}
        for z in DISTANCES:
            px, py, pv = port_map(reg_x, reg_y, d2r, np.full((H, W), z), mirror_x=mir)
            res[z] = compare(sdk["z%d" % z], px, py, pv)
        results["variants"][name] = res
        print("\n== %s" % name)
        for z in DISTANCES:
            r = res[z]
            print(fmt % (z, r["n_valid"], r["within1"], r["exact_x"], r["exact_y"], r["ex_median"], *r["ex_minmax"],
                         r["ey_median"], *r["ey_minmax"], r["within1_after_offset"]))

    # ---------------- exploratory: the SDK's depth dependence, 1 mm steps, 5 pixels
    # For a fixed pixel the SDK x changes only through the depth->shift term, so its steps give that function directly.
    zs = SWEEP_Z
    lo = zs < 8192
    sweep = {}
    print("\n== EXPLORATORY depth sweep (MapDepthPointToColorPoint, z = 300..8191 mm, 1 mm steps)")
    for (x, y) in SWEEP_PIXELS:
        key = "%d_%d" % (x, y)
        xs = sdk["sweep_" + key][:, 0].astype(int)
        steps = zs[1:][lo[1:] & (np.diff(xs) != 0)]
        sweep[key] = {"y_values": np.unique(sdk["sweep_" + key][lo, 1]).tolist(),
                      "x_at_300": int(xs[0]), "x_at_8191": int(xs[lo][-1]), "steps_at_mm": steps.tolist()}
        raw_x = (W - 1) - x
        base = np.floor(raw_x + dx[y, raw_x] + DEPTH_X_OFFSET) + 1
        fits = {}
        for scale in (256, 16):
            for rc in (2.3, 2.4):
                for clamp in (None, 2047):
                    pred = (W - 1) - (base + int_shift(zs[lo], zpps, zpd, rc, scale, clamp))
                    fits["scale%d_rc%.1f_clamp%s" % (scale, rc, clamp)] = float(np.mean(pred == xs[lo]))
        sweep[key]["model_match"] = fits
        hi = zs >= 8192 + 300                                   # 13-bit wrap: does depth 8192+k map like depth k?
        sweep[key]["wrap_8192_match"] = float(np.mean(xs[hi] == xs[np.searchsorted(zs, zs[hi] - 8192)]))
    first = sweep["320_240"]
    print("  steps (mm) at pixel (320,240):", first["steps_at_mm"])
    print("  identical step depths at all 5 pixels:", all(sweep[k]["steps_at_mm"] == first["steps_at_mm"] for k in sweep))
    for k, v in first["model_match"].items():
        print("  model %-28s matches SDK x at %.4f of depths (pixel 320,240)" % (k, v))
    for rc in (2.4, 2.3):
        st = zs[1:][np.diff(int_shift(zs, zpps, zpd, rc, 256)) != 0]
        print("  libfreenect (%.1f) steps 1200-4500 mm:" % rc, [int(v) for v in st if 1200 < v < 4500])
    print("  depth taken modulo 8192 (13-bit field):", {k: v["wrap_8192_match"] for k, v in sweep.items()})
    results["exploratory_sweep"] = sweep

    # ---------------- exploratory: the post-hoc SDK model on the full frames
    print("\n== EXPLORATORY post-hoc SDK model (mirrored; warp floored +1; 1/16-px shift table, rc 2.4, no growth past ~2 m)")
    model = {}
    for z in DISTANCES:
        mx, my = sdk_model_map(dx, dy, z, zpps, zpd)
        r = compare(sdk["z%d" % z], mx.astype(np.int64), my.astype(np.int64), np.ones((H, W), bool))
        model[z] = r
        print(fmt % (z, r["n_valid"], r["within1"], r["exact_x"], r["exact_y"], r["ex_median"], *r["ex_minmax"],
                     r["ey_median"], *r["ey_minmax"], r["within1_after_offset"]))
    results["exploratory_sdk_model"] = model

    faithful = results["variants"]["faithful (2.4, no mirror)"]
    passed = all(faithful[z]["within1"] >= 0.99 for z in DISTANCES)
    results["verdict_faithful_PASS"] = passed
    ranking = sorted(results["variants"], key=lambda k: -np.mean([results["variants"][k][z]["within1"] for z in DISTANCES]))
    results["variants_by_mean_within1"] = ranking
    print("\nSTAGE 2 VERDICT (faithful port, >= 99 %% within +-1 px at every Z): %s" % ("PASS" if passed else "FAIL"))
    for k in ranking:
        print("  %-26s within1 by Z: %s" % (k, [round(results["variants"][k][z]["within1"], 4) for z in DISTANCES]))
    with open(os.path.join(HERE, "stage2_results.json"), "w") as f:
        json.dump(results, f, indent=1, default=lambda o: int(o) if isinstance(o, np.integer) else float(o))


if __name__ == "__main__":
    main()
