# Reproduction and final repository ZIP instructions

## 1. Source-only verification

Use a short working path on Windows to avoid long-path extraction failures.
Python 3.10+ is declared; the recorded constrained environment is CPython 3.13.7.
On Python 3.10 use the unconstrained supported dependency ranges in pyproject.toml;
the recorded NumPy constraint is intended for the tested newer interpreter.

From the project root:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c constraints-tested.txt -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.\.venv\Scripts\python.exe scripts/build_docs.py --check
```

Expected: 171 tests pass and 10 modules pass API freshness/local-link checks.
Regenerate HTML only when needed with `python scripts/build_docs.py`; inspect
the diff rather than generating it during final clone packaging. Tests use
synthetic temporary fixtures and do not require the original dataset.

The baseline demo reads the already tracked synthetic fixture:

```powershell
$run = Get-Date -Format "yyyyMMdd_HHmmss_fff"
.\.venv\Scripts\python.exe scripts/run_visible_baseline.py --output "results/demo_$run"
```

Always use a new output directory. No instruction here requires rewriting the
tracked fixture or any existing experiment directory.

## 2. Full experiment evidence and replay

Git intentionally excludes raw RGB-D and large generated results. The separate
Step 6.1 review ZIP contains full source, frozen development/evaluation arrays,
graphs, figures, historical v2 evidence, original metrics and verification logs.
It is an evidence archive, not the required final zipped Git clone.

In the extracted Step 6.1 review package:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH=(Resolve-Path project/src).Path
python verification/verify_saved_step61.py --project project
```

Use an environment containing NumPy, Pillow and pytest as recorded by that
package. Expected: 600 development/evaluation metric rows checked and 480 saved
evaluation graphs replayed. Metric recomputation reads references only on the
evaluation side. Observation replay reads only visible/depth/occlusion and
calibration, never truth arrays or a new simulator scene. Coordinates use
atol=1e-12, rtol=1e-10; topology, identity and statuses are exact.

The original timings remain original records; reading/replaying them is not a
new runtime benchmark. Do not re-run `evaluate_step61.py develop/evaluate` into
existing frozen directories. Real gallery regeneration needs the external RGB
dataset/draft annotations and does not establish physical 3D accuracy.

Tracked docs/validation/step61_summary.json and step61_frozen_plan.json are small
copies of recorded evidence; they are not replacements for the full replay inputs.

## 3. Final review before publication

The Brief (PDF p. 8) requires an accessible GitHub link and a zipped CLONE through
Moodle. The final written report is a separate individual deliverable. This task
does not authorise a commit, push or submission.

Before a later approved release:

1. Review the Step 7 diff and docs/18_step7_repository_audit.md. Confirm the
   student copyright attribution, contribution estimate and personal reflection.
2. Check `git diff --check`, the 171-test report and
   `python scripts/build_docs.py --check`.
3. After explicit approval, commit only intended source/config/docs files,
   including new HTML, api_manifest.json, index.html and compact validation data.
   Do not force-add ignored raw data, results, environments, caches or ZIPs.
4. Push the approved commit to main and confirm its SHA against
   `git ls-remote origin refs/heads/main`. Check CI and assessor permissions.

No git commit/push command is executed during this preparation.

## 4. Create the final zipped clone AFTER approval and publication

Use the already tested project virtual environment, located outside the new
clone. The following commands perform a fresh clone, verify it without creating
bytecode/cache files, and zip the entire clone including its .git history.
Choose a new destination and output ZIP name if either already exists.

```powershell
# Start in the existing project root, after the approved commit was pushed.
$verificationPython=(Resolve-Path .venv/Scripts/python.exe).Path
$submissionRoot=Join-Path $env:TEMP ("MMA3001_submission_"+(Get-Date -Format "yyyyMMdd_HHmmss_fff"))
New-Item -ItemType Directory -Path $submissionRoot | Out-Null
Set-Location $submissionRoot
git clone --branch main --single-branch https://github.com/xinwangma/MMA3001-AppleTree-Occlusion-Reconstruction.git MMA3001_Final_Repository
Set-Location MMA3001_Final_Repository
git branch --show-current
git rev-parse HEAD
git status --short
git ls-files data/raw data/processed results
# Expected last output: results/.gitkeep only; status should be empty.
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH=(Resolve-Path src).Path
& $verificationPython -m pytest -q -p no:cacheprovider
& $verificationPython scripts/build_docs.py --check
git diff --check
Set-Location ..
& $verificationPython -m zipfile -c MMA3001_Final_Repository.zip MMA3001_Final_Repository
& $verificationPython -m zipfile -t MMA3001_Final_Repository.zip
Get-FileHash -Algorithm SHA256 MMA3001_Final_Repository.zip
```

Inspect the archive inventory before submitting. It should include README,
LICENSE, pyproject.toml, constraints-tested.txt, src, scripts, tests, docs/api,
the compact documentation evidence and .git, with no raw dataset, results runs,
virtual environment, PDF Brief or former review ZIP. Python's zipfile includes
hidden .git files, unlike some GUI/PowerShell archive workflows. `git archive`
and GitHub Download ZIP omit .git history and are not used here as a substitute
for the Brief's zipped clone wording.

The clone procedure cannot include uncommitted Step 7 changes. Do not package
the old remote main while these updates are still awaiting review.

Submit the final accessible repository URL and zipped clone through the required
course channels; confirm due dates in the Unit Overview Spreadsheet. Prepare the
individual 5-minute presentation and 3-minute questions (Brief p. 9), including
engineering limits and AI reflection. Do not claim that test success proves
verified real-tree reconstruction accuracy.
