"""
Interleaved split gave 1.85mm; consecutive-block split gave ~8mm on the same sensor.
Interleaving cancels slow drift, blocks do not. So the gap IS the drift. Measure it.

Track a stable ROI's mean depth against wall-clock for 6 minutes from a cold start.
  - thermal warm-up  -> monotonic trend, flattening
  - scene motion     -> irregular, non-monotonic
  - nothing          -> flat; then the earlier disagreement was something else

Records per-frame ROI statistics plus every 30th full frame.
"""
import sys, time; sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import numpy as np, nui
SHIFT=3; DUR=360.0

k = nui.Kinect(nui.INIT_DEPTH)
try:
    k.open_stream(nui.IMG_DEPTH, nui.RES_640x480); time.sleep(1.0)
    warm=[]
    for _ in range(60):
        a,_,_ = k.grab(nui.IMG_DEPTH, timeout_ms=3000); warm.append(a>>SHIFT)
    W = np.stack(warm).astype(np.float32)
    roi = (W>0).all(0) & (W.std(0) < 40)          # valid + not wildly noisy
    print("ROI pixels: %d (%.1f%%)  mean depth %.0f mm" % (roi.sum(), 100*roi.mean(), W.mean(0)[roi].mean()))

    ts=[]; mu=[]; keep=[]; t0=time.time(); i=0
    while time.time()-t0 < DUR:
        a,fn,_ = k.grab(nui.IMG_DEPTH, timeout_ms=3000)
        d = (a>>SHIFT).astype(np.float32)
        m = roi & (d>0)
        ts.append(time.time()-t0); mu.append(d[m].mean())
        if i%30==0: keep.append(d)
        i+=1
finally:
    k.close()

ts=np.array(ts); mu=np.array(mu)
np.savez('drift.npz', ts=ts, mu=mu, frames=np.stack(keep), roi=roi)
print("frames: %d over %.0fs (%.1f fps)" % (ts.size, ts[-1], ts.size/ts[-1]))

print("\n--- ROI mean depth vs time (30s bins) ---")
for lo in range(0, int(ts[-1])-29, 30):
    m=(ts>=lo)&(ts<lo+30)
    if m.sum(): print("  t=%3d-%3ds : %8.3f mm   (sd within bin %.3f)" % (lo,lo+30,mu[m].mean(),mu[m].std()))

drift = mu[ts>ts[-1]-30].mean() - mu[ts<30].mean()
print("\ntotal drift over %.0fs : %+.3f mm" % (ts[-1], drift))
# short-timescale noise for comparison: successive-frame differences
noise = np.diff(mu).std()/np.sqrt(2)
print("frame-to-frame noise on ROI mean : %.4f mm" % noise)
print("drift / noise                    : %.1fx" % (abs(drift)/noise))

# trend vs first/second half slope -- is it flattening (thermal) or linear?
h=ts<ts[-1]/2
s1=np.polyfit(ts[h],mu[h],1)[0]*60; s2=np.polyfit(ts[~h],mu[~h],1)[0]*60
print("slope first half : %+.3f mm/min" % s1)
print("slope 2nd half   : %+.3f mm/min" % s2)
print("VERDICT: %s" % ("THERMAL WARM-UP (slope decaying)" if abs(s2)<0.6*abs(s1) and abs(s1)>0.05
                       else "not a decaying thermal trend"))
