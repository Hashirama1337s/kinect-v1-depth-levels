"""Silhouette edges: depth image vs IR image, edge by edge (existing captures; same camera, sequential sessions of a still scene).

Prints, for each listed edge, the IR profile (20-frame mean, averaged along the edge, which averages out the dots) and the depth
profile (temporal-median depth, averaged the same way), and two sub-pixel crossings in pixel-centre coordinates:
  IR    : mid-level crossing between the median IR level on the inside band and on the outside band (walking from the inside);
  depth : mid-depth crossing between the inside and outside depth levels (walking from the inside).
delta = depth - IR (px, along +col or +row). These deltas mix a pure image offset, the depth engine's behaviour at a depth jump, the
projector shadow (right-hand side of near objects in this image) and reflectance/print at the edge; see ir_depth_register.py for the
offset measured from the dots themselves. Edges flagged 'print' or 'shadow' are listed for the record, not used for an offset.
usage: python ir_depth_offset.py"""
import os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
# (capture, label, 'col' edge (profile along columns, averaged over rows) or 'row' edge, averaging range, profile range,
#  inside band, outside band (both as ranges of positions), flag)
EDGES = [
    ('paper1', 'paper stack, left', 'col', (205, 275), (228, 252), (242, 252), (228, 236), ''),
    ('paper1', 'paper stack, right', 'col', (205, 275), (352, 380), (352, 360), (364, 371), 'shadow side (bright object)'),
    ('paper1', 'paper stack, top', 'row', (255, 350), (186, 212), (203, 212), (186, 195), ''),
    ('dark', 'box face, left', 'col', (170, 230), (254, 280), (268, 280), (254, 261), 'print at edge'),
    ('dark', 'box face, right', 'col', (170, 230), (425, 452), (425, 433), (442, 452), 'dark print + shadow side'),
    ('dark', 'box face, top', 'row', (300, 400), (124, 150), (142, 150), (124, 133), 'print at edge'),
    ('env', 'backing board, right', 'col', (190, 260), (355, 390), (355, 366), (378, 390), 'dark + 1 px shadow; 40 mm step'),
    ('env', 'backing board, top', 'row', (240, 340), (155, 185), (174, 185), (155, 164), '25 mm step'),
    ('mug', 'black mug body, left', 'col', (275, 306), (310, 332), (324, 332), (310, 318), ''),
    ('mug', 'black mug rim, top', 'row', (330, 366), (235, 262), (250, 262), (235, 243), ''),
    ('p3', 'box face, top', 'row', (310, 371), (50, 72), (65, 72), (50, 58), 'print at edge'),
]


def load(tag):
    z = np.load(os.path.join(HERE, '..', f'dark_room_{tag}.npz'))
    I = (z['I'] >> 6).astype(np.float64).mean(0)
    D = z['D'].astype(np.float64); D[D == 0] = np.nan
    with np.errstate(all='ignore'):
        Z = np.nanmedian(D, 0)
    return I, Z


def cross(p, pos, level, from_end):
    idx = list(range(len(p)))
    if from_end:
        idx = idx[::-1]
    for a, b in zip(idx[:-1], idx[1:]):
        u, v = p[a] - level, p[b] - level
        if np.isfinite(u) and np.isfinite(v) and u * v <= 0 and u != v:
            return pos[a] + (pos[b] - pos[a]) * u / (u - v)
    return np.nan


cache = {}
print(f"{'capture':7s} {'edge':26s}  IR cross  depth cross  delta   flag")
for tag, label, kind, avg, prof, inside, outside, flag in EDGES:
    if tag not in cache:
        cache[tag] = load(tag)
    I, Z = cache[tag]
    pos = np.arange(prof[0], prof[1] + 1)
    with np.errstate(all='ignore'):
        if kind == 'col':
            pI = I[avg[0]:avg[1] + 1][:, pos].mean(0); pZ = np.nanmedian(Z[avg[0]:avg[1] + 1][:, pos], 0)
        else:
            pI = I[pos][:, avg[0]:avg[1] + 1].mean(1); pZ = np.nanmedian(Z[pos][:, avg[0]:avg[1] + 1], 1)
    sel = lambda rng: (pos >= rng[0]) & (pos <= rng[1])
    iI, oI = np.median(pI[sel(inside)]), np.median(pI[sel(outside)])
    iZ, oZ = np.nanmedian(pZ[sel(inside)]), np.nanmedian(pZ[sel(outside)])
    from_end = inside[0] > outside[0]                       # inside lies at the high end of the profile -> walk backwards
    cI = cross(pI, pos, 0.5 * (iI + oI), from_end)
    cZ = cross(np.where(np.isfinite(pZ), pZ, oZ), pos, 0.5 * (iZ + oZ), from_end)
    print(f"{tag:7s} {label:26s}  {cI:7.2f}   {cZ:9.2f}   {cZ - cI:+6.2f}   {flag}")
    print(f"        pos  " + " ".join(f"{p:5d}" for p in pos))
    print(f"        IR   " + " ".join(f"{v:5.0f}" for v in pI))
    print(f"        z    " + " ".join(f"{v:5.0f}" for v in pZ))
