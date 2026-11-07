# Kinect v1 as a measuring instrument — the depth lattice, the three noise populations, and what the Xbox 360 sensor can and cannot do

One Xbox 360 Kinect, measured like an instrument: every claim below comes with the script that produced it, the number, and its
status. Corrections are listed first. Single device, single host, one operator — published so that it can be contested.

Status labels used throughout: **HOLDS** (reproduced by its script and survives the checks listed) · **QUALIFIED** (holds only with the
stated restriction) · **RETRACTED** (withdrawn) · **NEGATIVE** (looked for and absent, or a feature the sensor refuses) · **NO VERDICT**
(the rule fixed in advance did not decide) · **OPEN** (observed, but not yet tested by a rule fixed in advance).

## In plain words (v2.1)

- **Depth comes in rungs, not a smooth scale.** The SDK's millimetre output is exactly PrimeSense's published shift-to-depth table,
  so between 1 and 4 m it can take only **259** values (345 in the SDK's 0.8–4 m window). How many of them a capture shows depends on
  how much of the range the scene covers. A drifting (warming) sensor sweeps surfaces across rungs and fills them in faster, but no
  capture, warm or cold, has produced a value outside the table. (v2.1: the earlier "cold sensor manufactures levels" story is
  retracted; see Corrections.)
- **The SDK and the open-source drivers use the same table at different phases.** Microsoft's SDK evaluates the formula at phase 0;
  libfreenect and OpenNI subtract a constant 0.375 that puts theirs at phase 0.5. Their millimetre value sets therefore interleave by
  half a rung. This is a verification of a public formula, plus a mechanism for a driver difference first reported in 2015.
- **"The noise" is three different populations** (measured at ~3 m; the split depends on range, v2.0.1). Per-pixel temporal noise has a
  median of **2.6 mm** but an RMS of **38 mm**: about half the pixels are **pinned** (1–3 mm, far below one rung), a quarter to a third
  **dither** between two adjacent rungs, and about **1 %** are **catastrophic** (edges, grazing angles, IR-absorbing surfaces) and carry
  **95 %** of the variance. Masking pixels whose temporal sigma exceeds 10 mm keeps ~73 % of a flat target and removes 99.4 % of the
  variance.
- **Averaging frames buys less than √N.** Depth noise is correlated in time, but part of that is slow drift: the raw integrated
  correlation time is 2.74 s, while after removing a 20 s trend the autocorrelation is only ~0.15 at lags 1–8 and gone by ~3 s
  (v2.0.1 correction). The short-range part is flat from lag 1 to 8, so it is not SDK frame smoothing. With consecutive blocks the
  averaging gain is ~1.8× at N = 180 frames.
- **It drifts while warming up.** +8.2 mm over the first 6 minutes at 2.5 m, settling to ~0.02 mm/min after about an hour. Warm-up
  drift is published prior art (credits under v2.1 corrections); what is ours is this unit's curve.
- **Lateral scale (corrected in v2.1).** Against a factory-sized reference (a US #10 envelope, 241.3 mm, on an IR-dark backing at
  1.27 m) the long side reads 242.4–245.5 mm, i.e. **+0.45 % to +1.74 %** depending on the focal length (575.82 or 571.26 px) and on
  which depth plane is used; a tape agrees to ~1 %. The sealed rule returned NO VERDICT (+1.74 % against a ±1.5 % bar), so the ~1 %
  reading is a post-hoc premise check. It is not short, and it is consistent with the published nominals. The earlier "−3.4 %" came
  from a box whose hand-tape reference was wrong.
- **Capabilities through SDK 1.8 on an Xbox 360 unit (mostly documented; confirmed here).**
  - `COLOR_RAW_BAYER` at 1280×960 (a documented SDK ≥ 1.6 format, labelled 12 fps) delivers **10.22 fps** and returns an
    un-demosaiced 8-bit **GRBG** mosaic after an **on-chip per-channel (white-balance) gain**; linearity is untested, and Microsoft
    states the 1280×960 colour data is compressed on the device, so it is not shown to be raw sensor data. The 640×480 Bayer is
    resampled in the sensor.
  - Through the SDK, IR is available only at 640×480 and is 10-bit (the low 6 bits are always zero); its largest code is 1019–1021,
    never 1023. The imager itself is 1280×1024, and libfreenect streams it at that size.
  - Near mode, projector-off and the colour-camera settings are all rejected on this Xbox 360 unit with `0x8301000F`
    (`E_NUI_HARDWARE_FEATURE_UNAVAILABLE` in the SDK header). For near mode and projector-off this is as Microsoft documents; for the
    colour-camera settings no restriction is documented.
  - The nearest value the packed depth stream reports is **801 mm**, the first lattice rung above the SDK's documented 800 mm floor;
    the farthest is 3975 mm, the last rung below 4000. This is the clamp and the lattice, not a hardware threshold: the extended-depth
    texture reports a real object at 573–799 mm on the same frames.
  - 13 of 28 (image type, resolution) pairs open. IR and depth run together; opening colour next to IR returns no error but silently
    turns the IR handle into something else.
  - The microphones are natively 4 channels at 16 kHz; the "2 channels, 48 kHz" that most tools show is the Windows shared-mode mix.
- **The SDK's calibration blob, read through documented calls.** The blob behind `GetColorToDepthRelationalParameters` contains the
  PrimeSense registration block that libfreenect reads from the device. The SDK uses it only for depth→colour registration (mirrored,
  and with the colour parallax frozen beyond 2047 mm). The SDK's 3-D coordinates ignore it: they use one nominal pinhole, so (as far as
  a one-unit test of the blob can show) every unit's SDK point cloud has the same focal length.

## Corrections (read first)

### v2.1 (2026-09-27)

- **RETRACTED: "a cold sensor manufactures levels that are not realisable at equilibrium".**
  - Every in-band value of the cold run (257) is among the settled run's 259, which are exactly the PrimeSense table; the cold set
    lacks only 1167 and 1212 and has no extras.
  - The two runs already differed at N = 1 (170 vs 259 values), which drift cannot cause: they covered different parts of the range.
  - The settled run's all-range count also kept rising (260 → 345 by N = 50,000) and stopped at exactly the table's 345 rungs in
    800–4000 mm.
  - U(N) measures scene coverage. Drift speeds coverage up but adds no new values.
  - Withdrawn: "warm-up state is a confound for level counting", "we have not seen it stated anywhere" and "any published
    cardinality without a stated thermal state is uninterpretable". A cardinality needs its range window and scene coverage stated.
  - Credit: the Byte Kitchen blog (M. Drossaers, "A Jitter Filter for the Kinect", 2014-03-17) had already reported **345** different
    depth values in the SDK's default range as a stable set, with the table. Our count replicates that census.
  - Scripts: `lattice_closure.py`, `sweep_un.py`, `sweep_un2.py`; data `results_un_sweep.json` (cold), `results_un_sweep_1e5.json`
    (settled).
