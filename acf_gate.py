"""ACF gate (2026-09-26; sealed rule fixed BEFORE looking, from the cross-exam): is the published integrated correlation time (2.74 s)
a property of the sensor, or warm-up drift leaking into the estimator?  90 s of depth (640x480, mm = raw >> 3) of a still scene on a
warmed sensor. Pixels valid in every frame. Three curves, averaged over pixels (per-pixel normalised ACF, lags 1..8, 30, 90 frames):
  RAW    : the mm series;
  DETR   : the mm series minus its centred 20 s (600-frame) moving mean (window fixed in advance), central 30 s only;
  BIT    : for pixels that take exactly two adjacent lattice values: the 0/1 'upper value' series (detrended the same way).
Sealed reading: detrended ACF at lag 8 > 0.3 -> memory in the depth pipeline (the 2.74 s figure stands, reworded);
                detrended ACF dead by lag 2 (< 0.05) -> the 2.74 s figure was drift -> CORRECTION in the repo; in between -> no verdict.
usage: python acf_gate.py"""
import sys, time
import numpy as np
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import nui
FPS, SECS, WIN = 30, 90, 600
k = nui.Kinect(nui.INIT_DEPTH)
try:
    k.open_stream(nui.IMG_DEPTH, nui.RES_640x480); time.sleep(1.0)
    t0 = time.time(); F = []; ts = []
    while len(F) < FPS * SECS:
        a, fn, t = k.grab(nui.IMG_DEPTH, timeout_ms=3000); F.append((a >> 3).astype(np.int16)); ts.append(t)
finally:
    k.close()
S = np.stack(F).reshape(len(F), -1).astype(np.float32); ts = np.array(ts)
print(f"{len(F)} frames in {time.time() - t0:.1f} s; timestamp span {(ts[-1] - ts[0]) / 1000:.1f} s")
ok = (S > 0).all(axis=0); X = S[:, ok]; print(f"pixels valid in every frame: {ok.sum()}")
nv = np.array([len(np.unique(X[:, j])) for j in range(0, X.shape[1], max(1, X.shape[1] // 20000))])
print(f"distinct values per pixel (sample): 1 -> {np.mean(nv == 1):.2f}, 2 -> {np.mean(nv == 2):.2f}, 3+ -> {np.mean(nv >= 3):.2f}")
def acf(Y, lags):
    Y = Y - Y.mean(0); v = (Y * Y).mean(0); good = v > 0; Y = Y[:, good]; v = v[good]
    return {L: float(np.mean((Y[:-L] * Y[L:]).mean(0) / v)) for L in lags}, int(good.sum())
def detrend(Y):
    c = np.cumsum(np.vstack([np.zeros((1, Y.shape[1])), Y]), axis=0)
    mm = (c[WIN:] - c[:-WIN]) / WIN                      # moving mean, length T - WIN + 1
    mid = slice(WIN // 2, WIN // 2 + mm.shape[0])
    R = Y[mid] - mm
    q = R.shape[0]; return R[q // 2 - 450:q // 2 + 450]    # central 30 s
LAGS = [1, 2, 3, 4, 8, 30, 90]
r_raw, n1 = acf(X, LAGS); r_det, n2 = acf(detrend(X), LAGS)
two = []
for j in range(X.shape[1]):
    u = np.unique(X[:, j])
    if len(u) == 2 and u[1] - u[0] <= 40: two.append(j)
two = np.array(two); B = (X[:, two] == X[:, two].max(0)).astype(np.float32) if len(two) else None
r_bit, n3 = acf(detrend(B), LAGS) if B is not None else ({}, 0)
fmt = lambda r: '  '.join(f"lag{L} {r[L]:+.3f}" for L in LAGS if L in r)
print(f"RAW  ({n1} px): {fmt(r_raw)}"); print(f"DETR ({n2} px): {fmt(r_det)}"); print(f"BIT  ({n3} two-level px): {fmt(r_bit)}")
v = r_det[8]
print("VERDICT:", "memory in the depth pipeline (lag-8 detrended ACF > 0.3)" if v > 0.3 else
      "the 2.74 s figure was drift (detrended ACF < 0.05 by lag 2)" if r_det[2] < 0.05 else "no verdict (in between)")
np.savez_compressed('acf_gate_result.npz', r_raw=[r_raw[L] for L in LAGS], r_det=[r_det[L] for L in LAGS], r_bit=[r_bit.get(L, np.nan) for L in LAGS], lags=LAGS)
