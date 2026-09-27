"""dmo_probe.py -- what does the KinectAudio DMO (NuiGetAudioSource) actually offer? (Kinect v1, SDK 1.8)

Public (opened 2026-09-27):
  - NuiSensor.h: INuiSensor vtable 21 = NuiGetAudioSource(INuiAudioBeam **ppDmo); INuiAudioBeam vtable
    3 GetBeam(double*), 4 SetBeam(double), 5 GetPosition(double* angle, double* confidence); MICARRAY_ADAPTIVE_BEAM 0x1100.
  - Docs jj663734 / jj663765 / hh855661: 11 fixed beams, "-0.875 to +0.875 radians in .0175 radian increments,
    which corresponds to approximately -50 to +50 degrees, in ten degree increments"; confidence in [0, 1];
    ProcessOutput must run before GetBeam / GetPosition.
  - Toolkit samples (AudioBasics-D2D): QI the INuiAudioBeam for IMediaObject and IPropertyStore; system mode
    SINGLE_CHANNEL_AEC 0 / OPTIBEAM_ARRAY_ONLY 2 / OPTIBEAM_ARRAY_AND_AEC 4 / SINGLE_CHANNEL_NSAGC 5; output set
    to 1 ch / 16 kHz / 16-bit PCM.
  Other method orders from Wine's public IDL: IMediaObject 3 GetStreamCount, 7 GetOutputType, 9 SetOutputType,
  11 GetOutputCurrentType, 22 ProcessOutput; IMediaBuffer 3 SetLength, 4 GetMaxLength, 5 GetBufferAndLength;
  IPropertyStore 3 GetCount, 4 GetAt, 5 GetValue, 6 SetValue.
  The property set {6F52C567-0360-4BD2-9617-CCBF1421C939} is the public Voice Capture DSP key set MFPKEY_WMAAECMA_*
  (Windows SDK wmcodecdsp.h; Microsoft Learn, "Voice Capture DSP"): 2 SYSTEM_MODE, 3 DMO_SOURCE_MODE, 4 DEVICE_INDEXES,
  5 FEATURE_MODE, 8 FEATR_NS, 9 FEATR_AGC, 10 FEATR_AES, 16 MICARRAY_DESCPTR, 18 FEATR_MICARR_MODE, 19 FEATR_MICARR_BEAM ...
  (Disclosure: during the first probe these ids were located by a byte search of the installed KinectAudio10.dll, before
  the public documentation was identified; this script does not read any SDK binary.)

Stage 1 reads types and properties (no audio). Stage 2 runs the DMO for ~12 s with OPTIBEAM_ARRAY_ONLY and reads
GetBeam / GetPosition after each ProcessOutput. The DMO's output audio is held in memory only to count bytes
and compute its RMS, then discarded. No audio file is written. BELOW_NORMAL priority.

SEALED BARS (fixed before the run):
  D1 CHANNELS  the claim "the DMO gives 4 channels" PASSES only if some output type the DMO offers, or accepts
               with DMO_SET_TYPEF_TEST_ONLY, has 4 channels. Otherwise the claim FAILS.
  D2 BEAM GRID every GetBeam value lies within 0.5 deg of the 11-beam grid -50..+50 deg step 10 -> PASS.
  D3 SOURCE    report the GetPosition angle / confidence distribution for the ambient room (no deliberate
               source) -- descriptive only; accuracy needs a source at a known bearing (operator).
  D4 RATE      produced bytes per second within 2 % of 32000 (16 kHz x 16-bit mono) -> PASS.
"""
import os, sys, time, json, math, struct
import ctypes as C
from ctypes import wintypes as W
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import nui                                    # noqa: E402
from sensor import Sensor                     # noqa: E402
from atlas_common import below_normal_priority   # noqa: E402

V_GET_AUDIO_SOURCE = 21                       # NuiSensor.h INuiSensorVtbl: NuiGetAudioSource
B_GETBEAM, B_SETBEAM, B_GETPOSITION = 3, 4, 5  # NuiSensor.h INuiAudioBeamVtbl
RUN_S = float(os.environ.get('DMO_RUN_S', '12'))
SYS_MODE = int(os.environ.get('DMO_SYS_MODE', '2'))   # 2 = OPTIBEAM_ARRAY_ONLY (sealed run); others are diagnostics