- **CORRECTED: "first accuracy check, −3.4 % narrow".** The box's hand-tape reference, not the sensor, was wrong.
  - A factory-sized US #10 envelope reads +0.45 % to +1.74 % (`envelope_scale.py`; rule sealed in `envelope_prediction.json`). By
    its sealed rule that is strictly **NO VERDICT** (+1.74 % against a ±1.5 % bar). It is not short, and it is consistent with the
    SDK's published nominals (58.5° × 45.6°, f = 285.63 px at 320×240). A #10 envelope is itself only good to about 1 %.
  - The rotation test agrees (`rot_test.py`): the same box side reads differently horizontally and vertically in a way that follows
    the box's sides, not the image axes, so the discrepancy is in the box or its tape numbers, and the sensor's horizontal and vertical
    scales agree to within ~2 %.
  - Prior art: Kreylos ("Kinect factory calibration", doc-ok.org, 2013-01-26) found that the factory calibration reads a precise
    target 1.5–2.8 % oversize (RMS 2.19 %). Published depth focal lengths span 571–598 px (SDK nominal 571.26; ROS 580;
    Smíšek et al. 585.6; Burrus 594/591).
- **CORRECTED: "the near limit is exactly 801 mm".** 801 mm is the first lattice rung above the SDK's documented 800 mm clamp
  (`NUI_IMAGE_DEPTH_MINIMUM`); 799 and 801 are rungs, 800 is not. The far end, 3975 mm, is likewise the last rung below 4000.
  Scripts: `lattice_closure.py`, `atlas/depth_flags_probe.py`.
- **SUPERSEDED: v1-card points 3 and 4** (fitted K = 345,316 px·mm; "implied baseline 73.79 mm at f = 585 px, ratio 0.984"). The exact
  table fixes K = f·b/Δd = 36000/0.1042 = **345,489 px·mm**: PrimeSense's own constants (b = 75 mm, f = 575.8 px at 640×480,
  Δd = ⅛ px). The fitted value was 0.05 % low and reproduces only 96.2 % of the observed values; the 1.6 % "baseline deficit" came from
  pairing the slope with f = 585 px. The 0.25 mm held-out residual is superseded too: the exact table reproduces every value with zero
  error. (`lattice_closure.py`)
- **CORRECTED: "`COLOR_RAW_BAYER` at 1280×960 is genuinely raw, linear, un-white-balanced sensor data".**
  - What holds: an un-demosaiced 8-bit mosaic, pattern **GRBG** in SDK frames ((0,0) G, (0,1) R, (1,0) B, (1,1) G; sealed bar passed
    at 640, and at 1280 for G, R, G, with blue noise-limited). At 1280 its temporal noise is pixel-independent and shows no block
    grid, so no trace of the compression Microsoft describes shows at our sensitivity; that does not prove rawness.
  - Not un-white-balanced: at matched signal blue sites carry 2.2–5× the noise SD of green sites, so a per-channel gain is applied
    on the chip before the output (exploratory). The host adds none: COLOR 640 equals RAW_BAYER 640 at native sites (slope 0.99).
  - Linearity: untested (no verdict in dim light). `bayer.py` only showed a mosaic; a re-mosaiced image would pass it too.
  - Frame rate: **10.22–10.23 fps** by SDK timestamps (4 live sessions, 8 archived captures), not the documented 12.
  - The 640×480 Bayer is resampled in the sensor (same-colour neighbours 2 px apart are noise-correlated 0.13–0.14), so use 1280×960
    for photometry.
  - Microsoft's Color Stream page states that the 1280×960 data "is compressed and converted to RGB before transmission"; the
    format itself is documented since SDK 1.6.
  - Scripts: `atlas/colour_probe.py`, `atlas/colour_offline.py`, `atlas/colour_offline2.py`, `atlas/colour_ptc.py`.
- **CORRECTED: the capability map is 13 of 28, not 10.** `DEPTH_AND_PLAYER_INDEX` opens at 640×480, 320×240 and 80×60 when initialised
  with its own flag and skeleton tracking (1280×960 is refused). v2.0 had initialised with `INIT_DEPTH` only. (`capmap.py`,
  `atlas/player_index_probe.py`, `atlas/pi_1280_check.py`)
- **CORRECTED: `sensor.py` docstring.** It said projector-off "makes the IR camera a passive 830 nm NIR camera". On this unit
  projector-off is rejected (`0x8301000F`), as the README already said; the docstring now says so. `nui.py`'s depth-sentinel constants
  were also wrong (0xFFF9 / 0xFFF8 / 0xFFF7); the header values are 0x0000 / 0x7FF8 / 0xFFF8 (too near / too far / unknown). No script
  used them, so no result changes. (`atlas/depth_flags_probe.py`)
- **CORRECTED: the IR row cited the wrong script.** The 10-bit (GCD = 64) test is in `capmap.py`. `ir.py`'s 1280×960 "native or
  upscaled" test cannot run: the SDK refuses 1280×960 IR.
- **Missing credit added: warm-up drift.** Temperature and air-draft effects on Kinect v1 range: Fiedler & Müller, WDIA 2012 (LNCS
  7854, 2013). "At least one hour" of warm-up: Chow, Ang, Lichti & Teskey, ISPRS Archives XXXIX-B5 (2012), applied by Qi et al.,
  Sensors 2014. Warm-up under SDK 1.8: Sarbolandi, Lefloch & Kolb, CVIU 139 (2015) §4.4 (strong variation over the first ~10 min, then
  within 1 mm over 120 min). Temperature effects that differ by model (1414, 1473, Kinect for Windows): DiFilippo & Jouaneh, IEEE
  Sensors J. 15(8):4554–4564 (2015). Warm-up protocols: Choo et al., Sensors 14 (2014); Andersen et al., Aarhus ECE-TR-6 (2012,
  "transient response"). Our one-hour figure agrees with Chow 2012 and disagrees with Sarbolandi's ~10 min.
