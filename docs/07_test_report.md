# Step 1 — Automated Test Report

## Test environment

- Date: 2026-10-22
- Test runner: `pytest`
- Execution command: `PYTHONPATH=src python -m pytest -q`
- Test result: **14 passed**
- Modules exercised: CSV manifest loading, input validation, binary F1/IoU,
  hidden-branch recall, file pairing, depth/image dimension checks.

## Synthetic format smoke test

The fixture generator `scripts/make_demo_manifest.py` created one artificial
Y-shaped RGB-D example with paired visible/whole branch masks. The real Monash
dataset was **not** used.

Command:

```sh
PYTHONPATH=src python scripts/make_demo_manifest.py
PYTHONPATH=src python -m apple_tree_project.audit data/demo/manifest.csv --json-output results/demo_audit.json
```

Output:

```
Samples=1  Errors=0  Warnings=0
Seasons={'winter': 1}  Unknown tree IDs=0
```

This shows the program can read a paired set matching our **internal** schema.
It does **not** demonstrate occlusion recovery, reconstructed 3D accuracy or
real-dataset validity.

## Environment limitation

The connected runtime blocked live package installation from PyPI. To test the
source tree with installed packages, `PYTHONPATH=src` was used instead of
`pip install -e .`. The standard installation instructions should be tested
on a normal network-enabled Windows Python environment before final submission.

## Future tests required

- Decoding the exact downloaded dataset and annotations.
- Cross-checking RGB/depth correspondence and depth units.
- Camera intrinsics and 3D reprojection correctness.
- Baseline and completion-algorithm geometric unit tests.
- Held-out real-dataset metrics (must be reported separately).
- Runtime and sensitivity analysis.

## Step 3 update — 23 October 2026

Complete suite: **36 passed** (22 existing plus 14 new baseline cases). Command: set PYTHONPATH to results/test_dependencies and src, then run `python -m pytest -q`. Coverage includes skeleton topology on synthetic fixtures, gap preservation, graph geometry, invalid inputs and runner output/source protection. The existing synthetic demo ran successfully; no real-tree accuracy or precise GT alignment is established. Details: [Step 3 baseline](11_visible_only_baseline.md).

Follow-up: git diff --check passes and all 36 pytest tests still pass. Additional executed real-input checks verified 20 native RGB schemas/copies against Step 2 hashes, 21 unchanged source files, rejection of mismatched real Summer GT, and refusal to overwrite review work. No real reconstruction accuracy is established.

## Step 3 real-RGB diagnostic update ? 23 October 2026

Complete suite: **50 passed** (36 previous plus 14 annotation/validation cases).
Command: PYTHONPATH includes results/test_dependencies and src; python -m pytest -q.
Added geometry, provenance, source-hash binding, deliberately lost connectivity,
pending-draft gates, source-preservation and output-protection tests. Real RGB
runs used 12 AI-authored draft masks, not human truth. Component correspondence
and pixel-subset checks passed; this establishes no real anatomical accuracy.
See [real-RGB findings](12_step3_real_data_review.md). GUI interaction awaits a
human check; CLI help and GUI-independent backend were exercised.


## Step 3 coverage revision ? 2026-10-23

Complete suite: **63 passed** (50 previous plus 13 new cases). PYTHONPATH includes
results/test_dependencies and src; command: python -m pytest -q. New cases cover
missing-trunk/occlusion point checks, absence of coverage evidence, invalid points,
nonmutating fragment/spur/endpoint prompts, polygon self-intersection, zoom
coordinates, separate review/approval/reset gates, and single-editor-JSON QA runs.
CLI help, Python compilation, final local HTML references and source hashes were
checked. The 12 final real runs preserve input components, with no outside skeleton
pixels, isolated pixels or graph cycles. These checks are not independent label
or anatomical accuracy validation. Human GUI usability acceptance remains pending.
See [the revision guide](13_step3_annotation_revision.md).
