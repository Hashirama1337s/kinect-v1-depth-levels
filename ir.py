"""
The IR stream: the actual raw sensor view, plus the projector's dot pattern.

TEST: is NUI's 1280x960 IR mode genuinely native, or a 640x480 upscale?
A natively-sampled image carries energy right up to its own Nyquist. An upscaled
one has near-zero energy above half-Nyquist, because the information was never there.
Measure radial power spectra of both modes and compare the high-frequency fraction.

H0 (upscaled): HF fraction of the 1280 image ~ that of an explicitly 2x-upsampled 640.
H1 (native)  : 1280 carries substantially more.
Both are computed, so the test can land on either.
"""
import sys, time; sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import numpy as np, nui

def grab_ir(res, n=10):
    k = nui.Kinect(nui.INIT_DEPTH | nui.INIT_COLOR)
    try:
        k.open_stream(nui.IMG_COLOR_INFRARED, res); time.sleep(1.5)
        out=[]
        for _ in range(n):
            a,fn,_ = k.grab(nui.IMG_COLOR_INFRARED, timeout_ms=4000); out.append(a)
        return np.stack(out)
    finally:
        k.close()

lo = grab_ir(nui.RES_640x480)
print("IR  640x480 : shape %s dtype %s  range %d..%d" % (lo.shape[1:], lo.dtype, lo.min(), lo.max()))
hi = grab_ir(nui.RES_1280x960)
print("IR 1280x960 : shape %s dtype %s  range %d..%d" % (hi.shape[1:], hi.dtype, hi.min(), hi.max()))
np.save('ir_640.npy', lo[0]); np.save('ir_1280.npy', hi[0])

def radial_hf(img):
    """fraction of spectral power above half-Nyquist, on a Hann-windowed centre crop"""
    a = img.astype(np.float64)
    s = min(a.shape); a = a[:s,:s]
    w = np.hanning(s); a = (a - a.mean()) * w[:,None] * w[None,:]
    P = np.abs(np.fft.fftshift(np.fft.fft2(a)))**2
    cy = cx = s//2
    Y,X = np.mgrid[:s,:s]
    r = np.hypot(Y-cy, X-cx) / (s/2.0)          # 1.0 = Nyquist
    tot = P[r<=1.0].sum()
    return P[(r>0.5)&(r<=1.0)].sum()/tot

f_lo = radial_hf(lo[0])
f_hi = radial_hf(hi[0])
up   = np.repeat(np.repeat(lo[0],2,0),2,1)      # explicit 2x nearest upscale of the 640
f_up = radial_hf(up)

print("\n--- fraction of spectral power above half-Nyquist ---")
print("  native  640x480 : %.4f" % f_lo)
print("  2x-upscaled 640 : %.4f   <- what an upscale looks like" % f_up)
print("  claimed 1280x960: %.4f" % f_hi)
print("\nVERDICT: %s" % ("NATIVE -- carries far more HF than an upscale"
      if f_hi > 3*f_up else "consistent with UPSCALING"))

# the projector's dot pattern: nearest-neighbour spacing of local maxima
img = hi[0].astype(np.float64)
c = img[300:700, 400:800]
from numpy.lib.stride_tricks import sliding_window_view
w = sliding_window_view(c, (3,3))
peaks = (w.max(axis=(-2,-1)) == c[1:-1,1:-1]) & (c[1:-1,1:-1] > np.percentile(c, 90))
ys, xs = np.where(peaks)
print("\n--- projector dot pattern (1280x960 IR, 400x400 crop) ---")
print("  local maxima found: %d  -> density %.4f dots/px" % (ys.size, ys.size/c.size))
if ys.size > 50:
    pts = np.c_[ys,xs].astype(np.float64)
    sub = pts[np.random.default_rng(0).choice(pts.shape[0], min(2000,pts.shape[0]), replace=False)]
    d = np.hypot(sub[:,None,0]-sub[None,:,0], sub[:,None,1]-sub[None,:,1])
    np.fill_diagonal(d, np.inf)
    nn = d.min(1)
    print("  nearest-neighbour spacing: median %.2f px  mean %.2f  sd %.2f" % (np.median(nn), nn.mean(), nn.std()))
    print("  => ~%.0f dots across the 1280px field" % (1280/np.median(nn)))
