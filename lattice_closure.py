"""Lattice closure test (2026-09-26; rule written before running). Are the SDK's millimetre depths exactly PrimeSense's published
shift-to-depth table? libfreenect's registration.c (default zero-plane constants: reference distance 120, reference pixel size 0.1042,
emitter distance 7.5, parameter coefficient 4, shift scale 10, S2D const offset 0.375) gives, per raw shift unit,
    1/z = 1/1200 - (raw/4 - const_shift - 0.375) * 0.1042 / 9000      [z in mm]
i.e. a lattice uniform in 1/z with step D = 0.1042 / 36000 mm^-1 (1/D = 345 489.4 mm) and a phase set by const_shift.
Data: depth_lattice.npy = the 266 distinct mm values this unit produced (863-3975 mm, 200 frames, earlier session).
RULE (sealed before running):
  EXACT CLOSURE : with D fixed at the formula value (NOT fitted), some phase and one rounding convention (round-half-up or floor)
                  reproduce >= 99 % of the 266 observed values exactly AND predict <= 1 % extra values inside observed runs
                  (an extra = a predicted value strictly between two observed values that are <= 3 predicted steps apart).
  PARTIAL       : the rule holds only for a D refitted within +-0.2 % of the formula value (report the D).
  FAIL          : neither.
Also reported (not part of the verdict): the phase against the formula's +0.5 prediction, and the implied f at 640 px."""
import numpy as np
obs = np.unique(np.load('depth_lattice.npy').astype(np.int64)); obs_set = set(obs.tolist())
D0 = 0.1042 / 36000.0
def table(D, phase, conv):
    # q = (1/1200 - 1/z) / D = n + phase for integer n  ->  z = 1 / (1/1200 - (n + phase) D)
    qmin = (1 / 1200 - 1 / 800.0) / D; qmax = (1 / 1200 - 1 / 4100.0) / D
    n = np.arange(np.floor(qmin) - 2, np.ceil(qmax) + 2)
    z = 1.0 / (1 / 1200 - (n + phase) * D)
    return np.floor(z + 0.5).astype(np.int64) if conv == 'round' else np.floor(z).astype(np.int64)
def score(D, phase, conv):
    t = np.unique(table(D, phase, conv)); ts = set(t.tolist())
    hit = np.mean([v in ts for v in obs])
    extra = 0
    for a, b in zip(obs[:-1], obs[1:]):
        between = t[(t > a) & (t < b)]
        local_step = (a / 1000.0) ** 2 * 1e6 * D          # dz = z^2 D (mm)
        if between.size and (b - a) <= 3 * local_step: extra += between.size
    return hit, extra / len(obs)
def best(D):
    out = []
    for conv in ('round', 'floor'):
        for ph in np.linspace(0, 1, 2001, endpoint=False):
            h, e = score(D, ph, conv); out.append((h - e, h, e, ph, conv))
    return max(out)
_, h, e, ph, conv = best(D0)
print(f"formula D (1/D = {1 / D0:,.1f} mm): best phase {ph:.4f} ({conv}) -> reproduces {100 * h:.1f} % of {len(obs)} observed values, extras {100 * e:.1f} %")
verdict = 'EXACT CLOSURE' if h >= 0.99 and e <= 0.01 else None
if not verdict:
    res = []
    for r in np.linspace(-0.002, 0.002, 81):
        s = best(D0 * (1 + r)); res.append((s[0], r, s))
    _, r, (_, h2, e2, ph2, conv2) = max(res)
    print(f"refitted D: {100 * r:+.3f} % (1/D = {1 / (D0 * (1 + r)):,.1f}) phase {ph2:.4f} ({conv2}) -> {100 * h2:.1f} % reproduced, extras {100 * e2:.1f} %")
    verdict = 'PARTIAL' if h2 >= 0.99 and e2 <= 0.01 else 'FAIL'
print("VERDICT:", verdict)
print(f"implied depth focal length at 640 px from the formula constants: 120 / (2 x 0.1042) = {120 / (2 * 0.1042):.2f} px (SDK nominal 571.26)")
