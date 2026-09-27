"""mapper_vs_inline.py -- does INuiCoordinateMapper's depth->skeleton transform use the header's nominal intrinsics, or this unit's
calibration? (No streaming: needs only NuiInitialize and the mapper.)

Public: NuiSkeleton.h defines NuiTransformDepthImageToSkeleton INLINE with NUI_CAMERA_DEPTH_NOMINAL_INVERSE_FOCAL_LENGTH_IN_PIXELS
3.501e-3 (at 320x240; f = 285.63 -> 571.26 px at 640x480) and principal point exactly (width/2, height/2); z = (packed >> 3)/1000.
The SDK docs call it a transform 'based on the optics of the depth sensor'. The INuiCoordinateMapper (SDK 1.6+) is built from a
per-sensor parameter blob (our blob_dump.py: 12 604 bytes carrying PrimeSense reg_info, 120.0 and 0.1042, which imply 575.82 px).
Not public (found): whether MapDepthPointToSkeletonPoint / MapDepthFrameToSkeletonFrame use the nominal 571.26 px or a per-unit
value, where their principal point is, whether z is planar depth, and what they do with depths outside 800-4000 mm.

RULES (fixed before running). Grid: x in 0..639 step 71, y in 0..479 step 53, depth in {800, 1200, 2000, 3000, 4000} mm.
  M1 INTRINSICS : fit X/Z = (x - cx)/fx and Y/Z = -(y - cy)/fy by least squares over the grid.
                  NOMINAL if fx, fy within 571.26 +- 0.1 and cx, cy within (320, 240) +- 0.05 ;
                  BLOB-CONSTANT if fx, fy within 575.82 +- 0.1 ; otherwise OTHER (report the numbers).
  M2 EXACTNESS  : max |mapper - inline formula| over the grid <= 1e-5 m -> IDENTICAL, else report the max.
  M3 Z          : Z == depth/1000 to 1e-6 m on every grid point -> PLANAR-MM (the NUI_DEPTH_IMAGE_POINT depth is unshifted mm).
  M4 RANGE      : report HRESULT and output for depth 500, 799, 4001, 8000, 20000 mm at the image centre and a corner.
  M5 FRAME      : MapDepthFrameToSkeletonFrame on a synthetic 640x480 frame (depth 2000 mm everywhere, playerIndex 0) equals
                  the point function on every pixel to 1e-6 m -> SAME PATH.
  M6 INVERSE    : MapSkeletonPointToDepthPoint round trip returns the original (x, y) on >= 99 % of the grid -> PASS (report the
                  rounding convention seen).
"""
import ctypes as C
import numpy as np
from atlas_common import (below_normal_priority, hr_hex, _vtbl, NUI_DEPTH_IMAGE_POINT, NUI_DEPTH_IMAGE_PIXEL,
                          V_GET_MAPPER, M_RELEASE, M_DEPTH_POINT_TO_SKELETON, M_DEPTH_FRAME_TO_SKELETON, M_SKELETON_POINT_TO_DEPTH,
                          INV_F_NOMINAL_320)
from sensor import Sensor, Vector4

RES640 = 2
_F_getmapper = C.WINFUNCTYPE(C.c_long, C.c_void_p, C.POINTER(C.c_void_p))
_F_d2s = C.WINFUNCTYPE(C.c_long, C.c_void_p, C.c_int, C.POINTER(NUI_DEPTH_IMAGE_POINT), C.POINTER(Vector4))
_F_s2d = C.WINFUNCTYPE(C.c_long, C.c_void_p, C.POINTER(Vector4), C.c_int, C.POINTER(NUI_DEPTH_IMAGE_POINT))
_F_frame = C.WINFUNCTYPE(C.c_long, C.c_void_p, C.c_int, C.c_ulong, C.POINTER(NUI_DEPTH_IMAGE_PIXEL), C.c_ulong, C.POINTER(Vector4))
_F_rel = C.WINFUNCTYPE(C.c_ulong, C.c_void_p)


