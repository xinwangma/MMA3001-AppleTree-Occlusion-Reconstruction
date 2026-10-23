# Step 3 real-RGB diagnostics and manual review workflow

Update (2026-10-23): the original run below is preserved. See
[Step 3 annotation revision](13_step3_annotation_revision.md) for the current
zoomable editor, separate review/approval, final v4 before/after figures, quality
checks and 63-test result. Its editor/workflow instructions supersede those below.

Date: 23 October 2026. Scope: real RGB inputs with RGB-only polygon **drafts**,
existing skeleton extraction, connectivity checks, figures and timing. This is not
an independently human-validated accuracy study. Step 4 has not been started.

## Baseline audit

Reviewed `src/apple_tree_project/baseline.py`, `scripts/run_visible_baseline.py`,
`scripts/prepare_visible_review.py` and `docs/11_visible_only_baseline.md`.
`visible_only_baseline(visible_mask)` needs an externally supplied visible binary
mask. It cannot extract branches from RGB. The runner reads RGB only for matching
image dimensions and visualisation. There is no segmentation model, colour-based
branch detector or reliable depth processing in the existing baseline.

The Zhang-Suen implementation and pixel-graph algorithm are unchanged in this
stage. No whole GT, winter or depth file was read to create this round's masks.
The previous readiness package remains preserved.

## Selection and provenance

Twelve native 640 x 480 Summer RGB images were selected: the second lexicographic
Summer RGB in each row R01..R12, giving R01N02 through R12N02. These differ from
the earlier first-per-row N01 overlays, avoiding reuse of those viewed whole masks.
All 12 RGBs were visually inspected. The selection covers contrasting background,
wood thickness, lower-trunk shapes and occlusion conditions; it is a convenience
sample, not a random, quantitatively stratified or held-out population benchmark.
It excludes rows R13..R20 and does not resolve physical identity independence.

No independent human visible labels were available locally. To execute feasible
real-image diagnostics without inventing human labels, Codex visually traced 30
conservative polygon patches directly from these RGBs. Their exact coordinates,
source hashes, annotator identity and limitations are versionable in
`data/annotations/step3_rgb_only_drafts.json`. Every sample is explicitly marked
`ai_rgb_only_draft`, `review_status=pending`, with no human reviewer. These drafts
are independent of Summer whole-GT generation, **not independent human annotations
or complete visible truth**. They may omit visible wood and include uncertain
boundary pixels. Pixel areas outside a selected patch are unlabelled for this
study, not independently established background truth. No IoU/F1 is computed.

## Reproducible manual workflow

`scripts/annotate_visible_branches.py` provides a local Tkinter RGB polygon editor.
It displays the native RGB at 1:1 and does not load whole GT or winter. Tkinter is
part of normal desktop Python distributions; it is imported only on GUI launch.
The CLI help and annotation/rasterisation backend were exercised here. The GUI
was not launched or operated by a human in this session; its mouse/key interaction
still needs a human usability check. No automated GUI testing is claimed.

Example for a fresh, unseeded human annotation:

```powershell
python scripts/annotate_visible_branches.py --rgb "data/raw/monash_y_tree/TreeID/Dataset (With Summer GT)/R01N02_Summer_RGB-12-40-59.png" --output results/step3_real_validation/human_R01N02_v1 --annotator "YOUR_NAME" --notes "Native RGB only; visible main wood; record uncertainty here"
```

1. Click vertices around visibly supported main trunk/arm surfaces. Use separate
   polygons at leaf/fruit occlusions. Do not bridge hidden wood or include support
   posts/wires, neighbouring trees or inferred limb continuations.
2. Enter completes a polygon. Backspace removes a current vertex; Delete removes
   the last completed polygon. S saves `annotation.json` and binary `visible.png`.
   Coordinates are integer native pixel centres; Pillow fills polygon boundaries
   inclusively. The same coordinates reproduce the same mask, without morphology.
3. Mark partial coverage, ambiguous material and image-edge truncation in notes.
   Exclude ambiguous samples from accuracy scoring unless a separate ignored-region
   protocol is established. Do not use unlabelled pixels as false-positive truth.
4. A different human reviewer must check RGB alignment, coverage and visible
   support, recording reviewer identity, date, issues and acceptance. The editor
   always saves pending status; acceptance must be deliberately adjudicated.
5. Optional `--load path/to/annotation.json` starts a revision in a new output
   directory. A parent hash and parent provenance are retained and provenance
   becomes `human_rgb_revision`. Editing an AI seed does not become an independent
   blind human annotation. For independent assessment, start without `--load`.

Output must be in a new directory under results/ or data/processed/, separate
from inputs. RGB hashes bind annotations to exact images. The rasteriser rejects
wrong sizes, unsupported provenance, noninteger/out-of-frame or degenerate
polygons and missing metadata. It does not certify wood identity, annotation
coverage, polygon simplicity, reviewer independence or anatomical correctness.
All polygons are additive; represent occlusions with separate polygons rather
than relying on holes or subtractive regions.

For batch processing of human annotations, place the per-image JSON objects into
a `samples` list matching the supplied draft bundle schema, with paths relative
to repository root (or absolute paths), `review_status=accepted` and reviewer
identity after genuine review. The command below accepts pending drafts only
with explicit `--include-drafts`; accepted metadata is still a user declaration,
not automatic certification of independent truth.

## Executed experiment

```powershell
python scripts/validate_visible_baseline.py --include-drafts
```

