"""Tests for prompt-aware detection evaluation."""

from __future__ import annotations

import pytest

from aegis.evaluation.detection_v2 import evaluate_detection, transform_boxes


def test_transform_uses_stretch_not_letterbox() -> None:
    boxes = [[100, 100, 200, 200]]
    got = transform_boxes(boxes, source_size=(704, 704), target_size=(960, 540))
    assert got[0][0] == pytest.approx(100 * 960 / 704)
    assert got[0][1] == pytest.approx(100 * 540 / 704)


def test_prompt_coverage_and_refused_precision() -> None:
    bench = {
        "iou_threshold": 0.3,
        "images": [
            {
                "id": "f1",
                "objects": [
                    {"label": "mug", "bbox": [0, 0, 10, 10]},
                    {"label": "laptop", "bbox": [20, 20, 30, 30]},
                ],
            }
        ],
    }
    predictions = {
        "f1": [
            {"label": "mug", "bbox": [0, 0, 10, 10]},
            {"label": "hand", "bbox": [50, 50, 60, 60]},
        ]
    }
    result = evaluate_detection(bench, predictions, prompt_classes=["mug", "hand"])
    assert result["prompt_coverage"] == 0.5
    assert result["gt_outside_prompt"] == 1
    assert result["recall"] == 1.0
    assert result["precision"] is None  # not exhaustive: cannot score FP
    assert result["unmatched_predictions"] == 1


def test_exhaustive_frame_reports_precision() -> None:
    bench = {
        "iou_threshold": 0.3,
        "images": [
            {
                "id": "f1",
                "exhaustive": True,
                "objects": [{"label": "mug", "bbox": [0, 0, 10, 10]}],
            }
        ],
    }
    predictions = {
        "f1": [
            {"label": "mug", "bbox": [0, 0, 10, 10]},
            {"label": "hand", "bbox": [50, 50, 60, 60]},
        ]
    }
    result = evaluate_detection(bench, predictions, prompt_classes=["mug", "hand"])
    assert result["precision"] == 0.5
    assert result["f1"] == pytest.approx(2 / 3, abs=1e-4)
