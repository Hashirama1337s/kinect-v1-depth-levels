"""Follow-up on dark_room_test.py (2026-09-26), after its first run. Nothing here changes the sealed verdict; each part says what it adds.
1. 3-D edge-to-edge width per row (corrects yaw): X = (u -/+ 0.5 - 319.5) * z_edge / f, z_edge = median depth 2..4 px inside each edge;
   width = hypot(dX, dz). Box as before; cylinder with z_edge = front + 22 mm (tangent points at the axis depth).
2. Cylinder height from its row profile: top = first row whose run is >= half the median width; bottom = last such row.
3. Dot contrast in the IR image (same camera as depth): sd of the high-passed IR in 7x7 windows over wall, box face, cylinder
   (diffuse surfaces keep sharp dots; subsurface scattering blurs them).
4. POST-HOC (not the sealed rule): dot-leak NCC on the Bayer image with outliers clipped at +-5 MAD, finer sensitivity grid."""
import sys
from collections import deque
import numpy as np
from scipy import ndimage, signal
z = np.load(sys.argv[1]); F = 571.26
D = z['D'].astype(float); V = D > 0; D[~V] = np.nan; Z = np.nanmedian(D, 0); H, W = Z.shape
def region(seed, tol=35):
    y0, x0 = seed; z0 = np.nanmedian(Z[y0 - 2:y0 + 3, x0 - 2:x0 + 3]); M = np.abs(Z - z0) < tol
    seen = np.zeros_like(M); q = deque([seed]); seen[seed] = True
    while q:
        y, x = q.popleft()
        for vy, vx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= vy < H and 0 <= vx < W and M[vy, vx] and not seen[vy, vx]: seen[vy, vx] = True; q.append((vy, vx))
    return seen
def width3d(R, rows, add=0.0):
    out = []
    for y in rows:
        c = np.nonzero(R[y])[0]
        if c.size < 5: continue
        l, r = c.min(), c.max()
        zl = np.nanmedian(Z[y, l + 2:l + 5]) + add; zr = np.nanmedian(Z[y, r - 4:r - 1]) + add
        if add: zl = zr = np.nanmin(Z[y, c]) + add
        xl = (l - 0.5 - 319.5) * zl / F; xr = (r + 0.5 - 319.5) * zr / F
        out.append((np.hypot(xr - xl, zr - zl), r - l + 1, zr - zl))
    return np.array(out)
Rb = region((200, 350)); ys = np.nonzero(Rb.any(1))[0]
rows = range(170, 245)
wb = width3d(Rb, rows)
print(f"1. box 3-D width: median {np.median(wb[:, 0]):.1f} mm (IQR {np.percentile(wb[:, 0], 25):.1f}-{np.percentile(wb[:, 0], 75):.1f}) "
      f"vs 330.2 -> {100 * (np.median(wb[:, 0]) / 330.2 - 1):+.2f} %; edge depth difference {np.median(wb[:, 2]):+.1f} mm "
      f"-> yaw {np.degrees(np.arcsin(np.median(wb[:, 2]) / np.median(wb[:, 0]))):+.1f} deg; {np.median(wb[:, 1]):.0f} px")
