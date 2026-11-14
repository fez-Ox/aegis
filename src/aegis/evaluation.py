"""Small, pure scoring helpers shared by the measurement scripts."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def match_events(
    predicted: Sequence[float], truth: Sequence[float], *, tolerance: float
) -> int:
    """Greedy one-to-one matches of event times within ``tolerance`` seconds."""

    used: set[int] = set()
    matches = 0
    for t in sorted(truth):
        best = None
        for index, p in enumerate(predicted):
            if index in used or abs(p - t) > tolerance:
                continue
            if best is None or abs(p - t) < abs(predicted[best] - t):
                best = index
        if best is not None:
            used.add(best)
            matches += 1
    return matches


def precision_recall(
    predicted: Sequence[float], truth: Sequence[float], *, tolerance: float
) -> dict[str, Any]:
    hits = match_events(predicted, truth, tolerance=tolerance)
    precision = hits / len(predicted) if predicted else (1.0 if not truth else 0.0)
    recall = hits / len(truth) if truth else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "matches": hits,
        "predicted": len(predicted),
        "truth": len(truth),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }
