"""wasapi_probe.py -- can a plain WASAPI client get the Kinect's four microphone channels? (Windows 11)

Context: the device format of the "Microphone Array (Kinect USB Audio)" endpoint is
4 ch / 16 kHz / 32-bit PCM, channel mask 0 (registry), but the shared-mode mix format is 2 ch / 48 kHz float,
and the toolkit's AudioCaptureRaw records the mix format -> our earlier "2 channels". PortAudio could not
reach 4 channels (WASAPI: channel count taken from the mix format; WDM-KS: pin creation failed).

Interface method order is taken from Wine's public IDL (include/audioclient.idl, include/mmdeviceapi.idl):
  IMMDeviceEnumerator: 3 EnumAudioEndpoints, 4 GetDefaultAudioEndpoint, 5 GetDevice
  IMMDevice: 3 Activate
  IAudioClient: 3 Initialize, 4 GetBufferSize, 7 IsFormatSupported, 8 GetMixFormat, 9 GetDevicePeriod,
                10 Start, 11 Stop, 14 GetService;  IAudioClient2: 16 SetClientProperties
  IAudioCaptureClient: 3 GetBuffer, 4 ReleaseBuffer, 5 GetNextPacketSize

Stage 1 asks questions only (no audio). Stage 2, if a 4-channel path exists, captures 10 s INTO MEMORY,
computes the same statistics as audio_ks_probe.py (K1 four distinct channels, K2 zero low bits, K3 pairwise
GCC-PHAT lags vs the published geometry) and deletes the samples. No audio file is written.

SEALED BAR W1 (before the run): 4-CH REACHABLE if exclusive-mode IsFormatSupported(4 ch, 16 kHz, 32-bit PCM,
mask 0) returns S_OK, or the RAW-mode shared mix format has 4 channels. Otherwise NOT REACHABLE (report codes).
K1-K3 bars: as in audio_ks_probe.py.
"""
import os, sys, json, time
import ctypes as C
from ctypes import wintypes as W
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from atlas_common import below_normal_priority            # noqa: E402
from audio_ks_probe import gcc_phat, X_MM, C_MM_S         # noqa: E402

# The endpoint ID of "Microphone Array (Kinect USB Audio)" is specific to each PC, so it is not written here. Set it in the
# environment before running, e.g. KINECT_MIC_ENDPOINT_ID={0.0.1.00000000}.{xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx}
# (the GUID is the endpoint's key under HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Capture).
ENDPOINT_ID = os.environ.get("KINECT_MIC_ENDPOINT_ID", "")
FS = 16000
DUR = 10.0

ole32 = C.OleDLL("ole32")
ole32.CoTaskMemFree.restype = None
ole32.CoTaskMemFree.argtypes = [C.c_void_p]


class GUID(C.Structure):
    _fields_ = [("d1", C.c_uint32), ("d2", C.c_uint16), ("d3", C.c_uint16), ("d4", C.c_ubyte * 8)]

    @classmethod
    def s(cls, text):
        g = cls()
        C.oledll.ole32.CLSIDFromString(C.c_wchar_p(text), C.byref(g))
        return g


