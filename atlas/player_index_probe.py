"""player_index_probe.py -- the DEPTH_AND_PLAYER_INDEX stream on an Xbox 360 sensor (flat API; ~3 x 1 s of streaming).

Public: NuiImageCamera.h / NuiImageStreamOpen remarks list DEPTH_AND_PLAYER_INDEX at 320x240 and 80x60 only (with
NUI_INITIALIZE_FLAG_USES_DEPTH_AND_PLAYER_INDEX); the 'Depth Stream' page: 'Player segmentation data is only available in the
depth stream when skeletal tracking is enabled', 0 = no player, 1-6 = players. Our capability map (capmap.py) left this row
untested (initialised with INIT_DEPTH only).

RULES (fixed before running). Init = DEPTH_AND_PLAYER_INDEX | SKELETON, NuiSkeletonTrackingEnable(NULL, 0).
  P1 OPEN   : report which of 640x480 / 320x240 / 80x60 open (the header documents 320x240 and 80x60 only).
  P2 EMPTY  : with nobody in view, the low 3 bits are 0 on 100 % of pixels of every frame -> PASS (report any nonzero share).
  P3 VALUES : the depth part (raw >> 3) is in {0} U [800, 4000] and every distinct in-range value is on the phase-0 floor table
              -> PASS (same cooked values as the DEPTH stream).
"""
import time, ctypes as C
from ctypes import wintypes as W
import numpy as np
from atlas_common import nui, below_normal_priority, flat_grab, hr_hex, on_lattice, DEPTH_MIN_MM, DEPTH_MAX_MM

nui._dll.NuiSkeletonTrackingEnable.argtypes = [W.HANDLE, C.c_uint32]
nui._dll.NuiSkeletonTrackingDisable.argtypes = []
DIMS = {2: (640, 480), 1: (320, 240), 0: (80, 60)}


def main():
    print("below-normal priority:", below_normal_priority())
    v = {}
    for res in (2, 1, 0):
        w, h = DIMS[res]
        k = nui.Kinect(nui.INIT_DEPTH_AND_PLAYER_INDEX | nui.INIT_SKELETON)
        try:
            r = nui._dll.NuiSkeletonTrackingEnable(None, C.c_uint32(0)); print(f"\n{w}x{h}: NuiSkeletonTrackingEnable {hr_hex(r)}")
            try:
                hs = k.open_stream(nui.IMG_DEPTH_AND_PLAYER_INDEX, res)
            except OSError as e:
                print(f"  open: REJECTED ({e})"); v[f'P1 {w}x{h}'] = 'REJECTED'; continue
            v[f'P1 {w}x{h}'] = 'OPENS'
            time.sleep(1.0)
            fr = [flat_grab(hs, w, h, 3000) for _ in range(20)]
            raw = np.stack([a for a, _ in fr]); metas = [m for _, m in fr]
            pb = raw & 7; z = (raw >> 3).astype(np.int64)
            pv, pc = np.unique(pb, return_counts=True)
            print(f"  player-index values: {dict(zip(pv.tolist(), (100 * pc / pb.size).round(4).tolist()))} (% of pixels)")
            print(f"  dwFrameFlags {sorted({hex(m['flags']) for m in metas})}  eImageType {sorted({m['type'] for m in metas})}")
            nz = z[z > 0]; bad = nz[(nz < DEPTH_MIN_MM) | (nz > DEPTH_MAX_MM)]
            inr = np.unique(nz[(nz >= DEPTH_MIN_MM) & (nz <= DEPTH_MAX_MM)])
            lat = on_lattice(inr).mean() if inr.size else float('nan')
            print(f"  zero {100 * np.mean(z == 0):.2f} %; out-of-range nonzero {bad.size}; distinct in-range {inr.size}, on lattice {100 * lat:.1f} %")
            v[f'P2 {w}x{h}'] = 'PASS' if int((pb != 0).sum()) == 0 else f'NONZERO {100 * np.mean(pb != 0):.4f} %'
            v[f'P3 {w}x{h}'] = 'PASS' if (bad.size == 0 and lat == 1.0) else 'FAIL'
        finally:
            nui._dll.NuiSkeletonTrackingDisable()
            k.close()
            time.sleep(0.5)
    print("\nVERDICTS:", v)


if __name__ == '__main__':
    main()
