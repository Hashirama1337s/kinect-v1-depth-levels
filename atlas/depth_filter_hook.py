"""depth_filter_hook.py -- does the SDK 1.8 runtime actually call an application depth filter ('Reserved for future use')?
Process-local only: installs a Python INuiDepthFilter on OUR INuiSensor instance, removes it before shutdown. No system change.
~2 x 1.5 s of streaming.

Public: NuiSensor.h declares INuiDepthFilter::ProcessFrame(LARGE_INTEGER liTimeStamp, UINT width, UINT height,
NUI_DEPTH_IMAGE_PIXEL *pDepthImagePixels, BOOL *pFrameModified) and INuiSensor::NuiSetDepthFilter (vtable 34). The 1.8 docs say
only 'Reserved for future use' / 'Not used'. depth_filter_probe.py showed the getters are live (S_OK + NULL; the for-timestamp
getter rejects timestamp 0 with E_INVALIDARG).

RULES (fixed before running):
  F1 ACCEPT      : NuiSetDepthFilter(ours) returns S_OK and NuiGetDepthFilter then returns our pointer -> SET WORKS.
  F2 CALLED      : phase 1 (pass-through, *pFrameModified = FALSE): ProcessFrame is invoked for >= 20 of 30 grabbed frames
                   -> RUNTIME CALLS THE FILTER; 0 calls -> INERT.
  F3 INPUT       : report width x height passed; the pixels passed equal the extended texture of the same frame (matched by
                   the timestamp argument == frame liTimeStamp) on >= 99.9 % of pixels -> FILTER SEES FULL DEPTH;
                   also report whether values < 800 / > 4000 occur in its input.
  F4 PROPAGATION : phase 2, the filter writes three marker pixels in row 10 (col 10 := 1234 mm, col 11 := 600 mm,
                   col 12 := 5000 mm) and sets *pFrameModified = TRUE. If extended shows 1234/600/5000 and packed (distinct-overflow
                   flag on) shows 1234 / 0 (too near) / 4095 (too far) -> FILTER RUNS BEFORE PACKING. Other outcomes reported as seen.
Prints summary numbers only.
"""
import time, ctypes as C
from ctypes import wintypes as W
import numpy as np
from atlas_common import (NUI_IMAGE_FRAME, NUI_DEPTH_IMAGE_PIXEL, _vtbl, below_normal_priority, hr_hex, FLAG_DISTINCT_OVERFLOW,
                          V_DEPTH_PIXEL_TEXTURE, V_SET_DEPTH_FILTER, V_GET_DEPTH_FILTER)
from extended_depth_probe import lock_copy, _F_dpt, _F_rel, W_, H_
from sensor import Sensor, V_STREAM_NEXT, V_STREAM_RELEASE, _F_next, _F_relframe
from depth_filter_probe import GUID, IID_INuiDepthFilter

IID_IUnknown = GUID(0, 0, 0, (C.c_ubyte * 8)(0xC0, 0, 0, 0, 0, 0, 0, 0x46))
_QI = C.WINFUNCTYPE(C.c_long, C.c_void_p, C.POINTER(GUID), C.POINTER(C.c_void_p))
_AR = C.WINFUNCTYPE(C.c_ulong, C.c_void_p)
_PF = C.WINFUNCTYPE(C.c_long, C.c_void_p, C.c_int64, C.c_uint, C.c_uint, C.POINTER(NUI_DEPTH_IMAGE_PIXEL), C.POINTER(C.c_int))
_F_setf = C.WINFUNCTYPE(C.c_long, C.c_void_p, C.c_void_p)
_F_getf = C.WINFUNCTYPE(C.c_long, C.c_void_p, C.POINTER(C.c_void_p))


def guid_eq(a, b):
    return a.a == b.a and a.b == b.b and a.c == b.c and bytes(a.d) == bytes(b.d)


class PyDepthFilter:
    def __init__(self):
        self.refs = 1; self.calls = []; self.modify = False
        self._qi = _QI(self.qi); self._ar = _AR(self.addref); self._rl = _AR(self.release); self._pf = _PF(self.process)
        self.vtbl = (C.c_void_p * 4)(C.cast(self._qi, C.c_void_p), C.cast(self._ar, C.c_void_p),
                                     C.cast(self._rl, C.c_void_p), C.cast(self._pf, C.c_void_p))
        self.obj = (C.c_void_p * 1)(C.cast(self.vtbl, C.c_void_p))          # COM object = pointer to vtable
        self.ptr = C.cast(self.obj, C.c_void_p)

    def qi(self, this, riid, ppv):
        if guid_eq(riid.contents, IID_IUnknown) or guid_eq(riid.contents, IID_INuiDepthFilter):
            ppv[0] = this; self.refs += 1; return 0
        ppv[0] = None; return -2147467262                                     # E_NOINTERFACE

    def addref(self, this):
        self.refs += 1; return self.refs

    def release(self, this):
        self.refs -= 1; return max(self.refs, 0)

    def process(self, this, ts, width, height, pix, pmod):
        try:
            n = int(width) * int(height)
            buf = np.frombuffer(C.string_at(C.cast(pix, C.c_void_p).value, n * 4), np.uint16).reshape(int(height), int(width), 2).copy()
            if self.modify and width >= 16 and height >= 16:
                row = C.cast(pix, C.POINTER(NUI_DEPTH_IMAGE_PIXEL))
                for col, val in ((10, 1234), (11, 600), (12, 5000)):
                    row[10 * int(width) + col].depth = val
                pmod[0] = 1
            else:
                pmod[0] = 0
            if len(self.calls) < 40:
                self.calls.append((int(ts), int(width), int(height), buf))
            else:
                self.calls.append((int(ts), int(width), int(height), None))
        except Exception as e:                                                # never raise into the SDK
            print("callback error:", e)
        return 0


