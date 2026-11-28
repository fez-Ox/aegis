"""Prompt-aware detection evaluation with honest handling of incomplete GT.

The earlier bench scored every unmatched detection as a false positive even
when the frame's ground truth was selective (not exhaustive) and included
classes the detector was never prompted for. This module separates:

* ``prompt_coverage`` — share of GT objects whose class is in the prompt set;
* ``recall`` — on labelled in-prompt objects (valid even with incomplete GT);
* ``precision`` — only when ``exhaustive=True`` is declared for the frame;
* ``localization`` / ``classification`` / ``background`` error breakdown
  (TIDE-style) for in-prompt predictions.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from aegis.core.vocabulary import Vocabulary, default_vocabulary


def iou(first: Sequence[float], second: Sequence[float]) -> float:
    ix1, iy1 = max(first[0], second[0]), max(first[1], second[1])
    ix2, iy2 = min(first[2], second[2]), min(first[3], second[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(0.0, first[2] - first[0]) * max(0.0, first[3] - first[1])
    area_b = max(0.0, second[2] - second[0]) * max(0.0, second[3] - second[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def transform_boxes(
    boxes: Sequence[Sequence[float]],
    *,
    source_size: tuple[int, int],
    target_size: tuple[int, int],
    letterbox: bool = False,
) -> list[list[float]]:
    """Map boxes between frame spaces using the same rule as ingestion.

    ``video.width/height`` uses ``cv2.resize`` (stretch), not letterboxing.
    """
    sx = target_size[0] / source_size[0]
    sy = target_size[1] / source_size[1]
    pad_x = (target_size[0] - source_size[0] * sx) / 2 if letterbox else 0.0
    pad_y = (target_size[1] - source_size[1] * sy) / 2 if letterbox else 0.0
    return [
        [b[0] * sx + pad_x, b[1] * sy + pad_y, b[2] * sx + pad_x, b[3] * sy + pad_y]
        for b in boxes
    ]


def evaluate_detection(
    benchmark: Mapping[str, Any],
    predictions: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    prompt_classes: Sequence[str] | None = None,
    vocabulary: Vocabulary | None = None,
    iou_threshold: float = 0.3,
) -> dict[str, Any]:
    """Score a prompt-aware, coverage-explicit detection benchmark."""
    vocab = vocabulary or default_vocabulary()
    prompts = (
        {vocab.canonical(name) for name in prompt_classes} if prompt_classes else None
    )
    threshold = float(benchmark.get("iou_threshold", iou_threshold))
    matched = outside = missed = 0
    extra_predictions = 0
    localization = classification = 0
    per_class: dict[str, dict[str, int]] = {}
    coverage_total = coverage_in_prompt = 0
    for image in benchmark.get("images", []):
        image_id = image["id"]
        preds = list(predictions.get(image_id, []))
        used: set[int] = set()
        gt_items = []
        for item in image.get("objects", []):
            label = vocab.canonical(item["label"])
            coverage_total += 1
            if prompts is not None and label not in prompts:
                outside += 1
                continue
            coverage_in_prompt += 1
            gt_items.append((label, item["bbox"]))
        for label, bbox in gt_items:
            bucket = per_class.setdefault(label, {"tp": 0, "fn": 0})
            candidates = [
                (iou(bbox, pred["bbox"]), index)
                for index, pred in enumerate(preds)
                if index not in used and vocab.canonical(pred["label"]) == label
            ]
            best, index = max(candidates, default=(0.0, -1))
            if best >= threshold:
                used.add(index)
                matched += 1
                bucket["tp"] += 1
            else:
                missed += 1
                bucket["fn"] += 1
                # TIDE-style diagnosis of the closest same-class prediction.
                same_class = [(score, idx) for score, idx in candidates if score >= 0.1]
                if same_class:
                    localization += 1
                else:
                    other_class = [
                        iou(bbox, pred["bbox"])
                        for i, pred in enumerate(preds)
                        if i not in used and vocab.canonical(pred["label"]) != label
                    ]
                    classification += (
                        1 if max(other_class, default=0.0) >= threshold else 0
                    )
        extra_predictions += sum(1 for i in range(len(preds)) if i not in used)
    recall = matched / (matched + missed) if matched + missed else 0.0
    exhaustive_frames = sum(
        1 for image in benchmark.get("images", []) if image.get("exhaustive")
    )
    precision = (
        matched / (matched + extra_predictions)
        if exhaustive_frames == len(benchmark.get("images", []))
        and matched + extra_predictions
        else None
    )
    return {
        "prompt_coverage": round(coverage_in_prompt / coverage_total, 4)
        if coverage_total
        else None,
        "gt_total": coverage_total,
        "gt_in_prompt": coverage_in_prompt,
        "gt_outside_prompt": outside,
        "matched": matched,
        "missed": missed,
        "recall": round(recall, 4),
        "precision": round(precision, 4) if precision is not None else None,
        "f1": round(2 * precision * recall / (precision + recall), 4)
        if precision
        else None,
        "unmatched_predictions": extra_predictions,
        "exhaustive_frames": exhaustive_frames,
        "error_breakdown": {
            "localization": localization,
            "classification": classification,
            "background_or_unlabeled": missed - localization - classification,
        },
        "per_class": dict(sorted(per_class.items())),
    }
