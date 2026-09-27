"""
Kill the projector and see what the IR camera sees on its own.

If NuiSetForceInfraredEmitterOff works, the dot pattern vanishes and IR intensity
collapses to whatever ambient 830nm light is in the room -- the Kinect becomes a
passive near-infrared camera. If the call is a no-op, intensity will not change,
and that is a clean negative.

The vtable is verified against two harmless slots with known answers before any
hardware call, so a wrong layout fails loudly rather than corrupting the process.
"""
import sys, time; sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import numpy as np, nui
from sensor import Sensor

s = Sensor(0)
try:
    print("vtable check:", s.verify(), "-> layout confirmed\n")
    # NuiInitialize FIRST -- accelerometer and emitter calls return
    # 0x80070015 ERROR_NOT_READY before the device is initialised.
    s.initialize(nui.INIT_DEPTH | nui.INIT_COLOR)
    s.open_stream(nui.IMG_COLOR_INFRARED, nui.RES_640x480)
    time.sleep(1.5)
    print("accelerometer (raw g): x=%+.3f y=%+.3f z=%+.3f" % s.accelerometer()[:3])
    print("elevation angle      : %d deg" % s.elevation_angle())
    print("emitter currently off: %s\n" % s.get_ir_emitter_off())

    def sample(n=25):
        fr, misses = [], 0
        while len(fr) < n and misses < 60:
            try:
                a, _fn = s.grab(nui.IMG_COLOR_INFRARED, timeout_ms=4000)
                fr.append((a >> 6).astype(np.float32))   # 10-bit payload
            except OSError:
                misses += 1; time.sleep(0.05)
        if not fr:
            raise RuntimeError("no IR frames after %d attempts" % misses)
        if misses:
            print("   (%d empty frames skipped)" % misses)
        return np.stack(fr)

    on = sample()
    print("EMITTER ON   mean %7.2f   p99 %6.0f   max %4.0f   frac>500 %.4f"
          % (on.mean(), np.percentile(on, 99), on.max(), (on > 500).mean()))

    s.set_ir_emitter_off(True)
    print("\n-> NuiSetForceInfraredEmitterOff(TRUE) accepted; get() now reports:",
          s.get_ir_emitter_off())
    time.sleep(2.0)
    off = sample()
    print("EMITTER OFF  mean %7.2f   p99 %6.0f   max %4.0f   frac>500 %.4f"
          % (off.mean(), np.percentile(off, 99), off.max(), (off > 500).mean()))

    np.save('ir_emitter_on.npy', on[0]); np.save('ir_emitter_off.npy', off[0])

    ratio = on.mean() / max(off.mean(), 1e-6)
    print("\nintensity ratio ON/OFF : %.2fx" % ratio)

    # the decisive test: the dot pattern is high-spatial-frequency structure.
    def hf(img):
        a = img.astype(float); n = min(a.shape); a = a[:n, :n]
        w = np.hanning(n); a = (a - a.mean()) * w[:, None] * w[None, :]
        P = np.abs(np.fft.fftshift(np.fft.fft2(a))) ** 2
        Y, X = np.mgrid[:n, :n]; r = np.hypot(Y - n // 2, X - n // 2) / (n / 2)
        return P[(r > 0.5) & (r <= 1.0)].sum() / P[r <= 1.0].sum()
    print("high-freq power (dots) ON  : %.4f" % hf(on[0]))
    print("high-freq power (dots) OFF : %.4f" % hf(off[0]))

    print("\nVERDICT: %s" % ("PROJECTOR OFF -- passive 830nm NIR camera confirmed"
                             if ratio > 2.0 else "no change -- the call did not take effect"))
finally:
    try: s.set_ir_emitter_off(False)
    except Exception: pass
    s.release()
    print("\nemitter restored to ON")
