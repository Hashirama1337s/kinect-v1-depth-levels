"""extended_followup.py -- POST-HOC follow-up to extended_depth_probe.py (labelled: questions raised BY that run, no sealed rule).
~2 s of streaming. Saves summary numbers only (pixel coordinates of a handful of off-table pixels, no image of the scene).

Questions: (1) the off-table extended values (4858, 22872, 50014, 52867, 53275 in the first run) -- fixed pixels or scattered?
constant over frames? (2) the >4000 mm extended pixels in a room of <= ~3 m: spatially coherent surface or isolated false matches?
persistent or flickering? (3) the <800 mm pixels: where are they (row band) and how persistent?
"""
import os, json, time, ctypes as C
from ctypes import wintypes as W
import numpy as np
from atlas_common import (HERE, NUI_IMAGE_FRAME, _vtbl, below_normal_priority, hr_hex, on_lattice, lattice_levels,
                          FLAG_DISTINCT_OVERFLOW, V_DEPTH_PIXEL_TEXTURE)
from extended_depth_probe import lock_copy, _F_dpt, _F_rel, W_, H_
from sensor import Sensor, V_STREAM_NEXT, V_STREAM_RELEASE, _F_next, _F_relframe

N = 60


def main():
    print("below-normal priority:", below_normal_priority())
    s = Sensor(); print("verify:", s.verify()); s.initialize(0x00000020)
    frames = []
    try:
        h = s.open_stream(4, 2, stream_flags=FLAG_DISTINCT_OVERFLOW); time.sleep(1.0)
        for _ in range(N):
            fr = NUI_IMAGE_FRAME()
            if s._call(V_STREAM_NEXT, _F_next)(s.p, h, C.c_uint32(3000), C.byref(fr)) < 0:
                continue
            try:
                near = C.c_int(); tex = C.c_void_p()
                if s._call(V_DEPTH_PIXEL_TEXTURE, _F_dpt)(s.p, h, C.byref(fr), C.byref(near), C.byref(tex)) < 0:
                    continue
                try:
                    ext, _ = lock_copy(tex, W_ * H_ * 4)
                finally:
                    _vtbl(tex, 2, _F_rel)(tex)
                frames.append(np.frombuffer(ext, np.uint16).reshape(H_, W_, 2)[..., 1].copy())
            finally:
                s._call(V_STREAM_RELEASE, _F_relframe)(s.p, h, C.byref(fr))
    finally:
        s.shutdown(); s.release()
    D = np.stack(frames).astype(np.int64); n = D.shape[0]
    lv = set(lattice_levels(300, 400000).tolist())
    nzv = np.unique(D[D > 0])
    off_vals = [int(x) for x in nzv if int(x) not in lv]
    print(f"frames {n}; distinct nonzero values {nzv.size}; off-table values ({len(off_vals)}): {off_vals[:30]}")
    rep = {"frames": n, "off_table_values": off_vals}
    if off_vals:
        m = np.isin(D, off_vals)
        pix = np.argwhere(m.any(axis=0))
        rep["off_table_pixels"] = []
        for (r, c) in pix[:40]:
            seq = D[:, r, c]; offs = np.isin(seq, off_vals)
            rep["off_table_pixels"].append({"row": int(r), "col": int(c), "frames_off": int(offs.sum()),
                                            "values_seen": sorted(set(seq.tolist()))[:8]})
        print(f"  off-table pixel count {len(pix)}; first: {rep['off_table_pixels'][:8]}")
    # far pixels
    far = D > 4000
    per_pix = far.mean(axis=0)
    fp = per_pix > 0
    nb = np.zeros_like(far)
    nb[:, 1:, :] |= far[:, :-1, :]; nb[:, :-1, :] |= far[:, 1:, :]; nb[:, :, 1:] |= far[:, :, :-1]; nb[:, :, :-1] |= far[:, :, 1:]
    coh = (far & nb).sum() / max(far.sum(), 1)
    rows = np.where(fp.any(axis=1))[0]; cols = np.where(fp.any(axis=0))[0]
    print(f"far (>4000): {fp.sum()} distinct pixels ever; per-pixel persistence median {np.median(per_pix[fp]):.2f}, "
          f"share persistent >= 90 % of frames {np.mean(per_pix[fp] >= 0.9):.2f}; 4-neighbour coherence {coh:.2f}; "
          f"rows {rows.min() if rows.size else '-'}..{rows.max() if rows.size else '-'}, cols {cols.min() if cols.size else '-'}..{cols.max() if cols.size else '-'}")
    if fp.any():
        med_far = np.median(np.where(far, D, np.nan), axis=0)
        pers = per_pix >= 0.9
        if pers.any():
            print(f"   persistent far pixels: median depth {np.nanmedian(med_far[pers]):.0f} mm, p10..p90 {np.nanpercentile(med_far[pers], 10):.0f}..{np.nanpercentile(med_far[pers], 90):.0f}")
    rep["far"] = {"pixels_ever": int(fp.sum()), "coherence": float(coh), "persistence_median": float(np.median(per_pix[fp])) if fp.any() else None}
    # near pixels
    near = (D > 0) & (D < 800); pn = near.mean(axis=0); npx = pn > 0
    rows = np.where(npx.any(axis=1))[0]; cols = np.where(npx.any(axis=0))[0]
    print(f"near (<800): {npx.sum()} distinct pixels ever; persistence median {np.median(pn[npx]):.2f}; rows {rows.min()}..{rows.max()}, cols {cols.min()}..{cols.max()}")
    sub600 = (D > 0) & (D < 560)
    if sub600.any():
        sp = np.argwhere(sub600.any(axis=0))
        print(f"   < 560 mm: {len(sp)} distinct pixels, rows {sp[:, 0].min()}..{sp[:, 0].max()}, cols {sp[:, 1].min()}..{sp[:, 1].max()}, "
              f"persistence median {np.median(sub600.mean(axis=0)[sub600.any(axis=0)]):.2f}")
    # row profile of near share (by 40-row band)
    band = [round(float(near[:, r0:r0 + 40].mean()), 3) for r0 in range(0, 480, 40)]
    print(f"   near share per 40-row band (top->bottom): {band}")
    rep["near"] = {"pixels_ever": int(npx.sum()), "min": int(D[near].min()) if near.any() else None, "row_band_share": band}
    json.dump(rep, open(os.path.join(HERE, 'extended_followup_result.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
