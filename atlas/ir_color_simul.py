"""Follow-up to ir_depth_simul.py (which found that COLOR 640x480 could be OPENED while IR + depth were streaming, against the SDK
1.8 'Color Stream' page: "impossible to have a color image stream and an infrared image stream open at the same time").
Question: after COLOR is opened, do BOTH the IR handle and the COLOR handle keep delivering genuine frames of their own kind?
Probe (~10 s, below-normal priority): NuiInitialize(DEPTH | COLOR); open IR 640x480 + DEPTH 640x480; grab 2 s; open COLOR 640x480;
then for ~5 s grab IR, DEPTH, COLOR in turn. Classify every delivered 'IR' frame: genuine IR = raw values all multiples of 64 (10-bit
<< 6) and dot contrast >= 0.3; every delivered 'COLOR' frame: 4 bytes per pixel with channel spread (B, G, R differ) > 2 DN.
Bar fixed before the run: IR+COLOR TOGETHER if, after COLOR opens, >= 90 % of attempts deliver genuine IR AND >= 90 % deliver genuine
colour. SWITCHED if one of the two stops (< 10 %) or turns into the other kind. Otherwise no verdict.
Frames are not saved. usage: python ir_color_simul.py"""
import os, sys, time, ctypes
import numpy as np
from scipy import ndimage

ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000)
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..'))
import nui


def ir_kind(a):
    a = np.asarray(a)
    if a.dtype != np.uint16 or a.size != 640 * 480:
        return 'other'
    if np.any(a % 64):
        return 'not-10bit'
    I = (a >> 6).astype(np.float64).reshape(480, 640)
    hp = I - ndimage.gaussian_filter(I, 3)
    c = np.median(np.sqrt(ndimage.uniform_filter(hp * hp, 7)) / np.maximum(ndimage.uniform_filter(I, 7), 1))
    return 'IR' if c >= 0.3 else f'flat({c:.2f})'


def col_kind(a):
    a = np.asarray(a).ravel()
    if a.size != 640 * 480 * 4:
        return f'size{a.size}'
    px = a.reshape(-1, 4)[:, :3].astype(np.float64)
    spread = np.median(np.abs(px[:, 0] - px[:, 1]) + np.abs(px[:, 1] - px[:, 2]))
    return 'COLOR' if spread > 2 else f'grey({spread:.1f})'


k = nui.Kinect(nui.INIT_DEPTH | nui.INIT_COLOR)
res = {'IR': [], 'DEPTH': [], 'COLOR': []}
try:
    k.open_stream(nui.IMG_COLOR_INFRARED, nui.RES_640x480); k.open_stream(nui.IMG_DEPTH, nui.RES_640x480)
    time.sleep(1.5)
    pre = []
    for _ in range(20):
        try: pre.append(ir_kind(k.grab(nui.IMG_COLOR_INFRARED, timeout_ms=1000)[0]))
        except OSError: pre.append('miss')
    print("before COLOR opens, IR frames:", {x: pre.count(x) for x in set(pre)})
    k.open_stream(nui.IMG_COLOR, nui.RES_640x480); time.sleep(1.0)
    t0 = time.time(); n = 0
    while time.time() - t0 < 5.0:
        n += 1
        try: res['IR'].append(ir_kind(k.grab(nui.IMG_COLOR_INFRARED, timeout_ms=700)[0]))
        except OSError: res['IR'].append('miss')
        try: d = k.grab(nui.IMG_DEPTH, timeout_ms=700)[0]; res['DEPTH'].append('ok' if (d >> 3).max() > 0 else 'empty')
        except OSError: res['DEPTH'].append('miss')
        try: res['COLOR'].append(col_kind(k.grab(nui.IMG_COLOR, timeout_ms=700, dtype=np.uint8)[0]))
        except OSError: res['COLOR'].append('miss')
finally:
    k.close()
for s, v in res.items():
    print(f"after COLOR opens, {s:5s} ({len(v)} attempts):", {x: v.count(x) for x in sorted(set(v))})
fI = res['IR'].count('IR') / max(len(res['IR']), 1); fC = res['COLOR'].count('COLOR') / max(len(res['COLOR']), 1)
if fI >= 0.9 and fC >= 0.9:
    print("VERDICT: IR+COLOR TOGETHER")
elif fI < 0.1 or fC < 0.1:
    print("VERDICT: SWITCHED (one stream stops or changes kind)")
else:
    print("VERDICT: no verdict")
