"""accel_series.py -- second 30 s accelerometer read, kept as a raw series for structure analysis.

Why: accel_probe.py (run 1) showed the SDK values are exactly count/819 and include odd counts, but the
per-axis histograms are multi-modal with ~8-count spacing (e.g. y: -844 / -836 / -828 / -820), not the
single Gaussian a 12-bit sensor with 5 counts of noise would give. This run saves the series so the
step structure can be examined (steps between consecutive distinct samples; which residues mod 8 occur).

SEALED BAR (before run 2): "8-COUNT GRID" if >= 80 % of the non-zero steps between consecutive distinct
samples (all axes pooled) are multiples of 8 counts; "FINE" if < 30 %; else "MIXED". Report also the
distinct-sample count again (repeatability of run 1's 64 % new-value fraction, +- 10 points).

Output: accel_series.npz (t, x, y, z in g; no images, no audio). BELOW_NORMAL priority, no motor moves.
"""
import os, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import nui                                    # noqa: E402
from sensor import Sensor                     # noqa: E402
from atlas_common import below_normal_priority  # noqa: E402


def main(duration=30.0, poll=0.01, tag=""):
    below_normal_priority()
    s = Sensor(0)
    rows = []
    try:
        s.verify()
        s.initialize(nui.INIT_DEPTH)
        time.sleep(0.5)
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < duration:
            x, y, z, _ = s.accelerometer()
            rows.append((time.perf_counter() - t0, x, y, z))
            time.sleep(poll)
    finally:
        s.release()
    R = np.array(rows)
    np.savez(os.path.join(HERE, "accel_series%s.npz" % tag), t=R[:, 0], v=R[:, 1:4])
    mag = np.linalg.norm(R[:, 1:4], axis=1)
    print("pitch %.3f deg (SE %.3f), roll %.3f deg, |g| %.4f" % (np.degrees(np.arcsin(-R[:, 3] / mag)).mean(),
          np.degrees(np.arcsin(-R[:, 3] / mag)).std() / np.sqrt(len(R)), np.degrees(np.arctan2(R[:, 1], -R[:, 2])).mean(), mag.mean()))
    K = np.round(R[:, 1:4] * 819).astype(int)
    ch = np.any(np.diff(K, axis=0) != 0, axis=1)
    Kd = K[np.concatenate([[True], ch])]
    steps = np.diff(Kd, axis=0).ravel()
    steps = steps[steps != 0]
    m8 = float(np.mean(steps % 8 == 0))
    verdict = "8-COUNT GRID" if m8 >= 0.8 else ("FINE" if m8 < 0.3 else "MIXED")
    print("%d reads, %.1f %% new values, %d distinct samples" % (len(R), 100 * ch.mean(), len(Kd)))
    print("non-zero steps: %d; fraction multiple of 8 = %.3f -> %s" % (len(steps), m8, verdict))
    vals, cnt = np.unique(np.abs(steps), return_counts=True)
    print("|step| histogram:", dict(zip(vals.tolist()[:30], cnt.tolist()[:30])))
    for i, ax in enumerate("xyz"):
        v, c = np.unique(K[:, i], return_counts=True)
        print(" %s: %s" % (ax, dict(zip(v.tolist(), c.tolist()))))
        print("    residues mod 8:", np.bincount(np.mod(K[:, i], 8), minlength=8).tolist())


if __name__ == "__main__":
    main(tag=("_" + sys.argv[1]) if len(sys.argv) > 1 else "")
