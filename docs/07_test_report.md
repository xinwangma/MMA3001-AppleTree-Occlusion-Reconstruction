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
