"""Registration dots and the zero-order spot of the IR projector pattern, located in existing IR captures (no new capture).

The Kinect v1 dot pattern is a 3x3 arrangement of tiles; each tile has one brighter dot near its centre, and the central one sits on the
projector's zero-order direction (public description: Reichinger 2011, "Kinect Pattern Uncovered"). Each bright dot is found inside a search window (row band x
column band, set from a first look at the captures), refined to an intensity-weighted sub-pixel centroid (5x5, local 15x15 median
subtracted), and paired with the SDK depth around it (median of the per-pixel temporal medians in a 9x9 box).

Depth moves a projected dot only along the image row (epipolar lines ~ rows), so for every dot: col = c_inf - K / z, row = const,
where K = f*b in px*mm. PrimeSense's constants predict K = (120 / (2 * 0.1042)) px * 75 mm = 43 186 px*mm at 640 x 480.
The fit uses one shared K and one c_inf per dot, over all captures where the dot sits on a surface with valid depth.

Reported per dot: row (mean, sd across captures), c_inf, peak level, and 'energy' = background-subtracted 5x5 sum, divided by the
median 5x5 energy of the 20 brightest ordinary dots within +-40 px (so a registration dot's brightness is relative to its neighbours).

usage: python ir_regdots.py            (reads ../dark_room_*.npz)"""
import os, glob
import numpy as np
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = sorted(glob.glob(os.path.join(HERE, '..', 'dark_room_*.npz')))
# search windows (row0, row1, col0, col1) in the 640x480 IR image; generous in column because depth moves dots along rows
WIN = {'TL': (50, 85, 0, 60), 'TC': (45, 85, 240, 330), 'TR': (40, 80, 470, 545),
       'ML': (232, 268, 0, 70), 'MC': (232, 268, 250, 320), 'MR': (225, 262, 470, 545),
       'BL': (405, 450, 0, 60), 'BC': (405, 450, 240, 330), 'BR': (400, 440, 480, 560)}
K_NOMINAL = 120 / (2 * 0.1042) * 75


def load(f):
    z = np.load(f)
    I = (z['I'] >> 6).astype(np.float64).mean(0)                 # 10-bit payload, 20-frame mean
    D = z['D'].astype(np.float64); D[D == 0] = np.nan
    with np.errstate(all='ignore'):
        Z = np.nanmedian(D, 0)
    return I, Z


def find(I, Z, win):
    r0, r1, c0, c1 = win
    bg = ndimage.median_filter(I, 15)
    E = ndimage.uniform_filter(I - bg, 5) * 25                    # 5x5 background-subtracted energy
    sub = E[r0:r1, c0:c1].copy()
    pk = (sub == ndimage.maximum_filter(sub, 7))
    ys, xs = np.nonzero(pk)
    if ys.size < 2:
        return None
    e = sub[ys, xs]; o = np.argsort(-e)
    y, x = ys[o[0]] + r0, xs[o[0]] + c0
    sep = e[o[0]] / max(e[o[1]], 1e-9)                            # how much the winner stands out in its window
    # sub-pixel centroid
    y0, y1, x0, x1 = max(0, y - 2), min(I.shape[0], y + 3), max(0, x - 2), min(I.shape[1], x + 3)
    w = np.clip(I[y0:y1, x0:x1] - bg[y0:y1, x0:x1], 0, None)
    gy, gx = np.mgrid[y0:y1, x0:x1]
    cy, cx = (w * gy).sum() / w.sum(), (w * gx).sum() / w.sum()
    # neighbours: ordinary dots within +-40 px (excluding +-4 px around the winner)
    a0, a1, b0, b1 = max(0, y - 40), min(I.shape[0], y + 41), max(8, x - 40), min(I.shape[1], x + 41)
    En = E[a0:a1, b0:b1]; pn = (En == ndimage.maximum_filter(En, 5))
    pn[max(0, y - 4 - a0):y + 5 - a0, max(0, x - 4 - b0):x + 5 - b0] = False
    en = np.sort(En[pn])[::-1][:20]
    rel = E[y, x] / np.median(en) if en.size else np.nan
    zz = np.nanmedian(Z[max(0, y - 4):y + 5, max(8, x - 4):x + 5]) if x > 12 else np.nan
    return dict(row=cy, col=cx, peak=I[y, x], rel=rel, sep=sep, z=zz)


rows = []
for f in FILES:
    tag = os.path.basename(f)[10:-4]
    I, Z = load(f)
    for name, win in WIN.items():
        d = find(I, Z, win)
        if d is None:
            continue
        d.update(tag=tag, dot=name); rows.append(d)
        print(f"{tag:7s} {name}: row {d['row']:6.1f} col {d['col']:6.1f}  peak {d['peak']:5.0f}  rel {d['rel']:4.1f}  "
              f"stands out x{d['sep']:3.1f}  z {d['z']:6.0f}")

# fit col = c_inf[dot] - K / z with a shared K, using detections that stand out (sep >= 1.3) and have valid depth
use = [r for r in rows if r['sep'] >= 1.3 and np.isfinite(r['z'])]
dots = sorted({r['dot'] for r in use})
A = np.zeros((len(use), len(dots) + 1)); b = np.zeros(len(use))
for i, r in enumerate(use):
    A[i, dots.index(r['dot'])] = 1.0; A[i, -1] = -1.0 / r['z']; b[i] = r['col']
sol, *_ = np.linalg.lstsq(A, b, rcond=None)
res = b - A @ sol
print(f"\nshared fit over {len(use)} detections, {len(dots)} dots: K = {sol[-1]:.0f} px*mm (PrimeSense constants: {K_NOMINAL:.0f}); "
      f"residual sd {res.std(ddof=len(dots) + 1):.2f} px")
# K with only the dots that were seen at >= 2 clearly different depths carries the information; report the depth spread per dot
for j, d in enumerate(dots):
    rr = [r for r in use if r['dot'] == d]
    zs = [r['z'] for r in rr]
    print(f"  {d}: n {len(rr)}  row {np.mean([r['row'] for r in rr]):6.1f} (sd {np.std([r['row'] for r in rr]):.2f})  "
          f"c_inf {sol[j]:6.1f}  z range {min(zs):.0f}-{max(zs):.0f}  rel. brightness median {np.median([r['rel'] for r in rr]):.1f}")
# fixed-K version (K from the constants): c_inf per dot, and its scatter across captures
print(f"\nwith K fixed at {K_NOMINAL:.0f}: c_inf per dot (mean, sd over captures)")
for d in dots:
    ci = [r['col'] + K_NOMINAL / r['z'] for r in use if r['dot'] == d]
    print(f"  {d}: {np.mean(ci):6.1f}  sd {np.std(ci):.2f}  (n {len(ci)})")
