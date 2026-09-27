"""Can the IR stream and the depth stream run at the same time on this Xbox 360 sensor under SDK 1.8?  (new capture, ~10 s)

Public: Microsoft's SDK 1.8 'Color Stream' page says a colour stream and an infrared stream cannot be open together; no Microsoft page
found that says IR + depth works (secondary sources say it does). libfreenect refuses 1280x1024 IR together with depth.
Probe: one NuiInitialize(DEPTH | COLOR), open COLOR_INFRARED 640x480 and DEPTH 640x480, grab them alternately for ~6 s.
Bar fixed before the run:
  SIMULTANEOUS if both streams deliver >= 90 % of the attempted grabs AND the IR frames grabbed while depth is streaming show the
  dot pattern (median band-pass contrast >= 0.3 over the frame) AND the depth frames are >= 50 % valid.
  NOT SIMULTANEOUS if opening the second stream fails or either stream delivers < 10 % of grabs.
Then (same session) try to open COLOR 640x480 as a third stream: expected to fail per the SDK page; the HRESULT is recorded.
Frames are kept locally only (../atlas_simul_ir_depth.npz, outside the script folder; a capture of a room is never published).
Runs at below-normal process priority. usage: python ir_depth_simul.py"""
import os, sys, time, ctypes
import numpy as np
from scipy import ndimage

ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000)   # BELOW_NORMAL_PRIORITY_CLASS
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..'))
import nui

k = nui.Kinect(nui.INIT_DEPTH | nui.INIT_COLOR)
try:
    k.open_stream(nui.IMG_COLOR_INFRARED, nui.RES_640x480)
    try:
        k.open_stream(nui.IMG_DEPTH, nui.RES_640x480)
    except OSError as e:
        print("opening DEPTH while IR is open FAILED:", e); print("VERDICT: NOT SIMULTANEOUS"); raise SystemExit
    time.sleep(1.5)
    IR, DP, fnI, fnD, missI, missD = [], [], [], [], 0, 0
    t0 = time.time(); tries = 0
    while time.time() - t0 < 6.0:
        tries += 1
        try:
            a, fn, _ = k.grab(nui.IMG_COLOR_INFRARED, timeout_ms=1000); fnI.append(fn)
            if len(IR) < 30: IR.append(a)
        except OSError:
            missI += 1
        try:
            d, fn, _ = k.grab(nui.IMG_DEPTH, timeout_ms=1000); fnD.append(fn)
            if len(DP) < 30: DP.append((d >> 3).astype(np.int16))
        except OSError:
            missD += 1
    third = 'not tried'
    try:
        k.open_stream(nui.IMG_COLOR, nui.RES_640x480); third = 'OPENED (unexpected)'
        try:
            k.grab(nui.IMG_COLOR, timeout_ms=1500, dtype=np.uint8); third += ', and a colour frame arrived'
        except OSError as e:
            third += f', but no colour frame: {e}'
    except OSError as e:
        third = f'rejected: {e}'
finally:
    k.close()

IR = np.stack(IR) if IR else np.zeros((0, 480, 640), np.uint16); DP = np.stack(DP) if DP else np.zeros((0, 480, 640), np.int16)
np.savez_compressed(os.path.join(HERE, '..', 'atlas_simul_ir_depth.npz'), I=IR, D=DP, fnI=np.array(fnI), fnD=np.array(fnD))
okI, okD = 1 - missI / tries, 1 - missD / tries
print(f"attempts {tries}: IR delivered {tries - missI} ({100 * okI:.0f} %), depth delivered {tries - missD} ({100 * okD:.0f} %)")
print(f"distinct frame numbers: IR {len(set(fnI))}, depth {len(set(fnD))}")
contrast = np.nan; valid = np.nan
if len(IR):
    I = (IR >> 6).astype(np.float64).mean(0)
    hp = I - ndimage.gaussian_filter(I, 3)
    contrast = np.median(np.sqrt(ndimage.uniform_filter(hp * hp, 7)) / np.maximum(ndimage.uniform_filter(I, 7), 1))
    from functools import reduce
    g = reduce(np.gcd, np.unique(IR).astype(np.int64))
    print(f"IR while depth streams: 10-bit mean {I.mean():.1f}, median dot contrast {contrast:.2f}, GCD of raw values {g}")
if len(DP):
    valid = (DP > 0).mean()
    print(f"depth while IR streams: valid fraction {valid:.3f}, median {np.median(DP[DP > 0]):.0f} mm")
print("third stream COLOR 640x480 in the same session:", third)
if okI >= 0.9 and okD >= 0.9 and contrast >= 0.3 and valid >= 0.5:
    print("VERDICT: SIMULTANEOUS")
elif okI < 0.1 or okD < 0.1:
    print("VERDICT: NOT SIMULTANEOUS")
else:
    print("VERDICT: no verdict")
