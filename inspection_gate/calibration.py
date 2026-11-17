"""Calibration measurements (ECE, MCE, Brier, NLL) without acceptance thresholds.

ECE depends on bin choice and says nothing about accuracy by itself, so results
are always reported next to accuracy and as raw measurements.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

_NOTE = (
    "ECE, MCE, Brier and NLL are measurements, not acceptance thresholds; "
    "ECE depends on bin choice and must be read next to accuracy."
)


def calibration_metrics(
    y_true: Sequence[int],
    probabilities: np.ndarray,
    class_order: Sequence[str],
    *,
    bins: int = 10,
) -> dict:
    truth = np.asarray(y_true, dtype=np.int64)
    probs = np.asarray(probabilities, dtype=np.float64)
    if probs.ndim != 2 or probs.shape[1] != len(class_order):
        raise ValueError("probabilities must be (samples, classes) matching class_order")
    if truth.ndim != 1 or truth.shape[0] != probs.shape[0]:
        raise ValueError("y_true must align with probability rows")
    if bins <= 0:
        raise ValueError("bins must be positive")

    sample_count = int(truth.shape[0])
    if sample_count == 0:
        return {
            "sample_count": 0,
            "bin_count": bins,
            "accuracy": 0.0,
            "expected_calibration_error": 0.0,
            "maximum_calibration_error": 0.0,
            "brier_score": 0.0,
            "negative_log_likelihood": 0.0,
            "reliability": [],
            "note": _NOTE,
        }

    confidence = probs.max(axis=1)
    predicted = probs.argmax(axis=1)
    correct = (predicted == truth).astype(np.float64)
    edges = np.linspace(0.0, 1.0, bins + 1)
    reliability: list[dict] = []
    ece = 0.0
    mce = 0.0
    for index in range(bins):
        lower, upper = float(edges[index]), float(edges[index + 1])
        if index == bins - 1:
            mask = (confidence >= lower) & (confidence <= upper)
        else:
            mask = (confidence >= lower) & (confidence < upper)
        count = int(mask.sum())
        if count == 0:
            reliability.append({
                "lower": lower, "upper": upper, "count": 0,
                "accuracy": None, "confidence": None, "gap": None,
            })
            continue
        bin_accuracy = float(correct[mask].mean())
        bin_confidence = float(confidence[mask].mean())
        gap = abs(bin_accuracy - bin_confidence)
        ece += (count / sample_count) * gap
        mce = max(mce, gap)
        reliability.append({
            "lower": lower, "upper": upper, "count": count,
            "accuracy": bin_accuracy, "confidence": bin_confidence, "gap": gap,
        })

    one_hot = np.eye(len(class_order))[truth]
    brier = float(np.mean(np.sum((probs - one_hot) ** 2, axis=1)))
    chosen = probs[np.arange(sample_count), truth]
    nll = float(-np.mean(np.log(np.clip(chosen, 1e-12, 1.0))))
    return {
        "sample_count": sample_count,
        "bin_count": bins,
        "accuracy": float(correct.mean()),
        "expected_calibration_error": ece,
        "maximum_calibration_error": mce,
        "brier_score": brier,
        "negative_log_likelihood": nll,
        "reliability": reliability,
        "note": _NOTE,
    }
