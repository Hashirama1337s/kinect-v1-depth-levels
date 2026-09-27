"""colour_probe.py -- Kinect v1 colour-camera atlas probe (SDK 1.8, INuiSensor COM). Read-only, <= ~25 s per run.

Three runs (pick one per call; each run is its own NuiInitialize/NuiShutdown):
  python colour_probe.py geo   COLOR 640 -> COLOR 1280 -> RAW_BAYER 1280 -> RAW_BAYER 640 -> DEPTH 640 + COLOR 640 together,
                               then the coordinate mapper (MapDepthPointToColorPoint / MapDepthFrameToColorFrame).
  python colour_probe.py yuv   RAW_YUV 640 -> COLOR_YUV 640 -> COLOR 640.
  python colour_probe.py b1280 COLOR 1280 -> RAW_BAYER 1280 (B1/B2 at 1280; added after run 1, whose COLOR1280 session was
                               captured while auto-exposure was still converging -> its B_1280 fit is VOID).
Every session: open stream, settle, grab for a fixed time, keep per-frame timestamps/frame numbers/sizes and a running MEAN
image in memory only; read every INuiColorCameraSettings GETTER (never a setter). After NuiShutdown the analysis runs and
writes NUMBERS ONLY to colour_probe_<run>_result.json. No image of the room is written anywhere.

Public / known before the run (sources listed in the README): SDK docs list COLOR 640@30, COLOR 1280@12 ("Fps12"),
YUV 640@15, RAW_BAYER 640@30 and 1280@12; "Color formats are computed from the same camera data, so all data types represent
the same image"; YUV is "gamma-corrected ... UYVY"; RGB/Bayer are called "linear". INuiColorCameraSettings documented ranges
(exposure/frame interval 0..4000 in 1/10 000 s, gain 1..16, WB 2700..6500 K) with no Xbox-360 restriction stated.

Bars fixed before the first run:
  S1 SETTINGS   OPEN if NuiGetColorCameraSettings (INuiSensor slot 30) returns S_OK and >= 30 of the 34 getters return S_OK;
                GATED if slot 30 or the getters return 0x8301000F (E_NUI_HARDWARE_FEATURE_UNAVAILABLE); else PARTIAL (list).
  F1 FPS        per mode, fps from the SDK timestamps over the capture window; MATCHES DOC if within 10 % of 30/15/12.
  G1 640 vs 1280 fit COLOR640 ~ COLOR1280 sampled at (sx*x+tx, sy*y+ty) (pixel centres). SAME FIELD (2x scale) if
                |sx-2| and |sy-2| < 0.01 and |tx-0.5|, |ty-0.5| < 1.5 px (1280 px) with NCC > 0.9; CROP if sx or sy < 1.9;
                ANAMORPHIC if |sx-sy| > 0.02; otherwise report the numbers (NO VERDICT).
  G2 MAPPER     SAME-FIELD MAPPING if MapDepthPointToColorPoint at colour 1280 = 2 x (colour 640) within +-1 px for every
                test point (and the same for RAW_BAYER); else report the relation.
  B1 BAYER PHASE a Bayer phase is assigned colour C if its native-site linear fit to COLOR channel C (same resolution) has
                R^2 >= 0.95 and exceeds the other two channels' R^2 by >= 0.02. PATTERN = the four assignments.
  B2 HOST TONE  COLOR vs RAW_BAYER at native sites: IDENTITY if slope in [0.95, 1.05] and |intercept| <= 3 DN for every phase
                (the SDK's COLOR is a demosaic of the same data, no host tone curve); otherwise HOST-PROCESSED (numbers).
  Y1 YUV ORDER  byte order from which byte positions track COLOR_YUV luma (corr > 0.9) -> UYVY or YUYV.
  Y2 TONE       fit Y(RAW_YUV) = a * L(COLOR640)^k over pixels with 20 <= L <= 200: RGB-PATH LINEAR vs YUV if k in [0.35, 0.60];
                SAME TONE CURVE if k in [0.85, 1.15]; else NO VERDICT.
  R1 REGISTRATION depth edges (jump > 50 mm) mapped to COLOR640 by MapDepthFrameToColorFrame; mean colour-gradient magnitude at
                the mapped foreground-edge points as a function of a global shift (dx, dy) in [-6, 6] px (0.5 px steps).
                CONSISTENT <= 1 px if the argmax |shift| <= 1.0 and peak / mean(|shift| >= 4) >= 1.2; OFFSET if argmax > 1.5 with
                the same contrast; NO VERDICT if contrast < 1.2.
SAFETY: vtable indices from NuiSensor.h (INuiSensor 28/30; INuiColorCameraSettings getters; INuiCoordinateMapper 2/7/9);
sensor.verify() first; the settings object is checked with AddRef/Release (known-answer refcounts) before any getter.
"""
import os, sys, time, json, ctypes as C
from ctypes import wintypes as W
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..')
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
from atlas_common import below_normal_priority, hr_hex, NUI_IMAGE_FRAME, NUI_LOCKED_RECT, _vtbl, _LockRect, _UnlockRect, \
    _VT_LOCKRECT, _VT_UNLOCKRECT, NUI_DEPTH_IMAGE_POINT, NUI_DEPTH_IMAGE_PIXEL   # noqa: E402
