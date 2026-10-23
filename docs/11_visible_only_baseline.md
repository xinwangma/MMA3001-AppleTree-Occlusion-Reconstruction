# Step 3: visible-only 2D skeleton baseline

Date: 23 October 2026. Status: implemented and tested as a **mask-assisted 2D
prototype**, demonstrated on the existing synthetic fixture. Real-tree baseline
accuracy and precise Summer GT alignment have not been validated.

## Scope and inputs

The Step 2 decision in [10_annotation_alignment.md](10_annotation_alignment.md)
permits independent development of a visible-mask-to-skeleton method. The local
real dataset has no separate visible labels, and R04N01 remains an alignment
exception. This stage therefore does not turn amodal Summer GT into a visible
mask, use winter as registered summer truth, or introduce guessed calibration.

`src/apple_tree_project/baseline.py` accepts one explicit visible binary mask:
nonempty 2D bool, 0/1 or 0/255. Empty foreground is valid. Soft probabilities,
nonfinite values, multichannel arrays and other encodings are rejected; choosing
a segmentation threshold belongs to the upstream segmentation method. The API
accepts neither whole GT nor depth. It copies the input and does not mutate it.

This is annotation-assisted inference when supplied a manually annotated visible
mask, and segmentation-assisted inference when supplied a predicted visible mask.
It is not automatic segmentation from RGB. The CLI records the caller's declared
provenance; it cannot independently prove that a file is a true visible annotation.

## Method and outputs

1. Retain the original visible foreground as the baseline prediction mask. This
   is the mask to compare against a whole target when independent references are
   eventually available; do not score a thin centreline as a filled branch mask.
2. Apply Zhang-Suen thinning using two sequential subiterations, with simultaneous
   deletions within each subiteration. The eight clockwise neighbours start at
   north; candidates require 2..6 neighbours and one background-to-foreground
   transition, plus the respective three-neighbour deletion constraints.
   Iterate until neither pass deletes pixels. Outside the image is background.
   Each nonfinal iteration removes pixels, so finite inputs terminate.
3. Build a deterministic undirected **pixel graph**, retaining every skeleton
   pixel as a node at integer `(x=column, y=row)`. Connect eight-neighbours,
   suppressing a diagonal whenever either orthogonal intermediary is present;
   this avoids redundant corner triangles while preserving connectivity.
   Edge length is 1 or sqrt(2) pixels. Report components, degree-1 endpoints,
   degree>=3 junction pixels and degree-0 isolated pixels.

There is no closing, pruning, largest-component filtering, smoothing, gap
bridging, Y-shape enforcement or hidden completion. Cycles, noise and disconnected
fragments are retained. Several adjacent junction pixels can represent a single
anatomical bifurcation; this graph is not yet a simplified branch-level graph.
No root/trunk/left-arm/right-arm identity is asserted. Coordinates and lengths
remain in image pixels, with no metric or cross-resolution interpretation.
`inferred=false` means no added geometry; it does not certify the input mask as
physically observed truth. Computational work for thinning is O(H*W*I), where I
is the number of iterations; graph storage is O(N) for N skeleton pixels.

## Reproduction

From the project root (existing NumPy and Pillow dependencies only):

```powershell
python scripts/run_visible_baseline.py
```

Default inputs are `data/demo/visible.png` and `data/demo/rgb.png`, declared
synthetic. The existing fixture is read, not regenerated or rewritten. No whole
label or synthetic depth is loaded by the inference runner.

Custom inputs must explicitly supply all three arguments:

```powershell
python scripts/run_visible_baseline.py --visible-mask data/processed/my_visible.png --rgb data/processed/my_rgb.png --provenance manual_visible --output results/visible_only_baseline/my_sample
```

`predicted_visible` and `synthetic` are the other provenance choices. RGB and
mask must already share the same pixel grid; no automatic resize or Step 2
transform is applied. Equal sizes alone do not establish actual registration.

Default outputs are under `results/visible_only_baseline/`:

| File | Contents |
|---|---|
| prediction.png | Unchanged visible foreground, encoded 0/255 |
| skeleton.png | Thinned centreline, encoded 0/255 |
| graph.json | Pixel nodes, adjacency edges, components, endpoints, junction pixels |
| overlay.png | Cyan visible mask and yellow skeleton on RGB |
| report.json | Input hashes, provenance, geometry counts, timing and warnings |

Output paths overlapping repository raw data or containing either input are
rejected. Input bytes and nanosecond modification times are checked before and
after execution. Rerunning into the same output directory replaces derived
outputs. No original dataset files are written. These outputs are Git-ignored.

## Executed demonstration and validation

Existing 128 x 128 synthetic Y fixture: **987 visible pixels**, **117 skeleton
pixels**, **2 components**, **5 endpoints**, **1 junction pixel**, total graph
length **139.0244 pixels**. The missing right-arm section remains disconnected.
The overlay was visually inspected. Input hash/mtime changes: **0**. This is a
software demonstration, not a real-tree experimental result. Runtime is recorded
in report.json for the individual run; it is not a benchmark.

