"""
Does the thermal drift ever settle?

At t=6min it was still +0.78 mm/min. The sensor has now been powered ~40 min, so this
measures the TAIL, not a cold start (I cannot power-cycle it remotely). Question: does
the slope reach zero, and what is the residual wander once it does?

45 minutes, ROI mean depth per frame. Reports slope per 5-min block, so a settling
curve is visible directly rather than inferred.
"""
import sys, time; sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import numpy as np, nui
SHIFT=3; DUR=2700.0

k = nui.Kinect(nui.INIT_DEPTH)
try:
    k.open_stream(nui.IMG_DEPTH, nui.RES_640x480); time.sleep(1.0)
    W = np.stack([(k.grab(nui.IMG_DEPTH,timeout_ms=3000)[0]>>SHIFT) for _ in range(60)]).astype(np.float32)
    roi = (W>0).all(0) & (W.std(0) < 40)
    print("ROI %d px, mean depth %.0f mm" % (roi.sum(), W.mean(0)[roi].mean()), flush=True)
    ts=[]; mu=[]; t0=time.time(); nxt=300
    while time.time()-t0 < DUR:
        a,_,_ = k.grab(nui.IMG_DEPTH, timeout_ms=3000)
        d=(a>>SHIFT).astype(np.float32); m=roi&(d>0)
        ts.append(time.time()-t0); mu.append(d[m].mean())
        if ts[-1] > nxt:
            t=np.array(ts); u=np.array(mu); w=t>t[-1]-300
            print("t=%4.0fs  mean %.3f mm   slope(last 5min) %+.4f mm/min"
                  % (t[-1], u[w].mean(), np.polyfit(t[w],u[w],1)[0]*60), flush=True)
            nxt += 300
finally:
    k.close()
ts=np.array(ts); mu=np.array(mu)
np.savez('warmup.npz', ts=ts, mu=mu)
print("\n--- 5-minute blocks ---", flush=True)
for lo in range(0,int(ts[-1])-299,300):
    m=(ts>=lo)&(ts<lo+300)
    if m.sum()>10:
        print("  %4d-%4ds  mean %9.3f  slope %+.4f mm/min  sd %.3f"
              % (lo,lo+300,mu[m].mean(),np.polyfit(ts[m],mu[m],1)[0]*60,mu[m].std()))
print("\ntotal excursion over %.0f min: %+.3f mm" % (ts[-1]/60, mu[ts>ts[-1]-120].mean()-mu[ts<120].mean()))
