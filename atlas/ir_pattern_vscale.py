"""Vertical scale of the projected dot pattern from its registration dots (existing captures; a ruler for a planned laser mode-hop test).

The laser wavelength scales the whole diffraction pattern about its centre; depth moves dots only along image rows (measured: the
patch shift test gives |dy| ~ 0.04 px for 10 px of disparity), so the ROW distance between the top and bottom registration dots is a
depth-free measure of pattern scale. Dots (row, approximate column range) from ir_regdots.py: TL ~68, TR ~59.5, BL ~428, BR ~420.5.
Per frame: 5x5 background-subtracted centroid of the brightest dot in a +-5 row x column window (saturated plateaus are symmetric,
so the centroid still works). Vertical spans S_L = row(BL) - row(TL), S_R = row(BR) - row(TR).
Reported: per capture mean and frame-to-frame sd (the ruler's single-frame precision), and the spread across captures (22:01-00:33,
different poses and scenes; a warmed sensor). A 0.25 nm hop at 830 nm is a relative scale step of 3.0e-4 = ~0.11 px on a 360 px span.
usage: python ir_pattern_vscale.py"""
import os, glob
import numpy as np
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
WIN = {'TL': (63, 74, 0, 45), 'TR': (54, 65, 495, 530), 'BL': (422, 434, 12, 45), 'BR': (415, 426, 505, 535)}


def centroid(img, bg, win):
    r0, r1, c0, c1 = win
    E = ndimage.uniform_filter(img - bg, 5)[r0:r1, c0:c1]
    y, x = np.unravel_index(np.argmax(E), E.shape); y += r0; x += c0
    s1 = np.sort(E.ravel())[::-1]
    y0, y1, x0, x1 = y - 2, y + 3, max(0, x - 2), x + 3
    w = np.clip(img[y0:y1, x0:x1] - bg[y0:y1, x0:x1], 0, None)
    gy, gx = np.mgrid[y0:y1, x0:x1]
    return (w * gy).sum() / w.sum(), (w * gx).sum() / w.sum()


rows = {}
for f in sorted(glob.glob(os.path.join(HERE, '..', 'dark_room_*.npz'))):
    tag = os.path.basename(f)[10:-4]
    I = (np.load(f)['I'] >> 6).astype(np.float64)
    bgm = ndimage.median_filter(I.mean(0), 15)
    per = {d: np.array([centroid(fr, bgm, w)[0] for fr in I]) for d, w in WIN.items()}
    SL, SR = per['BL'] - per['TL'], per['BR'] - per['TR']
    rows[tag] = (SL.mean(), SL.std(), SR.mean(), SR.std(), {d: per[d].mean() for d in WIN})
    print(f"{tag:7s} TL {per['TL'].mean():6.2f} TR {per['TR'].mean():6.2f} BL {per['BL'].mean():6.2f} BR {per['BR'].mean():6.2f} | "
          f"S_L {SL.mean():7.3f} (frame sd {SL.std():.3f})  S_R {SR.mean():7.3f} (frame sd {SR.std():.3f})")
SLm = np.array([v[0] for v in rows.values()]); SRm = np.array([v[2] for v in rows.values()])
print(f"\nacross {len(rows)} captures: S_L {SLm.mean():.3f} sd {SLm.std():.3f} px ({SLm.std() / SLm.mean():.1e} rel);  "
      f"S_R {SRm.mean():.3f} sd {SRm.std():.3f} px ({SRm.std() / SRm.mean():.1e} rel)")
print("single-frame precision (median frame sd): S_L %.3f px (%.1e rel), S_R %.3f px (%.1e rel)" %
      (np.median([v[1] for v in rows.values()]), np.median([v[1] for v in rows.values()]) / SLm.mean(),
       np.median([v[3] for v in rows.values()]), np.median([v[3] for v in rows.values()]) / SRm.mean()))
