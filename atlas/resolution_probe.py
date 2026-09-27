"""resolution_probe.py -- how are the 320x240 and 80x60 depth streams made from the 640x480 one? (3 sessions x ~1.5 s, static scene)

Public: the SDK offers DEPTH at 640x480, 320x240 and 80x60 (NuiImageStreamOpen remarks); nothing says how the lower resolutions
are produced (sub-sampling, block minimum, block median, averaging, or a separate hardware mode). player_index_probe.py showed that
all three stay on the integer shift-to-depth table (so no millimetre-domain averaging).

RULES (fixed before running). Per session: 40 frames, per-pixel temporal MEDIAN (packed >> 3; 0 / sentinels excluded by using the
no-flag stream where invalid = 0). For each low-res pixel (i, j) with factor s (2 or 8) compare with the 640x480 median image:
  CEILING          : exact agreement of two 640x480 medians of the same scene (start vs end of the run) = the best any rule can do.
  DECIMATION(k, l) : equals median640[s*i + k, s*j + l] on >= 0.9 x CEILING of low-res pixels where both are valid, for some offset
                     (k, l), AND beats the runner-up rule by >= 10 percentage points (report best, runner-up, rates);
  BLOCK-MIN / BLOCK-MEDIAN / BLOCK-MAX : the same test against the min / median / max of the valid 640 pixels in the s x s block;
  OTHER            : no rule meets that bar (report the best rate). A moving cat or person voids the run (check: 640 median of
                     session 1 vs a 640 median re-taken at the end must agree on >= 95 % of valid pixels).
"""
import time
import numpy as np
from atlas_common import nui, below_normal_priority, flat_grab

DIMS = {2: (640, 480), 1: (320, 240), 0: (80, 60)}


def med_image(res, n=40):
    w, h = DIMS[res]
    k = nui.Kinect(nui.INIT_DEPTH)
    try:
        hs = k.open_stream(nui.IMG_DEPTH, res); time.sleep(1.0)
        st = np.stack([flat_grab(hs, w, h, 3000)[0] >> 3 for _ in range(n)]).astype(np.float64)
    finally:
        k.close()
    st[st == 0] = np.nan
    valid = np.mean(~np.isnan(st), axis=0) >= 0.8
    med = np.nanmedian(st, axis=0)
    med[~valid] = np.nan
    return np.floor(med)                                   # median of integers may be .5 -> compare floors on both sides


def test(low, hi, s):
    H, W = low.shape
    res = {}
    for k in range(s):
        for l in range(s):
            cand = hi[k::s, l::s][:H, :W]
            m = ~np.isnan(low) & ~np.isnan(cand)
            res[f"DECIMATION({k},{l})"] = (np.mean(low[m] == cand[m]) if m.any() else 0.0, int(m.sum()))
    blocks = hi[:H * s, :W * s].reshape(H, s, W, s).transpose(0, 2, 1, 3).reshape(H, W, s * s)
    with np.errstate(all='ignore'):
        for name, fn in (("BLOCK-MIN", np.nanmin), ("BLOCK-MEDIAN", np.nanmedian), ("BLOCK-MAX", np.nanmax)):
            try:
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    cand = np.floor(fn(blocks, axis=2))
            except ValueError:
                continue
            m = ~np.isnan(low) & ~np.isnan(cand)
            res[name] = (np.mean(low[m] == cand[m]) if m.any() else 0.0, int(m.sum()))
    ranked = sorted(res.items(), key=lambda kv: -kv[1][0])
    return ranked


def main():
    print("below-normal priority:", below_normal_priority())
    hi1 = med_image(2); time.sleep(0.3)
    q = med_image(1); time.sleep(0.3)
    e = med_image(0); time.sleep(0.3)
    hi2 = med_image(2)
    m = ~np.isnan(hi1) & ~np.isnan(hi2)
    stab = np.mean(np.abs(hi1[m] - hi2[m]) <= 0) if m.any() else 0
    stab_tol = np.mean(np.abs(hi1[m] - hi2[m]) <= 0.01 * hi1[m]) if m.any() else 0
    print(f"scene check: 640 medians start vs end equal on {100 * stab:.1f} % (within 1 %: {100 * stab_tol:.1f} %) of {m.sum()} valid pixels")
    void = stab_tol < 0.95
    hi = hi1
    for name, low, s in (("320x240", q, 2), ("80x60", e, 8)):
        ranked = test(low, hi, s)
        best, (rate, n) = ranked[0]
        runner = ranked[1][1][0] if len(ranked) > 1 else 0.0
        verdict = best if (rate >= 0.9 * stab and rate - runner >= 0.10) else f"OTHER (best {best} {100 * rate:.1f} %, runner-up {100 * runner:.1f} %, ceiling {100 * stab:.1f} %)"
        print(f"{name}: top rules " + "; ".join(f"{k} {100 * v[0]:.1f} % (n={v[1]})" for k, v in ranked[:4]))
        print(f"   VERDICT {name}: {'VOID (scene moved)' if void else verdict}")
        # also: exact equality against the SECOND 640 median for the best decimation offset (drift sanity)
        if best.startswith("DECIMATION"):
            k, l = map(int, best[best.index('(') + 1:-1].split(','))
            H, W = low.shape; cand = hi2[k::s, l::s][:H, :W]; mm = ~np.isnan(low) & ~np.isnan(cand)
            print(f"   same offset vs end-of-run 640 median: {100 * np.mean(low[mm] == cand[mm]):.1f} %")


if __name__ == '__main__':
    main()