def run_phase(s, filt, label):
    frames = []
    h = s.open_stream(4, 2, stream_flags=FLAG_DISTINCT_OVERFLOW); time.sleep(0.5)
    for _ in range(30):
        fr = NUI_IMAGE_FRAME()
        if s._call(V_STREAM_NEXT, _F_next)(s.p, h, C.c_uint32(3000), C.byref(fr)) < 0:
            continue
        try:
            raw, _ = lock_copy(fr.pFrameTexture, W_ * H_ * 2)
            near = C.c_int(); tex = C.c_void_p()
            ext = None
            if s._call(V_DEPTH_PIXEL_TEXTURE, _F_dpt)(s.p, h, C.byref(fr), C.byref(near), C.byref(tex)) >= 0:
                try:
                    ext, _ = lock_copy(tex, W_ * H_ * 4)
                finally:
                    _vtbl(tex, 2, _F_rel)(tex)
            frames.append((fr.liTimeStamp, np.frombuffer(raw, np.uint16).reshape(H_, W_).copy(),
                           None if ext is None else np.frombuffer(ext, np.uint16).reshape(H_, W_, 2).copy()))
        finally:
            s._call(V_STREAM_RELEASE, _F_relframe)(s.p, h, C.byref(fr))
    return frames


def main():
    print("below-normal priority:", below_normal_priority())
    s = Sensor(); print("verify:", s.verify()); s.initialize(0x00000020)
    filt = PyDepthFilter(); v = {}
    try:
        hr = s._call(V_SET_DEPTH_FILTER, _F_setf)(s.p, filt.ptr); print("NuiSetDepthFilter", hr_hex(hr), "refs", filt.refs)
        g = C.c_void_p(); hr2 = s._call(V_GET_DEPTH_FILTER, _F_getf)(s.p, C.byref(g))
        print("NuiGetDepthFilter", hr_hex(hr2), "returns ours:", g.value == filt.ptr.value)
        if g.value == filt.ptr.value:
            filt.refs -= 1                                                    # balance the getter's AddRef (our own counter)
        v['F1'] = 'SET WORKS' if (hr >= 0 and g.value == filt.ptr.value) else f'NO ({hr_hex(hr)}, get {hr_hex(hr2)})'
        # phase 1: pass-through
        fr1 = run_phase(s, filt, "pass-through")
        n1 = len(filt.calls); print(f"phase 1: {len(fr1)} frames grabbed, ProcessFrame calls {n1}")
        v['F2'] = 'RUNTIME CALLS THE FILTER' if n1 >= 20 else ('INERT' if n1 == 0 else f'PARTIAL ({n1})')
        if n1:
            sizes = sorted({(c[1], c[2]) for c in filt.calls}); print("   width x height passed:", sizes)
            ts_map = {c[0]: c[3] for c in filt.calls if c[3] is not None}
            matched = [(ext, ts_map[ts]) for ts, raw, ext in fr1 if ts in ts_map and ext is not None]
            print(f"   frames matched by timestamp: {len(matched)} of {len(fr1)}")
            if matched:
                same = [np.mean(e[..., 1] == f[..., 1]) for e, f in matched if e.shape == f.shape]
                eq = float(np.mean(same)) if same else float('nan')
                allin = np.concatenate([f[..., 1].ravel() for _, f in matched]).astype(np.int64)
                print(f"   filter input == extended texture on {100 * eq:.4f} % of pixels; input <800 (nonzero) "
                      f"{100 * np.mean((allin > 0) & (allin < 800)):.3f} %, >4000 {100 * np.mean(allin > 4000):.3f} %, "
                      f"player index nonzero {100 * np.mean(np.concatenate([f[..., 0].ravel() for _, f in matched]) != 0):.3f} %")
                v['F3'] = 'FILTER SEES FULL DEPTH' if eq >= 0.999 else f'DIFFERS ({100 * eq:.3f} %)'
        # phase 2: marker pixels
        filt.modify = True; c0 = len(filt.calls)
        fr2 = run_phase(s, filt, "marker")
        print(f"phase 2: {len(fr2)} frames, calls {len(filt.calls) - c0}")
        seen = []
        for ts, raw, ext in fr2[3:]:
            z = raw >> 3
            seen.append((tuple(int(ext[10, c, 1]) for c in (10, 11, 12)) if ext is not None else None,
                         tuple(int(z[10, c]) for c in (10, 11, 12))))
        from collections import Counter
        cnt = Counter(seen); print("   (extended, packed>>3) at the three markers:", cnt.most_common(4))
        top = cnt.most_common(1)[0][0] if cnt else None
        v['F4'] = ('FILTER RUNS BEFORE PACKING' if top == ((1234, 600, 5000), (1234, 0, 4095)) else f'SEEN {top}')
    finally:
        try:
            s._call(V_SET_DEPTH_FILTER, _F_setf)(s.p, None)                    # remove ours before shutdown
        finally:
            s.shutdown(); s.release()
    print("\nVERDICTS:", v)


if __name__ == '__main__':
    main()
