"""
KINECT INSTRUMENT PANEL

Not a demo viewer. Shows what our own measurements found and stock viewers do not:
the quantisation shells, live per-pixel stability, and the confidence mask that
removes 99.4% of the variance while keeping 72.6% of the pixels.

KEYS
  1  DEPTH       colourised range
  2  IR          10-bit infrared, correctly unpacked (low 6 bits are structurally zero)
  3  BAYER       1280x960 un-demosaiced GRBG mosaic (on-chip white-balance gain; see README)
  4  CONFIDENCE  green = sigma<=10mm (keep) / red = masked
  5  STABILITY   live per-pixel temporal sigma, rolling 60-frame window
  6  LATTICE     which disparity level each pixel sits on -- the shells, made visible
  M  toggle the confidence mask on DEPTH
  S  save PNG      R  reset rolling buffer      Q / Esc  quit
  click a pixel to probe it
"""
import sys, time, os
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import numpy as np
import nui
import tkinter as tk
from PIL import Image, ImageTk
from matplotlib import colormaps

SHIFT      = 3
STEP       = 0.1042 / 36000.0 # 1/mm, exact disparity step of PrimeSense's shift-to-depth table (lattice_closure.py)
INTERCEPT  = 1.0 / 1200.0     # 1/mm, the 1200 mm reference plane is rung 0 (v2.1: were the fitted 2.895897e-06 / 4.977113e-04)
SIGMA_GATE = 10.0             # mm; masking above this drops 99.4% of variance (README, noise populations)
WIN        = 60
Z_LO, Z_HI = 500.0, 4000.0
NAMES = {1: "DEPTH", 2: "IR", 3: "BAYER", 4: "CONFIDENCE", 5: "STABILITY", 6: "LATTICE"}


def make_lut(name):
    c = colormaps[name](np.linspace(0, 1, 256))[:, :3]
    return (c * 255).astype(np.uint8)


LUT_D, LUT_S, LUT_I = make_lut('turbo'), make_lut('inferno'), make_lut('magma')


def apply_lut(norm, table, invalid=None):
    idx = np.clip(norm * 255.0, 0, 255).astype(np.uint8)
    rgb = table[idx]
    if invalid is not None:
        rgb[invalid] = (25, 25, 30)
    return rgb


