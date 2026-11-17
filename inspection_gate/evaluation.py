"""Plain classification metrics without a composite score or pass threshold."""

from __future__ import annotations

from typing import Sequence

import numpy as np


def classification_metrics(
    y_true: Sequence[int], y_pred: Sequence[int], class_order: Sequence[str]
) -> dict:
    """Return accuracy, per-class precision/recall and a confusion matrix."""
    truth = np.asarray(y_true, dtype=np.int64)
    predicted = np.asarray(y_pred, dtype=np.int64)
    if truth.shape != predicted.shape:
        raise ValueError("y_true and y_pred must have the same shape")
    class_count = len(class_order)
    if truth.size and (truth.min() < 0 or truth.max() >= class_count):
        raise ValueError("y_true contains an index outside class_order")
    if predicted.size and (predicted.min() < 0 or predicted.max() >= class_count):
        raise ValueError("y_pred contains an index outside class_order")

    confusion = np.zeros((class_count, class_count), dtype=np.int64)
    for actual, guess in zip(truth.tolist(), predicted.tolist(), strict=True):
        confusion[actual, guess] += 1

    per_class: dict[str, dict[str, float | int]] = {}
    for index, label in enumerate(class_order):
        true_positive = int(confusion[index, index])
        predicted_positive = int(confusion[:, index].sum())
        actual_positive = int(confusion[index, :].sum())
        per_class[label] = {
            "precision": true_positive / predicted_positive if predicted_positive else 0.0,
            "recall": true_positive / actual_positive if actual_positive else 0.0,
            "support": actual_positive,
        }
    return {
        "sample_count": int(truth.size),
        "accuracy": float(np.mean(truth == predicted)) if truth.size else 0.0,
        "class_order": list(class_order),
        "per_class": per_class,
        "confusion_matrix": confusion.tolist(),
    }
