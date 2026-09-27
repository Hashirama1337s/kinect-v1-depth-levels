"""
Capability map: which (image type, resolution) pairs does SDK 1.8 actually accept
on THIS sensor? Documentation and folklore disagree; ask the hardware.

Then: the IR stream's real bit depth. Values top out at 65280 = 0xFF00, so the low
bits may be structurally zero -- same trick as the depth lattice. The GCD of all
distinct values reveals the true granularity.
"""
import sys, time; sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import numpy as np, nui
from math import gcd
from functools import reduce

TYPES = [("DEPTH_AND_PLAYER_INDEX",0),("COLOR",1),("COLOR_YUV",2),("COLOR_RAW_YUV",3),
         ("DEPTH",4),("COLOR_INFRARED",5),("COLOR_RAW_BAYER",6)]
RES   = [("80x60",0),("320x240",1),("640x480",2),("1280x960",3)]

print("%-24s %-10s %s" % ("image type","resolution","result"))
print("-"*52)
ok=[]
for tn,tv in TYPES:
    for rn,rv in RES:
        flags = nui.INIT_DEPTH | nui.INIT_COLOR
        k = nui.Kinect(flags)
        try:
            k.open_stream(tv, rv)
            print("%-24s %-10s OK" % (tn,rn)); ok.append((tn,tv,rn,rv))
        except OSError as e:
            code = str(e).split('0x')[-1]
            print("%-24s %-10s %s" % (tn,rn, "E_INVALIDARG" if code=="80070057" else code))
        finally:
            k.close()
        time.sleep(0.15)

print("\naccepted combinations: %d" % len(ok))

# ---- IR bit depth
k = nui.Kinect(nui.INIT_DEPTH | nui.INIT_COLOR)
try:
    k.open_stream(nui.IMG_COLOR_INFRARED, nui.RES_640x480); time.sleep(1.5)
    ir = np.stack([k.grab(nui.IMG_COLOR_INFRARED, timeout_ms=4000)[0] for _ in range(20)])
finally:
    k.close()
np.save('ir_640.npy', ir[0])
u = np.unique(ir)
g = reduce(gcd, u.tolist())
print("\n--- IR stream, 640x480 ---")
print("range %d..%d   distinct values %d" % (u.min(), u.max(), u.size))
print("GCD of all values : %d  -> low %d bits are structurally zero" % (g, int(np.log2(g)) if g and (g&(g-1))==0 else -1))
print("effective bit depth: %.1f bits  (%d levels spanning the range)"
      % (np.log2(u.size), u.size))

# ---- projector dot pattern
img = ir[0].astype(np.float64)
c = img[120:360, 200:440]
from numpy.lib.stride_tricks import sliding_window_view
w = sliding_window_view(c,(3,3))
pk = (w.max(axis=(-2,-1))==c[1:-1,1:-1]) & (c[1:-1,1:-1] > np.percentile(c,88))
ys,xs = np.where(pk)
print("\n--- projector dot pattern (640x480 IR, 240x240 crop) ---")
print("local maxima: %d   density %.4f dots/px" % (ys.size, ys.size/c.size))
if ys.size>50:
    pts=np.c_[ys,xs].astype(float)
    rng=np.random.default_rng(0); sub=pts[rng.choice(len(pts),min(1500,len(pts)),replace=False)]
    d=np.hypot(sub[:,None,0]-sub[None,:,0], sub[:,None,1]-sub[None,:,1]); np.fill_diagonal(d,np.inf)
    nn=d.min(1)
    print("nearest-neighbour spacing: median %.2f px  sd %.2f" % (np.median(nn), nn.std()))
    print("=> ~%.0f dots across the 640px field, ~%.0f dots total in view"
          % (640/np.median(nn), (640/np.median(nn))*(480/np.median(nn))))
# temporal stability of the pattern: is it fixed?
print("\npattern fixed over 20 frames? corr(frame0, frame19) = %.4f"
      % np.corrcoef(ir[0].ravel().astype(float), ir[19].ravel().astype(float))[0,1])