def inline_d2s(x, y, depth_mm, w=640, h=480):
    """NuiTransformDepthImageToSkeleton from NuiSkeleton.h, in float32 as the header does."""
    f = np.float32
    z = f(depth_mm) / f(1000.0)
    X = (f(x) - f(w / 2.0)) * (f(320.0) / f(w)) * f(INV_F_NOMINAL_320) * z
    Y = -(f(y) - f(h / 2.0)) * (f(240.0) / f(h)) * f(INV_F_NOMINAL_320) * z
    return float(X), float(Y), float(z)


def main():
    print("below-normal priority:", below_normal_priority())
    s = Sensor(); print("verify:", s.verify())
    s.initialize(0x00000020)
    m = C.c_void_p()
    try:
        hr = s._call(V_GET_MAPPER, _F_getmapper)(s.p, C.byref(m)); print("NuiGetCoordinateMapper", hr_hex(hr))
        d2s = _vtbl(m, M_DEPTH_POINT_TO_SKELETON, _F_d2s); s2d = _vtbl(m, M_SKELETON_POINT_TO_DEPTH, _F_s2d)
        rows = []
        for depth in (800, 1200, 2000, 3000, 4000):
            for y in range(0, 480, 53):
                for x in range(0, 640, 71):
                    p = NUI_DEPTH_IMAGE_POINT(x, y, depth, 0); v = Vector4()
                    r = d2s(m, RES640, C.byref(p), C.byref(v))
                    if r < 0:
                        print("d2s failed", x, y, depth, hr_hex(r)); continue
                    rows.append((x, y, depth, v.x, v.y, v.z, v.w))
        a = np.array(rows)
        x, y, dep, X, Y, Z = a[:, 0], a[:, 1], a[:, 2], a[:, 3], a[:, 4], a[:, 5]
        print(f"grid points {len(a)}; w values {sorted(set(np.round(a[:, 6], 6)))}")
        # M3
        dz = np.abs(Z - dep / 1000.0).max(); print(f"M3 max |Z - depth/1000| = {dz:.3e} m ->", 'PLANAR-MM' if dz <= 1e-6 else 'OTHER')
        # M1 fit
        A = np.c_[x, np.ones_like(x)]
        (ax, bx), *_ = np.linalg.lstsq(A, X / Z, rcond=None)
        (ay, by), *_ = np.linalg.lstsq(np.c_[y, np.ones_like(y)], -Y / Z, rcond=None)
        fx, cx, fy, cy = 1 / ax, -bx / ax, 1 / ay, -by / ay
        resx = np.abs(X / Z - (ax * x + bx)).max(); resy = np.abs(-Y / Z - (ay * y + by)).max()
        print(f"M1 fx {fx:.4f}  cx {cx:.4f}  fy {fy:.4f}  cy {cy:.4f}  (max linear-fit residual in X/Z {resx:.2e}, Y/Z {resy:.2e})")
        if all(abs(f - 571.26) <= 0.1 for f in (fx, fy)) and abs(cx - 320) <= 0.05 and abs(cy - 240) <= 0.05:
            m1 = 'NOMINAL'
        elif all(abs(f - 575.82) <= 0.1 for f in (fx, fy)):
            m1 = 'BLOB-CONSTANT'
        else:
            m1 = 'OTHER'
        # M2
        inl = np.array([inline_d2s(xx, yy, dd) for xx, yy, dd in zip(x, y, dep)])
        dmax = np.abs(np.c_[X, Y, Z] - inl).max(); m2 = 'IDENTICAL' if dmax <= 1e-5 else f'DIFFERENT (max {dmax:.3e} m)'
        print(f"M2 max |mapper - inline| = {dmax:.3e} m")
        # M4
        print("M4 out-of-range depths:")
        for depth in (0, 500, 799, 4001, 8000, 20000, 60000):
            for (px, py) in ((320, 240), (0, 0)):
                p = NUI_DEPTH_IMAGE_POINT(px, py, depth, 0); v = Vector4()
                r = d2s(m, RES640, C.byref(p), C.byref(v))
                print(f"   depth {depth:>6} at ({px},{py}): hr {hr_hex(r)} -> ({v.x:.5f}, {v.y:.5f}, {v.z:.5f}, w {v.w:.1f})")
        # M5 frame path
        n = 640 * 480
        pix = (NUI_DEPTH_IMAGE_PIXEL * n)()
        for i in range(n):
            pix[i].playerIndex = 0; pix[i].depth = 2000
        out = (Vector4 * n)()
        r = _vtbl(m, M_DEPTH_FRAME_TO_SKELETON, _F_frame)(m, RES640, n, pix, n, out)
        print("M5 MapDepthFrameToSkeletonFrame", hr_hex(r))
        fr = np.frombuffer(out, dtype=np.float32).reshape(480, 640, 4)
        yy, xx = np.mgrid[0:480, 0:640]
        f = np.float32
        Xi = (xx.astype(f) - f(320)) * f(0.5) * f(INV_F_NOMINAL_320) * f(2.0)
        Yi = -(yy.astype(f) - f(240)) * f(0.5) * f(INV_F_NOMINAL_320) * f(2.0)
        # compare frame path with the point path on a subset (every 16th pixel) and with inline everywhere
        sub = []
        for py in range(0, 480, 16):
            for px in range(0, 640, 16):
                p = NUI_DEPTH_IMAGE_POINT(px, py, 2000, 0); v = Vector4(); d2s(m, RES640, C.byref(p), C.byref(v))
                sub.append(np.abs(np.array([v.x, v.y, v.z]) - fr[py, px, :3]).max())
        d_fp = max(sub); d_fi = max(np.abs(fr[..., 0] - Xi).max(), np.abs(fr[..., 1] - Yi).max(), np.abs(fr[..., 2] - 2.0).max())
        m5 = 'SAME PATH' if d_fp <= 1e-6 else f'DIFFERENT (max {d_fp:.3e})'
        print(f"M5 frame vs point max diff {d_fp:.3e} m; frame vs inline max diff {d_fi:.3e} m")
        # M6 inverse
        hits = 0; tot = 0; offs = []
        for (xx_, yy_, dd, X_, Y_, Z_) in zip(x, y, dep, X, Y, Z):
            v = Vector4(X_, Y_, Z_, 1.0); p = NUI_DEPTH_IMAGE_POINT()
            r = s2d(m, C.byref(v), RES640, C.byref(p)); tot += 1
            if r >= 0 and p.x == int(xx_) and p.y == int(yy_):
                hits += 1
            else:
                offs.append((int(xx_), int(yy_), int(dd), p.x, p.y, p.depth, hr_hex(r)))
        print(f"M6 round trip exact on {hits}/{tot}; first misses: {offs[:6]}")
        p = NUI_DEPTH_IMAGE_POINT(); v = Vector4(0.0, 0.0, 2.0, 1.0); s2d(m, C.byref(v), RES640, C.byref(p))
        print(f"   skeleton (0,0,2.0) -> depth point ({p.x}, {p.y}) depth {p.depth} reserved {p.reserved}")
        v = Vector4(0.001, -0.001, 2.0, 1.0); s2d(m, C.byref(v), RES640, C.byref(p))
        print(f"   skeleton (+1 mm, -1 mm, 2.0) -> ({p.x}, {p.y}) depth {p.depth}")
        print("\nVERDICTS:", {'M1': m1, 'M2': m2, 'M3': 'PLANAR-MM' if dz <= 1e-6 else 'OTHER', 'M5': m5,
                              'M6': 'PASS' if hits >= 0.99 * tot else 'FAIL'})
    finally:
        if m.value:
            _vtbl(m, M_RELEASE, _F_rel)(m)
        s.shutdown(); s.release()


if __name__ == '__main__':
    main()
