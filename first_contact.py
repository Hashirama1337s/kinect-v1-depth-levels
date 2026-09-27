import sys, time; sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import numpy as np, nui

print("sensors detected:", nui.sensor_count())
k = nui.Kinect(nui.INIT_DEPTH)
try:
    print("elevation angle (accelerometer-derived): %d deg" % nui.elevation_angle())
    k.open_stream(nui.IMG_DEPTH, nui.RES_640x480)
    time.sleep(1.0)                      # let the stream spin up
    frames = []
    for i in range(5):
        a, fn, ts = k.grab(nui.IMG_DEPTH, timeout_ms=3000)
        frames.append((a, fn, ts))
        print("frame %d  num=%-6d ts=%d  shape=%s dtype=%s" % (i, fn, ts, a.shape, a.dtype))
    a = frames[-1][0]
    valid = a[a > 0]
    print("\n--- depth frame statistics ---")
    print("total pixels      :", a.size)
    print("nonzero pixels    : %d (%.1f%%)" % (valid.size, 100*valid.size/a.size))
    if valid.size:
        print("min / max raw     : %d / %d" % (valid.min(), valid.max()))
        print("median raw        : %d" % np.median(valid))
        print("distinct values   : %d" % np.unique(valid).size)
    fns = [f[1] for f in frames]
    print("frame numbers      :", fns, "-> consecutive:", all(b-a_==1 for a_,b in zip(fns,fns[1:])))
    np.save('first_depth.npy', a)
    print("saved first_depth.npy")
finally:
    k.close()