Rc = region((205, 238)); prof = np.array([Rc[y].sum() for y in range(H)])
wmed = np.median(prof[prof > 0]); good = np.nonzero(prof >= wmed / 2)[0]
top, bot = good.min(), good.max()
wc = width3d(Rc, range(top + (bot - top) // 4, bot - (bot - top) // 4 + 1), add=22.0)
zc = np.nanmedian([np.nanmin(Z[y, Rc[y]]) for y in range(top, bot + 1) if Rc[y].any()]) + 22
print(f"   cylinder 3-D width: median {np.median(wc[:, 0]):.1f} mm ({np.median(wc[:, 1]):.0f} px) vs 44.0 -> {100 * (np.median(wc[:, 0]) / 44 - 1):+.1f} %")
print(f"2. cylinder rows with run >= {wmed / 2:.0f} px: {top}-{bot} -> {bot - top + 1} px = {(bot - top + 1) * zc / F:.1f} mm vs 144.0; "
      f"runs near the bottom: {[int(prof[y]) for y in range(bot - 8, bot + 6)]}")
I = z['I'].astype(float).mean(0) / 64; Ih = I - ndimage.gaussian_filter(I, 3)
loc = np.sqrt(ndimage.uniform_filter(Ih * Ih, 7)); lm = ndimage.uniform_filter(I, 7)
def dotc(mask): return np.median(loc[mask] / lm[mask])
wall = np.zeros_like(Rb); wall[40:120, 460:600] = True
cyl_core = ndimage.binary_erosion(Rc, iterations=3)
cyl_col = np.zeros_like(Rb); cc = int(np.median(np.nonzero(Rc[top:bot + 1])[1])); cyl_col[top:bot + 1, cc - 4:cc + 5] = True
up = np.zeros_like(Rb); up[130:top - 3, cc - 4:cc + 5] = True
print(f"3. IR dot contrast (local high-pass sd / local mean): wall {dotc(wall):.3f}, box face {dotc(ndimage.binary_erosion(Rb, iterations=3)):.3f}, "
      f"cylinder core {dotc(cyl_core):.3f}, cylinder centre strip {dotc(cyl_col):.3f}, above the cylinder's depth top (rows 130-{top - 3}) {dotc(up):.3f}")
print(f"   IR level: wall {np.median(I[wall]):.0f}, box {np.median(I[Rb]):.0f}, cylinder {np.median(I[cyl_core]):.0f}, above-top strip {np.median(I[up]):.0f}; "
      f"depth above-top strip {np.nanmedian(Z[up]):.0f} mm")
B = z['Bmean'].astype(float); S = B[0::2, 0::2] + B[0::2, 1::2] + B[1::2, 0::2] + B[1::2, 1::2]
Sh = S - ndimage.gaussian_filter(S, 3); m = np.median(Sh); s = 1.4826 * np.median(np.abs(Sh - m)); Sc = np.clip(Sh, m - 5 * s, m + 5 * s)
def ncc_z(img, t):
    t = t - t.mean(); t = t / np.sqrt((t * t).sum()); n = t.size
    num = signal.fftconvolve(img, t[::-1, ::-1], mode='valid'); s1 = signal.fftconvolve(img, np.ones_like(t), mode='valid')
    s2 = signal.fftconvolve(img * img, np.ones_like(t), mode='valid'); c = num / np.sqrt(np.maximum(s2 - s1 * s1 / n, 1e-12))
    med = np.median(c); return (c.max() - med) / (1.4826 * np.median(np.abs(c - med)))
SC = np.round(np.arange(0.80, 1.0001, 0.01), 2)
bz = lambda img, t: max(ncc_z(img, ndimage.zoom(t, q, order=1)) for q in SC)
def test(img, y, x):
    t = Ih[y:y + 96, x:x + 96]; return bz(img, t), max(bz(img, np.rot90(t, 2)), bz(img, t[:, ::-1]), bz(img, t[::-1, :]))
print(f"4. POST-HOC clipped Bayer (clip +-5 MAD = {5 * s:.2f} DN; {np.mean(np.abs(Sh - m) > 5 * s):.4f} of px clipped)")
for nm, (y, x) in (('wall', (60, 470)), ('box', (150, 300))):
    tz, nz = test(Sc, y, x); print(f"   {nm}: true z {tz:.2f}  null z {nz:.2f}  ratio {tz / nz:.2f}")
big = ndimage.zoom(Ih, 0.90, order=1); big /= big.std(); inj = np.zeros_like(Sc); inj[20:20 + big.shape[0], 30:30 + big.shape[1]] = big[:460, :610]
for a in (0.05, 0.1, 0.2, 0.3, 0.5):
    tz, nz = test(Sc + a * Sc.std() * inj, 60, 470); print(f"   injected a={a:.2f} ({a * Sc.std():.3f} DN rms): true {tz:.2f} null {nz:.2f} -> {'detected' if tz >= 2 * nz else 'missed'}")