CLSID_MMDeviceEnumerator = GUID.s("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
IID_IMMDeviceEnumerator = GUID.s("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
IID_IAudioClient2 = GUID.s("{726778CD-F60A-4EDA-82DE-E47610CD78AA}")
IID_IAudioCaptureClient = GUID.s("{C8ADBD64-E71E-48A0-A4DE-185C395CD317}")
SUB_PCM = GUID.s("{00000001-0000-0010-8000-00AA00389B71}")
SUB_FLOAT = GUID.s("{00000003-0000-0010-8000-00AA00389B71}")
CLSCTX_ALL = 0x17
SHARED, EXCLUSIVE = 0, 1


class WFX(C.Structure):
    _pack_ = 1
    _fields_ = [("wFormatTag", C.c_uint16), ("nChannels", C.c_uint16), ("nSamplesPerSec", C.c_uint32),
                ("nAvgBytesPerSec", C.c_uint32), ("nBlockAlign", C.c_uint16), ("wBitsPerSample", C.c_uint16),
                ("cbSize", C.c_uint16)]


class WFXE(C.Structure):
    _pack_ = 1
    _fields_ = [("Format", WFX), ("wValidBitsPerSample", C.c_uint16), ("dwChannelMask", C.c_uint32),
                ("SubFormat", GUID)]


assert C.sizeof(WFX) == 18 and C.sizeof(WFXE) == 40


class AudioClientProperties(C.Structure):
    _fields_ = [("cbSize", C.c_uint32), ("bIsOffload", C.c_int), ("eCategory", C.c_int), ("Options", C.c_int)]


def vcall(p, idx, restype, *argtypes):
    vt = C.cast(p, C.POINTER(C.POINTER(C.c_void_p))).contents
    return C.WINFUNCTYPE(restype, C.c_void_p, *argtypes)(vt[idx])


def hx(hr):
    return "0x%08X" % (hr & 0xFFFFFFFF)


def release(p):
    if p:
        vcall(p, 2, C.c_ulong)(p)


def make_fmt(ch, bits, fl=False, mask=0):
    f = WFXE()
    f.Format.wFormatTag = 0xFFFE
    f.Format.nChannels = ch
    f.Format.nSamplesPerSec = FS
    f.Format.wBitsPerSample = bits
    f.Format.nBlockAlign = ch * bits // 8
    f.Format.nAvgBytesPerSec = FS * f.Format.nBlockAlign
    f.Format.cbSize = 22
    f.wValidBitsPerSample = bits
    f.dwChannelMask = mask
    f.SubFormat = SUB_FLOAT if fl else SUB_PCM
    return f


def describe(pw):
    w = C.cast(pw, C.POINTER(WFX)).contents
    d = dict(tag=hex(w.wFormatTag), ch=w.nChannels, sr=w.nSamplesPerSec, bits=w.wBitsPerSample)
    if w.wFormatTag == 0xFFFE:
        e = C.cast(pw, C.POINTER(WFXE)).contents
        d.update(mask=hex(e.dwChannelMask), valid=e.wValidBitsPerSample,
                 sub=("PCM" if e.SubFormat.d1 == 1 else "FLOAT" if e.SubFormat.d1 == 3 else hex(e.SubFormat.d1)))
    return d


def new_client(dev):
    pc = C.c_void_p()
    hr = vcall(dev, 3, C.c_long, C.POINTER(GUID), C.c_uint32, C.c_void_p, C.POINTER(C.c_void_p))(
        dev, C.byref(IID_IAudioClient2), CLSCTX_ALL, None, C.byref(pc))
    if hr < 0:
        raise OSError("IMMDevice::Activate " + hx(hr))
    return pc


def mix_format(cl):
    pw = C.c_void_p()
    hr = vcall(cl, 8, C.c_long, C.POINTER(C.c_void_p))(cl, C.byref(pw))
    if hr < 0:
        return hx(hr), None
    d = describe(pw)
    return d, pw                                   # caller frees


def set_raw(cl):
    p = AudioClientProperties(16, 0, 0, 1)         # category Other, AUDCLNT_STREAMOPTIONS_RAW
    return vcall(cl, 16, C.c_long, C.POINTER(AudioClientProperties))(cl, C.byref(p))


def is_supported(cl, mode, fmt):
    closest = C.c_void_p()
    hr = vcall(cl, 7, C.c_long, C.c_int, C.c_void_p, C.POINTER(C.c_void_p))(
        cl, mode, C.byref(fmt), C.byref(closest) if mode == SHARED else None)
    cm = None
    if closest.value:
        cm = describe(closest)
        ole32.CoTaskMemFree(closest)
    return hx(hr), cm


def capture(dev, mode, fmt_ptr, raw):
    cl = new_client(dev)
    try:
        if raw:
            set_raw(cl)
        dur = C.c_int64(2_000_000)                  # 200 ms buffer (100-ns units)
        hr = vcall(cl, 3, C.c_long, C.c_int, C.c_uint32, C.c_int64, C.c_int64, C.c_void_p, C.c_void_p)(
            cl, mode, 0, dur, (dur.value if mode == EXCLUSIVE else 0), fmt_ptr, None)
        if hr < 0:
            return None, "Initialize " + hx(hr)
        cap = C.c_void_p()
        hr = vcall(cl, 14, C.c_long, C.POINTER(GUID), C.POINTER(C.c_void_p))(cl, C.byref(IID_IAudioCaptureClient), C.byref(cap))
        if hr < 0:
            return None, "GetService " + hx(hr)
        w = C.cast(fmt_ptr, C.POINTER(WFX)).contents
        ch, bits, sr = w.nChannels, w.wBitsPerSample, w.nSamplesPerSec
        fl = (w.wFormatTag == 3) or (w.wFormatTag == 0xFFFE and C.cast(fmt_ptr, C.POINTER(WFXE)).contents.SubFormat.d1 == 3)
        dt = np.float32 if fl else {32: np.int32, 16: np.int16}[bits]
        n = int(DUR * sr)
        buf = np.zeros((n, ch), dtype=dt)
        pos = 0
        flags_seen = 0
        GetBuffer = vcall(cap, 3, C.c_long, C.POINTER(C.c_void_p), C.POINTER(C.c_uint32), C.POINTER(C.c_uint32), C.c_void_p, C.c_void_p)
        Release = vcall(cap, 4, C.c_long, C.c_uint32)
        NextSize = vcall(cap, 5, C.c_long, C.POINTER(C.c_uint32))
        vcall(cl, 10, C.c_long)(cl)
        t0 = time.perf_counter()
        while pos < n and time.perf_counter() - t0 < DUR + 5:
            sz = C.c_uint32(0)
            NextSize(cap, C.byref(sz))
            if sz.value == 0:
                time.sleep(0.005)
                continue
            pd, nf, fg = C.c_void_p(), C.c_uint32(0), C.c_uint32(0)
            hr = GetBuffer(cap, C.byref(pd), C.byref(nf), C.byref(fg), None, None)
            if hr < 0:
                break
            k = min(nf.value, n - pos)
            if k:
                raw_b = C.string_at(pd, nf.value * ch * np.dtype(dt).itemsize)
                buf[pos:pos + k] = np.frombuffer(raw_b, dtype=dt).reshape(nf.value, ch)[:k]
            flags_seen |= fg.value
            pos += k
            Release(cap, nf.value)
        vcall(cl, 11, C.c_long)(cl)
        release(cap)
        return (buf[:pos], sr, ch, dt, flags_seen), None
    finally:
        release(cl)


def stats(buf, sr, ch, dt):
    out = {"frames": int(len(buf)), "fs": sr, "channels": ch, "dtype": np.dtype(dt).name}
    if np.dtype(dt).kind == 'i':
        u = buf.ravel().view(np.uint32 if buf.dtype == np.int32 else np.uint16)
        orv = int(np.bitwise_or.reduce(u))
        out["K2_zero_low_bits"] = ((orv & -orv).bit_length() - 1) if orv else None
        full = 2.0 ** (31 if buf.dtype == np.int32 else 15)
    else:
        full = 1.0
        # float data: test whether the values sit on a 2^-23 (24-bit) or 2^-31 grid
        q = buf.astype(np.float64) * 2 ** 23
        out["float_on_24bit_grid"] = bool(np.all(np.abs(q - np.round(q)) < 1e-6))
    x = buf.astype(np.float64)
    out["distinct_values_per_ch"] = [int(len(np.unique(buf[:, i]))) for i in range(ch)]
    xc = x - x.mean(0)
    rms = np.sqrt(np.mean(xc ** 2, 0))
    out["rms_dbfs"] = np.round(20 * np.log10(np.maximum(rms, 1e-12) / full), 1).tolist()
    out["dc_fraction_fs"] = (x.mean(0) / full).tolist()
    Cm = np.corrcoef(xc.T)
    out["corr"] = np.round(Cm, 4).tolist()
    off = Cm[np.triu_indices(ch, 1)]
    out["K1_pass"] = bool(ch == 4 and np.all(rms > 0) and np.all(off < 0.99))
    if ch == 4 and sr == FS:
        res = []
        for i in range(4):
            for j in range(i + 1, 4):
                lag, sh = gcc_phat(xc[:, i], xc[:, j])
                res.append({"pair": [i + 1, j + 1], "lag": round(lag, 3), "sharp": round(sh, 2),
                            "limit": round(abs(X_MM[i] - X_MM[j]) * FS / C_MM_S, 3)})
        A = np.array([(X_MM[r["pair"][0] - 1] - X_MM[r["pair"][1] - 1]) * FS / C_MM_S for r in res])
        L = np.array([r["lag"] for r in res])
        s = float(np.dot(A, L) / np.dot(A, A))
        resid = float(np.sqrt(np.mean((L - A * s) ** 2)))
        sharp_med = float(np.median([r["sharp"] for r in res]))
        within = all(abs(r["lag"]) <= r["limit"] + 0.5 for r in res)
        verdict = ("NO RESULT (median sharpness %.1f < 4)" % sharp_med if sharp_med < 4 else
                   "GEOMETRY-CONSISTENT" if (within and resid < 0.5) else "INCONSISTENT")
        out.update(K3_pairs=res, K3_sharp_median=sharp_med, K3_within_limits=bool(within),
                   K3_sin_theta=s, K3_fit_rms=resid, K3_verdict=verdict)
        # spectrum by band (dBFS, summed power)
        F = np.fft.rfftfreq(len(xc), 1 / sr)
        P = np.abs(np.fft.rfft(xc * np.hanning(len(xc))[:, None], axis=0)) ** 2
        out["band_db"] = {"%d-%d" % b: np.round(10 * np.log10(P[(F >= b[0]) & (F < b[1])].sum(0) / full ** 2 + 1e-30), 1).tolist()
                          for b in [(20, 125), (125, 500), (500, 2000), (2000, 6000), (6000, 7600), (7600, 8000)]}
    return out


def main():
    below_normal_priority()
    try:
        ole32.CoInitializeEx(None, 0)
    except OSError:
        pass                                        # COM already initialised on this thread (PortAudio import)
    if not ENDPOINT_ID:
        raise SystemExit("set KINECT_MIC_ENDPOINT_ID to this PC's Kinect microphone-array endpoint ID (see the comment at the top)")
    out = {}
    en, dev = C.c_void_p(), C.c_void_p()
    hr = ole32.CoCreateInstance(C.byref(CLSID_MMDeviceEnumerator), None, CLSCTX_ALL, C.byref(IID_IMMDeviceEnumerator), C.byref(en))
    hr = vcall(en, 5, C.c_long, C.c_wchar_p, C.POINTER(C.c_void_p))(en, ENDPOINT_ID, C.byref(dev))
    if hr < 0:
        raise OSError("GetDevice " + hx(hr))
    # ---- stage 1: questions only ----
    cl = new_client(dev)
    d, pw = mix_format(cl); out["mix_default"] = d
    if pw: ole32.CoTaskMemFree(pw)
    out["set_raw_hr"] = hx(set_raw(cl))
    d, pw = mix_format(cl); out["mix_after_raw"] = d
    if pw: ole32.CoTaskMemFree(pw)
    tests = {}
    for mode, mname in ((EXCLUSIVE, "excl"), (SHARED, "shared_raw")):
        for ch, bits, fl in ((4, 32, False), (4, 32, True), (4, 16, False), (4, 24, False), (2, 32, False), (1, 32, False)):
            f = make_fmt(ch, bits, fl)
            tests["%s_%dch_%d%s" % (mname, ch, bits, "f" if fl else "i")] = is_supported(cl, mode, f)
    out["is_supported"] = tests
    release(cl)
    # ---- the 4-channel verdict ----
    excl_ok = tests["excl_4ch_32i"][0] == "0x00000000"
    raw4 = isinstance(out["mix_after_raw"], dict) and out["mix_after_raw"].get("ch") == 4
    out["W1"] = "4-CH REACHABLE" if (excl_ok or raw4) else "NOT REACHABLE"
    print(json.dumps(out, indent=1))
    # ---- stage 2: in-memory capture over the best path ----
    path = None
    if excl_ok:
        f = make_fmt(4, 32, False)
        path = ("exclusive 4ch/16k/32-bit PCM", EXCLUSIVE, C.cast(C.pointer(f), C.c_void_p), False, f)
    elif raw4:
        cl = new_client(dev); set_raw(cl); d, pw = mix_format(cl)
        path = ("shared RAW mix format", SHARED, pw, True, None)
        release(cl)
    if path:
        name, mode, fp, raw, keep = path
        r, err = capture(dev, mode, fp, raw)
        if err:
            out["capture_error"] = err; print("capture failed:", err)
        else:
            buf, sr, ch, dt, fl = r
            st = stats(buf, sr, ch, dt)
            del buf, r                              # nothing of the audio survives past this point
            st["path"] = name; st["buffer_flags_seen"] = fl
            out["capture_stats"] = st
            print(json.dumps({k: v for k, v in st.items() if k != "K3_pairs"}, indent=1))
            for p in st.get("K3_pairs", []):
                print("pair %s lag %+.2f (limit %.2f) sharp %.1f" % (p["pair"], p["lag"], p["limit"], p["sharp"]))
            print("K3:", st.get("K3_verdict"))
    release(dev); release(en)
    with open(os.path.join(HERE, "wasapi_probe.json"), "w") as f:
        json.dump(out, f, indent=1)
    print("wrote wasapi_probe.json (statistics only; no audio stored)")


if __name__ == "__main__":
    main()
