"""
Recover the Kinect's hidden disparity lattice from the SDK's millimetre output.

HYPOTHESIS (structured light):  z = fb/d  with d quantised in integer steps.
  => 1/z is UNIFORMLY spaced.  Spacing of 1/z  =  dd/(fb).
  => spacing in z grows as  dz = (dd/fb) * z^2   (quadratic)

CONTROL (a sensor quantised uniformly in distance, e.g. naive time-of-flight):
  => z itself is uniformly spaced, and 1/z is NOT.

These two make opposite predictions, so the test can fail. We measure the
coefficient of variation (CV) of the gaps under each model; the smaller CV wins.
"""
import sys, time; sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import numpy as np, nui

SHIFT = 3   # NUI_IMAGE_PLAYER_INDEX_SHIFT

k = nui.Kinect(nui.INIT_DEPTH)
seen = set()
try:
    k.open_stream(nui.IMG_DEPTH, nui.RES_640x480)
    time.sleep(1.0)
    t0 = time.time()
    n = 0
    while n < 200:
        a, fn, ts = k.grab(nui.IMG_DEPTH, timeout_ms=3000)
        mm = (a >> SHIFT).astype(np.int32)
        seen.update(np.unique(mm[mm > 0]).tolist())
        n += 1
    print("frames: %d in %.1fs   unique depths accumulated: %d" % (n, time.time()-t0, len(seen)))
finally:
    k.close()

z = np.array(sorted(seen), dtype=np.float64)
z = z[(z > 500) & (z < 4000)]
print("range: %.0f .. %.0f mm   (%d levels)" % (z.min(), z.max(), z.size))

gz  = np.diff(z)
inv = 1.0/z
gi  = np.abs(np.diff(inv))
# drop any duplicate-adjacent artefacts
gz, gi = gz[gz>0], gi[gi>0]

cv = lambda x: x.std()/x.mean()
print("\n--- which lattice is uniform? (lower CV wins; these disagree by construction) ---")
print("CV of gaps in  z   (uniform-in-distance model) : %.4f" % cv(gz))
print("CV of gaps in 1/z  (structured-light  model)   : %.4f" % cv(gi))

step = np.median(gi)
fb_over_dd = 1.0/step
print("\nmedian spacing of 1/z : %.6e  1/mm" % step)
print("=> f*b/dd = %.1f  px*mm per disparity step" % fb_over_dd)

print("\n--- quantisation step vs range (predicted dz = z^2 / %.0f) ---" % fb_over_dd)
mid = 0.5*(z[:-1]+z[1:])
obs = np.diff(z)
for target in (600, 1000, 1500, 2000, 2500, 3000, 3500):
    if mid.min() <= target <= mid.max():
        sel = np.abs(mid-target) < 150
        if sel.sum() >= 3:
            print("  z=%4d mm : observed %6.2f mm   predicted %6.2f mm"
                  % (target, np.median(obs[sel]), target**2/fb_over_dd))

# published Kinect v1 geometry: baseline ~75 mm, focal ~585 px, disparity in 1/8 px
pred = 585.0*75.0*8.0
print("\ncross-check against published geometry (b=75mm, f=585px, 1/8-px disparity):")
print("  expected f*b/dd = %.0f      measured = %.0f      ratio = %.3f"
      % (pred, fb_over_dd, fb_over_dd/pred))
np.save('depth_lattice.npy', z)
