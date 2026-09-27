"""Offline: does sigma fall as 1/sqrt(N)? Plus ACF and Allan, from one series."""
import json, numpy as np

d = json.load(open("results_sigma_n_raw.json"))
NS = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000]

def sigma_of_n(x, N):
    m = len(x) // N
    if m < 8: return None
    return float(np.std(np.asarray(x[:m*N], float).reshape(m, N).mean(axis=1), ddof=1))

def acf_tau(x):
    x = np.asarray(x, float); x = x - x.mean()
    n = len(x); c = np.correlate(x, x, "full")[n-1:]; c /= c[0]
    below = np.where(c < np.exp(-1))[0]
    return (float(below[0]) if below.size else float("nan")), c

def allan(x, taus):
    x = np.asarray(x, float); out = []
    for t in taus:
        m = len(x)//t
        if m < 3: out.append(None); continue
        y = x[:m*t].reshape(m, t).mean(axis=1)
        out.append(float(np.sqrt(0.5*np.mean(np.diff(y)**2))))
    return out

for locus in ("noisy", "quiet", "patch"):
    x = [v for v in d["series"][locus] if v == v]
    for label, s in (("raw", np.asarray(x, float)),
                     ("detrended(1)", np.asarray(x, float) -
                      np.polyval(np.polyfit(np.arange(len(x)), x, 1), np.arange(len(x))))):
        s1 = sigma_of_n(s, 1)
        print("\n%s / %s   sigma(1) = %.3f mm   n = %d" % (locus, label, s1, len(s)))
        print("     N      sigma(N)   ideal 1/sqrt(N)   ratio")
        for N in NS:
            sn = sigma_of_n(s, N)
            if sn is None: continue
            ideal = s1 / np.sqrt(N)
            print("  %6d   %8.4f   %13.4f   %5.2fx" % (N, sn, ideal, sn/ideal if ideal else float('nan')))
        tau, _ = acf_tau(s)
        fps = len(x) / max(d["series"]["t"][-1], 1e-9)
        print("  ACF 1/e at lag %.0f frames (~%.1f s at %.1f fps)" % (tau, tau/fps, fps))
        print("  Allan dev @ tau=[1,10,100,1000] frames:",
              [None if v is None else round(v, 4) for v in allan(s, [1, 10, 100, 1000])])
