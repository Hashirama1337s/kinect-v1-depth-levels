# Kinect v1 as a measuring instrument — the hidden depth lattice, the three noise populations, and what the Xbox 360 sensor can and cannot do

One Xbox 360 Kinect, measured like an instrument: every claim below comes with the script that produced it, the number, and its
status. Corrections are listed first. Single device, single host, one operator — published so that it can be contested.

## In plain words (v2)

- **Depth comes in rungs, not a smooth scale.** The SDK's millimetres hide an integer disparity lattice uniform in 1/z; between
  1 and 4 m a warmed-up sensor emits only **259** distinct values. A cold sensor seems to keep "finding" new ones — that is thermal
  drift, not information. (The v1 card below.)
- **"The noise" is three different populations** (measured at ~3 m; the split depends on range, v2.0.1). Per-pixel temporal noise has a median of **2.6 mm** but an RMS of **38 mm**:
  about half the pixels are **pinned** (1–3 mm, far below one rung), a quarter to a third **dither** between two adjacent rungs, and
  about **1 %** are **catastrophic** (edges, grazing angles, IR-absorbing surfaces) and carry **95 %** of the variance. Masking pixels
  whose temporal sigma exceeds 10 mm keeps ~73 % of a flat target and removes 99.4 % of the variance.
- **Averaging frames buys less than √N.** Depth noise is correlated in time, but part of that is slow drift: the raw integrated
  correlation time is 2.74 s, while after removing a 20 s trend the autocorrelation is only ~0.15 at lags 1–8 and gone by ~3 s
  (v2.0.1 correction). The short-range part is flat from lag 1 to 8, so it is not SDK frame smoothing.
