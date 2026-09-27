"""Calibration blob, stage 3 (2026-09-27): does the SDK's coordinate mapper actually USE the blob's contents?

Method: NuiCreateCoordinateMapperFromParameters (flat export of Kinect10.dll; prototype from NuiSensor.h) builds a mapper from a
blob. CONTROL: the unmodified blob must map identically to the live sensor's own mapper. Then copies with ONE field changed
(required: const_shift 200 -> 220; reg_info ax x1.05; zero-plane distance 120 -> 130; exploratory extras below), each mapped with
MapDepthPointToColorPoint and MapDepthPointToSkeletonPoint on a pixel grid at six depths, plus a 1 mm depth sweep of the colour x
at the centre pixel. The implied skeleton focal length comes from X/Z = (u - cx)/f (and Y/Z = -(v - cy)/f).

Each mapper runs in its own child process (a bad blob that crashes the SDK kills only that child; the crash is reported).
Vtable indices / signatures / struct sizes are those of decode_stage2.py (re-checked against NuiSensor.h at run time);
sensor.verify() runs before the live sensor is touched.
usage: python decode_stage3.py             (runs everything; writes stage3_out/*.npz and stage3_results.json)
       python decode_stage3.py --analyse   (re-analyse saved outputs only)
"""
import os, sys, json, struct, subprocess
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import decode_stage2 as s2

OUT = os.path.join(HERE, "stage3_out")
GRID_X = list(range(0, 640, 40)) + [639]
GRID_Y = list(range(0, 480, 40)) + [479]
GRID_Z = (800, 1000, 1500, 2000, 3000, 4000)
SWEEP_Z = np.arange(300, 8192)
T1_OFF, T1_N = 20, 2051            # uint16 table, 2051 words (identity-like on this unit)
T2_OFF, T2_N = 4122, 4096          # uint16 table, 4096 entries (identity on this unit)


# ------------------------------------------------------------------ one-field edits
def _set_i32(b, off, v):
    struct.pack_into("<i", b, off, v)


def _set_f32(b, off, v):
    struct.pack_into("<f", b, off, v)


def _get_i32(b, off):
    return struct.unpack_from("<i", b, off)[0]


def _get_f32(b, off):
    return struct.unpack_from("<f", b, off)[0]


def e_const_shift(b):
    _set_i32(b, s2.SHIFT_OFF, 220)


def e_ax(b):
    o = s2.reg_field_offset("ax"); _set_i32(b, o, int(round(_get_i32(b, o) * 1.05)))


def e_zpd(b):
    _set_f32(b, s2.ZPD_OFF, 130.0)


def e_zpps(b):
    _set_f32(b, s2.ZPPS_OFF, _get_f32(b, s2.ZPPS_OFF) * 1.05)


def e_dx_start(b):                  # libfreenect scaling: dx_start / 256 = px  -> +512 = +2 px expected
    o = s2.reg_field_offset("dx_start"); _set_i32(b, o, _get_i32(b, o) + 512)


def e_dy_start(b):
    o = s2.reg_field_offset("dy_start"); _set_i32(b, o, _get_i32(b, o) + 512)


def e_dx_center(b):                 # "not used by mapping algorithm" in libfreenect
    _set_i32(b, s2.reg_field_offset("dx_center"), 0)


def e_t1(b):                        # values stay inside 0..2047
    t = np.frombuffer(bytes(b[T1_OFF:T1_OFF + 2 * T1_N]), "<u2").astype(np.int64)
    b[T1_OFF:T1_OFF + 2 * T1_N] = np.clip(t - 100, 0, 2047).astype("<u2").tobytes()


