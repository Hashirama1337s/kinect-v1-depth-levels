"""colour_ptc.py -- is RAW_BAYER linear, and what per-channel gains (white balance) sit on it? Photon-transfer probe (read-only).

Why: the public README calls COLOR_RAW_BAYER "linear, un-white-balanced". Tonight (colour_offline*.py, colour_probe.py):
the blue sites carry 2-5x the noise of green at the same signal (a per-channel gain upstream of the output), COLOR 640 equals
RAW_BAYER 640 at native sites (no host-side tone/WB), and the dim-light photon-transfer test was inconclusive because a large
signal-independent (high-gain) noise dominated. Exposure cannot be locked (INuiColorCameraSettings is gated, 0x8301000F), so the
photon-transfer curve -- temporal variance vs mean over the pixels of one static scene -- is the exposure-independent test.
NEEDS BRIGHT, STEADY LIGHT (a lamp or daylight on a still scene); in dim light it reports NOT BRIGHT ENOUGH.

Run: python colour_ptc.py      RAW_BAYER 640 (~3 s, ~90 frames) then RAW_BAYER 1280 (~4 s, ~40 frames), after AE settles.
Keeps per-pixel sum / sum of squares and two single frames in memory; writes NUMBERS ONLY to colour_ptc_result.json.

Bars (fixed before any bright-light run):
  P0 PREMISE    scene mean >= 60 DN and frame means within +-2 % over the window; otherwise NOT BRIGHT ENOUGH / UNSTEADY (no verdict).
  P1 LINEARITY  per phase: slope of log(temporal var) vs log(mean) over bins in [30, 200] DN, flat pixels only (spatial gradient
                below median), temporal outliers masked (pixel SD > 5x the bin median). LINEAR-LIKE if slope >= 0.6 in all four
                phases; TONE-CURVE if slope <= 0.2 in all four and the lowest-bin variance <= 10 DN^2; otherwise NO VERDICT.
  P2 WB GAINS   (only if P1 = LINEAR-LIKE) channel gain ratio = (var/mean) of the channel / (var/mean) of green, in the common
                mean range. Reported, no verdict: these are the white-balance gains the camera applied.
  P3 NOISE INDEPENDENCE  as colour_offline2.py N1 (frame first vs last): RAW-LIKE if every |corr| < 0.10.
AMENDMENT A1 (2026-09-27, after the DIM dry run, before any bright-light run): P1/P2 use only the central half of the field
  (|x - cx| < W/4 and |y - cy| < H/4). Reason: the dry run showed variance FALLING with mean, which a linear sensor cannot do
  at one gain; on-chip lens-shading correction (enabled in the published Xbox init of CMOS register 0x106) applies more gain
  towards the corners, so pooling the whole field mixes gains. Dry-run result (dim, P0 failed): kept as colour_ptc_dryrun.json.
"""
import os, sys, time, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from colour_probe import Sensor, grab, decode, INIT_DEPTH, INIT_COLOR, T_BAYER, R640, R1280, DIMS  # noqa: E402
from atlas_common import below_normal_priority                                                   # noqa: E402

PH = [(0, 0), (0, 1), (1, 0), (1, 1)]


def capture(s, res, settle, secs):
    w, hgt = DIMS[res]
    h = s.open_stream(T_BAYER, res, 0, 2)
    time.sleep(settle)
    tw, recent = time.time(), []
    while time.time() - tw < 8.0:                              # wait for auto-exposure to settle (<= 8 s)
        try:
            raw, m = grab(s, h, 3000)
        except OSError:
            continue
        if m['type'] != T_BAYER or m['size'] != w * hgt:
            continue
        recent = (recent + [float(np.frombuffer(raw, dtype=np.uint8)[::97].mean())])[-5:]
        if len(recent) == 5 and max(recent) - min(recent) <= 0.02 * max(np.mean(recent), 1e-6):
            break
    S = np.zeros((hgt, w)); SS = np.zeros((hgt, w)); n = 0; fm = []; first = last = None
    t0 = time.time()
    while time.time() - t0 < secs:
        try:
            raw, m = grab(s, h, 3000)
        except OSError:
            continue
        if m['type'] != T_BAYER or m['size'] != w * hgt:
            continue
        a = decode(raw, T_BAYER, res)
        S += a; SS += a * a; n += 1; fm.append(float(a.mean()))
        if first is None:
            first = a
        last = a
    mean = S / n; var = SS / n - mean ** 2
    return dict(mean=mean, var=var * n / max(n - 1, 1), n=n, fm=fm, first=first, last=last)


def box(a, k):
    from numpy.lib.stride_tricks import sliding_window_view
    p = k // 2
    return sliding_window_view(np.pad(a, p, mode='reflect'), (k, k)).mean(axis=(-2, -1))