- **Missing credit added: noise models.** Compare Nguyen, Izadi & Lovell, 3DIMPVT 2012 (axial σ vs z and angle) and Choo et al. 2014
  (σ as a function of pixel position and z, with a radial term). Sarbolandi et al. 2015 §4.1 state that a per-pixel noise model is
  impossible under structured-light quantisation; our range-only predictor (R² 0.574) is a partial counterpoint, and it does not
  include pixel position (comparison OPEN).
- **AMENDED: what is ours.** Counting and tabulating the SDK's values was done before (Byte Kitchen 2014; Smíšek et al. 2011 for q(z)).
  What is ours: the identification of the SDK's value set with PrimeSense's formula at phase 0 and the driver phase mechanism, the
  noise populations, the correlation-time qualification, the SDK-blob usage map, and the capability confirmations.

**Corrections to unpublished working notes.** None of these reached a public file, but they circulated in our notes and are stated
here so that nobody repeats them:

- **WITHDRAWN as a sensor property: "depth outlines sit 0–3 px inside the IR outlines".** The SDK does not align depth to IR: depth
  content sits about 3–5 px right of and about 3 px above the IR content (`atlas/ir_depth_register.py`, `atlas/ir_depth_offset.py`;
  exploratory, one object). Outline positions cannot be compared until that offset is removed, and a signed four-edge test gave no
  verdict (`four_edges.py`).
- **"~38 000 dots in view" was not a count.** It was an area-per-nearest-neighbour estimate (640 × 480 / 2.83²), ~10 % high. The
  published figure is ~34.7 k bright spots (Reichinger, "Kinect Pattern Uncovered", 2011: 3 × 3 tiles of 3,861).
- **Audio: RETRACTED "2 channels" and the 2-channel direction-of-arrival demo.** The device is natively 4 ch / 16 kHz (24-bit data)
  and a plain WASAPI client gets all four in exclusive mode or in shared mode with the RAW option (`atlas/wasapi_probe.py`). The two
  channels we had recorded were the Windows audio engine's shared-mode mix (4 → 2 ch, 16 → 48 kHz), so their lag is not a
  microphone-pair delay; the direction-of-arrival figure from them is withdrawn.

### v2.0.1 (2026-09-26)

- **The 2.74 s correlation time is qualified.** A 90 s capture of a still scene on a warmed sensor at ~1 m (`acf_gate.py`, rule fixed
  before looking): the raw autocorrelation is 0.58 / 0.52 / 0.38 / 0.24 at lags 1 / 8 / 30 / 90 frames, but after removing a 20 s
  moving mean it is only 0.16 / 0.13 / 0.08 / 0.02. Much of the published 2.74 s is slow drift leaking into the estimator; a smaller
  genuinely correlated component remains (flat from lag 1 to 8, gone by ~3 s). Quote the detrended curve.
- **The noise-population split is range-dependent.** The pinned / dithering / catastrophic numbers were measured at a median range of
  2.9 m, where one lattice step is ~25 mm. At ~1 m (step ~3 mm) 94 % of valid pixels visit three or more values in 90 s, so "about
  half the pixels are pinned" holds only where the step is large compared with the noise.

### v2.0 (2026-09-26)

- **Retracted: "averaging beats quantisation 12.5×".** That came from an interleaved split-half, valid only for white noise. With
  consecutive blocks the honest gain is **~1.8×** (about 6 mm at N = 180). Never quote precision from an interleaved split.
- **Withdrawn: the word "accuracy" for plane-fit results.** A plane fitted over many pixels is a spatial estimator, not point accuracy.
  (v2.1: the lateral width test that v2.0 called the first real accuracy measurement is itself corrected above.)
- **Arithmetic fix:** the uniform-rounding floor for the lattice residual is 0.0145 grid units (the std of U(−½, ½) is 0.2887, not
  0.5); the observed 0.0154 sits just above it.
- **Not a discovery:** the quantisation law itself is textbook (Khoshelham & Oude Elberink 2012). (v2.1: the list of what is ours is
  amended above.)

## Findings added in v2.1 (status · script)

