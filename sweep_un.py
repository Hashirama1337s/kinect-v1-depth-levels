"""U(N): does the realisable depth-level set SATURATE, or keep growing?

Pre-publication gate: until U(N) plateaus, a cardinality of 259 is a
FLOOR, not a census. This sweeps N to 10,000 frames under a locked driver,
mode and scene, and reports the growth curve.

U(N) = |union of valid mm depth values over frames 1..N|
"""
import sys, time, json
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import numpy as np, nui

SHIFT = 3                      # NUI_IMAGE_PLAYER_INDEX_SHIFT
CHECKS = [1, 10, 50, 100, 200, 500, 1000, 2000, 5000, 10000]
NMAX = CHECKS[-1]

seen_all, seen_band = set(), set()
curve = []
k = nui.Kinect(nui.INIT_DEPTH)
try:
    k.open_stream(nui.IMG_DEPTH, nui.RES_640x480)
    time.sleep(1.0)
    t0 = time.time()
    for n in range(1, NMAX + 1):
        a, fn, ts = k.grab(nui.IMG_DEPTH, timeout_ms=3000)
        mm = (a >> SHIFT).astype(np.int32)
        v = np.unique(mm[mm > 0])
        seen_all.update(v.tolist())
        seen_band.update(v[(v >= 1000) & (v <= 4000)].tolist())
        if n in CHECKS:
            row = {"N": n, "U_all": len(seen_all), "U_1000_4000": len(seen_band),
                   "secs": round(time.time() - t0, 1)}
            curve.append(row)
            print("  N=%-6d U_all=%-6d U[1000,4000]=%-6d  %.0fs"
                  % (n, len(seen_all), len(seen_band), time.time() - t0), flush=True)
finally:
    k.close()

lo, hi = min(seen_all), max(seen_all)
print("\nrange observed: %d - %d mm" % (lo, hi))
print("U_all(%d)        = %d" % (NMAX, len(seen_all)))
print("U[1000,4000](%d) = %d" % (NMAX, len(seen_band)))
a, b = curve[-2], curve[-1]
growth = (b["U_1000_4000"] - a["U_1000_4000"]) / max(a["U_1000_4000"], 1)
print("\nlast decade growth (N=%d -> %d): %+.2f%% in band" % (a["N"], b["N"], 100 * growth))
print("VERDICT:", "PLATEAU - census wording defensible" if abs(growth) < 0.01
      else "STILL CLIMBING - 259 is a FLOOR, relabel the card")
json.dump({"curve": curve, "range_mm": [int(lo), int(hi)],
           "U_all": len(seen_all), "U_band": len(seen_band),
           "levels_band": sorted(int(x) for x in seen_band)},
          open("results_un_sweep.json", "w"), indent=1)
print("wrote results_un_sweep.json")
