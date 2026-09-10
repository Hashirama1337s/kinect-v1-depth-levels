# Kinect v1 — how many distinct depths does it actually produce?

A single-operator measurement on one named Xbox 360 Kinect, with the scripts, the raw curve,
the failed controls, and the criteria that would prove it wrong.

**Short version:** the sensor's realisable depth values form a lattice that is uniform in 1/z,
and the number of distinct values you can observe **keeps growing the longer you look** — so any
published count is a floor conditioned on run length, not a property of the device. We ran it to
10,000 frames and it had not saturated.

---


## In plain words

A Kinect doesn't measure distance smoothly. It projects a pattern of infrared dots, measures
how far each dot has shifted, and stores that shift as a whole number. Whole numbers only — so
the sensor can report distances from a fixed ladder of rungs and nothing in between. Because of
the geometry, the rungs are millimetres apart up close and centimetres apart far away.

This card answers one question and gives you everything you need to check it yourself:

> **Across its working range, how many distinct depth values does the sensor actually produce —
> and does that number ever stop growing?**

Measured here: **at least 257** between 1 and 4 metres, after ten thousand frames — and the
count was **still slowly climbing** when we stopped. The folklore number is 2048 (11-bit
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

    D:\_LIVE\KINECT\quantisation.py   accumulate levels, gap analysis vs both models
    D:\_LIVE\KINECT\lattice_test.py   the corrected grid-residual test (use this one)

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
- the **U(N) growth curve** for the realisable level set, to 10,000 frames;
- the resulting statement that the set **does not saturate** at that scale, so published
  cardinalities are floors conditioned on run length;
- the two **failed controls**, with protocols, as labelled negative results;
- all of it on a **named unit** (serial, driver, mode, USB topology) so it can be contested.

**Known tension to resolve:** a 2014 blog (Byte Kitchen) asserts 345 unique depths for
Kinect-for-Windows default range and 781 for an Xbox unit, without stating accumulation
protocol or frame count. Our U_all = 343 at N = 10,000 sits beside their 345; their 781 does
not. Without their N, the numbers are not comparable — which is precisely the point this card
is making.

## Status

`LAB-CLAIMED`. Single device, single host, single driver stack, one operator, one static scene.
Not independently replicated. Published so that it can be.
