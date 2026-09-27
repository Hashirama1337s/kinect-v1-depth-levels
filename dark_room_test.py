"""Dark-room tests on a dark_room capture (2026-09-26). Rules written before the analysis was run.

A. DOT-LEAK KILL TEST (vision menu #4): does the RGB camera's raw Bayer stream see the IR projector's dot pattern?
   Image: the Bayer mean's 2x2 block sum (640x480, DN), high-passed (minus a Gaussian blur, sigma 3 px). Templates: two 96x96 patches of the
   high-passed IR mean, one on the flat wall and one on the box face (IR coordinates). Each template is scaled by s in 0.80..1.00
   (step 0.01; the RGB/IR focal-length ratio is ~0.9) and matched over the whole Bayer image by normalised cross-correlation. Score z =
   (peak - median) / (1.4826 MAD) of the NCC map; best over scales. Null: the same template rotated 180 deg, flipped left-right and
   flipped up-down (same statistics, wrong structure), best over the same scales; null = the max of the three.
   Sealed verdict: LEAK if true z >= 2 x null in BOTH patches; KILL if true z <= 1.25 x null in both; otherwise no verdict.
   Sensitivity control: the wall template's own IR high-pass pattern (scaled 0.90, shifted) is injected into the real Bayer image at
   amplitudes a x (Bayer high-pass sd); the smallest a that the same rule detects is the stated detection limit.
B. KNOWN-SIZE TARGETS at ~1 m: box (330.2 mm wide) and the opaque plastic cylinder (hand ruler 44 mm wide, 144 mm tall).
   Region = flood fill from a seed within +-35 mm (seeds from the depth preview); widths per row over the middle half of rows; f = 571.26 px.
   Box: width uses the face's median depth. Cylinder: the silhouette's tangent points lie at the axis depth, so width uses
   z_axis = median front depth (centre column) + 22 mm (half the ruler width). Height = rows spanned x z / f.
   Materials: temporal sigma and valid fraction, cylinder front vs box face at the same distance.
usage: python dark_room_test.py dark_room_dark.npz [--box-seed=y,x] [--cyl-seed=y,x]"""
import sys
from collections import deque
import numpy as np
from scipy import ndimage, signal
z = np.load(sys.argv[1])
arg = lambda k, d: tuple(int(v) for v in next((a.split('=')[1] for a in sys.argv if a.startswith(f'--{k}=')), d).split(','))
F = 571.26

# ---------- A. dot leak ----------
B = z['Bmean'].astype(np.float64)
S = B[0::2, 0::2] + B[0::2, 1::2] + B[1::2, 0::2] + B[1::2, 1::2]
hp = lambda a: a - ndimage.gaussian_filter(a, 3)
Shp = hp(S)
I = hp(z['I'].astype(np.float64).mean(0) / 64.0)             # 10-bit counts
def ncc_z(img, t):
    t = t - t.mean(); t /= np.sqrt((t * t).sum()); n = t.size
    num = signal.fftconvolve(img, t[::-1, ::-1], mode='valid')
    s1 = signal.fftconvolve(img, np.ones_like(t), mode='valid'); s2 = signal.fftconvolve(img * img, np.ones_like(t), mode='valid')
    den = np.sqrt(np.maximum(s2 - s1 * s1 / n, 1e-12)); c = num / den
    med = np.median(c); mad = 1.4826 * np.median(np.abs(c - med))
    k = np.unravel_index(np.argmax(c), c.shape); return (c[k] - med) / mad, k
SCALES = np.round(np.arange(0.80, 1.0001, 0.01), 2)
def best(img, t):
    out = []
    for s in SCALES:
        zz, k = ncc_z(img, ndimage.zoom(t, s, order=1)); out.append((zz, s, k))
    return max(out)
def dot_test(img, patches, label):
    res = []
    for name, (y, x) in patches.items():
        t = I[y:y + 96, x:x + 96]
        tz = best(img, t); nz = max(best(img, np.rot90(t, 2))[0], best(img, t[:, ::-1])[0], best(img, t[::-1, :])[0])
        res.append((name, tz, nz))
        if label: print(f"  {name:5s}: true z {tz[0]:6.2f} (scale {tz[1]:.2f}, at {tz[2]})   null z {nz:6.2f}   ratio {tz[0] / nz:5.2f}")
    return res
