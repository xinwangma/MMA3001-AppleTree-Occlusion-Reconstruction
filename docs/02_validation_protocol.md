# Step 1 — Planned Validation Protocol (not yet executed on real data)

## Experimental scenarios

- **A. Annotation-assisted completion:** supply *visible branch ground truth*
  to the geometry method. This isolates the branch-completion problem and is
  **not** evidence of a fully automatic RGB-D system.
- **B. End-to-end completion:** supply predicted visible masks from an image
  segmentation stage. Report these results separately from scenario A.

The *whole branch ground-truth annotation* is never accessible to the inference
function. It is used only for training (if chosen) or held-out evaluation.

## Baseline and candidate

A: visible-only mask/skeleton, unchanged in hidden regions.
B: geometric Y-branch completion with tunable connection thresholds and
curve-fitting regularisation.

## Quantitative definitions (binary pixel masks)

- TP: pixels predicted as branch that belong to whole-branch GT.
- FP: predicted branch pixels absent from whole-branch GT.
- FN: whole-branch GT pixels missed by prediction.
- Precision = TP/(TP+FP).
- Recall = TP/(TP+FN).
- F1 = 2TP/(2TP+FP+FN).
- IoU = TP/(TP+FP+FN).
- Hidden GT region = Whole GT AND NOT Visible GT.
- Hidden-branch recall = predicted foreground pixels in hidden GT region /
  total pixels in hidden GT region.

For absent denominators, `metrics.py` states the edge-case convention.
Use the same mask resolution and preprocessing for baseline and proposed model.
Include geometric continuity and spuriously added branches in qualitative
review (high hidden recall alone can be misleading).

## Train/validation/test design

Before splitting, determine whether repeated frames depict the same tree,
repeated camera viewpoints, or adjacent dates. Group by tree identity when
possible; otherwise explicitly disclose uncertain independence. Choose all
hyperparameters with training/validation data; report untouched test results
once. Report per-season results rather than simply pooling seasons (sample
counts differ). Record random seed, sample IDs and preprocessing settings.

## 3D validity and calibration checks

For a pixel (u,v) with calibrated optical-axis depth Z, the camera-frame
coordinate is X=(u-cx)Z/fx, Y=(v-cy)Z/fy, Z=depth*scale. This formula is valid
only after depth meaning (axial depth vs range), pixel registration, camera
intrinsics, and conversion to metres have been verified. Depth at occluded
segments is not measured. Inferring 3D points on hidden branches requires
extra assumptions and explicit uncertainty notation.

## Planned sensitivity analysis

Increase mask occlusion, vary centreline fit degree, endpoint connection
threshold, and depth noise where physically defensible. Record F1, hidden
recall, topological errors and runtime. Synthetic occlusion is a secondary
stress test and not a substitute for real-season evaluation.

## Failure cases

Branches hidden for their full lengths; invalid or out-of-range depth;
non-Y topology; erroneous foreground masks; inconsistent registered image
sizes; label leakage; repeated views crossing dataset partitions.
