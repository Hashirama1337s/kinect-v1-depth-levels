"""Does averaging N frames actually reduce Kinect depth noise as 1/sqrt(N)?

Everyone assumes it does. The pre-publication gate: for Kinect v1 that assumption is
ASSUMED EVERYWHERE AND NEVER MEASURED. This measures it.

We deliberately do NOT claim a mechanism. Whether a departure from 1/sqrt(N)
is thermal drift or correlated stochastic noise cannot be separated by any
accepted procedure in this literature (pre-publication gate, question 2: it failed). What CAN be
stated honestly is the behaviour: average N frames, and here is what sigma
actually does. That is the fact every pipeline relies on.

Protocol per the gate:
  - sensor already warm (>= 60 min on-line); thermal state stated, not assumed
  - MULTI-LOCUS: a high-variance (in-stripe) pixel, a low-variance (quiet)
    pixel, and a 5x5 patch mean -- stripes are a known spatial structure and a
    single pixel is not representative
  - raw per-frame series saved, so sigma(N), ACF and Allan are all computed
    offline from the same data and anyone can recompute differently
  - report detrended AND undetrended: undetrended includes drift, which is the
    honest 'what you actually get' number
"""
import os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, nui

SHIFT, PROBE, NFRAMES = 3, 600, 20000

k = nui.Kinect(nui.INIT_DEPTH)
try:
    k.open_stream(nui.IMG_DEPTH, nui.RES_640x480)
    time.sleep(1.0)

    # --- phase 1: find loci empirically instead of guessing where stripes are
    print("probing %d frames to locate stripe / quiet pixels ..." % PROBE, flush=True)
    buf = []
    for _ in range(PROBE):
        a, _, _ = k.grab(nui.IMG_DEPTH, timeout_ms=3000)
        buf.append((a >> SHIFT).astype(np.int32))
    st = np.stack(buf)
    valid = (st > 0).all(axis=0)
    sd = st.std(axis=0)
    sd_masked = np.where(valid, sd, np.nan)
    c = (slice(180, 300), slice(260, 380))           # central region only
    sub = sd_masked[c]
    if np.all(np.isnan(sub)):
        raise SystemExit("no continuously-valid pixels in the central region — re-aim the sensor")
    noisy = np.unravel_index(np.nanargmax(sub), sub.shape)
    quiet = np.unravel_index(np.nanargmin(np.where(np.isnan(sub), np.inf, sub)), sub.shape)
    NOISY = (180 + noisy[0], 260 + noisy[1])
    QUIET = (180 + quiet[0], 260 + quiet[1])
    print("  in-stripe pixel %s sd=%.2f mm | quiet pixel %s sd=%.2f mm"
          % (NOISY, sd[NOISY], QUIET, sd[QUIET]), flush=True)

    # --- phase 2: long series at the chosen loci
    print("recording %d frames (~%.0f min) ..." % (NFRAMES, NFRAMES/30/60), flush=True)
    series = {"noisy": [], "quiet": [], "patch": [], "t": []}
    t0 = time.time()
    for n in range(NFRAMES):
        a, _, _ = k.grab(nui.IMG_DEPTH, timeout_ms=3000)
        mm = (a >> SHIFT).astype(np.int32)
        p = mm[NOISY[0]-2:NOISY[0]+3, NOISY[1]-2:NOISY[1]+3]
        series["noisy"].append(int(mm[NOISY]))
        series["quiet"].append(int(mm[QUIET]))
        series["patch"].append(float(p[p > 0].mean()) if (p > 0).any() else float("nan"))
        series["t"].append(round(time.time()-t0, 3))
        if (n+1) % 5000 == 0:
            print("  %d frames  %.0fs" % (n+1, time.time()-t0), flush=True)
finally:
    k.close()

json.dump({"NOISY": list(map(int, NOISY)), "QUIET": list(map(int, QUIET)),
           "sd_noisy": float(sd[NOISY]), "sd_quiet": float(sd[QUIET]),
           "series": series}, open("results_sigma_n_raw.json", "w"))
print("wrote results_sigma_n_raw.json — analysis is offline in analyse_sigma.py")
