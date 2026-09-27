"""Code-density test (2026-09-26; rule written before any data): are the Kinect v1's disparity codes all the same width?
Every depth simulator assumes equal 1/8-px codes; correlation sub-pixel estimators often 'peak-lock' toward whole pixels, which
would make codes near integer-pixel boundaries narrower or wider in a period-8 pattern (the ADC code-density / DNL test).
Target: a flat surface (the box's big face) turned steeply to the camera so it spans many codes. 300 depth frames per tilt.
Codes: from the exact closure (lattice_closure.py): SDK mm = floor(1 / (1/1200 - n D)), D = 0.1042/36000, so each observation's code
is n = round((1/1200 - 1/(z_mm + 0.5)) / D) (exact while one code step > 1 mm, i.e. z > ~0.6 m).
DNL_n = count_n / (16-code moving average of counts) - 1, for codes >= 8 away from both ends of the observed range and with
expected count >= 2000 (a 16-code window cancels any period-8 pattern exactly, so it only removes slow density changes: surface
bow, area per code). Fold DNL by n mod 8 -> 8 bin means; A8 = max |bin mean|. Null: 20 000 random permutations of the DNL values
over codes -> p. Negative controls (not part of the verdict): the same fold at periods 7 and 9.
SEALED VERDICT (both tilts required):
  PEAK-LOCKING : A8 >= 0.15 with p < 0.001 at BOTH tilts, and the most extreme bin's phase agrees within +-1 bin between tilts.
  UNIFORM      : every |bin mean| <= 0.05 at both tilts (codes equal to 5 %).
  otherwise    : no verdict (report the numbers).
AMENDMENT 1 (2026-09-26, after capture t1, BEFORE any further capture; thresholds above unchanged): t1 (ramp aligned with the image
rows, ~3 rows per code) is logged as an INVALID SETUP: whole-row sampling makes per-code counts jump by +-33 % (DNL rms 0.41-0.49), which
swamps a 0.15 effect. A capture now counts only if (a) the depth gradient of the face (plane fit to the median map) points 25-65 deg
from the image x axis (mod 90), i.e. iso-code bands cross the pixel grid diagonally, and (b) the all-code DNL rms <= 0.20. Both are
printed; the verdict ignores captures that fail them. (Original file sha256 prefix 8cc93df73e8c8caf.)
AMENDMENT 2 (2026-09-26, after t2; thresholds unchanged): the flood fill can leak into adjacent surfaces (t2: the face touches the side
wall -> 190k px, 0.8-3.2 m). Optional --box=y0,y1,x0,x1 clips the region to the object's outline, chosen from the depth preview BEFORE
the DNL of that region is computed. t2 frames 280-299 dropped (a cat entered: moved-pixel fraction 0.8-2.6 %); saved as code_t2trim.npz.
AMENDMENT 3 (2026-09-26, after t2; thresholds unchanged): catastrophic flicker (edge pixels jumping to the wall) spreads counts over
~140 codes for a ~50-code face. Observations more than 3 codes from their own pixel's median code are dropped, and only codes inside
the 2nd-98th percentile of the face's median-map codes are used (the population cleaning of the noise-population finding).
AMENDMENT 4 (2026-09-26, after the t2 pilot; thresholds unchanged): region = plane inliers: fit a plane to the median map on the
(clipped) flood region, keep pixels within 15 mm of it, refit, repeat once (excludes wall pixels inside the outline).
AMENDMENT 4 REVISED (same session, before any verdict): as first written it kept only 605 px (the first plane fit was biased by wall
pixels). The first fit now uses only a 31x31 patch around the seed (on the face), then grows inliers within the clip box.
NOT FROZEN (superseded, see STATUS). Originally: FROZEN after amendment 4: t1 = invalid setup, t2 = PILOT (the method was developed on it; never part of the verdict). The verdict
uses only captures taken after the freeze (t3, t4, ...), analysed with this file unchanged.
STATUS (2026-09-26 late): the box face is an inadequate target (small, bowed, touches the side wall). On the t2 pilot the period-8
fold moved with every reasonable cleaning choice (extreme bin 4 -> 6 -> 1; p 0.02-0.27), i.e. no robust signal and no result either
way. Iteration stopped deliberately (forking paths). Next design, to be written and sealed BEFORE capture: the room wall as the target
(large, rigid, flat), the Kinect turned ~45 deg to it and rolled on a book so iso-code bands cross the image diagonally (~200 codes).
usage: python code_density.py capture --tag=t1 [--frames=300]      (captures, saves code_<tag>.npz)
       python code_density.py analyse --tag=t1 --seed=y,x           (region = flood fill from seed, neighbour step <= 12 mm)
       python code_density.py verdict --tags=t1,t2"""
import sys, os, time, json
from collections import deque
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
arg = lambda k, d=None: next((a.split('=', 1)[1] for a in sys.argv if a.startswith(f'--{k}=')), d)
D = 0.1042 / 36000.0
def capture(tag, n):
    import nui
    k = nui.Kinect(nui.INIT_DEPTH)
    try:
        k.open_stream(nui.IMG_DEPTH, nui.RES_640x480); time.sleep(1.0)
        F = np.stack([(k.grab(nui.IMG_DEPTH, timeout_ms=3000)[0] >> 3).astype(np.int16) for _ in range(n)])
    finally:
        k.close()
    np.savez_compressed(os.path.join(HERE, f'code_{tag}.npz'), D=F); print(f"saved code_{tag}.npz {F.shape}")
def region(Z, seed, step=12.0):
    H, W = Z.shape; R = np.zeros(Z.shape, bool); q = deque([seed]); R[seed] = True
    while q:
        y, x = q.popleft()
        for vy, vx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= vy < H and 0 <= vx < W and not R[vy, vx] and not np.isnan(Z[vy, vx]) and abs(Z[vy, vx] - Z[y, x]) <= step:
                R[vy, vx] = True; q.append((vy, vx))
    return R
