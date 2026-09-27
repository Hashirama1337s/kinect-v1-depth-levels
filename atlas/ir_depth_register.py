"""Depth-image vs IR-image pixel registration WITHOUT reflectance edges (existing captures only).

Silhouette edges mix three things: a pure pixel offset between the depth and IR images, the depth engine's behaviour at a depth jump
(which side 'wins' a correlation window that straddles the edge) and reflectance/print at the edge. Here the IR side is replaced by
a disparity-CHANGE map computed from the IR pattern itself, so both maps come from the same dots:
  M_IR(x, y) : horizontal shift (px) of the 9x9 IR pattern patch centred at IR pixel (x, y) in capture A, found in capture B
               (same camera pose; an object added in A). Band-passed, contrast-normalised IR; NCC; parabola sub-pixel; dy fixed 0.
  M_D(u, v)  : the same quantity predicted from the SDK depth maps, K (1/z_A - 1/z_B), K = 43 186 px*mm (ir_shift_scale.py).
If depth pixel (u, v) looks at IR pixel (u + ox, v + oy), then M_D(u, v) = M_IR(u + ox, v + oy). (ox, oy) is found by least squares
over a window around the object (bilinear resampling, 0.1 px grid), and separately on bands around each edge (left/right/top).
A 9x9 window is close to the 9x7/9x9 the public reverse-engineering attributes to the PS1080, so edge 'snapping' biases should be
similar in both maps (partly cancelling); the per-edge fits show how much remains.

Captures: A = paper1 (paper stack at ~1.00 m), B = phone (same pose; wall at ~1.32 m where the stack stands).
usage: python ir_depth_register.py"""
import os
import numpy as np
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
K = 120 / (2 * 0.1042) * 75


def load(tag):
    z = np.load(os.path.join(HERE, '..', f'dark_room_{tag}.npz'))
    I = (z['I'] >> 6).astype(np.float64).mean(0)
    B = ndimage.gaussian_filter(I, 0.7) - ndimage.gaussian_filter(I, 4)
    B /= np.maximum(ndimage.gaussian_filter(np.abs(B), 8), 1e-6)
    D = z['D'].astype(np.float64); D[D == 0] = np.nan
    with np.errstate(all='ignore'):
        Z = np.nanmedian(D, 0); V = np.isfinite(D).mean(0)
    Z[V < 0.9] = np.nan
    return B, Z


def shift_map(A, B, dxs, w=9):
    f = lambda a: ndimage.uniform_filter(a, w)
    mA = f(A); vA = f(A * A) - mA ** 2
    C = []
    for dx in dxs:
        Bs = np.roll(B, -dx, axis=1)                       # Bs[y, x] = B[y, x + dx]
        mB = f(Bs); vB = f(Bs * Bs) - mB ** 2
        C.append((f(A * Bs) - mA * mB) / np.sqrt(np.maximum(vA * vB, 1e-12)))
    C = np.array(C); i = np.argmax(C, 0); c = np.take_along_axis(C, i[None], 0)[0]
    im, ip = np.clip(i - 1, 0, len(dxs) - 1), np.clip(i + 1, 0, len(dxs) - 1)
    cm = np.take_along_axis(C, im[None], 0)[0]; cp = np.take_along_axis(C, ip[None], 0)[0]
    den = cm - 2 * c + cp; sub = np.where(den < 0, 0.5 * (cm - cp) / np.where(den < 0, den, -1), 0.0)
    return np.array(dxs)[i] + sub, c


BA, ZA = load('paper1'); BB, ZB = load('phone')
MI, cI = shift_map(BA, BB, list(range(-4, 17)))
MI[cI < 0.4] = np.nan
MD = K * (1 / ZA - 1 / ZB)

# region around the stack: rows 185..250 (above the phone / mug), cols 225..385
r0, r1, c0, c1 = 185, 250, 225, 385
yy, xx = np.mgrid[r0:r1, c0:c1]


