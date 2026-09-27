"""Known-width target test (2026-09-26): an object of known width (13.000 in = 330.2 mm, measured with a hand tape) facing the Kinect near the image
centre. 90 depth frames (640x480, mm = raw >> 3), per-pixel median; the face = the connected region around the centre within
+-35 mm of the centre patch's depth; width per row = rightmost - leftmost column + 1 over the middle half of its rows;
width_mm = w_px * z / f with the SDK's nominal depth focal length f = 571.26 px (NUI_CAMERA_DEPTH_NOMINAL_FOCAL_LENGTH_IN_PIXELS
285.63 at 320x240) and, for comparison, the often-quoted 585 px. Edge pixels are +-1 px each side (the IR shadow falls on one side).
usage: python box_width.py [--true-mm 330.2]"""
import sys, time
import numpy as np
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import nui
TRUE = float(next((a.split('=')[1] for a in sys.argv if a.startswith('--true-mm=')), 330.2))
k = nui.Kinect(nui.INIT_DEPTH)
try:
    k.open_stream(nui.IMG_DEPTH, nui.RES_640x480); time.sleep(1.0)
    F = [(k.grab(nui.IMG_DEPTH, timeout_ms=3000)[0] >> 3).astype(np.float64) for _ in range(90)]
finally:
    k.close()
S = np.stack(F); S[S == 0] = np.nan
Z = np.nanmedian(S, axis=0)
H, W = Z.shape; cy, cx = H // 2, W // 2
z0 = np.nanmedian(Z[cy - 10:cy + 10, cx - 10:cx + 10])
M = np.abs(Z - z0) < 35
from collections import deque                        # flood fill from the centre
seen = np.zeros_like(M); q = deque([(cy, cx)]); seen[cy, cx] = True
while q:
    y, x = q.popleft()
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        v, u = y + dy, x + dx
        if 0 <= v < H and 0 <= u < W and M[v, u] and not seen[v, u]: seen[v, u] = True; q.append((v, u))
ys, xs = np.nonzero(seen); top, bot = ys.min(), ys.max()
mid = [y for y in range(top + (bot - top) // 4, bot - (bot - top) // 4 + 1)]
widths = []; zs = []
for y in mid:
    c = np.nonzero(seen[y])[0]
    if c.size: widths.append(c.max() - c.min() + 1); zs.append(np.nanmedian(Z[y, c]))
w = float(np.median(widths)); z = float(np.median(zs))
left_z = np.nanmedian(Z[cy, :max(1, np.nonzero(seen[cy])[0].min() - 3)]) if seen[cy].any() else float('nan')
print(f"face: {len(ys)} px, rows {top}-{bot} ({bot - top + 1} px tall), median depth z = {z:.1f} mm (centre patch {z0:.1f})")
print(f"width: median {w:.1f} px over {len(mid)} middle rows (IQR {np.percentile(widths, 25):.0f}-{np.percentile(widths, 75):.0f} px)")
for f in (571.26, 585.0):
    wm = w * z / f; e1 = z / f
    print(f"  f = {f:7.2f} px: width = {wm:6.1f} mm (+-{e1:.1f} mm per edge pixel)  vs true {TRUE:.1f} mm -> {wm - TRUE:+.1f} mm ({100 * (wm / TRUE - 1):+.2f} %)")
print(f"height of the face in the image: {(bot - top + 1) * z / 571.26:.1f} mm (f = 571.26)")
np.savez_compressed('box_width_capture.npz', Z=Z, face=seen)