class GUID(C.Structure):
    _fields_ = [("d1", C.c_uint32), ("d2", C.c_uint16), ("d3", C.c_uint16), ("d4", C.c_ubyte * 8)]

    @classmethod
    def s(cls, text):
        g = cls()
        C.oledll.ole32.CLSIDFromString(C.c_wchar_p(text), C.byref(g))
        return g

    def __str__(self):
        return "{%08X-%04X-%04X-%s-%s}" % (self.d1, self.d2, self.d3, bytes(self.d4[:2]).hex().upper(),
                                            bytes(self.d4[2:]).hex().upper())


IID_IUnknown = GUID.s("{00000000-0000-0000-C000-000000000046}")
IID_IMediaObject = GUID.s("{D8AD0F58-5494-4102-97C5-EC798E59BCF4}")
IID_IMediaBuffer = GUID.s("{59EFF8B9-938C-4A26-82F2-95CB84CDC837}")
IID_IPropertyStore = GUID.s("{886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99}")
MEDIATYPE_Audio = GUID.s("{73647561-0000-0010-8000-00AA00389B71}")
MEDIASUBTYPE_PCM = GUID.s("{00000001-0000-0010-8000-00AA00389B71}")
MEDIASUBTYPE_FLOAT = GUID.s("{00000003-0000-0010-8000-00AA00389B71}")
FORMAT_WaveFormatEx = GUID.s("{05589F81-C356-11CE-BF01-00AA0055595A}")
AEC_FMTID = GUID.s("{6F52C567-0360-4BD2-9617-CCBF1421C939}")
PID_NAMES = {2: "SYSTEM_MODE", 3: "DMO_SOURCE_MODE", 4: "DEVICE_INDEXES", 5: "FEATURE_MODE", 6: "FEATR_FRAME_SIZE",
             7: "FEATR_ECHO_LENGTH", 8: "FEATR_NS", 9: "FEATR_AGC", 10: "FEATR_AES", 11: "FEATR_VAD",
             12: "FEATR_CENTER_CLIP", 13: "FEATR_NOISE_FILL", 14: "RETRIEVE_TS_STATS", 15: "QUALITY_METRICS",
             16: "MICARRAY_DESCPTR", 17: "DEVICEPAIR_GUID", 18: "FEATR_MICARR_MODE", 19: "FEATR_MICARR_BEAM",
             20: "FEATR_MICARR_PREPROC", 21: "MIC_GAIN_BOUNDER"}


class PROPERTYKEY(C.Structure):
    _fields_ = [("fmtid", GUID), ("pid", C.c_uint32)]


class PROPVARIANT(C.Structure):
    _fields_ = [("vt", C.c_uint16), ("r1", C.c_uint16), ("r2", C.c_uint16), ("r3", C.c_uint16),
                ("u1", C.c_uint64), ("u2", C.c_uint64)]


class WFX(C.Structure):
    _pack_ = 1
    _fields_ = [("wFormatTag", C.c_uint16), ("nChannels", C.c_uint16), ("nSamplesPerSec", C.c_uint32),
                ("nAvgBytesPerSec", C.c_uint32), ("nBlockAlign", C.c_uint16), ("wBitsPerSample", C.c_uint16),
                ("cbSize", C.c_uint16)]


class DMO_MEDIA_TYPE(C.Structure):
    _fields_ = [("majortype", GUID), ("subtype", GUID), ("bFixedSizeSamples", C.c_int),
                ("bTemporalCompression", C.c_int), ("lSampleSize", C.c_uint32), ("formattype", GUID),
                ("pUnk", C.c_void_p), ("cbFormat", C.c_uint32), ("pbFormat", C.c_void_p)]


class DMO_OUTPUT_DATA_BUFFER(C.Structure):
    _fields_ = [("pBuffer", C.c_void_p), ("dwStatus", C.c_uint32), ("rtTimestamp", C.c_int64),
                ("rtTimelength", C.c_int64)]


