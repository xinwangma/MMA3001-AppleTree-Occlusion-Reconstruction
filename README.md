# Occlusion-Aware Apple Tree Skeleton Reconstruction

MMA3001 — Numerical Methods and Machine Learning, 2026 individual project.
Version 0.1.0. Steps 1?6.1 are complete within the validation limits below.
Algorithms, numerical settings and historical experiments are frozen.

## Purpose and validation boundary

Estimate the trunk and two primary branches of an upright Y-shaped apple tree
when observations contain gaps. This is a **mask-assisted research prototype**:
it takes an explicit visible-branch mask; it does not segment branches from RGB.
RGB supports annotation and visual review. Whole-branch labels are evaluation
references and are never inference inputs.

Visible-only skeletonisation, Linear/Quadratic gap completion, fork-anchored
matching and calibrated synthetic 3D lifting are implemented. Hidden geometry is
labelled as inferred; unsupported physical coordinates remain null. The real
RGB-D depth encoding, calibration and registration are unverified. The 12 real
annotations remain AI DRAFT. **No real-world reconstruction accuracy is claimed.**
This prototype is not validated for pruning or robot control.

## Methods and final default

1. `baseline.py`: binary-mask validation, Zhang–Suen thinning and pixel graph.
2. `completion.py`: candidate screening and Linear/Quadratic completion with
   explicit occlusion support and topology checks.
3. `matching.py`: optional matching anchored at a single visible upright Y fork.
4. `reconstruction3d.py`: explicit-camera backprojection; optional hidden-Z
   interpolation between supported anchors. Surface depth is a proxy, not axis GT.

Retain **original Linear** as the default completion method. Keep visible-only,
Quadratic and both anchored variants for comparison. Frozen Step 6.1 evaluation:

| Method | Cases accepting completion / 96 | Correct connections | Incorrect connections |
| --- | ---: | ---: | ---: |
| Visible-only | 0 | 0 | 0 |
| Linear | 3 | 3 | 0 |
| Quadratic | 4 | 3 | 1 |
| Anchored Linear | 3 | 3 | 0 |
| Anchored Quadratic | 3 | 3 | 0 |

The anchored variants reject all 12 real drafts. They have not demonstrated a
reason to replace the simpler current default. These results do not establish
universal safety or superiority. The 24 development and 96 frozen evaluation
cases use different seeds/configurations from the **same simulator**, not
independent real trees. See the [full Step 6.1 report](docs/17_step61_fork_matching.md)
and [small frozen evidence snapshot](docs/validation/step61_summary.json).
Default selection is post-evaluation interpretation, not an additional test set.

## Repository map

```text
src/apple_tree_project/  manifest, audit, alignment, visible_annotation,
                        metrics, baseline, completion, matching, reconstruction3d
scripts/                runnable annotation, reconstruction, evaluation, replay,
                        and HTML documentation tools
tests/                  171 tests plus small synthetic regression fixtures
data/demo/              small synthetic format fixture, tracked
data/annotations/       RGB-only AI draft polygons, tracked; no source photographs
docs/                   methods, validation, AI log, current repository audit
docs/api/index.html     generated offline HTML for all 10 package modules
docs/validation/        compact numeric evidence and current verification summary
results/                local generated experiments; ignored except .gitkeep
data/raw/               original external RGB-D data; ignored
```

## Install and test

Python 3.10+ is declared. The locally verified preparation environment is Windows,
CPython 3.13.7. CI configuration uses Ubuntu/Python 3.11; this preparation does not
claim that a new remote CI run has completed. NumPy and Pillow are runtime
dependencies; pytest and Matplotlib are development/test dependencies. HTML generation uses Python's
standard-library `pydoc`, so pdoc/Sphinx is not required.

From the repository root in Windows PowerShell:

```powershell
py -3 -m venv .venv
# Direct interpreter paths avoid an activation-policy requirement.
.\.venv\Scripts\python.exe -m pip install -c constraints-tested.txt -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.\.venv\Scripts\python.exe scripts/build_docs.py --check
```

`constraints-tested.txt` records the tested runtime/test package versions for
CPython 3.13; it is not an exhaustive cross-platform lock. On Python 3.10 use
the unconstrained dependency ranges instead. Unconstrained supported installation is
`python -m pip install -e ".[dev]"`. Optional `.[study]` adds Matplotlib for
experiment plotting without pytest. Two existing Step 6 tests also import the
study runner, so the full suite needs Matplotlib. HTML generation and the
visible-mask demo do not need it.
For Unix, use `.venv/bin/python` in place of the Windows interpreter path.

The complete current suite has **171 passing tests**. See the
[current test report](docs/07_test_report.md) for environment, commands and limits.

## Run a demonstration without raw data

The small synthetic fixture is already tracked. Do not regenerate it just to use
the demo: the generator rewrites its files. Give every run a new output directory:

```powershell
$run = Get-Date -Format "yyyyMMdd_HHmmss_fff"
.\.venv\Scripts\python.exe scripts/run_visible_baseline.py --output "results/demo_visible_$run"
```

Inspect `overlay.png`, `skeleton.png`, `graph.json` and `report.json` in that new
directory. This demonstrates input handling and skeleton extraction, not real
reconstruction accuracy. The baseline runner can overwrite an existing output;
always use a new name. Other reconstruction runners require a new output.