def fold(dnl, P):
    ph = np.arange(dnl.size) % P; return np.array([dnl[ph == b].mean() for b in range(P)])
def analyse(tag, seed):
    from scipy import ndimage
    F = np.load(os.path.join(HERE, f'code_{tag}.npz'))['D'].astype(float); F[F == 0] = np.nan
    with np.errstate(all='ignore'): Z = np.nanmedian(F, 0)
    R = region(Z, seed)
    if arg('box'):
        y0, y1, x0, x1 = (int(v) for v in arg('box').split(',')); clip = np.zeros_like(R); clip[y0:y1, x0:x1] = True; R &= clip
    P = np.zeros_like(R); P[seed[0] - 15:seed[0] + 16, seed[1] - 15:seed[1] + 16] = True; clipR = R.copy(); R = R & P
    for _ in range(3):
        yy, xx = np.nonzero(R); zz = Z[R]; ok = ~np.isnan(zz)
        c = np.linalg.lstsq(np.c_[np.ones(ok.sum()), xx[ok], yy[ok]], zz[ok], rcond=None)[0]
        Yg, Xg = np.mgrid[:Z.shape[0], :Z.shape[1]]; R = clipR & (np.abs(Z - (c[0] + c[1] * Xg + c[2] * Yg)) <= 15)
    R = ndimage.binary_erosion(R, iterations=3)
    obs = F[:, R]; med = np.nanmedian(obs, 0)
    toc = lambda v: np.rint((1 / 1200 - 1 / (v + 0.5)) / D)
    nm = toc(med); nobs = toc(obs); good = ~np.isnan(obs) & (np.abs(nobs - nm) <= 3)
    lo_c, hi_c = np.nanpercentile(nm, 2), np.nanpercentile(nm, 98)
    n = nobs[good & (nobs >= lo_c) & (nobs <= hi_c)].astype(np.int64); obs = obs[good]
    lo, hi = n.min(), n.max(); cnt = np.bincount(n - lo).astype(float)
    ma = np.convolve(cnt, np.ones(16) / 16, mode='same')
    keep = np.zeros(cnt.size, bool); keep[8:cnt.size - 8] = True; keep &= ma >= 2000
    codes = np.arange(lo, hi + 1)[keep]; dnl = cnt[keep] / ma[keep] - 1
    # fold on the ABSOLUTE code number so phases compare across tilts
    f8 = np.array([dnl[(codes % 8) == b].mean() for b in range(8)]); A8 = np.abs(f8).max()
    rng = np.random.default_rng(1); perm = np.array([np.abs(np.array([p[(codes % 8) == b].mean() for b in range(8)])).max()
                                                     for p in (rng.permutation(dnl) for _ in range(20000))])
    p = (1 + np.sum(perm >= A8)) / (1 + perm.size)
    A7 = np.abs([dnl[(codes % 7) == b].mean() for b in range(7)]).max(); A9 = np.abs([dnl[(codes % 9) == b].mean() for b in range(9)]).max()
    zr = (1 / (1 / 1200 - lo * D), 1 / (1 / 1200 - hi * D))
    yy, xx = np.nonzero(R); zz = Z[R]; ok = ~np.isnan(zz)
    gx, gy = np.linalg.lstsq(np.c_[np.ones(ok.sum()), xx[ok], yy[ok]], zz[ok], rcond=None)[0][1:]
    ang = float(np.degrees(np.arctan2(abs(gy), abs(gx)))); ang = min(ang % 90, 90 - ang % 90) if False else ang % 90
    res = {"tag": tag, "pixels": int(R.sum()), "observations": int(obs.size), "codes_used": int(keep.sum()), "z_range_mm": [round(zr[0]), round(zr[1])],
           "fold8": [round(v, 4) for v in f8], "A8": round(float(A8), 4), "p8": float(p), "extreme_bin": int(np.argmax(np.abs(f8))),
           "A7_control": round(float(A7), 4), "A9_control": round(float(A9), 4), "dnl_rms_all": round(float(dnl.std()), 4),
           "gradient_angle_deg": round(ang, 1), "valid_setup": bool(25 <= ang <= 65 and dnl.std() <= 0.20)}
    json.dump(res, open(os.path.join(HERE, f'code_{tag}.json'), 'w'), indent=1); print(json.dumps(res))
def verdict(tags):
    r = [json.load(open(os.path.join(HERE, f'code_{t}.json'))) for t in tags]
    bad = [x["tag"] for x in r if not x.get("valid_setup")]
    if bad: print("INVALID SETUP (amendment 1):", bad); r = [x for x in r if x.get("valid_setup")]
    if len(r) < 2: print("VERDICT: NO VERDICT (fewer than two valid tilts)"); return
    lock = all(x["A8"] >= 0.15 and x["p8"] < 0.001 for x in r) and (min((r[0]["extreme_bin"] - r[1]["extreme_bin"]) % 8, (r[1]["extreme_bin"] - r[0]["extreme_bin"]) % 8) <= 1)
    unif = all(max(abs(v) for v in x["fold8"]) <= 0.05 for x in r)
    print("VERDICT:", "PEAK-LOCKING" if lock else "UNIFORM" if unif else "NO VERDICT", [(x["tag"], x["A8"], x["p8"]) for x in r])
if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'capture': capture(arg('tag'), int(arg('frames', 300)))
    elif mode == 'analyse': analyse(arg('tag'), tuple(int(v) for v in arg('seed').split(',')))
    else: verdict(arg('tags').split(','))
