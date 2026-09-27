"""audio_ks_probe.py -- are the four Kinect microphones reachable without the DMO? (Kinect v1, Windows 11)

Public (opened 2026-09-27):
  - SDK docs jj131026 "Audio Stream": raw audio via WASAPI (AudioCaptureRaw-Console) or processed audio via
    the KinectAudio DMO. Sample page hh855374: AudioCaptureRaw writes "a standard 4-channel .wav".
  - Toolkit sample source (AudioBasics-D2D / AudioExplorer-D2D): the DMO output is set to 1 channel,
    16 kHz, 16-bit PCM. Spec page jj131033: "16-kHz, 24-bit mono PCM"; "24-bit ADC".
  - AudioCaptureRaw's own source (WASAPICapture.cpp): it records the SHARED-MODE MIX FORMAT, not the device
    format.
  - Mic positions (Xbox 360 model 1473, libfreenect channel order, measured by eye through the bottom
    covers): x = +113, -36, -76, -113 mm (a hobbyist note; not an official source).
  Our earlier "2 channels, 48 kHz, 32-bit int" came from AudioCaptureRaw. Registry on this host: device
  format 4 ch / 16 kHz / 32-bit PCM, channel mask 0; the mix format is 2 ch / 48 kHz float.

Probe: 10 s of 4-channel capture through WDM-KS (kernel streaming, bypasses the Windows audio engine),
HELD IN MEMORY ONLY. Only summary statistics are printed and saved (audio_ks_probe.json). No audio file is
written; the sample array is deleted before the JSON is written. BELOW_NORMAL priority.

SEALED BARS (fixed before the run):
  K1 FOUR     PASS if a 4-ch 16 kHz stream opens and every channel has non-zero RMS and every pairwise
              broadband correlation is < 0.99 (four distinct signals, not copies).
  K2 BITS     report the number of always-zero low bits in the int32 samples (24-bit data -> 8 zero bits).
  K3 GEOMETRY for each of the 6 pairs, GCC-PHAT peak lag over the whole 10 s (ambient sound; no claps).
              GEOMETRY-CONSISTENT if every |lag| <= |x_i - x_j| * fs / c + 0.5 sample using the model-1473
              positions above, AND a single far-field angle fits all 6 lags with RMS residual < 0.5 sample.
              NO RESULT if the median PHAT sharpness (peak / RMS of the correlation) < 4 (no dominant source).
"""
import os, sys, json, math
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
from atlas_common import below_normal_priority   # noqa: E402
import sounddevice as sd                          # noqa: E402

FS = 16000
DUR = 10.0
X_MM = np.array([113.0, -36.0, -76.0, -113.0])   # model 1473, libfreenect order (hobbyist measurement)
C_MM_S = 343000.0


def find_ks():
    for i, d in enumerate(sd.query_devices()):
        if 'kinect' in d['name'].lower() and sd.query_hostapis(d['hostapi'])['name'] == 'Windows WDM-KS' \
                and d['max_input_channels'] >= 4:
            return i, d
    raise RuntimeError("no WDM-KS Kinect capture pin found")


