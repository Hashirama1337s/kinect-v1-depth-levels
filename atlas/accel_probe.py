"""accel_probe.py -- what does NuiAccelerometerGetCurrentReading actually return? (Kinect v1, SDK 1.8)

Public (opened 2026-09-27):
  - SDK docs (jj663844): Vector4 "in gravity units (g)", level sensor -> (0, -1.0, 0, 0), w "always 0.0".
  - libfreenect (include/libfreenect.h): FREENECT_COUNTS_PER_G 819, citing the Kionix KXSD9 product brief;
    raw int16 counts over USB control request 0xC0/0x32 (motor device), bytes 2-7, big-endian.
  - KXSD9-2050 datasheet Rev 3 (Jul 2010): 12-bit ADC; +-2 g range 794 / 819 / 844 counts/g (min/typ/max);
    zero-g offset 1843 / 2048 / 2253 counts (i.e. +-205 counts = +-0.25 g); noise density 750 ug/rtHz;
    bandwidth 50 Hz typ (factory LPF options up to 2 kHz).
  - A widely copied hobby page says "10 bits of data per axis".
  Unknown on the SDK path: is the float exactly count/819? Are all 12 bits passed? Noise? |g|? Is the
  integer elevation angle the accelerometer pitch?

Probe: ~30 s of polling (no motor moves, no streams opened), BELOW_NORMAL priority. Nothing written to
the device. Saves only accelerometer numbers (no images, no audio) to accel_probe_result.json.

SEALED BARS (fixed before the first run):
  A1 SCALE     PASS if the denominator D in [600, 1200] (step 0.25) that minimises the RMS distance of
               value*D to the nearest integer is 819 +- 0.5, AND that RMS at D = 819 is < 0.02 counts on all
               three axes. Otherwise FAIL and report the best D.
  A2 BITS      12-BIT if >= 25 % of distinct counts (all axes pooled) are odd; 10-BIT if every count is a
               multiple of 4; otherwise MIXED (report the residue histogram mod 4).
  A3 |g|       report mean |v|. "Within datasheet sensitivity alone" if 0.97 <= |g| <= 1.03 (794..844 counts/g).
               Outside that, offset error (datasheet +-0.25 g) must be contributing. One orientation cannot
               separate offset from scale -- that needs the multi-pose probe in the atlas table.
  A4 NOISE     report per-axis SD in counts over the whole window. Prediction if unfiltered at the datasheet
               50 Hz bandwidth: 750 ug/rtHz * sqrt(50 * pi/2) = 6.6 mg = 5.4 counts rms. SD < 1.5 counts means
               the firmware/SDK filters or decimates; SD within 2x of 5.4 means it does not.
  A5 ANGLE     SDK integer elevation vs pitch = asin(-z/|v|) in degrees. PASS (same quantity) if
               |elevation - pitch| <= 1.0 deg; report which rounding (round / floor / trunc) matches.
  A6 W         w == 0.0 on every read (docs).
"""
import os, sys, time, json, math
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import nui                                    # noqa: E402
from sensor import Sensor                     # noqa: E402
from atlas_common import below_normal_priority, hr_hex   # noqa: E402

DURATION_S = 30.0
POLL_S = 0.01


