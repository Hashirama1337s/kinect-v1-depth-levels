"""
Can the IR image PREDICT per-pixel depth uncertainty?

If depth noise is speckle/signal-limited, a pixel's IR return should set its depth
sigma. If true this is a tool, not a property: every point in a cloud carries its own
predicted error bar, computable from a single IR frame with no repeat measurements.

Falsifiable: if IR intensity carries no information about depth sigma beyond what range
alone gives, R^2 improvement over a range-only model is ~0 and the idea is dead.
Range-only is the control, and it is a strong one -- sigma grows steeply with z.
"""
import sys, time; sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import numpy as np, nui
SHIFT=3; S=256; ND=400; NI=60
y0,x0=(480-S)//2,(640-S)//2

k = nui.Kinect(nui.INIT_DEPTH)
try:
    k.open_stream(nui.IMG_DEPTH, nui.RES_640x480); time.sleep(1.0)
    D=np.zeros((ND,S,S),np.float32)
    for i in range(ND):
        a,_,_=k.grab(nui.IMG_DEPTH,timeout_ms=3000); D[i]=a[y0:y0+S,x0:x0+S]>>SHIFT
finally: k.close()
time.sleep(0.5)
k = nui.Kinect(nui.INIT_DEPTH | nui.INIT_COLOR)
try:
    k.open_stream(nui.IMG_COLOR_INFRARED, nui.RES_640x480); time.sleep(1.5)
    I=np.zeros((NI,S,S),np.float32)
    for i in range(NI):
        a,_,_=k.grab(nui.IMG_COLOR_INFRARED,timeout_ms=4000); I[i]=a[y0:y0+S,x0:x0+S]>>6  # IR is 10-bit<<6
finally: k.close()
print("depth %s  IR %s (10-bit, unpacked)" % (D.shape, I.shape))

good=(D>0).all(0)
z   = D.mean(0)[good]
sig = D.std(0)[good]
ir  = I.mean(0)[good]
print("pixels: %d   z %.0f..%.0f mm   IR %.0f..%.0f   sigma %.2f..%.2f mm"
      % (z.size, z.min(), z.max(), ir.min(), ir.max(), sig.min(), sig.max()))

# work in logs: multiplicative models are the physically motivated ones
m = (sig>0.05) & (ir>1)
L = np.log(sig[m]); Z = np.log(z[m]); R = np.log(ir[m])
def fit(cols, name):
    A=np.c_[np.ones(L.size), *cols]
    c,*_=np.linalg.lstsq(A,L,rcond=None)
    r2=1-((L-A@c).var()/L.var())
    print("  %-28s R2 = %.4f   coeffs %s" % (name, r2, np.array2string(c,precision=3)))
    return r2, c
print("\n--- predicting log(depth sigma), %d pixels ---" % L.size)
r2_z ,_ = fit([Z],    "range only (CONTROL)")
r2_i ,_ = fit([R],    "IR only")
r2_zi,c = fit([Z,R],  "range + IR")
print("\n  IR adds %+.4f R2 over the range-only control" % (r2_zi-r2_z))
print("  fitted law: sigma ~ z^%.2f * IR^%.2f" % (c[1], c[2]))

# does it actually work? held-out split by SPATIAL halves (different surfaces)
half = np.zeros(z.size, bool); half[:z.size//2]=True
tr, te = half[m], ~half[m]
A=np.c_[np.ones(L.size), Z, R]
cc,*_=np.linalg.lstsq(A[tr],L[tr],rcond=None)
pred=A[te]@cc
err=np.exp(pred)-np.exp(L[te])
print("\n--- held out on the other spatial half (%d px) ---" % te.sum())
print("  median |predicted sigma - actual| : %.3f mm" % np.median(np.abs(err)))
print("  median actual sigma               : %.3f mm" % np.median(np.exp(L[te])))
print("  median relative error             : %.1f%%" % (100*np.median(np.abs(err)/np.exp(L[te]))))
Ac=np.c_[np.ones(L.size), Z]
ccz,*_=np.linalg.lstsq(Ac[tr],L[tr],rcond=None)
errz=np.exp(Ac[te]@ccz)-np.exp(L[te])
print("  control (range only) rel. error   : %.1f%%" % (100*np.median(np.abs(errz)/np.exp(L[te]))))
print("\nVERDICT: %s" % ("IR CARRIES REAL INFORMATION about depth uncertainty"
      if (r2_zi-r2_z)>0.02 else "IR adds nothing beyond range -- idea DEAD"))
