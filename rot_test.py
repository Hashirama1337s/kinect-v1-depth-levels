"""Rotation test (2026-09-26): p1 = box in its normal orientation (330.2 mm horizontal), p3 = the same box stood on end (330.2 mm vertical) on
a narrower 11.6 cm wooden support, both ~1.05 m. The bottom edge at p3 is read only in columns beside the support (wall 15 cm behind = clean
edge). Tape-independent comparison: the SAME physical length in pixels horizontally (p1) vs vertically (p3), scaled to one depth."""
import numpy as np, warnings
from collections import deque
from scipy import ndimage
warnings.simplefilter('ignore'); F = 571.26
def load(fn, seed, tol=35):
    D = np.load(fn)['D'].astype(float); D[D == 0] = np.nan; Z = np.nanmedian(D, 0); Zm = np.nanmean(D, 0); H, W = Z.shape
    z0 = np.nanmedian(Z[seed[0] - 2:seed[0] + 3, seed[1] - 2:seed[1] + 3]); M = np.abs(Z - z0) < tol
    R = np.zeros_like(M); q = deque([seed]); R[seed] = True
    while q:
        y, x = q.popleft()
        for vy, vx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= vy < H and 0 <= vx < W and M[vy, vx] and not R[vy, vx]: R[vy, vx] = True; q.append((vy, vx))
    return Z, Zm, R
def run_end(col):
    r = np.nonzero(col)[0]; e = r[0]
    for y in r[1:]:
        if y - e > 1: break
        e = y
    return r[0], e
def plane(Zm, R, rows):
    m = R.copy(); m[:rows[0]] = False; m[rows[1] + 1:] = False; m = ndimage.binary_erosion(m, iterations=2)
    cy, cx = np.nonzero(m); ok = ~np.isnan(Zm[cy, cx]); cy, cx = cy[ok], cx[ok]
    A = np.c_[np.ones(cy.size), cx - cx.mean(), cy - cy.mean()]; return np.linalg.lstsq(A, Zm[cy, cx], rcond=None)[0][0]
# p3
Z, Zm, R = load('pos_p3.npz', (150, 335))
xs = np.nonzero(R[100:200].any(0))[0] + 0; x0, x1 = xs.min(), xs.max()
te = {x: run_end(R[:, x]) for x in range(x0, x1 + 1) if R[:, x].any()}
ends = np.array([te[x][1] for x in te]); body_end = np.median(ends[ends < np.percentile(ends, 30) + 15])
side = [x for x in te if te[x][1] < body_end + 8 and x0 + 3 <= x <= x1 - 3]        # columns beside the support
sup = [x for x in te if te[x][1] >= body_end + 8]
top = np.median([te[x][0] for x in range(x0 + (x1 - x0) // 4, x1 - (x1 - x0) // 4 + 1) if x in te])
bot = np.median([te[x][1] for x in side]); h3 = bot - top + 1
rows = range(int(top + (bot - top) / 4), int(bot - (bot - top) / 4) + 1)
w3 = np.median([np.ptp(np.nonzero(R[y])[0]) + 1 for y in rows]); z3 = plane(Zm, R, (int(top), int(bot)))
below = [np.nanmedian(Z[int(bot) + 3:int(bot) + 8, x]) for x in side]
print(f"p3: z {z3:.2f} mm | top {top:.0f}, bottom {bot:.0f} (from {len(side)} side columns, IQR {np.percentile([te[x][1] for x in side], 25):.0f}-"
      f"{np.percentile([te[x][1] for x in side], 75):.0f}; depth just below {np.median(below):.0f} mm; support columns {min(sup) if sup else -1}-{max(sup) if sup else -1})")
print(f"    330.2 mm VERTICAL {h3:.0f} px | 218.4 mm HORIZONTAL {w3:.0f} px")
# p1
Z1, Zm1, R1 = load('pos_p1.npz', (195, 355)); z1 = 1043.13
rows1 = range(170, 245); w1 = np.median([np.ptp(np.nonzero(R1[y])[0]) + 1 for y in rows1])
print(f"p1: z {z1:.2f} mm | 330.2 mm HORIZONTAL {w1:.0f} px")
w1s = w1 * z1 / z3
print(f"330.2 mm at z = {z3:.1f}: horizontal {w1s:.1f} px (p1 scaled) vs vertical {h3:.0f} px -> vertical - horizontal = {h3 - w1s:+.1f} px")
for nm, S, px in (('330.2 vertical', 330.2, h3), ('218.4 horizontal', 218.44, w3), ('330.2 horizontal (p1)', 330.2, w1)):
    z = z1 if 'p1' in nm else z3; exp = F * S / z
    print(f"  {nm:22s}: {px:6.1f} px vs pinhole {exp:6.1f} px (f=571.26) -> {px - exp:+5.1f} px ({100 * (px / exp - 1):+.1f} %)")
