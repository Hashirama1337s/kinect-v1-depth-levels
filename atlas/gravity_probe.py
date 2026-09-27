"""gravity_probe.py -- does the SDK rotate the accelerometer into camera space, and does it agree with the floor?

Public (opened 2026-09-27):
  - NuiSensor.h: NUI_SKELETON_FRAME = {liTimeStamp, dwFrameNumber, dwFlags, Vector4 vFloorClipPlane,
    Vector4 vNormalToGravity, NUI_SKELETON_DATA[6]}; INuiSensor vtable 16 NuiSkeletonTrackingEnable(HANDLE, DWORD),
    19 NuiSkeletonGetNextFrame(DWORD, NUI_SKELETON_FRAME*).
  - Docs jj663844: accelerometer = gravity direction, sensor frame, level sensor -> (0, -1, 0).
  - Spec page jj131033: accelerometer "with a 1 deg accuracy upper limit".
  Unknown: whether vNormalToGravity is just the (normalised, sign-flipped) accelerometer or includes a per-unit
  accelerometer-to-depth-camera rotation; whether it agrees with the depth-derived floor plane.

Probe: ~10 s with depth+player index 320x240 and skeleton tracking on (no person needed), BELOW_NORMAL
priority, no motor moves. Only vectors are saved (gravity_probe.json); no images.

SEALED BARS (fixed before the run):
  G1 SAME     angle between vNormalToGravity and -accel/|accel| (both averaged over the run) < 0.1 deg -> the SDK
              uses the accelerometer direction as-is (no extrinsic rotation). > 0.3 deg and stable -> a rotation is
              applied; report it. Between -> UNRESOLVED.
  G2 FLOOR    if the SDK reports a floor plane (non-zero A,B,C), the angle between its normal and vNormalToGravity
              <= 1.0 deg -> AGREE (the documented 1 deg); else DISAGREE (report). No floor -> NO RESULT.
"""
import os, sys, time, json, math
import ctypes as C
from ctypes import wintypes as W
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import nui                                    # noqa: E402
from sensor import Sensor, Vector4            # noqa: E402
from atlas_common import below_normal_priority   # noqa: E402

V_SKEL_ENABLE, V_SKEL_NEXT = 16, 19            # NuiSensor.h INuiSensorVtbl


class SKEL_FRAME(C.Structure):
    _fields_ = [("liTimeStamp", C.c_int64), ("dwFrameNumber", C.c_uint32), ("dwFlags", C.c_uint32),
                ("vFloorClipPlane", Vector4), ("vNormalToGravity", Vector4),
                ("data", C.c_ubyte * (6 * 436)), ("slack", C.c_ubyte * 4096)]   # generous slack


assert SKEL_FRAME.vFloorClipPlane.offset == 16 and SKEL_FRAME.vNormalToGravity.offset == 32


def ang(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    c = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def main():
    below_normal_priority()
    s = Sensor(0)
    rows = []
    hrs = {}
    try:
        print("vtable check:", s.verify())
        s.initialize(nui.INIT_DEPTH_AND_PLAYER_INDEX | nui.INIT_SKELETON)
        s.open_stream(nui.IMG_DEPTH_AND_PLAYER_INDEX, nui.RES_320x240)
        hr = s._call(V_SKEL_ENABLE, C.WINFUNCTYPE(C.c_long, C.c_void_p, W.HANDLE, C.c_uint32))(s.p, None, 0)
        print("NuiSkeletonTrackingEnable ->", "0x%08X" % (hr & 0xFFFFFFFF))
        nxt = s._call(V_SKEL_NEXT, C.WINFUNCTYPE(C.c_long, C.c_void_p, C.c_uint32, C.POINTER(SKEL_FRAME)))
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < 10.0:
            try:
                s.grab(nui.IMG_DEPTH_AND_PLAYER_INDEX, timeout_ms=200)     # keep the depth pipeline drained
            except OSError:
                pass
            fr = SKEL_FRAME()
            hr = nxt(s.p, 200, C.byref(fr))
            key = "0x%08X" % (hr & 0xFFFFFFFF)
            hrs[key] = hrs.get(key, 0) + 1
            if hr >= 0:
                a = s.accelerometer()
                f, g = fr.vFloorClipPlane, fr.vNormalToGravity
                rows.append((fr.dwFrameNumber, f.x, f.y, f.z, f.w, g.x, g.y, g.z, g.w, a[0], a[1], a[2]))
    finally:
        s.release()
    out = {"GetNextFrame_hr_counts": hrs, "n_frames": len(rows)}
    if rows:
        R = np.array(rows, float)
        F, G, A = R[:, 1:5], R[:, 5:9], R[:, 9:12]
        g_mean, a_mean = G[:, :3].mean(0), A.mean(0)
        out.update(normal_to_gravity_mean=g_mean.tolist(), normal_to_gravity_w=float(G[:, 3].mean()),
                   ntg_sd=G[:, :3].std(0).tolist(), accel_mean=a_mean.tolist(),
                   ntg_distinct_rows=int(len(np.unique(np.round(G[:, :3], 6), axis=0))),
                   floor_mean=F.mean(0).tolist(), floor_nonzero_frac=float(np.mean(np.any(F[:, :3] != 0, axis=1))))
        if np.linalg.norm(g_mean) == 0:
            # run 1 fault: an all-zero vNormalToGravity made ang() return NaN and min() then reported
            # "SAME (no rotation)". A zero vector is NO RESULT, not agreement.
            out.update(G1_verdict="NO RESULT (vNormalToGravity is all zeros in every frame)")
            nz = np.any(F[:, :3] != 0, axis=1)
            out["G2_verdict"] = "NO RESULT (no floor plane reported)" if not nz.any() else "floor reported but no gravity vector"
            print(json.dumps(out, indent=1))
            with open(os.path.join(HERE, "gravity_probe.json"), "w") as f:
                json.dump(out, f, indent=1)
            return
        a1 = ang(g_mean, -a_mean); a2 = ang(g_mean, a_mean)
        sign = "ntg = -accel direction" if a1 < a2 else "ntg = +accel direction"
        gang = min(a1, a2)
        # per-frame check: does each ntg equal that frame's accel sample, or a smoothed one?
        per = [min(ang(G[i, :3], -A[i]), ang(G[i, :3], A[i])) for i in range(len(R))]
        out.update(G1_angle_deg=gang, G1_sign=sign, G1_per_frame_median_deg=float(np.median(per)),
                   G1_verdict=("SAME (no rotation)" if gang < 0.1 else "ROTATED" if gang > 0.3 else "UNRESOLVED"))
        nz = np.any(F[:, :3] != 0, axis=1)
        if nz.any():
            fn = F[nz, :3].mean(0)
            fa = ang(fn, g_mean)
            fa = min(fa, 180 - fa)
            out.update(G2_floor_normal=fn.tolist(), G2_floor_height_m=float(F[nz, 3].mean()), G2_angle_deg=fa,
                       G2_verdict="AGREE" if fa <= 1.0 else "DISAGREE")
        else:
            out["G2_verdict"] = "NO RESULT (no floor plane reported)"
    print(json.dumps(out, indent=1))
    with open(os.path.join(HERE, "gravity_probe.json"), "w") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
