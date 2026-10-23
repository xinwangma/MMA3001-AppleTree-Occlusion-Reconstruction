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

## 2026-10-23 — Step 3: visible-only 2D prototype

Implemented binary-visible-mask thinning and a deterministic pixel graph in the existing src layout, plus a provenance-recording CLI. Reused the synthetic fixture without rewriting it: 117 skeleton pixels, 2 components; occlusion gap preserved. Full suite: 36 passed. Added docs/11_visible_only_baseline.md and usage/status updates. No real visible masks were fabricated; Step 2 alignment and depth calibration remain unresolved. No commit or push.

Real-data readiness follow-up: reused Step 2 selection to prepare 20 native-RGB annotation/review inputs, verified source/copy hashes and unchanged metadata, exercised real GT dimension rejection and existing-package protection. No real visible labels available; all acceptance flags remain no. No algorithm changes; 36 tests pass; no commit/push.

## 2026-10-23 ? Step 3 real-RGB draft diagnostics

Audited the mask-assisted baseline (it cannot segment RGB). Selected 12 N02 RGBs
across R01..R12. Added native polygon editor, provenance/hash-checked rasteriser,
and batch figures/connectivity/runtime diagnostics. Saved 30 RGB-only AI draft
patches, explicitly pending human review, with no whole-GT-derived masks. All 12
input component correspondences were preserved and all 30 patches retained
skeleton pixels. Median sample-median inference 196.8 ms; broad graft draft
R06N02 produced a spur. 50 tests passed. No real accuracy or human acceptance is
claimed. Details: docs/12_step3_real_data_review.md. Baseline algorithms unchanged;
no Step 4, commit or push.


## 2026-10-23 ? Step 3 annotation coverage revision

Reviewed all 12 RGBs and draft masks at native/cropped scale. Final v4 conservatively
revises 10 samples and retains R03N02/R12N02 because of ambiguity. Added zoom/pan,
vertex editing, overlay and visible/occluded checkpoints to the editor; separate
human review and approval records; heuristic QA and before/after outputs. Rejected
preflight polygons that crossed leaves/fruit/vegetation and corrected polygon-join
artifacts. 63 tests pass. All 12 final annotations remain AI DRAFT; no real accuracy
claim, source changes, occlusion completion, commit or push. See docs/13_step3_annotation_revision.md.
