"""
Is the temporal correlation in the SENSOR or in the SDK?

Red-team review: "SDK may correlate frames." Decisive because the outcomes differ in what you do:
  SDK smoothing  -> a short, fixed IIR/FIR time constant; bypass it (libfreenect) and
                    recover real sqrt(N) averaging.
  physical       -> long, scale-free-ish decay; no software fix exists.

Full frame rate (33 ms), lags 1..900 (33 ms .. 30 s). Previous run was 1 Hz decimated
and structurally blind to the short lags where an SDK filter would live.

Also computes N_eff = N / (1 + 2*sum(rho)) -- the integrated autocorrelation time.
That is the number of frames you are ACTUALLY averaging, which is the figure anyone
stacking Kinect frames needs and nobody quotes.
"""
import sys, time; sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import numpy as np, nui
SHIFT=3; NF=1800; NPIX=6000

k = nui.Kinect(nui.INIT_DEPTH)
try:
    k.open_stream(nui.IMG_DEPTH, nui.RES_640x480); time.sleep(1.0)
    W = np.stack([(k.grab(nui.IMG_DEPTH,timeout_ms=3000)[0]>>SHIFT) for _ in range(40)]).astype(np.float32)
    ok = np.where(((W>0).all(0) & (W.std(0)<40)).ravel())[0]
    sel = np.random.default_rng(1).choice(ok, NPIX, replace=False)
    print("tracking %d pixels, mean depth %.0f mm" % (NPIX, W.reshape(40,-1)[:,sel].mean()), flush=True)
    X = np.zeros((NF, NPIX), np.float32); t=np.zeros(NF)
    t0=time.time()
    for i in range(NF):
        a,_,_ = k.grab(nui.IMG_DEPTH, timeout_ms=3000)
        X[i] = (a.ravel()[sel] >> SHIFT); t[i]=time.time()-t0
finally:
    k.close()
dt = np.median(np.diff(t))
print("captured %d frames, dt=%.4f s (%.1f fps)" % (NF, dt, 1/dt))

bad = (X<=0).any(0); X = X[:, ~bad]
X = X - X.mean(1, keepdims=True)     # remove global per-frame offset (drift)
X = X - X.mean(0, keepdims=True)     # per-pixel mean
print("usable pixels: %d" % X.shape[1])

var = X.var()
def rho(lag): return float((X[:-lag]*X[lag:]).mean()/var)

print("\n--- autocorrelation at FULL frame rate ---")
for lag in (1,2,3,4,5,8,15,30,60,120,300,600,900):
    print("  lag %4d (%6.2f s) : rho = %+.4f" % (lag, lag*dt, rho(lag)))

# SDK-filter signature: a fixed IIR gives rho(k)=r^k. Test log-linearity at SHORT lags.
sl = np.arange(1,11); rs = np.array([rho(l) for l in sl])
if (rs>0).all():
    p = np.polyfit(sl, np.log(rs), 1)
    pred = np.exp(np.polyval(p, sl))
    err = np.abs(pred-rs).max()
    tau_iir = -1/p[0]
    print("\n--- short-lag shape (lags 1-10) ---")
    print("  best single-exponential tau = %.2f frames (%.3f s); max deviation %.4f" % (tau_iir, tau_iir*dt, err))
    r30 = rho(300)
    print("  a pure IIR with that tau would give rho(300) = %.2e ; observed %.4f"
          % (np.exp(np.polyval(p,300)), r30))
    print("  VERDICT: %s" % ("PHYSICAL -- long tail far exceeds any short IIR"
          if r30 > 20*max(np.exp(np.polyval(p,300)),1e-12) else "consistent with SDK smoothing"))

# integrated autocorrelation time -> effective sample size
lags = np.arange(1, NF//4)
r = np.array([rho(int(l)) for l in lags])
cut = np.argmax(r <= 0) if (r<=0).any() else len(r)
tau_int = 1 + 2*r[:cut].sum()
print("\n--- effective sample size ---")
print("  integrated autocorr time tau_int = %.1f frames (%.2f s)" % (tau_int, tau_int*dt))
for N in (30, 150, 300, 900, 1800):
    print("    stacking %4d frames -> N_eff = %6.1f  (gain %.2fx, ideal %.2fx)"
          % (N, N/tau_int, np.sqrt(N/tau_int), np.sqrt(N)))
np.save('acf_lags.npy', r)
