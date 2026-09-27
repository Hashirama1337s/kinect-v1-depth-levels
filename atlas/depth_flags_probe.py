"""depth_flags_probe.py -- special depth values, stream flags, low bits and frame metadata (flat API, ~6 s of streaming).

Public (SDK 1.8 docs, 'Coordinate Spaces' page): with NUI_IMAGE_STREAM_FLAG_DISTINCT_OVERFLOW_DEPTH_VALUES the packed stream marks
out-of-range pixels as too near 0x0000, too far 0x0FFF, unknown 0x1FFF (13-bit values, i.e. packed 0x0000 / 0x7FF8 / 0xFFF8);
without the flag every overflow pixel is 0. Header: NUI_IMAGE_DEPTH_MINIMUM 800 mm, _MAXIMUM 4000 mm (default range).
Not public for the Xbox 360 sensor: whether the flag is honoured on it, how the scene splits into the three classes, whether
the flag can be toggled on an open stream (the SetImageFrameFlags doc does not say), what the frame flags carry.

RULES (fixed before running):
  A  LOW BITS   : DEPTH stream (INIT_DEPTH only), no flag: (raw & 7) == 0 on 100 % of pixels of every frame -> PASS, else FAIL.
  B  RANGE      : no flag: every nonzero (raw >> 3) lies in [800, 4000] -> PASS, else FAIL (report the offenders).
  C  ROUND TRIP : GetImageFrameFlags returns exactly what was opened / set (0, then 0x40000 after SetImageFrameFlags) -> PASS.
  D  SENTINELS  : with the flag (set at runtime AND, separately, at open): every (raw >> 3) outside [800, 4000] is one of
                  {0, 4095, 8191} and at least one 8191 appears -> PASS; any other out-of-range value -> FAIL.
  E  ZEROS      : report the zero fraction without / with the flag (prediction: with the flag, zeros shrink to 'too near' only).
  F  METADATA   : report the distinct dwFrameFlags / eImageType / eResolution / view-area values (no timing analysis: fenced).
Output: prints only summary numbers; saves nothing of the scene.
"""
import time
import numpy as np
from atlas_common import (nui, below_normal_priority, flat_grab, flat_get_flags, flat_set_flags, hr_hex,
                          FLAG_DISTINCT_OVERFLOW, DEPTH_MIN_MM, DEPTH_MAX_MM, TOO_FAR_13, UNKNOWN_13)

W, H = 640, 480
N = 30


def grab_set(h, n=N):
    frames, metas = [], []
    for _ in range(n):
        a, m = flat_grab(h, W, H, 3000)
        frames.append(a); metas.append(m)
    return np.stack(frames), metas


def summarise(label, raw, metas):
    z = (raw >> 3).astype(np.int64)
    low = (raw & 7)
    nz = z[z > 0]
    out = z[(z > 0) & ((z < DEPTH_MIN_MM) | (z > DEPTH_MAX_MM))]
    vals, cnts = np.unique(out, return_counts=True)
    print(f"--- {label}: {raw.shape[0]} frames")
    print(f"  low 3 bits nonzero: {int((low != 0).sum())} of {low.size} pixels")
    print(f"  zero fraction: {100 * np.mean(z == 0):.3f} %   valid-range fraction: {100 * np.mean((z >= DEPTH_MIN_MM) & (z <= DEPTH_MAX_MM)):.3f} %")
    if nz.size:
        inr = nz[(nz >= DEPTH_MIN_MM) & (nz <= DEPTH_MAX_MM)]
        if inr.size:
            print(f"  in-range min / max: {inr.min()} / {inr.max()} mm; distinct in-range values {np.unique(inr).size}")
    print(f"  out-of-range nonzero values: {dict(zip(vals.tolist(), (100 * cnts / z.size).round(3).tolist()))} (value: % of pixels)")
    fl = sorted({m['flags'] for m in metas}); ty = sorted({m['type'] for m in metas}); rs = sorted({m['res'] for m in metas})
    va = sorted({(m['zoom'], m['cx'], m['cy']) for m in metas})
    fn = [m['frame'] for m in metas]
    print(f"  dwFrameFlags {[hex(f) for f in fl]}  eImageType {ty}  eResolution {rs}  view-area {va}")
    print(f"  frame numbers: first {fn[0]} last {fn[-1]} (span {fn[-1] - fn[0]} for {len(fn)} grabs)")
    return z, low, vals


