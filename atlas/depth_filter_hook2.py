"""depth_filter_hook2.py -- POST-HOC follow-up to depth_filter_hook.py (labelled; no new sealed rule).
depth_filter_hook.py: NuiSetDepthFilter(ours) BEFORE opening a stream -> E_INVALIDARG, ProcessFrame never called.
Here: log every QueryInterface / AddRef the runtime makes on our object, and try the call (a) with NULL, (b) after the depth stream
is open, (c) after the first frame. Pass-through only (*pFrameModified = FALSE). Process-local; removed before shutdown. ~2 s streaming.
"""
import time, ctypes as C
from atlas_common import NUI_IMAGE_FRAME, below_normal_priority, hr_hex, FLAG_DISTINCT_OVERFLOW, V_SET_DEPTH_FILTER, V_GET_DEPTH_FILTER
from sensor import Sensor, V_STREAM_NEXT, V_STREAM_RELEASE, _F_next, _F_relframe
from depth_filter_hook import PyDepthFilter, _F_setf, _F_getf, guid_eq, IID_IUnknown
from depth_filter_probe import IID_INuiDepthFilter


class LoggingFilter(PyDepthFilter):
    def __init__(self):
        self.log = []
        super().__init__()

    def qi(self, this, riid, ppv):
        g = riid.contents
        self.log.append("QI {%08X-%04X-%04X-%s}" % (g.a, g.b, g.c, bytes(g.d).hex().upper()))
        return super().qi(this, riid, ppv)

    def addref(self, this):
        self.log.append("AddRef"); return super().addref(this)

    def release(self, this):
        self.log.append("Release"); return super().release(this)


def main():
    print("below-normal priority:", below_normal_priority())
    s = Sensor(); print("verify:", s.verify()); s.initialize(0x00000020)
    f = LoggingFilter(); setf = s._call(V_SET_DEPTH_FILTER, _F_setf); getf = s._call(V_GET_DEPTH_FILTER, _F_getf)
    try:
        print("(a) Set(NULL) before stream:", hr_hex(setf(s.p, None)))
        print("    Set(ours) before stream:", hr_hex(setf(s.p, f.ptr)), f.log); f.log.clear()
        h = s.open_stream(4, 2, stream_flags=FLAG_DISTINCT_OVERFLOW)
        print("(b) Set(ours) after open:", hr_hex(setf(s.p, f.ptr)), f.log); f.log.clear()
        time.sleep(0.5)
        fr = NUI_IMAGE_FRAME(); r = s._call(V_STREAM_NEXT, _F_next)(s.p, h, C.c_uint32(3000), C.byref(fr))
        if r >= 0:
            s._call(V_STREAM_RELEASE, _F_relframe)(s.p, h, C.byref(fr))
        print("(c) Set(ours) after a frame:", hr_hex(setf(s.p, f.ptr)), f.log); f.log.clear()
        g = C.c_void_p(); print("    Get:", hr_hex(getf(s.p, C.byref(g))), "ours" if g.value == f.ptr.value else g.value)
        for _ in range(30):
            fr = NUI_IMAGE_FRAME()
            if s._call(V_STREAM_NEXT, _F_next)(s.p, h, C.c_uint32(3000), C.byref(fr)) >= 0:
                s._call(V_STREAM_RELEASE, _F_relframe)(s.p, h, C.byref(fr))
        print("    ProcessFrame calls during 30 frames:", len(f.calls), "| sizes", sorted({(c[1], c[2]) for c in f.calls}), "| log", f.log[:6])
    finally:
        try:
            print("    Set(NULL) at end:", hr_hex(setf(s.p, None)))
        finally:
            s.shutdown(); s.release()


if __name__ == '__main__':
    main()