| finding | number | status | script |
|---|---|---|---|
| SDK depth table = PrimeSense's shift-to-depth formula | all 266 values this unit produced (863–3975 mm) reproduced with zero extras and **no fitted parameter**: z = floor(1/(1/1200 − n·D)), D = 0.1042/36000 mm⁻¹ | HOLDS — a verification: the formula is public (libfreenect `registration.c`, OpenNI `XnShiftToDepth`) | `lattice_closure.py`, `depth_lattice_values.json` |
| SDK vs libfreenect/OpenNI phase | SDK at phase 0; the open drivers' 0.375 puts them at phase 0.5 → the value sets interleave by half a rung | HOLDS for the value sets; QUALIFIED for the same-shift gap (see below) | `lattice_closure.py` |
| rung counts and range edges | 259 rungs in 1–4 m, 345 in 0.8–4 m (Byte Kitchen's 345); packed stream 801–3975 mm = first/last rung inside the 800–4000 mm clamp | HOLDS | `lattice_closure.py`, `results_un_sweep*.json` |
| SDK calibration blob, stage 1 (layout) | 12,604 bytes; contains the 118-byte PrimeSense registration block in libfreenect's `freenect_reg_info` order, float32 120.0 and 0.1042, int32 const_shift 200 | HOLDS | `blob_dump.py` |
| stage 2: SDK depth→colour registration vs PrimeSense's | sealed verdict **FAIL** (faithful port within ±1 px on 0–15 % of pixels); explained by a mirror and by the parallax shift being evaluated at min(z, 2047 mm); the SDK uses 2.4 cm | FAIL as sealed; the explanation HOLDS as a description and was confirmed predictively in stage 3 | `decode_stage2.py`, `stage2_results.json` |
| stage 3: what the blob drives | reg_info warp, zero-plane distance and pixel size move colour coordinates; const_shift, dx_center and both uint16 tables change nothing tested; **no edit moves any 3-D (skeleton) coordinate** | HOLDS | `decode_stage3.py`, `stage3_results.json` |
| SDK 3-D (skeleton) coordinates | nominal pinhole: f = 571.2653 px, centre (320, 240), Z = depth/1000, no distortion; the blob's 575.82 px is not used | HOLDS | `decode_stage3.py`, `atlas/mapper_vs_inline.py` |
| extended depth texture (SDK ≥ 1.6) | equals packed >> 3 on 100 % of in-range pixels; reports a real near object at **573–799 mm** below the clamp (flicker to 498); values beyond 4 m seen, but not from a real surface in a ≤ 3 m room | HOLDS for the values; accuracy OPEN; sealed on-table rule FAIL (94.0 %, 98.2 % after fixing our own table cap) | `atlas/extended_depth_probe.py`, `atlas/extended_followup.py` |
| extended depth wraps modulo 65,536 | the 5 off-table values equal rungs n = 283–287 (70–380 m) mod 65,536: 4858, 22872, 53275, 50014, 52867 (52869 predicted) | OPEN — a reported observation (post hoc, seen in two runs); confirmation run pending | `atlas/extended_depth_probe.py`, `atlas/extended_followup.py` |
| capability map | 13 of 28 pairs (v2.0: 10) | HOLDS | `capmap.py`, `atlas/player_index_probe.py` |
| colour-camera settings | `NuiGetColorCameraSettings` → `0x8301000F` in 9 of 9 sessions, so exposure, gain and white balance can be neither read nor set | NEGATIVE (hardware gate; not documented for this feature) | `atlas/colour_probe.py` |
| IR and depth together | 185/185 frames on each stream in 6 s | HOLDS | `atlas/ir_depth_simul.py` |
| IR and colour together | opening COLOR returns no error; the IR handle then delivers 0/77 IR frames (wrong-size buffers) while COLOR delivers 77/77 | HOLDS (Microsoft says they cannot be open together; the silent failure is the trap) | `atlas/ir_color_simul.py` |
| IR ceiling | per-frame maximum 1019, 1020 or 1021, never above, over 9 captures; it moves with the frame's dark level (corr 0.98–1.00 where both vary) — a jumping pedestal. 0.1–0.4 % of pixels clip on ordinary scenes | HOLDS (descriptive); cause OPEN | `ir_ceiling.py` |
| SDK depth vs IR registration | depth content ~3–5 px right of and ~3 px above IR content; consistent with published libfreenect-era offsets once the SDK's mirror is allowed for | OPEN (exploratory, one object) | `atlas/ir_depth_register.py`, `atlas/ir_depth_offset.py` |
| accelerometer | every value = integer count / 819 exactly (11,333 reads); \|g\| 1.015–1.018 at rest; noise ~8 counts ≈ 10 mg per sample; 12-bit codes pass through | HOLDS (uncalibrated) | `atlas/accel_probe.py`, `atlas/accel_series.py` |
| tilt motor | command +5° → **5.10 ± 0.03°** by the accelerometer; return trip +0.16°; the call blocks 0.63 s (up) / 0.89 s (down) | HOLDS (two moves) | `atlas/motor_probe.py` |
| microphones | 4 ch / 16 kHz, 24-bit data in a 32-bit container via WASAPI exclusive; 4 ch float via shared + RAW | HOLDS (as Microsoft's AudioCaptureRaw documents) | `atlas/wasapi_probe.py` |
| audio DMO | outputs mono only; its array mode (the only mode with beam and source angle) fails to start on this host (`E_FAIL`) | OPEN | `atlas/dmo_probe.py` |
| milky plastic cylinder | dot contrast 0.11–0.14 vs 0.60 on a box face (~5× smear), depth valid 51 % vs 98.7 %, temporal σ 3.5 vs 1.05 mm | HOLDS (one object; quantifies known subsurface scattering) | `dark_room_test.py`, `dark_room_edges.py` |
| black glossy ceramic mug | depth valid on 60 % of its pixels in every frame and correct: 1063–1066 mm vs tape 1067 mm | HOLDS (one object; the sealed rule refuted the "mirror" hypothesis) | `dark_room.py`, `mug_prediction.json`, `ir_edges.py` |
| glossy phone screen | IR saturates and blooms (~40 px); depth hole over the phone | HOLDS (illustrative, one pose; known specular behaviour) | `dark_room.py` |
| RGB camera vs projector dots | no detection; a post-hoc control detects an injected dot pattern at 0.22 DN rms and still finds nothing | NEGATIVE (a measured bound) | `dark_room_test.py`, `dark_room_edges.py` |
| ⅛-px code widths (code density), first attempt | setup invalid (t1), pilot not robust (t2) | NO VERDICT (design lesson) | `code_density.py`, `code_t1.json`, `code_t2trim.json` |
| signed four-edge test (depth vs IR outline) | left edge +1.26 px inward; the other three unmeasurable on this target | NO VERDICT | `four_edges.py` |

Other probes in `atlas/` (results in `atlas/*.json`) are recorded for completeness and are not claimed here.

### The SDK table and the driver phase (details)

- `lattice_closure.py` fixes the step at D = 0.1042/36000 mm⁻¹ (1/D = 345,489.4 mm) from PrimeSense's constants (zero-plane distance
  120, pixel size 0.1042, coefficient 4, shift scale 10) and tries 1000 phases and two rounding rules. Exactly one phase works: 0,
  with floor rounding, reproducing all 266 observed values with zero extras. D off by ±0.02 % already drops to 88–90 %; our own earlier
  fitted K reproduces 96.2 %. The constants 120 and 0.1042 are also in this unit's SDK blob (below); 7.5 cm, 4 and 10 are taken from
  PrimeSense's published code. The earlier fitted "intercept" is simply the 1200 mm reference plane, which is itself a rung.
- libfreenect and OpenNI subtract 0.375 in quarter-shift units, i.e. 1.5 raw shift steps, which puts their table at phase 0.5. The two
  value sets interleave: for example SDK 998 / 1001 / 1004 vs OpenNI 1000 / 1003 / 1006 mm.
- **What a value set can and cannot say.** It fixes the offset only modulo one step. For the same physical disparity, the SDK reads
  farther than OpenNI by half a step (≈ D·z²/2 = **4.7 mm at 1.8 m**) if its constant is 0.25 instead of 0.375, by 1.5 steps (14 mm)
  if it drops the constant entirely, and nearer if its constant is 0.5.
- **Prior observation (credit).** DiFilippo & Jouaneh ("Characterization of Different Microsoft Kinect Sensor Models", IEEE Sensors J.
  15(8):4554–4564, 2015) ran the same units with both drivers at an 1800 mm target and reported that, for all three Kinect models,
  the SDK returned a farther depth than OpenNI; they gave no mechanism. Read off their Fig. 2 at steady state, the gap is ~4 mm for
  model 1414 (ours), which matches the half-step case. Their 1473 and Kinect for Windows gaps (~13 and ~7 mm) are not explained here.
- The OpenNI side rests on the public code and on one public Xtion-class recording (a PS1080 sibling, pixel size 0.1052), whose values
  sit at phase 0.502 ± 0.015; it has not been checked on an OpenNI recording of a Kinect v1.

### The SDK calibration blob, stages 1–3 (details)

**Method and licence.** The Kinect for Windows SDK 1.8 licence forbids reverse engineering, decompiling and disassembling the software.
This work used documented APIs only — `INuiSensor::NuiGetCoordinateMapper`, `INuiCoordinateMapper::GetColorToDepthRelationalParameters`,
`NuiCreateCoordinateMapperFromParameters`, `MapDepthFrameToColorFrame`, `MapDepthPointToColorPoint` and `MapDepthPointToSkeletonPoint`
— with the public SDK headers and the public libfreenect source. The blob's fields were identified by matching its bytes to the public
libfreenect `freenect_reg_info` layout; edited copies of the blob were fed only to the documented
`NuiCreateCoordinateMapperFromParameters`. No SDK binary was disassembled, decompiled or patched. Disclosure: before the licence
constraint was noted, the presence of one export was confirmed by listing `Kinect10.dll`'s PE export-name table (names only; no code
inspected). Separately, during the first audio probe the property ids of the audio DMO were located by a byte search of the
installed `KinectAudio10.dll` (data only; no code inspected); they are the public Voice Capture DSP keys `MFPKEY_WMAAECMA_*`
(Windows SDK `wmcodecdsp.h`, documented on Microsoft Learn), which `atlas/dmo_probe.py` now cites; no published script reads an
SDK binary. The blob itself (`calib_blob.bin`) is per-unit data and is not published;
`blob_dump.py` writes yours.