from sensor import Sensor, V_STREAM_NEXT, V_STREAM_RELEASE, _F_next, _F_relframe  # noqa: E402

INIT_DEPTH, INIT_COLOR = 0x20, 0x02
T_COLOR, T_YUV, T_RAWYUV, T_DEPTH, T_BAYER = 1, 2, 3, 4, 6
R640, R1280 = 2, 3
DIMS = {R640: (640, 480), R1280: (1280, 960)}
BPP = {T_COLOR: 4, T_YUV: 4, T_RAWYUV: 2, T_BAYER: 1, T_DEPTH: 2}
DOC_FPS = {(T_COLOR, R640): 30, (T_COLOR, R1280): 12, (T_YUV, R640): 15, (T_RAWYUV, R640): 15,
           (T_BAYER, R640): 30, (T_BAYER, R1280): 12}

V_GET_MAPPER, V_GET_COLOR_SETTINGS = 28, 30                        # INuiSensorVtbl
M_RELEASE, M_DEPTH_FRAME_TO_COLOR, M_DEPTH_POINT_TO_COLOR = 2, 7, 9  # INuiCoordinateMapperVtbl
GETTERS = [(4, 'AutoWhiteBalance', 'b'), (6, 'WhiteBalance', 'l'), (7, 'MinWhiteBalance', 'l'), (8, 'MaxWhiteBalance', 'l'),
           (10, 'Contrast', 'd'), (11, 'MinContrast', 'd'), (12, 'MaxContrast', 'd'),
           (14, 'Hue', 'd'), (15, 'MinHue', 'd'), (16, 'MaxHue', 'd'),
           (18, 'Saturation', 'd'), (19, 'MinSaturation', 'd'), (20, 'MaxSaturation', 'd'),
           (22, 'Gamma', 'd'), (23, 'MinGamma', 'd'), (24, 'MaxGamma', 'd'),
           (26, 'Sharpness', 'd'), (27, 'MinSharpness', 'd'), (28, 'MaxSharpness', 'd'),
           (30, 'AutoExposure', 'b'), (32, 'ExposureTime', 'd'), (33, 'MinExposureTime', 'd'), (34, 'MaxExposureTime', 'd'),
           (36, 'FrameInterval', 'd'), (37, 'MinFrameInterval', 'd'), (38, 'MaxFrameInterval', 'd'),
           (40, 'Brightness', 'd'), (41, 'MinBrightness', 'd'), (42, 'MaxBrightness', 'd'),
           (44, 'PowerLineFrequency', 'l'), (46, 'BacklightCompensationMode', 'l'),
           (48, 'Gain', 'd'), (49, 'MinGain', 'd'), (50, 'MaxGain', 'd')]
_F_getptr = C.WINFUNCTYPE(C.c_long, C.c_void_p, C.POINTER(C.c_void_p))
_F_out = C.WINFUNCTYPE(C.c_long, C.c_void_p, C.c_void_p)
_F_ref = C.WINFUNCTYPE(C.c_ulong, C.c_void_p)


