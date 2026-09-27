"""pi_1280_check.py -- completes the capability-map row: does DEPTH_AND_PLAYER_INDEX open at 1280x960? (no frames grabbed)
Rule: OPENS or REJECTED (report HRESULT). Also re-checks DEPTH at 1280x960 under the same init flags."""
import ctypes as C
from ctypes import wintypes as W
from atlas_common import nui, below_normal_priority
nui._dll.NuiSkeletonTrackingEnable.argtypes = [W.HANDLE, C.c_uint32]
print("below-normal priority:", below_normal_priority())
for init, typ, name in ((nui.INIT_DEPTH_AND_PLAYER_INDEX | nui.INIT_SKELETON, nui.IMG_DEPTH_AND_PLAYER_INDEX, "DEPTH_AND_PLAYER_INDEX"),
                        (nui.INIT_DEPTH, nui.IMG_DEPTH, "DEPTH")):
    k = nui.Kinect(init)
    try:
        if typ == nui.IMG_DEPTH_AND_PLAYER_INDEX:
            nui._dll.NuiSkeletonTrackingEnable(None, C.c_uint32(0))
        try:
            k.open_stream(typ, nui.RES_1280x960); print(name, "1280x960: OPENS")
        except OSError as e:
            print(name, "1280x960: REJECTED", e)
    finally:
        k.close()
