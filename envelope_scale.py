"""Lateral-scale check against a factory-sized reference (2026-09-27): a US #10 envelope (4 1/8 x 9 1/2 in = 104.8 x 241.3 mm) on an
IR-dark black backing ~7 cm in front of a wall, ~1.27 m from the sensor. Rule sealed before measuring: envelope_prediction.json.
Method: IR image (the camera the depth is computed from), 20-frame mean, 3x3 smoothing; the envelope = the largest bright blob inside the
backing; edges = half-level crossings between envelope and background levels on profiles averaged over the middle half of each edge
(one crossing per edge required); z = plane fit of the backing depth on a ring around the envelope (sealed method) and, as a premise
check, the envelope's own depth plane; size_mm = px * z / f for f = 571.26 px (SDK nominal) and 575.82 px (120 / (2 x 0.1042)).
usage: python envelope_scale.py dark_room_env.npz"""
import sys, warnings
import numpy as np
from scipy import ndimage
warnings.simplefilter('ignore')
SPEC = (241.3, 104.8)
z = np.load(sys.argv[1]); Dr = z['D']; D = Dr.astype(float); D[Dr == 0] = np.nan; Zmed = np.nanmedian(D, 0); Zmean = np.nanmean(D, 0)
I = ndimage.uniform_filter(z['I'].astype(float).mean(0) / 64, 3)
win = I[150:300, 160:400]; lo, hi = np.percentile(win, 20), np.percentile(win, 97); thr = (lo + hi) / 2
lab, n = ndimage.label(ndimage.binary_opening(I > thr, iterations=2)); sizes = np.bincount(lab.ravel()); sizes[0] = 0
k = int(np.argmax(sizes)); ys, xs = np.nonzero(lab == k); r0, r1, c0, c1 = ys.min(), ys.max(), xs.min(), xs.max()
mr = slice(r0 + (r1 - r0) // 4, r1 - (r1 - r0) // 4 + 1); mc = slice(c0 + (c1 - c0) // 4, c1 - (c1 - c0) // 4 + 1)
def edges(p, off):
    top = np.median(p[len(p) // 2 - 5:len(p) // 2 + 5]); out = []
    for first, base, rng in ((True, np.median(p[:5]), range(0, len(p) // 2)), (False, np.median(p[-5:]), range(len(p) // 2, len(p) - 1))):
        lv = (base + top) / 2; xs_ = [i + (lv - p[i]) / (p[i + 1] - p[i]) for i in rng if (p[i] - lv) * (p[i + 1] - lv) < 0]
        out.append((off + (xs_[0] if first else xs_[-1]), len(xs_)))
    return out
he = edges(I[mr, c0 - 8:c1 + 9].mean(0), c0 - 8); ve = edges(I[r0 - 8:r1 + 9, mc].mean(1), r0 - 8)
ncross = [e[1] for e in he + ve]; w = he[1][0] - he[0][0]; h = ve[1][0] - ve[0][0]
print(f"edges x {he[0][0]:.2f} / {he[1][0]:.2f}, y {ve[0][0]:.2f} / {ve[1][0]:.2f}; crossings per edge {ncross}; {w:.2f} x {h:.2f} px, aspect {w / h:.3f} (#10 {SPEC[0] / SPEC[1]:.3f})")
def plane_at(mask, zmap, y, x):
    yy, xx = np.nonzero(mask); zz = zmap[mask]; ok = ~np.isnan(zz)
    c = np.linalg.lstsq(np.c_[np.ones(ok.sum()), xx[ok], yy[ok]], zz[ok], rcond=None)[0]; return c[0] + c[1] * x + c[2] * y
ring = ndimage.binary_dilation(lab == k, iterations=8) & ~ndimage.binary_dilation(lab == k, iterations=3)
env = np.zeros(Zmean.shape, bool); env[r0:r1 + 1, c0:c1 + 1] = True; core = ndimage.binary_erosion(env, iterations=6)
yc, xc = (r0 + r1) / 2, (c0 + c1) / 2
for label, zc in (("sealed: backing ring (median map)", plane_at(ring, Zmed, yc, xc)), ("premise check: envelope's own plane (mean map)", plane_at(core, Zmean, yc, xc))):
    for f in (571.26, 575.82):
        L, S = w * zc / f, h * zc / f
        print(f"{label:48s} z {zc:7.1f} mm  f {f}: {L:6.1f} x {S:6.1f} mm -> long {100 * (L / SPEC[0] - 1):+.2f} %, short {100 * (S / SPEC[1] - 1):+.2f} %")
