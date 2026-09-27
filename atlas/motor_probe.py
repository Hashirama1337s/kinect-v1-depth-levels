"""motor_probe.py -- two tilt-motor moves (out and back), watched by the accelerometer. Kinect v1, SDK 1.8.

Public (opened 2026-09-27):
  - SDK docs hh855454 / NuiImageCamera.h: range [-27, +27] deg "relative to gravity"; "no more than once per
    second" and "at least 20 seconds of rest after 15 consecutive changes"; ERROR_RETRY / ERROR_TOO_MANY_CMDS.
  - libfreenect src/tilt.c: USB request 0x40/0x31 with value 2*degrees; clamps to [-31, +31]; state byte 8
    in half-degrees; status 0 stopped / 1 limit / 4 moving.
  Unknown: does the motor land on the commanded angle (vs gravity, measured by the accelerometer)? How
  repeatable is a return to the same command? Does GetAngle report the measured or the commanded angle?

Operator rules applied: at most 2 moves in this run, both targets within +-10 deg, >= 25 s between moves
(stricter than the SDK's 1 s / 15-per-20 s). BELOW_NORMAL priority. The run returns the sensor to the
angle it started at. Saves only accelerometer + angle numbers (motor_probe.npz, motor_probe.json).

SEALED BARS (fixed before the run):
  M1 TARGET   after settling (mean of the 5 s before move 2): SDK elevation == target (+-1) and accelerometer
              pitch within +-1.0 deg of the target -> PASS. (The docs say the angle is relative to gravity.)
  M2 RETURN   |pitch after return - pitch before| <= 0.5 deg -> PASS (repeatability of one round trip).
              Pitch = asin(-z/|v|) from 5 s means; the per-sample SD is ~0.55 deg, so a 5 s mean (~300
              samples) has SE ~0.03 deg.
  M3 MOTION   report: time from command to 90 % of the pitch change, mean slew rate (deg/s) between 10 % and
              90 %, and whether GetAngle changes during the motion (measured) or jumps (commanded).
  M4 SIGN     a positive command must increase pitch (sensor looks up) -> PASS.
"""
import os, sys, time, json, math
import ctypes as C
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import nui                                    # noqa: E402
from sensor import Sensor, V_ELEV_SET         # noqa: E402  (index 14 from NuiSensor.h INuiSensorVtbl)
from atlas_common import below_normal_priority, hr_hex   # noqa: E402

GAP_S = 25.0
STEP_DEG = 5
LIMIT = 10
_F_set = C.WINFUNCTYPE(C.c_long, C.c_void_p, C.c_long)


def set_angle(s, deg):
    return s._call(V_ELEV_SET, _F_set)(s.p, C.c_long(int(deg)))


