"""Does NEAR MODE work on this Xbox 360 sensor?
Near mode is documented as a Kinect-for-Windows HARDWARE feature; Xbox sensors
commonly reject it. If it works, the minimum range drops from ~800mm to ~400mm.
"""
import sys, time, ctypes as C; sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import numpy as np, nui
NEAR = 0x00020000
nui._dll.NuiImageStreamSetImageFrameFlags.argtypes = [C.c_void_p, C.c_uint32]

def probe(flags, label):
    k = nui.Kinect(nui.INIT_DEPTH)
    try:
        k.open_stream(nui.IMG_DEPTH, nui.RES_640x480, stream_flags=flags)
        time.sleep(1.2)
        mins = []
        for _ in range(60):
            a, _, _ = k.grab(nui.IMG_DEPTH, timeout_ms=3000)
            z = (a >> 3).astype(np.int32); v = z[z > 0]
            if v.size > 500: mins.append(int(v.min()))
        if mins:
            print("%-30s nearest %d mm   median-of-frame-minima %d mm"
                  % (label, min(mins), int(np.median(mins))))
        else:
            print("%-30s no valid frames" % label)
    except OSError as e:
        print("%-30s REJECTED: %s" % (label, e))
    finally:
        k.close()
    time.sleep(0.4)

print("NEAR MODE TEST\n")
probe(0, "default range")
probe(NEAR, "NEAR flag at open")

k = nui.Kinect(nui.INIT_DEPTH)
try:
    h = k.open_stream(nui.IMG_DEPTH, nui.RES_640x480)
    hr = nui._dll.NuiImageStreamSetImageFrameFlags(h, C.c_uint32(NEAR))
    ok = hr >= 0
    print("\nNuiImageStreamSetImageFrameFlags(NEAR) -> HRESULT 0x%08X  %s"
          % (hr & 0xFFFFFFFF, "ACCEPTED" if ok else "REJECTED"))
    if ok:
        time.sleep(1.2); mins = []
        for _ in range(60):
            a, _, _ = k.grab(nui.IMG_DEPTH, timeout_ms=3000)
            z = (a >> 3).astype(np.int32); v = z[z > 0]
            if v.size > 500: mins.append(int(v.min()))
        if mins: print("   nearest after enabling: %d mm" % min(mins))
finally:
    k.close()