assert C.sizeof(PROPVARIANT) == 24 and C.sizeof(DMO_MEDIA_TYPE) == 88 and C.sizeof(DMO_OUTPUT_DATA_BUFFER) == 32

ole32 = C.windll.ole32
ole32.PropVariantClear.argtypes = [C.POINTER(PROPVARIANT)]
ole32.CoTaskMemFree.argtypes = [C.c_void_p]
ole32.CoTaskMemFree.restype = None


def vcall(p, idx, restype, *argtypes):
    vt = C.cast(p, C.POINTER(C.POINTER(C.c_void_p))).contents
    return C.WINFUNCTYPE(restype, C.c_void_p, *argtypes)(vt[idx])


def hx(hr):
    return "0x%08X" % (hr & 0xFFFFFFFF)


def qi(p, iid):
    out = C.c_void_p()
    hr = vcall(p, 0, C.c_long, C.POINTER(GUID), C.POINTER(C.c_void_p))(p, C.byref(iid), C.byref(out))
    return hr, out


def release(p):
    if p and p.value:
        vcall(p, 2, C.c_ulong)(p)


# ---------------- a minimal IMediaBuffer implemented in Python ----------------
QI_T = C.WINFUNCTYPE(C.c_long, C.c_void_p, C.POINTER(GUID), C.POINTER(C.c_void_p))
REF_T = C.WINFUNCTYPE(C.c_ulong, C.c_void_p)
SETLEN_T = C.WINFUNCTYPE(C.c_long, C.c_void_p, C.c_uint32)
MAXLEN_T = C.WINFUNCTYPE(C.c_long, C.c_void_p, C.POINTER(C.c_uint32))
GETBUF_T = C.WINFUNCTYPE(C.c_long, C.c_void_p, C.POINTER(C.c_void_p), C.POINTER(C.c_uint32))


class PyMediaBuffer:
    def __init__(self, size):
        self.data = (C.c_ubyte * size)()
        self.size = size
        self.length = 0
        self.fns = [QI_T(self._qi), REF_T(lambda this: 2), REF_T(lambda this: 1), SETLEN_T(self._setlen),
                    MAXLEN_T(self._maxlen), GETBUF_T(self._getbuf)]
        self.vtbl = (C.c_void_p * 6)(*[C.cast(f, C.c_void_p) for f in self.fns])
        self.obj = C.c_void_p(C.addressof(self.vtbl))       # object = pointer to vtable
        self.ptr = C.c_void_p(C.addressof(self.obj))

    def _qi(self, this, riid, ppv):
        g = riid.contents
        if bytes(g) in (bytes(IID_IUnknown), bytes(IID_IMediaBuffer)):
            ppv[0] = this
            return 0
        ppv[0] = None
        return 0x80004002 - (1 << 32)                        # E_NOINTERFACE

    def _setlen(self, this, n):
        if n > self.size:
            return 0x80070057 - (1 << 32)
        self.length = n
        return 0

    def _maxlen(self, this, p):
        p[0] = self.size
        return 0

    def _getbuf(self, this, ppbuf, plen):
        if ppbuf:
            ppbuf[0] = C.addressof(self.data)
        if plen:
            plen[0] = self.length
        return 0


def decode_mt(mt):
    d = {"major": str(mt.majortype), "sub": str(mt.subtype), "formattype": str(mt.formattype), "cbFormat": mt.cbFormat}
    if mt.pbFormat and mt.cbFormat >= 16:
        w = C.cast(mt.pbFormat, C.POINTER(WFX)).contents
        d.update(tag=hex(w.wFormatTag), ch=w.nChannels, sr=w.nSamplesPerSec, bits=w.wBitsPerSample)
    return d