def analyse(c):
    M, V, fm = c['mean'], c['var'], np.array(c['fm'])
    out = dict(frames=c['n'], scene_mean=float(M.mean()), frame_mean_spread=float((fm.max() - fm.min()) / fm.mean()))
    if M.mean() < 60:
        out['P0'] = 'NOT BRIGHT ENOUGH'
    elif out['frame_mean_spread'] > 0.04:
        out['P0'] = 'UNSTEADY'
    else:
        out['P0'] = 'OK'
    gy, gx = np.gradient(M); g = np.hypot(gx, gy); flat = g < np.median(g)
    Hh, Ww = M.shape
    yy, xx = np.mgrid[0:Hh, 0:Ww]
    central = (np.abs(xx - Ww / 2) < Ww / 4) & (np.abs(yy - Hh / 2) < Hh / 4)      # amendment A1
    flat_c = flat & central
    slopes, curves, lowvar, vm = {}, {}, {}, {}
    for p in PH:
        m = M[p[0]::2, p[1]::2]; v = V[p[0]::2, p[1]::2]; f = flat_c[p[0]::2, p[1]::2]
        xs, ys = [], []
        for a in np.arange(30, 200, 10):
            sel = f & (m >= a) & (m < a + 10)
            if sel.sum() < 150:
                continue
            vv = v[sel]; vv = vv[vv <= 25 * np.median(vv)]          # mask temporal outliers (SD > 5x median)
            xs.append(float(np.median(m[sel]))); ys.append(float(np.median(vv)))
        slopes[str(p)] = float(np.polyfit(np.log(xs), np.log(ys), 1)[0]) if len(xs) >= 4 else None
        curves[str(p)] = [[round(a, 1), round(b, 3)] for a, b in zip(xs, ys)]
        lowvar[str(p)] = ys[0] if ys else None
        vm[str(p)] = {round(a): b / a for a, b in zip(xs, ys)}
    out.update(slopes=slopes, curves=curves)
    sl = [x for x in slopes.values() if x is not None]
    if out['P0'] != 'OK' or len(sl) < 4:
        out['P1'] = 'NO VERDICT (premise)'
    elif all(x >= 0.6 for x in sl):
        out['P1'] = 'LINEAR-LIKE'
    elif all(x <= 0.2 for x in sl) and all(lv is not None and lv <= 10 for lv in lowvar.values()):
        out['P1'] = 'TONE-CURVE'
    else:
        out['P1'] = 'NO VERDICT'
    # green = the two diagonal phases (GRBG on this unit: (0,0),(1,1) green, (0,1) red, (1,0) blue)
    common = set.intersection(*[set(d) for d in vm.values()]) if all(vm.values()) else set()
    if out['P1'] == 'LINEAR-LIKE' and common:
        g = {k: np.mean([0.5 * (vm['(0, 0)'][k] + vm['(1, 1)'][k])]) for k in common}
        out['P2_gain_ratio_vs_green'] = {ph: float(np.median([vm[ph][k] / g[k] for k in common])) for ph in vm}
    # P3
    d = c['first'] - c['last']
    hp = np.empty_like(d)
    for p in PH:
        pl = d[p[0]::2, p[1]::2]; hp[p[0]::2, p[1]::2] = pl - box(pl, 15)
    cor = {}
    for name, (dy, dx) in {'same_colour_right_2px': (0, 2), 'same_colour_down_2px': (2, 0), 'adjacent_right_1px': (0, 1),
                           'adjacent_down_1px': (1, 0)}.items():
        a = hp[:hp.shape[0] - dy, :hp.shape[1] - dx]; b = hp[dy:, dx:]
        m = flat[:flat.shape[0] - dy, :flat.shape[1] - dx] & flat[dy:, dx:]
        u, w = a[m] - a[m].mean(), b[m] - b[m].mean()
        cor[name] = float((u * w).mean() / np.sqrt((u * u).mean() * (w * w).mean()))
    out['P3'] = dict(cor, verdict=('RAW-LIKE' if max(abs(x) for x in cor.values()) < 0.10 else 'NOT RAW-LIKE'))
    return out


def main():
    print("below-normal priority:", below_normal_priority())
    s = Sensor(); print("verify:", s.verify())
    s.initialize(INIT_DEPTH | INIT_COLOR)
    caps = {}
    try:
        caps['BAYER640'] = capture(s, R640, 1.5, 3.0)
        caps['BAYER1280'] = capture(s, R1280, 1.5, 4.0)
    finally:
        s.shutdown(); s.release()
    res = {k: analyse(c) for k, c in caps.items()}
    for k, r in res.items():
        print(k, {a: b for a, b in r.items() if a not in ('curves',)})
    json.dump(res, open(os.path.join(HERE, 'colour_ptc_result.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