The script binds annotations to source hashes, rasterises polygons and calls the
unchanged `visible_only_baseline`. Default output is a new
`results/step3_real_validation/draft_run/` directory; existing runs are protected.
Use `--output results/step3_real_validation/another_run` for reruns.

Each sample directory contains the explicit annotation JSON, binary visible mask,
skeleton, pixel graph, diagnostics and `comparison.png`. Four native-resolution
panels show original RGB, cyan RGB-only patch overlays, yellow skeleton, and
component-coloured pixel graph. Each graph node is a pixel, adjacent nodes have
unit/diagonal edges, red circles mark endpoints and white circles mark junction
or isolated pixels. Degree-2 nodes are shown at their pixel positions, not as
large circles. Node/edge coordinates and degrees are in graph.json. The root
contains summary.csv, summary.json and a 12-sample contact_sheet.png.

All 12 outputs were reviewed at contact-sheet scale; R01N02, R03N02, R06N02,
R07N02, R09N02 and R12N02 were additionally inspected in full four-panel figures.
This was an AI visual review, not an independent human adjudication.

## Actual connectivity, patch preservation and timing

Input components are computed with an independent eight-neighbour flood fill.
For each output graph component, its nodes must map to one input component;
the correspondence must cover every input component exactly once. This checks
preservation of the supplied mask topology, not the physical tree's topology.
Patch survival means at least one skeleton pixel lies in each polygon; it is a
weak retention check and not branch recall, length preservation or endpoint error.

Runtime measures thinning plus graph construction, excluding annotation, IO,
connectivity diagnostics and figures. One warmup per sample, then five repeats;
table values are medians for this specific run. Python 3.13.7, NumPy 2.3.4,
Windows 11. Background load and hardware affect repeatability.

| Sample | Visible pixels | Skeleton pixels | Input/output components | Endpoints | Junction pixels | Median ms |
|---|---:|---:|---|---:|---:|---:|
| R01N02 | 3031 | 295 | 2 / 2 | 4 | 0 | 162.1 |
| R02N02 | 3120 | 263 | 2 / 2 | 4 | 0 | 191.5 |
| R03N02 | 1424 | 124 | 2 / 2 | 4 | 0 | 120.5 |
| R04N02 | 3417 | 167 | 3 / 3 | 6 | 0 | 238.9 |
| R05N02 | 3218 | 255 | 3 / 3 | 6 | 0 | 179.4 |
| R06N02 | 2451 | 178 | 2 / 2 | 5 | 1 | 209.9 |
| R07N02 | 1024 | 79 | 3 / 3 | 6 | 0 | 119.4 |
| R08N02 | 2092 | 193 | 3 / 3 | 6 | 0 | 151.0 |
| R09N02 | 3457 | 225 | 3 / 3 | 6 | 0 | 235.1 |
| R10N02 | 3644 | 247 | 3 / 3 | 6 | 0 | 211.7 |
| R11N02 | 1797 | 114 | 2 / 2 | 4 | 0 | 202.0 |
| R12N02 | 2378 | 143 | 2 / 2 | 4 | 0 | 302.4 |

Results: input components preserved one-to-one in all 12 samples; all 30 polygons
retain skeleton pixels; 0 skeleton pixels outside input masks; prediction masks
unchanged; no graph cycles or isolated pixels. Median of sample-median times:
196.8 ms, range 119.4..302.4 ms. These are implementation diagnostics on draft
masks, not tree reconstruction accuracy or an end-to-end RGB runtime benchmark.
All 12 source RGB hashes/mtime were unchanged. Source image bytes are not tracked
or rewritten; derived PNGs/graphs/reports remain ignored under results/.

## Failure cases and limitations observed

- R03N02 and R07N02: heavy leaf/fruit occlusion and sparse conservative patches
  yield disconnected fragments; complete Y connectivity cannot be justified.
- R06N02: the broad lower-trunk/graft draft produces a short extra skeleton spur
  and one degree-3 junction pixel. This is not evidence of a true extra branch.
  Coarse polygon corners and swelling geometry affect topology and centreline.
- R01N02, R09N02 and R12N02: conservative separate polygons leave artificial
  annotation gaps as well as possible occlusion gaps. The baseline preserves
  both and cannot distinguish them. Good component preservation can coexist
  with incomplete or erroneous annotations.
- All samples: patch survival does not demonstrate preservation of every visible
  branch, fine-twig coverage, correct branch identity or accurate centreline tips.
  Thin tips may retract; multiple junction pixels can represent one anatomical
  joint. No independently traced centreline/topology reference is available.
- Samples are small convenience coverage; no held-out evaluation, inter-annotator
  agreement, human accepted labels, calibrated depth or 3D accuracy is available.

## Tests and decision

Full automated suite: **50 passed**, including the 36 previous tests and 14 new
annotation/diagnostic cases. New tests cover raster geometry, deterministic JSON
round trips, invalid policy/provenance/vertices, hash mismatch, a deliberately
lost component, pending-draft gating, source preservation, output protection and
honest provenance of the checked-in 12 draft records. Synthetic tests are separate
from these real-input diagnostics. CLI help also runs without a GUI display.

Step 3 now has an executable RGB-only annotation workflow and real-RGB draft
smoke tests. **Independent human real-data validation remains incomplete**:
0 accepted human-reviewed samples, no defensible real accuracy scores. Obtain
fresh human annotations and review (and independent centreline/topology references
for accuracy), then rerun the same frozen baseline. Whole-GT evaluation still
requires resolving Step 2 alignment; metric 3D still requires calibration.
Do not treat this draft study as passing those gates. Step 4 was not started;
no commit or push was made.
