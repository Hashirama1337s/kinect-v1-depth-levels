"""colour_offline2.py -- follow-ups written AFTER the first look at colour_offline.py (labelled as such).

Why: colour_offline.py O4 (block grid) peaked at 44-63 px in every capture -- the scale of its own 65-px detrend window,
so O4 is VOID as run (method artefact). O3 showed temporal variances of 65-880 DN^2 at means of 12-128 DN, far above what a
raw 8-bit sensor path should give, so the next question is whether the temporal noise is pixel-independent (raw) or
spatially correlated (processed: demosaic/re-mosaic, compression, denoise). Uses existing ../dark_room_*.npz only.

Bars fixed before running this file:
  N1 NOISE INDEPENDENCE  d = frame0 - frame30 (Braw[0]-Braw[1], 3 s apart), minus its 15x15 same-phase local mean, flat
     pixels only (Bmean gradient below median). Correlation of d with (a) the same-colour neighbour 2 px right and 2 px down,
     (b) the adjacent other-colour pixel 1 px right and 1 px down. RAW-LIKE if every |corr| < 0.10; PROCESSED if any
     same-colour or adjacent corr > 0.30; otherwise UNCLEAR.
  O4b BLOCK GRID (redo)  per phase plane, column and row profiles of Bstd, high-passed by subtracting a 9-tap moving mean,
     periods 3..40 phase-plane px (= 6..80 full-res px). BLOCK GRID if the same period (+-5 %) is the top peak with
     peak/median > 10 in >= 3 of 4 phase planes in >= 5 of the 7 usable captures. Otherwise NONE FOUND.
usage: python colour_offline2.py
"""
import os, json, glob
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
PH = [(0, 0), (0, 1), (1, 0), (1, 1)]


def box(a, k):
    from numpy.lib.stride_tricks import sliding_window_view
    p = k // 2
    ap = np.pad(a, p, mode='reflect')
    return sliding_window_view(ap, (k, k)).mean(axis=(-2, -1))


def corr(u, v):
    u = u - u.mean(); v = v - v.mean()
    return float((u * v).mean() / np.sqrt((u * u).mean() * (v * v).mean()))


def n1(Braw, Bm):
    d = Braw[0].astype(np.float64) - Braw[1].astype(np.float64)
    # subtract same-phase local mean (removes a global/smooth exposure change between the two frames)
    hp = np.empty_like(d)
    for p in PH:
        pl = d[p[0]::2, p[1]::2]
        hp[p[0]::2, p[1]::2] = pl - box(pl, 15)
    gy, gx = np.gradient(Bm.astype(np.float64)); g = np.hypot(gx, gy)
    flat = g < np.median(g)
    out = {}
    for name, (dy, dx) in {'same_colour_right_2px': (0, 2), 'same_colour_down_2px': (2, 0),
                           'adjacent_right_1px': (0, 1), 'adjacent_down_1px': (1, 0), 'diagonal_1px': (1, 1)}.items():
        a = hp[:hp.shape[0] - dy, :hp.shape[1] - dx]; b = hp[dy:, dx:]
        m = flat[:flat.shape[0] - dy, :flat.shape[1] - dx] & flat[dy:, dx:]
        out[name] = corr(a[m], b[m])
    out['d_sd_DN'] = float(hp[flat].std())
    vals = [abs(v) for k, v in out.items() if k != 'd_sd_DN']
    out['verdict'] = 'RAW-LIKE' if max(vals) < 0.10 else 'PROCESSED' if max(vals) > 0.30 else 'UNCLEAR'
    return out


def peaks(profile, pmin=3, pmax=40):
    x = profile - np.convolve(profile, np.ones(9) / 9, mode='same')
    x = x[10:-10]
    P = np.abs(np.fft.rfft(x - x.mean())) ** 2
    f = np.fft.rfftfreq(x.size)
    with np.errstate(divide='ignore'):
        per = 1 / f
    idx = np.where((per >= pmin) & (per <= pmax))[0]
    k = idx[np.argmax(P[idx])]
    return float(per[k]), float(P[k] / np.median(P[idx]))


def o4b(Bs):
    out = {}
    for p in PH:
        pl = Bs[p[0]::2, p[1]::2].astype(np.float64)
        out[str(p)] = dict(col=peaks(pl.mean(0)), row=peaks(pl.mean(1)))
    return out


def main():
    res = {}
    for fn in sorted(glob.glob(os.path.join(ROOT, 'dark_room_*.npz'))):
        tag = os.path.basename(fn)[len('dark_room_'):-4]
        z = np.load(fn)
        if z['Bmean'].mean() <= 10:
            continue
        r = dict(N1=n1(z['Braw'], z['Bmean']), O4b=o4b(z['Bstd']))
        res[tag] = r
        print(tag, 'N1', {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r['N1'].items()})
        print('    O4b', {k: ((round(v['col'][0], 1), round(v['col'][1], 1)), (round(v['row'][0], 1), round(v['row'][1], 1)))
                          for k, v in r['O4b'].items()})
    n1v = sorted({r['N1']['verdict'] for r in res.values()})
    # O4b verdict
    hits = {}
    for tag, r in res.items():
        for axis in ('col', 'row'):
            per = [v[axis][0] for v in r['O4b'].values() if v[axis][1] > 10]
            for pp in per:
                same = sum(abs(q - pp) / pp < 0.05 for q in per)
                if same >= 3:
                    hits.setdefault((axis, round(pp)), set()).add(tag)
    grid = {f"{a}:{p}": sorted(t) for (a, p), t in hits.items() if len(t) >= 5}
    summary = dict(N1=n1v, O4b=('BLOCK GRID ' + json.dumps(grid)) if grid else 'NONE FOUND')
    print('SUMMARY', summary)
    json.dump(dict(results=res, summary=summary), open(os.path.join(HERE, 'colour_offline2_result.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
