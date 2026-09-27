"""Does the IR camera's brightness auto-adjust to the scene?  (existing captures only)

Four captures share one camera pose (paper, paper1, phone, env): between them the operator added a bright paper stack (paper1), a
glossy phone that saturates and blooms (phone), and a dark backing board (env), so the frame-mean IR level changes a lot. An automatic
gain / exposure loop driven by the scene would move the level of every UNCHANGED wall pixel in the same direction as a correction.
Test: IR 20-frame mean in wall regions that no object touches in any of the four captures (depth within 15 mm across the captures),
compared with the frame mean over the whole image. Bar fixed before the run:
  NO SCENE-DRIVEN GAIN if the unchanged-wall level varies by <= 1 % across the captures while the frame mean varies by >= 10 %;
  GAIN MOVES if the wall level moves by >= 5 % in the direction that would offset the frame-mean change; otherwise no verdict.
Also reported: the frame-to-frame sd of the wall level within each 20-frame session (short-term stability).
usage: python ir_agc_check.py"""
import os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TAGS = ['paper', 'paper1', 'phone', 'env']
I, Z = {}, {}
for t in TAGS:
    z = np.load(os.path.join(HERE, '..', f'dark_room_{t}.npz'))
    I[t] = (z['I'] >> 6).astype(np.float64)
    D = z['D'].astype(np.float64); D[D == 0] = np.nan
    with np.errstate(all='ignore'):
        Z[t] = np.nanmedian(D, 0)
Zs = np.stack([Z[t] for t in TAGS])
with np.errstate(all='ignore'):
    same = np.all(np.isfinite(Zs), 0) & ((np.nanmax(Zs, 0) - np.nanmin(Zs, 0)) <= 15)
same[:, :20] = False; same[260:] = False                        # left edge invalid band; desk and its reflections below row 260
# keep only pixels far (>= 25 px) from anything that changed, so object glow / shadows cannot leak in
from scipy import ndimage
changed = ~same; changed[260:] = False
far = ~ndimage.binary_dilation(changed, iterations=25)
wall = same & far
print(f"unchanged-wall pixels used: {wall.sum()} ({100 * wall.mean():.1f} % of the frame)")
ref = None
for t in TAGS:
    fm = I[t].reshape(len(I[t]), -1).mean(1)
    wl = I[t][:, wall].mean(1)
    sat = (I[t].mean(0) >= 1015).mean()
    if ref is None:
        ref = (fm.mean(), wl.mean())
    print(f"  {t:6s}: frame mean {fm.mean():7.2f} ({100 * (fm.mean() / ref[0] - 1):+6.1f} %)   unchanged wall {wl.mean():7.2f} "
          f"({100 * (wl.mean() / ref[1] - 1):+6.2f} %)   within-session sd of the wall level {wl.std():.2f} ({100 * wl.std() / wl.mean():.2f} %)"
          f"   saturated px {100 * sat:.2f} %")
fms = np.array([I[t].mean() for t in TAGS]); wls = np.array([I[t][:, wall].mean() for t in TAGS])
fr = fms.max() / fms.min() - 1; wr = wls.max() / wls.min() - 1
# correlation sign: an AGC would make the wall level fall when the frame mean rises
c = np.corrcoef(fms, wls)[0, 1]
print(f"frame-mean range {100 * fr:.1f} %, unchanged-wall range {100 * wr:.2f} %, corr(frame mean, wall) {c:+.2f}")
if wr <= 0.01 and fr >= 0.10:
    print("VERDICT: NO SCENE-DRIVEN GAIN over this range")
elif wr >= 0.05 and c < 0:
    print("VERDICT: GAIN MOVES")
else:
    print("VERDICT: no verdict")
