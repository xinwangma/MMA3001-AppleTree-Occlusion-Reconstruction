# Step 7 — Final repository preparation audit

This is a repository compliance audit, not the final assessed written report.
Algorithms and frozen experiments are preserved. No commit or push is authorised
in this preparation. Status applies to the tested working tree, not an uncreated
final release.

## Brief inspected

Primary source: local `MMA3001_2026_Project_Brief.pdf`, 15 pages, SHA-256
`1029cf7c7c2844161af0c3727bbcbf40fac3913575683defe34ee942f9a9550c`.
Both downloaded copies have the same hash. The Brief is not redistributed.
Page references below use PDF page numbers. The raw PDF and its extraction are
not project runtime dependencies.

## Requirement-to-evidence audit

| Brief requirement | Evidence/status | Remaining action |
| --- | --- | --- |
| Engineering problem, scope, inputs/outputs (pp. 2, 4, 7) | README; docs/01_project_definition.md; methods reports | Explain mask-assisted scope and robotics relevance in final student report |
| Numerical method and reproducible implementation (pp. 2, 4) | Thinning, least-squares curve fitting, calibrated backprojection; all source on main | No new algorithm required for repository preparation |
| Alternative/baseline comparison (p. 5) | Visible-only, Linear, Quadratic and anchored variants; docs/17_step61_fork_matching.md; docs/validation/step61_summary.json | Do not describe anchored matching as universally superior |
| Justified validation and limitations (p. 5) | Synthetic benchmarks, topology/geometry tests, frozen evaluation and saved replay | Real annotations/calibration remain unverified; no real accuracy claim |
| Performance/sensitivity and final design justification (p. 6) | Step 4–6 sensitivity, stage timings, positive-gap benchmark, v2 stability audit; Linear retained | Do not rerun or reinterpret old timing records as new measurements |
| README and logical hierarchy (pp. 8, 11) | Current README replaces outdated scaffold-only structure/status; usage and external-data requirements explicit | Review final wording before publication |
| HTML source documentation (pp. 8, 12) | docs/api/index.html; all 10 source modules; source/page hashes and local link check | Generated additions must later be committed to main after approval |
| Licensing agreement (p. 8) | Existing MIT LICENSE is present; third-party data excluded | Student confirms generic copyright attribution and external-data rights |
| Functional main with comments/docstrings (pp. 8, 12) | main at a721168 contains all 10 source modules, runners, tests and small fixtures; comments explain numerical/topological intent | No src edits; Google/NumPy-style parameter/return/exception detail is not uniform |
| Test functions and report (p. 8) | Full 171-test suite; updated docs/07_test_report.md; compact verification JSON | Unit tests do not certify anatomical correctness or real calibration |
| Accessible final GitHub link (p. 8) | Remote main queried read-only and matches local a721168 | Student verifies assessor access; no new CI/accessibility claim before publication |
| Zipped CLONE via Moodle (p. 8) | Exact fresh-clone procedure in docs/19_reproducibility_and_submission.md | Create only after review, approved commit and push; Step 6.1 evidence ZIP is separate |
| Individual 5–10 page written report, excluding references/appendices from 10-page limit (p. 8) | Historical outline and technical evidence exist | Final individual assessed report has not been produced by this repository task |
| AI disclosure and personal reflection (pp. 6, 8, 15) | Dated AI use log, errors and verification recorded | Student supplies final contribution estimate, personal learning/reflection and responsibility |
| 5-minute presentation + 3-minute questions (p. 9) | Repository, docs and demo available for preparation | Student books/attends session and explains work without AI answering questions |

## Source documentation review

AST inspection found module docstrings in all 10 package files and docstrings for
all 31 public top-level functions/classes. This is a presence check, not a quality
score. Mathematical comments explain the angular guard, quadratic fitting,
simple-bridge topology and depth interpolation. Many shorter helper docstrings
do not use a uniform Args/Returns/Raises layout. Keep this limitation visible;
source bytes are intentionally preserved rather than rewriting frozen code for style.
The API generator renders the actual current docstrings, not invented contracts.

The old module allowlist omitted completion, reconstruction3d and matching.
The generator now discovers modules recursively, builds an index and a hash
manifest, and removes links to nonexistent local imported-library pages.
`python scripts/build_docs.py --check` verifies coverage, freshness and local links.

## Reproducibility and dependency review

NumPy/Pillow are core dependencies; pytest and Matplotlib are dev dependencies. pdoc was unused
and is removed from the dev extra because this repository uses standard-library
pydoc. Matplotlib is also available through the study extra. A clean-venv run
initially found 169 passes and two missing-Matplotlib failures; adding the actual
test dependency fixes setup without changing algorithms or tests. constraints-tested.txt records
the locally tested runtime/test versions, with environment details in the test report.
The clean installation, test and demo checks are documented in the current report;
they are distinct from historical experiment reproduction.

Large results stay ignored. Small numeric copies under docs/validation allow
review of headline evidence without raw RGB-D. All-case averages include refusals;
runtime records are copied, not rerun. Full Step 6.1 replay needs the separately
preserved evidence package. A clean Git clone supports the 171 tests and small
visible-mask demonstration; it is not claimed to reproduce external-data studies
without their recorded inputs and artifacts.

## Known issues retained without algorithm changes

1. Automatic detection uses the v2 angular ambiguity guard, while direct
   `complete_gaps` calls use a cosine gate. Exact-boundary manually supplied gaps
   can therefore differ from the automatic detector. Existing frozen evaluation
   passes through the detector; Step 7 does not change that evaluation.
2. `run_visible_baseline.py` permits an existing output directory. Always select a
   new run name. Other main reconstruction runners reject existing outputs.
3. The tracked demo calibration is a legacy format-audit fixture, not a complete
   current Calibration object. Do not add guessed real calibration fields.
4. No unified end-to-end RGB CLI exists; visible masks, occlusion and identities
   must be supplied and reviewed. Calibration flags/evidence are caller declarations.
5. Fixed Step 6.1 output paths and only two frozen code hashes limit fresh-run
   ergonomics. The separate full-source review snapshot supplies archival context.

## Branch and publication state

Start-of-preparation local branch: main, commit
`a7211681d62a36c55320b091176fdb4fd6ae7e31`.
Read-only `git ls-remote origin refs/heads/main` returned the same commit.
All src modules, experiment/replay scripts and tests are already committed there.
The newly regenerated HTML, revised README and Step 7 documents are working-tree
changes awaiting review; they are not yet present in committed or remote main.

No tracked raw RGB-D or large generated result files were found in the current
tree or reachable branch history. .gitignore excludes data/raw, data/processed,
results (except .gitkeep), virtual environments, caches and local output archives.
The existing raw files, previous experiments and Step 6.1 review ZIP are verified
by SHA-256, size and modification time. No experiments are regenerated.

See docs/validation/step7_verification.json and docs/07_test_report.md for executed
checks. Approval, commit/push, assessor access, final report/reflection and final
zipped clone remain separate actions. This audit does not mark those complete.
