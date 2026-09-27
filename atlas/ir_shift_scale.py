"""Does the IR image use the same pixel scale as the depth engine?  (existing captures only)

Physics: a projected dot hits the first surface along its ray; the IR camera sees it at column  c_inf - K / z  (row unchanged, because
the camera-projector baseline is horizontal). PrimeSense's constants (zero-plane distance 120 mm, pixel size 0.1042 mm at 1280 px,
emitter distance 75 mm) give K = f*b = 575.8 px * 75 mm = 43 186 px*mm in 640 x 480 pixels, and the SDK's millimetre table is built
from exactly those constants (lattice_closure.py). So if the 640x480 IR stream samples the scene on the depth engine's pixel grid, the
SAME pattern patch seen on a surface at z_A in one capture and at z_B in another capture (same camera pose, the object moved) is
displaced by  dx = K (1/z_A - 1/z_B)  with K = 43 186, and dy = 0.

Method: pairs of captures with the same pose (paper, paper1, phone, env: the operator added/removed a paper stack, a phone, an envelope
on a black backing; the camera did not move). Template = 31x31 patch of the band-passed IR mean (20 frames) in capture A where the SDK
depth is near-planar (temporal-median depth, 10-90 % spread <= 10 mm inside the patch). Search in capture B over dx -20..+20, dy -6..+6; NCC; sub-pixel
by a parabola through the peak in x and in y. Depth in B is read at the matched location. Keep matches with NCC >= 0.5 and
|1/z_A - 1/z_B| large enough that dx >= 3 px (so an error of 0.1 px is <= 3 %).
PASS bar (fixed before the run): median K within +-2 % of 43 186 and median |dy| <= 0.3 px -> 'IR pixels = depth-engine pixels'.
FAIL: K off by > 5 % (the IR stream would be a rescaled image) or |dy| > 1 px (a baseline not along rows).

usage: python ir_shift_scale.py"""
import os, itertools
import numpy as np
from scipy import ndimage, signal

HERE = os.path.dirname(os.path.abspath(__file__))
K0 = 120 / (2 * 0.1042) * 75
TAGS = ['paper', 'paper1', 'phone', 'env']


def load(tag):
    z = np.load(os.path.join(HERE, '..', f'dark_room_{tag}.npz'))
    I = (z['I'] >> 6).astype(np.float64).mean(0)
    B = ndimage.gaussian_filter(I, 0.7) - ndimage.gaussian_filter(I, 4)          # band-pass: keep the dots, drop shading
    B /= np.maximum(ndimage.gaussian_filter(np.abs(B), 8), 1e-6)                    # local contrast normalisation
    D = z['D'].astype(np.float64); D[D == 0] = np.nan
    with np.errstate(all='ignore'):
        Z = np.nanmedian(D, 0)
    return B, Z


def ncc(a, b):
    a = a - a.mean(); b = b - b.mean()
    return float((a * b).sum() / np.sqrt((a * a).sum() * (b * b).sum() + 1e-12))


def match(BA, BB, y, x, h=15, rx=20, ry=6):
    t = BA[y - h:y + h + 1, x - h:x + h + 1]
    y0, y1, x0, x1 = y - h - ry, y + h + ry + 1, x - h - rx, x + h + rx + 1
    if y0 < 0 or x0 < 8 or y1 > BB.shape[0] or x1 > BB.shape[1]:
        return -2, 0, 0, 0
    S = BB[y0:y1, x0:x1]; n = t.size
    tt = (t - t.mean()) / np.sqrt(((t - t.mean()) ** 2).sum())
    num = signal.correlate(S, tt, mode='valid', method='fft')
    ones = np.ones_like(t)
    s1 = signal.correlate(S, ones, mode='valid', method='fft'); s2 = signal.correlate(S * S, ones, mode='valid', method='fft')
    C = num / np.sqrt(np.maximum(s2 - s1 * s1 / n, 1e-12))
    iy, ix = np.unravel_index(np.argmax(C), C.shape); c = C[iy, ix]
    def para(m, c0, p):
        den = m - 2 * c0 + p
        return 0.0 if den >= 0 else 0.5 * (m - p) / den
    sx = para(C[iy, ix - 1], c, C[iy, ix + 1]) if 0 < ix < C.shape[1] - 1 else 0.0
    sy = para(C[iy - 1, ix], c, C[iy + 1, ix]) if 0 < iy < C.shape[0] - 1 else 0.0
    # second-best peak outside +-2 px: how unique the match is
    C2 = C.copy(); C2[max(0, iy - 2):iy + 3, max(0, ix - 2):ix + 3] = -2
    return c, iy - ry + sy, ix - rx + sx, float(C2.max())


data = {t: load(t) for t in TAGS}
allK, alldy = [], []
for A, Bt in itertools.permutations(TAGS, 2):
    BA, ZA = data[A]; BB, ZB = data[Bt]
    Ks, dys = [], []
    for y in range(40, 440, 12):
        for x in range(60, 600, 12):
            pa = ZA[y - 15:y + 16, x - 15:x + 16]
            if np.isnan(pa).mean() > 0.05 or np.nanpercentile(pa, 90) - np.nanpercentile(pa, 10) > 10:
                continue
            zA = np.nanmedian(pa)
            # expected shift if B has a different planar surface here: unknown a priori, so search
            c, dy, dx, c2 = match(BA, BB, y, x)
            if c < 0.5 or c2 > 0.6 * c:
                continue
            yb, xb = int(round(y + dy)), int(round(x + dx))
            pb = ZB[yb - 15:yb + 16, xb - 15:xb + 16]
            if pb.shape != (31, 31) or np.isnan(pb).mean() > 0.05 or np.nanpercentile(pb, 90) - np.nanpercentile(pb, 10) > 10:
                continue
            zB = np.nanmedian(pb); w = 1 / zA - 1 / zB
            if abs(K0 * w) < 3:
                continue
            Ks.append(dx / w); dys.append(dy)
    if Ks:
        Ks = np.array(Ks); dys = np.array(dys)
        print(f"{A:6s} -> {Bt:6s}: n {Ks.size:4d}  K median {np.median(Ks):7.0f}  IQR {np.percentile(Ks, 25):6.0f}-{np.percentile(Ks, 75):6.0f}"
              f"   dy median {np.median(dys):+.2f} px")
        allK += list(Ks); alldy += list(dys)
allK = np.array(allK); alldy = np.array(alldy)
if allK.size:
    k = np.median(allK)
    print(f"\nALL: n {allK.size}  K median {k:.0f} px*mm = {100 * (k / K0 - 1):+.2f} % vs {K0:.0f};  median dy {np.median(alldy):+.2f} px "
          f"(|dy| median {np.median(np.abs(alldy)):.2f})")
    ok = abs(k / K0 - 1) <= 0.02 and np.median(np.abs(alldy)) <= 0.3
    bad = abs(k / K0 - 1) > 0.05 or np.median(np.abs(alldy)) > 1
    print("VERDICT:", "PASS (IR pixels = depth-engine pixels)" if ok else "FAIL" if bad else "no verdict")
else:
    print("no usable patch pairs")