def main():
    below_normal_priority()
    s = Sensor(0)
    rows, events = [], []
    try:
        print("vtable check:", s.verify())
        s.initialize(nui.INIT_DEPTH)
        time.sleep(0.5)
        a0 = s.elevation_angle()
        if abs(a0) > LIMIT:
            print("start angle %d outside +-%d: no moves (rule)" % (a0, LIMIT)); return
        target = a0 + STEP_DEG if a0 + STEP_DEG <= LIMIT else a0 - STEP_DEG
        print("start elevation %d -> target %d -> back to %d" % (a0, target, a0))
        t0 = time.perf_counter()
        plan = [(4.0, target), (4.0 + GAP_S, a0)]      # 4 s of baseline first
        done = 0
        k = 0
        while True:
            t = time.perf_counter() - t0
            if done < len(plan) and t >= plan[done][0]:
                hr = set_angle(s, plan[done][1])
                events.append((t, plan[done][1], hr_hex(hr)))
                print("t=%.2f s  SetAngle(%d) -> %s" % (t, plan[done][1], hr_hex(hr)))
                done += 1
            if t > plan[-1][0] + 9.0:
                break
            x, y, z, _ = s.accelerometer()
            e = s.elevation_angle() if k % 5 == 0 else np.nan
            rows.append((t, x, y, z, e))
            k += 1
            time.sleep(0.01)
    finally:
        s.release()

    R = np.array(rows, dtype=float)
    t, V, E = R[:, 0], R[:, 1:4], R[:, 4]
    np.savez(os.path.join(HERE, "motor_probe.npz"), t=t, v=V, elev=E, events=np.array([(a, b) for a, b, _ in events]))
    mag = np.linalg.norm(V, axis=1)
    pitch = np.degrees(np.arcsin(-V[:, 2] / mag))
    t1, t2 = events[0][0], events[1][0]
    def win(lo, hi):
        m = (t >= lo) & (t < hi)
        return pitch[m].mean(), pitch[m].std() / math.sqrt(m.sum()), np.nanmedian(E[m]), int(m.sum())
    pb = win(t1 - 3.5, t1)
    ps = win(t2 - 5.0, t2)
    pa = win(t[-1] - 5.0, t[-1] + 1)
    out = {"events": events, "start_elev": a0, "target": target,
           "pitch_before": pb[:3], "pitch_settled": ps[:3], "pitch_after": pa[:3]}
    print("\npitch before %.3f +- %.3f (elev %s) | settled at target %.3f +- %.3f (elev %s) | after return %.3f +- %.3f (elev %s)"
          % (pb[0], pb[1], pb[2], ps[0], ps[1], ps[2], pa[0], pa[1], pa[2]))
    m1 = abs(ps[2] - target) <= 1 and abs(ps[0] - target) <= 1.0
    m2 = abs(pa[0] - pb[0]) <= 0.5
    m4 = (ps[0] - pb[0]) * (target - a0) > 0
    out.update(M1_pass=bool(m1), M2_return_err_deg=float(pa[0] - pb[0]), M2_pass=bool(m2), M4_pass=bool(m4))
    print("M1 TARGET: settled pitch %.3f vs target %d (SDK elev %s) -> %s" % (ps[0], target, ps[2], "PASS" if m1 else "FAIL"))
    print("M2 RETURN: after - before = %+.3f deg -> %s" % (pa[0] - pb[0], "PASS" if m2 else "FAIL"))
    print("M4 SIGN  : %s" % ("PASS" if m4 else "FAIL"))

    # M3 motion profile for each move, from a 0.25 s running median of pitch
    k = 25
    pm = np.array([np.median(pitch[max(0, i - k // 2): i + k // 2 + 1]) for i in range(len(pitch))])
    for (tc, tgt, _), (lo, hi) in zip(events, [(pb[0], ps[0]), (ps[0], pa[0])]):
        m = (t >= tc) & (t < tc + GAP_S - 1)
        tt, pp = t[m] - tc, pm[m]
        frac = (pp - lo) / (hi - lo)
        try:
            i10 = int(np.argmax(frac >= 0.1)); i90 = int(np.argmax(frac >= 0.9))
            slew = (pp[i90] - pp[i10]) / max(tt[i90] - tt[i10], 1e-3)
            em = E[m]; tm = tt
            ev = [(round(float(a), 2), int(b)) for a, b in zip(tm[~np.isnan(em)], em[~np.isnan(em)])]
            # compress the elevation trace to its changes
            chg = [ev[0]] + [ev[i] for i in range(1, len(ev)) if ev[i][1] != ev[i - 1][1]]
            print("move to %d: 10%% at %.2f s, 90%% at %.2f s, slew %.1f deg/s; GetAngle changes: %s"
                  % (tgt, tt[i10], tt[i90], slew, chg[:12]))
            out.setdefault("M3", []).append({"target": tgt, "t10": float(tt[i10]), "t90": float(tt[i90]),
                                             "slew_deg_s": float(slew), "elev_changes": chg[:40]})
        except Exception as ex:                                   # report, do not hide
            print("M3 analysis failed for move to %d: %r" % (tgt, ex))
    with open(os.path.join(HERE, "motor_probe.json"), "w") as f:
        json.dump(out, f, indent=1, default=float)
    print("wrote motor_probe.json / motor_probe.npz")


if __name__ == "__main__":
    main()
