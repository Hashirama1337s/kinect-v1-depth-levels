"""extended_depth_probe.py -- the 'full depth' texture (INuiSensor vtable 29, NuiImageFrameGetDepthImagePixelFrameTexture) against
the packed stream of the SAME frame, on an Xbox 360 sensor (~3 s of streaming).

Public (SDK 1.8 'Depth Stream' page): the full format reports 'all detected depth values, including those outside the reliable
range'; unknown depth is 0. SDK 1.6 announcement: extended-range data 'beyond 4 meters', lower accuracy. Nobody (found) states
how far below 800 mm / above 4000 mm an Xbox 360 unit actually reports, or whether those values sit on the same shift-to-depth
table as the in-range values (our lattice_closure.py: SDK mm = floor(1/(1/1200 - n*0.1042/36000)), 266/266 in range).

RULES (fixed before running; packed stream opened WITH the distinct-overflow flag so the classes are visible):
  E1 SAME VALUES : where packed>>3 is in [800, 4000], extended.depth == packed>>3 on >= 99.9 % of those pixels -> PASS.
  E2 PLAYER      : extended.playerIndex == 0 on 100 % of pixels (no skeleton tracking) -> PASS.
  E3 EXTENT      : report counts of extended depth < 800 and > 4000, and their min / max; and what the packed stream shows there
                   (prediction: packed 0 = too near where extended < 800; packed 4095 = too far where extended > 4000).
  E4 LATTICE     : of the DISTINCT extended values outside [800, 4000], >= 99 % are on the phase-0 floor table -> PASS
                   (< 99 % -> FAIL; < 5 distinct values -> NO VERDICT, the scene lacks the range).
  E5 NEAR FLAG   : pNearMode == FALSE on every frame -> PASS.
  E6 UNKNOWN     : where packed == 8191 (unknown), extended.depth == 0 on >= 99 % -> PASS.
Prints summary numbers only; saves only value histograms (no image of the scene).
"""
import os, time, json
import ctypes as C
from ctypes import wintypes as W
import numpy as np
from atlas_common import (HERE, NUI_IMAGE_FRAME, NUI_LOCKED_RECT, _vtbl, _LockRect, _UnlockRect, _VT_LOCKRECT, _VT_UNLOCKRECT,
                          below_normal_priority, hr_hex, on_lattice, FLAG_DISTINCT_OVERFLOW, DEPTH_MIN_MM, DEPTH_MAX_MM,
                          TOO_FAR_13, UNKNOWN_13, V_DEPTH_PIXEL_TEXTURE)
from sensor import Sensor, V_STREAM_NEXT, V_STREAM_RELEASE, _F_next, _F_relframe

W_, H_ = 640, 480
N = 60
_F_dpt = C.WINFUNCTYPE(C.c_long, C.c_void_p, W.HANDLE, C.POINTER(NUI_IMAGE_FRAME), C.POINTER(C.c_int), C.POINTER(C.c_void_p))
_F_rel = C.WINFUNCTYPE(C.c_ulong, C.c_void_p)


def lock_copy(tex, nbytes_expected):
    lr = NUI_LOCKED_RECT()
    r = _vtbl(tex, _VT_LOCKRECT, _LockRect)(tex, 0, C.byref(lr), None, 0)
    if r < 0:
        raise OSError("LockRect " + hr_hex(r))
    try:
        if lr.size != nbytes_expected:
            raise OSError(f"unexpected buffer size {lr.size} (expected {nbytes_expected}), pitch {lr.Pitch}")
        return C.string_at(lr.pBits, lr.size), lr.Pitch
    finally:
        _vtbl(tex, _VT_UNLOCKRECT, _UnlockRect)(tex, 0)


