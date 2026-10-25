# Reproducing the completed Step 1–6.1 project

This guide describes the existing implementation and saved experiments. It does
not introduce new algorithms, rerun optimisation or replace historical results.
Original Linear remains the default; Quadratic and fork-anchored variants are
comparison alternatives. Real masks remain unverified drafts and real metric
reconstruction is unsupported without independently verified calibration.

## Install a clean checkout

Clone the approved main branch into a new, short directory. The currently
published a721168 commit does not include the uncommitted documentation/dependency
repairs. A fresh clone alone cannot contain those repairs until review and a later
approved commit/push. Local audit results distinguish that baseline clone from
the same clone with the reviewed working-tree changes applied.

```powershell
git clone --branch main --single-branch https://github.com/xinwangma/MMA3001-AppleTree-Occlusion-Reconstruction.git apple-tree
Set-Location apple-tree
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,study]"
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.\.venv\Scripts\python.exe scripts/build_docs.py --check
```

Expected for the repaired version: 171 tests pass and all 10 module API pages are
current. Matplotlib is needed by two existing Step 6 tests because the study
runner imports it before its output guards. It is included in the dev extra;
explicit `.[dev,study]` also supports the earlier packaging layout. NumPy/Pillow
are core dependencies. pypdf is not a project dependency: it was a temporary PDF
reading tool, and its retired staging code can be removed safely.

The recorded constraint set targets CPython 3.13.7 on Windows:
`pip install -c constraints-tested.txt -e ".[dev,study]"`.
For Python 3.10, use the supported unpinned ranges instead of the newer NumPy pin.
On Unix use `.venv/bin/python`; no custom PYTHONPATH is needed after installation.
Tkinter is needed only for the interactive annotation GUI.

## What works using repository files only?

| Command/tool | Inputs | Scope |
| --- | --- | --- |
| `python -m pytest -q -p no:cacheprovider` | Tracked tests and synthetic fixtures | 171 verification tests, no real data |
| `python scripts/build_docs.py` / `--check` | Current source and docstrings | Build/check offline HTML for all package modules |
| `python -m apple_tree_project.audit data/demo/manifest.csv` | Tracked synthetic format fixture | File pairing, dimensions and provisional metadata checks |
| `python scripts/run_visible_baseline.py --output results/NEW_NAME` | Tracked synthetic visible mask/RGB | New mask-assisted skeleton/graph demonstration |
| `python scripts/run_branch_completion.py --help` | Help requires installed package only | Actual run requires explicit skeleton, occlusion mask and gaps JSON |
| `python scripts/run_3d_reconstruction.py --help` | Help requires installed package only | Actual run requires graph, scalar depth, branch support and complete calibration |
| `python scripts/replay_step61_saved.py --help` | Repository only | Actual replay requires separately saved synthetic observations and graphs |

The visible demo requires no regeneration of `data/demo`; `make_demo_manifest.py`
rewrites that tracked fixture and is not needed for ordinary usage. The demo's
legacy calibration JSON is sufficient for format auditing, not for constructing
the current `Calibration` class. Do not fill its missing real-world fields by guessing.

Always choose a new output name. The baseline runner can overwrite existing
outputs; the completion and 3D runners reject existing output directories.

## Which historical experiments need external artifacts?

| Script | Required external/local-only inputs |
| --- | --- |
| `inspect_monash_dataset.py`, `compare_annotation_alignment.py` | Authorised original Monash folders; alignment outputs written separately |
| `prepare_visible_review.py` | Earlier alignment report plus original RGB data |
| Annotation editor/reviewer and real-mask validation | Original RGB plus independent native-grid polygons/review records |
| `evaluate_step4.py` | Its synthetic functions are self-contained; the complete CLI also reads Step 3 saved drafts/skeletons and their RGB sources |
| `evaluate_step5.py` | Original depth files, Step 4 saved completion and associated real draft data |
| `evaluate_step6.py` | Saved Step 4/5 evidence and Step 3 real drafts; it also runs new experiments/timings, so is not a read-only replay command |
| `evaluate_step6_boundary_policy.py` | Original Step 6 evidence and archived v1 source in its history folder |
| `evaluate_step61.py develop` | v2 `decisions.json`, `all_case_metrics.json`, and holdout_39 observations/calibration |
| `evaluate_step61.py evaluate` | Frozen plan and completed development phase, plus Step 3 real drafts and their original RGBs for the qualitative gallery |

