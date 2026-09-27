"""Signed four-edge test (2026-09-27; rule fixed before running, from the independent review): is the depth outline of an object
inset relative to its IR outline (same camera), or merely shifted?
Object: a rectangle that is IR-dark against a bright wall AND stands clear of the wall in depth (the black backing board, ~7 cm).
Per edge: profiles perpendicular to the edge, averaged over the middle half of the edge; IR contour = half-level crossing between the
object's and the background's IR levels; depth contour = 0.5 crossing of the object-mask fraction (mask = depth within 35 mm of the
object plane). Signed offset = depth contour minus IR contour, positive = INWARD (the depth outline is smaller on that side).
RULE (fixed before running): report the signed 4-tuple. Call it an INSET only if all measurable edges are inward by >= 1 px and agree
within 1 px. A horizontal-only (left/right, opposite-sign) pattern is an image-to-image offset, not an inset. An edge with more than one
crossing, or whose background is not the wall, is marked unmeasurable.
CORRECTION before any verdict (2026-09-27): the first run used a mistyped bounding box and a 35 mm mask tolerance, which leaks into the
wall when the object stands only 40-65 mm off it; the tolerance is now an argument (default 35; use ~1/3 of the object-wall gap).
usage: python four_edges.py capture.npz y0,y1,x0,x1 [tol_mm] (the object's bounding box, from the depth preview)"""
import sys, warnings
import numpy as np
from scipy import ndimage
warnings.simplefilter('ignore')
z = np.load(sys.argv[1]); Dr = z['D']; D = Dr.astype(float); D[Dr == 0] = np.nan; Z = np.nanmedian(D, 0)
I = ndimage.uniform_filter(z['I'].astype(float).mean(0) / 64, 3)
y0, y1, x0, x1 = (int(v) for v in sys.argv[2].split(','))
core = np.zeros(Z.shape, bool); core[y0 + 8:y1 - 8, x0 + 8:x1 - 8] = True
yy, xx = np.nonzero(core & ~np.isnan(Z)); c = np.linalg.lstsq(np.c_[np.ones(yy.size), xx, yy], Z[yy, xx], rcond=None)[0]
Yg, Xg = np.mgrid[:Z.shape[0], :Z.shape[1]]; TOL = float(sys.argv[3]) if len(sys.argv) > 3 else 35.0
M = (np.abs(Z - (c[0] + c[1] * Xg + c[2] * Yg)) <= TOL).astype(float)
print(f"object plane at centre {c[0] + c[1] * (x0 + x1) / 2 + c[2] * (y0 + y1) / 2:.1f} mm; IR inside {np.median(I[core]):.0f}")
def crossings(p, lvl):
    return [i + (lvl - p[i]) / (p[i + 1] - p[i]) for i in range(len(p) - 1) if (p[i] - lvl) * (p[i + 1] - lvl) < 0]
res = {}
for name, horiz, pos, lo_, hi_, inward in (("left", True, x0, y0, y1, +1), ("right", True, x1, y0, y1, -1), ("top", False, y0, x0, x1, +1), ("bottom", False, y1, x0, x1, -1)):
    a = lo_ + (hi_ - lo_) // 4; b = hi_ - (hi_ - lo_) // 4; span = np.arange(pos - 12, pos + 13)
    if horiz: pi, pm = I[a:b, span].mean(0), M[a:b, span].mean(0)
    else:     pi, pm = I[span, a:b].mean(1), M[span, a:b].mean(1)
    outside = pi[:4] if inward > 0 else pi[-4:]; inside = pi[-4:] if inward > 0 else pi[:4]
    ci = crossings(pi, (np.median(outside) + np.median(inside)) / 2); cm = crossings(pm, 0.5)
    ok = len(ci) == 1 and len(cm) == 1 and np.median(outside) > np.median(inside) + 30
    if ok:
        off = inward * (cm[0] - ci[0]); res[name] = off
        print(f"  {name:6s}: IR {span[0] + ci[0]:.2f}  depth {span[0] + cm[0]:.2f}  signed offset (+ = inward) {off:+.2f} px  "
              f"[IR out {np.median(outside):.0f} / in {np.median(inside):.0f}]")
    else:
        print(f"  {name:6s}: UNMEASURABLE (IR crossings {len(ci)}, depth crossings {len(cm)}, IR out {np.median(outside):.0f} / in {np.median(inside):.0f})")
v = list(res.values())
inset = len(v) >= 3 and all(o >= 1 for o in v) and (max(v) - min(v)) <= 1
lr = [res[k] for k in ("left", "right") if k in res]
print("signed tuple:", {k: round(x, 2) for k, x in res.items()})
print("READING:", "INSET" if inset else ("left/right opposite signs -> image offset, not an inset" if len(lr) == 2 and lr[0] * lr[1] < 0 else "no inset by the rule (report the tuple)"))