def main():
    print("below-normal priority:", below_normal_priority())
    s = Sensor(); print("verify:", s.verify())
    s.initialize(0x00000020)                                  # INIT_DEPTH
    packed, ext_d, ext_p, near_flags = [], [], [], []
    pitch_ext = None
    try:
        h = s.open_stream(4, 2, stream_flags=FLAG_DISTINCT_OVERFLOW)   # DEPTH, 640x480
        time.sleep(1.0)
        for _ in range(N):
            fr = NUI_IMAGE_FRAME()
            hr = s._call(V_STREAM_NEXT, _F_next)(s.p, h, C.c_uint32(3000), C.byref(fr))
            if hr < 0:
                raise OSError("GetNextFrame " + hr_hex(hr))
            try:
                if not fr.pFrameTexture:
                    continue
                raw, _ = lock_copy(fr.pFrameTexture, W_ * H_ * 2)
                near = C.c_int(-1); tex = C.c_void_p()
                hr = s._call(V_DEPTH_PIXEL_TEXTURE, _F_dpt)(s.p, h, C.byref(fr), C.byref(near), C.byref(tex))
                if hr < 0:
                    raise OSError("NuiImageFrameGetDepthImagePixelFrameTexture " + hr_hex(hr))
                try:
                    ext, pitch_ext = lock_copy(tex, W_ * H_ * 4)
                finally:
                    _vtbl(tex, 2, _F_rel)(tex)                 # IUnknown::Release, as the SDK's DepthBasics sample does
                packed.append(np.frombuffer(raw, np.uint16).reshape(H_, W_))
                e = np.frombuffer(ext, np.uint16).reshape(H_, W_, 2)   # NUI_DEPTH_IMAGE_PIXEL = {playerIndex, depth}
                ext_p.append(e[..., 0].copy()); ext_d.append(e[..., 1].copy())
                near_flags.append(near.value)
            finally:
                s._call(V_STREAM_RELEASE, _F_relframe)(s.p, h, C.byref(fr))
    finally:
        s.shutdown(); s.release()
    P = np.stack(packed); z = (P >> 3).astype(np.int64)
    D = np.stack(ext_d).astype(np.int64); PI = np.stack(ext_p)
    print(f"frames {len(packed)}; extended pitch {pitch_ext} bytes/row; pNearMode values {sorted(set(near_flags))}")
    v = {}
    inr = (z >= DEPTH_MIN_MM) & (z <= DEPTH_MAX_MM)
    eq = np.mean(D[inr] == z[inr]); v['E1'] = 'PASS' if eq >= 0.999 else f'FAIL ({100 * eq:.3f} %)'
    print(f"E1 in-range pixels {inr.sum()}: extended == packed on {100 * eq:.4f} %")
    if eq < 1:
        d = D[inr] - z[inr]; dv, dc = np.unique(d[d != 0], return_counts=True)
        print("   differences (ext - packed):", dict(zip(dv[:20].tolist(), dc[:20].tolist())))
    v['E2'] = 'PASS' if int((PI != 0).sum()) == 0 else f'FAIL ({int((PI != 0).sum())} nonzero)'
    lo = (D > 0) & (D < DEPTH_MIN_MM); hi = D > DEPTH_MAX_MM
    print(f"E3 extended < 800 mm: {100 * lo.mean():.3f} % of pixels" + (f", min {D[lo].min()} max {D[lo].max()}" if lo.any() else ""))
    print(f"   extended > 4000 mm: {100 * hi.mean():.3f} % of pixels" + (f", min {D[hi].min()} max {D[hi].max()}" if hi.any() else ""))
    for name, m in (("ext<800", lo), ("ext>4000", hi), ("ext==0", D == 0)):
        if m.any():
            pv, pc = np.unique(z[m], return_counts=True)
            top = sorted(zip(pc.tolist(), pv.tolist()), reverse=True)[:6]
            print(f"   packed value where {name}: " + ", ".join(f"{val}: {100 * c / m.sum():.1f} %" for c, val in top))
    out_vals = np.unique(D[lo | hi])
    if out_vals.size < 5:
        v['E4'] = f'NO VERDICT ({out_vals.size} distinct out-of-range values)'
    else:
        ok = on_lattice(out_vals); frac = ok.mean()
        v['E4'] = 'PASS' if frac >= 0.99 else 'FAIL'
        print(f"E4 distinct out-of-range extended values {out_vals.size}: on phase-0 floor lattice {100 * frac:.1f} %")
        print(f"   below 800: {out_vals[out_vals < 800].tolist()[:40]}")
        print(f"   above 4000: {out_vals[out_vals > 4000].tolist()[:40]}")
        if not ok.all():
            print(f"   off-lattice: {out_vals[~ok].tolist()[:40]}")
    # in-range distinct values on lattice too (sanity, same frames)
    inv = np.unique(D[(D >= DEPTH_MIN_MM) & (D <= DEPTH_MAX_MM)])
    print(f"   sanity: distinct in-range extended values {inv.size}, on lattice {100 * on_lattice(inv).mean():.1f} %")
    v['E5'] = 'PASS' if set(near_flags) == {0} else f'FAIL {sorted(set(near_flags))}'
    unk = z == UNKNOWN_13
    if unk.any():
        f0 = np.mean(D[unk] == 0); v['E6'] = 'PASS' if f0 >= 0.99 else f'FAIL ({100 * f0:.2f} %)'
        print(f"E6 packed-unknown pixels {unk.sum()}: extended == 0 on {100 * f0:.3f} %")
    tf = z == TOO_FAR_13
    if tf.any():
        print(f"   packed too-far pixels {tf.sum()}: extended min/median/max {D[tf].min()} / {int(np.median(D[tf]))} / {D[tf].max()}")
    tn = z == 0
    if tn.any():
        print(f"   packed zero (too near) pixels {tn.sum()}: extended nonzero on {100 * np.mean(D[tn] > 0):.2f} %; "
              f"extended min/median/max of nonzero {D[tn][D[tn] > 0].min() if (D[tn] > 0).any() else '-'} / "
              f"{int(np.median(D[tn][D[tn] > 0])) if (D[tn] > 0).any() else '-'} / {D[tn].max()}")
    print("\nVERDICTS:", v)
    hist = {int(a): int(b) for a, b in zip(*np.unique(D[lo | hi], return_counts=True))}
    json.dump({"verdicts": v, "out_of_range_value_counts": hist}, open(os.path.join(HERE, 'extended_depth_result.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