Full test suite: **36 passed**, including 22 existing tests and 14 new test cases.
Tests cover thick Y connectivity, endpoint/junction counts, thinning idempotence,
subset and unchanged-input guarantees, gaps and zero hidden recall, empty
foreground, isolated noise, cycles, border foreground, single rows/columns,
diagonal lengths, corner shortcuts, invalid encodings, CLI-output generation,
input preservation, provenance rejection, output protection and size mismatch.

```powershell
$env:PYTHONPATH = "$PWD/results/test_dependencies;$PWD/src"
python -m pytest -q
```

The zero hidden-recall test uses synthetic whole truth only in the test evaluator,
never as inference input. For the unchanged prediction P=V, no pixels in W & ~V
can be recovered; an empty hidden region instead follows the existing metric's
1.0 convention. No real IoU/F1/hidden recall is reported without valid references.

## Remaining work and boundaries

The mask-to-centreline portion of Step 3 is complete as an engineering prototype.
Real-data evaluation still needs independently reviewed visible masks in native
RGB coordinates and a documented accepted-sample list. Whole-GT scoring also
requires resolving the provisional alignment and exceptions from Step 2.
A compact branch graph, robust pruning and anatomical branch selection are
potential extensions requiring separately justified rules and tests; they are
not implied by the present pixel graph. Skeleton endpoints can move inward
relative to thick-mask tips, and thinning is sensitive to segmentation noise.
No claim is made about all possible topology patterns from a finite test suite.

Step 4 can use this output as a baseline interface, but any later inferred edges
must be explicitly marked and evaluated separately. Step 3 does not establish
RGB/depth registration, sensor scale, intrinsics, metric 3D or hidden 3D truth.
No commit or push is performed in this development stage.

## Real-data readiness follow-up (23 October 2026)

Whitespace recheck found no remaining errors; changed/new Markdown files already
had no unnecessary trailing blank lines. No reconstruction algorithm was changed.
The complete pytest suite was rerun: **36 passed**.

`scripts/prepare_visible_review.py` reuses the Step 2 report, rather than repeating
the full dataset inventory. It copies only native RGBs for the same 20 row-prefix
samples, verifies source hashes against Step 2, checks native schema, supplies a
pending-review manifest and annotation guide, and refuses to overwrite an existing
review directory. No whole masks are shown to annotators, and no placeholder or
pseudo visible masks are generated. These are preparation checks, not real-data
reconstruction accuracy measurements.

The final explicitly hash-verified package is at
`results/visible_only_baseline/real_review_verified/`:

- `rgb/`: 20 byte-identical native RGB copies.
- `review_manifest.csv`: all annotation/review statuses pending; all acceptance
  flags no; R04N01 explicitly flags the Step 2 whole-GT mismatch.
- `ANNOTATION_GUIDE.md`: visible-only annotation policy, uncertainty recording,
  independent human review and separation of native-2D and whole-GT acceptance.
- `readiness_report.json`: all source and copy checks and the real negative control.

Reproduce with a **new** output directory (existing review work is protected):

```powershell
python scripts/prepare_visible_review.py --output results/visible_only_baseline/real_review_new
```

Executed checks: all 20 RGBs are 640 x 480 RGB; all selected source hashes match
Step 2; every copied RGB hash matches its original; all 21 checked originals
(20 RGB plus one GT negative control) retained their bytes and modification times.
The real R01N01 Summer GT was rejected by the runner for its mismatched grid,
before inference or reconstruction output creation. The negative control's
`manual_visible` provenance value was deliberately a misuse attempt, not a claim
that the GT is visible truth. Same-size amodal inputs cannot be detected by this
shape guard; provenance and review remain essential. Existing-package overwrite
rejection was also exercised successfully.

No real visible masks were found in the inspected project inputs (only the
existing synthetic visible fixture; data/processed does not exist). **Accepted
real samples: 0; real reconstruction accuracy evaluated: no.** Pending work is
independent native-grid visible annotation and human review, followed by baseline
runs and overlay/topology review on accepted samples. Quantitative whole-GT scoring
additionally needs the unresolved Step 2 mapping. Merely comparing the unchanged
visible prediction with its own input is not independent accuracy validation.
Generated review packages remain ignored under results; no commit or push.

## Real-RGB draft experiment and manual workflow

A subsequent Step 3 run selected 12 new N02 Summer RGBs, generated explicitly
AI-authored RGB-only polygon drafts (not human ground truth), and executed the
unchanged skeleton baseline. A native-grid manual polygon editor and batch
connectivity/timing/figure runner are now available. Full suite: 50 passed.
See [the actual results and remaining human review gate](12_step3_real_data_review.md).
The earlier 0 accepted-human-sample status remains true; real accuracy is not
validated. No Step 4 development, commit or push was performed.
