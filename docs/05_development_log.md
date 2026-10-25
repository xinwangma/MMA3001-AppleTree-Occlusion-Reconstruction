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


## 2026-10-25 — Step 6 paired final validation and profiling

Reused and checked Step 4/5 numerical evidence. Added 48 frozen-seed synthetic holdout configurations, 30 targeted 3D gap/physical-curvature cases, 8 negative fixtures per completion method, and 192/640-width stage/runtime/memory benchmarks. Shared thinning and detection only across the three-method comparison; original methods retained. Real 12 drafts remain pending, with R06/R08/R09/R10 flagged for independent human review. Full-suite totals: {"tests": 139, "failures": 0, "errors": 0, "skipped": 0, "passed": 139}. See docs/16_step6_final_validation.md and results/step6_final_validation/. No raw/previous-results changes, Step 7, commit or push.


Step 6 recovery final verification: {"tests": 140, "failures": 0, "errors": 0, "skipped": 0, "passed": 140}. Source snapshot suite also passed; saved Step 6 replay 234 graphs and Step 5 replay 15 graphs passed. Preserved initial analysis/test/package attempts. Windows ZIP readback fix only; no experiment/runtime repetition or Step 3–5 algorithm change.

Step 6 runtime interpretation audit: original timing inputs had zero candidates; preserved all timing records, added one successful-gap microbenchmark with accepted-count assertions. Full suite/source snapshot: {"tests": 141, "failures": 0, "errors": 0, "skipped": 0, "passed": 141}. No prior experiment/runtime reruns or Step 3–5 changes.


## Step 6 v2 angular boundary stability

Fixed conservative numerical boundary policy; frozen inputs/plan preserved. Audited 234 graphs against archived v1 source and current policy, regenerated affected outputs in a new version, checked +/-1e-12 degree decision perturbations and holdout_19. Full suite: {"tests": 160, "failures": 0, "errors": 0, "skipped": 0, "passed": 160}. Original data/results/ZIP unchanged. See docs/16_step6_numerical_stability.md. No commit/push or Step7.


## 2026-10-25 — Step 6.1 fork-anchored matching

Completed the interrupted detector, 24-case development and frozen 96-case evaluation, with unchanged fitters and angular policy. Saved five-method metrics, historical error/rejection audit, real draft gallery, 480-graph observation replay and original-evidence preservation checks. Full suite: 171 passed. See docs/17_step61_fork_matching.md. No real accuracy claim, commit or push.


## Step 7 — final repository preparation (pending review)

Inspected the actual 15-page 2026 Brief; verified local/remote main at a721168.
Replaced outdated README/setup guidance; regenerated all 10 API pages with an
index and freshness/link checks; added submission audit, zipped-clone procedure,
tested constraints and compact frozen numeric evidence. Workspace and clean-venv
snapshot each pass 171 tests; installed demo and pip check pass. Source algorithms,
tests, raw RGB-D and archived experiments are unchanged. No commit or push.
See docs/18_step7_repository_audit.md for remaining student deliverables and issues.


## Completed Step 1–6.1 repository repair

Retired 61 temporary Python modules/scripts and 59 bytecode files used only by
repository preparation/PDF extraction. Preserved their backup, all academic
documents, original algorithms, tests, datasets, historical results and archives.
Verified current API/README, Matplotlib setup, 171 tests in workspace and repaired
fresh clone, and saved-result replay (600 metric rows / 480 evaluation graphs).
No optimisation, commit or push. See docs/21_repository_repair.md.
