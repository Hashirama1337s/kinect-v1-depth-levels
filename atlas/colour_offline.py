"""colour_offline.py -- colour-camera atlas, analyses of EXISTING captures only (no Kinect access).

Inputs: ../dark_room_*.npz (written by ../dark_room.py): Bmean/Bstd = per-pixel temporal mean/SD of 60 frames of
COLOR_RAW_BAYER 1280x960 (uint8 source), Braw = 3 of those frames, Tb = SDK frame timestamps (ms), Bfm = frame means.
Output: numbers only, printed and written to colour_offline_result.json. No image is written anywhere.

Bars fixed before the first run (2026-09-27):
  O1 PHASES   the two 2x2 phases with the smallest mean |difference| between their co-sited planes are the green pair.
              GREEN-DIAGONAL if that pair is (0,0)+(1,1) or (0,1)+(1,0) in every usable capture; else INCONSISTENT.
  O2 CODES    per phase, inside the central 98 % of values: fraction of integer codes that never occur (3 frames x
              307 200 samples). MISSING-CODES if > 5 % of codes in that range are empty in every usable capture
              (=> a digital gain > 1 or a LUT acts after quantisation); DENSE if < 1 %; otherwise UNCLEAR.
  O3 PTC      per phase, log(temporal variance) vs log(mean) over bins with mean in [12, 128] DN (flat pixels only:
              local spatial gradient below the median). LINEAR-LIKE if slope >= 0.6; TONE-CURVE if slope <= 0.3 and the
              variance is > 0.5 DN^2 (so read noise/quantisation cannot flatten it); otherwise NO VERDICT.
  O4 BLOCKS   spectrum of the column- and row-profiles of the temporal SD map (full-res, detrended). BLOCK GRID at
              period P (4..64 px) if the peak power at P is > 8x the median power of all other periods in 4..64.
  O5 CHROMA   high-frequency energy ratio horizontal/vertical for each colour plane (|d/dx| vs |d/dy| of Bmean).
              4:2:2-LIKE if the two non-green planes' H/V ratio is < 0.75x the green planes' ratio in every usable capture.
  O6 TIMING   frame interval statistics from Tb: fps, and any interval > 1.5x the median (= dropped/late frames).
  O7 FLICKER  row profile of (Braw frame / Bmean), FFT: report the strongest period (rows) and its peak/median ratio.
              Exploratory only (no verdict): a rolling shutter under mains-modulated light makes horizontal bands.
usage: python colour_offline.py
"""
import os, json, glob
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
PH = [(0, 0), (0, 1), (1, 0), (1, 1)]


def phase(a, p):
    return a[p[0]::2, p[1]::2]


def o1_phases(Bm):
    planes = {p: phase(Bm, p).astype(np.float64) for p in PH}
    means = {str(p): float(planes[p].mean()) for p in PH}
    pairs = {}
    for i in range(4):
        for j in range(i + 1, 4):
            a, b = planes[PH[i]], planes[PH[j]]
            a = a / a.mean(); b = b / b.mean()                     # remove channel gain: compare texture only
            pairs[f"{PH[i]}+{PH[j]}"] = float(np.mean(np.abs(a - b)))
    best = min(pairs, key=pairs.get)
    return dict(phase_means=means, pair_mad=pairs, green_pair=best)


def o2_codes(Braw):
    out = {}
    for p in PH:
        v = np.concatenate([phase(f, p).ravel() for f in Braw]).astype(np.int64)
        lo, hi = np.percentile(v, [1, 99]).astype(int)
        h = np.bincount(v, minlength=256)
        rng = h[lo:hi + 1]
        out[str(p)] = dict(lo=int(lo), hi=int(hi), n_codes=int(rng.size), empty=int((rng == 0).sum()),
                           empty_frac=float((rng == 0).mean()) if rng.size else None)
    return out


def o3_ptc(Bm, Bs):
    gy, gx = np.gradient(Bm.astype(np.float64))
    g = np.hypot(gx, gy)
    out = {}
    for p in PH:
        m = phase(Bm, p).ravel(); s = phase(Bs, p).ravel(); gg = phase(g, p).ravel()
        flat = gg < np.median(gg)
        m, v = m[flat], (s[flat].astype(np.float64)) ** 2
        edges = np.arange(12, 130, 4)
        xs, ys, ns = [], [], []
        for a, b in zip(edges[:-1], edges[1:]):
            sel = (m >= a) & (m < b)
            if sel.sum() >= 300:
                xs.append(float(np.median(m[sel]))); ys.append(float(np.median(v[sel]))); ns.append(int(sel.sum()))
        if len(xs) >= 4:
            slope = float(np.polyfit(np.log(xs), np.log(ys), 1)[0])
        else:
            slope = None
        verdict = ("NO DATA" if slope is None else "LINEAR-LIKE" if slope >= 0.6 else
                   "TONE-CURVE" if (slope <= 0.3 and min(ys) > 0.5) else "NO VERDICT")
        out[str(p)] = dict(bins=len(xs), mean_range=[xs[0], xs[-1]] if xs else None,
                           var_range=[min(ys), max(ys)] if ys else None, slope=slope, verdict=verdict,
                           curve=[[round(a, 1), round(b, 3)] for a, b in zip(xs, ys)])
    return out


def _period_peak(profile, pmin=4, pmax=64):
    x = profile - np.convolve(profile, np.ones(65) / 65, mode='same')          # detrend
    x = x[40:-40]
    P = np.abs(np.fft.rfft(x - x.mean())) ** 2
    f = np.fft.rfftfreq(x.size)
    per = np.where(f > 0, 1 / np.maximum(f, 1e-12), np.inf)
    sel = (per >= pmin) & (per <= pmax)
    idx = np.where(sel)[0]
    k = idx[np.argmax(P[idx])]
    others = np.delete(P[idx], np.argmax(P[idx]))
    return float(per[k]), float(P[k] / np.median(others))