class NUI_COLOR_IMAGE_POINT(C.Structure):
    _fields_ = [("x", C.c_long), ("y", C.c_long)]


_F_pt2col = C.WINFUNCTYPE(C.c_long, C.c_void_p, C.c_int32, C.POINTER(NUI_DEPTH_IMAGE_POINT), C.c_int32, C.c_int32,
                          C.POINTER(NUI_COLOR_IMAGE_POINT))
_F_frm2col = C.WINFUNCTYPE(C.c_long, C.c_void_p, C.c_int32, C.c_uint32, C.POINTER(NUI_DEPTH_IMAGE_PIXEL), C.c_int32, C.c_int32,
                           C.c_uint32, C.POINTER(NUI_COLOR_IMAGE_POINT))


# ------------------------------------------------------------------------------------------------ device side
def read_settings(s):
    out = {'_slot30_hr': None}
    p = C.c_void_p()
    hr = s._call(V_GET_COLOR_SETTINGS, _F_getptr)(s.p, C.byref(p))
    out['_slot30_hr'] = hr_hex(hr)
    if hr < 0 or not p.value:
        return out
    try:
        a = _vtbl(p, 1, _F_ref)(p); r = _vtbl(p, 2, _F_ref)(p)          # AddRef / Release: known-answer check
        out['_refcount_check'] = [int(a), int(r)]
        if int(a) != int(r) + 1:
            out['_abort'] = 'refcount check failed; no getters called'
            return out
        for idx, name, t in GETTERS:
            buf = C.c_double(0.0)
            hr = _vtbl(p, idx, _F_out)(p, C.byref(buf))
            raw = bytes(buf)
            if t == 'd':
                val = buf.value
            elif t in ('l', 'b'):
                val = int.from_bytes(raw[:4], 'little', signed=True)
            out[name] = {'hr': hr_hex(hr), 'value': (val if hr >= 0 else None)}
    finally:
        _vtbl(p, 2, _F_ref)(p)
    return out


def grab(s, h, timeout=3000):
    fr = NUI_IMAGE_FRAME()
    hr = s._call(V_STREAM_NEXT, _F_next)(s.p, h, C.c_uint32(timeout), C.byref(fr))
    if hr < 0:
        raise OSError("GetNextFrame " + hr_hex(hr))
    try:
        tex = fr.pFrameTexture
        if not tex:
            raise OSError("null texture")
        lr = NUI_LOCKED_RECT()
        r = _vtbl(tex, _VT_LOCKRECT, _LockRect)(tex, 0, C.byref(lr), None, 0)
        if r < 0:
            raise OSError("LockRect " + hr_hex(r))
        try:
            raw = C.string_at(lr.pBits, lr.size); pitch = lr.Pitch
        finally:
            _vtbl(tex, _VT_UNLOCKRECT, _UnlockRect)(tex, 0)
        return raw, dict(pitch=pitch, size=len(raw), frame=fr.dwFrameNumber, ts=fr.liTimeStamp, type=fr.eImageType,
                         res=fr.eResolution, flags=fr.dwFrameFlags)
    finally:
        s._call(V_STREAM_RELEASE, _F_relframe)(s.p, h, C.byref(fr))


def decode(raw, t, res):
    w, hgt = DIMS[res]
    a = np.frombuffer(raw, dtype=np.uint8)
    if t in (T_COLOR, T_YUV):
        return a.reshape(hgt, w, 4)[..., :3].astype(np.float64)       # B, G, R
    if t == T_BAYER:
        return a.reshape(hgt, w).astype(np.float64)
    if t == T_RAWYUV:
        return a.reshape(hgt, w * 2).astype(np.float64)
    if t == T_DEPTH:
        return (np.frombuffer(raw, dtype=np.uint16).reshape(hgt, w) >> 3).astype(np.float64)
    raise ValueError(t)


