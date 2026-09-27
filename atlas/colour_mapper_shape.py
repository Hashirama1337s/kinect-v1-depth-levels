"""colour_mapper_shape.py -- does the SDK's depth->colour mapping contain lens distortion, or is it projective only? (offline)

Public: SDK headers give only nominal pinhole constants for the colour camera (NUI_CAMERA_COLOR_NOMINAL_FOCAL_LENGTH_IN_PIXELS
531.15 at 640x480, FOV 62.0 x 48.6 deg) and no distortion model. Published per-unit calibrations of Kinect v1 colour cameras carry
strong radial terms (e.g. TUM RGB-D fr1 d0..d4 = 0.2624, -0.9531, -0.0054, 0.0026, 1.1633; fr2 0.2312, -0.7849, ..., 0.9172;
a per-unit calibration page: k1 0.2645, k2 -0.8399, k3 0.9119), i.e. roughly 19-23 px of radial displacement at the 640x480 corners.
Unknown: whether the SDK's own mapping (MapDepthFrameToColorFrame, used for every registered colour pixel) models any of it.

Method (fixed before running): the mapper is rebuilt offline from this unit's ../calib_blob.bin (NuiCreateCoordinateMapperFromParameters).
For flat synthetic depth frames at Z = 1000, 2000, 3000 mm, map every depth pixel to COLOR 640 coordinates; fit a homography
(8 dof, least squares) from depth pixel (x, y) to colour (u, v) over the interior (valid, inside the colour frame).
Bars: PROJECTIVE ONLY if residual rms <= 0.5 px and max <= 1.0 px at every Z (integer outputs alone give rms ~0.41);
      NON-PROJECTIVE (distortion-like terms present) if max > 2 px at every Z; report the radial profile either way.
Output: numbers only -> colour_mapper_shape_result.json.
"""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from colour_registration import make_mapper, map_frame, M_RELEASE, _F_ref   # noqa: E402
from atlas_common import below_normal_priority, hr_hex, _vtbl               # noqa: E402


def fit_h(x, y, u, v):
    A = []
    for xi, yi, ui, vi in zip(x, y, u, v):
        A.append([xi, yi, 1, 0, 0, 0, -ui * xi, -ui * yi, -ui]); A.append([0, 0, 0, xi, yi, 1, -vi * xi, -vi * yi, -vi])
    A = np.array(A)
    _, _, Vt = np.linalg.svd(A); H = Vt[-1].reshape(3, 3); H /= H[2, 2]
    # refine by Gauss-Newton on reprojection error
    from scipy.optimize import least_squares
    def res(h):
        Hh = np.r_[h, 1].reshape(3, 3); w = Hh[2, 0] * x + Hh[2, 1] * y + Hh[2, 2]
        return np.r_[(Hh[0, 0] * x + Hh[0, 1] * y + Hh[0, 2]) / w - u, (Hh[1, 0] * x + Hh[1, 1] * y + Hh[1, 2]) / w - v]
    r = least_squares(res, H.ravel()[:8])
    rr = res(r.x); n = x.size
    return np.r_[r.x, 1].reshape(3, 3), rr[:n], rr[n:]


def main():
    below_normal_priority()
    m, hr, keep = make_mapper()
    print("mapper", hr_hex(hr))
    out = {}
    try:
        yy, xx = np.mgrid[0:480, 0:640]
        for Z in (1000, 2000, 3000):
            D = np.full((480, 640), Z, dtype=np.float64)
            h, pts = map_frame(m, D)
            u = pts[..., 0].astype(np.float64); v = pts[..., 1].astype(np.float64)
            ok = (u >= 0) & (u < 640) & (v >= 0) & (v < 480)
            sub = ok & (yy % 4 == 0) & (xx % 4 == 0)
            H, ru, rv = fit_h(xx[sub].astype(float), yy[sub].astype(float), u[sub], v[sub])
            r = np.hypot(ru, rv)
            # radial profile about the colour-image centre
            cu, cv = u[sub] - 319.5, v[sub] - 239.5; rad = np.hypot(cu, cv)
            radial = (ru * cu + rv * cv) / np.maximum(rad, 1e-9)       # signed radial component of the residual
            bins = np.arange(0, 420, 60)
            prof = [[int(b), float(np.mean(radial[(rad >= b) & (rad < b + 60)])), float(np.mean(r[(rad >= b) & (rad < b + 60)]))]
                    for b in bins if ((rad >= b) & (rad < b + 60)).sum() > 20]
            out[Z] = dict(map_hr=hr_hex(h), valid_frac=float(ok.mean()), rms=float(np.sqrt(np.mean(r ** 2))), max=float(r.max()),
                          H=[[round(float(a), 6) for a in row] for row in H], radial_profile=prof,
                          corr_radial_vs_radius=float(np.corrcoef(radial, rad)[0, 1]))
            print(Z, {k: v for k, v in out[Z].items() if k not in ('H',)})
    finally:
        _vtbl(m, M_RELEASE, _F_ref)(m)
    v = ('PROJECTIVE ONLY' if all(o['rms'] <= 0.5 and o['max'] <= 1.0 for o in out.values()) else
         'NON-PROJECTIVE' if all(o['max'] > 2 for o in out.values()) else 'UNCLEAR')
    print("VERDICT", v)
    json.dump(dict(results=out, verdict=v), open(os.path.join(HERE, 'colour_mapper_shape_result.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