def o4_blocks(Bs):
    col = Bs.astype(np.float64).mean(0); row = Bs.astype(np.float64).mean(1)
    pc, rc = _period_peak(col); pr, rr = _period_peak(row)
    return dict(col_period=pc, col_peak_ratio=rc, col_block=bool(rc > 8),
                row_period=pr, row_peak_ratio=rr, row_block=bool(rr > 8))


def o5_chroma(Bm, green_pair):
    out = {}
    for p in PH:
        a = phase(Bm, p).astype(np.float64)
        h = np.mean(np.abs(np.diff(a, axis=1))) / a.mean(); v = np.mean(np.abs(np.diff(a, axis=0))) / a.mean()
        out[str(p)] = dict(hf_h=float(h), hf_v=float(v), h_over_v=float(h / v))
    g = [str(q) for q in PH if str(q) in green_pair]
    ng = [str(q) for q in PH if str(q) not in green_pair]
    gr = np.mean([out[k]['h_over_v'] for k in g]); nr = np.mean([out[k]['h_over_v'] for k in ng])
    out['green_hv'] = float(gr); out['nongreen_hv'] = float(nr); out['ratio'] = float(nr / gr)
    return out


def o6_timing(Tb):
    dt = np.diff(Tb)
    med = float(np.median(dt))
    return dict(n=int(Tb.size), fps=float((Tb.size - 1) / ((Tb[-1] - Tb[0]) / 1000.0)), dt_median_ms=med,
                dt_min=float(dt.min()), dt_max=float(dt.max()), late=int((dt > 1.5 * med).sum()),
                dt_values_ms=sorted(set(np.round(dt, 1).tolist()))[:12])


def o7_flicker(Braw, Bm):
    res = []
    for f in Braw:
        r = f.astype(np.float64).mean(1) / np.maximum(Bm.astype(np.float64).mean(1), 1e-6)
        per, ratio = _period_peak(r, 8, 480)
        res.append(dict(period_rows=per, peak_ratio=ratio, rel_rms=float(np.std(r) / np.mean(r))))
    return res


def main():
    results = {}
    for fn in sorted(glob.glob(os.path.join(ROOT, 'dark_room_*.npz'))):
        tag = os.path.basename(fn)[len('dark_room_'):-4]
        z = np.load(fn)
        Bm, Bs, Braw, Tb, fm = z['Bmean'], z['Bstd'], z['Braw'], z['Tb'], z['Bfm']
        usable = bool(Bm.mean() > 10)
        r = dict(mean_DN=float(Bm.mean()), frame_mean_range=[float(fm.min()), float(fm.max())], usable=usable)
        r['O1'] = o1_phases(Bm)
        r['O2'] = o2_codes(Braw)
        r['O3'] = o3_ptc(Bm, Bs)
        r['O4'] = o4_blocks(Bs)
        r['O5'] = o5_chroma(Bm, r['O1']['green_pair'])
        r['O6'] = o6_timing(Tb)
        r['O7'] = o7_flicker(Braw, Bm)
        results[tag] = r
        print(f"\n=== {tag}  mean {r['mean_DN']:.1f} DN  usable={usable}")
        print("  O1 phase means", {k: round(v, 2) for k, v in r['O1']['phase_means'].items()}, " green pair:", r['O1']['green_pair'])
        print("  O2 empty-code fraction", {k: round(v['empty_frac'], 3) for k, v in r['O2'].items()},
              " ranges", {k: (v['lo'], v['hi']) for k, v in r['O2'].items()})
        print("  O3 PTC slope", {k: (None if v['slope'] is None else round(v['slope'], 2), v['verdict']) for k, v in r['O3'].items()})
        print("  O4 blocks", {k: (round(v, 2) if isinstance(v, float) else v) for k, v in r['O4'].items()})
        print("  O5 chroma H/V: green %.3f non-green %.3f ratio %.3f" % (r['O5']['green_hv'], r['O5']['nongreen_hv'], r['O5']['ratio']))
        print("  O6 timing", {k: v for k, v in r['O6'].items()})
        print("  O7 flicker", [(round(x['period_rows'], 1), round(x['peak_ratio'], 1), round(x['rel_rms'], 4)) for x in r['O7']])
    # verdicts across usable captures
    U = {k: v for k, v in results.items() if v['usable']}
    gp = {v['O1']['green_pair'] for v in U.values()}
    o1 = ("GREEN-DIAGONAL" if len(gp) == 1 and list(gp)[0] in ("(0, 0)+(1, 1)", "(0, 1)+(1, 0)") else "INCONSISTENT") + f" {sorted(gp)}"
    ef = [p['empty_frac'] for v in U.values() for p in v['O2'].values()]
    o2 = "MISSING-CODES" if min(ef) > 0.05 else "DENSE" if max(ef) < 0.01 else "UNCLEAR"
    o5 = "4:2:2-LIKE" if all(v['O5']['ratio'] < 0.75 for v in U.values()) else "NOT 4:2:2-LIKE"
    summary = dict(O1=o1, O2=o2 + f" (empty fraction {min(ef):.3f}..{max(ef):.3f})", O5=o5,
                   O3={k: sorted({p['verdict'] for p in v['O3'].values()}) for k, v in U.items()},
                   O4={k: (v['O4']['col_block'], v['O4']['row_block']) for k, v in U.items()})
    print("\nSUMMARY", json.dumps(summary, indent=1))
    json.dump(dict(results=results, summary=summary), open(os.path.join(HERE, 'colour_offline_result.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