def session(s, name, t, res, settle, secs, keep_last=None):
    w, hgt = DIMS[res]
    h = s.open_stream(t, res, 0, 2)
    time.sleep(settle)
    # auto-exposure must be settled before the capture window (added after run 1: COLOR1280 was still converging after
    # 2.5 s): drain frames until the last 5 frame means agree within 2 %, at most 8 s; the wait is recorded.
    tw, recent = time.time(), []
    while time.time() - tw < 8.0:
        try:
            raw, m = grab(s, h, 3000)
        except OSError:
            continue
        if m['type'] != t or m['res'] != res or m['size'] != w * hgt * BPP[t]:
            continue
        recent = (recent + [float(np.frombuffer(raw, dtype=np.uint8)[::97].mean())])[-5:]
        if len(recent) == 5 and (max(recent) - min(recent)) <= 0.02 * max(np.mean(recent), 1e-6):
            break
    settle_wait = time.time() - tw
    meta, acc, fm, n = [], None, [], 0
    halves = [None, None]
    t0 = time.time()
    while time.time() - t0 < secs:
        try:
            raw, m = grab(s, h, 3000)
        except OSError as e:
            meta.append(dict(error=str(e))); continue
        if m['type'] != t or m['res'] != res or m['size'] != w * hgt * BPP[t]:
            meta.append(dict(stale=True, **m)); continue
        img = decode(raw, t, res)
        acc = img if acc is None else acc + img
        fm.append(float(img.mean())); meta.append(m); n += 1
        if keep_last is not None:
            keep_last[name] = img
    settings = read_settings(s)
    good = [m for m in meta if 'ts' in m and not m.get('stale')]
    ts = np.array([m['ts'] for m in good], dtype=np.float64); fn = np.array([m['frame'] for m in good])
    info = dict(name=name, type=t, res=res, frames=n, ae_wait_s=round(settle_wait, 2), stale=sum(1 for m in meta if m.get('stale')),
                errors=[m['error'] for m in meta if 'error' in m][:3],
                size=good[0]['size'] if good else None, pitch=good[0]['pitch'] if good else None,
                fps=float((len(ts) - 1) / ((ts[-1] - ts[0]) / 1000.0)) if len(ts) > 2 else None,
                dt_ms=sorted(set(np.diff(ts).round(1).tolist())) if len(ts) > 2 else None,
                frame_number_steps=sorted(set(np.diff(fn).tolist())) if len(fn) > 2 else None,
                frame_mean_range=[min(fm), max(fm)] if fm else None, settings=settings)
    print(f"  {name}: {n} frames, fps {info['fps']}, size {info['size']} pitch {info['pitch']}, "
          f"mean {info['frame_mean_range']}, slot30 {settings.get('_slot30_hr')}")
    return info, (acc / n if n else None)


def mapper_points(s):
    m = C.c_void_p()
    hr = s._call(V_GET_MAPPER, _F_getptr)(s.p, C.byref(m))
    out = dict(get_mapper_hr=hr_hex(hr), points=[])
    if hr < 0:
        return out, None
    f = _vtbl(m, M_DEPTH_POINT_TO_COLOR, _F_pt2col)
    for z in (1000, 2000, 3000):
        for (x, y) in ((40, 40), (320, 240), (600, 40), (40, 440), (600, 440), (160, 120), (480, 360)):
            dp = NUI_DEPTH_IMAGE_POINT(x, y, z, 0)
            row = dict(x=x, y=y, z=z)
            for t, tn in ((T_COLOR, 'COLOR'), (T_BAYER, 'BAYER'), (T_RAWYUV, 'RAWYUV')):
                for res, rn in ((R640, '640'), (R1280, '1280')):
                    cp = NUI_COLOR_IMAGE_POINT()
                    r = f(m, R640, C.byref(dp), t, res, C.byref(cp))
                    row[f'{tn}_{rn}'] = [cp.x, cp.y] if r >= 0 else hr_hex(r)
            out['points'].append(row)
    return out, m


