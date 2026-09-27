"""One box position for the scale test (2026-09-26): 90 depth frames (640x480, mm = raw >> 3), saved locally as pos_<tag>.npz (never published).
Reports for the box face (flood fill from --seed within +-35 mm): interior median depth (2-px-eroded face), 3-D edge-to-edge width per row
over the middle half of rows (X = (u -/+ 0.5 - 319.5) z_edge / f, f = 571.26), top and bottom rows, and a per-row profile of the bottom
edge (the box stands on a glass desk: a reflection would continue the face below its true bottom edge with slowly rising depth).
usage: python kinect_pos.py --tag=p1 [--seed=195,355]"""
import sys, time, os
from collections import deque
import numpy as np
from scipy import ndimage
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
arg = lambda k, d: next((a.split('=', 1)[1] for a in sys.argv if a.startswith(f'--{k}=')), d)
TAG = arg('tag', 'p'); SEED = tuple(int(v) for v in arg('seed', '195,355').split(',')); F = 571.26
if arg('load', ''):
    D = np.load(arg('load', ''))['D']
else:
    import nui
    k = nui.Kinect(nui.INIT_DEPTH)
    try:
        k.open_stream(nui.IMG_DEPTH, nui.RES_640x480); time.sleep(1.0)
        D = np.stack([(k.grab(nui.IMG_DEPTH, timeout_ms=3000)[0] >> 3).astype(np.int16) for _ in range(90)])
    finally:
        k.close()
    np.savez_compressed(os.path.join(HERE, f'pos_{TAG}.npz'), D=D)
Df = D.astype(float); Df[D == 0] = np.nan
with np.errstate(all='ignore'):
    Z = np.nanmedian(Df, 0); VF = (D > 0).mean(0)
H, W = Z.shape
z0 = np.nanmedian(Z[SEED[0] - 2:SEED[0] + 3, SEED[1] - 2:SEED[1] + 3]); M = np.abs(Z - z0) < 35
R = np.zeros_like(M); q = deque([SEED]); R[SEED] = True
while q:
    y, x = q.popleft()
    for vy, vx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
        if 0 <= vy < H and 0 <= vx < W and M[vy, vx] and not R[vy, vx]: R[vy, vx] = True; q.append((vy, vx))
core = ndimage.binary_erosion(R, iterations=2); zc = float(np.nanmedian(Z[core]))
with np.errstate(all='ignore'):
    Zmean = np.nanmean(Df, 0)                                 # per-pixel temporal mean: sub-lattice
cy, cx = np.nonzero(core); ok = ~np.isnan(Zmean[cy, cx]); cy, cx = cy[ok], cx[ok]
A = np.c_[np.ones(cy.size), cx - cx.mean(), cy - cy.mean()]; coef = np.linalg.lstsq(A, Zmean[cy, cx], rcond=None)[0]
res = Zmean[cy, cx] - A @ coef
print(f"[{TAG}] plane fit at the face centroid (row {cy.mean():.1f}, col {cx.mean():.1f}): {coef[0]:.2f} mm "
      f"(slope {coef[1]:+.4f} mm/col, {coef[2]:+.4f} mm/row; residual sd {res.std():.2f} mm over {cy.size} px)")
ys = np.nonzero(R.any(1))[0]; xs = np.nonzero(R.any(0))[0]; top, bot = ys.min(), ys.max()
rows = range(top + (bot - top) // 4, bot - (bot - top) // 4 + 1); wid = []
for y in rows:
    c = np.nonzero(R[y])[0]
    if c.size < 5: continue
    l, r = c.min(), c.max(); zl = np.nanmedian(Z[y, l + 2:l + 5]); zr = np.nanmedian(Z[y, r - 4:r - 1])
    wid.append((np.hypot((r + 0.5 - 319.5) * zr / F - (l - 0.5 - 319.5) * zl / F, zr - zl), r - l + 1))
wid = np.array(wid)
print(f"[{TAG}] face {R.sum()} px, interior median depth {zc:.1f} mm; valid in every frame (face) {np.mean(VF[core] == 1):.3f}")
print(f"  3-D width median {np.median(wid[:, 0]):.1f} mm (IQR {np.percentile(wid[:, 0], 25):.1f}-{np.percentile(wid[:, 0], 75):.1f}), "
      f"{np.median(wid[:, 1]):.0f} px; vs 330.2 -> {100 * (np.median(wid[:, 0]) / 330.2 - 1):+.2f} %")
cols = range(xs.min() + (xs.max() - xs.min()) // 4, xs.max() - (xs.max() - xs.min()) // 4 + 1)
tops = [np.nonzero(R[:, x])[0].min() for x in cols if R[:, x].any()]
print(f"  top edge row median {np.median(tops):.1f} (IQR {np.percentile(tops, 25):.0f}-{np.percentile(tops, 75):.0f}); face rows {top}-{bot}")
print("  bottom profile (row: fraction of middle columns in face, their median depth mm):")
for y in range(max(top, bot - 24), min(H, bot + 3)):
    inr = [R[y, x] for x in cols]; zz = [Z[y, x] for x in cols if R[y, x]]
    print(f"    {y}: {np.mean(inr):.2f}  {np.nanmedian(zz) if zz else float('nan'):.1f}")