def fit(mask, label):
    best = None
    for oy in np.arange(-6, 6.01, 0.1):
        for ox in np.arange(-8, 8.01, 0.1):
            m = ndimage.map_coordinates(MI, [yy + oy, xx + ox], order=1, mode='nearest', cval=np.nan)
            d = (MD[r0:r1, c0:c1] - m)[mask]
            d = d[np.isfinite(d)]
            if d.size < 50:
                continue
            s = np.mean(d ** 2)
            if best is None or s < best[0]:
                best = (s, ox, oy, d.size)
    if best:
        print(f"  {label:34s}: ox {best[1]:+.1f}  oy {best[2]:+.1f}  rms {np.sqrt(best[0]):.2f} px  (n {best[3]})")
    return best


# edges of the stack in the depth map (for the per-edge bands)
st = np.isfinite(ZA) & (np.abs(ZA - 1003) < 30)
lab, _ = ndimage.label(st); big = lab == np.argmax(np.bincount(lab.ravel())[1:]) + 1
ys, xs = np.nonzero(big); top, left, right = ys.min(), xs.min(), xs.max()
print(f"stack in depth: top row {top}, cols {left}-{right};  M_IR valid {np.isfinite(MI[r0:r1, c0:c1]).mean():.2f} of the window")
print("least-squares registration, M_D(u,v) = M_IR(u+ox, v+oy):")
fit(np.ones_like(yy, bool), 'whole window')
fit((np.abs(xx - left) <= 8) & (yy >= top + 6), 'left edge band (x only)')
fit((np.abs(xx - right) <= 8) & (yy >= top + 6), 'right edge band (x only; shadow side)')
fit((np.abs(yy - top) <= 8) & (xx > left + 8) & (xx < right - 8), 'top edge band (y only)')
# 1-D profiles across the edges, both maps, for the record
for name, sl, ax in (('left', (slice(top + 8, r1), slice(left - 8, left + 9)), 0),
                     ('top', (slice(top - 8, top + 9), slice(left + 12, right - 12)), 1)):
    pm = np.nanmedian(MD[sl], axis=ax); pi = np.nanmedian(MI[sl], axis=ax)
    print(f"  {name} profile (pos, M_D, M_IR):")
    base = (left - 8) if name == 'left' else (top - 8)
    print("    " + " ".join(f"{base + i:4d}" for i in range(len(pm))))
    print("    " + " ".join(f"{v:4.1f}" for v in pm))
    print("    " + " ".join(f"{v:4.1f}" for v in pi))

# step midpoints, edge by edge (median over the rows / columns of the edge): where each map crosses half of the object's step
def mid_cross(p, pos, lo, hi, rising):
    h = 0.5 * (lo + hi)
    for i in range(len(p) - 1):
        a, b = p[i] - h, p[i + 1] - h
        if np.isfinite(a) and np.isfinite(b) and ((a < 0 <= b) if rising else (a >= 0 > b)):
            return pos[i] + (pos[i + 1] - pos[i]) * (-a) / (b - a)
    return np.nan


step = np.nanmedian(MD[top + 10:r1, left + 10:right - 10])
print(f"\nstep midpoints (object step {step:.1f} px of disparity change); pure offset: depth edge = IR-pattern edge - o")
for name, lines, rng, rising in (('left', range(top + 8, r1), np.arange(left - 12, left + 13), True),
                                 ('right', range(top + 8, r1), np.arange(right - 12, right + 13), False),
                                 ('top', range(left + 12, right - 12), np.arange(top - 12, top + 13), True)):
    eD, eI = [], []
    for L in lines:
        pd = MD[L, rng] if name != 'top' else MD[rng, L]
        pi = MI[L, rng] if name != 'top' else MI[rng, L]
        eD.append(mid_cross(np.nan_to_num(pd, nan=0.0), rng, 0.0, step, rising))
        eI.append(mid_cross(np.nan_to_num(pi, nan=0.0), rng, 0.0, step, rising))
    eD, eI = np.array(eD), np.array(eI); ok = np.isfinite(eD) & np.isfinite(eI)
    print(f"  {name:5s}: depth edge {np.median(eD[ok]):6.2f}   IR-pattern edge {np.median(eI[ok]):6.2f}   "
          f"depth - IR {np.median(eD[ok] - eI[ok]):+.2f} px (IQR {np.percentile(eD[ok] - eI[ok], 25):+.2f}..{np.percentile(eD[ok] - eI[ok], 75):+.2f}, n {ok.sum()})")