class Panel:
    def __init__(self):
        self.mode = 1
        self.pending = None
        self.mask_on = False
        self.buf = []
        self.probe = None
        self.k = None
        self.stream = None
        self.times = []
        self.note = ""
        self.rgb = None
        self._open(1)

        self.root = tk.Tk()
        self.root.title("Kinect Instrument Panel")
        self.root.configure(bg="#111111")
        self.lbl = tk.Label(self.root, bg="#111111")
        self.lbl.pack()
        self.info = tk.Label(self.root, bg="#111111", fg="#dddddd",
                             font=("Consolas", 10), justify="left", anchor="w")
        self.info.pack(fill="x", padx=8, pady=(4, 2))
        tk.Label(self.root, bg="#111111", fg="#777777", font=("Consolas", 9),
                 text="1 depth  2 IR  3 bayer  4 confidence  5 stability  6 lattice   "
                      "M mask  S save  R reset  Q quit   (click to probe)"
                 ).pack(fill="x", padx=8, pady=(0, 6))
        self.root.bind("<Key>", self.key)
        self.lbl.bind("<Button-1>", self.click)
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.root.after(50, self.tick)

    # IR and BAYER need a different NuiInitialize, so reopen the sensor on switch
    def _open(self, group):
        if self.k is not None:
            try:
                self.k.close()
            except Exception:
                pass
            time.sleep(0.35)
        if group == 2:
            self.k = nui.Kinect(nui.INIT_DEPTH | nui.INIT_COLOR)
            self.stream = (nui.IMG_COLOR_INFRARED, nui.RES_640x480, np.uint16)
        elif group == 3:
            self.k = nui.Kinect(nui.INIT_DEPTH | nui.INIT_COLOR)
            self.stream = (nui.IMG_COLOR_RAW_BAYER, nui.RES_1280x960, np.uint8)
        else:
            self.k = nui.Kinect(nui.INIT_DEPTH)
            self.stream = (nui.IMG_DEPTH, nui.RES_640x480, np.uint16)
        self.k.open_stream(self.stream[0], self.stream[1])
        time.sleep(0.6)

    @staticmethod
    def group_of(mode):
        return 2 if mode == 2 else (3 if mode == 3 else 1)

    def key(self, e):
        c = (e.char or "").lower()
        if c in "123456":
            m = int(c)
            if self.group_of(m) != self.group_of(self.mode):
                self.pending = m
            self.mode = m
        elif c == "m":
            self.mask_on = not self.mask_on
        elif c == "r":
            self.buf = []
        elif c == "s":
            self.save()
        elif c == "q" or e.keysym == "Escape":
            self.quit()

    def click(self, e):
        self.probe = (e.x, e.y)

    def quit(self):
        try:
            self.k.close()
        except Exception:
            pass
        self.root.destroy()

    def save(self):
        if self.rgb is not None:
            fn = time.strftime(r"shot_%Y%m%d_%H%M%S.png")
            Image.fromarray(self.rgb).save(fn)
            self.note = "saved " + os.path.basename(fn)

    def live_sigma(self, z):
        self.buf.append(z)
        if len(self.buf) > WIN:
            self.buf.pop(0)
        if len(self.buf) < 8:
            return None
        st = np.stack(self.buf)
        ok = (st > 0).all(0)
        return np.where(ok, st.std(0), np.nan)

    def tick(self):
        if self.pending is not None:
            m, self.pending = self.pending, None
            try:
                self._open(self.group_of(m))
                self.buf = []
            except Exception as ex:
                self.note = "stream switch failed: %s" % ex
        try:
            arr, fnum, _ = self.k.grab(self.stream[0], timeout_ms=800,
                                       dtype=self.stream[2])
        except OSError:
            self.root.after(5, self.tick)
            return

        now = time.time()
        self.times.append(now)
        self.times = [t for t in self.times if now - t < 2.0]
        fps = (len(self.times) / (now - self.times[0])) if len(self.times) > 1 else 0.0

        m = self.mode
        extra = ""

        if m == 3:
            g = arr.astype(np.float32)
            g = 255.0 * (g - g.min()) / max(float(g.max() - g.min()), 1.0)
            rgb = np.dstack([g, g, g]).astype(np.uint8)
            rgb = np.array(Image.fromarray(rgb).resize((960, 720), Image.BILINEAR))
            extra = "raw Bayer 1280x960, undebayered   8-bit   range %d..%d" % (arr.min(), arr.max())

        elif m == 2:
            ir = (arr >> 6).astype(np.float32)          # 10-bit payload
            n = np.clip(ir / max(float(np.percentile(ir, 99.5)), 1.0), 0, 1)
            rgb = apply_lut(n, LUT_I)
            extra = "IR 10-bit   distinct levels %d   peak %d/1023" % (
                len(np.unique(arr)), int(ir.max()))

        else:
            z = (arr >> SHIFT).astype(np.float32)
            bad = z <= 0
            sig = self.live_sigma(z)

            if m == 1:
                n = np.clip((z - Z_LO) / (Z_HI - Z_LO), 0, 1)
                rgb = apply_lut(1.0 - n, LUT_D, bad)
                if self.mask_on and sig is not None:
                    rgb[np.nan_to_num(sig, nan=1e9) > SIGMA_GATE] = (70, 0, 0)
                # NEAR-EDGE READOUT: nearest valid depth in the centre box.
                # Move an object slowly AWAY until depth appears; this reads the
                # distance at which it switched on (the packed stream's floor is the SDK's 800 mm clamp: 801 mm).
                h, w = z.shape
                cy, cx = h // 2, w // 2
                box = z[cy - 80:cy + 80, cx - 80:cx + 80]
                v = box[box > 0]
                near = ("%.0f mm" % v.min()) if v.size > 40 else "-- none --"
                cover = 100.0 * (v.size / box.size)
                extra = ("depth %.0f-%.0f mm   mask %s\n"
                         "CENTRE BOX: nearest valid %s   coverage %.0f%%" %
                         (Z_LO, Z_HI, "ON" if self.mask_on else "off", near, cover))
                rgb[cy - 80, cx - 80:cx + 80] = (255, 255, 255)
                rgb[cy + 79, cx - 80:cx + 80] = (255, 255, 255)
                rgb[cy - 80:cy + 80, cx - 80] = (255, 255, 255)
                rgb[cy - 80:cy + 80, cx + 79] = (255, 255, 255)

            elif m == 4:
                rgb = np.zeros(z.shape + (3,), np.uint8)
                if sig is None:
                    extra = "confidence -- filling buffer (%d/8)" % len(self.buf)
                else:
                    keep = np.nan_to_num(sig, nan=1e9) <= SIGMA_GATE
                    rgb[keep & ~bad] = (30, 190, 90)
                    rgb[~keep & ~bad] = (200, 40, 40)
                    pct = 100.0 * keep[~bad].mean() if (~bad).any() else 0.0
                    extra = "confidence   sigma <= %.0f mm : %.1f%% of valid pixels kept" % (
                        SIGMA_GATE, pct)

            elif m == 5:
                if sig is None:
                    rgb = np.zeros(z.shape + (3,), np.uint8)
                    extra = "stability -- filling buffer (%d/8)" % len(self.buf)
                else:
                    n = np.clip(np.nan_to_num(sig, nan=0.0) / 25.0, 0, 1)
                    rgb = apply_lut(n, LUT_S, bad | ~np.isfinite(sig))
                    v = sig[np.isfinite(sig)]
                    if v.size:
                        extra = "live sigma over %d frames   median %.2f mm   p95 %.1f mm" % (
                            len(self.buf), np.median(v), np.percentile(v, 95))

            else:  # 6 LATTICE
                with np.errstate(divide='ignore', invalid='ignore'):
                    lvl = (INTERCEPT - 1.0 / np.where(z > 0, z + 0.5, np.nan)) / STEP   # z is floored: use the bin centre
                band = np.mod(np.round(np.nan_to_num(lvl, nan=0.0)), 6) / 5.0
                rgb = apply_lut(band, LUT_D, bad)
                fin = np.isfinite(lvl)
                if fin.any():
                    a, b = np.nanmin(lvl[fin]), np.nanmax(lvl[fin])
                    extra = "disparity level index   %d..%d   (%d shells in view)" % (
                        int(a), int(b), int(b - a) + 1)

            if self.probe is not None:
                px, py = self.probe
                if 0 <= py < z.shape[0] and 0 <= px < z.shape[1]:
                    if z[py, px] > 0:
                        zz = float(z[py, px])
                        lv = (INTERCEPT - 1.0 / (zz + 0.5)) / STEP
                        ss = ("%.2f mm" % sig[py, px]) if (
                            sig is not None and np.isfinite(sig[py, px])) else "n/a"
                        extra += ("\nprobe (%d,%d)  z=%.0f mm  level=%.1f  "
                                  "step here=%.2f mm  sigma=%s" % (px, py, zz, lv,
                                                                   zz * zz * STEP, ss))
                    rgb[max(py - 6, 0):py + 7, px] = (255, 255, 255)
                    rgb[py, max(px - 6, 0):px + 7] = (255, 255, 255)

        self.rgb = rgb
        self.tkimg = ImageTk.PhotoImage(Image.fromarray(rgb))
        self.lbl.configure(image=self.tkimg)
        if self.note:
            extra += "   [%s]" % self.note
        self.info.configure(text="[%s]  %4.1f fps  frame %d\n%s" % (
            NAMES[m], fps, fnum, extra))
        self.root.after(1, self.tick)


if __name__ == "__main__":
    Panel().root.mainloop()