Custom RGB and native-grid binary masks:

```powershell
.\.venv\Scripts\python.exe scripts/run_visible_baseline.py `
  --rgb "path/to/rgb.png" --visible-mask "path/to/visible.png" `
  --provenance manual_visible --output "results/my_visible_001"
```

Masks must be single-channel binary 0/1 or 0/255 and match the RGB dimensions.
The polygon editor is `scripts/annotate_visible_branches.py --help`; its GUI
needs Tkinter and independent human review of saved drafts.

## Completion, 3D and experiment reproduction

- `scripts/run_branch_completion.py --help` compares Linear and Quadratic using
  an explicit skeleton, occlusion mask and gaps JSON. Endpoint roles and occlusion
  must not be fabricated from whole GT. There is no unified end-to-end RGB CLI.
- `scripts/run_3d_reconstruction.py --help` lifts a graph with scalar depth,
  branch support and a **complete verified Calibration contract**. Hidden-depth
  inference is off unless explicitly enabled. `data/demo/calibration.json` is a
  legacy audit fixture and is not a complete 3D calibration file.
- Automatic detection applies the v2 angular ambiguity guard. Direct manually
  supplied gaps use the existing completion cosine gate; these boundaries are
  not identical. This known limitation is recorded, not changed in Step 7.
- All unit tests and the visible demo run from a clean clone without real data
  or archived experiments. Full historical evaluations and observation replay
  require external saved artifacts. See [reproduction and submission instructions](docs/20_reproducibility.md).

The original RGB-D dataset and large experiment directories are deliberately
absent from Git. Local gallery paths such as `results/step61_fork_matching/index.html`
work only when the separate evidence package is available. Do not run the fixed
Step 6.1 develop/evaluate commands over the frozen output directory.

## Documentation and submission

```powershell
.\.venv\Scripts\python.exe scripts/build_docs.py
.\.venv\Scripts\python.exe scripts/build_docs.py --check
```

Open [the HTML API index](docs/api/index.html). Every package module is discovered
automatically; a source/page hash manifest detects missing or stale pages.

The [current reproducibility guide](docs/20_reproducibility.md) describes clean-clone
verification, saved-result replay and the external data required by historical runs.
The [repository repair record](docs/21_repository_repair.md) lists code cleanup,
backups, exact removals, tests and remaining limitations. Previous compliance and
submission documents remain as historical academic records.

## Completed development stages

| Stage | Completed work | Evidence |
| --- | --- | --- |
| 1 | Engineering definition, input contracts, audit and metric scaffold | [Definition](docs/01_project_definition.md) |
| 2 | RGB-D inventory, annotation/alignment investigation | [Data inspection](docs/09_real_dataset_inspection.md), [alignment](docs/10_annotation_alignment.md) |
| 3 | Mask-assisted skeleton and independent RGB-only annotation workflow | [Baseline](docs/11_visible_only_baseline.md), [draft review](docs/13_step3_annotation_revision.md) |
| 4 | Linear/Quadratic gap completion and sensitivity study | [Completion](docs/14_step4_branch_completion.md) |
| 5 | Calibrated synthetic 3D lifting; unresolved real calibration documented | [3D study](docs/15_step5_3d_reconstruction.md) |
| 6 | Paired validation, profiling and conservative v2 numerical boundaries | [Validation](docs/16_step6_final_validation.md), [stability](docs/16_step6_numerical_stability.md) |
| 6.1 | Frozen fork-anchored comparison and saved-result verification | [Matching study](docs/17_step61_fork_matching.md) |

Completion of these stages does not imply verified real-tree reconstruction or
completion of the student's separate final report/presentation obligations.

## Saved results and local-only evidence

Small original metrics and selected synthetic figures are available in
[the compact review index](docs/reproducibility/step61/index.html). These are
copies of frozen evidence, not new experiments or an additional test set.

Large arrays, graph archives and RGB-D remain outside Git. If the separately
provided synthetic replay archive is available, extract it outside the repository
and run:

```powershell
.\.venv\Scripts\python.exe scripts/replay_step61_saved.py `
  --project . --results "path/to/step61_synthetic"
```

Expected: 600 saved metric rows checked and 480 evaluation graphs replayed.
The replay does not call the simulator or read truth as an inference input.
It accepts only CRLF/LF conversion when checking frozen source hashes; numerical
code changes still fail the source check. Historical results are never rewritten.
All observations in this replay archive are synthetic; no Monash RGB-D is included.

## Data, licence and AI use

The external Monash Y-shaped Tree Dataset is described in
[the dataset inspection](docs/09_real_dataset_inspection.md) and
[data integration guide](docs/04_data_integration.md). Alignment remains provisional.
Keep original files unchanged; confirm third-party redistribution terms separately.

[MIT LICENSE](LICENSE) covers original project code/documentation only, not
third-party RGB-D data, photographs or labels. NumPy, Pillow and other dependencies
retain their own licences. The generic copyright attribution should be confirmed
by the student before final publication.

AI assistance is disclosed in [the AI usage log](docs/03_ai_usage_log.md). The
student remains responsible for decisions, verified claims, references and the
final contribution estimate and personal reflection. AI cannot certify human
annotation acceptance or student understanding.