def main():
    print("below-normal priority:", below_normal_priority())
    s = Sensor(0)
    reads, elev = [], []
    try:
        print("vtable check:", s.verify())
        s.initialize(nui.INIT_DEPTH)            # accelerometer returns ERROR_NOT_READY before NuiInitialize
        time.sleep(0.5)
        elev.append((0.0, s.elevation_angle()))
        t0 = time.perf_counter()
        while True:
            t = time.perf_counter() - t0
            if t > DURATION_S:
                break
            x, y, z, w = s.accelerometer()
            reads.append((t, x, y, z, w))
            if len(reads) % 500 == 0:
                elev.append((t, s.elevation_angle()))
            time.sleep(POLL_S)
        elev.append((time.perf_counter() - t0, s.elevation_angle()))
    finally:
        s.release()

    R = np.array(reads, dtype=np.float64)
    t, V, W = R[:, 0], R[:, 1:4], R[:, 4]
    out = {"n_reads": int(len(R)), "duration_s": float(t[-1]), "elevation_samples": elev}
    print("\n%d reads in %.1f s" % (len(R), t[-1]))

    # A6
    out["A6_w_all_zero"] = bool(np.all(W == 0.0))
    print("A6 w all zero:", out["A6_w_all_zero"], " distinct w:", np.unique(W)[:5])

    # A1 -- scale lattice
    Ds = np.arange(600.0, 1200.0 + 1e-9, 0.25)
    def rms_frac(vals, D):
        r = vals * D
        return float(np.sqrt(np.mean((r - np.round(r)) ** 2)))
    uniq = [np.unique(V[:, i]) for i in range(3)]
    pooled = np.concatenate(uniq)
    scores = np.array([rms_frac(pooled, D) for D in Ds])
    bestD = float(Ds[int(np.argmin(scores))])
    rms819 = [rms_frac(uniq[i], 819.0) for i in range(3)]
    a1 = abs(bestD - 819.0) <= 0.5 and all(r < 0.02 for r in rms819)
    out.update(A1_bestD=bestD, A1_rms_at_819=rms819, A1_pass=bool(a1),
               A1_rms_best=float(scores.min()), A1_rms_median_over_D=float(np.median(scores)))
    print("A1 best D = %.2f (rms %.4f; median over D %.3f); rms at 819 per axis = %s -> %s"
          % (bestD, scores.min(), np.median(scores), ["%.5f" % r for r in rms819], "PASS" if a1 else "FAIL"))
    # second-best local minima, for the record
    order = np.argsort(scores)[:8]
    out["A1_top_D"] = [(float(Ds[j]), float(scores[j])) for j in order]
    print("   lowest-residual D:", ["%.2f:%.4f" % (Ds[j], scores[j]) for j in order])

    # counts
    K = np.round(V * 819.0).astype(np.int64)
    ks = np.concatenate([np.unique(K[:, i]) for i in range(3)])
    mod4 = np.bincount(np.mod(ks, 4), minlength=4)
    odd = float(np.mean(np.mod(ks, 2) == 1))
    a2 = "12-BIT" if odd >= 0.25 else ("10-BIT" if np.all(np.mod(ks, 4) == 0) else "MIXED")
    out.update(A2_distinct_counts_per_axis=[int(len(np.unique(K[:, i]))) for i in range(3)],
               A2_mod4_hist=mod4.tolist(), A2_odd_fraction=odd, A2_verdict=a2,
               counts_min=[int(K[:, i].min()) for i in range(3)], counts_max=[int(K[:, i].max()) for i in range(3)])
    print("A2 distinct counts per axis:", out["A2_distinct_counts_per_axis"], " mod-4 histogram:", mod4.tolist(),
          " odd fraction %.2f -> %s" % (odd, a2))
    for i, ax in enumerate("xyz"):
        vals, cnt = np.unique(K[:, i], return_counts=True)
        print("   %s counts: %s" % (ax, dict(zip(vals.tolist(), cnt.tolist())) if len(vals) <= 25
                                   else "%d values %d..%d" % (len(vals), vals.min(), vals.max())))

    # A3 -- magnitude
    mag = np.linalg.norm(V, axis=1)
    mean_v = V.mean(0)
    out.update(A3_mean_vector=mean_v.tolist(), A3_mean_counts=(mean_v * 819).tolist(),
               A3_g_mag_mean=float(mag.mean()), A3_g_mag_sd=float(mag.std()),
               A3_within_sensitivity_band=bool(0.97 <= mag.mean() <= 1.03))
    print("A3 mean vector (g) = %s  counts = %s  |g| = %.4f +- %.4f  -> %s"
          % (np.round(mean_v, 4).tolist(), np.round(mean_v * 819, 1).tolist(), mag.mean(), mag.std(),
             "within +-3 %" if out["A3_within_sensitivity_band"] else "OUTSIDE +-3 %"))

    # A4 -- noise
    sd_counts = (V * 819).std(0)
    # how often the value actually changes between consecutive polls (a cached register vs fresh samples)
    changed = np.any(np.diff(V, axis=0) != 0, axis=1)
    frac_changed = float(changed.mean())
    # SD on de-duplicated sample sequence (only the reads where something changed)
    Vd = V[np.concatenate([[True], changed])]
    sd_dedup = (Vd * 819).std(0)
    out.update(A4_sd_counts=sd_counts.tolist(), A4_sd_mg=(sd_counts / 819 * 1000).tolist(),
               A4_sd_counts_dedup=sd_dedup.tolist(), A4_frac_polls_changed=frac_changed,
               A4_n_distinct_samples=int(len(Vd)))
    print("A4 SD counts x,y,z = %s (mg %s); dedup SD = %s; %.1f %% of polls saw a new value (%d samples)"
          % (np.round(sd_counts, 3).tolist(), np.round(sd_counts / 819 * 1000, 2).tolist(),
             np.round(sd_dedup, 3).tolist(), 100 * frac_changed, len(Vd)))
    # slow drift over the window: first vs last 5 s means (counts)
    a = V[t < 5].mean(0) * 819; b = V[t > t[-1] - 5].mean(0) * 819
    out["A4_first5_last5_delta_counts"] = (b - a).tolist()
    print("   first-5-s vs last-5-s mean delta (counts):", np.round(b - a, 2).tolist())

    # A5 -- elevation vs pitch
    pitch = np.degrees(np.arcsin(-V[:, 2] / mag))
    roll = np.degrees(np.arctan2(V[:, 0], -V[:, 1]))
    p = float(pitch.mean())
    ev = [e for _, e in elev]
    out.update(A5_pitch_deg=p, A5_roll_deg=float(roll.mean()), A5_elevations=ev,
               A5_round=int(round(p)), A5_floor=int(math.floor(p)), A5_trunc=int(math.trunc(p)),
               A5_pass=bool(all(abs(e - p) <= 1.0 for e in ev)))
    print("A5 accel pitch = %.3f deg (roll %.3f deg); SDK elevation samples = %s; round/floor/trunc = %d/%d/%d -> %s"
          % (p, roll.mean(), ev, round(p), math.floor(p), math.trunc(p), "PASS" if out["A5_pass"] else "FAIL"))

    with open(os.path.join(HERE, "accel_probe_result.json"), "w") as f:
        json.dump(out, f, indent=1)
    print("\nwrote accel_probe_result.json")


if __name__ == "__main__":
    main()
