# Annotation alignment investigation

Date: 23 October 2026. This stage extends the completed inventory in
[09_real_dataset_inspection.md](09_real_dataset_inspection.md); it does not repeat
that inventory or change original data. Evidence is local, with no new upstream
registration documentation. No depth calibration or 3D truth is inferred.

## Methods and coordinate conventions

Implementation: `src/apple_tree_project/alignment.py`; reproducible experiment:
`scripts/compare_annotation_alignment.py`. Only the GT-containing release is used;
exact Summer RGB/GT suffixes are paired, without cross-release or winter matching.
All 562 pairs were decoded and checked for 640 x 480 RGB and 256 x 256 binary L GT.

The fixed candidates map source pixel-edge coordinates to target coordinates as
`u = sx*x + tx`, `v = sy*y + ty`. Pixel centres are at `(column+.5,row+.5)`.

| Candidate | sx | sy | tx | ty | Interpretation |
|---|---:|---:|---:|---:|---|
| stretch | 0.4 | 0.5333333333 | 0 | 0 | Resize full frame independently in x/y |
| center_crop | 0.5333333333 | 0.5333333333 | -42.66666667 | 0 | Crop x=[80,560), then resize 480-square |
| letterbox | 0.4 | 0.4 | 0 | 32 | Resize to 256 x 192, pad 32 rows above/below |

RGB is sampled with Pillow bilinear interpolation. Inverse GT mapping into the
original RGB grid uses nearest neighbour and zero fill, preserving 0/255 labels.
No translation fitting, rotation, projective fitting, manual correction or
per-image optimisation was performed. Arbitrary crops and such transforms remain
possible but need independent corresponding landmarks rather than fitted amodal
labels. These functions deliberately expose hypotheses, not an automatic adapter.

## Generated evidence

Run from the repository root:

```powershell
python scripts/compare_annotation_alignment.py
$env:PYTHONPATH = "$PWD/results/test_dependencies;$PWD/src"
python -m pytest -q
```

All generated experiment outputs are under `results/alignment_candidates/`:

- `report.json`: candidate parameters, aggregate results, input SHA-256 hashes,
  modification times, source paths and deterministic sample selection.
- `scores.csv`: 1,686 sample/candidate rows, including diagnostic edge score and
  foreground outside the mapped source image.
- `R01N01_comparison.png` through `R20N01_comparison.png`: 20 sheets, selecting
  the first lexicographic Summer pair per row prefix. Each shows original RGB,
  original GT, three annotation-grid overlays and three RGB-grid overlays.
  Magenta is translucent foreground; yellow is the inner mask boundary.
  Display thumbnails are resized for presentation; calculations use 256-square.

This selection covers row prefixes, not all trees, viewpoints or annotation
failure modes. Six sheets were visually inspected in this execution: R01N01,
R04N01, R07N01, R10N01, R15N01 and R20N01. The other 14 sheets were generated
but have not been individually reviewed.

## Quantitative diagnostics (not registration accuracy)

For each candidate, compute luminance gradient magnitude on its transformed RGB,
then the maximum gradient in a 5 x 5 neighbourhood around each GT inner-boundary
pixel and average. Scores below are unweighted means over all 562 observations.
No visible-branch reference exists, so neither IoU nor pixel registration error
can legitimately be calculated against the RGB itself.

| Candidate | Mean boundary edge proxy | Mean GT foreground outside source |
|---|---:|---:|
| stretch | 0.142208 | 0% |
| center_crop | 0.135927 | 0% |
| letterbox | 0.122274 | 21.5954% |

Stretch ranks highest by this diagnostic. However foliage, fruit, supports,
background texture, interpolation and the artificial padding edge all affect
this score. Amodal branch boundaries may have no observable RGB edge. The score
has no accuracy threshold, no independent registration truth and no statistical
validation; it cannot establish the correct transform. The letterbox candidate
places substantial annotated foreground in padding, inconsistent with interpreting
these labels purely as a transformed in-frame mask. Off-frame amodal annotation
would be a different, undocumented policy; this finding is not a universal proof.

## Visual findings and exceptions

R01N01, R07N01, R10N01, R15N01 and R20N01 support full-frame stretch as the most
plausible working hypothesis: the lower trunk is closer to visible wood, and
major-arm trajectories are broadly consistent where visible. Center cropping
changes arm width/spread; letterboxing shifts vertical structure and sends labels
into the padded bands. Hidden arm portions cannot be checked against foliage.

**R04N01 is a material exception.** Its labelled lower trunk is visibly to the
left of the photographed lower trunk under stretch, and substantial mismatch
persists under the other two candidates. None of these fixed transforms safely
resolves this sample. It could reflect annotation error, a different source
view, or an untested transformation; the files do not establish the cause.
Do not repair it by asserting a manually chosen shift is ground truth. This
exception prevents treating the whole dataset as verified by one resize rule.
No numerical landmark residuals or independently adjudicated correspondence
measurements were collected. Qualitative agreement is not pixel-level precision.

## Decision for the visible-only baseline

**Proceed conditionally with a 2D engineering prototype; do not yet proceed with
a validated supervised benchmark or metric 3D reconstruction.**

A visible-only mask-to-skeleton implementation can be developed and tested on
synthetic fixtures and independently reviewed visible annotations in native RGB
coordinates. Summer GT is an amodal main-branch target, not a visible-only input;
skeletonising it would leak hidden structure into the baseline. Do not derive
visible truth by assuming every GT pixel is visible or using winter as registered
summer truth. Whole-GT/visible intersection is not an independent annotation.

Before dataset-level evaluation: obtain annotation preprocessing documentation
or independently mark visible corresponding landmarks across a broader sample;
measure residuals and set a justified acceptance tolerance; review suspect pairs
including R04N01; retain accepted/excluded records and reasons; create or obtain
visible-branch labels independently of the whole mask. Freeze the chosen transform
and validation rule before held-out evaluation, and keep verified physical tree
identities together in splits. Until then stretch remains explicitly provisional,
not a silently enabled loader default. RGB/depth registration, depth transfer
function, intrinsics, depth units and 3D ground truth remain unresolved as in doc 09.

## Tests and source protection

Full repository suite: **22 passed** (17 existing plus 5 new), Python pytest,
23 October 2026. New coverage verifies analytic parameters, centre landmarks,
nearest-neighbour binary output, crop support, padding boundaries, invalid inputs,
boundary behaviour and an end-to-end synthetic evidence run with source-byte and
mtime preservation. These tests establish implementation behaviour, not real
annotation correctness. No external dependencies were added.

The real experiment hashed all 1,124 RGB/GT inputs before processing and rehashed
them afterwards, also comparing nanosecond modification times: **0 changes**.
The output guard rejects destinations inside or above the supplied raw root.
Originals were opened read-only. Other original dataset files were not processed
or written in this stage. Outputs remain Git-ignored. No commit or push was made.
