"""Two-position scale test (2026-09-26): the box at p1 and p2 (moved straight toward the camera; tape: 6 in = 152.4 mm, 'did my best').
Per position: face = flood fill (+-35 mm) from a seed; top edge = median over the middle half of columns of the first face row; bottom edge =
last row where >= 50 % of those columns are face (the glass-desk reflection below never reaches 50 %); width = median over the middle half
of the box's own rows of (rightmost - leftmost + 1). Depth = plane fit to the per-pixel temporal mean at the face centroid (sub-lattice).
Model per direction: pixels = F' * size / z_sdk + e  (F' = f / depth-scale; e = edge gain/loss in px, constant with distance). Two
positions -> F' and e. Box 330.2 x 218.4 mm (hand tape)."""
import numpy as np
from collections import deque
from scipy import ndimage
def load(fn, seed):
    D = np.load(fn)['D'].astype(float); V = D > 0; D[~V] = np.nan
    with np.errstate(all='ignore'): Z = np.nanmedian(D, 0); Zm = np.nanmean(D, 0)
    H, W = Z.shape; z0 = np.nanmedian(Z[seed[0] - 2:seed[0] + 3, seed[1] - 2:seed[1] + 3]); M = np.abs(Z - z0) < 35
    R = np.zeros_like(M); q = deque([seed]); R[seed] = True
    while q:
        y, x = q.popleft()
        for vy, vx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= vy < H and 0 <= vx < W and M[vy, vx] and not R[vy, vx]: R[vy, vx] = True; q.append((vy, vx))
    return Z, Zm, R
def box(fn, seed):
    Z, Zm, R = load(fn, seed)
    xs = np.nonzero(R.any(0))[0]; cols = np.arange(xs.min() + (xs.max() - xs.min()) // 4, xs.max() - (xs.max() - xs.min()) // 4 + 1)
    top = np.median([np.nonzero(R[:, x])[0].min() for x in cols])
    frac = R[:, cols].mean(1); rows_ok = np.nonzero(frac >= 0.5)[0]; bot = rows_ok.max()
    rows = np.arange(int(top) + int(bot - top) // 4, int(bot) - int(bot - top) // 4 + 1)
    w = np.array([np.ptp(np.nonzero(R[y])[0]) + 1 for y in rows if R[y].any()])
    core = ndimage.binary_erosion(R, iterations=2); core[int(bot) + 1:] = False
    cy, cx = np.nonzero(core); ok = ~np.isnan(Zm[cy, cx]); cy, cx = cy[ok], cx[ok]
    A = np.c_[np.ones(cy.size), cx - cx.mean(), cy - cy.mean()]; c = np.linalg.lstsq(A, Zm[cy, cx], rcond=None)[0]
    h = bot - top + 1
    print(f"{fn}: z {c[0]:.2f} mm | width {np.median(w):.0f} px (IQR {np.percentile(w, 25):.0f}-{np.percentile(w, 75):.0f}) | "
          f"top {top:.0f} bottom {bot} -> height {h:.0f} px | width/height px {np.median(w) / h:.4f} (true 330.2/218.4 = {330.2 / 218.44:.4f})")
    return c[0], float(np.median(w)), float(h)
z1, w1, h1 = box('pos_p1.npz', (195, 355)); z2, w2, h2 = box('pos_p2.npz', (190, 345))
dz = z1 - z2; print(f"SDK move {dz:.2f} mm vs tape 152.4 mm -> ratio {dz / 152.4:.4f}  (tape +-1/16 in = +-1.0 %, +-1/8 in = +-2.1 %)")
for nm, S, a, b in (('width', 330.2, w1, w2), ('height', 218.44, h1, h2)):
    x1, x2 = S / z1, S / z2; Fp = (b - a) / (x2 - x1); e = a - Fp * x1
    sF = np.hypot(1, 1) * 1.0 / (x2 - x1)          # +-1 px per reading (edge quantisation), propagated
    print(f"{nm:6s}: F' = {Fp:6.1f} px (+-{sF:.0f})  vs nominal 571.26 ({100 * (Fp / 571.26 - 1):+.1f} %);  edge term e = {e:+5.1f} px")