def e_t2(b):                        # values stay inside 0..4095
    t = np.frombuffer(bytes(b[T2_OFF:T2_OFF + 2 * T2_N]), "<u2").astype(np.int64)
    b[T2_OFF:T2_OFF + 2 * T2_N] = (t // 2).astype("<u2").tobytes()


def e_zpd_step5_at(z_target):
    """Zero-plane distance chosen so that PrimeSense's formula (rc 2.4, 1/16-px table) puts the shift step 4 -> 5 exactly at
    z_target mm (threshold at z_target - 0.5). Where that step appears or not brackets the SDK's depth clamp (stage 2)."""
    def edit(b):
        zpps = _get_f32(b, s2.ZPPS_OFF)
        ps = 1.0 / (float(np.float32(zpps)) * 20); pb = float(np.float32(2.4)) * 10 * ps
        rd = float(np.float32((z_target - 0.5) * (1 - 4.625 / pb) / 10))
        zs = np.arange(1900, 2300)
        st = zs[1:][np.diff(s2.int_shift(zs, zpps, rd, 2.4, 16, None)) != 0]
        assert list(st) == [z_target], st
        _set_f32(b, s2.ZPD_OFF, rd)
    return edit


VARIANTS = {   # name: (edit, description, required?)
    "control":        (None,        "unmodified blob", True),
    "const_shift_220": (e_const_shift, "int32 const_shift @12600: 200 -> 220", True),
    "ax_x1.05":       (e_ax,        "reg_info ax: 1556 -> 1634 (x1.05)", True),
    "zpd_130":        (e_zpd,       "float32 zero-plane distance @12532: 120.0 -> 130.0", True),
    "zpps_x1.05":     (e_zpps,      "float32 zero-plane pixel size @12536: 0.1042 -> 0.10941 (x1.05)", False),
    "dx_start_+512":  (e_dx_start,  "reg_info dx_start: 4528 -> 5040 (+2 px in libfreenect scaling)", False),
    "dy_start_+512":  (e_dy_start,  "reg_info dy_start: 6449 -> 6961 (+2 px in libfreenect scaling)", False),
    "dx_center_0":    (e_dx_center, "reg_info dx_center (unused in libfreenect) -> 0", False),
    "table2051_-100": (e_t1,        "uint16 table @20 (2051 words): each value -100, floored at 0", False),
    "table4096_half": (e_t2,        "uint16 table @4122 (4096 entries): each value halved", False),
    "zpd_step5_at_2047": (e_zpd_step5_at(2047), "zero-plane distance 122.4617: formula's 5th shift step at 2047 mm", False),
    "zpd_step5_at_2048": (e_zpd_step5_at(2048), "zero-plane distance 122.5216: formula's 5th shift step at 2048 mm", False),
    "zpd_step5_at_2049": (e_zpd_step5_at(2049), "zero-plane distance 122.5814: formula's 5th shift step at 2049 mm", False),
}


def edited_blob(name):
    blob = bytearray(open(os.path.join(HERE, "calib_blob.bin"), "rb").read())
    edit = VARIANTS[name][0]
    if edit:
        before = bytes(blob); edit(blob)
        diff = [i for i in range(len(blob)) if blob[i] != before[i]]
        assert diff, "edit changed nothing"
    return bytes(blob)


# ------------------------------------------------------------------ child: measure one mapper
def measure(m):
    col = np.zeros((len(GRID_Z), len(GRID_Y), len(GRID_X), 2), np.int32)
    col_hr = np.zeros(col.shape[:3], np.int64)
    skel = np.zeros((len(GRID_Z), len(GRID_Y), len(GRID_X), 4), np.float32)
    skel_hr = np.zeros(col.shape[:3], np.int64)
    for i, z in enumerate(GRID_Z):
        for j, y in enumerate(GRID_Y):
            for k, x in enumerate(GRID_X):
                (cx, cy), hr = m.depth_point_to_color(x, y, z); col[i, j, k] = (cx, cy); col_hr[i, j, k] = hr
                v, hr = m.depth_point_to_skeleton(x, y, z); skel[i, j, k] = v; skel_hr[i, j, k] = hr
    sweep = np.array([m.depth_point_to_color(320, 240, int(z))[0] for z in SWEEP_Z], np.int32)
    frame2000, _ = m.depth_frame_to_color(np.full((s2.H, s2.W), 2000, np.uint16))
    return dict(col=col, col_hr=col_hr, skel=skel, skel_hr=skel_hr, sweep=sweep, frame2000=frame2000)


def child(name):
    s2.below_normal_priority()
    s2.check_header()
    os.makedirs(OUT, exist_ok=True)
    if name == "live":
        from sensor import Sensor
        s = Sensor(); print("verify:", s.verify())
        s.initialize(0x00000020 | 0x00000002)
        try:
            m = s2.live_mapper(s)
            try:
                blob = m.params()
                ref = open(os.path.join(HERE, "calib_blob.bin"), "rb").read()
                print("live blob == calib_blob.bin:", blob == ref)
                res = measure(m); res["create_hr"] = np.int64(0)
            finally:
                m.release()
        finally:
            s.shutdown(); s.release()
    else:
        blob = edited_blob(name)
        m, hr = s2.mapper_from_blob(blob)
        print("%s: NuiCreateCoordinateMapperFromParameters hr=0x%08X mapper=%s" % (name, hr & 0xFFFFFFFF, bool(m)))
        if m is None:
            res = {"create_hr": np.int64(hr)}
        else:
            try:
                res = measure(m); res["create_hr"] = np.int64(hr)
                back = m.params()                      # does the mapper hand back the edited blob?
                res["params_back_equal"] = np.int64(back == blob)
            finally:
                m.release()
    np.savez_compressed(os.path.join(OUT, "stage3_%s.npz" % name), **res)
    print("saved", name)


# ------------------------------------------------------------------ parent: run children, analyse
def focal_fit(skel):
    """X/Z = (u - cx)/f, Y/Z = -(v - cy)/f over the grid (all depths)."""
    u = np.broadcast_to(np.array(GRID_X, float)[None, None, :], skel.shape[:3]).ravel()
    v = np.broadcast_to(np.array(GRID_Y, float)[None, :, None], skel.shape[:3]).ravel()
    X, Y, Z = (skel[..., i].astype(float).ravel() for i in range(3))
    ok = Z > 0
    ax_, bx_ = np.polyfit(u[ok], X[ok] / Z[ok], 1)
    ay_, by_ = np.polyfit(v[ok], Y[ok] / Z[ok], 1)
    rx = X[ok] / Z[ok] - (ax_ * u[ok] + bx_); ry = Y[ok] / Z[ok] - (ay_ * v[ok] + by_)
    return {"f_x": 1 / ax_, "cx": -bx_ / ax_, "f_y": -1 / ay_, "cy": -by_ / ay_,
            "rms_resid_x_px": float(np.sqrt(np.mean(rx ** 2)) / ax_), "rms_resid_y_px": float(np.sqrt(np.mean(ry ** 2)) / -ay_),
            "Z_over_depth_m": float(np.median(Z[ok] / (np.broadcast_to(np.array(GRID_Z, float)[:, None, None],
                                                                          skel.shape[:3]).ravel()[ok] / 1000.0)))}


def steps(sweep):
    return [int(z) for z in SWEEP_Z[1:][np.diff(sweep[:, 0]) != 0]]


def diff_summary(a, c):
    """a vs control c."""
    out = {}
    dcol = (a["col"].astype(np.int64) - c["col"].astype(np.int64))
    out["colour_points_changed_frac"] = float(np.mean(np.any(dcol != 0, axis=-1)))
    out["colour_dx_mean_by_Z"] = [float(dcol[i, ..., 0].mean()) for i in range(len(GRID_Z))]
    out["colour_dy_mean_by_Z"] = [float(dcol[i, ..., 1].mean()) for i in range(len(GRID_Z))]
    out["colour_dx_range"] = [int(dcol[..., 0].min()), int(dcol[..., 0].max())]
    out["colour_dy_range"] = [int(dcol[..., 1].min()), int(dcol[..., 1].max())]
    # spatial trend of the change at 2000 mm (full frame): dx = a + b*(x-320) + c*(y-240)
    fd = (a["frame2000"].astype(np.int64) - c["frame2000"].astype(np.int64))
    yy, xx = np.mgrid[0:s2.H, 0:s2.W]
    A = np.c_[np.ones(xx.size), (xx - 320).ravel(), (yy - 240).ravel()]
    out["frame2000_changed_frac"] = float(np.mean(np.any(fd != 0, axis=-1)))
    out["frame2000_dx_fit_const_perx_pery"] = [float(v) for v in np.linalg.lstsq(A, fd[..., 0].ravel(), rcond=None)[0]]
    out["frame2000_dy_fit_const_perx_pery"] = [float(v) for v in np.linalg.lstsq(A, fd[..., 1].ravel(), rcond=None)[0]]
    ds = a["skel"].astype(np.float64) - c["skel"].astype(np.float64)
    out["skeleton_max_abs_diff_xyz_m"] = [float(np.abs(ds[..., i]).max()) for i in range(3)]
    out["skeleton_identical"] = bool(np.array_equal(a["skel"], c["skel"]))
    out["sweep_steps_changed"] = steps(a["sweep"]) != steps(c["sweep"])
    out["sweep_steps"] = steps(a["sweep"])
    out["sweep_x_offset_vs_control"] = sorted(set((a["sweep"][:, 0].astype(int) - c["sweep"][:, 0].astype(int)).tolist()))
    return out


def model_outputs(blob):
    """EXPLORATORY: the post-hoc SDK model of decode_stage2.py, fed with a (possibly edited) blob's own fields."""
    reg, zpd, zpps, _ = s2.parse_blob(blob)
    _, _, dx, dy = s2.init_registration_table(reg)
    fx, fy = s2.sdk_model_map(dx, dy, 2000, zpps, zpd)
    raw_x = s2.W - 1 - 320
    base = np.floor(raw_x + dx[240, raw_x] + s2.DEPTH_X_OFFSET) + 1
    sw = (s2.W - 1) - (base + s2.int_shift(SWEEP_Z, zpps, zpd, 2.4, 16, 2047))
    return fx, fy, sw


def model_check(a, c, name):
    """Does the model, given the edited field, predict the SDK's output (sweep) and its CHANGE (2000 mm frame)?"""
    mfx, mfy, msw = model_outputs(edited_blob(name))
    cfx, cfy, csw = model_outputs(edited_blob("control"))
    sdk_dx = a["frame2000"][..., 0].astype(int) - c["frame2000"][..., 0].astype(int)
    sdk_dy = a["frame2000"][..., 1].astype(int) - c["frame2000"][..., 1].astype(int)
    return {"sweep_exact": float(np.mean(msw == a["sweep"][:, 0])),
            "frame_change_x_match": float(np.mean(sdk_dx == (mfx - cfx))),
            "frame_change_y_match": float(np.mean(sdk_dy == (mfy - cfy)))}


def run_children():
    os.makedirs(OUT, exist_ok=True)
    status = {}
    import time
    for name in ["live"] + list(VARIANTS):
        # the live child can meet E_NUI_DEVICE_IN_USE (0x83010009) transiently after another process let go of the
        # sensor; it gets up to three attempts, 10 s apart. Parameter-built mappers do not touch the sensor.
        for attempt in range(3 if name == "live" else 1):
            try:
                p = subprocess.run([sys.executable, os.path.abspath(__file__), "--child", name], cwd=HERE,
                                   capture_output=True, text=True, timeout=600)
                rc = p.returncode
                print(p.stdout.strip())
                if rc != 0:
                    print("  CHILD %s (attempt %d) exited 0x%08X\n%s" % (name, attempt + 1, rc & 0xFFFFFFFF, p.stderr[-2000:]))
            except subprocess.TimeoutExpired:
                rc = "timeout"; print("  CHILD %s timed out" % name)
            if rc == 0:
                break
            time.sleep(10)
        status[name] = rc if isinstance(rc, str) else int(rc & 0xFFFFFFFF)
    return status


def analyse(status=None):
    def load(n):
        p = os.path.join(OUT, "stage3_%s.npz" % n)
        return dict(np.load(p)) if os.path.exists(p) else None
    live, ctrl = load("live"), load("control")
    rpath = os.path.join(HERE, "stage3_results.json")
    if status is None and os.path.exists(rpath):              # --analyse keeps the exit codes of the last full run
        status = json.load(open(rpath)).get("child_exit_codes")
    results = {"child_exit_codes": status, "variants": {}}
    if live is None or ctrl is None or "col" not in ctrl:
        print("control or live output missing; cannot analyse"); return results
    same = all(np.array_equal(live[k], ctrl[k]) for k in ("col", "skel", "sweep", "frame2000"))
    results["control_identical_to_live"] = same
    print("\nCONTROL: mapper from the unmodified blob == live sensor mapper (colour grid, skeleton grid, sweep, 2000 mm frame):",
          "IDENTICAL" if same else "DIFFERENT")
    if not same:
        for k in ("col", "skel", "sweep", "frame2000"):
            print("   ", k, "equal" if np.array_equal(live[k], ctrl[k]) else "DIFFERS")
    results["control_params_back_equal"] = bool(ctrl.get("params_back_equal", 0))
    fc = focal_fit(ctrl["skel"]); fl = focal_fit(live["skel"])
    results["focal_control"] = fc; results["focal_live"] = fl
    print("skeleton focal (control): f_x %.4f  f_y %.4f  cx %.3f  cy %.3f  resid rms %.4f/%.4f px  Z/depth %.6f"
          % (fc["f_x"], fc["f_y"], fc["cx"], fc["cy"], fc["rms_resid_x_px"], fc["rms_resid_y_px"], fc["Z_over_depth_m"]))
    print("  nominal 285.63 x 2 = 571.26; blob constants 120/(2 x 0.1042) = %.3f" % (120 / (2 * 0.1042)))
    print("control sweep steps (centre pixel):", steps(ctrl["sweep"]))
    cfx, cfy, csw = model_outputs(edited_blob("control"))
    results["model_control"] = {"sweep_exact": float(np.mean(csw == ctrl["sweep"][:, 0])),
                                "frame2000_exact_x": float(np.mean(cfx == ctrl["frame2000"][..., 0])),
                                "frame2000_exact_y": float(np.mean(cfy == ctrl["frame2000"][..., 1]))}
    print("post-hoc model vs control (exploratory):", results["model_control"])
    for name, (edit, desc, req) in VARIANTS.items():
        if name == "control":
            continue
        a = load(name)
        entry = {"description": desc, "required": req, "exit": (status or {}).get(name)}
        if a is None:
            entry["result"] = "no output (child crashed or failed)"
        elif "col" not in a:
            entry["result"] = "mapper creation failed hr=0x%08X" % (int(a["create_hr"]) & 0xFFFFFFFF)
        else:
            entry.update(diff_summary(a, ctrl))
            entry["params_back_equal"] = bool(a.get("params_back_equal", 0))
            entry["focal"] = focal_fit(a["skel"])
            entry["model_prediction"] = model_check(a, ctrl, name)
        results["variants"][name] = entry
        print("\n== %s%s: %s" % (name, "" if req else " (exploratory)", desc))
        if "colour_points_changed_frac" not in entry:
            print("   ", entry.get("result")); continue
        print("   colour: %.3f of grid points changed; mean dx by Z %s; dy by Z %s; ranges dx %s dy %s"
              % (entry["colour_points_changed_frac"], [round(v, 2) for v in entry["colour_dx_mean_by_Z"]],
                 [round(v, 2) for v in entry["colour_dy_mean_by_Z"]], entry["colour_dx_range"], entry["colour_dy_range"]))
        print("   2000 mm frame: %.3f changed; dx fit [const, per-px x, per-px y] %s; dy fit %s"
              % (entry["frame2000_changed_frac"], [round(v, 5) for v in entry["frame2000_dx_fit_const_perx_pery"]],
                 [round(v, 5) for v in entry["frame2000_dy_fit_const_perx_pery"]]))
        print("   sweep: steps changed %s; x offset vs control %s; steps %s"
              % (entry["sweep_steps_changed"], entry["sweep_x_offset_vs_control"],
                 entry["sweep_steps"] if entry["sweep_steps_changed"] else "(same)"))
        mp = entry["model_prediction"]
        print("   post-hoc model given the edited field (exploratory): sweep exact %.4f; 2000 mm frame change matched x %.4f y %.4f"
              % (mp["sweep_exact"], mp["frame_change_x_match"], mp["frame_change_y_match"]))
        f = entry["focal"]
        print("   skeleton: identical %s; max |diff| xyz (m) %s; f_x %.4f f_y %.4f cx %.3f cy %.3f; params handed back = edited blob: %s"
              % (entry["skeleton_identical"], [round(v, 6) for v in entry["skeleton_max_abs_diff_xyz_m"]],
                 f["f_x"], f["f_y"], f["cx"], f["cy"], entry["params_back_equal"]))
    with open(os.path.join(HERE, "stage3_results.json"), "w") as fh:
        json.dump(results, fh, indent=1, default=lambda o: int(o) if isinstance(o, np.integer) else float(o))
    return results


if __name__ == "__main__":
    if "--child" in sys.argv:
        child(sys.argv[sys.argv.index("--child") + 1])
    elif "--analyse" in sys.argv:
        analyse()
    else:
        s2.below_normal_priority()
        s2.check_header()
        analyse(run_children())