The full Step 6.1 CLI therefore cannot reproduce the entire historical study from
an empty Git clone. It intentionally combines synthetic evaluation, historical
failure analysis and real-image review. Its output path is fixed and protected;
do not delete or overwrite it to force a rerun. Recreating historical development
and timings is different from verifying saved results, and was not done in this repair.

## Read-only Step 6.1 replay without the Monash dataset

The separate `MMA3001_Step61_Synthetic_Replay.zip` contains the original synthetic
development/evaluation arrays, calibrations, saved graphs, decisions and metrics.
Selected figures and the technical report are preserved copies. All RGB views
from real Monash images are excluded. The small repository review index contains
only numeric evidence and selected synthetic PNGs, not the large arrays/graphs.

Check the ZIP's supplied SHA-256 sidecar, then extract to a new external folder:

```powershell
python -m zipfile -t "PATH/MMA3001_Step61_Synthetic_Replay.zip"
python -m zipfile -e "PATH/MMA3001_Step61_Synthetic_Replay.zip" "PATH/new_replay_folder"
python scripts/replay_step61_saved.py --project . --results "PATH/new_replay_folder/step61_synthetic"
```

Expected: 600 development/evaluation metric rows recomputed from saved graphs,
and 480 evaluation graphs replayed from observations. Replay inference reads
visible/depth/occlusion and calibration only. Truth/reference arrays are used
only by the metric audit. No scene simulation or runtime benchmark is rerun.
Topology, identity and statuses are exact; geometry uses the archived comparator's
atol=1e-12, rtol=1e-10. The original timing records are preserved, not remeasured.

The original frozen source hashes were recorded on Windows. The new replay
entrypoint accepts the original bytes or an LF/CRLF-only conversion; any other
change to the checked completion/matching source is rejected. The original frozen
plan and source algorithms are not edited to bypass this check. This addresses
fresh-clone line endings without changing numerical policy or results.

For the larger original review package, the same entrypoint can target its
`project/results/step61_fork_matching` folder. It does not require the old v2 or
real-image folders because it calls only the saved-observation/metric audit path.
The Step 5 and Step 6 replay scripts remain available for their respective saved
artifacts: use their `--help` to select evidence/source roots explicitly.

## Obtain and prepare authorised real data

Use the [official Monash dataset page](https://www.monash.edu/engineering/lmga/news/y-shaped-tree-dataset-for-tree-branch-prediction)
and its publisher-provided download link. The page currently links to
[the publisher's Drive file](https://drive.google.com/file/d/1-6akVXezq26ihtDrVH9czGUQDFd8Py81/view?usp=drive_web).
Confirm the applicable licence/access terms; if access or interpretation is
unclear, contact the publisher through the official page. A download link is not
permission to redistribute the dataset in a public Git repository.

1. Keep originals unchanged in an ignored local data folder. The inspected layout
   was `data/raw/monash_y_tree/TreeID/{Dataset,Dataset (With Summer GT)}`; use
   `--root` with the inspector if your authorised copy is elsewhere.
2. Inventory files and hashes with `inspect_monash_dataset.py --root PATH`.
   Compare with docs/09_real_dataset_inspection.md; do not assume a new download
   has the same counts or modalities as the inspected copy.
3. Confirm native grids and investigate annotation alignment. Do not stretch GT
   into place and then describe that hypothesis as verified registration.
4. Supply RGB-only visible masks with honest provenance and independent review.
   The 12 stored AI drafts are not accepted human truth. Provide confirmed
   occlusion/branch identity before treating completion as supported geometry.
5. Verify scalar depth decoding, intrinsics, rectification and RGB-depth
   registration before physical 3D projection. An evidence string/boolean alone
   is a caller declaration, not independent calibration proof.
6. Restore authorised historical result archives separately when replaying the
   full stage chain. Use new output directories for any future authorised runs.

Do not upload raw RGB-D, derived photographs or large experiment archives to Git.
Tests/synthetic examples do not establish real anatomical or physical 3D accuracy.
Default Linear and all comparison methods retain their original validation limits.