PATCH = {'wall': arg('wall', '60,470'), 'box': arg('boxp', '150,300')}
print("A. dot leak (Bayer 2x2 sum, high-pass sd %.3f DN; frames mean level %.2f DN)" % (Shp.std(), z['Bfm'].mean()))
r = dot_test(Shp, PATCH, True)
leak = all(tz[0] >= 2 * nz for _, tz, nz in r); kill = all(tz[0] <= 1.25 * nz for _, tz, nz in r)
print("  VERDICT:", "LEAK (dots visible in the RGB camera)" if leak else "KILL (no dot pattern above the null)" if kill else "no verdict")
# sensitivity: inject the wall pattern
wy, wx = PATCH['wall']; big = ndimage.zoom(I, 0.90, order=1); big = big / big.std()
inj = np.zeros_like(Shp); dy, dx = 20, 30; h, w = min(big.shape[0], 480 - dy), min(big.shape[1], 640 - dx)
inj[dy:dy + h, dx:dx + w] = big[:h, :w]
print("  sensitivity (wall pattern injected at a x Bayer high-pass sd):")
for a in (0.02, 0.05, 0.1, 0.2):
    (_, tz, nz), = dot_test(Shp + a * Shp.std() * inj, {'wall': PATCH['wall']}, False)
    print(f"    a = {a:4.2f} ({a * Shp.std():.3f} DN rms): true z {tz[0]:6.2f} null {nz:6.2f} -> {'detected' if tz[0] >= 2 * nz else 'missed'}")

# ---------- B. known-size targets ----------
D = z['D'].astype(np.float64); V = D > 0; D[~V] = np.nan
Z = np.nanmedian(D, 0); SD = np.nanstd(D, 0); VF = V.mean(0); H, W = Z.shape
def region(seed):
    y0, x0 = seed; z0 = np.nanmedian(Z[y0 - 2:y0 + 3, x0 - 2:x0 + 3]); M = np.abs(Z - z0) < 35
    seen = np.zeros_like(M); q = deque([seed]); seen[seed] = True
    while q:
        y, x = q.popleft()
        for vy, vx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= vy < H and 0 <= vx < W and M[vy, vx] and not seen[vy, vx]: seen[vy, vx] = True; q.append((vy, vx))
    return seen
def measure(name, seed, true_w, true_h=None, radius=0.0):
    R = region(seed); ys = np.nonzero(R.any(1))[0]; top, bot = ys.min(), ys.max()
    rows = range(top + (bot - top) // 4, bot - (bot - top) // 4 + 1)
    wid = []; zf = []
    for y in rows:
        c = np.nonzero(R[y])[0]; wid.append(c.max() - c.min() + 1); zf.append(np.nanmin(Z[y, c]) if radius else np.nanmedian(Z[y, c]))
    wp = float(np.median(wid)); zc = float(np.median(zf)) + radius
    print(f"  {name}: {R.sum()} px, rows {top}-{bot}, width {wp:.1f} px (IQR {np.percentile(wid, 25):.0f}-{np.percentile(wid, 75):.0f}), "
          f"z used {zc:.1f} mm ({'front + %.0f mm' % radius if radius else 'face median'})")
    wm = wp * zc / F; print(f"     width {wm:6.1f} mm vs {true_w} -> {100 * (wm / true_w - 1):+.1f} %  (1 px = {zc / F:.2f} mm = {100 * zc / F / true_w:.1f} %)")
    if true_h:
        hm = (bot - top + 1) * zc / F; print(f"     height {hm:6.1f} mm vs {true_h} -> {100 * (hm / true_h - 1):+.1f} %")
    return R
print("B. known-size targets (f = %.2f px)" % F)
Rb = measure('box', arg('box-seed', '200,350'), 330.2)
Rc = measure('cylinder', arg('cyl-seed', '205,238'), 44.0, 144.0, radius=22.0)
def core(R):                                   # interior only (2 px erosion) so edges don't dominate
    return ndimage.binary_erosion(R, iterations=2)
for nm, R in (('box face', Rb), ('cylinder', Rc)):
    c = core(R); print(f"  {nm:9s} interior {c.sum():5d} px: valid {VF[c].mean():.3f}, temporal sigma median {np.nanmedian(SD[c]):.2f} mm, "
                     f"p90 {np.nanpercentile(SD[c], 90):.2f} mm, >10 mm {np.mean(SD[c] > 10):.3f}")
