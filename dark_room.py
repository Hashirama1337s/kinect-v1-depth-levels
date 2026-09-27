"""Dark-room capture (2026-09-26): lights dimmed; in view, the known-width box (13.000 in = 330.2 mm, hand tape) and a clear/translucent
plastic cylinder (hand ruler: 44 mm wide, 144 mm tall). Three sequential sessions on a warmed sensor, saved locally only (a capture of a
room is never published; the repo carries code and summary numbers):
  depth : 90 frames 640x480 (mm = raw >> 3)
  bayer : 60 frames COLOR_RAW_BAYER 1280x960 after 4 s for auto-exposure to settle (per-frame means kept to show whether it did)
  ir    : 20 frames COLOR_INFRARED 640x480 (the projector's dots: the positive control for the dot-leak test)
usage: python dark_room.py [--tag=dark]"""
import sys, time, os
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import nui
TAG = next((a.split('=')[1] for a in sys.argv if a.startswith('--tag=')), 'dark')

def session(init, img, res, n, settle, dtype=np.uint16):
    k = nui.Kinect(init)
    try:
        k.open_stream(img, res); time.sleep(settle)
        F, T = [], []
        for _ in range(n):
            a, fn, t = k.grab(img, timeout_ms=5000, dtype=dtype); F.append(a); T.append(t)
        return np.stack(F), np.array(T, dtype=np.float64)
    finally:
        k.close()

D, Td = session(nui.INIT_DEPTH, nui.IMG_DEPTH, nui.RES_640x480, 90, 1.0)
D = (D >> 3).astype(np.int16)
print(f"depth: {D.shape}, {(Td[-1] - Td[0]) / 1000:.1f} s, valid in every frame {np.mean((D > 0).all(0)):.3f}")
B, Tb = session(nui.INIT_DEPTH | nui.INIT_COLOR, nui.IMG_COLOR_RAW_BAYER, nui.RES_1280x960, 60, 4.0, dtype=np.uint8)
fm = B.reshape(len(B), -1).mean(1)
print(f"bayer: {B.shape}, {len(B) / max((Tb[-1] - Tb[0]) / 1000, 1e-9):.1f} fps, frame mean {fm.min():.2f}..{fm.max():.2f} "
      f"(first 5 {fm[:5].round(2).tolist()}), saturated px {np.mean(B == 255):.5f}")
I, Ti = session(nui.INIT_DEPTH | nui.INIT_COLOR, nui.IMG_COLOR_INFRARED, nui.RES_640x480, 20, 1.5)
print(f"ir: {I.shape}, range {I.min()}..{I.max()}, mean {I.mean():.1f}")
Bf = B.astype(np.float64)
np.savez_compressed(os.path.join(HERE, f'dark_room_{TAG}.npz'), D=D, Td=Td, Bmean=Bf.mean(0).astype(np.float32),
                    Bstd=Bf.std(0).astype(np.float32), Braw=B[[0, 30, 59]], Bfm=fm, Tb=Tb, I=I, Ti=Ti)
print("saved", f'dark_room_{TAG}.npz')