def map_frame(m, depth_mm):
    n = depth_mm.size
    buf = np.zeros((n, 2), dtype=np.uint16)                     # NUI_DEPTH_IMAGE_PIXEL {USHORT playerIndex; USHORT depth}
    buf[:, 1] = np.clip(depth_mm, 0, 65535).astype(np.uint16).ravel()
    pts = np.zeros((n, 2), dtype=np.int32)                      # NUI_COLOR_IMAGE_POINT {LONG x; LONG y}
    hr = _vtbl(m, M_DEPTH_FRAME_TO_COLOR, _F_frm2col)(m, R640, n, buf.ctypes.data_as(C.POINTER(NUI_DEPTH_IMAGE_PIXEL)),
                                                       T_COLOR, R640, n, pts.ctypes.data_as(C.POINTER(NUI_COLOR_IMAGE_POINT)))
    return hr, pts.reshape(depth_mm.shape[0], depth_mm.shape[1], 2).copy()


# ------------------------------------------------------------------------------------------------ analysis side
def grey(bgr):
    return bgr.mean(axis=2)


def ncc(a, b):
    a = a - a.mean(); b = b - b.mean()
    return float((a * b).sum() / np.sqrt((a * a).sum() * (b * b).sum()))


def fit_640_1280(g640, g1280):
    from scipy.ndimage import map_coordinates, uniform_filter
    from scipy.optimize import minimize
    src = uniform_filter(g1280, 2)                                 # 2x2 box ~ what binning/scaling would do
    YY, XX = np.mgrid[40:440, 40:600].astype(np.float64)
    TGT = g640[40:440, 40:600]

    def score(p, step=1):
        sx, sy, tx, ty = p
        yy, xx, tgt = YY[::step, ::step], XX[::step, ::step], TGT[::step, ::step]
        smp = map_coordinates(src, [sy * yy + ty + 0.5, sx * xx + tx + 0.5], order=1, mode="nearest")
        return -ncc(smp, tgt)             # src[j] = mean(g[j-1], g[j]) is centred at j-0.5 -> sample at centre+0.5
    best = None
    for sx in np.arange(1.90, 2.141, 0.02):
        for sy in np.arange(1.90, 2.201, 0.02):
            for tx in (-20, -10, 0.5, 10, 20):
                for ty in (-40, -20, 0.5, 20, 40):
                    v = score((sx, sy, tx, ty), 4)
                    if best is None or v < best[0]:
                        best = (v, (sx, sy, tx, ty))
    r = minimize(score, best[1], method='Nelder-Mead', options=dict(xatol=1e-4, fatol=1e-7, maxiter=4000))
    sx, sy, tx, ty = r.x
    nominal = -score((2.0, 2.0, 0.5, 0.5))
    return dict(sx=float(sx), sy=float(sy), tx=float(tx), ty=float(ty), ncc=float(-r.fun), ncc_at_nominal_2x=float(nominal),
                grid_start=[float(v) for v in best[1]])


def bayer_vs_color(bay, col):
    out = {}
    names = ['B', 'G', 'R']
    for py in (0, 1):
        for px in (0, 1):
            b = bay[py::2, px::2].ravel()
            fits = {}
            for ci, cn in enumerate(names):
                c = col[py::2, px::2, ci].ravel()
                sel = (b > 3) & (b < 250) & (c > 3) & (c < 250)
                A = np.vstack([b[sel], np.ones(sel.sum())]).T
                coef, *_ = np.linalg.lstsq(A, c[sel], rcond=None)
                pred = A @ coef
                r2 = 1 - np.var(c[sel] - pred) / np.var(c[sel])
                q = np.polyfit(b[sel], c[sel], 2)
                fits[cn] = dict(slope=float(coef[0]), intercept=float(coef[1]), r2=float(r2),
                                rms=float(np.std(c[sel] - pred)), quad=float(q[0]))
            order = sorted(fits, key=lambda k: -fits[k]['r2'])
            assigned = order[0] if (fits[order[0]]['r2'] >= 0.95 and fits[order[0]]['r2'] - fits[order[1]]['r2'] >= 0.02) else None
            out[f'({py},{px})'] = dict(fits=fits, assigned=assigned)
    pattern = [out[k]['assigned'] for k in ('(0,0)', '(0,1)', '(1,0)', '(1,1)')]
    ident = all(out[k]['assigned'] and 0.95 <= out[k]['fits'][out[k]['assigned']]['slope'] <= 1.05 and
                abs(out[k]['fits'][out[k]['assigned']]['intercept']) <= 3 for k in out)
    return dict(phases=out, pattern=''.join(p or '?' for p in pattern), B2=('IDENTITY' if ident else 'HOST-PROCESSED'))


