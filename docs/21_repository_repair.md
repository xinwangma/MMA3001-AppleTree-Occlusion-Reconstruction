# Completed-project repository repair record

The completed Step 1–6.1 algorithms, numerical settings and conclusions are unchanged.
No new optimisation, commit, push or dataset upload was performed.

## Removed code and retained materials

An inspected deletion manifest contains **61 Python source files and 59 bytecode
files**: the temporary preparation runner, a staging duplicate of the retained
generic API generator, and pypdf modules/caches used only for Brief extraction.
No Step 1–6.1 code or tests imports that temporary dependency. All removals were
verified against a backup before deleting only the exact listed .py/.pyc files.

The complete per-file list, purposes and original hashes are in
[step7_code_removals.json](validation/step7_code_removals.json).
Step 7 academic audit documents, extraction text, metadata, logs and test records
are retained as history. Reports, Word/presentation materials, figures, datasets,
previous experiment directories and ZIP archives were not deleted. The generic
API generator, Matplotlib dependency and all 171 original tests are required by
the completed project and are retained. Historical mentions of Step 7 inside old
report strings are not executable Step 7 features and remain unchanged.

## Repairs

- Current README covers completed stages, method selection, scope and working links.
- Complete API HTML covers all 10 package modules, including completion/matching/3D.
- CI installs dev/study dependencies, checks Matplotlib and runs the full suite/API check.
- A generic saved-result CLI accepts an external evidence directory, avoiding the
  historical experiment command's unnecessary real-image/history dependencies.
- Frozen source hashes accept only an LF/CRLF conversion for cross-platform clones.
- Small metrics/selected synthetic figures are copied unchanged into the
  [review index](reproducibility/step61/index.html). Full replay arrays/graphs are
  in the separate local synthetic-only ZIP, excluded from Git.

## Executed verification

- Published baseline clone: {'tests': 171, 'failures': 2, 'errors': 0, 'skipped': 0}; missing Matplotlib confirmed:
  True.
- Repaired workspace: 171 passed. Repaired isolated clone/clean installation: 171 passed.
- Saved metrics: 600 rows, maximum difference 0.0. Evaluation replay: 480 graphs.
- All source algorithms/original tests unchanged; 11467 prior
  data/results files retain SHA-256, size and mtime.
- English source comments/docstrings and generated documentation links checked.
- `git diff --check` is executed after the final documentation updates.

Details: [completed_project_verification.json](validation/completed_project_verification.json).
Current commands and authorised external-data requirements:
[reproducibility guide](20_reproducibility.md).

## Remaining limits

The published main remains at the audited commit until a later approved commit
and push. A real GitHub Actions run on these uncommitted changes cannot exist;
local compatibility checks do not claim online CI success. Full historical
experiments require the explicitly documented excluded dataset and old results.
Real annotation/calibration remain unverified. Existing manual-gap boundary,
baseline overwrite and legacy demo-calibration limits are documented, not changed.
