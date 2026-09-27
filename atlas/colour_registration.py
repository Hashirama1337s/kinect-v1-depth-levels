"""colour_registration.py -- how well does the SDK's depth->colour mapping land on the colour image? (offline, no sensor)

Why: the live R1 probe in colour_probe.py (dim room, whatever was in view) gave NO VERDICT (peak contrast 1.16 < 1.2).
The dark-room captures (../dark_room_*.npz) hold, for one static scene each, 90 depth frames (mm) and the temporal mean of
60 RAW_BAYER 1280x960 frames taken seconds apart, and include manufactured depth steps with colour contrast (backing board
7 cm in front of the wall, box, mug, paper). The unit's own mapper is rebuilt offline from its calibration blob
(../calib_blob.bin, from INuiCoordinateMapper::GetColorToDepthRelationalParameters) with NuiCreateCoordinateMapperFromParameters
(flat export of Kinect10.dll, prototype from NuiSensor.h), so no sensor time is used.

Method (fixed before running):
  colour image  = green plane of the Bayer mean (mean of phases (0,0) and (1,1) per 2x2 cell) -> 640x480, same field as
                  COLOR 640 (colour_probe G1: 1280 = 2 x 640, offset <= 0.35 px at 640 scale);
  depth         = per-pixel median of the 90 frames (0 = invalid);
  edge points   = foreground-side pixels of 4-neighbour depth jumps > 50 mm; outward normal n = direction to the farther
                  side (from a Sobel of depth with invalid pixels set to the local maximum);
  map           = MapDepthFrameToColorFrame(depth 640, pixels, RAW_BAYER, 640) (integer colour coordinates);
  per point     = colour-gradient-magnitude profile along n, s in [-5, 5] px (0.25 px steps); s_i = parabolic peak;
                  keep points whose profile peak is > 2x the profile median (a colour edge exists there);
  model         = s_i = n_i . t + b  (robust least squares, Huber), t = global registration translation (px, 640 scale),
                  b = common offset along the outward normal (colour silhouette outside the depth silhouette if b > 0);
                  95 % CI by bootstrap over points (400 resamples).
Bars (per capture): CONSISTENT <= 1 px if |t| <= 1.0 and the CI half-width of |t| < 0.5; OFFSET if |t| > 1.5 with the same CI;
  otherwise NO VERDICT.  Overall: CONSISTENT if >= 4 usable captures say CONSISTENT and none says OFFSET.
Output: numbers only -> colour_registration_result.json (no image is written).
"""
import os, sys, json, glob
import ctypes as C
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..')
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
from atlas_common import below_normal_priority, hr_hex, _vtbl, NUI_DEPTH_IMAGE_PIXEL   # noqa: E402
import nui                                                                             # noqa: E402

M_RELEASE, M_DEPTH_FRAME_TO_COLOR = 2, 7                 # INuiCoordinateMapperVtbl (NuiSensor.h)
T_BAYER, R640 = 6, 2


class NUI_COLOR_IMAGE_POINT(C.Structure):
    _fields_ = [("x", C.c_long), ("y", C.c_long)]


_F_frm2col = C.WINFUNCTYPE(C.c_long, C.c_void_p, C.c_int32, C.c_uint32, C.POINTER(NUI_DEPTH_IMAGE_PIXEL), C.c_int32,
                           C.c_int32, C.c_uint32, C.POINTER(NUI_COLOR_IMAGE_POINT))
_F_ref = C.WINFUNCTYPE(C.c_ulong, C.c_void_p)


def make_mapper():
    blob = open(os.path.join(ROOT, 'calib_blob.bin'), 'rb').read()
    f = nui._dll.NuiCreateCoordinateMapperFromParameters
    f.argtypes = [C.c_ulong, C.c_void_p, C.POINTER(C.c_void_p)]
    f.restype = C.c_long
    buf = C.create_string_buffer(blob, len(blob))
    m = C.c_void_p()
    hr = f(len(blob), C.cast(buf, C.c_void_p), C.byref(m))
    return m, hr, buf


def map_frame(m, depth_mm):
    n = depth_mm.size
    px = np.zeros((n, 2), dtype=np.uint16); px[:, 1] = np.clip(depth_mm, 0, 65535).astype(np.uint16).ravel()
    pts = np.zeros((n, 2), dtype=np.int32)
    hr = _vtbl(m, M_DEPTH_FRAME_TO_COLOR, _F_frm2col)(m, R640, n, px.ctypes.data_as(C.POINTER(NUI_DEPTH_IMAGE_PIXEL)),
                                                       T_BAYER, R640, n, pts.ctypes.data_as(C.POINTER(NUI_COLOR_IMAGE_POINT)))
    return hr, pts.reshape(depth_mm.shape[0], depth_mm.shape[1], 2)


