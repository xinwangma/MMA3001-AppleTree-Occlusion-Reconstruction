# Step 1 — Engineering Problem Definition

## Project title
**Occlusion-Aware 3D Skeleton Reconstruction of Y-Shaped Apple Trees Using RGB-D Data**

## 1. Engineering context

Agricultural robots used for orchard inspection, robotic pruning and navigation
need reliable information about the geometric arrangement of trunks and major
branches. Leaves, fruits, and crossing branches may occlude parts of the tree.
RGB images alone cannot directly measure depth, while depth cameras observe
visible surfaces rather than geometry behind an occluder.

## 2. Problem statement

Estimate a plausible, simplified skeleton of the *trunk and two primary
branches* of a Y-shaped apple tree from incomplete RGB-D observations. The
method must distinguish observed branch segments from inferred occluded
segments and make uncertainty and validation limitations explicit.

## 3. Research question

Can an occlusion-aware geometric branch-completion method improve predicted
branch completeness relative to a visible-only baseline, while preserving
reasonable branch geometry and computational efficiency?

## 4. Scope

**Included:** Paired RGB/depth processing; visible-branch masks; Y-junction
identification; baseline visible-only skeleton; geometric completion of
partially hidden *primary* branches; simplified 3D skeleton; reproducible
2D label-based validation; sensitivity to occlusion and key parameters.

**Excluded:** Whole-orchard mapping, full canopy/leaf reconstruction, detailed
secondary-twig geometry, robotic path planning, closed-loop robotic control,
and unverified claims of millimetre-level 3D accuracy.

## 5. Input/output contract (provisional, pending dataset inspection)

| Input | Format | Meaning | Unit |
| --- | --- | --- | --- |
| RGB image | H x W x 3 | Registered colour observation | 8-bit image intensity |
| Depth map | H x W | Registered depth or distance measurement | Raw depth units; conversion must be verified |
| Visible-branch annotation | H x W mask or convertible annotation | Visible tree pixels | Binary |
| Camera intrinsics | fx, fy, cx, cy | Required for calibrated camera-frame projection | Pixels |
| Whole-branch annotation | H x W mask or convertible annotation | Supervision/evaluation target **only** | Binary |
| Tree/season metadata | Strings | Splitting and robustness studies | N/A |

| Output | Meaning | Unit |
| --- | --- | --- |
| Predicted complete-branch mask | Estimated visible + hidden major branches | H x W binary mask |
| Branch topology | Trunk and main limbs, connected at Y-junction | Graph |
| Simplified 3D skeleton | Estimated nodes and edges, observed nodes distinguished from inferred nodes | Metres only after depth calibration |
| Performance report | F1, IoU, hidden-branch recall, runtime, sensitivity | Unitless + seconds |

**Unsupported input policy:** Files with inconsistent dimensions, missing
paired modalities, invalid depth, or incompatible label encoding are flagged
by the audit rather than silently accepted. 3D reconstruction in physical
units is deferred if camera intrinsics or depth scale cannot be established.

## 6. Computational proposal

**Baseline A:** visible-branch mask followed by skeleton extraction, with no
occlusion completion. It cannot recover invisible parts by construction.

**Proposed B:** locate Y-junction and visible branch fragments; fit smooth
branch centreline curves with geometric constraints (e.g., least squares),
connect consistent endpoints across plausible gaps, and lift visible segments
using valid RGB-D depth. Inferred hidden segments must be marked as such.

The precise curve parameterisation, thresholds and projection procedure will
be finalised **only after examining actual data**.

## 7. Validation strategy

The known whole-branch annotation can supervise or evaluate **2D branch
completion**. On withheld samples compare both methods using binary F1 and
IoU, and measure recovery of pixels in the hidden ground-truth region.
Perform season/occlusion and parameter sensitivity analysis, with explicit
runtime measurement. Reserve test data; do not tune parameters on test labels.
If reliable metric 3D ground truth is absent, do not claim a numerical 3D
accuracy; instead report projection consistency, calibration dependence and
visual geometric plausibility as weaker evidence.

## 8. Anticipated limitations

A single-view depth image cannot directly recover surfaces behind leaves.
Geometric completion may fail for highly curved, broken, or atypical branches.
Available annotations may be only 2D; data identity/split metadata may be
insufficient to prevent leakage without manual grouping. Segmentation-derived
inputs and annotation-derived inputs represent different experimental settings.

## 9. Engineering success criteria

A defensible success is not 'perfect 3D reconstruction'. It is an executable,
reproducible, well-tested pipeline whose completion method improves valid
whole-branch/hidden-branch 2D scores over the baseline on a properly held-out
set, with geometric limitations and computation costs explained. If no
improvement is observed, report that negative result and its causes honestly.

## 10. Source basis

- MMA3001 2026 Project Brief, pp. 1–15 (course assessment requirements).
- Nti et al., *Applications of artificial intelligence in engineering and
  manufacturing: a systematic review*, Journal of Intelligent Manufacturing,
  33 (2022), 1581–1601, DOI:10.1007/s10845-021-01771-6 (motivation and
  justification of method evaluation, not an implementation-specific source).
- Monash LMGA, *Y-shaped Tree Dataset for Tree Branch Prediction* (2022):
  https://www.monash.edu/engineering/lmga/news/y-shaped-tree-dataset-for-tree-branch-prediction
- Chen et al. (2023), *Obscured tree branches segmentation and 3D
  reconstruction using deep learning and geometrical constraints*,
  Computers and Electronics in Agriculture, 210, 107884,
  DOI:10.1016/j.compag.2023.107884 (related work, not reproduced results).
