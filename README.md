# Occlusion-Aware 3D Apple Tree Skeleton Reconstruction

**MMA3001 | Numerical Methods and Machine Learning**  
**Project type:** Individual engineering computing project  
**Development status:** Step 5 - calibrated synthetic 3D lifting implemented; real metric 3D unsupported pending calibration
**Version:** 0.1.0

> **Important:** Linear and quadratic 2D gap completion are implemented and tested on synthetic Y trees. The 12 real RGB draft examples are qualitative hypotheses only, not verified ground truth or evidence of real-data accuracy. Calibrated 3D lifting is validated on synthetic trees; real metric 3D remains unsupported because depth decoding, calibration and registration are unverified. See [Step 5 report](docs/15_step5_3d_reconstruction.md) and [3D gallery](results/step5_3d_reconstruction/index.html). See [Step 4 report](docs/14_step4_branch_completion.md) and the [results gallery](results/step4_occlusion_completion/index.html).

## 1. Project overview

Agricultural robots need information about tree trunks and branches for tasks such as orchard inspection, navigation and pruning. However, leaves and other objects can hide parts of a branch. A camera provides colour information, and a depth sensor provides distances to visible surfaces; neither directly observes the geometry hidden behind an obstruction.

This project investigates whether an **occlusion-aware geometric branch-completion method** can estimate the missing main branches of Y-shaped apple trees more reliably than a **visible-only baseline**. A simplified three-dimensional (3D) skeleton is the intended engineering output, with inferred segments explicitly distinguished from measured segments.

### Research question

> Can an occlusion-aware geometric branch-completion algorithm improve the completeness of Y-shaped apple-tree skeletons compared with visible-only reconstruction, while maintaining reasonable geometric consistency and computational efficiency?

### Project objectives

1. Inspect and validate paired RGB images, depth maps and branch annotations.
2. Implement a visible-only baseline for the trunk and two primary branches.
3. Develop a geometric algorithm to estimate partially occluded main branches.
4. Use calibrated depth observations, when available, to recover observed 3D points; label hidden 3D segments as inferred estimates.
5. Evaluate the baseline and proposed method on held-out annotations using transparent metrics, runtime analysis and sensitivity tests.
6. Document assumptions, limitations, reproducibility and the use of AI tools.

## 2. Dataset and provenance

