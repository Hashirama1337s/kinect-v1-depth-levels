"""IR ceiling and per-frame pedestal (2026-09-27; descriptive, no rule fixed before looking).

Question: what is the largest 10-bit code the SDK's 640x480 IR stream ever reports, and does it move?
Input: any capture with an 'I' array of raw IR frames (uint16, 10-bit data in the high bits), e.g. the dark_room_*.npz captures
written by dark_room.py (kept locally; a capture of a room is never published).
Per frame: max code (raw >> 6), dark level = mean of the darkest 1 % of pixels, share of pixels at >= 1019.
Per capture: the set of per-frame maxima, the dark-level range, and corr(max, dark level) when both vary.
usage: python ir_ceiling.py dark_room_*.npz"""
import sys
import numpy as np

allmax = set()
for fn in sys.argv[1:]:
    I = (np.load(fn)['I'] >> 6).astype(np.float64)
    F = I.reshape(I.shape[0], -1)
    mx = F.max(1)
    dark = np.array([r[r <= np.percentile(r, 1)].mean() for r in F])
    sat = 100.0 * (F >= 1019).mean()
    c = np.corrcoef(mx, dark)[0, 1] if mx.std() > 0 and dark.std() > 0 else float('nan')
    allmax |= set(mx.astype(int).tolist())
    print(f"{fn}: frames {F.shape[0]}  per-frame max {sorted(set(mx.astype(int).tolist()))}  dark level {dark.min():.2f}-{dark.max():.2f}"
          f"  corr(max, dark) {'n/a (one of them constant)' if np.isnan(c) else f'{c:.2f}'}  pixels >= 1019: {sat:.2f} %")
print("largest code in any frame:", max(allmax) if allmax else None, "  all per-frame maxima:", sorted(allmax))
