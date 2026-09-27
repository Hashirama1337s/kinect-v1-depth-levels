"""
Why did averaging saturate at 2-3x instead of sqrt(N)?

Hypothesis: per-pixel depth noise is NOT white -- it has long temporal correlation.
Consequences if true, both of which are checkable:
  (a) averaging N frames gains far less than sqrt(N)
  (b) INTERLEAVED split-half is biased LOW, because adjacent frames share the same
      slow excursion -> that would make the 1.85 mm figure an artefact of my estimator.

Global drift is removed first: it is a constant offset per frame and both split-half
statistics take a SPATIAL std, which cancels it. So drift cannot be the explanation
and must not be allowed to masquerade as one.
"""
import numpy as np
d = np.load('drift.npz')
F, roi = d['frames'].astype(np.float64), d['roi']      # every 30th frame => 1 Hz
print("decimated stack:", F.shape, " (1 frame/sec)")

m = roi & (F > 0).all(0)
X = F[:, m]                                             # (T, P)
T, P = X.shape
print("pixels tracked: %d over %d seconds" % (P, T))

# remove the global per-frame offset (the drift) -- this is exactly what a spatial std does
X = X - X.mean(1, keepdims=True)
X = X - X.mean(0, keepdims=True)                        # per-pixel mean

def autocorr(lag):
    a, b = X[:-lag], X[lag:]
    num = (a*b).mean()
    return num / X.var()

print("\n--- temporal autocorrelation of per-pixel depth, drift removed ---")
print("  (white noise => ~0 at every lag)")
for lag in (1,2,3,5,10,20,40,80,160):
    if lag < T: print("  lag %3ds : r = %+.4f" % (lag, autocorr(lag)))

# effective sample size: how many frames does averaging N actually buy?
print("\n--- averaging gain: block vs interleaved split, same N, same data ---")
print("   N   block-split sigma   interleaved sigma   ratio")
for n in (2,4,8,16,32,64,128):
    if 2*n > T: break
    A, B = X[0:n].mean(0), X[n:2*n].mean(0)             # consecutive blocks
    sb = (A-B).std()/np.sqrt(2)
    idx = np.arange(2*n)
    A2, B2 = X[idx[0::2]].mean(0), X[idx[1::2]].mean(0) # interleaved
    si = (A2-B2).std()/np.sqrt(2)
    print("  %4d  %14.4f  %17.4f  %6.2fx" % (n, sb, si, sb/max(si,1e-12)))

s1 = (X[0:1].mean(0)-X[1:2].mean(0)).std()/np.sqrt(2)
nmax = T//2
Ab, Bb = X[0:nmax].mean(0), X[nmax:2*nmax].mean(0)
sN = (Ab-Bb).std()/np.sqrt(2)
print("\nsingle-frame sigma %.3f mm -> N=%d block sigma %.3f mm" % (s1, nmax, sN))
print("observed gain %.2fx   ideal sqrt(N) = %.2fx   efficiency %.1f%%"
      % (s1/sN, np.sqrt(nmax), 100*(s1/sN)/np.sqrt(nmax)))