def analyse(D, G, colpts, rng):
    from scipy.ndimage import sobel, maximum_filter, map_coordinates
    Df = D.astype(np.float64)
    fill = np.where(Df > 0, Df, maximum_filter(np.where(Df > 0, Df, 0), 7))
    gx, gy = sobel(fill, 1), sobel(fill, 0)
    fg = np.zeros(D.shape, bool)
    for dy, dx in ((0, 1), (1, 0)):
        a = Df[:D.shape[0] - dy, :D.shape[1] - dx]; b = Df[dy:, dx:]
        jump = (a > 0) & (b > 0) & (np.abs(a - b) > 50)
        fg[:D.shape[0] - dy, :D.shape[1] - dx] |= jump & (a < b)
        fg[dy:, dx:] |= jump & (b < a)
    ys, xs = np.where(fg)
    nx, ny = gx[ys, xs], gy[ys, xs]; nn = np.hypot(nx, ny); ok = nn > 0
    ys, xs, nx, ny = ys[ok], xs[ok], nx[ok] / nn[ok], ny[ok] / nn[ok]
    cx = colpts[ys, xs, 0].astype(np.float64); cy = colpts[ys, xs, 1].astype(np.float64)
    ok = (cx > 8) & (cx < 631) & (cy > 8) & (cy < 471)
    cx, cy, nx, ny = cx[ok], cy[ok], nx[ok], ny[ok]
    gm = np.hypot(sobel(G, 1), sobel(G, 0))
    s = np.arange(-5, 5.001, 0.25)
    P = map_coordinates(gm, [cy[:, None] + s[None, :] * ny[:, None], cx[:, None] + s[None, :] * nx[:, None]], order=1)
    k = np.argmax(P, axis=1)
    strong = (P.max(1) > 2 * np.median(P, axis=1)) & (k > 0) & (k < s.size - 1)
    kk = k[strong]; Pk = P[strong]
    y0, y1, y2 = Pk[np.arange(kk.size), kk - 1], Pk[np.arange(kk.size), kk], Pk[np.arange(kk.size), kk + 1]
    den = y0 - 2 * y1 + y2
    frac = np.where(den != 0, 0.5 * (y0 - y2) / den, 0.0)
    si = s[kk] + 0.25 * np.clip(frac, -0.5, 0.5)
    X = np.c_[nx[strong], ny[strong], np.ones(kk.size)]

    def huber_fit(X, y):
        w = np.ones(len(y))
        for _ in range(30):
            beta, *_ = np.linalg.lstsq(X * w[:, None] ** 0.5, y * w ** 0.5, rcond=None)
            r = y - X @ beta; sc = 1.4826 * np.median(np.abs(r)) + 1e-9
            u = np.abs(r) / (1.345 * sc); w = np.where(u <= 1, 1.0, 1.0 / u)
        return beta
    if kk.size < 50:
        return dict(points=int(kk.size), verdict='NO DATA')
    beta = huber_fit(X, si)
    boots = []
    for _ in range(400):
        idx = rng.integers(0, kk.size, kk.size)
        boots.append(huber_fit(X[idx], si[idx]))
    boots = np.array(boots)
    tmag = np.hypot(boots[:, 0], boots[:, 1])
    lo, hi = np.percentile(tmag, [2.5, 97.5]); half = (hi - lo) / 2
    t = float(np.hypot(beta[0], beta[1]))
    verdict = ('CONSISTENT <= 1 px' if (t <= 1.0 and half < 0.5) else 'OFFSET' if (t > 1.5 and half < 0.5) else 'NO VERDICT')
    ang = np.degrees(np.arctan2(ny[strong], nx[strong]))
    return dict(points=int(kk.size), candidates=int(strong.size), tx=float(beta[0]), ty=float(beta[1]), b=float(beta[2]),
                t=t, t_ci95=[float(lo), float(hi)], tx_ci95=[float(v) for v in np.percentile(boots[:, 0], [2.5, 97.5])],
                ty_ci95=[float(v) for v in np.percentile(boots[:, 1], [2.5, 97.5])],
                b_ci95=[float(v) for v in np.percentile(boots[:, 2], [2.5, 97.5])],
                normal_angle_hist=np.histogram(ang, bins=[-180, -135, -45, 45, 135, 180])[0].tolist(),
                verdict=verdict)


def main():
    print("below-normal priority:", below_normal_priority())
    m, hr, keep = make_mapper()
    print("NuiCreateCoordinateMapperFromParameters", hr_hex(hr), bool(m.value))
    if hr < 0 or not m.value:
        return
    rng = np.random.default_rng(0)
    res = {}
    try:
        for fn in sorted(glob.glob(os.path.join(ROOT, 'dark_room_*.npz'))):
            tag = os.path.basename(fn)[len('dark_room_'):-4]
            z = np.load(fn)
            Bm = z['Bmean'].astype(np.float64)
            if Bm.mean() <= 10:
                continue
            D = np.median(z['D'].astype(np.float64), axis=0)
            G = 0.5 * (Bm[0::2, 0::2] + Bm[1::2, 1::2])
            h, pts = map_frame(m, D)
            if h < 0:
                res[tag] = dict(map_hr=hr_hex(h)); continue
            r = analyse(D, G, pts, rng)
            r['map_hr'] = hr_hex(h)
            res[tag] = r
            print(tag, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()})
    finally:
        _vtbl(m, M_RELEASE, _F_ref)(m)
    v = [r.get('verdict') for r in res.values()]
    overall = ('CONSISTENT' if v.count('CONSISTENT <= 1 px') >= 4 and 'OFFSET' not in v else
               'OFFSET' if v.count('OFFSET') >= 4 else 'NO VERDICT')
    print("OVERALL", overall, v)
    json.dump(dict(results=res, overall=overall), open(os.path.join(HERE, 'colour_registration_result.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