**Candidate dataset:** Monash University — [Y-shaped Tree Dataset for Tree Branch Prediction](https://www.monash.edu/engineering/lmga/news/y-shaped-tree-dataset-for-tree-branch-prediction).

The published dataset description reports **435 RGB-D images** across summer, autumn and winter, with *position*, *visible-branch* and *whole-branch* annotations. The local file structure and pixel encodings have been inventoried. Precise annotation alignment, depth scale and camera calibration remain unresolved; no 3D ground truth was found. See docs/09_real_dataset_inspection.md and docs/10_annotation_alignment.md.

The original dataset is **not redistributed** in this repository; check its applicable terms before storing or sharing data. See [`docs/04_data_integration.md`](docs/04_data_integration.md).

## 3. Inputs and outputs

| Component | Intended format | Role |
| --- | --- | --- |
| RGB image | `height x width x 3` image | Colour observation |
| Depth image | `height x width` array/image | Depth of visible surfaces; physical scale must be verified |
| Visible-branch annotation | Binary mask or converted annotation | Baseline input / evaluation reference |
| Camera calibration | Intrinsics and depth unit conversion, if available | Project visible observations into metric 3D |
| Whole-branch annotation | Binary mask or converted annotation | Training/validation label; **not an inference-time input** |
| Season and tree ID | Sample metadata | Robustness study and leakage-aware data split |
| Completed branch mask | Binary image | Predicted visible and inferred branch pixels |
| Skeleton graph | Nodes and edges | Main trunk and branch connectivity |
| 3D skeleton | Coordinates plus observed/inferred flags | Simplified spatial tree structure, subject to calibration |
| Evaluation report | CSV / JSON / figures | Accuracy, robustness and runtime evidence |

**Scope:** The intended reconstruction focuses on the trunk and two major branches of Y-shaped trees. Full canopy reconstruction, fine twigs, and robot control are out of scope.

## 4. Proposed computational approach

### Method A — Visible-only baseline

Extract centreline structure from the available visible branches. This method provides a simple comparison and, by definition, does not recover fully occluded branch sections.

### Method B — Occlusion-aware geometric completion

Locate the Y-junction and visible branch fragments; estimate a plausible continuation through gaps using fitted curves and geometric constraints; then represent the visible and inferred segments in a connected skeleton graph. Candidate techniques include least-squares curve fitting and constrained interpolation. Final details and parameter values will be selected after inspecting real annotations.

### Depth-assisted 3D reconstruction

When the depth representation, camera registration and intrinsics are verified, valid visible pixels may be back-projected into camera coordinates. Fully hidden segments have no directly observed depth and therefore require explicit geometric assumptions. **A plausible 3D rendering is not itself proof of 3D accuracy.**

## 5. Validation plan

For a completed-branch prediction mask `P` and whole-branch ground truth `W`:

- **Precision:** `TP / (TP + FP)`
- **Recall:** `TP / (TP + FN)`
- **F1 score:** `2TP / (2TP + FP + FN)`
- **Intersection over Union (IoU):** `TP / (TP + FP + FN)`
- **Hidden-branch recall:** fraction of reference pixels in `W AND NOT V` recovered by `P`, where `V` is the visible-branch label.

Compare both approaches on appropriately held-out data and measure runtime. Study sensitivity to missing branch length, noise, fitting settings and, where supported, seasons. Group repeated observations of the same tree together when constructing data splits to avoid leakage.

**Validation boundary:** Whole-branch labels support 2D branch-completion evaluation. Do **not** claim quantitative 3D reconstruction accuracy without reliable 3D ground truth or an independently justified metric benchmark.

Full details: [`docs/02_validation_protocol.md`](docs/02_validation_protocol.md).

## 6. Repository structure

```text
.
├── .github/workflows/tests.yml  # Automated tests on GitHub
├── data/                       # README and synthetic demonstration fixture
├── docs/                       # Project definition, validation, logs, test report
│   └── api/                    # Generated HTML source documentation
├── results/                    # Generated output (ignored by Git)
├── scripts/                    # Fixture generator and docs generator
├── src/apple_tree_project/
│   ├── manifest.py             # Paired input paths and sample metadata
│   ├── audit.py                # RGB-D / annotation consistency checks
│   └── metrics.py              # Precision, recall, F1, IoU and hidden recall
├── tests/                      # Automated verification of foundation code
├── .gitignore
├── LICENSE
├── pyproject.toml
└── README.md
```

## 7. Installation and usage (Windows PowerShell)

**Requirements:** Python 3.10+ and Git (for version control).

Clone the GitHub repository or open the downloaded project folder, then run:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### Run the unit tests

```powershell
python -m pytest -q
```

### Create and audit a synthetic RGB-D fixture

```powershell
python scripts/make_demo_manifest.py
python -m apple_tree_project.audit data/demo/manifest.csv --json-output results/demo_audit.json
```

This checks file pairing, dimensions, depth validity and provisional annotation consistency. The generated fixture is **synthetic** and cannot be used as evidence of reconstruction accuracy.

### Generate HTML API documentation

```powershell
python scripts/build_docs.py
```

Open the HTML file(s) inside `docs/api/`. API documentation describes the implemented modules and should be regenerated after code changes.

## 8. Current implementation status

| Component | Status |
| --- | --- |
| Engineering problem and scope | Complete — initial definition |
| Manifest loading and metadata checks | Implemented |
| RGB-D / annotation input audit | Implemented |
| Binary prediction metrics | Implemented |
| Synthetic input-format fixture | Implemented; demonstration only |
| Automated tests and initial test report | Implemented |
| Real dataset decoding and calibration | Inventory complete; alignment provisional; depth calibration unresolved |
| Visible-only baseline reconstruction | Implemented: mask-assisted 2D skeleton/pixel graph; synthetic demonstration only |
| Occluded-branch completion | Planned |
| Full 3D skeleton reconstruction | Planned |
| Held-out quantitative model evaluation | Planned |

See the dated [`development log`](docs/05_development_log.md) and [`test report`](docs/07_test_report.md). Test counts are specific to the code version and must be re-run after changes.

## 9. Development roadmap

- **Step 1:** Project definition, reproducible repository and input-audit foundation.
- **Step 2:** Inspect the real dataset; document annotation schema, depth units and calibration.
- **Step 3:** Implement the visible-only skeleton baseline.
- **Step 4:** Implement geometry-based completion of partially occluded branches.
- **Step 5:** Project observations into 3D and identify inferred geometry.
- **Step 6:** Evaluate on held-out images/trees; compare methods, robustness and runtime.
- **Step 7:** Finalise the 5–10 page report, HTML API docs, tests, AI reflection and demonstration.

## 10. AI usage and academic integrity

ChatGPT assisted with the initial requirements interpretation, project scoping, repository structure, code scaffolding, tests and English draft documentation. The student must review and test generated material, make and justify technical decisions, record errors and revisions, and be able to explain the methods independently at the presentation. Actual AI contributions should be updated throughout development in [`docs/03_ai_usage_log.md`](docs/03_ai_usage_log.md).

## 11. Key references

1. Monash University, *Y-shaped Tree Dataset for Tree Branch Prediction* — [dataset description](https://www.monash.edu/engineering/lmga/news/y-shaped-tree-dataset-for-tree-branch-prediction).
2. Nti, I. K. et al. (2022), *Applications of artificial intelligence in engineering and manufacturing: a systematic review*, *Journal of Intelligent Manufacturing*, 33, 1581–1601. [DOI: 10.1007/s10845-021-01771-6](https://doi.org/10.1007/s10845-021-01771-6).
3. *MMA3001 2026 Project Brief*, Monash University (course assessment requirements).

## 12. Licence

The project scaffold includes an MIT licence for the original source code. This licence **does not** apply to third-party images, annotations, datasets or models. Review the licence choice and data usage restrictions before publication.

### Real-data alignment stage (23 October 2026)

The real dataset inventory is complete; annotation alignment candidates have now been compared on all 562 Summer RGB/GT pairs. See [annotation alignment evidence and baseline decision](docs/10_annotation_alignment.md) and [the existing inventory](docs/09_real_dataset_inspection.md). Full-frame stretch is provisional; a reviewed mismatch prevents claiming universal registration. A 2D visible-only prototype can proceed with independent visible labels, while supervised evaluation and metric 3D remain gated. Generate local comparisons with `python scripts/compare_annotation_alignment.py`; outputs are saved under `results/alignment_candidates/`.

### Step 3 visible-only baseline

Run `python scripts/run_visible_baseline.py` for the existing synthetic demonstration. Outputs (prediction, skeleton, pixel graph, overlay and provenance report) go to `results/visible_only_baseline/`. See [methods, usage, tests and limitations](docs/11_visible_only_baseline.md). The baseline preserves visible-mask gaps and never reads whole GT. Real-data evaluation requires independent visible labels; precise Summer GT alignment remains unresolved.

### Step 3 real-RGB review

The baseline requires an external visible mask; it does not segment RGB. A native
RGB polygon editor (`scripts/annotate_visible_branches.py`) and batch diagnostic
runner (`scripts/validate_visible_baseline.py`) now support reproducible review.
A 12-image experiment used explicitly AI-authored RGB-only draft polygons, with
0 human-accepted samples. See [actual diagnostics, commands and limitations](docs/12_step3_real_data_review.md).
Full suite after coverage-review improvements: 63 tests pass. Independent human real-data accuracy validation remains
pending; Step 4 has not started.

See the [Step 3 coverage revision guide](docs/13_step3_annotation_revision.md) for
zoom/pan, vertex editing, visible/occluded checkpoints, separate review/approval,
graph warnings and final v4 before/after figures. Ten samples received conservative
visible-wood revisions; two were retained because of ambiguity. All remain DRAFT.
Open `results/step3_real_validation/coverage_revision_v4/run/index.html` locally.
