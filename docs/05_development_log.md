# Development Log

## 2026-10-22 — Step 1: Project reframing and repository scaffold

- Selected engineering task: occlusion-aware reconstruction of the Y-shaped
  tree's major branches, rather than generic tree skeletonisation.
- Kept whole-branch annotation separate from inference inputs to prevent leakage.
- Set baseline A (visible-only) and planned proposed B (geometry completion).
- Created manifest, data audit, explicit 2D metrics and tests.
- Identified calibration/3D ground-truth uncertainty as a decision gate.

**Results:** No real dataset evaluation has been run.
**Next:** Obtain/inspect actual dataset and adapt its formats.

## 2026-10-22 — GitHub-ready packaging

- Reworked the root README to explain the project objectives, provisional dataset contract,
  proposed baseline/completion methods, validation limits, exact installation commands,
  current implementation status, development roadmap and AI-use disclosure.
- Updated `.gitignore` to allow the generated `docs/api/` HTML documentation to be
  tracked in the final submission (required by the MMA3001 brief).
- Confirmed foundation unit tests on this snapshot: `PYTHONPATH=src python -m pytest -q`
  returned `14 passed`. This verifies scaffolding utilities only; it does not validate
  real-dataset branch completion or 3D reconstruction.