def gcc_phat(a, b, maxlag=24, nfft=1 << 15, seg=1 << 14):
    # average the PHAT-weighted cross-spectrum over segments, then transform once
    acc = None
    for s0 in range(0, len(a) - seg + 1, seg // 2):
        A = np.fft.rfft(a[s0:s0 + seg] * np.hanning(seg), nfft)
        B = np.fft.rfft(b[s0:s0 + seg] * np.hanning(seg), nfft)
        R = A * np.conj(B)
        R /= np.maximum(np.abs(R), 1e-20)
        acc = R if acc is None else acc + R
    cc = np.fft.irfft(acc, nfft)
    cc = np.concatenate([cc[-maxlag:], cc[:maxlag + 1]])
    lags = np.arange(-maxlag, maxlag + 1)
    j = int(np.argmax(cc))
    # parabolic sub-sample peak
    if 0 < j < len(cc) - 1:
        y0, y1, y2 = cc[j - 1], cc[j], cc[j + 1]
        d = 0.5 * (y0 - y2) / (y0 - 2 * y1 + y2) if (y0 - 2 * y1 + y2) != 0 else 0.0
    else:
        d = 0.0
    return float(lags[j] + d), float(cc[j] / np.sqrt(np.mean(cc ** 2)))


def main():
    below_normal_priority()
    idx, d = find_ks()
    print("device %d: %s (WDM-KS), default sr %.0f, max in %d" % (idx, d['name'], d['default_samplerate'],
                                                                  d['max_input_channels']))
    # WDM-KS in PortAudio supports callback streams only ("Blocking API not supported yet")
    n = int(DUR * FS)
    rec = np.zeros((n, 4), dtype=np.int32)
    pos = [0]
    import threading
    done = threading.Event()

    def cb(indata, frames, t, status):
        k = min(frames, n - pos[0])
        rec[pos[0]:pos[0] + k] = indata[:k]
        pos[0] += k
        if pos[0] >= n:
            done.set()
            raise sd.CallbackStop

    with sd.InputStream(device=idx, channels=4, samplerate=FS, dtype='int32', callback=cb):
        done.wait(DUR + 5)
    if pos[0] < n:
        raise RuntimeError("only %d of %d frames arrived" % (pos[0], n))
    out = {"device": d['name'], "hostapi": "WDM-KS", "fs": FS, "seconds": DUR, "n": int(len(rec))}
    x = rec.astype(np.float64)
    # K2 bits
    orv = int(np.bitwise_or.reduce(rec.ravel().view(np.uint32)))
    tz = (orv & -orv).bit_length() - 1 if orv else 32
    out["K2_zero_low_bits"] = tz
    out["distinct_values_per_ch"] = [int(len(np.unique(rec[:, i]))) for i in range(4)]
    full = 2.0 ** 31
    rms = np.sqrt(np.mean((x - x.mean(0)) ** 2, axis=0))
    out["dc_fraction_fs"] = (x.mean(0) / full).tolist()
    out["rms_dbfs"] = (20 * np.log10(np.maximum(rms, 1e-9) / full)).tolist()
    out["peak_dbfs"] = (20 * np.log10(np.maximum(np.abs(x).max(0), 1) / full)).tolist()
    xc = x - x.mean(0)
    Cm = np.corrcoef(xc.T)
    out["corr"] = np.round(Cm, 4).tolist()
    off = Cm[np.triu_indices(4, 1)]
    k1 = bool(np.all(rms > 0) and np.all(off < 0.99))
    out["K1_pass"] = k1
    # spectrum summary (per channel, octave bands), in dB relative to full scale
    bands = [(20, 125), (125, 250), (250, 500), (500, 1000), (1000, 2000), (2000, 4000), (4000, 6000),
             (6000, 7500), (7500, 8000)]
    F = np.fft.rfftfreq(len(xc), 1 / FS)
    P = np.abs(np.fft.rfft(xc * np.hanning(len(xc))[:, None], axis=0)) ** 2
    out["band_db"] = {"%d-%d" % b: (10 * np.log10(P[(F >= b[0]) & (F < b[1])].sum(0) / full ** 2 + 1e-30)).round(1).tolist()
                      for b in bands}
    # K3 geometry
    pairs = [(i, j) for i in range(4) for j in range(i + 1, 4)]
    res = []
    for i, j in pairs:
        lag, sh = gcc_phat(xc[:, i], xc[:, j])
        lim = abs(X_MM[i] - X_MM[j]) * FS / C_MM_S
        res.append({"pair": [i + 1, j + 1], "lag": lag, "sharp": sh, "limit": lim})
    del rec, x, xc, P                           # nothing of the audio survives past this point
    sharp_med = float(np.median([r["sharp"] for r in res]))
    within = all(abs(r["lag"]) <= r["limit"] + 0.5 for r in res)
    # far-field fit: lag_ij = (x_i - x_j) * s * fs / c, s = sin(theta); least squares for s
    A = np.array([(X_MM[r["pair"][0] - 1] - X_MM[r["pair"][1] - 1]) * FS / C_MM_S for r in res])
    L = np.array([r["lag"] for r in res])
    s = float(np.dot(A, L) / np.dot(A, A))
    resid = float(np.sqrt(np.mean((L - A * s) ** 2)))
    if sharp_med < 4:
        k3 = "NO RESULT (median sharpness %.1f < 4)" % sharp_med
    elif within and resid < 0.5:
        k3 = "GEOMETRY-CONSISTENT"
    else:
        k3 = "INCONSISTENT"
    out.update(K3_pairs=res, K3_sharp_median=sharp_med, K3_within_limits=bool(within),
               K3_sin_theta=s, K3_fit_rms=resid, K3_verdict=k3)
    print(json.dumps({k: v for k, v in out.items() if k not in ("K3_pairs", "band_db")}, indent=1))
    for r in res:
        print("pair %s: lag %+.2f samples (limit %.2f), sharpness %.1f" % (r["pair"], r["lag"], r["limit"], r["sharp"]))
    for b, v in out["band_db"].items():
        print("band %s Hz dBFS: %s" % (b, v))
    print("K1 FOUR: %s | K2 zero low bits: %d | K3: %s (sin theta %.2f, fit rms %.2f)"
          % ("PASS" if k1 else "FAIL", tz, k3, s, resid))
    with open(os.path.join(HERE, "audio_ks_probe.json"), "w") as f:
        json.dump(out, f, indent=1)
    print("wrote audio_ks_probe.json (statistics only; no audio stored)")


if __name__ == "__main__":
    main()
