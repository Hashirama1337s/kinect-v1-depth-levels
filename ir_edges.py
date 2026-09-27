"""Tape-free edge check (2026-09-26): the IR image comes from the same camera the depth is computed from, so the box's silhouette in IR
intensity and its silhouette in depth can be compared edge by edge. Profiles across each edge, averaged over the middle half of the edge.
Prints IR mean (10-bit) and the depth-face fraction on the same pixel axis. usage: python ir_edges.py capture.npz seed_y,seed_x"""
import sys, warnings
import numpy as np
from collections import deque
warnings.simplefilter('ignore')
z = np.load(sys.argv[1]); seed = tuple(int(v) for v in sys.argv[2].split(','))
D = z['D'].astype(float); D[D == 0] = np.nan; Z = np.nanmedian(D, 0); H, W = Z.shape
I = z['I'].astype(float).mean(0) / 64
z0 = np.nanmedian(Z[seed[0] - 2:seed[0] + 3, seed[1] - 2:seed[1] + 3]); M = np.abs(Z - z0) < 35
R = np.zeros_like(M); q = deque([seed]); R[seed] = True
while q:
    y, x = q.popleft()
    for vy, vx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
        if 0 <= vy < H and 0 <= vx < W and M[vy, vx] and not R[vy, vx]: R[vy, vx] = True; q.append((vy, vx))
ys, xs = np.nonzero(R); 
rowR = R.sum(1); colR = R.sum(0)
body_rows = np.nonzero(rowR > 0.6 * np.median(rowR[rowR > 0]))[0]; body_cols = np.nonzero(colR > 0.6 * np.median(colR[colR > 0]))[0]
t, b = body_rows.min(), body_rows.max(); l, r = body_cols.min(), body_cols.max()
mr = slice(t + (b - t) // 4, b - (b - t) // 4 + 1); mc = slice(l + (r - l) // 4, r - (r - l) // 4 + 1)
print(f"{sys.argv[1]}: face body rows {t}-{b}, cols {l}-{r}, depth {z0:.0f} mm")
def show(name, ax_range, prof_I, prof_R):
    print(f"  {name}:")
    print("    px   : " + " ".join(f"{p:5d}" for p in ax_range))
    print("    IR   : " + " ".join(f"{v:5.0f}" for v in prof_I))
    print("    face : " + " ".join(f"{v:5.2f}" for v in prof_R))
for name, rng, get in (("LEFT edge (cols)", range(l - 8, l + 9), lambda p: (I[mr, p].mean(), R[mr, p].mean())),
                       ("RIGHT edge (cols)", range(r - 8, r + 9), lambda p: (I[mr, p].mean(), R[mr, p].mean())),
                       ("TOP edge (rows)", range(t - 8, t + 9), lambda p: (I[p, mc].mean(), R[p, mc].mean())),
                       ("BOTTOM edge (rows)", range(b - 8, b + 9), lambda p: (I[p, mc].mean(), R[p, mc].mean()))):
    v = [get(p) for p in rng]; show(name, list(rng), [a for a, _ in v], [c for _, c in v])