def registration(depth, col, colpts):
    from scipy.ndimage import sobel, map_coordinates
    g = grey(col)
    gm = np.hypot(sobel(g, 1), sobel(g, 0))
    z = depth
    fg = np.zeros_like(z, dtype=bool)
    for dy, dx in ((0, 1), (1, 0)):
        a = z[:z.shape[0] - dy, :z.shape[1] - dx]; b = z[dy:, dx:]
        valid = (a > 0) & (b > 0)
        jump = valid & (np.abs(a - b) > 50)
        fg[:z.shape[0] - dy, :z.shape[1] - dx] |= jump & (a < b)   # foreground = nearer side
        fg[dy:, dx:] |= jump & (b < a)
    ys, xs = np.where(fg)
    cx = colpts[ys, xs, 0].astype(np.float64); cy = colpts[ys, xs, 1].astype(np.float64)
    ok = (cx > 5) & (cx < 634) & (cy > 5) & (cy < 474)
    cx, cy = cx[ok], cy[ok]
    shifts = np.arange(-6, 6.01, 0.5)
    S = np.zeros((shifts.size, shifts.size))
    for i, dy in enumerate(shifts):
        for j, dx in enumerate(shifts):
            S[i, j] = map_coordinates(gm, [cy + dy, cx + dx], order=1).mean()
    i, j = np.unravel_index(np.argmax(S), S.shape)
    DY, DX = np.meshgrid(shifts, shifts, indexing='ij')
    far = np.hypot(DX, DY) >= 4
    contrast = float(S[i, j] / S[far].mean())
    mag = float(np.hypot(shifts[j], shifts[i]))
    verdict = ('NO VERDICT' if contrast < 1.2 else 'CONSISTENT <= 1 px' if mag <= 1.0 else 'OFFSET' if mag > 1.5 else 'NO VERDICT')
    return dict(edge_points=int(cx.size), best_dx=float(shifts[j]), best_dy=float(shifts[i]), contrast=contrast, verdict=verdict,
                profile_dx_at_best_dy=[round(float(v), 3) for v in S[i, :]], profile_dy_at_best_dx=[round(float(v), 3) for v in S[:, j]])


def yuv_analysis(rawyuv, yuvrgb, col640):
    # byte positions 0..3 within each 2-pixel group
    grp = rawyuv.reshape(480, 320, 4)
    L = grey(yuvrgb)                                       # SDK's RGB from the YUV stream
    Lp = L.reshape(480, 320, 2)
    cors = {}
    for k in range(4):
        cors[k] = [ncc(grp[..., k], Lp[..., 0]), ncc(grp[..., k], Lp[..., 1])]
    luma = [k for k in range(4) if max(cors[k]) > 0.9]
    order = 'UYVY' if luma == [1, 3] else 'YUYV' if luma == [0, 2] else f'unclear (luma bytes {luma})'
    out = dict(byte_corr_with_luma={str(k): [round(v, 4) for v in cors[k]] for k in cors}, Y1=order)
    if order in ('UYVY', 'YUYV'):
        yi = (1, 3) if order == 'UYVY' else (0, 2); ui, vi = ((0, 2) if order == 'UYVY' else (1, 3))
        Y = np.empty((480, 640)); Y[:, 0::2] = grp[..., yi[0]]; Y[:, 1::2] = grp[..., yi[1]]
        U = np.repeat(grp[..., ui], 2, axis=1); V = np.repeat(grp[..., vi], 2, axis=1)
        out['Y_range'] = [float(Y.min()), float(np.percentile(Y, 0.1)), float(np.percentile(Y, 99.9)), float(Y.max())]
        out['UV_range'] = [float(min(U.min(), V.min())), float(max(U.max(), V.max()))]
        # SDK YUV->RGB conversion: least squares R,G,B = M [Y, U-128, V-128] + c
        X = np.vstack([Y.ravel(), U.ravel() - 128, V.ravel() - 128, np.ones(Y.size)]).T
        M = {}
        for ci, cn in ((2, 'R'), (1, 'G'), (0, 'B')):
            tgt = yuvrgb[..., ci].ravel(); sel = (tgt > 5) & (tgt < 250)
            coef, *_ = np.linalg.lstsq(X[sel], tgt[sel], rcond=None)
            M[cn] = dict(coef=[round(float(c), 4) for c in coef], rms=float(np.std(tgt[sel] - X[sel] @ coef)))
        out['sdk_yuv_to_rgb_fit'] = M
        # tone: Y(raw YUV stream) vs luma of the COLOR (Bayer-path) stream, same scene, sequential sessions
        Lc = 0.299 * col640[..., 2] + 0.587 * col640[..., 1] + 0.114 * col640[..., 0]
        sel = (Lc >= 20) & (Lc <= 200) & (Y > 16) & (Y < 250)
        k, loga = np.polyfit(np.log(Lc[sel]), np.log(Y[sel]), 1)
        bins = np.arange(20, 205, 10)
        curve = [[float(b), float(np.median(Y[sel & (Lc >= b) & (Lc < b + 10)]))] for b in bins if (sel & (Lc >= b) & (Lc < b + 10)).sum() > 200]
        out['Y2'] = dict(k=float(k), a=float(np.exp(loga)), n=int(sel.sum()), curve=curve,
                         verdict=('RGB-PATH LINEAR vs YUV' if 0.35 <= k <= 0.60 else 'SAME TONE CURVE' if 0.85 <= k <= 1.15 else 'NO VERDICT'))
        out['static_check_ncc_yuvrgb_vs_color'] = ncc(L, grey(col640))
    return out


