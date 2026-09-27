# Open questions — Kinect v1 (Xbox 360, model 1414)

This is a list of open, measurable questions about the Kinect v1 that are left after this repository's v2.1. Each entry gives the
unknown, the best public source we found (one, with its link), a probe that can answer it with an ordinary Kinect v1 and the Kinect
for Windows SDK 1.8, and a pass/fail bar. The method rule is simple: **fix the bar, and freeze the analysis code, before you look at
the data, and publish the result whichever way it falls**, including NULL, FAIL and NO VERDICT. To contribute, open an issue with the
probe ID, the script you ran (or its hash), the numbers it produced and your sensor model; negatives are as welcome as positives.

---

## How to read this list

- **Rank** is our priority order across the whole list (1 = most valuable to settle next). Sections group probes by subsystem; inside
  each section, entries are in rank order.
- **Value** says what the answer would change. **Prior-art risk** says how likely it is that the answer is already published somewhere
  we did not find. Run your own prior-art check at the primary source before calling anything new.
- **Setup:** *none* = software only, or offline on your own captures; *small* = a few minutes with simple props; *session* = 30+ minutes
  or a special prop; *rides X* = captured in the same setup as probe X, at no extra cost.
- **System change:** every probe outside the last section runs on stock SDK 1.8 with no driver change. One part of one probe (AUD-3b)
  toggles a Windows audio setting and reverts it. The last section needs a USB driver change (reversible).
- Script names refer to files in this repository; `atlas/` scripts live in the `atlas` folder. Captures of a scene are never published,
  so offline probes need your own captures.
- All numbers quoted as "ours" come from a single Xbox 360 unit, model 1414. Model 1473 and Kinect for Windows numbers are not
  interchangeable with them.
- Distances are measured from the sensor's front face. Image coordinates are in the SDK's mirrored orientation unless stated.

### Before you start

- Setup as in the README: SDK 1.8 driver, the sensor on a root-hub USB port, Python 3 with numpy and scipy. Run `sensor.py`'s
  `verify()` first.
- One streaming process at a time (a second one gets `E_NUI_DEVICE_IN_USE`, 0x83010009). Keep captures short (≤ 30 s where possible)
  and save numbers only.
- Unless the probe is about warm-up, power the sensor for ≥ 60 min first, with the tilt motor at 0°.
- Facing the Kinect: the left window is the projector, the centre one is the colour camera, the right one is the IR camera. Confirm each
  on the live view (`viewer.py`).
- Props that recur: a **white card** (one US Letter sheet glued flat to stiff cardboard, trimmed flush, glue dry); an **IR-dark black
  board**; a **thin post** (a wooden ruler standing in a mug filled with coins or rice, the target taped to its top edge, lower edge
  ≥ 15 cm above the support, other edges free); masking tape and a tape measure.

---

## Ranked overview

| rank | id | subsystem | question | value | setup |
|---|---|---|---|---|---|
| 1 | IR-1 | registration | Is SDK depth offset from IR by a pure shift, or also eroded? | HIGH | small |
| 2 | DEP-2 | depth | Is the extended-depth 16-bit wrap fixed to five values? | HIGH | none |
| 3 | ACC-1 | accelerometer | Zero-g offsets of the accelerometer | HIGH | small |
| 4 | DEP-1 | depth | Is 500–800 mm usable through the extended texture? | HIGH | session |
| 5 | AUD-1 | microphones | Mic positions and channel order on model 1414 | HIGH | small |
| 6 | COL-1 | colour | Are RAW_BAYER and COLOR linear? | HIGH | small |
| 7 | COL-2 | colour | Is white balance applied on the mosaic? | HIGH | small |
| 8 | COL-7 | registration | SDK colour-mapper accuracy on real image content | HIGH | small |
| 9 | IR-6 | IR / laser | Does the laser mode-hop, and how often? | HIGH | session |
| 10 | IR-7 | IR / laser | Does warm-up pattern scale explain the +8 mm drift? | HIGH | session (same run) |
| 11 | NSE-1 | noise | Are the ⅛-px disparity codes equal width? | HIGH | session |
| 12 | IR-3 | IR / projector | Is the projected pattern the same on every unit? | HIGH | rides IR-6 or NSE-1 |
| 13 | CAL-2 | registration | Is the 2047 mm colour-parallax clamp physically right? | HIGH | session |
| 14 | IR-8 | noise | Is correlated depth noise a whole-field scale jitter? | MED–HIGH | none |
| 15 | AUD-2 | microphones | DMO array-mode failure: our binding or the host? | MED | small |
| 16 | AUD-3 | microphones | Default 2-ch stream: plain downmix or processed? | MED | none / small |
| 17 | DEP-3 | depth | Are extended values beyond 4 m real, and how accurate? | MED–HIGH | session |
| 18 | CAL-1 | registration | Which blob fields do the colour→depth functions use? | MED | none |
| 19 | DEP-9 | hardware route | Same-unit proof of the SDK / OpenNI half-step | HIGH | driver change |
| 20 | IR-14 | hardware route | Does the firmware answer PS1080 TEC / emitter reads? | HIGH if it answers | driver change |
| 21 | MAT-2 | materials | Surface bias of milky water vs concentration | MED–HIGH | session |
| 22 | CAL-3 | registration | Intrinsics; is the mapper residual the colour lens distortion? | MED | session |
| 23 | MOT-1 | tilt motor | Repeatability, backlash and landing accuracy | MED | none (11 motor moves) |
| 24 | IR-5 | IR camera | Black level, pedestal and ceiling; does the pedestal touch depth? | MED–LOW | none + small |
| 25 | COL-3 | colour | Is COLOR 1280 a demosaic of RAW_BAYER 1280? Compression? | MED | small |
| 26 | ACC-2 | accelerometer | Full per-axis offset and gain | MED | none / small |
| 27 | ACC-3 | accelerometer | Accelerometer-to-camera roll alignment | MED | small |
| 28 | IR-9 | IR camera | Does IR brightness auto-adjust? | MED | small |
| 29 | COL-4 | colour | On-chip lens-shading correction | MED–LOW | small |
| 30 | NSE-2 | noise | Are vertical noise bands rung boundaries? | MED | rides NSE-1 |
| 31 | COL-6 | colour | Does the IR-cut filter block 940 nm? | LOW–MED | small |
| 32 | IR-4 | IR / projector | Pattern field distortion and roll | MED | none (after IR-3) |
| 33 | ACC-4 | accelerometer | Resting-pitch wander: physical or sensor drift? | MED–LOW | rides IR-6 |
| 34 | AUD-4 | microphones | Beam and source-angle accuracy | MED | session (short) |
| 35 | DEP-6 | depth | Where does the published "781 values" come from? | LOW–MED | none |
| 36 | IR-10 | IR / projector | Are the nine bright dots a rigid angular grid? | LOW–MED | rides DEP-1 |
| 37 | COL-8 | colour | Is the 1280 frame rate camera-limited or USB-limited? | LOW–MED | none |
| 38 | DEP-8 | depth | Per-unit depth scale and offset | LOW | rides DEP-1 |
| 39 | DEP-7 | registration | Lateral scale on a factory-sized reference | LOW | rides IR-1 |
| 40 | IR-11 | registration | Does edge erosion depend on step size or reflectance? | MED–LOW | session (short) |
| 41 | NSE-3 | noise | Does pixel position add to the range-only noise predictor? | LOW–MED | none |
| 42 | NSE-4 | noise | Averaging gain as a function of window length | LOW | none |
| 43 | MAT-1 | materials | How many paper sheets until depth drops out? | LOW–MED | small |
| 44 | IR-2 | registration | Shadow-width K vs pattern-shift K | LOW | none |
| 45 | DEP-4 | depth | How is 80×60 depth produced? | LOW | none |
| 46 | IR-12 | IR / projector | Is a separate zero-order spot visible? | LOW–MED | rides CAL-2 / DEP-3 |
| 47 | NSE-5 | noise | Does the pinned per-pixel bias reshuffle with wavelength? | MED–LOW | rides IR-6 |
| 48 | ACC-5 | accelerometer | Origin of the sparse 8-count code structure | LOW–MED | none |
| 49 | DEP-5 | depth | Is the 640×480 player index native? | LOW | small |
| 50 | ACC-6 | accelerometer | Does vNormalToGravity populate? | LOW | small |
| 51 | COL-5 | colour | The SDK's YUV→RGB matrix and range | LOW | small |
| 52 | NSE-6 | noise | Does edge noise depend on sub-pixel edge position? | LOW–MED | small (rides IR-1) |
| 53 | NSE-7 | noise | Is air draft behind a ~4 mm drift excursion? | LOW | rides IR-6 |
| 54 | AUD-5 | microphones | AEC / NS performance, and where it runs | LOW | none (plays sound) |
| 55 | AUD-6 | microphones | Array self-noise at the default gain | LOW | none |
| 56 | NSE-8 | noise | Sub-code transfer curve | LOW | session (only if NSE-1 passes) |
| 57 | IR-13 | hardware route | Which 480 of 488 IR rows; is SDK IR binned? | LOW–MED | driver change |
| 58 | COL-9 | hardware route | Which 960 of 1024 colour rows | LOW | driver change |
| 59 | ACC-7 | hardware route | What GetAngle computes | LOW | driver change |
| 60 | IR-15 | hardware route | Projector off on Xbox units, outside the SDK | LOW–MED | driver change + device write |
| 61 | AUD-7 | hardware route | What the "Audio Array Control" interface carries | LOW | second driver change; not recommended |

---

## 1. Registration, calibration and geometry

### IR-1 · rank 1 — Is SDK depth offset from IR by a pure translation, or is the depth outline also eroded?

- **Unknown.** Whether SDK depth sits on the IR image by a pure translation (about 4 × 3 px in an exploratory look) or whether the
  depth outline is also eroded. An earlier "depth outline 0–3 px inside the IR outline" reading measured one side only.
