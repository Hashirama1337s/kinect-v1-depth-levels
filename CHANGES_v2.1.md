# Changes in v2.1 (2026-09-27)

## README.md

- Title: "the hidden depth lattice" → "the depth lattice" (the lattice is documented).
- Status-label legend added at the top (HOLDS / QUALIFIED / RETRACTED / NEGATIVE / NO VERDICT / OPEN).
- "In plain words" rewritten for v2.1: depth rungs = PrimeSense's table (259 / 345), driver phase, lateral scale corrected,
  capabilities retitled "mostly documented; confirmed here", calibration-blob summary; warm-up bullet now credits prior art.
- Corrections: new v2.1 block, placed first:
  - RETRACTED the cold/warm U(N) "manufacturing levels" story; U(N) measures scene coverage; Byte Kitchen 2014 credited for 345.
  - CORRECTED "−3.4 % narrow": box hand-tape reference; #10 envelope +0.45..+1.74 %, sealed rule NO VERDICT (+1.74 %);
    rotation test agrees; Kreylos 2013 credited.
  - CORRECTED "near limit exactly 801 mm": the SDK's 800 mm clamp landing on the next rung.
  - SUPERSEDED v1-card points 3 and 4 (K = 345,489 px·mm exactly; the 73.79 mm baseline and the 0.25 mm residual).
  - CORRECTED raw Bayer: GRBG mosaic, on-chip white-balance gain, linearity untested, 10.22 fps at 1280×960, 640 Bayer resampled,
    Microsoft's compression statement.
  - CORRECTED capability map: 13 of 28.
  - CORRECTED `sensor.py` docstring (passive-IR claim) and `nui.py` sentinel constants.
  - CORRECTED the IR row's script (`capmap.py`, not `ir.py`).
  - Credit added for warm-up drift (Fiedler & Müller; Chow 2012 via Qi 2014; Sarbolandi 2015; DiFilippo & Jouaneh 2015; Choo 2014;
    Andersen 2012) and noise models (Nguyen 2012; Choo 2014; Sarbolandi 2015).
  - AMENDED "what is ours".
  - Corrections to unpublished working notes: "depth outlines 0–3 px inside IR outlines" withdrawn (SDK depth/IR offset ~3–5 px x,
    ~3 px y); "~38 000 dots" was not a count (published ~34.7 k); audio 2-channel reading and DOA demo retracted (Windows mix).
  - v2.0.1 and v2.0 blocks kept, with v2.1 pointers where they are amended.
- New "Findings added in v2.1" table (25 rows, each with status and script) and detail sections: SDK table and driver phase
  (DiFilippo & Jouaneh 2015 credited; offset known only modulo one step), calibration blob stages 1–3 with the method/licence
  statement and prior-art gate NOT FOUND, extended depth (16-bit wrap labelled OPEN, confirmation pending), materials and negatives.
- v2 findings table: raw Bayer → QUALIFIED; capability map 13/28; IR row cites `capmap.py` and `ir_ceiling.py`; drift row credits
  prior art; lateral-scale row split into box (RETRACTED) and envelope (NO VERDICT); predictor row notes pixel position is not used.
- Near mode / projector-off paragraph: HRESULT named (`E_NUI_HARDWARE_FEATURE_UNAVAILABLE`, in the header but not in the online error
  tables); documented as Kinect-for-Windows-only.
- Tools / setup: `atlas/` described; captures never published; scipy/matplotlib listed; `KINECT_MIC_ENDPOINT_ID` noted.
- v1 card: new short version; plain-words mechanism (window matching, ⅛-px steps); folklore 2048 cited (Khoshelham §3.2); claim 3
  replaced with the exact K and gaps (Smíšek 2011 for 2.89 mm); claim 4 struck; 0.25 mm residual marked superseded; camera serial
  truncated to `A003…`; model 1414 added; USB note says NEC/Renesas (VID 0x0409), "likely", with Microsoft's known issue; software
  note on the libfreenect port; falsifiers rewritten (≤ 259 / ≤ 345, prior census exists); replicate list adds `lattice_closure.py`;
  "not ours" adds the formula, PrimeSense's primary source for ⅛ px, the census, and moves Boehm to unit-to-unit variation; Smíšek
  cited by venue (report number dropped), Andersen section number dropped; "ours" reworded; "Known tension" replaced by "Prior census
  (credit)"; U(N) frame counts stated correctly (cold 10,000, settled 100,000).
- Cite: licence note for the Apache-2.0 section of `decode_stage2.py`.

## Code (edited)

- `sensor.py`: slot-32 docstring corrected (rejected on Xbox hardware, no passive-IR mode); accelerometer described as count/819,
  uncalibrated.
- `nui.py`: "on this drive" removed; depth sentinels fixed to 0x0000 / 0x7FF8 / 0xFFF8 (unused by any script); elevation docstring
  cites the teardown for the KXSD9.
- `viewer.py`: LATTICE uses the exact constants (STEP = 0.1042/36000, INTERCEPT = 1/1200) at the floor-bin centre (z + 0.5; all 345
  rungs resolve, max index error 0.25); references to the private notes removed; BAYER key described as a GRBG mosaic.
- `blob_dump.py`: "from the panel" → "fixed before running" (comment only).
- `decode_stage2.py` (copy): private-notes reference removed; Apache-2.0 attribution added to the ported libfreenect section.
- `atlas/` copies, comment-only scrubs: `colour_probe.py`, `ir_regdots.py`, `ir_pattern_vscale.py`, `player_index_probe.py`,
  `wasapi_probe.py`. `wasapi_probe.py` also no longer hard-codes this PC's audio endpoint GUID (reads `KINECT_MIC_ENDPOINT_ID`).
  Because of these edits, the sha256 prefixes recorded for the as-run atlas scripts do not match these five files.

## Files added

- From the working folder: `decode_stage2.py`, `decode_stage3.py`, `four_edges.py`.
- Results (numbers only, no images): `stage2_results.json`, `stage3_results.json` (these include this unit's reg_info values),
  `code_t1.json`, `code_t2trim.json`.
- `depth_lattice_values.json`: the 266 observed millimetre values that `lattice_closure.py` / `lattice_test.py` read.
- `ir_ceiling.py`: new descriptive script for the IR ceiling / pedestal; run on the nine local IR captures for the numbers quoted.
- `atlas/`: 34 scripts and 18 JSON results (no `.npz`).
- Already staged before this pass and left byte-identical (sealed rules and predictions): `lattice_closure.py`, `code_density.py`,
  `dark_room*.py`, `envelope_scale.py`, `ir_edges.py`, `kinect_pos.py`, `rot_test.py`, `scale_two_pos.py`, and the six
  `*_prediction.json` files.

## Metadata

- `CITATION.cff`: version 2.1, date 2026-09-27, title without "hidden", keyword "calibration", abstract rewritten (no −3.4 %, no
  unqualified 2.74 s).
- `.zenodo.json`: version 2.1 added; title and description rewritten to match; keywords extended.
- `.gitignore`: also ignores `*.png`, `*.jpg`, `*.wav`, `*.bin` (the calibration blob) and `stage3_out/`.

## Checks

- Every `.py` parses; every `.json` loads; `CITATION.cff` parses as YAML.
- No `.npz`, `.npy`, `.png`, `.jpg`, `.wav` or `.bin` in the folder.
- Name/path grep (assistant and company names, internal codenames, personal names, local paths, phone brand, full serial): clean.
