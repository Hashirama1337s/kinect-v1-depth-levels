"""U(N) to 10^5 frames -- WITH the confound control the first run lacked.

The first sweep found U(N) still climbing at 10,000 frames. But this sensor
drifts thermally (~8 mm / 6 min from cold), and a drifting sensor sweeps a
static surface ACROSS depth levels -- which inflates the count and looks
exactly like genuine level discovery.

So this run tracks both:
    U(N)        cumulative distinct mm values (the claim)
    z_med(N)    median depth of a fixed central patch (the confound)

If z_med is flat and U still climbs -> the growth is real level discovery.
If z_med wanders -> U(N) growth is partly the sensor walking through levels,
and the published curve needs that caveat attached.

A 60-minute warm-up runs first so drift has largely settled before counting.
"""
import os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, nui

SHIFT = 3
WARMUP_S = 3600
NMAX = 100000
CHECKS = [1,10,50,100,200,500,1000,2000,5000,10000,20000,50000,100000]
PATCH = (slice(230, 250), slice(310, 330))     # 20x20 central patch

seen_all, seen_band, curve = set(), set(), []
k = nui.Kinect(nui.INIT_DEPTH)
try:
    k.open_stream(nui.IMG_DEPTH, nui.RES_640x480)
    print("warming up %d s (thermal drift settles) ..." % WARMUP_S, flush=True)
    t_w = time.time()
    while time.time() - t_w < WARMUP_S:
        k.grab(nui.IMG_DEPTH, timeout_ms=3000)
    print("warm. counting.", flush=True)

    t0 = time.time()
    for n in range(1, NMAX + 1):
        a, fn, ts = k.grab(nui.IMG_DEPTH, timeout_ms=3000)
        mm = (a >> SHIFT).astype(np.int32)
        v = np.unique(mm[mm > 0])
        seen_all.update(v.tolist())
        seen_band.update(v[(v >= 1000) & (v <= 4000)].tolist())
        if n in CHECKS:
            p = mm[PATCH]; p = p[p > 0]
            zmed = float(np.median(p)) if p.size else float("nan")
            row = {"N": n, "U_all": len(seen_all), "U_band": len(seen_band),
                   "z_med_mm": zmed, "secs": round(time.time()-t0, 1)}
            curve.append(row)
            print("  N=%-7d U_all=%-5d U_band=%-5d  patch z_med=%.1f mm  %.0fs"
                  % (n, len(seen_all), len(seen_band), zmed, time.time()-t0), flush=True)
            json.dump({"curve": curve}, open("results_un_sweep_1e5_partial.json", "w"), indent=1)
finally:
    k.close()

z0, z1 = curve[0]["z_med_mm"], curve[-1]["z_med_mm"]
a, b = curve[-2], curve[-1]
growth = (b["U_band"] - a["U_band"]) / max(a["U_band"], 1)
print("\npatch drift over the counted run: %.1f -> %.1f mm  (%+.1f mm)" % (z0, z1, z1 - z0))
print("last-decade U_band growth (N=%d -> %d): %+.2f%%" % (a["N"], b["N"], 100*growth))
print("\nVERDICT:")
if abs(z1 - z0) > 3:
    print("  CONFOUNDED - the patch moved %.1f mm; U(N) growth is not clean level discovery." % (z1-z0))
elif abs(growth) < 0.01:
    print("  PLATEAU with stable patch - census wording is defensible at this N.")
else:
    print("  STILL CLIMBING with a stable patch - the growth is real and unexplained.")
json.dump({"curve": curve, "U_all": len(seen_all), "U_band": len(seen_band),
           "patch_drift_mm": z1 - z0,
           "levels_band": sorted(int(x) for x in seen_band)},
          open("results_un_sweep_1e5.json", "w"), indent=1)
print("wrote results_un_sweep_1e5.json")
