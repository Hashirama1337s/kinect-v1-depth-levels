"""plane_gravity_probe.py -- does the accelerometer's "down" agree with vertical/horizontal planes seen in depth?

Public (opened 2026-09-27): SDK docs jj663844 (accelerometer frame: right-handed, +z where the sensor points,
level -> (0,-1,0)); spec page jj131033 ("1 deg accuracy upper limit"). libfreenect issue #7 (open since
2010-11-13) asks where per-unit accelerometer calibration lives; nothing public states how the accelerometer
axes are aligned to the depth camera.
Unknown: the angle between the accelerometer's gravity and planes the depth camera sees.

Probe: 30 depth frames (640x480), per-pixel median, back-projection with the SDK nominal focal length
(571.26 px, NUI_CAMERA_DEPTH_NOMINAL_FOCAL_LENGTH_IN_PIXELS x2), RANSAC for the 3 largest planes; accelerometer
averaged over the same ~3 s. Nothing but plane parameters and angles is saved (plane_gravity_probe.json);
no depth image is written. BELOW_NORMAL priority, no motor moves.

Camera coordinates follow the SDK skeleton convention: X = (u - 319.5) z / f (sign irrelevant here),
Y = -(v - 239.5) z / f (up), Z = z (forward). The accelerometer vector is used as given (docs: same axes).

SEALED BARS (before the run):
  P1 VERTICAL   for the largest plane whose normal is within 5 deg of horizontal (a vertical-surface candidate:
                wall, box face, board), delta_v = angle(normal, gravity) - 90 deg. |delta_v| <= 1.0 -> AGREE
                (within the documented 1 deg); else report. Caveat fixed now: a single surface's own tilt is
                unknown, so AGREE/DISAGREE is about sensor + surface together.
  P2 HORIZONTAL same for the largest plane within 5 deg of vertical normal (floor / desk top), delta_h =
                angle(normal, gravity) (0 or 180 folded). NO RESULT if no such plane with >= 3 % of valid pixels.
"""
import os, sys, time, json, math
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import nui                                    # noqa: E402
from sensor import Sensor                     # noqa: E402
from atlas_common import below_normal_priority, F_NOMINAL_320   # noqa: E402

F = 2 * F_NOMINAL_320


def ransac_planes(P, k=3, iters=400, tol=12.0, min_frac=0.03, rng=np.random.default_rng(7)):
    planes = []
    idx_all = np.arange(len(P))
    remaining = np.ones(len(P), bool)
    n0 = len(P)
    for _ in range(k):
        R = idx_all[remaining]
        if len(R) < 500:
            break
        best, best_in = None, None
        for _ in range(iters):
            a, b, c = P[rng.choice(R, 3, replace=False)]
            n = np.cross(b - a, c - a)
            if np.linalg.norm(n) < 1e-6:
                continue
            n /= np.linalg.norm(n)
            d = -np.dot(n, a)
            tol_z = tol * (P[R, 2] / 1000.0) ** 2 + 3.0          # tolerance grows ~z^2 like the depth step
            inl = np.abs(P[R] @ n + d) < tol_z
            if best_in is None or inl.sum() > best_in.sum():
                best, best_in = (n, d), inl
        if best is None or best_in.sum() < min_frac * n0:
            break
        Q = P[R[best_in]]
        c = Q.mean(0)
        _, _, vt = np.linalg.svd(Q - c, full_matrices=False)       # least-squares refit on inliers
        n = vt[2] / np.linalg.norm(vt[2])
        if np.dot(n, c) > 0:
            n = -n                                                  # normal points toward the camera
        planes.append({"normal": n.tolist(), "centroid_mm": c.tolist(), "frac": float(len(Q) / n0),
                       "rms_mm": float(np.sqrt(np.mean(((Q - c) @ n) ** 2)))})
        remaining[R[best_in]] = False
    return planes


def main():
    below_normal_priority()
    s = Sensor(0)
    frames, acc = [], []
    try:
        s.verify()
        s.initialize(nui.INIT_DEPTH)
        s.open_stream(nui.IMG_DEPTH, nui.RES_640x480)
        time.sleep(1.0)
        while len(frames) < 30:
            try:
                a, _ = s.grab(nui.IMG_DEPTH, timeout_ms=2000)
                frames.append((a >> 3).astype(np.float32))
            except OSError:
                pass
            acc.append(s.accelerometer()[:3])
    finally:
        s.release()
    D = np.stack(frames)
    D[D == 0] = np.nan
    z = np.nanmedian(D, axis=0)
    del D, frames
    v, u = np.mgrid[0:480, 0:640]
    ok = np.isfinite(z) & (z >= 800) & (z <= 4000)
    X = (u[ok] - 319.5) * z[ok] / F
    Y = -(v[ok] - 239.5) * z[ok] / F
    P = np.column_stack([X, Y, z[ok]]).astype(np.float64)
    del z
    g = np.mean(acc, axis=0)
    gn = g / np.linalg.norm(g)
    out = {"valid_pixels": int(len(P)), "accel_mean": g.tolist(), "accel_pitch_deg": math.degrees(math.asin(-gn[2])),
           "accel_roll_deg": math.degrees(math.atan2(g[0], -g[1]))}
    planes = ransac_planes(P)
    for p in planes:
        a = math.degrees(math.acos(abs(float(np.dot(p["normal"], gn)))))    # 0 = horizontal surface, 90 = vertical
        p["angle_to_gravity_folded_deg"] = a
        p["kind"] = "vertical-candidate" if abs(a - 90) <= 5 else ("horizontal-candidate" if a <= 5 else "oblique")
        n = np.array(p["normal"])
        # decompose a vertical surface's residual into pitch-like (about camera x) and roll-like parts
        p["normal_pitch_deg"] = math.degrees(math.atan2(n[1], -n[2]))
        p["normal_yaw_deg"] = math.degrees(math.atan2(n[0], -n[2]))
    out["planes"] = planes
    vert = [p for p in planes if p["kind"] == "vertical-candidate"]
    hor = [p for p in planes if p["kind"] == "horizontal-candidate"]
    if vert:
        n = np.array(vert[0]["normal"])
        dv = math.degrees(math.asin(float(np.dot(n, -gn))))      # signed: + = the normal tilts up (away from gravity)
        out["P1_delta_v_deg"] = dv
        out["P1_verdict"] = "AGREE" if abs(dv) <= 1.0 else "DISAGREE"
    else:
        out["P1_verdict"] = "NO RESULT (no vertical-candidate plane)"
    if hor:
        out["P2_delta_h_deg"] = hor[0]["angle_to_gravity_folded_deg"]
        out["P2_verdict"] = "AGREE" if out["P2_delta_h_deg"] <= 1.0 else "DISAGREE"
    else:
        out["P2_verdict"] = "NO RESULT (no horizontal-candidate plane >= 3 %)"
    print(json.dumps(out, indent=1))
    with open(os.path.join(HERE, "plane_gravity_probe.json"), "w") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