- **Stage 1, layout** (`blob_dump.py`). `GetColorToDepthRelationalParameters` returns 12,604 bytes: a 20-byte header; a 2051-word uint16
  table (identity after four leading zeros on this unit); a 4096-entry uint16 table (identity); at byte 12314 a 118-byte PrimeSense
  registration block (2-byte prefix + 29 int32 in libfreenect's `freenect_reg_info` order); float32 120.0 (zero-plane distance) at
  12532; float32 0.1042 (zero-plane pixel size) at 12536; int32 const_shift 200 at 12600. The emitter distance 7.5 and libfreenect's
  2.3 / 2.4 constant are not present as plain floats. Prior art: libfreenect reads the same block from the device over USB (2011), and
  Kreylos (2013) reverse-engineered the device's factory calibration. What is new is narrow: the SDK's opaque blob contains that block.
- **Stage 2, registration** (`decode_stage2.py`, a Python port of libfreenect's `registration.c` fed with this unit's block, compared
  pixel by pixel with the SDK's `MapDepthFrameToColorFrame` on flat frames at 800–4000 mm). Sealed verdict: **FAIL** — the faithful port
  agrees within ±1 px on 0–15 % of pixels. Two differences explain it:
  1. The SDK's depth and colour images are mirror images of libfreenect's raw frames. The mirrored port agrees within ±1 px on 100 % of
     pixels up to 2000 mm.
  2. Beyond 2 m the SDK adds no further colour parallax. A 1 mm depth sweep shows the SDK's x stepping at the same 40 depths at every
     pixel (…, 1269, 1398, 1555, 1752, 2006 mm) and never again up to 8191 mm, i.e. the shift is evaluated at min(z, 2047 mm).
  Those steps equal the formula's with **2.4 cm** exactly (sweep match 1.000 vs 0.16–0.22 for 2.3), which settles, for the SDK, the
  question in libfreenect's "FIXME: OpenNI seems to use 2.4 instead of 2.3". A model with the mirror, the clamp, whole-pixel flooring of
  the warp and 1/16-px quantisation of the shift matches the SDK within ±1 px on 100 % of pixels at all six depths (exactly on 98.7 %).
  That model was fitted after seeing the SDK output, so it is a description; stage 3 then tested it predictively. Whether the frozen
  parallax is physically worse beyond 2 m (≈ 2 px at 3 m, 3 px at 4 m against the formula) is untested and not claimed.
- **Stage 3, usage** (`decode_stage3.py`: one-field edits, each mapper built in its own process). Control: a mapper built from the
  unmodified blob maps identically to the live sensor's. Editing the reg_info `ax` coefficient moves colour x only, identically at
  every depth (the stage-2 model predicts the change on 97.5 % of pixels in x and 100 % in y); editing the zero-plane distance moves
  colour x in a depth-dependent way (model: 100 %); zero-plane distances chosen to put a step at 2047 / 2048 / 2049 mm show it only at
  2047, which pins the clamp. const_shift, dx_center and both uint16 tables change nothing these functions return. **No edit changed
  any skeleton coordinate**: `MapDepthPointToSkeletonPoint` computes X = (u − 320)·Z/f, Y = −(v − 240)·Z/f, Z = depth/1000 with
  f = 571.2653 px = 2/3.501e-3 (the header's nominal inverse focal length), not the blob's 120/(2·0.1042) = 575.82 px. Since no blob
  field moves it, every unit's SDK point cloud uses the same nominal pinhole (inferred from the edits on one unit), so any per-unit
  focal-length error goes straight into X and Y. `atlas/mapper_vs_inline.py` confirms the mapper equals the header's inline formula.
- **Prior-art gate on the blob: NOT FOUND.** Microsoft documents the blob only as "a byte array containing the relational parameters";
  a 2013 MSDN question about it was never answered; projects that stored the blob never parsed it; Kreylos parsed the device's factory
  calibration but did not tie it to the SDK blob; no SDK-vs-libfreenect registration comparison was found.

### Extended depth (details)

`atlas/extended_depth_probe.py` compares the SDK ≥ 1.6 extended-depth texture (`NuiImageFrameGetDepthImagePixelFrameTexture`) with the
packed stream on the same frames. In range they agree on 100 % of 10.8 M pixels, and the packed stream's "too near / too far /
unknown" classes are thresholds on the extended value. Below the clamp, a real object on the left edge of the view read a steady
573–799 mm (persistence 0.92); 498–532 mm values were flicker. Above 4 m, 0.10 % of pixels read 4021–58,479 mm in a room no deeper than
3 m; they are not a surface (each is > 4 m in ~2 % of frames, next to a near object at the image edge), so any use beyond 4 m needs a
persistence mask, and accuracy beyond 4 m is untested. The sealed rule (≥ 99 % of out-of-range values on the table) FAILED at 94.0 %;
after fixing a cap in our own table it is 98.2 %, still a FAIL. The five remaining values match the table's rungs n = 283–287
(70,395 / 88,409 / 118,812 / 181,087 / 380,550 mm) taken modulo 65,536, so the SDK appears to write floor(z) into the 16-bit `depth`
field without saturating; if confirmed, a plausible-looking 4858 mm can really be a ~70 m (near-zero-disparity) false match. This is a
post-hoc reading of two runs; a confirmation run with a sealed prediction is pending.

### Materials and negatives (details)

- **Milky plastic** (`dark_room_test.py`, `dark_room_edges.py`): an opaque-looking plastic cylinder smears the projected dots about 5×
  and loses half its depth. This quantifies a known effect, subsurface scattering in structured light (Gupta & Nayar, "Micro Phase
  Shifting", CVPR 2012; Sarbolandi et al. 2015 §4.6, milk series).
- **Black glossy ceramic** gives correct depth (tape-confirmed, one mug). **Glossy phone glass** acts as a mirror to the projector: IR
  saturates and depth has a hole. Specular failure is known behaviour; both are single poses.
- **The RGB camera cannot see the projector's dots** (`dark_room_test.py`, `dark_room_edges.py`). The sealed rule returned KILL (true /
  null ratio 0.94 wall, 0.92 box). The sealed sensitivity control was too weak (hot pixels inflate its null); a post-hoc version with
  outliers clipped detects an injected dot pattern at 0.22 DN rms and still finds nothing (0.85 / 1.05). So there is no second
  triangulation camera. Publish it as a bound; Microsoft says the 1280×960 colour path is compressed.
- **Code density, first attempt** (`code_density.py`): no result. With the target's iso-code bands aligned to pixel rows the per-code
  counts jump by whole rows (invalid setup); a diagonal pilot moved with every reasonable cleaning choice. Lesson: a large, rigid, flat
  target with bands diagonal to the pixel grid, and the analysis frozen before the confirmatory capture.
- **Four-edge test** (`four_edges.py`, rule fixed before running): left edge +1.26 px inward; right, top and bottom unmeasurable because
  the IR-dark cloth does not coincide with the board's depth outline. No verdict; it needs a board that is IR-dark on all four sides and
  stands clear of the wall.

## Findings added in v2 (status · script)

| finding | number | status | script |
|---|---|---|---|
| three noise populations; σ > 10 mm mask | median 2.62 mm, RMS 38.06 mm; worst 1 % = 94.9 % of variance (median range 2.9 m) | HOLDS at ~3 m; range-dependent (v2.0.1) | `analyse_sigma.py`, `sigma_n.py` |
| per-pixel σ predicted by range alone | σ ∝ z^1.80, R² 0.574, held-out median rel. error 25.8 % | HOLDS (range only; pixel position not included — compare Nguyen 2012, Choo 2014) | `predictor.py` |
| the IR image does not predict σ | +0.0027 R² over range alone | NEGATIVE (the control was the result) | `predictor.py` |
| temporal correlation | raw τ_int = 84.9 frames = 2.74 s, but detrended (20 s) ACF only 0.16 → 0.02 over 1–90 frames | QUALIFIED (v2.0.1: drift inflates the raw figure) | `correlated.py`, `neff.py`, `acf_gate.py` |
| warm-up drift | +8.17 mm / 6 min at 2.5 m → +0.02 mm/min by ~70 min; one unexplained ~4 mm excursion | HOLDS (prior art credited in v2.1) / OPEN (air draft, a published cause, was not controlled) | `drift.py`, `warmup.py` |
| raw Bayer 1280×960 | a mosaic (lag-2 > lag-1 autocorrelation, 12.9 % phase-mean spread) | QUALIFIED (v2.1: a GRBG mosaic after on-chip gain; not shown raw; linearity untested) | `bayer.py`, `atlas/colour_probe.py` |
| stream capability map | 13 of 28 (type, resolution) pairs open; no 1280×960 IR | HOLDS (v2.1: was 10) | `capmap.py`, `atlas/player_index_probe.py` |
| IR is 10-bit | GCD of all values = 64 (1014 levels); maximum code 1019–1021 | HOLDS | `capmap.py`, `ir_ceiling.py` |
| near mode / projector off | both rejected, `0x8301000F` | NEGATIVE (hardware gate, as documented) | `nearmode.py`, `ir_off.py` |
| lateral scale, box face (hand tape) | −3.4 % | RETRACTED (v2.1: the reference was wrong) | `box_width.py`, `kinect_pos.py`, `scale_two_pos.py`, `rot_test.py` |
| lateral scale, US #10 envelope | long side +0.45 % to +1.74 % (f 575.82 / 571.26, own or backing plane) | NO VERDICT by the sealed rule (+1.74 % vs ±1.5 %); post-hoc ~1 % | `envelope_scale.py`, `envelope_prediction.json` |

Numbers for the noise populations were measured on static scenes; the confidence keep-rate is scene-dependent (38–48 % on real rooms
vs 73 % on a flat target), so never quote 73 % as a sensor property.

**Near mode and projector-off, precisely.** Both are rejected on this Xbox 360 unit with `0x8301000F`, which the SDK header `NuiApi.h`
defines as `E_NUI_HARDWARE_FEATURE_UNAVAILABLE`; the online documentation's error tables do not list that code. The rejection itself is
as documented: Microsoft lists the near range as "available only in the Kinect for Windows sensor" and states that
ForceInfraredEmitterOff does not work on Xbox 360 sensors. A checkbox in Microsoft's sample UI is not evidence the hardware can do it.

## Tools

- `nui.py` — a direct ctypes binding to `Kinect10.dll` (SDK 1.8): all 25 exports are plain x64 C symbols, struct sizes asserted at import.
- `sensor.py` — the `INuiSensor` COM interface (37 vtable slots, indices from the SDK's own `NuiSensor.h`), gated by a `verify()`.
  ⚠ The COM and flat APIs have **different signatures for the same function**: `NuiImageStreamGetNextFrame` takes a pointer-to-pointer
  in the flat API but a caller-allocated struct in COM; mixing them overwrites memory. `NuiInitialize` must come before accelerometer
  or emitter calls.
- `viewer.py` — a live instrument panel (tkinter + pillow): depth, IR, the 1280×960 Bayer mosaic, confidence, live σ, and **LATTICE**,
  which colours each pixel by its rung of the exact table (v2.1: exact constants instead of fitted ones) — a live contour map where one
  band is one quantisation step (2.35 mm at 0.9 m, 26 mm at 3 m).
- `first_contact.py` — a 5-frame smoke test.
- `atlas/` — the v2.1 probes of the depth pipeline, IR, colour camera, audio, accelerometer and motor (`atlas/atlas_common.py` holds
  shared helpers). Each script states its rule in its docstring; post-hoc runs are labelled.

Setup: Kinect for Windows SDK 1.8 (driver), the sensor on a **root-hub** USB port (not behind an external hub), Python 3 with numpy and
scipy (the viewer also uses pillow and matplotlib). Run every script from its own folder. Captures of a room (`*.npz`, `*.npy`, images,
audio) are never published; the capture scripts write them locally, and the analysis scripts take a capture as an argument.
`atlas/wasapi_probe.py` needs your PC's microphone-array endpoint ID in `KINECT_MIC_ENDPOINT_ID`.

---

## The v1 card: how many distinct depths does it actually produce?
A single-operator measurement on one Xbox 360 Kinect, with the scripts, the raw curve,
the failed controls, and the criteria that would prove it wrong. (Updated in v2.1: the thermal
interpretation is retracted, points 3 and 4 are superseded, and a prior census is credited.)

**Short version:** the realisable depth values form a lattice uniform in 1/z. On this unit it is
exactly PrimeSense's published shift-to-depth table: 259 rungs between 1 and 4 m, 345 in the SDK's
0.8–4 m window. A census converges on that count when the scene covers the range. It is a property of
the table and of scene coverage, not of thermal state.

---


## In plain words

A Kinect doesn't measure distance smoothly. It projects a fixed pattern of infrared dots, matches
small windows of what its IR camera sees against a stored reference image of that pattern, and
stores the shift as a whole number of ⅛-pixel steps. Whole numbers only — so the sensor can report
distances from a fixed ladder of rungs and nothing in between. Because of the geometry, the rungs are
millimetres apart up close and centimetres apart far away.

This card answers one question and gives you everything you need to check it yourself:

> **Across its working range, how many distinct depth values does the sensor actually produce —
> and does that number ever stop growing?**

Measured here: **259** distinct values between 1 and 4 metres — exactly the rungs of PrimeSense's table
in that band. A capture shows fewer if the scene does not cover the whole band. (v1 of this card said
"at least 257 and still climbing"; v2 attributed the difference to warm-up; v2.1 retracts that: it was
scene coverage.) The folklore number is 2048 (11-bit disparity, 0–2047; Khoshelham & Oude Elberink 2012
§3.2), or 1024 "usable". The realisable count is neither: it is the table's rung count inside the range
window (259 in 1–4 m, 345 in 0.8–4 m).

## The claim, stated precisely

1. Depth is quantised on a lattice that is **uniform in 1/z**, not in z — the signature of a
   structured-light triangulation sensor rather than a time-of-flight one.
2. Between 863 mm and 3975 mm, accumulating over 200 frames, **266 distinct millimetre values**
   appear. Restricted to 1000-4000 mm the count is **259**.
3. The step follows Δz ≈ z²/K with K = f·b/Δd = 36000/0.1042 = **345,489 px·mm**: PrimeSense's own
   constants (b = 75 mm, f = 575.8 px at 640 × 480, Δd = ⅛ px). The earlier fitted 345,316 was 0.05 %
   low (v2.1). Exact rung gaps against z²/K:

       z (mm)       1000   1500   2000   2500   3000   3500
       exact gaps    3/3    6/7  11/12  18/18  26/27  35/37
       z²/K         2.89   6.51  11.58  18.09  26.05  35.46

   The ~2.9 mm step at 1 m matches Smíšek et al. 2011 (eq. 1: q(1 m) = 2.89 mm); Khoshelham & Oude
   Elberink 2012 report "about 2 mm".
4. ~~Implied baseline 73.79 mm at f = 585 px~~: superseded (v2.1). With PrimeSense's constants the
   product is exact at b = 75 mm and f = 575.8 px. The 1.6 % gap came from pairing our fitted slope with
   f = 585 px.

## What this card does NOT claim — read this before objecting

The figure **0.25 mm** appears in the underlying findings and is **not a quantisation step**.
It is the *held-out prediction error of the fitted lattice model*: fit the grid on far levels
only (z > 2000 mm, n = 86), then predict the 180 near levels the fit never saw — median error
0.25 mm, max 0.58 mm, against a device that outputs integer millimetres (so rounding alone
permits 0.5 mm). It is a model residual sitting at the rounding floor. Anyone comparing it to
the ~3 mm/m quantisation step is comparing two different measurands. (v2.1: the 0.25 mm held-out
residual is superseded by the exact closure, which reproduces every value with zero error.)

## Hardware

| item | value |
|---|---|
| sensor | Xbox 360 Kinect (model 1414), PrimeSense PS1080, structured light |
| camera serial | `A003…` (truncated) |
| host | Windows 11, AMD xHCI |
| **USB topology** | **root-hub port, NOT behind an external hub** |

⚠ **The USB topology is load-bearing.** Behind an NEC/Renesas external hub (VID 0x0409) the Kinect is
likely starved of isochronous bandwidth; Microsoft's known-issues page lists "certain NEC USB 2.0
controllers" and the "Renesas Electronics USB 3.0 Controller". Symptom: motor and audio enumerate,
camera does not. This was first misdiagnosed here as a missing 12 V supply — power was fine the whole
time. If your camera interface will not come up, move to a root-hub port before you suspect anything else.

## Software

- **Kinect for Windows SDK 1.8** installed (driver only).
- Access via `nui.py` — a direct ctypes binding to `Kinect10.dll`. All 25 exports are
  undecorated x64 C symbols, so no wrapper library is required. Struct layouts are asserted
  against known `sizeof` at import, so a wrong offset fails loudly instead of returning
  plausible garbage.
- No libfreenect, OpenNI or ROS is used to drive the sensor. (`decode_stage2.py` contains a Python
  port of libfreenect's `registration.c`, used under its Apache 2.0 licence, for comparison only.)

⚠ **The bit shift is load-bearing.** `NUI_IMAGE_TYPE_DEPTH` returns `uint16` where millimetres
live in **bits 3-15** (`NUI_IMAGE_PLAYER_INDEX_SHIFT = 3`) — **even when no player-index stream
is open.** Read the raw value as millimetres and every number is wrong by a factor of eight.
Any replication that skips `>> 3` will not reproduce this card. (v2.1: the low 3 bits were 0 on
100 % of pixels in every mode tested, `atlas/depth_flags_probe.py`.)

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
(v2.1: `lattice_closure.py` goes further — with no fitted parameter, one phase of the published
formula reproduces every observed value.)

## What would falsify this

- Any value outside the table, or a count above 259 in 1–4 m or above 345 in 0.8–4 m, on the same
  hardware and driver under this protocol.
- Residual std near 0.2887 rather than ~0.015 — that would say the lattice is uniform in z and
  the structured-light model is wrong for this device.
- A prior census exists (Byte Kitchen 2014); this card replicates its count and adds the closed form.

## Replicate it

    python quantisation.py      accumulate levels, gap analysis vs both models (writes depth_lattice.npy)
    python lattice_test.py      the corrected grid-residual test
    python lattice_closure.py   the exact table: no fitted parameter (reads depth_lattice.npy;
                                our 266 values are in depth_lattice_values.json)
    python sweep_un.py / sweep_un2.py   the U(N) curves (to 10^4 / 10^5 frames)

The scripts contain their hypothesis and control in the docstring. `lattice_test.py` supersedes
the CV formulation in `quantisation.py` for the reasons in the controls section above, and
`lattice_closure.py` supersedes both for the lattice constants.

## What is ours and what is not

**Not ours — cite, do not rediscover:**
- The depth **quantisation law** (Δz ∝ z², step-vs-range curves): Khoshelham & Oude Elberink,
  *Sensors* 12(2):1437-1454, 2012, doi:10.3390/s120201437.
- The **shift-to-depth formula and its constants**: PrimeSense's `XnShiftToDepth` (OpenNI PS1080 driver)
  and libfreenect's `registration.c` / `cameras.c`, including the 0.375 offset.
- The **unique-depths → ΔZ method**: Smíšek, Jančošek & Pajdla, "3D with Kinect", ICCV Workshops
  (CDC4CV) 2011, §2.4, eq. 1.
- **Δd = ⅛ px**: reverse-engineered by Konolige & Mihelich (ROS `kinect_calibration/technical`, "the
  authors' best guess") and restated by Sarbolandi et al. 2015. It is implicit in PrimeSense's own
  open-source driver: `XnShiftToDepth` uses a coefficient of 4 on zero-plane pixels defined at 1280
  width. We found no Microsoft document that states ⅛.
- **Millimetre-LUT level drops**: Andersen et al., Aarhus ECE-TR-6, 2012.
- **The census itself**: Byte Kitchen (M. Drossaers), 2014, 345 values in the SDK's default range.
- **Unit-to-unit variation** of PrimeSense-family sensors: Boehm, *PFG* 2/2014:117-127.

Our steps at 1.0-3.5 m reproduce the published law. That reproduction is a **check on the
rig**, not a discovery.

**Ours, offered as new:**
- the identification of the SDK's value set with PrimeSense's formula at phase 0, and the driver
  phase mechanism (see the v2.1 findings);
- the U(N) curves (cold to 10,000 frames, settled to 100,000), as scene-coverage curves that converge
  on the table count;
- the two **failed controls**, with protocols, as labelled negative results;
- all of it on a **named unit** (model, driver, mode, USB topology) so it can be contested.

**A detector bug of ours, recorded because it nearly inverted the conclusion:** the drift control
compared the *first* patch reading against the *last* and reported "CONFOUNDED" on a run that was
stationary for 50,000 frames and moved only at the final checkpoint. An endpoint comparison cannot
distinguish slow drift from a discrete scene change. Stability must be checked across the whole
series, not at its ends.

**Prior census (credit).**
- The Byte Kitchen blog (M. Drossaers, "A Jitter Filter for the Kinect", 2014-03-17) reported that a
  Kinect for Windows produces **345** different depth values in the SDK's default range, as a stable
  set, and published the table.
- It reported 781 on an Xbox 360 unit "due to the larger range", and slightly different tables on its
  two units.
- 345 is exactly the number of PrimeSense-table rungs between 800 and 4000 mm. Our settled run reached
  exactly 345 (801–3975 mm) by N = 50,000.
- Our count is therefore a replication of that census. The 781 was reported without a range or
  method and is not tested here; with this unit's table the SDK's packed stream cannot exceed 345.

## Status

`LAB-CLAIMED`. Single device, single host, single driver stack, one operator, one static scene.
Not independently replicated. Published so that it can be.


## Cite

See `CITATION.cff`. Licence: MIT (`LICENSE`), except the ported libfreenect section of `decode_stage2.py`
(Apache 2.0, as marked in the file). By Moki&Julio.

## Other work by Moki & Julio

- [moki-julio-wifi-ris-cell](https://github.com/Hashirama1337s/moki-julio-wifi-ris-cell): One 1-bit reconfigurable-intelligent-surface cell covering the 2.4 GHz and 5-7 GHz Wi-Fi bands with one switch state (simulation study, Palace FEM) ([doi:10.5281/zenodo.23165406](https://doi.org/10.5281/zenodo.23165406))
- [rikitake-chaos](https://github.com/Hashirama1337s/rikitake-chaos): Computer-assisted proof that Rikitake's two-disc dynamo (1958) is chaotic ([doi:10.5281/zenodo.23041182](https://doi.org/10.5281/zenodo.23041182))
- [szilassi-12](https://github.com/Hashirama1337s/szilassi-12): No symmetric 12-face Szilassi polyhedron: a computer-assisted proof with DRAT certificates ([doi:10.5281/zenodo.23003257](https://doi.org/10.5281/zenodo.23003257))
- [moki-julio-circle-packing](https://github.com/Hashirama1337s/moki-julio-circle-packing): 6,071 new best-known packings of equal circles, spheres and hyperspheres, each verified by two independent exact checkers ([doi:10.5281/zenodo.22981305](https://doi.org/10.5281/zenodo.22981305))

All projects: [github.com/Hashirama1337s](https://github.com/Hashirama1337s)