- **It drifts while warming up.** +8.2 mm over the first 6 minutes at 2.5 m, settling to ~0.02 mm/min after about an hour.
- **Hidden capabilities, and hard limits.** `COLOR_RAW_BAYER` at 1280×960 is genuinely raw, linear, un-white-balanced sensor data;
  IR is 640×480 only and 10-bit (the low 6 bits are always zero); near mode and projector-off are **rejected** on Xbox hardware
  (`0x8301000F`, a Kinect-for-Windows hardware gate — a checkbox in Microsoft's sample UI is not evidence the hardware can do it);
  the near limit is exactly **801 mm**.
- **First accuracy check (lateral).** A box face of 330.2 mm (hand tape) reads **319 ± 3.5 mm** — a repeatable **−3.4 %** — at
  0.8–1.0 m with the SDK's nominal focal length. Cause not yet separated (see below).

## Corrections (read first)

- **v2.0.1 (same evening) — the 2.74 s correlation time is qualified.** A 90 s capture of a still scene on a warmed sensor at ~1 m
  (`acf_gate.py`, rule fixed before looking): the raw autocorrelation is 0.58 / 0.52 / 0.38 / 0.24 at lags 1 / 8 / 30 / 90 frames, but
  after removing a 20 s moving mean it is only 0.16 / 0.13 / 0.08 / 0.02. Much of the published 2.74 s is slow drift leaking into
  the estimator; a smaller genuinely correlated component remains (flat from lag 1 to 8, gone by ~3 s). Quote the detrended curve.
- **v2.0.1 — the noise-population split is range-dependent.** The pinned / dithering / catastrophic numbers were measured at a median
  range of 2.9 m, where one lattice step is ~25 mm. At ~1 m (step ~3 mm) 94 % of valid pixels visit three or more values in 90 s,
  so "about half the pixels are pinned" holds only where the step is large compared with the noise.
- **Retracted: "averaging beats quantisation 12.5×".** That came from an interleaved split-half, valid only for white noise. With
  consecutive blocks the honest gain is **~1.8×** (about 6 mm at N = 180). Never quote precision from an interleaved split.
- **Withdrawn: the word "accuracy" for plane-fit results.** A plane fitted over many pixels is a spatial estimator, not point
  accuracy. The first real accuracy measurement is the lateral width test in v2 (below), and it is still single-target.
- **Arithmetic fix:** the uniform-rounding floor for the lattice residual is 0.0145 grid units (the std of U(−½, ½) is 0.2887, not
  0.5); the observed 0.0154 sits just above it. The v1 card below already uses the corrected numbers.
- **Not a discovery:** the quantisation law itself is textbook (Khoshelham & Oude Elberink 2012). What is ours is recovering the lattice
  from the SDK's cooked millimetre output, the warm/cold U(N) curve, the noise populations, the correlation time and the capability map.

## Findings added in v2 (status · script)

| finding | number | status | script |
|---|---|---|---|
| three noise populations; σ > 10 mm mask | median 2.62 mm, RMS 38.06 mm; worst 1 % = 94.9 % of variance (median range 2.9 m) | HOLDS at ~3 m; range-dependent (v2.0.1) | `analyse_sigma.py`, `sigma_n.py` |
| per-pixel σ predicted by range alone | σ ∝ z^1.80, R² 0.574, held-out median rel. error 25.8 % | HOLDS | `predictor.py` |
| the IR image does not predict σ | +0.0027 R² over range alone | NEGATIVE (the control was the result) | `predictor.py` |
| temporal correlation | raw τ_int = 84.9 frames = 2.74 s, but detrended (20 s) ACF only 0.16 → 0.02 over 1–90 frames | QUALIFIED (v2.0.1: drift inflates the raw figure) | `correlated.py`, `neff.py`, `acf_gate.py` |
| warm-up drift | +8.17 mm / 6 min at 2.5 m → +0.02 mm/min by ~70 min; one unexplained ~4 mm excursion | HOLDS / OPEN | `drift.py`, `warmup.py` |
| raw Bayer 1280×960 | genuinely raw (lag-2 > lag-1 autocorrelation, 12.9 % phase-mean spread) | HOLDS | `bayer.py` |
| stream capability map | 10 of 28 (type, resolution) pairs open; no 1280×960 IR | HOLDS | `capmap.py` |
| IR is 10-bit | GCD of all values = 64 (1014 levels) | HOLDS | `ir.py` |
| near mode / projector off | both rejected, `0x8301000F` | NEGATIVE (hardware gate) | `nearmode.py`, `ir_off.py` |
| lateral scale, known-width target | 318.3 / 322.7 / 315.9 mm vs 330.2 mm at 0.81 / 0.97 / 1.03 m (f = 571.26 px) | OPEN: focal-length error (~552 px) vs ~4 px edge loss per side vs tape error | `box_width.py` |

Numbers for the noise populations were measured on static scenes; the confidence keep-rate is scene-dependent (38–48 % on real rooms
vs 73 % on a flat target), so never quote 73 % as a sensor property.

## Tools

- `nui.py` — a direct ctypes binding to `Kinect10.dll` (SDK 1.8): all 25 exports are plain x64 C symbols, struct sizes asserted at import.
- `sensor.py` — the `INuiSensor` COM interface (37 vtable slots, indices from the SDK's own `NuiSensor.h`), gated by a `verify()`.
  ⚠ The COM and flat APIs have **different signatures for the same function**: `NuiImageStreamGetNextFrame` takes a pointer-to-pointer
  in the flat API but a caller-allocated struct in COM; mixing them overwrites memory. `NuiInitialize` must come before accelerometer
  or emitter calls.
- `viewer.py` — a live instrument panel (tkinter + pillow): depth, IR, raw Bayer, confidence, live σ, and **LATTICE**, which colours each
  pixel by its disparity rung — a live contour map where one band is one quantisation step (2.35 mm at 0.9 m, 26 mm at 3 m).
- `first_contact.py` — a 5-frame smoke test.

Setup: Kinect for Windows SDK 1.8 (driver), the sensor on a **root-hub** USB port (not behind an external hub), Python 3 with numpy
(the viewer also uses pillow). Run every script from this folder.

---

## The v1 card: how many distinct depths does it actually produce?
A single-operator measurement on one named Xbox 360 Kinect, with the scripts, the raw curve,
the failed controls, and the criteria that would prove it wrong.

**Short version:** the sensor's realisable depth values form a lattice that is uniform in 1/z,
and in the 1–4 m band a **thermally settled** sensor emits exactly **259** distinct values —
invariant from the first frame to the hundred-thousandth. A **cold** sensor appears to keep
finding new levels for as long as you watch. That difference is not the sensor discovering
anything; it is thermal drift dragging the scene across the lattice and manufacturing levels
that are not realisable at equilibrium. **Warm-up state is a confound for level counting, and we
have not seen it stated anywhere.**

---


## In plain words

A Kinect doesn't measure distance smoothly. It projects a pattern of infrared dots, measures
how far each dot has shifted, and stores that shift as a whole number. Whole numbers only — so
the sensor can report distances from a fixed ladder of rungs and nothing in between. Because of
the geometry, the rungs are millimetres apart up close and centimetres apart far away.

This card answers one question and gives you everything you need to check it yourself:

> **Across its working range, how many distinct depth values does the sensor actually produce —
> and does that number ever stop growing?**

Measured here: **259** distinct values between 1 and 4 metres once the sensor is thermally settled (flat from the
first frame to the hundred-thousandth); a cold, warming sensor appears to keep adding levels (see *The claim*).
(v1 of this card said "at least 257 and still climbing" here — that was the cold-sensor run; corrected in v2.) The folklore number is 2048 (11-bit
disparity), or 1024 "usable". The realisable count is neither, and it is not a single number:
it depends on how long you look.

## The claim, stated precisely

1. Depth is quantised on a lattice that is **uniform in 1/z**, not in z — the signature of a
   structured-light triangulation sensor rather than a time-of-flight one.
2. Between 863 mm and 3975 mm, accumulating over 200 frames, **266 distinct millimetre values**
   appear. Restricted to 1000-4000 mm the count is **259**.
3. The quantisation step follows `Δz = z² / (f·b/Δd)` with `f·b/Δd = 345,316 px·mm`:

       z (mm)     1000   1500   2000   2500   3000   3500
       observed    3.00   6.00  11.50  18.00  26.00  35.00
       predicted   2.89   6.50  11.56  18.06  26.01  35.40

   The 3.00 mm step at 1 m agrees with the published Kinect v1 figure (~3 mm at 1 m).
4. Implied baseline **73.79 mm** at f = 585 px, against 75 mm nominal (ratio 0.984).

## What this card does NOT claim — read this before objecting

The figure **0.25 mm** appears in the underlying findings and is **not a quantisation step**.
It is the *held-out prediction error of the fitted lattice model*: fit the grid on far levels
only (z > 2000 mm, n = 86), then predict the 180 near levels the fit never saw — median error
0.25 mm, max 0.58 mm, against a device that outputs integer millimetres (so rounding alone
permits 0.5 mm). It is a model residual sitting at the rounding floor. Anyone comparing it to
the ~3 mm/m quantisation step is comparing two different measurands.

## Hardware

| item | value |
|---|---|
| sensor | Xbox 360 Kinect, PrimeSense PS1080, structured light |
| camera serial | `A00365W07067202A` |
| host | Windows 11, AMD xHCI |
| **USB topology** | **root-hub port, NOT behind an external hub** |

⚠ **The USB topology is load-bearing.** Behind a Renesas `VID_0409` external hub the Kinect is
starved of isochronous bandwidth. Symptom: motor and audio enumerate, camera does not. This was
first misdiagnosed here as a missing 12 V supply — power was fine the whole time. If your camera
interface will not come up, move to a root-hub port before you suspect anything else.

## Software

- **Kinect for Windows SDK 1.8** installed (driver only).
- Access via `nui.py` — a direct ctypes binding to `Kinect10.dll`. All 25 exports are
  undecorated x64 C symbols, so no wrapper library is required. Struct layouts are asserted
  against known `sizeof` at import, so a wrong offset fails loudly instead of returning
  plausible garbage.
- No libfreenect, no OpenNI, no ROS.

⚠ **The bit shift is load-bearing.** `NUI_IMAGE_TYPE_DEPTH` returns `uint16` where millimetres
live in **bits 3-15** (`NUI_IMAGE_PLAYER_INDEX_SHIFT = 3`) — **even when no player-index stream
is open.** Read the raw value as millimetres and every number is wrong by a factor of eight.
Any replication that skips `>> 3` will not reproduce this card.

## Protocol

1. Kinect on a root-hub port. Open `IMG_DEPTH` at `RES_640x480`.
2. Settle 1.0 s after opening the stream.
3. Grab **200 frames** (`timeout_ms = 3000`), scene static.
4. For each frame: `mm = (raw >> 3)`, discard zeros (invalid/shadow), accumulate
   `set(np.unique(mm))` across all frames.
5. Report `len(set)` — this is the cardinality — and the sorted level list for lattice fitting.

**Definition of "a distinct depth":** a unique integer millimetre value returned by the SDK
after the 3-bit shift, with zero excluded, pooled over all frames and all pixels. Not a raw
disparity code (not exposed by this API); not a rounded or binned value.

## Controls, including the two that failed

The first control compared the coefficient of variation of gaps in `z` against gaps in `1/z`.
It returned **the wrong answer** (CV 1.03 vs 2.50, apparently favouring the null) while gap
predictions were matching theory to ~1%. Cause: integer-millimetre rounding merges adjacent
disparity levels, and a dropped level becomes a doubled gap — an outlier that destroys a CV
statistic.

The second version was still inconclusive (ratio 0.825) for a different reason: at 863 mm the
mm-rounding noise floor is 0.23 grid units against the null's 0.289. **Near levels cannot
discriminate at all**, so including them guaranteed a null. Restricting to z > 2000 mm, where
the floor falls to 0.025, separated the hypotheses immediately.

**Two controls, two instrument faults, before the real signal was visible.** Both are reported
here because a replication that hits either will otherwise conclude the effect is absent.

The surviving test: fit the uniform grid in 1/z on far levels, measure residuals in grid units.

    observed residual std   0.0154 grid units
    null (uniform in z)     0.2887          -> 19x tighter
    mm-rounding floor       0.0145          -> observed sits just above it (ratio 1.065)

The null is a real alternative making the opposite prediction, so the test **can** fail.

## What would falsify this

- A replication on the same hardware and driver reporting cardinality outside roughly 200-350
  over 1-4 m under this protocol.
- Residual std near 0.2887 rather than ~0.015 — that would say the lattice is uniform in z and
  the structured-light model is wrong for this device.
- A demonstration that the accumulated set is dominated by frame count rather than physics —
  i.e. cardinality still climbing steeply at 200 frames. (Sweep frame count and show the curve
  flattening; if it does not, this number is a floor, not a census.)
- Any published prior census of realisable depth levels for this sensor. That would make this a
  replication rather than a measurement, which is still worth knowing.

## Replicate it

    python quantisation.py   accumulate levels, gap analysis vs both models
    python lattice_test.py   the corrected grid-residual test (use this one)
    python sweep_un.py / sweep_un2.py   the U(N) curve (to 10^4 / 10^5 frames, with the confound control)

Both scripts contain their hypothesis and control in the docstring. `lattice_test.py` supersedes
the CV formulation in `quantisation.py` for the reasons in the controls section above.

## What is ours and what is not

**Not ours — cite, do not rediscover:**
- The depth **quantisation law** (Δz ∝ z², step-vs-range curves): Khoshelham & Oude Elberink,
  *Sensors* 12(2):1437-1454, 2012, doi:10.3390/s120201437; Boehm, *PFG* 2/2014:117-127.
- The **unique-depths → ΔZ method**: Smíšek, CTU-CMP-2011-06 / ICCV Workshops 2011.
- **Δd = ⅛ px**: established by Konolige & Mihelich's ROS `kinect_calibration/technical`
  reverse-engineering, restated in Sarbolandi et al., arXiv:1505.05459. **Microsoft does not
  document ⅛ anywhere** — do not cite them for it.
- **Millimetre-LUT level drops**: Andersen et al., Aarhus ECE-TR-6, 2012, §3.

Our steps at 1.0-3.5 m reproduce the published law to ~1%. That reproduction is a **check on the
rig**, not a discovery.

**Ours, offered as new:**
- the **U(N) curve** for the realisable level set, to 100,000 frames, warm and cold;
- the finding that it is **invariant at 259 when settled** and **spuriously increasing when
  warming** — so any published cardinality without a stated thermal state is uninterpretable;
- the two **failed controls**, with protocols, as labelled negative results;
- all of it on a **named unit** (serial, driver, mode, USB topology) so it can be contested.

**A detector bug of ours, recorded because it nearly inverted the conclusion:** the drift control
compared the *first* patch reading against the *last* and reported "CONFOUNDED" on a run that was
stationary for 50,000 frames and moved only at the final checkpoint. An endpoint comparison cannot
distinguish slow drift from a discrete scene change. Stability must be checked across the whole
series, not at its ends.

**Known tension to resolve:** a 2014 blog (Byte Kitchen) asserts 345 unique depths for
Kinect-for-Windows default range and 781 for an Xbox unit, without stating accumulation
protocol or frame count. Our U_all = 343 at N = 10,000 sits beside their 345; their 781 does
not. Without their N, the numbers are not comparable — which is precisely the point this card
is making.

## Status

`LAB-CLAIMED`. Single device, single host, single driver stack, one operator, one static scene.
Not independently replicated. Published so that it can be.


## Cite

See `CITATION.cff`. Licence: MIT (`LICENSE`). By Moki&Julio.