def make_mt(ch, bits, fl=False):
    w = WFX(3 if fl else 1, ch, 16000, 16000 * ch * bits // 8, ch * bits // 8, bits, 0)
    mt = DMO_MEDIA_TYPE()
    mt.majortype = MEDIATYPE_Audio
    mt.subtype = MEDIASUBTYPE_FLOAT if fl else MEDIASUBTYPE_PCM
    mt.bFixedSizeSamples = 1
    mt.formattype = FORMAT_WaveFormatEx
    mt.cbFormat = C.sizeof(WFX)
    mt.pbFormat = C.cast(C.pointer(w), C.c_void_p)
    return mt, w


def pv_decode(pv):
    vt = pv.vt
    raw = bytes(pv)
    if vt == 0:
        return "EMPTY"
    if vt == 3:
        return ("I4", struct.unpack_from("<i", raw, 8)[0])
    if vt == 19:
        return ("UI4", struct.unpack_from("<I", raw, 8)[0])
    if vt == 11:
        return ("BOOL", struct.unpack_from("<h", raw, 8)[0])
    if vt == 65:                                               # VT_BLOB
        n, p = struct.unpack_from("<IxxxxQ", raw, 8)
        blob = C.string_at(p, n) if p and n else b""
        return ("BLOB", n, blob.hex())
    if vt == 72:                                               # VT_CLSID
        p = struct.unpack_from("<Q", raw, 8)[0]
        return ("CLSID", str(C.cast(p, C.POINTER(GUID)).contents) if p else None)
    return ("VT%d" % vt, raw[8:24].hex())


def decode_mic_geometry(hexblob):
    b = bytes.fromhex(hexblob)
    if len(b) < 18:
        return None
    ver, typ, vb, ve, hb, he, flo, fhi, n = struct.unpack_from("<HHhhhhHHH", b, 0)
    mics = []
    for i in range(n):
        o = 18 + 12 * i
        if o + 12 > len(b):
            break
        t, x, y, z, va, ha = struct.unpack_from("<Hhhhhh", b, o)
        mics.append({"type": t, "x_mm": x, "y_mm": y, "z_mm": z, "v_angle_1e-4rad": va, "h_angle_1e-4rad": ha})
    return {"version": ver, "array_type": typ, "v_angle_begin_end_1e-4rad": [vb, ve],
            "h_angle_begin_end_1e-4rad": [hb, he], "freq_band_hz": [flo, fhi], "n_mics": n, "mics": mics}


def main():
    below_normal_priority()
    out = {}
    # the toolkit samples call CoInitializeEx(NULL, COINIT_MULTITHREADED) first; without it every
    # ProcessOutput returns 0x800401F0 CO_E_NOTINITIALIZED (run 1 of this probe)
    out["CoInitializeEx_MTA"] = hx(C.windll.ole32.CoInitializeEx(None, 0))
    s = Sensor(0)
    beam = C.c_void_p(); dmo = C.c_void_p(); ps = C.c_void_p()
    try:
        print("vtable check:", s.verify())
        s.initialize(nui.INIT_AUDIO)
        hr = s._call(V_GET_AUDIO_SOURCE, C.WINFUNCTYPE(C.c_long, C.c_void_p, C.POINTER(C.c_void_p)))(s.p, C.byref(beam))
        out["NuiGetAudioSource"] = hx(hr)
        if hr < 0:
            raise OSError("NuiGetAudioSource " + hx(hr))
        hr1, dmo = qi(beam, IID_IMediaObject)
        hr2, ps = qi(beam, IID_IPropertyStore)
        out["QI_IMediaObject"], out["QI_IPropertyStore"] = hx(hr1), hx(hr2)

        # ---- beam / position before any ProcessOutput ----
        a, c = C.c_double(), C.c_double()
        out["GetBeam_before"] = (hx(vcall(beam, B_GETBEAM, C.c_long, C.POINTER(C.c_double))(beam, C.byref(a))), a.value)
        out["GetPosition_before"] = (hx(vcall(beam, B_GETPOSITION, C.c_long, C.POINTER(C.c_double), C.POINTER(C.c_double))(
            beam, C.byref(a), C.byref(c))), a.value, c.value)

        # ---- stream counts and offered output types ----
        ni, no = C.c_uint32(), C.c_uint32()
        out["GetStreamCount"] = (hx(vcall(dmo, 3, C.c_long, C.POINTER(C.c_uint32), C.POINTER(C.c_uint32))(dmo, C.byref(ni), C.byref(no))),
                                 ni.value, no.value)
        offered = []
        for i in range(16):
            mt = DMO_MEDIA_TYPE()
            hr = vcall(dmo, 7, C.c_long, C.c_uint32, C.c_uint32, C.POINTER(DMO_MEDIA_TYPE))(dmo, 0, i, C.byref(mt))
            if hr < 0:
                offered.append({"index": i, "hr": hx(hr)})
                break
            offered.append(dict(index=i, **decode_mt(mt)))
            if mt.pbFormat:
                ole32.CoTaskMemFree(mt.pbFormat)
        out["GetOutputType"] = offered

        # ---- properties ----
        props = {}
        n = C.c_uint32()
        hr = vcall(ps, 3, C.c_long, C.POINTER(C.c_uint32))(ps, C.byref(n))
        out["PropertyStore_GetCount"] = (hx(hr), n.value)
        keys = []
        if hr >= 0:
            for i in range(n.value):
                k = PROPERTYKEY()
                if vcall(ps, 4, C.c_long, C.c_uint32, C.POINTER(PROPERTYKEY))(ps, i, C.byref(k)) >= 0:
                    keys.append(k)
        if not keys:
            for pid in list(range(2, 22)) + list(range(42, 50)):
                k = PROPERTYKEY(); k.fmtid = AEC_FMTID; k.pid = pid; keys.append(k)
        for k in keys:
            pv = PROPVARIANT()
            hr = vcall(ps, 5, C.c_long, C.POINTER(PROPERTYKEY), C.POINTER(PROPVARIANT))(ps, C.byref(k), C.byref(pv))
            name = PID_NAMES.get(k.pid, "pid%d" % k.pid) if bytes(k.fmtid) == bytes(AEC_FMTID) else "%s,%d" % (k.fmtid, k.pid)
            props[name] = (hx(hr), pv_decode(pv)) if hr >= 0 else (hx(hr),)
            if hr >= 0:
                ole32.PropVariantClear(C.byref(pv))
        out["properties_default"] = props
        geo = props.get("MICARRAY_DESCPTR")
        if geo and len(geo) > 1 and isinstance(geo[1], tuple) and geo[1][0] == "BLOB":
            out["mic_geometry_from_DMO"] = decode_mic_geometry(geo[1][2])

        # ---- which output formats does it ACCEPT (test only)? ----
        accepts = {}
        for ch, bits, fl in ((1, 16, False), (1, 32, True), (2, 16, False), (4, 16, False), (4, 32, True), (4, 32, False)):
            mt, _w = make_mt(ch, bits, fl)
            hr = vcall(dmo, 9, C.c_long, C.c_uint32, C.POINTER(DMO_MEDIA_TYPE), C.c_uint32)(dmo, 0, C.byref(mt), 1)  # TEST_ONLY
            accepts["%dch_%d%s" % (ch, bits, "f" if fl else "i")] = hx(hr)
        out["SetOutputType_test_only"] = accepts
        d1 = any(isinstance(o.get("ch"), int) and o["ch"] == 4 for o in offered) or any(
            v == "0x00000000" for k, v in accepts.items() if k.startswith("4ch"))
        out["D1_claim_DMO_gives_4ch"] = "PASS" if d1 else "FAIL"
        print(json.dumps(out, indent=1, default=str))

        # ---- stage 2: run it ----
        pv = PROPVARIANT(); pv.vt = 3; pv.u1 = SYS_MODE          # VT_I4 system mode
        k = PROPERTYKEY(); k.fmtid = AEC_FMTID; k.pid = 2
        out["set_SYSTEM_MODE_%d" % SYS_MODE] = hx(vcall(ps, 6, C.c_long, C.POINTER(PROPERTYKEY), C.POINTER(PROPVARIANT))(ps, C.byref(k), C.byref(pv)))
        mt, _w = make_mt(1, 16)
        out["SetOutputType_1ch16"] = hx(vcall(dmo, 9, C.c_long, C.c_uint32, C.POINTER(DMO_MEDIA_TYPE), C.c_uint32)(dmo, 0, C.byref(mt), 0))
        out["AllocateStreamingResources"] = hx(vcall(dmo, 18, C.c_long)(dmo))
        mb = PyMediaBuffer(16000 * 2)
        odb = DMO_OUTPUT_DATA_BUFFER(); odb.pBuffer = mb.ptr.value
        PO = vcall(dmo, 22, C.c_long, C.c_uint32, C.c_uint32, C.POINTER(DMO_OUTPUT_DATA_BUFFER), C.POINTER(C.c_uint32))
        GB = vcall(beam, B_GETBEAM, C.c_long, C.POINTER(C.c_double))
        GP = vcall(beam, B_GETPOSITION, C.c_long, C.POINTER(C.c_double), C.POINTER(C.c_double))
        recs, produced, sq, nsamp, hrs = [], 0, 0.0, 0, {}
        t0 = time.perf_counter()
        first_data = None
        while time.perf_counter() - t0 < RUN_S:
            while True:
                mb.length = 0
                odb.dwStatus = 0
                st = C.c_uint32()
                hr = PO(dmo, 0, 1, C.byref(odb), C.byref(st))
                hrs[hx(hr)] = hrs.get(hx(hr), 0) + 1
                if hr < 0:
                    break
                if hr == 0 and mb.length:
                    if first_data is None:
                        first_data = time.perf_counter() - t0
                    produced += mb.length
                    x = np.frombuffer(bytes(mb.data[:mb.length]), dtype=np.int16).astype(np.float64)
                    sq += float(np.dot(x, x)); nsamp += len(x)
                    del x
                if not (odb.dwStatus & 0x01000000):              # DMO_OUTPUT_DATA_BUFFERF_INCOMPLETE
                    break
            b, a, c = C.c_double(), C.c_double(), C.c_double()
            hb = GB(beam, C.byref(b)); hp = GP(beam, C.byref(a), C.byref(c))
            recs.append((time.perf_counter() - t0, hb, b.value, hp, a.value, c.value))
            time.sleep(0.02)
        elapsed = time.perf_counter() - t0
        R = np.array([(r[0], r[2], r[4], r[5]) for r in recs])
        ok = np.array([(r[1] >= 0 and r[3] >= 0) for r in recs])
        beams_deg = np.degrees(R[ok, 1])
        grid_err = np.abs(beams_deg - 10 * np.round(beams_deg / 10))
        ang, conf = np.degrees(R[ok, 2]), R[ok, 3]
        rate = produced / max(elapsed - (first_data or 0), 1e-6)
        out.update(ProcessOutput_hr_counts=hrs, n_polls=len(recs), n_ok=int(ok.sum()),
                   first_data_s=first_data, produced_bytes=produced,
                   D4_bytes_per_s=rate, D4_pass=bool(abs(rate / 32000 - 1) <= 0.02),
                   output_rms_dbfs=(20 * math.log10(math.sqrt(sq / nsamp) / 32768) if nsamp else None),
                   beam_values_deg=sorted(set(np.round(beams_deg, 3).tolist())),
                   D2_max_grid_err_deg=float(grid_err.max()) if len(grid_err) else None,
                   D2_pass=bool(len(grid_err) and grid_err.max() <= 0.5),
                   D3_source_angle_deg_pcts=np.percentile(ang, [5, 25, 50, 75, 95]).round(2).tolist() if len(ang) else None,
                   D3_confidence_pcts=np.percentile(conf, [5, 25, 50, 75, 95]).round(3).tolist() if len(conf) else None,
                   D3_frac_zero_zero=float(np.mean((R[ok, 2] == 0) & (R[ok, 3] == 0))) if ok.any() else None,
                   D3_distinct_source_angles=int(len(np.unique(np.round(ang, 4)))) if len(ang) else 0)
        print(json.dumps({k: v for k, v in out.items() if k not in ("properties_default", "GetOutputType")}, indent=1, default=str))
    finally:
        release(dmo); release(ps); release(beam)
        s.release()
    with open(os.path.join(HERE, "dmo_probe.json" if SYS_MODE == 2 else "dmo_probe_mode%d.json" % SYS_MODE), "w") as f:
        json.dump(out, f, indent=1, default=str)
    print("wrote dmo_probe.json (statistics only; no audio stored)")


if __name__ == "__main__":
    main()
