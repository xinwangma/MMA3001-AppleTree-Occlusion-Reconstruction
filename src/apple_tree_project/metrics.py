"""Explicit binary-mask metrics for the future 2D branch completion study."""
from __future__ import annotations
import numpy as np


def to_mask(image: np.ndarray) -> np.ndarray:
    """Convert a single-channel numeric label image into a boolean mask.

    Args:
        image: H x W integer, float or boolean label array.

    Returns:
        H x W binary array; positive pixels are foreground.

    Raises:
        ValueError: If not a finite, single-channel, two-dimensional image.
    """
    array = np.asarray(image)
    if array.ndim != 2 or not np.issubdtype(array.dtype, np.number) and array.dtype != np.bool_:
        raise ValueError("Expected a numeric 2D label mask")
    if not np.all(np.isfinite(array)):
        raise ValueError("Nonfinite values in mask")
    return array > 0


def binary_scores(prediction: np.ndarray, reference: np.ndarray) -> dict[str, float]:
    """Compute precision, recall, F1 and IoU against a binary ground truth.

    Empty prediction and reference are assigned perfect scores (1.0), while a
    nonempty prediction against empty truth has recall 1.0 and precision 0.0.

    Args:
        prediction: Predicted H x W mask.
        reference: Ground-truth H x W mask.

    Returns:
        Dictionary with precision, recall, f1, iou (unitless values 0..1).

    Raises:
        ValueError: If shapes or mask contents are incompatible.
    """
    p, y = to_mask(prediction), to_mask(reference)
    if p.shape != y.shape:
        raise ValueError("Prediction and reference must have identical dimensions")
    tp = int(np.count_nonzero(p & y))
    fp = int(np.count_nonzero(p & ~y))
    fn = int(np.count_nonzero(~p & y))
    if tp + fp + fn == 0:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "iou": 1.0}
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0
    iou = tp / (tp + fp + fn)
    return {"precision": precision, "recall": recall, "f1": f1, "iou": iou}


def hidden_branch_recall(prediction: np.ndarray, visible: np.ndarray,
                         whole_reference: np.ndarray) -> float:
    """Fraction of truly hidden branch pixels recovered by the prediction.

    Hidden-reference region is ``whole_reference & ~visible``. This metric
    uses the *ground-truth visible mask for evaluation only*; never feed
    ``whole_reference`` to a method during inference.

    Args:
        prediction: H x W predicted complete-branch mask.
        visible: H x W ground-truth visible-branch mask.
        whole_reference: H x W ground-truth complete-branch mask.

    Returns:
        Recall in [0, 1]; 1.0 if reference has no hidden pixels.

    Raises:
        ValueError: If mask shapes differ or visible mask is not a subset
            of the whole-branch ground truth.
    """
    p, v, w = map(to_mask, (prediction, visible, whole_reference))
    if p.shape != v.shape or v.shape != w.shape:
        raise ValueError("All masks must have equal dimensions")
    if np.any(v & ~w):
        raise ValueError("Visible mask is not contained in whole-branch mask")
    hidden = w & ~v
    size = int(np.count_nonzero(hidden))
    return (int(np.count_nonzero(p & hidden)) / size) if size else 1.0
