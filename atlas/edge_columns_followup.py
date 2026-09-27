"""edge_columns_followup.py -- POST-HOC (labelled; no sealed rule). ~2 s streaming, summary numbers only.
(1) extended_depth_probe.py found 0.23 % of packed 'too near' (0) pixels with extended depth 0 -- where are they?
(2) validity by image column/row at the frame borders (the PS1080 is often described as producing fewer than 640 valid depth columns).
"""
import time, ctypes as C
import numpy as np
from atlas_common import NUI_IMAGE_FRAME, _vtbl, below_normal_priority, FLAG_DISTINCT_OVERFLOW, V_DEPTH_PIXEL_TEXTURE
from extended_depth_probe import lock_copy, _F_dpt, _F_rel, W_, H_
from sensor import Sensor, V_STREAM_NEXT, V_STREAM_RELEASE, _F_next, _F_relframe


def main():
    print("below-normal priority:", below_normal_priority())
    s = Sensor(); print("verify:", s.verify()); s.initialize(0x00000020)
    P, E = [], []
    try:
        h = s.open_stream(4, 2, stream_flags=FLAG_DISTINCT_OVERFLOW); time.sleep(1.0)
        for _ in range(45):
            fr = NUI_IMAGE_FRAME()
            if s._call(V_STREAM_NEXT, _F_next)(s.p, h, C.c_uint32(3000), C.byref(fr)) < 0:
                continue
            try:
                raw, _ = lock_copy(fr.pFrameTexture, W_ * H_ * 2)
                near = C.c_int(); tex = C.c_void_p()
                if s._call(V_DEPTH_PIXEL_TEXTURE, _F_dpt)(s.p, h, C.byref(fr), C.byref(near), C.byref(tex)) < 0:
                    continue
                try:
                    ext, _ = lock_copy(tex, W_ * H_ * 4)
                finally:
                    _vtbl(tex, 2, _F_rel)(tex)
                P.append(np.frombuffer(raw, np.uint16).reshape(H_, W_) >> 3)
                E.append(np.frombuffer(ext, np.uint16).reshape(H_, W_, 2)[..., 1].copy())
            finally:
                s._call(V_STREAM_RELEASE, _F_relframe)(s.p, h, C.byref(fr))
    finally:
        s.shutdown(); s.release()
    P = np.stack(P).astype(np.int64); E = np.stack(E).astype(np.int64)
    both0 = (P == 0) & (E == 0)
    print(f"frames {len(P)}; packed 0 & extended 0: {both0.sum()} px-frames ({100 * both0.mean():.4f} % of all)")
    if both0.any():
        idx = np.argwhere(both0.any(axis=0))
        print(f"   distinct pixels {len(idx)}; rows {idx[:, 0].min()}..{idx[:, 0].max()}; cols {idx[:, 1].min()}..{idx[:, 1].max()}")
        cols, cnt = np.unique(idx[:, 1], return_counts=True); print("   top columns:", sorted(zip(cnt.tolist(), cols.tolist()), reverse=True)[:8])
        # their other-frame values
        vals = E[:, both0.any(axis=0)]; print("   extended values seen at those pixels in other frames: min nonzero",
                                                 vals[vals > 0].min() if (vals > 0).any() else '-', "median", int(np.median(vals[vals > 0])) if (vals > 0).any() else '-')
    unk = P == 8191
    colv = 1 - unk.mean(axis=(0, 1)); rowv = 1 - unk.mean(axis=(0, 2))
    print("   non-unknown share, first 10 cols:", np.round(colv[:10], 3).tolist())
    print("   non-unknown share, last 12 cols:", np.round(colv[-12:], 3).tolist())
    print("   non-unknown share, first 4 / last 4 rows:", np.round(rowv[:4], 3).tolist(), np.round(rowv[-4:], 3).tolist())
    always_unknown_cols = [int(c) for c in range(W_) if colv[c] == 0]
    print("   columns unknown in every pixel of every frame:", always_unknown_cols)


if __name__ == '__main__':
    main()
