import numpy as np
import pytest
from apple_tree_project.metrics import binary_scores, hidden_branch_recall, to_mask


def test_perfect_binary_scores():
    mask = np.array([[0, 1], [0, 1]])
    assert binary_scores(mask, mask) == {"precision": 1, "recall": 1, "f1": 1, "iou": 1}


def test_one_true_positive_one_false_positive_and_one_false_negative():
    prediction = np.array([[1, 1], [0, 0]])
    truth = np.array([[1, 0], [1, 0]])
    scores = binary_scores(prediction, truth)
    assert scores["precision"] == 0.5
    assert scores["recall"] == 0.5
    assert scores["f1"] == 0.5
    assert scores["iou"] == pytest.approx(1 / 3)


def test_empty_scores_defined():
    zero = np.zeros((2, 2), dtype=np.uint8)
    assert binary_scores(zero, zero)["f1"] == 1.0


def test_hidden_recall_for_visible_only_baseline():
    visible = np.array([[1, 0, 0]], dtype=np.uint8)
    whole = np.array([[1, 1, 1]], dtype=np.uint8)
    assert hidden_branch_recall(visible, visible, whole) == 0
    predicted = np.array([[1, 1, 0]], dtype=np.uint8)
    assert hidden_branch_recall(predicted, visible, whole) == 0.5


def test_hidden_gt_cannot_be_smaller_than_visible():
    with pytest.raises(ValueError, match="not contained"):
        hidden_branch_recall(np.array([[1]]), np.array([[1]]), np.array([[0]]))


def test_mask_shape_validation():
    with pytest.raises(ValueError):
        binary_scores(np.zeros((2, 2)), np.zeros((2, 3)))
    with pytest.raises(ValueError):
        to_mask(np.zeros((2, 2, 3)))


def test_nonfinite_mask_rejected():
    with pytest.raises(ValueError):
        to_mask(np.array([[float('nan')]]))