def settings_verdict(infos):
    st = [i['settings'] for i in infos if i.get('settings')]
    if not st:
        return 'NO DATA'
    s0 = st[0]
    if s0.get('_slot30_hr') != '0x00000000':
        return 'GATED' if s0.get('_slot30_hr') == '0x8301000F' else f"FAILED slot30 {s0.get('_slot30_hr')}"
    ok = sum(1 for k, v in s0.items() if isinstance(v, dict) and v.get('hr') == '0x00000000')
    gated = [k for k, v in s0.items() if isinstance(v, dict) and v.get('hr') == '0x8301000F']
    return 'OPEN' if ok >= 30 else 'GATED' if gated else f'PARTIAL ({ok}/34 S_OK)'


def main():
    run = sys.argv[1] if len(sys.argv) > 1 else 'geo'
    print("below-normal priority:", below_normal_priority())
    s = Sensor(); print("verify:", s.verify())
    s.initialize(INIT_DEPTH | INIT_COLOR)
    infos, means, res = [], {}, {}
    mapper, mp = None, None
    try:
        if run == 'geo':
            plan = [('COLOR640', T_COLOR, R640, 2.0, 2.0), ('COLOR1280', T_COLOR, R1280, 2.5, 3.0),
                    ('BAYER1280', T_BAYER, R1280, 2.5, 3.0), ('BAYER640', T_BAYER, R640, 2.0, 2.0)]
        elif run == 'b1280':
            plan = [('COLOR1280', T_COLOR, R1280, 1.0, 3.0), ('BAYER1280', T_BAYER, R1280, 1.0, 3.0)]
        else:
            plan = [('RAWYUV640', T_RAWYUV, R640, 1.5, 3.0), ('YUV640', T_YUV, R640, 1.5, 3.0), ('COLOR640', T_COLOR, R640, 1.0, 2.0)]
        for name, t, r, settle, secs in plan:
            info, mean = session(s, name, t, r, settle, secs)
            infos.append(info); means[name] = mean
        if run == 'geo':
            # depth + colour together for registration
            hd = s.open_stream(T_DEPTH, R640, 0, 2)
            hc = s.open_stream(T_COLOR, R640, 0, 2)
            time.sleep(1.5)
            D, Cc = [], []
            for _ in range(12):
                rd, md = grab(s, hd, 3000); rc, mc = grab(s, hc, 3000)
                if md['type'] == T_DEPTH and md['size'] == 640 * 480 * 2:
                    D.append(decode(rd, T_DEPTH, R640))
                if mc['type'] == T_COLOR and mc['size'] == 640 * 480 * 4:
                    Cc.append(decode(rc, T_COLOR, R640))
            Dm = np.median(np.stack(D), axis=0); Cm = np.mean(np.stack(Cc), axis=0)
            mp, mapper = mapper_points(s)
            if mapper is not None:
                hr, colpts = map_frame(mapper, Dm)
                res['map_frame_hr'] = hr_hex(hr)
                if hr >= 0:
                    res['R1'] = registration(Dm, Cm, colpts)
                _vtbl(mapper, M_RELEASE, _F_ref)(mapper)
            res['mapper'] = mp
    finally:
        s.shutdown(); s.release()
    # ---------------- analysis
    res['sessions'] = [{k: v for k, v in i.items() if k != 'settings'} for i in infos]
    res['settings'] = {i['name']: i['settings'] for i in infos}
    res['S1'] = settings_verdict(infos)
    res['F1'] = {i['name']: dict(fps=i['fps'], doc=DOC_FPS.get((i['type'], i['res'])),
                                 matches_doc=(i['fps'] is not None and abs(i['fps'] - DOC_FPS[(i['type'], i['res'])]) <= 0.1 * DOC_FPS[(i['type'], i['res'])]))
                 for i in infos}
    if run == 'geo':
        g1 = fit_640_1280(grey(means['COLOR640']), grey(means['COLOR1280']))
        v = ('SAME FIELD (2x)' if abs(g1['sx'] - 2) < 0.01 and abs(g1['sy'] - 2) < 0.01 and abs(g1['tx'] - 0.5) < 1.5
             and abs(g1['ty'] - 0.5) < 1.5 and g1['ncc'] > 0.9 else 'CROP' if min(g1['sx'], g1['sy']) < 1.9
             else 'ANAMORPHIC' if abs(g1['sx'] - g1['sy']) > 0.02 else 'NO VERDICT')
        g1['verdict'] = v; res['G1'] = g1
        res['B_1280'] = bayer_vs_color(means['BAYER1280'], means['COLOR1280'])
        res['B_640'] = bayer_vs_color(means['BAYER640'], means['COLOR640'])
        # G2
        pts = res.get('mapper', {}).get('points', [])
        dev = []
        for p in pts:
            for tn in ('COLOR', 'BAYER', 'RAWYUV'):
                a, b = p.get(f'{tn}_640'), p.get(f'{tn}_1280')
                if isinstance(a, list) and isinstance(b, list):
                    dev.append(max(abs(b[0] - 2 * a[0]), abs(b[1] - 2 * a[1])))
        res['G2'] = dict(max_dev_px=(max(dev) if dev else None), n=len(dev),
                         verdict=('SAME-FIELD MAPPING' if dev and max(dev) <= 1 else 'SEE NUMBERS'))
    elif run == 'b1280':
        res['B_1280'] = bayer_vs_color(means['BAYER1280'], means['COLOR1280'])
    else:
        res['YUV'] = yuv_analysis(means['RAWYUV640'], means['YUV640'], means['COLOR640'])
    out = os.path.join(HERE, f'colour_probe_{run}_result.json')
    json.dump(res, open(out, 'w'), indent=1, default=str)
    brief = {k: v for k, v in res.items() if k in ('S1', 'F1', 'G1', 'G2', 'R1', 'map_frame_hr')}
    if 'B_1280' in res:
        brief['B_1280'] = dict(pattern=res['B_1280']['pattern'], B2=res['B_1280']['B2'])
        if 'B_640' in res:
            brief['B_640'] = dict(pattern=res['B_640']['pattern'], B2=res['B_640']['B2'])
    if 'YUV' in res:
        brief['YUV'] = {k: v for k, v in res['YUV'].items() if k in ('Y1', 'Y_range', 'UV_range', 'Y2', 'static_check_ncc_yuvrgb_vs_color')}
    print(json.dumps(brief, indent=1, default=str)[:6000])
    print("saved", out)


if __name__ == '__main__':
    main()
