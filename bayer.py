"""
Is COLOR_RAW_BAYER genuinely raw sensor data, or debayered output relabelled?

A true Bayer mosaic interleaves colour channels on a 2x2 grid, so:
  - the four 2x2 phases have DIFFERENT intensity statistics (G pixels ~2x R/B)
  - horizontal lag-1 autocorrelation is LOWER than lag-2 (neighbours are different colours)
A debayered/interpolated image has the opposite: lag-1 > lag-2, phases identical.
Both outcomes are computed, so this can fail.
"""
import sys, time; sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import numpy as np, nui

k = nui.Kinect(nui.INIT_DEPTH | nui.INIT_COLOR)
try:
    k.open_stream(nui.IMG_COLOR_RAW_BAYER, nui.RES_1280x960); time.sleep(2.0)
    b,fn,_ = k.grab(nui.IMG_COLOR_RAW_BAYER, timeout_ms=5000, dtype=np.uint8)
finally:
    k.close()
print("raw bayer frame: shape %s dtype %s  range %d..%d" % (b.shape, b.dtype, b.min(), b.max()))
np.save('bayer_1280.npy', b)
a = b.astype(np.float64)

print("\n--- 2x2 phase statistics (a real mosaic makes these differ) ---")
ph = {}
for dy in (0,1):
    for dx in (0,1):
        p = a[dy::2, dx::2]; ph[(dy,dx)] = p.mean()
        print("  phase (%d,%d): mean %8.3f   sd %7.3f" % (dy,dx,p.mean(),p.std()))
means = np.array(list(ph.values()))
spread = means.max()/max(means.min(),1e-9)
print("  max/min phase mean ratio: %.3f" % spread)

def lagcorr(x, lag, axis=1):
    if axis==1: u,v = x[:,:-lag], x[:,lag:]
    else:       u,v = x[:-lag,:], x[lag:,:]
    u = u - u.mean(); v = v - v.mean()
    return (u*v).mean()/np.sqrt((u*u).mean()*(v*v).mean())

h1,h2 = lagcorr(a,1,1), lagcorr(a,2,1)
v1,v2 = lagcorr(a,1,0), lagcorr(a,2,0)
print("\n--- autocorrelation ---")
print("  horizontal lag1 %.4f   lag2 %.4f   lag2>lag1: %s" % (h1,h2,h2>h1))
print("  vertical   lag1 %.4f   lag2 %.4f   lag2>lag1: %s" % (v1,v2,v2>v1))

mosaic = (h2 > h1) and (v2 > v1) and spread > 1.05
print("\nVERDICT: %s" % ("GENUINE BAYER MOSAIC -- raw, undebayered sensor data"
      if mosaic else "NOT a raw mosaic (looks interpolated/processed)"))
if mosaic:
    print("  => linear, un-white-balanced, un-gamma'd photometry at 1280x960")