def main():
    print("below-normal priority:", below_normal_priority())
    verdict = {}
    # ---------------- session 1: open with no flag, then toggle the flag at runtime --------------------------
    k = nui.Kinect(nui.INIT_DEPTH)
    try:
        h = k.open_stream(nui.IMG_DEPTH, nui.RES_640x480, stream_flags=0)
        hr, f0 = flat_get_flags(h); print(f"GetImageFrameFlags after open(0): hr={hr_hex(hr)} flags={hex(f0)}")
        time.sleep(1.0)
        raw0, m0 = grab_set(h)
        z0, low0, out0 = summarise("NO FLAG", raw0, m0)
        verdict['A'] = 'PASS' if int((low0 != 0).sum()) == 0 else 'FAIL'
        verdict['B'] = 'PASS' if out0.size == 0 else 'FAIL'
        hr = flat_set_flags(h, FLAG_DISTINCT_OVERFLOW); print(f"SetImageFrameFlags(0x40000): hr={hr_hex(hr)}")
        hr, f1 = flat_get_flags(h); print(f"GetImageFrameFlags after set: hr={hr_hex(hr)} flags={hex(f1)}")
        verdict['C'] = 'PASS' if (f0 == 0 and f1 == FLAG_DISTINCT_OVERFLOW) else 'FAIL'
        time.sleep(0.5)
        raw1, m1 = grab_set(h)
        z1, low1, out1 = summarise("FLAG SET AT RUNTIME", raw1, m1)
        # pixel-level transition table on the per-pixel median (static scene assumed)
        med0 = np.median(z0, axis=0); med1 = np.median(z1, axis=0)
        was0 = med0 == 0
        print("  pixels that were 0 without the flag now read (median):",
              {int(v): round(100 * c / was0.sum(), 2) for v, c in zip(*np.unique(med1[was0].astype(np.int64), return_counts=True)) if c / was0.sum() > 0.001})
        low_ok1 = int((low1 != 0).sum())
        print(f"  low 3 bits nonzero with flag: {low_ok1}")
    finally:
        k.close()
    time.sleep(0.5)
    # ---------------- session 2: flag given at open ----------------------------------------------------------
    k = nui.Kinect(nui.INIT_DEPTH)
    try:
        h = k.open_stream(nui.IMG_DEPTH, nui.RES_640x480, stream_flags=FLAG_DISTINCT_OVERFLOW)
        hr, f2 = flat_get_flags(h); print(f"GetImageFrameFlags after open(0x40000): hr={hr_hex(hr)} flags={hex(f2)}")
        time.sleep(1.0)
        raw2, m2 = grab_set(h)
        z2, low2, out2 = summarise("FLAG AT OPEN", raw2, m2)
    finally:
        k.close()
    allowed = {0, TOO_FAR_13, UNKNOWN_13}
    bad = [v for v in set(out1.tolist()) | set(out2.tolist()) if v not in allowed]
    has_unknown = (UNKNOWN_13 in set(out1.tolist())) and (UNKNOWN_13 in set(out2.tolist()))
    verdict['D'] = 'PASS' if (not bad and has_unknown) else ('FAIL (other values: %s)' % bad[:10] if bad else 'FAIL (no 8191 seen)')
    print("\nVERDICTS:", verdict)
    print(f"E: zero fraction no-flag {100 * np.mean(z0 == 0):.3f} % -> runtime-flag {100 * np.mean(z1 == 0):.3f} % / open-flag {100 * np.mean(z2 == 0):.3f} %")


if __name__ == '__main__':
    main()