- **Public.** [ROS kinect_calibration/technical](http://wiki.ros.org/kinect_calibration/technical): −4.8 × −3.9 px on unmirrored
  libfreenect frames. Nothing for SDK 1.8 (mirrored, 480 rows).
- **Probe.** The white card on the post, ≥ 30 cm clear of the wall. Stations: 1.0 m centre, left third and right third, then 2.0 m
  centre. Turn the card until left and right depth agree within 3 mm. IR + depth together, 10 s each. Measure the signed outward offsets
  L, R, T, B (depth contour minus IR contour); ox = (R − L)/2, oy = (B − T)/2, erosion e = −(L + R + T + B)/4.
- **Bar.** **PURE OFFSET** if |e| ≤ 0.5 px and (ox, oy) agree across placements within ±0.7 px: publish the SDK offset. **SHRINK** only
  if e ≥ 1 px and (L + R) − (T + B) is within ±1 px at every placement. **FAIL** (spread > 1.5 px): publish the signed four-tuples as
  edge-dependent. Corner check: K within ±2 %.
- **Value / prior-art risk.** HIGH: every SDK IR + depth overlay is off by pixels, and every published offset is for unmirrored
  libfreenect frames. / MED: libfreenect offsets are well known; no SDK version found.
- **Setup.** small · no system change · `four_edges.py`, `atlas/ir_depth_offset.py`, `atlas/ir_depth_register.py`. Use a white card,
  not an IR-dark one (see Pitfalls: the projector shadow).

### COL-7 · rank 8 — How accurate is the SDK colour mapper against real image content?

- **Unknown.** The SDK depth→colour mapper's accuracy against image content on a real unit.
- **Public.** [Kreylos 2013, doc-ok.org/?p=313](http://doc-ok.org/?p=313): the factory depth→colour polynomial; no SDK mapper figure
  anywhere.
- **Probe.** The black board on the post, ≥ 30 cm clear of the wall, lit. Stations: 1.0 m centre, left, right and upper-left (stand the
  post's base on a stack of books), then 2.0 m centre. Depth + COLOR 640 together (never IR and colour together; see Pitfalls).
- **Bar.** **CONSISTENT** if the fitted translation |t| ≤ 1 px with a CI half-width < 0.5 px at every station; **OFFSET** if > 1.5 px
  anywhere at the same CI.
- **Value / prior-art risk.** HIGH: the first real-content figure for the SDK registration. / LOW.
- **Setup.** small (rides IR-1's stations) · no system change · `atlas/colour_registration.py`.

### CAL-2 · rank 13 — Is the SDK's colour-parallax clamp at 2047 mm physically right?

- **Unknown.** Beyond 2047 mm the SDK adds no further colour parallax; PrimeSense's formula differs from it by ~2 px at 3 m and ~3 px
  at 4 m. Which one matches the real colour image?
- **Public.** [libfreenect registration.c](https://raw.githubusercontent.com/OpenKinect/libfreenect/master/src/registration.c): the
  formula, with no clamp.
- **Probe.** The black board on the post (on a stool), ≥ 30 cm clear of a far wall, at 3.0 m and then 3.8 m, lit; depth + COLOR
  together. Write down both models' predicted colour edge before the capture.
- **Bar.** **SDK-RIGHT** if the colour edge is within ±0.7 px of the SDK map at both distances; **FORMULA-RIGHT** if within ±0.7 px of
  the unclamped formula; otherwise report the numbers.
- **Value / prior-art risk.** HIGH: if the formula wins, SDK colour registration past 2 m is off by 2–3+ px on every v1. / LOW (no prior
  work found on the SDK blob; run a separate check on the clamp itself).
- **Setup.** session (a far-wall session of about 45 min, shared with DEP-3 and IR-12) · no system change · `decode_stage2.py`,
  `decode_stage3.py`.

### CAL-1 · rank 18 — Which blob fields do the colour→depth mapping functions use?

- **Unknown.** Which fields of the calibration blob `MapColorFrameToDepthFrame` and `MapColorFrameToSkeletonFrame` use: the two uint16
  tables, const_shift, the header bytes. (v2.1 answered this for the depth→colour and depth→skeleton functions only.)
- **Public.** [jj663736](https://learn.microsoft.com/en-us/previous-versions/windows/kinect-1.8/jj663736(v=ieb.10)): Microsoft describes
  the blob only as a byte array of relational parameters.
- **Probe.** The `decode_stage3.py` method applied to the colour→depth functions: one-field edits of the blob, fed only to the documented
  `NuiCreateCoordinateMapperFromParameters`, each mapper built in its own process, on synthetic depth frames. Control: the unedited blob
  maps identically to the live mapper.
- **Bar.** **USED** if ≥ 1 % of mapped pixels move after a one-field edit; **NOT USED** otherwise.
- **Value / prior-art risk.** MED: completes the blob map (colour→depth is untested). / LOW.
- **Setup.** none · no system change · `blob_dump.py`, `decode_stage3.py`.

### CAL-3 · rank 22 — This unit's intrinsics, and is the mapper's non-projective residual the colour lens distortion?

- **Unknown.** The unit's colour and IR intrinsics and distortion. Does the mapper's non-projective residual (±3.4 px at the corners)
  equal the colour lens distortion? (The colour cy is also a weak hint to which 960 of the 1024 sensor rows the SDK delivers.)
- **Public.** [TUM RGB-D file formats](https://cvg.cit.tum.de/data/datasets/rgbd-dataset/file_formats): per-unit fx 517–521 plus
  distortion.
- **Probe.** A printed checkerboard (e.g. 10 × 7 squares of 25 mm on Letter) glued flat to stiff card; measure 8 squares with a ruler,
  because printers rescale. Colour: 15–20 poses at 0.8–1.5 m, covering the corners. IR: cover the projector window with an opaque sticky
  note, light the board with halogen or daylight (LEDs emit almost no 830 nm), 8 poses; uncover the projector afterwards.
- **Bar.** **TYPICAL** if colour f is in 516–531 and cy is in the published band; **SAME** if the distortion field matches the mapper
  residual within 1 px rms; IR **NOMINAL OK** if |fx − 571.27| ≤ 0.5 % and |cx − 320| ≤ 3 px.
- **Value / prior-art risk.** MED: intrinsics are routine; the link to the mapper residual is new. / HIGH for the intrinsics; LOW for the
  link.
- **Setup.** session (about 20 min; printed prop) · no system change · `atlas/colour_mapper_shape.py`.

### DEP-7 · rank 39 — Lateral scale on a factory-sized reference

- **Unknown.** A sealed re-run of the lateral-scale check. The #10 envelope gave NO VERDICT (+1.74 % against a ±1.5 % bar).
- **Public.** [Kreylos 2013](http://doc-ok.org/?p=313): the factory calibration reads a precise target 1.5–2.8 % oversize.
- **Probe.** Rides IR-1: the Letter card (215.9 × 279.4 mm); size = IR outline × its own depth plane / 571.2653.
- **Bar.** **PASS** if both sides are within ±1.0 %; **FAIL** if either is off by > 2 %.
- **Value / prior-art risk.** LOW: a consistency check that closes the NO VERDICT. / HIGH.
- **Setup.** rides IR-1 · no system change · `envelope_scale.py`.

### IR-11 · rank 40 — Once the offset is removed, does edge erosion depend on step size or reflectance?

- **Unknown.** Whether the remaining depth-edge erosion depends on the depth step behind the edge or on the target's reflectance.
- **Public.** [Smíšek et al. 2011](https://cmp.felk.cvut.cz/ftp/articles/pajdla/Smisek-CDC4CV-2011.pdf): IR→depth shift 3.0 / 2.9 px,
  7 × 7 correlation window.
- **Probe.** The white card, then the black board, on the post at 1.0 m, with a flattened cardboard box as a background panel 5, 20 and
  40 cm behind; IR + depth, 10 s each.
- **Bar.** **CONSTANT EROSION** if the width deficit is the same within ±0.5 px across gaps and reflectance; otherwise report the
  dependence.
- **Value / prior-art risk.** MED–LOW. / MED.
- **Setup.** session (about 15 min) · no system change · `four_edges.py`.

### IR-2 · rank 44 — Does the occlusion-shadow width give the same K (f·b) as the pattern shift?

- **Unknown.** Whether K derived from projector-shadow widths agrees with K from the pattern shift.
- **Public.** [libfreenect registration.c](https://raw.githubusercontent.com/OpenKinect/libfreenect/master/src/registration.c): the
  emitter distance is read from the device (it is not in the SDK blob).
- **Probe.** Offline, on captures with clean near/far depth steps: K_shadow = width / (1/z_near − 1/z_far).
- **Bar.** **PASS** if the implied baseline b is within ±2 mm of 75 mm at f 575.8; **FAIL** if it is off by > 5 mm.
- **Value / prior-art risk.** LOW: a third check of K (the pattern shift already agrees within 0.74 %). / MED.
- **Setup.** none · no system change.

---

## 2. Depth: range, value set and streams

### DEP-2 · rank 2 — Is the extended-depth uint16 wrap fixed?

- **Unknown.** Do only rungs n = 283–287 wrap, and always to exactly 4858 / 22 872 / 53 275 / 50 014 / 52 867–9 mm?
- **Public.** [jj131028](https://learn.microsoft.com/en-us/previous-versions/windows/kinect-1.8/jj131028(v=ieb.10)): extended depth is
  a 16-bit millimetre field; nothing on values above 65 535.
- **Probe.** Five fresh 60-frame runs of the extended-depth texture, in at least two different scenes.
- **Bar.** **PASS** if every off-table value is in that set; **FAIL** on any other off-table value. Also report the share of 4–8 m
  extended values that are 4858.
- **Value / prior-art risk.** HIGH: a plausible 4.86 m reading that is really a ~70 m false match, in a documented API. / LOW–MED (quick
  search only).
- **Setup.** none (~3 s per run) · no system change · `atlas/extended_depth_probe.py`, `atlas/extended_followup.py`.

### DEP-1 · rank 4 — Is 500–800 mm usable through the extended texture on an Xbox unit?

- **Unknown.** Whether the near band below the SDK's 800 mm clamp is usable through the extended texture; where the true minimum is; and
  what "too near" looks like when there is no depth.
- **Public.** [jj131028](https://learn.microsoft.com/en-us/previous-versions/windows/kinect-1.8/jj131028(v=ieb.10)): values nearer than
  the "too near" limit are reported, with no numbers. Near mode is Kinect for Windows only
  ([hh855246](https://learn.microsoft.com/en-us/previous-versions/windows/kinect-1.8/hh855246(v=ieb.10))).
- **Probe.** A matte WHITE board ≥ 30 × 40 cm (foam board, or cardboard covered in printer paper; not the IR-dark board) on the post,
  square to the sensor, with the bright centre dot on it. Tape marks at 1300 / 1100 / 950 / 850 / 780 / 700 / 620 / 560 / 500 mm from
  the front face. Check squareness on depth at ≥ 850 mm and on the extended texture below that. 60 frames per station: packed depth +
  extended texture + IR.
- **Bar.** (a) The minimum is the smallest station with ≥ 50 % valid pixels. (b) **USABLE** if extended median − tape stays within the
  850 mm offset ± 1 % at every valid station; otherwise **FAIL**. (c) Temporal σ ≤ 2 mm: **PASS**. (d) **BELOW-WINDOW** if the share of
  (packed 0, extended 0) pixels rises monotonically inside the minimum.
- **Value / prior-art risk.** HIGH: a near-range route on Xbox units with no driver change, where the SDK says "too near". / MED:
  forum-level use is likely; no numbers found.
- **Setup.** session (about 35 min; IR-10 and DEP-8 ride it) · no system change · `atlas/extended_depth_probe.py`.

### DEP-3 · rank 17 — Do extended values beyond 4 m come from a real surface, and how accurate are they?

- **Unknown.** Whether extended-depth values > 4 m are real surfaces, and their accuracy.
- **Public.** [SDK 1.6 release blog](https://learn.microsoft.com/en-us/archive/blogs/kinectforwindows/kinect-for-windows-releases-sdk-update-and-launches-in-china):
  says accuracy is lower beyond 4 m; no numbers.
- **Probe.** Square to a flat matte wall 4.5–6.5 m away, floor distance taped; extended depth + IR, 60 frames, at 1–2 distances. No
  sunlight (evening, or curtains drawn). A passive USB cable run is limited to about 5 m.
- **Bar.** **REAL-SURFACE** if ≥ 50 % of wall pixels are valid with persistence ≥ 0.9; **ACCURATE** if the extended median is within
  ±2 % of tape; otherwise **FAIL**.
- **Value / prior-art risk.** MED–HIGH: the first numbers for a documented but unquantified range. / MED (OpenNI readings beyond 9 m are
  reported; no SDK numbers found).
- **Setup.** session (shared with CAL-2) · no system change · `atlas/extended_depth_probe.py`.

### DEP-6 · rank 35 — Where does the published "781 values" on an Xbox unit come from?

- **Unknown.** Which documented depth window, if any, produces 781 distinct values.
- **Public.** [Byte Kitchen 2014](https://thebytekitchen.com/2014/03/17/a-jitter-filter-for-the-kinect/): reports 781 values and
  attributes them to the larger range, with no method.
- **Probe.** Arithmetic on the exact table; write the bar down before counting.
- **Bar.** **EXPLAINED** if a documented window (packed, extended or near; SDK ≥ 1.6) holds exactly 781 rungs; otherwise record
  "unexplained".
- **Value / prior-art risk.** LOW–MED: closes a published tension. / n/a.
- **Setup.** none · no system change · `lattice_closure.py`.

### DEP-8 · rank 38 — Per-unit depth scale and offset

- **Unknown.** The unit's depth scale and offset, SDK = s × tape + c.
- **Public.** [Khoshelham & Oude Elberink 2012](https://pmc.ncbi.nlm.nih.gov/articles/PMC3304120/): a scale near 1.01 on their unit.
- **Probe.** Rides DEP-1: ≥ 5 taped stations between 500 and 1300 mm, with the fit rule fixed before capture. The front face is the
  datum; c absorbs the lens offset. Report s and c with confidence intervals.
- **Bar.** A calibration, not a test: report s and c with CIs under the pre-fixed rule.
- **Value / prior-art risk.** LOW: calibrates one unit; not a discovery. / HIGH.
- **Setup.** rides DEP-1 · no system change.

### DEP-4 · rank 45 — How is 80×60 depth produced?

- **Unknown.** How the SDK makes the 80×60 depth stream. It is not a 640 decimation, and not a block min, median or max.
- **Public.** SDK 1.8 header `NuiImageCamera.h`: the resolution list only.
- **Probe.** 640 → 320 → 80 → 640 on a static scene, 40 frames each. Test 320-decimation offsets (s = 4), block modes and mirrored
  offsets.
- **Bar.** As fixed in `atlas/resolution_probe.py`: a candidate wins at ≥ 0.9 × the ceiling and ≥ 10 points over the runner-up.
- **Value / prior-art risk.** LOW. / LOW.
- **Setup.** none (~2 min) · no system change · `atlas/resolution_probe.py`.

### DEP-5 · rank 49 — Is the 640×480 player index native or upsampled from 320×240?

- **Unknown.** Whether the 640×480 player-index mask is computed at 640 or upsampled from 320.
- **Public.** SDK header remarks: player index is listed only at 320×240 and 80×60.
- **Probe.** A person stands still ~2.5 m in front of the sensor, whole body in view with the floor visible, for 10 s, then walks slowly
  across the view once. Skeleton + depth-and-player-index at 640 and 320. (Enable skeleton tracking only after any audio capture: it
  stops the audio stream.)
- **Bar.** **NATIVE** if ≥ 30 % of 640 mask-boundary pixels cannot come from 2× upsampling of the 320 mask; otherwise **UPSAMPLED**.
- **Value / prior-art risk.** LOW. / LOW.
- **Setup.** small · no system change · `atlas/player_index_probe.py`.

---

## 3. Accelerometer and tilt motor

### ACC-1 · rank 3 — The accelerometer's x/z zero-g offsets

- **Unknown.** This unit's x/z zero-g offsets. Is the −1.5° roll, and the 1.7° gap to the side plane seen in depth, an accelerometer
  offset or a tilted support surface? (The output format is settled: every value is count/819 exactly, |g| 1.017.)
- **Public.** [libfreenect issue #7](https://github.com/OpenKinect/libfreenect/issues/7): asks where the accelerometer calibration
  lives; open since 2010-11-13, no comments.
- **Probe.** A 180° reversal on a taped footprint. Tape along the front edge and one side of the base; read 30 s; lift by the BASE only,
  turn 180° on the spot, set it back into the taped corner, read 30 s. Do the pair twice. offset = (a + b)/2, support tilt = (a − b)/2.
- **Bar.** **PASS** if the two repeats agree within 2 counts; then the offset-corrected roll must match the depth side plane within
  0.3°. **FAIL** if the repeats differ by > 4 counts.
- **Value / prior-art risk.** HIGH: the first public offset for a Kinect v1 accelerometer, and the reachable half of issue #7. / LOW.
- **Setup.** small · no system change · `atlas/accel_probe.py`, `atlas/plane_gravity_probe.py`.

### MOT-1 · rank 23 — Tilt-motor repeatability, backlash and landing accuracy

- **Unknown.** How repeatably the motor returns, how much backlash it has, and how close it lands to the commanded angle.
- **Public.** [hh855454](https://learn.microsoft.com/en-us/previous-versions/windows/kinect-1.8/hh855454(v=ieb.10)): ±27°, relative to
  gravity; no repeatability figure.
- **Probe.** 11 moves, well spaced (we use ≥ 25 s between moves): 0 → +5 → 0 → −5 → 0 → +15 → +5 → −5 → +5 → +10 → −10 → 0. At each
  stop, a 30 s accelerometer mean plus the depth-plane pitch.
- **Bar.** **REPEATABLE** if the SD of the returns to 0 is < 0.1°. Backlash at +5 (arriving from +15 vs from below): **PASS** ≤ 0.5°,
  **FAIL** > 1°. **LANDING PASS** if every stop is within 1° of its target.
- **Value / prior-art risk.** MED: no public figure. / LOW.
- **Setup.** none, but it moves the motor 11 times; never probe the lockouts · no system change · `atlas/motor_probe.py`.

### ACC-2 · rank 26 — Full per-axis offset and gain, including y

- **Unknown.** Offset and gain on all three axes.
- **Public.** [KXSD9-2050 datasheet](https://akizukidenshi.com/goodsaffix/KXSD9-2050%20Specifications%20Rev%203a.pdf): 819 ± 25
  counts/g; offset ±205 counts.
- **Probe.** Partial, at no extra cost: a y–z ellipse fit from MOT-1's stops (weak over 25°). Full: a six-pose tumble on a folded towel,
  held by the base (upright, upside down, left side down, right side down, lens up, lens down), 30 s each. Never press on the head:
  the tilt gears can be damaged.
- **Bar.** **PASS** if the post-fit |g| scatter across poses is < 0.2 %.
- **Value / prior-art risk.** MED. / LOW.
- **Setup.** none (partial) or small (tumble) · no system change · `atlas/accel_probe.py`.

### ACC-3 · rank 27 — Roll alignment between the accelerometer and the IR/depth camera

- **Unknown.** The roll angle between the accelerometer axes and the camera, against a known vertical.
- **Public.** [jj663844](https://learn.microsoft.com/en-us/previous-versions/windows/kinect-1.8/jj663844(v=ieb.10)): axes defined; no
  alignment figure.
- **Probe.** A plumb line (a dark cord ~1 m long with a small weight, e.g. keys) hung 10–20 cm in front of a wall, centred in view, left
  to stop swinging. Its angle in a 100-frame mean IR image vs the accelerometer roll, after ACC-1's offset.
- **Bar.** **PASS** ≤ 0.3°; **FAIL** > 0.6°.
- **Value / prior-art risk.** MED. / LOW.
- **Setup.** small · no system change · `atlas/plane_gravity_probe.py`.

### ACC-4 · rank 33 — Is the ±0.2° resting-pitch wander physical, or offset drift?

- **Unknown.** Whether the pitch wander seen with no motor command is real motion or the accelerometer's thermal offset drift.
- **Public.** [KXSD9 datasheet](https://akizukidenshi.com/goodsaffix/KXSD9-2050%20Specifications%20Rev%203a.pdf): z offset tempco
  3 mg/°C.
- **Probe.** Rides IR-6's warm-up run: a 30 s accelerometer read per burst plus the frontal-plane pitch from depth.
- **Bar.** **PHYSICAL** if the depth-plane pitch tracks the accelerometer within 0.05°; **SENSOR DRIFT** if depth stays within 0.05°
  while the accelerometer moves > 0.15°.
- **Value / prior-art risk.** MED–LOW. / LOW.
- **Setup.** rides IR-6 · no system change · `atlas/accel_series.py`.

### ACC-5 · rank 48 — Where does the sparse 8-count code structure come from?

- **Unknown.** Why the accelerometer's output codes are sparse with an 8-count structure.
- **Public.** None found.
- **Probe.** Code occupancy at MOT-1's stops (no extra moves).
- **Bar.** **DNL-LIKE** if the same code widths recur at 3 poses within 20 %. The decisive version needs raw 0x32 counts from the
  device (hardware route).
- **Value / prior-art risk.** LOW–MED. / LOW.
- **Setup.** none · no system change (the decisive part needs the hardware route) · `atlas/accel_series.py`.

### ACC-6 · rank 50 — Does vNormalToGravity populate with a tracked person and the floor in view?

- **Unknown.** Whether the skeleton frame's floor-normal field is ever filled on this hardware.
- **Public.** SDK header `NuiSkeleton.h`: the field only.
- **Probe.** The same stance as DEP-5.
- **Bar.** **PASS** if it is non-zero and within 0.1° of −accel. A zero vector is NO RESULT, never "same".
- **Value / prior-art risk.** LOW. / LOW.
- **Setup.** small · no system change · `atlas/gravity_probe.py`.

---

## 4. Microphones

### AUD-1 · rank 5 — Microphone positions and SDK channel order on model 1414

- **Unknown.** The mic spacing along the bar, and which SDK channel is which mic.
- **Public.** [A hobbyist measurement on a model 1473](http://giampierosalvi.blogspot.com/2013/12/ms-kinect-microphone-array-geometry.html):
  x = +113 / −36 / −76 / −113 mm. Microsoft publishes none.
- **Probe.** Endfire claps in quiet surroundings: stand ~1 m beyond one end of the bar, in line with it, hands at bar height; 5 claps
  ~2 s apart; then the same at the other end. Four-channel exclusive WASAPI capture, analysed in memory; GCC-PHAT with 8× upsampling.
- **Bar.** **PASS** if the spacings are 149 / 40 / 37 mm (226 mm total) within ±5 mm and the lag signs flip between ends. **FAIL**:
  publish the measured spacings.
- **Value / prior-art risk.** HIGH: the first 1414 geometry; it also corrects an earlier "2 channels" reading, which was the Windows
  default mix. / LOW–MED.
- **Setup.** small · no system change · `atlas/wasapi_probe.py` (set `KINECT_MIC_ENDPOINT_ID`).

### AUD-2 · rank 15 — Is the DMO array-mode E_FAIL caused by our binding or by the host?

- **Unknown.** The audio DMO's array mode (the only mode with beam and source angle) fails to start with `E_FAIL`. Our code, or the
  host?
- **Public.** [jj131026 Audio Stream](https://learn.microsoft.com/en-us/previous-versions/windows/kinect-1.8/jj131026(v=ieb.10)): the
  DMO path gives beamforming and source angle.
- **Probe.** Run the Developer Toolkit's Audio Basics-D2D sample. Stand ~1.5 m away front-left and clap 3 times, then front-right and
  clap 3 times.
- **Bar.** The on-screen beam indicator moves: our binding is at fault. It does not: a host / DMO issue.
- **Value / prior-art risk.** MED: gates AUD-4 and AUD-5, and is a Windows 11 compatibility fact. / LOW.
- **Setup.** small · no system change · `atlas/dmo_probe.py`.

### AUD-3 · rank 16 — Is the default 2-ch / 48 kHz stream a plain downmix, and does its processing break the DMO?

- **Unknown.** Whether the default-mode stream is a fixed downmix of the four mics or is processed by the endpoint's audio-effects
  pack, and whether that processing is why the DMO's array mode fails.
- **Public.** [hh855374 AudioCaptureRaw](https://learn.microsoft.com/en-us/previous-versions/windows/kinect-1.8/hh855374(v=ieb.10)):
  describes the output as a standard 4-channel .wav.
- **Probe.** (a) Default-mode and RAW streams together, 10 s of ambient sound, in memory; regress each 2-ch output on the 4 mics after
  resampling. (b) Turn the endpoint's audio enhancements off, repeat, then turn them back on.
- **Bar.** (a) **PLAIN DOWNMIX** if R² > 0.99 with a fixed matrix; **PROCESSED** if R² < 0.9. (b) **CAUSE FOUND** if the default mix
  becomes 4 ch / 16 kHz and array mode starts.
- **Value / prior-art risk.** MED. / LOW.
- **Setup.** (a) none; (b) small · (a) no system change; (b) toggles a Windows audio setting, reversible · `atlas/wasapi_probe.py`,
  `atlas/dmo_probe.py`.

### AUD-4 · rank 34 — Beam and source-angle accuracy

- **Unknown.** How accurate the DMO's beam choice and source angle are.
- **Public.** [DAGA 2012](https://pub.dega-akustik.de/DAGA_2012/data/articles/000110.pdf): tracks within ±50° with an offset; no numeric
  error.
- **Probe.** Only once AUD-2/3 have array mode running. Floor marks at 1.5 m for −40 / −20 / 0 / +20 / +40°: x = −0.96 / −0.51 / 0 /
  +0.51 / +0.96 m and y = 1.15 / 1.41 / 1.50 / 1.41 / 1.15 m. Five impulsive taps at each (e.g. a spoon on a mug); record the DMO's
  GetPosition / GetBeam and an independent 4-channel estimate.
- **Bar.** **PASS** if the median |error| ≤ 5° and GetBeam returns the nearest 10° beam.
- **Value / prior-art risk.** MED. / MED.
- **Setup.** session (about 15 min) · no system change · `atlas/dmo_probe.py`, `atlas/wasapi_probe.py`.

### AUD-5 · rank 54 — AEC / NS performance, and where it runs

- **Unknown.** How much echo cancellation and noise suppression deliver, and whether they run on the device or the host (Microsoft's
  pages disagree).
- **Public.** [jj131033](https://learn.microsoft.com/en-us/previous-versions/windows/kinect-1.8/jj131033(v=ieb.10)): describes AEC and
  NS as running on the Kinect itself.
- **Probe.** After AUD-2: pink noise through the PC speakers; DMO mode 4 vs mode 2; echo-return-loss enhancement computed in memory.
- **Bar.** **AEC WORKS** if the enhancement is ≥ 20 dB.
- **Value / prior-art risk.** LOW. / LOW.
- **Setup.** none (plays sound through the speakers) · no system change · `atlas/dmo_probe.py`.

### AUD-6 · rank 55 — Array self-noise at the current gain

- **Unknown.** The array's self-noise at the default endpoint gain, given Microsoft's own note that the default is too high.
- **Public.** [jj663798 known issues](https://learn.microsoft.com/en-us/previous-versions/windows/kinect-1.8/jj663798(v=ieb.10)): the
  default gain of 100 is higher than optimal; the advice is 3.
- **Probe.** Read the endpoint level (no change). Measure per-channel self-noise in dBFS in quiet surroundings, and report. Changing the
  gain is a separate, reversible setting change.
- **Bar.** Descriptive (report the numbers); fix a bar before any gain change.
- **Value / prior-art risk.** LOW. / LOW.
- **Setup.** none · no system change · `atlas/wasapi_probe.py`.

---

## 5. Colour camera

### COL-1 · rank 6 — Are RAW_BAYER and COLOR linear?

- **Unknown.** Whether the colour outputs are linear in light, as documented, or carry a tone curve.
- **Public.** [jj131027 Color Stream](https://learn.microsoft.com/en-us/previous-versions/windows/kinect-1.8/jj131027(v=ieb.10)): calls
  RGB and Bayer linear. Never tested; the Xbox initialisation sequence writes a gamma knee table.
- **Probe.** `atlas/colour_ptc.py` under a bright, steady lamp, central half of the field. Premise: ≥ 60 DN, steady within ±2 %.
  Wait for auto-exposure to settle.
- **Bar.** **LINEAR-LIKE** if the variance-vs-mean slope is ≥ 0.6 in all 4 Bayer phases; **TONE-CURVE** if ≤ 0.2 in all 4 with low-bin
  variance ≤ 10 DN²; otherwise NO VERDICT.
- **Value / prior-art risk.** HIGH: settles a claim in this repository's README and Microsoft's wording. / LOW.
- **Setup.** small · no system change · `atlas/colour_ptc.py`.

### COL-2 · rank 7 — Is white balance applied on the mosaic?

- **Unknown.** Whether per-channel white-balance gains are applied before the Bayer output.
- **Public.** [OpenKinect Protocol_Documentation](https://openkinect.org/wiki/Protocol_Documentation): the Xbox initialisation turns
  AWB on; the SDK's initialisation is unknown.
- **Probe.** The same still scene under a warm lamp, then under a white LED or daylight; `atlas/colour_ptc.py` gain ratios (rule P2).
- **Bar.** **AWB-ON-MOSAIC** if the B/G gain ratio changes by > 25 % while the grey-world B/G stays within ±15 %; **NO-AWB** if it
  changes by < 10 %.
- **Value / prior-art risk.** HIGH: backs or refutes the "un-white-balanced" correction. / LOW.
- **Setup.** small · no system change · `atlas/colour_ptc.py`.

### COL-3 · rank 25 — Is COLOR 1280 a demosaic of RAW_BAYER 1280, and does 1280 Bayer show compression?

- **Unknown.** Whether COLOR 1280 is simply a demosaic of RAW_BAYER 1280 (as it is at 640), and whether 1280 Bayer shows the
  compression Microsoft describes.
- **Public.** [jj131027](https://learn.microsoft.com/en-us/previous-versions/windows/kinect-1.8/jj131027(v=ieb.10)): says 1280×960
  Bayer is compressed and converted to RGB before transmission.
- **Probe.** `atlas/colour_probe.py b1280`, bright light, 60 frames. Compression: full-band vs half-band R−G at R sites on a coloured,
  detailed target, plus the block-grid test (O4b in `atlas/colour_offline2.py`).
- **Bar.** **IDENTITY** if the slope is 0.95–1.05 and |intercept| ≤ 3 DN in all 4 phases (Deming regression). Compression: bars fixed
  before looking.
- **Value / prior-art risk.** MED: settles "raw" against Microsoft's own note. / LOW.
- **Setup.** small · no system change · `atlas/colour_probe.py`, `atlas/colour_offline2.py`.

### COL-4 · rank 29 — Is lens shading corrected on-chip, and by how much?

- **Unknown.** The corner-to-centre response of the colour path.
- **Public.** [Protocol_Documentation](https://openkinect.org/wiki/Protocol_Documentation): the Xbox initialisation enables lens-shading
  correction.
- **Probe.** One sheet of paper held flat against the colour window as a diffuser, the lamp ~50 cm away shining straight at it; 60
  RAW_BAYER 1280 frames.
- **Bar.** **CORRECTED** if corner/centre ≥ 0.9; **UNCORRECTED** if ≤ 0.7.
- **Value / prior-art risk.** MED–LOW. / LOW.
- **Setup.** small · no system change · `atlas/colour_probe.py`.

### COL-6 · rank 31 — Does the IR-cut filter also block 940 nm?

- **Unknown.** The colour camera's response at 940 nm (at 830 nm it sees nothing of the projector's dots, bound 0.22 DN rms).
- **Public.** No measured transmission found; the filter's presence is asserted in
  [arXiv 1812.09595](https://arxiv.org/abs/1812.09595) (found by search, not read in full).
- **Probe.** A consumer IR remote control (940 nm) 20 cm from the colour window, pointed at it: press and hold 5 s, release 5 s, three
  times; RAW_BAYER.
- **Bar.** **LEAKS** if > 5 DN above background in any channel; otherwise **BLOCKED** to 5 DN.
- **Value / prior-art risk.** LOW–MED: with the 830 nm null, the first measured bounds. / LOW.
- **Setup.** small · no system change · `atlas/colour_probe.py`.

### COL-8 · rank 37 — Is the 1280 frame rate set by the camera or by USB bandwidth?

- **Unknown.** The 1280 modes deliver 10.22 fps, not the SDK's "Fps12" label. Is the limit the camera or the USB load? (A capability
  number.)
- **Public.** [jj131027](https://learn.microsoft.com/en-us/previous-versions/windows/kinect-1.8/jj131027(v=ieb.10)): labels the mode
  Fps12.
- **Probe.** 20 s of RAW_BAYER 1280 with depth off, then 20 s with depth on.
- **Bar.** **BUS** if depth-off is within 0.5 fps of 12 and depth-on is lower; **CAMERA** if depth-off stays below 11.
- **Value / prior-art risk.** LOW–MED: corrects Microsoft's label with a cause. / MED (libfreenect reports ~10).
- **Setup.** none · no system change · `atlas/colour_probe.py`.

### COL-5 · rank 51 — The SDK's YUV→RGB matrix and range

- **Unknown.** Which matrix and range the SDK uses to turn UYVY into RGB.
- **Public.** [jj131027](https://learn.microsoft.com/en-us/previous-versions/windows/kinect-1.8/jj131027(v=ieb.10)): UYVY,
  gamma-corrected; no matrix.
- **Probe.** A lamp plus red, green and blue matte objects in a still scene; `atlas/colour_probe.py yuv`.
- **Bar.** **BT.601-FULL** if every coefficient is within 3 % of JFIF; **STUDIO** if luma stays in 16–235 while COLOR clips.
- **Value / prior-art risk.** LOW. / LOW.
- **Setup.** small · no system change · `atlas/colour_probe.py`.

---

## 6. IR camera, projector and laser

### IR-6 · rank 9 — Does the laser mode-hop, and how often?

- **Unknown.** Whether the projector laser mode-hops during warm-up, and the hop rate.
- **Public.** [OpenNI2 XnHostProtocol.h](https://raw.githubusercontent.com/structureio/OpenNI2/master/Source/Drivers/PS1080/Sensor/XnHostProtocol.h):
  PS1080 hop counters (nIsHop, nCurrentHopsCount); that driver enumerates the PrimeSense USB vendor ID only.
- **Probe.** A cold-start warm-up run of about 100 min. The ruler is the vertical row span between the pattern's tile-centre
  (registration) dots, a depth-free measure of pattern scale; every one of those dots must land on one bare matte wall (~1.5–2 m; find
  the pose beforehand and tape the base's footprint). Leave the sensor unpowered ≥ 3 h; plugging it in is the start. Still air (no
  fan, heater or air-conditioning), nobody in view, a thermometer beside the sensor read at start and end. Every 3 min for 90 min, a
  ≤ 30 s burst of IR + depth plus a 30 s accelerometer read. Freeze the ruler analysis before the run. Gate: burst-mean scale SD ≤ 3e-5
  (single frames give ~1.4e-4, so use burst means of ≥ ~25 frames).
- **Bar.** **PASS** if there is at least one step > 10σ above the smooth trend (between bursts, or inside a burst within 2 frames),
  with the same sign on every dot pair, and a depth ramp pivoting on column 323.1 − 43 186/z. **FAIL**: publish a 95 % bound on the hop
  rate.
- **Value / prior-art risk.** HIGH: no Kinect v1 hop measurement is published. / MED: hops are textbook laser physics; the Kinect number
  is not published.
- **Setup.** session (IR-7 shares the run; ACC-4, NSE-5, NSE-7 and IR-3 ride it) · no system change · `atlas/ir_pattern_vscale.py`,
  `atlas/ir_regdots.py`.

### IR-7 · rank 10 — How much does pattern scale change during warm-up, and does it explain the +8 mm drift?

- **Unknown.** The size of the pattern-scale change during warm-up, and whether it accounts for the published warm-up depth drift
  (+8 mm on our unit).
- **Public.** [Fiedler & Müller 2012](https://link.springer.com/chapter/10.1007/978-3-642-40303-3_3): temperature changes range
  (abstract; no pattern scale).
- **Probe.** The same run as IR-6.
- **Bar.** **PASS** if the measured Δs predicts the drift's column slope within ±30 % and the zero column lies within ±20 px of
  323.1 − 43 186/z_wall. **FAIL** if the drift is uniform across columns (slope < 10 % of the prediction).
- **Value / prior-art risk.** HIGH: a mechanism for a published drift (the drift itself is not new). / MED.
- **Setup.** session (same run as IR-6) · no system change · `drift.py`, `warmup.py`, `atlas/ir_pattern_vscale.py`.

### IR-3 · rank 12 — Is the projected pattern the same on every unit?

- **Unknown.** Whether this unit projects the pattern Reichinger published, i.e. whether the pattern is identical across units.
- **Public.** [Reichinger 2011](https://azttm.wordpress.com/2011/04/03/kinect-pattern-uncovered/): believes it is the same on every
  unit; no comparison made.
- **Probe.** 100 IR frames of a bare matte wall filling the view, square to it at ≥ 1.5 m. Rectify (rows fixed, columns c_inf − K/z),
  rebuild the central tile, and similarity-fit it to the published pattern (a download).
- **Bar.** **PASS** if ≥ 90 % of our bright spots fall within 0.5 grid unit; **FAIL** if ≤ 20 % (chance is ~11 %); in between, NO
  VERDICT.
- **Value / prior-art risk.** HIGH: a 15-year-old assertion never tested. / MED–LOW.
- **Setup.** rides IR-6 (end of run) or NSE-1 · no system change · `atlas/ir_regdots.py`.

### IR-5 · rank 24 — IR black level, the per-frame pedestal and the 1019–1021 ceiling

- **Unknown.** The IR camera's black level, the per-frame pedestal that jumps with the ceiling, and whether that pedestal touches depth.
- **Public.** [libfreenect cameras.c](https://raw.githubusercontent.com/OpenKinect/libfreenect/master/src/cameras.c): 10-bit IR modes;
  no black level or ceiling.
- **Probe.** (a) 900 frames of IR + depth of an ordinary scene. (b) Cover the IR camera window with a folded square of aluminium foil
  held flat for 20 s, without touching the head or its hinge.
- **Bar.** (a) **CEILING PASS** if no value exceeds 1021 and the clip level tracks the dark level (r ≥ 0.9); **DEPTH-NEUTRAL** if
  |r(pedestal, global depth mean)| < 0.1. (b) **SINGLE-CODE** if ≥ 99 % of covered pixels share one code per frame; **PEDESTAL LOOP**
  if per-frame dark means step in whole codes with SD ≥ 0.5 code.
- **Value / prior-art risk.** MED–LOW: photometry rules (saturation starts at 1019; remove the pedestal). / LOW.
- **Setup.** (a) none; (b) small · no system change · `ir_ceiling.py`.

### IR-9 · rank 28 — Does IR brightness auto-adjust (AGC / AE)?

- **Unknown.** Whether the IR camera changes its gain or exposure with scene content.
- **Public.** [OpenNI2 PS1080.h](https://raw.githubusercontent.com/structureio/OpenNI2/master/Include/PS1080.h): PARAM_DEPTH_AGC,
  default gain 50; the Kinect's behaviour is unstated.
- **Probe.** Hold a white sheet ~40 cm in front of the sensor over the LEFT half of the view for 10 s, then remove it. Nothing in the
  right half. IR, 20 s.
- **Bar.** **NO AGC** if the untouched wall level moves ≤ 1 % while the frame mean moves ≥ 20 %; **AGC** if the wall moves ≥ 5 %
  against the frame mean within 30 frames.
- **Value / prior-art risk.** MED. / LOW.
- **Setup.** small · no system change · `atlas/ir_agc_check.py`.

### IR-4 · rank 32 — Field distortion of the pattern and its −1.1° roll

- **Unknown.** How well the projected pattern follows sine-space tiling through a pinhole, across the field.
- **Public.** [US8384997](https://patents.google.com/patent/US8384997B2/en): sine-space tiling; no measured map.
- **Probe.** Fit every bright spot in IR-3's capture to sine-space tiling + pinhole.
- **Bar.** **PASS** if the rms residual is ≤ 0.2 px over the field; otherwise publish the residual map.
- **Value / prior-art risk.** MED: feeds IR-6/7 and IR-8. / LOW.
- **Setup.** none (after IR-3) · no system change.

### IR-10 · rank 36 — Are the nine bright dots a rigid angular grid?

- **Unknown.** Whether the nine bright registration dots move exactly as column = c_inf − K/z with a fixed row.
- **Public.** [OpenKinect Imaging_Information](https://openkinect.org/wiki/Imaging_Information): notes nine much brighter dots in a
  regular grid and suggests they might be useful; the question is left open.
- **Probe.** Rides DEP-1: the centre dot on the board at 9 taped stations.
- **Bar.** **PASS** if the column residual is ≤ 0.3 px from a 1/z fit whose slope equals K within ±1 %, and the row is constant within
  0.3 px. **FAIL** if the slope is off by > 5 %.
- **Value / prior-art risk.** LOW–MED: answers the wiki's open question and gives K from taped z. / LOW.
- **Setup.** rides DEP-1 · no system change · `atlas/ir_regdots.py`.

### IR-12 · rank 46 — Is a separate zero-order spot visible above the tile-centre dots?

- **Unknown.** Whether the diffractive element's zero order shows as an extra-bright centre dot.
- **Public.** [US8384997](https://patents.google.com/patent/US8384997B2/en): zero order ≤ 1 %.
- **Probe.** Rides the far-wall session (CAL-2 / DEP-3): wall ≥ 2.5 m away, so no centre dot clips.
- **Bar.** **VISIBLE** if the centre dot is ≥ 1.5 × the median of the other 8; **NOT** if within ±20 %.
- **Value / prior-art risk.** LOW–MED. / LOW.
- **Setup.** rides CAL-2 / DEP-3 · no system change · `atlas/ir_regdots.py`.

---

## 7. Depth noise and quantisation

### NSE-1 · rank 11 — Are the ⅛-px disparity codes equal width?

- **Unknown.** Whether all sub-pixel disparity codes are equally wide (differential non-linearity, peak-locking).
- **Public.** [Chatterjee & Govindu 2015, arXiv 1505.01936](https://arxiv.org/abs/1505.01936): a noise model; no per-code widths.
- **Probe.** A bare wall. Turn the base ~45° to the wall (the nearest wall point in view ≥ 1.0 m) and wedge a paperback under one side so
  the sensor rolls ~20–30°: the iso-depth bands must run diagonally and span ~200 codes. Freeze and hash the analysis before capture.
  Capture; change yaw and roll to a second tilt; capture again.
- **Bar.** **PASS** if the period-8 DNL is ≥ 0.15 step, with the same phase at both tilts, p < 0.001. **NULL** if all codes are within
  0.05. Both are publishable.
- **Value / prior-art risk.** HIGH: nobody has measured code widths. / LOW.
- **Setup.** session (a bare-wall block of about 40 min, with NSE-2 and IR-3) · no system change · `code_density.py`.

### IR-8 · rank 14 — Is the frame-to-frame correlated depth noise a whole-field pattern-scale jitter?

- **Unknown.** The origin of the correlated noise (detrended ACF ~0.15 at lags 1–8 frames) that limits averaging.
- **Public.** [Choo et al. 2014](https://pmc.ncbi.nlm.nih.gov/articles/PMC4208232/): σ(i, j, z) with a radial term; no cross-pixel
  correlated-noise model.
- **Probe.** Offline, on 90 s still-scene depth captures. Per frame, fit a + b(x − x0) + c(y − y0) in disparity, with
  x0 = 323.1 − 43 186/z.
- **Bar.** **PASS** if b carries ≥ 50 % of the lag 1–8 autocovariance and the SD-minimum column is within ±20 px of x0. **FAIL** if
  ≤ 10 %.
- **Value / prior-art risk.** MED–HIGH: a physical origin for the noise that limits averaging. / LOW–MED.
- **Setup.** none (offline) · no system change · `acf_gate.py`, `correlated.py`.

### NSE-2 · rank 30 — Are the vertical bands in noise maps rung boundaries, not pattern repetition?

- **Unknown.** What causes the vertical stripes seen in per-pixel noise maps.
- **Public.** [Choo et al. 2014](https://pmc.ncbi.nlm.nih.gov/articles/PMC4208232/): attributes the stripes to the repeating
  structured-light pattern.
- **Probe.** Rides NSE-1: square to the wall at 1.0 m, then 1.5 m, then with a 3° yaw at 1.5 m; 1000 frames each, in ≤ 30 s bursts.
  Compare the entropy map with the predicted dither probability; the yaw gives a predicted band spacing.
- **Bar.** **PASS** if the rank correlation is ≥ 0.6 and the spacing is within 20 % of the prediction.
- **Value / prior-art risk.** MED: would correct a published attribution (bands on a slanted plane are expected). / MED–HIGH (may be
  folk knowledge).
- **Setup.** rides NSE-1 · no system change.

### NSE-3 · rank 41 — Does pixel position add to the range-only noise predictor?

- **Unknown.** Whether a radial term improves the range-only σ predictor (R² 0.574).
- **Public.** [Choo et al. 2014](https://pmc.ncbi.nlm.nih.gov/articles/PMC4208232/): σ(i, j, z) with a radial term.
- **Probe.** Add a radial term to `predictor.py`, on still-scene captures.
- **Bar.** **POSITION MATTERS** if ΔR² ≥ 0.05; **RANGE-ONLY HOLDS** if ΔR² < 0.01.
- **Value / prior-art risk.** LOW–MED: needed before citing Choo or Sarbolandi against the range-only model. / MED.
- **Setup.** none · no system change · `predictor.py`.

### NSE-4 · rank 42 — Averaging gain as a function of window length

- **Unknown.** The averaging gain as a curve over window length N, replacing a single "1.8×" figure.
- **Public.** [Sarbolandi et al. 2015 §4.1](https://ar5iv.labs.arxiv.org/html/1505.05459): notes that per-pixel temporal statistics are
  hard to estimate under structured-light quantisation.
- **Probe.** On 90 s still-scene data: measured gain(N) for N = 1–300 against the curve implied by the ACF.
- **Bar.** **PASS** if within 10 % at every N. Publish the curve, not one number.
- **Value / prior-art risk.** LOW: a wording fix with a curve. / LOW.
- **Setup.** none · no system change · `sigma_n.py`, `analyse_sigma.py`.

### NSE-5 · rank 47 — Is the pinned per-pixel bias a frozen pattern that reshuffles when the wavelength changes?

- **Unknown.** Whether the static per-pixel depth bias is speckle-like and changes with the laser wavelength.
- **Public.** Dorsch, Häusler & Herrmann 1994, on the speckle limit of laser triangulation (no link; not re-read for this list).
- **Probe.** Rides IR-6: pinned-bias maps cold vs warm, and across any hop.
- **Bar.** **RESHUFFLES** if the cold–warm map correlation is < 0.5 while two maps from the warm end correlate ≥ 0.9; **STATIC** if
  ≥ 0.9 across warm-up.
- **Value / prior-art risk.** MED–LOW. / MED.
- **Setup.** rides IR-6 · no system change.

### NSE-6 · rank 52 — Does lateral edge noise depend on sub-pixel edge position?

- **Unknown.** Whether depth-edge jitter varies with where the edge falls inside a pixel.
- **Public.** [Osvaldova et al. 2024, arXiv 2402.16514](https://arxiv.org/abs/2402.16514).
- **Probe.** Rides IR-1: at 1.0 m centre, lean the post so the card rolls ~5° in its own plane; IR + depth, 30 s.
- **Bar.** **PHASE-DEPENDENT** if edge σ varies ≥ 2× with sub-pixel phase; **FLAT** if < 1.3×.
- **Value / prior-art risk.** LOW–MED. / MED.
- **Setup.** small (rides IR-1) · no system change · `four_edges.py`.

### NSE-7 · rank 53 — Is air draft the cause of the unexplained ~4 mm drift excursion?

- **Unknown.** The cause of one ~4 mm excursion in our warm-up drift data.
- **Public.** [Fiedler & Müller 2012](https://link.springer.com/chapter/10.1007/978-3-642-40303-3_3): air draft affects range.
- **Probe.** End of IR-6's run, warm: a fan blowing across the sensor, 2 min on / 2 min off, twice; static wall.
- **Bar.** **EFFECT** if wall depth shifts ≥ 2 mm with the fan and returns; **NULL** if < 0.5 mm.
- **Value / prior-art risk.** LOW: a known effect; it would explain an excursion in our own data. / HIGH.
- **Setup.** rides IR-6 · no system change · `drift.py`.

### NSE-8 · rank 56 — Sub-code transfer curve

- **Unknown.** The duty cycle between neighbouring codes as a function of position within one code.
- **Public.** [Qi et al. 2014](https://pmc.ncbi.nlm.nih.gov/articles/PMC3958284/).
- **Probe.** Only if NSE-1 passes: a paper-ream stage moved in one-sheet (~0.1 mm) steps across one code.
- **Bar.** To be fixed after NSE-1, before this capture.
- **Value / prior-art risk.** LOW; sub-code claims are easy to over-read, so the bar must be high. / MED.
- **Setup.** session · no system change.

---

## 8. Materials

### MAT-2 · rank 21 — Surface bias of milky or dyed water vs concentration

- **Unknown.** How far the measured water surface sits from the true surface as a function of milk or pigment concentration.
- **Public.** [Nichols et al. 2020](https://pmc.ncbi.nlm.nih.gov/articles/PMC7349220/): TiO₂ only, at 0–0.0162 %; they note that
  concentration must be taken into account.
- **Probe.** A flat-bottomed tub ≥ 30 cm across. The sensor looks down from 1.2–1.5 m at an angle (motor at about −20°, or a wedge) so
  the water surface is not square to the optical axis. A small white card glued to a foam slice floats as the true surface; a paper
  stack is the positive control. Ladder: 0 → 0.1 → 0.3 → 1 → 3 → 10 → 30 % whole milk, then white acrylic paint; 60 frames each, with
  the floating card at every step. Keep liquids ≥ 1 m from the electronics.
- **Bar.** **EFFECT** if a bias ≥ 1 mm falls with concentration (Spearman ≤ −0.9). **NULL** if |bias| ≤ 0.5 mm.
- **Value / prior-art risk.** MED–HIGH: flume labs still run v1s and validate against nominal depth. / MED.
- **Setup.** session (about 60 min) · no system change.

### MAT-1 · rank 43 — How many sheets of paper over the black board until depth drops out?

- **Unknown.** The scattering curve of stacked paper: valid depth and IR dot width vs sheet count.
- **Public.** [Sarbolandi et al. 2015 §4.6](https://ar5iv.labs.arxiv.org/html/1505.05459): a milk series; no sheet count.
- **Probe.** The black board at 1.0 m centre: bare, then 1, 2 and 3 Letter sheets laid flat over its face (tape 2 corners); depth + IR,
  10 s each.
- **Bar.** **PASS** if the valid fraction falls monotonically and crosses 50 % at one count, and IR dot width grows monotonically.
  Non-monotonic twice: discard.
- **Value / prior-art risk.** LOW–MED: a scattering curve instead of one plastic object. / MED.
- **Setup.** small · no system change.

---

## 9. Hardware route: libfreenect / UsbDk — needs a USB driver change; reversible

Everything above runs on stock SDK 1.8. The probes in this section need libfreenect talking to the sensor through the UsbDk filter
driver. That is a system change, but a reversible one: UsbDk filters the device without replacing the SDK's driver binding (Zadig /
WinUSB would replace it; do not use Zadig). libfreenect and the SDK cannot hold the device at the same time.

**What it unlocks**

1. **Raw 11-bit disparity (shift) frames.** DEP-9; NSE-1 on raw codes, free of the SDK's 1 mm floor that merges codes nearer than 1 m;
   a direct check of whether the SDK ever drops or merges codes.
2. **IR at 1280×1024 and 640×488.** IR-13; IR-3 and IR-4 at full resolution, where neighbouring dots no longer merge; about twice the
   precision for IR-6's ruler.
3. **The device's own factory calibration over USB**, from the reg_info and zero-plane reads in libfreenect's `cameras.c`: a
   byte-for-byte comparison with the SDK blob's 118-byte block, 120.0, 0.1042 and const_shift 200; the two constants the blob lacks
   (DCMOS–emitter distance 7.5 and DCMOS–RCMOS distance 2.3), which settles the SDK's hard-coded 2.4 from the device side; raw
   accelerometer 0x32 counts (ACC-5, and issue #7 from the device side).
4. **TEC / emitter reads (IR-14)**, read-only.
5. **Smaller:** colour at 1280×1024 (COL-9); the tilt state byte (ACC-7); the projector register 0x105 (IR-15, a device write); raw
   32-bit audio plus the device's "cancelled" stream (libfreenect uploads audio firmware to the device's RAM at run time, which is also a
   device write).

**Procedure**

- **Before.** Record an SDK baseline: `sensor.py`'s `verify()`, the capability map (`capmap.py`: 13 of 28 pairs), the calibration
  blob's sha256 (`blob_dump.py`), and a depth value set checked against the exact table (`lattice_closure.py`).
- **Install.** UsbDk from its official release page; libfreenect built from source or from an official build.
- **Probes.** Order: device calibration read → raw disparity of a static scene (then the SDK on the same scene) → IR 1280 / 488 → TEC
  reads. Read opcodes only. Never flash firmware or write set points. Treat any device write (register 0x105, the audio firmware upload)
  as a separate, deliberate step.
- **After.** Uninstall UsbDk and replug the sensor (reboot if asked). Re-run the baseline: it must match exactly (13 / 28, the same blob
  hash, every value on the table). Report the before/after check with your results.

### DEP-9 · rank 19 — Same-unit proof of the SDK / OpenNI half-step

- **Unknown.** Whether, on one unit and one scene, the SDK table sits at phase 0 and the open drivers' −0.375 puts them at phase 0.5
  (half a rung apart).
- **Public.** [DiFilippo & Jouaneh 2015](https://doi.org/10.1109/JSEN.2015.2422611): the SDK reads farther than OpenNI on the same unit;
  no mechanism.
- **Probe.** The same static scene: libfreenect raw 11-bit shift, then SDK millimetres (sequentially).
- **Bar.** **PASS** if one constant maps shift to the SDK rung index on ≥ 95 % of stable pixels and libfreenect's own millimetres sit
  half a rung away.
- **Value / prior-art risk.** HIGH: turns an inference from an Xtion-class recording plus a figure match into a same-unit proof. / LOW.
- **Setup.** none after install · driver change · `lattice_closure.py`.

### IR-14 · rank 20 — Does the Kinect firmware answer the PS1080 TEC / emitter / hop-counter reads?

- **Unknown.** Whether the Kinect's firmware answers read requests for TEC set point, measured temperature and duty, emitter set point
  and photodiode, and the wavelength-correction hop counters (IsHop).
- **Public.** [OpenNI2 PS1080.h](https://raw.githubusercontent.com/structureio/OpenNI2/master/Include/PS1080.h): the fields exist;
  wavelength correction needs firmware ≥ 5.2. The OpenNI2 PS1080 driver only enumerates PrimeSense's vendor ID (0x1D27).
- **Probe.** Read-only opcode queries through libfreenect's command path; never a write.
- **Bar.** **ANSWERS** if the structs come back with plausible values; then log them beside an IR-6 rerun (hop counter vs optical
  steps), which gives that run a real temperature axis.
- **Value / prior-art risk.** HIGH if it answers: a real temperature axis and a counter check on IR-6/7. / LOW.
- **Setup.** none after install · driver change.

### IR-13 · rank 57 — Which 480 of the 488 IR rows does the SDK deliver? Is SDK IR a 2×2 bin of 1280×1024?

- **Unknown.** The SDK's IR crop, and whether its 640-wide IR is binned from the full sensor.
- **Public.** [libfreenect cameras.c](https://raw.githubusercontent.com/OpenKinect/libfreenect/master/src/cameras.c): IR at 640×488 and
  1280×1024 (~10 fps).
- **Probe.** libfreenect frames vs SDK IR of the same static scene.
- **Bar.** **ROWS** = the best row offset at NCC ≥ 0.98; **BINNED** if the 2×2 mean of 1280 matches 640 at NCC ≥ 0.98.
- **Value / prior-art risk.** LOW–MED. / LOW.
- **Setup.** none after install · driver change.

### COL-9 · rank 58 — Which 960 of the 1024 colour rows the SDK delivers

- **Unknown.** The SDK's crop of the 1280×1024 colour array.
- **Public.** [Protocol_Documentation](https://openkinect.org/wiki/Protocol_Documentation): a 1024-row array.
- **Probe.** libfreenect 1280×1024 vs SDK 1280×960 of the same scene; NCC row offset. CAL-3's cy is a weak independent hint.
- **Bar.** Report the best row offset; fix an NCC threshold before looking (IR-13 uses 0.98).
- **Value / prior-art risk.** LOW. / LOW.
- **Setup.** none after install · driver change.

### ACC-7 · rank 59 — What GetAngle computes (smoothing, truncation)

- **Unknown.** How the SDK's integer tilt angle is derived from the device.
- **Public.** [hh855454](https://learn.microsoft.com/en-us/previous-versions/windows/kinect-1.8/hh855454(v=ieb.10)): the angle is
  relative to gravity; libfreenect's `tilt.c` reads a state byte in half-degrees.
- **Probe.** The device's tilt byte vs the SDK integer across MOT-1's stops.
- **Bar.** Not yet fixed: write one before the capture.
- **Value / prior-art risk.** LOW. / LOW.
- **Setup.** none after install · driver change.

### IR-15 · rank 60 — Projector off / auto-cycle (register 0x105) on Xbox hardware, outside the SDK

- **Unknown.** Whether the projector can be switched off on an Xbox 360 unit through libfreenect.
- **Public.** [jj663867](https://learn.microsoft.com/en-us/previous-versions/windows/kinect-1.8/jj663867(v=ieb.10)): the SDK's
  emitter-off does not work with Xbox 360 sensors.
- **Probe.** A libfreenect register **write**: a device write, beyond this section's read-only rule, so a separate, deliberate step.
- **Bar.** **PASS** if the IR stream shows no dots with the projector off.
- **Value / prior-art risk.** LOW–MED: passive 830 nm imaging on Xbox units. / MED.
- **Setup.** none · driver change + device write.

### AUD-7 · rank 61 — What the "Audio Array Control" WinUSB interface carries

- **Unknown.** The traffic on the device's audio-array control interface.
- **Public.** None found.
- **Probe.** Needs a USB-capture filter driver, which is a second system change. Not recommended.
- **Bar.** Not yet fixed.
- **Value / prior-art risk.** LOW. / LOW.
- **Setup.** none · a second driver change.

---

## Pitfalls we hit

### Claims that are not new

- **Warm-up drift is published** (Fiedler & Müller 2012; Sarbolandi et al. 2015 §4.4; DiFilippo & Jouaneh 2015; Chow 2012, who reports
  at least an hour of warm-up). So is a 1.88 mm/°C figure (we have read only the abstract of that thermal paper). Laser mode hops are
  textbook. Bands on a slanted plane are what a horizontal baseline does. Publish measurements and mechanisms as new, never the
  phenomena.
- **The exact depth table is a verification, not a discovery:** libfreenect's `registration.c` already implements the formula. "266 /
  266", "259" and "345" are one function check, and Byte Kitchen (2014) already counted 345. What is ours is the phase-0 identification.
  The sign of the SDK/OpenNI half-step gap is DiFilippo & Jouaneh's (2015); ours is the mechanism, and it is fixed only modulo one rung.
  The OpenNI side rests on an Xtion-class recording.
- **The U(N) thermal story is retracted:** the cold values are a subset of the warm values, and the warm values are the table. U(N)
  measures scene coverage.
- **"Near limit 801 mm"** is the SDK's 800 mm clamp meeting the lattice (799 and 801 are rungs). The extended texture reaches 498–573 mm.
- **Lateral scale:** "~1 %" and "H/V agree" match the published nominals; the envelope is only good to ~1 %, and its sealed verdict was
  NO VERDICT; credit Kreylos (+1.5–2.8 %); the old "−3.4 %" came from a hand-taped reference. K = 345 489, not 345 316; the "73.79 mm
  at f 585" baseline is superseded.
- **Blob wording:** "the SDK's relational-parameters blob contains the PrimeSense factory block libfreenect reads". Never "decoded the
  factory calibration".
- **Capability claims:** near mode, emitter-off and 640-only IR are documented SDK limits (returned as
  `E_NUI_HARDWARE_FEATURE_UNAVAILABLE`). The SDK 1.6 notes document the 1280 Bayer format. "Genuinely raw, linear, un-white-balanced"
  is contradicted by Microsoft's compression note and by our own gain evidence. "Averaging gain 1.8×" needs its window length.
- **Surfaces:** the colour camera missing the projector dots is the IR-cut filter working. Single poses of glossy objects illustrate
  behaviour already described in words. Milky plastic is Sarbolandi §4.6 territory.
- **Web searches now return this repository;** prior-art checks will hit our own work.
- **Model 1473 numbers are not model 1414 numbers** (microphones, thermal behaviour, the SDK/OpenNI gap).

### SDK and API behaviour that fails silently

- **Opening COLOR while IR is open returns S_OK,** and the IR handle then carries colour frames. Check the buffer size and stream type on
  every frame.
- **SDK depth and IR are not registered** (~4 × 3 px, mirrored relative to every published offset). Compare outline widths, not
  positions, until IR-1 is settled.
- **Extended depth appears to wrap modulo 65 536** (confirmation pending, DEP-2): 4858 mm can be a ~70 m false match. Extended values
  > 4 m in a scene no deeper than 3 m were phantoms (persistence 0.02). Always use a persistence mask.
- **Mapper point input is plain mm, not mm << 3,** and depth ≥ 8192 wraps modulo 8192. The SDK's colour parallax stops growing at
  2047 mm.
- **SDK skeleton space and the inline helper use nominal f 571.2653 px and c (320, 240) on every unit,** so SDK point clouds cannot show
  a per-unit calibration. Use 571.2653 for skeleton space; 575.82 is PrimeSense zero-plane geometry, used only inside colour
  registration.
- **Depth sentinel values** are the header's 0 / 0x7FF8 / 0xFFF8 (an earlier `nui.py` had them wrong; fixed in v2.1). The capability
  map is 13 of 28 pairs, not 10.
- **Depth columns 0–7 are dead.** The principal point is the image centre, not the centre of the valid region.
- **IR saturates at ≥ 1019, not at 1023.** Remove the per-frame pedestal before any IR photometry. The dot count is ~34.7 k
  (Reichinger), not the ~38 k we first estimated.
- **The pattern centre is not a fixed column:** it is 323.1 − 43 186/z.
- **The colour camera cannot be locked** (settings are gated, 0x8301000F), so every colour probe must wait for auto-exposure to settle
  (> 3 s after a mode switch). RAW_BAYER 640 is resampled: do photometry at 1280. Mask blinking pixels at high gain. The 1280 modes
  deliver 10.22–10.23 fps (not 12, 10.7 or 10.4). The header's "YUY2" is really UYVY.
- **Mapper outputs are integers** (a ±0.5 px floor).
- **Audio:** "2 channels" is the host's default mix format; four channels come via exclusive WASAPI or shared + RAW. The DMO is mono,
  needs `CoInitializeEx` (MTA) first, and its array mode currently fails on our host. Enabling skeleton tracking after audio stops the
  audio stream. Microsoft's radian step (.0175) is a typo for 0.175, and two of its pages disagree on where AEC runs.
- **Motor:** SetAngle blocks the calling thread, so read sensors from a second thread. Space moves generously and never probe the
  lockouts (wear). The resting pitch wanders ±0.2° with no command (≈ 2 px at f 571; z tempco 3 mg/°C).
- **An all-zero vNormalToGravity** gives a NaN angle that once read as "same". Zero vectors are NO RESULT.
- **`E_NUI_DEVICE_IN_USE` (0x83010009)** when another process is streaming: run one probe at a time, and retry.

### Measurement design

- **A bar that any geometry passes is not a test.** Broadside ambient sound gave lag ≈ 0 for every microphone geometry. Fix a bar that
  can fail before the data, and label post-hoc work as post hoc.
- **Suspect the instrument first.** Our own past faults: a 20 m cap in our on-table check; spectral "peaks" at the detrend's own 65 px
  window; a planarity-filter change (disclosed in the README); the DMO used without `CoInitialize`.
- **Freeze the analysis before a confirmatory capture.** Code density's first attempt gave p from 0.02 to 0.27 across cleaning choices.
- **Code density:** the target must be large, rigid and flat; iso-code bands must run diagonal to the pixel grid (with bands along the
  rows, the counts jump by whole rows); stay ≥ 1 m, because the SDK's 1 mm floor merges codes nearer than that.
- **Time-averaged depth keeps the staircase** (pinned pixels). Averaged "distortion maps" partly encode the lattice.
- **Hops:** a depth step is not a hop, because firmware can rewrite depth. Call a hop only with an abrupt, global, same-sign vertical
  IR-scale step at the same moment. The per-frame ruler (median 1.4e-4) does not meet the 3e-5 gate; burst means do. The ruler needs
  every tile-centre dot on one matte wall.
- **Two stations cannot separate scale from offset:** use ≥ 4–5. A tape's 1/8 in resolution is ~2 % of a 6 in move. Yaw read from edge
  pixels is circular.
- **A horizontal-only edge shift is an epipolar assignment,** not an inset. Publish a shrink only after the offset is removed on all
  four edges.
- **The projector shadow falls to the RIGHT of near objects** in the SDK's mirrored image. On an IR-dark target the right-hand IR edge
  is the shadow's edge; use a white card for four-edge work.
- **Water:** a level surface square to the axis sits on one rung, so tilt the sensor. Checking against nominal tank depth or run-to-run
  repeatability cannot see a constant bias. Cold drift looks like "settling".
- **Accelerometer offset vs support tilt:** only a reversal separates them. One pose cannot split offset from gain.

### Scene and props

- **Hand-measured references limit every absolute-size test.** Use factory sizes (US Letter 215.9 × 279.4 mm; #10 envelope
  104.8 × 241.3 mm). Measure a printed checkerboard, because printers rescale.
- **Reflective surfaces under the target** (e.g. glass) mirror its lower edge into a 5–20 px smear and have their own dead zone. Keep
  targets on the post, clear of them.
- **Glossy surfaces** saturate the IR and leave depth holes. Printing at the edges and black print break IR edges. A cylinder's
  silhouette is made of tangent rays, which makes it a poor target.
- **Halogen, incandescent and daylight flood 830 nm.** Keep them out of depth and IR probes, except the IR checkerboard, where the
  projector is covered. LEDs are safe.
- **Keep the scene still:** recapture any frame with movement in view.
- **Air draft moves range:** no fans or moving air during depth work, except the NSE-7 test.

### Licence, safety and publication

- **SDK licence:** use documented APIs only. The Kinect for Windows SDK 1.8 licence forbids reverse engineering, decompiling and
  disassembling the software. State your method in any publication.
- **Hardware route:** never flash firmware or write set points; treat any device write as a separate, deliberate step; do not use
  Zadig.
- **Eye safety:** the projector is a Class 1 laser product (IEC 60825-1:2007 label); do not modify it.
- **Privacy:** post numbers, not raw captures of your surroundings or audio recordings. Truncate device serial numbers.
- **Credit:** cite the people who got there first; "ours" means the mechanism or the number, never the phenomenon.

---

## Already answered in v2.1 (see the README; no need to re-run on the same model)

- **Depth:** sentinel classes and low bits, and the runtime flag toggle; extended == packed >> 3 in range, and the class mapping; the
  mapper and skeleton space are nominal (f 571.2653, c (320, 240), the same on every unit); no default depth filter, and
  `NuiSetDepthFilter` rejects application objects; the player-index stream opens at 640 / 320 / 80 (13 of 28 pairs open); columns 0–7
  are dead and 320 is decimation (0, 1); the exact table (a verification, with 345 / 259 rungs); the half-step's size matches DiFilippo
  & Jouaneh's model-1414 gap (4.7 mm at 1800 mm).
- **Calibration blob:** stages 1–3 (layout, registration, what the blob drives).
- **IR:** K from the pattern within 0.74 %, with the baseline along the rows; IR + depth run together, and opening colour silently takes
  over the IR handle; value GCD 64.
- **Colour:** settings are gated (0x8301000F); the 1280 modes run at 10.22–10.23 fps; 640 is the same field as 1280; GRBG at 640; YUV is
  UYVY; 640 Bayer is resampled; 1280 noise is pixel-independent, with no block grid; the mapper is non-projective (descriptive); the
  projector dots do not reach the colour camera (bound 0.22 DN rms).
- **Accelerometer and motor:** output is exactly count/819, from 12-bit codes, |g| 1.015–1.018, w = 0; GetAngle is a smoothed integer;
  +5° lands at 5.10°.
- **Audio:** 4 channels via exclusive WASAPI or shared + RAW; the DMO outputs mono.
- **Lateral scale:** ~1 % (post hoc); the "−3.4 %" is retracted.

## Needs hardware or a unit we do not have

- **A second unit.** A cross-unit census would turn this single-unit list into a comparison: the depth value set, the calibration-blob
  layout, pattern identity (IR-3) and microphone geometry (AUD-1). If you have another 1414, a 1473 or a Kinect for Windows, those four
  are the most useful things you can run.
- **Another device:** the Orbbec Astra's depth lattice.
- **Applications:** the bed-change detection limit, and wet vs dry granular surfaces.
- **Instruments:** laser wavelength and linewidth (needs a spectrometer); laser power (needs a power meter). For eye safety, document the
  Class 1 / IEC 60825-1:2007 label only.
