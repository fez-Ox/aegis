"""Unit tests for the independent evaluation metrics."""

from __future__ import annotations

import pytest

from aegis.evaluation.metrics import (
    bbox_iou,
    evaluate_detection,
    evaluate_events,
    evaluate_rooms,
    evaluate_tracking,
    linear_sum_assignment,
    normalise_label,
    wilson_interval,
)
from aegis.evaluation.schema import Detection, Event


def test_normalise_label_strips_memory_suffixes() -> None:
    assert normalise_label("Shoes #1 [Active Pair]") == "shoes"
    assert normalise_label("  Water   Bottle #12 ") == "water bottle"
    assert normalise_label(None) == ""


def test_bbox_iou_basic_cases() -> None:
    assert bbox_iou([0, 0, 10, 10], [0, 0, 10, 10]) == pytest.approx(1.0)
    assert bbox_iou([0, 0, 10, 10], [20, 20, 30, 30]) == pytest.approx(0.0)
    # Half overlap: each box area 100, intersection 50, union 150.
    assert bbox_iou([0, 0, 10, 10], [5, 0, 15, 10]) == pytest.approx(1 / 3)


def test_linear_sum_assignment_square_and_rectangular() -> None:
    import numpy as np

    assignment = linear_sum_assignment(np.array([[1.0, 9.0], [8.0, 1.0]]))
    assert assignment == [0, 1]

    # More rows than columns: one row must remain unassigned.
    assignment = linear_sum_assignment(np.array([[1.0, 9.0], [8.0, 1.0], [5.0, 5.0]]))
    assert assignment[0] == 0
    assert assignment[1] == 1
    assert assignment[2] == -1

    # More columns than rows: one column must remain unassigned.
    assignment = linear_sum_assignment(np.array([[1.0, 9.0, 5.0], [8.0, 1.0, 5.0]]))
    assert sorted(assignment) == [0, 1]


def test_wilson_interval_bounds() -> None:
    low, high = wilson_interval(0, 10)
    assert low == 0.0
    assert 0.0 < high < 0.4
    low, high = wilson_interval(10, 10)
    assert high == 1.0
    assert 0.6 < low < 1.0


def _detection(
    frame: int,
    label: str,
    bbox: tuple[float, float, float, float],
    instance: int | None = None,
    confidence: float = 1.0,
) -> Detection:
    return Detection(
        frame_id=frame,
        label=label,
        bbox=bbox,
        instance_id=instance,
        confidence=confidence,
    )


def test_evaluate_detection_counts_and_ap() -> None:
    gt = [
        _detection(0, "shoes", (0, 0, 10, 10), 1),
        _detection(1, "shoes", (0, 0, 10, 10), 1),
        _detection(1, "bottle", (20, 20, 30, 30), 2),
    ]
    preds = [
        _detection(0, "shoes", (0, 0, 10, 10), 10, 0.9),
        _detection(1, "shoes", (0, 0, 10, 10), 10, 0.8),
        # Missed bottle, plus one false positive.
        _detection(1, "chair", (40, 40, 50, 50), 11, 0.7),
    ]
    result = evaluate_detection(gt, preds)
    assert result["counts"]["true_positives"] == 2
    assert result["counts"]["false_positives"] == 1
    assert result["counts"]["false_negatives"] == 1
    assert result["precision"] == pytest.approx(2 / 3)
    assert result["recall"] == pytest.approx(2 / 3)
    assert result["per_class"]["shoes"]["average_precision"] == pytest.approx(1.0)
    assert result["per_class"]["bottle"]["average_precision"] is None


def test_evaluate_tracking_detects_id_switch() -> None:
    gt = [_detection(frame, "shoes", (0, 0, 10, 10), 1) for frame in range(4)]
    # The predicted identity changes halfway through, so IDF1 must fall below 1.
    preds = [
        _detection(0, "shoes", (0, 0, 10, 10), 10),
        _detection(1, "shoes", (0, 0, 10, 10), 10),
        _detection(2, "shoes", (0, 0, 10, 10), 11),
        _detection(3, "shoes", (0, 0, 10, 10), 11),
    ]
    result = evaluate_tracking(gt, preds)
    assert result["available"] is True
    assert result["idf1"] < 1.0
    assert result["counts"]["id_switches"] >= 1


def test_evaluate_events_with_tolerance_and_type_alias() -> None:
    gt = [
        Event(
            event_type="pickup",
            start_time=10.0,
            end_time=11.0,
            object_label="shoes",
            instance_id=1,
        )
    ]
    preds = [
        Event(
            event_type="pick_up",
            start_time=10.5,
            end_time=11.4,
            object_label="Shoes #1",
            instance_id=1,
        )
    ]
    result = evaluate_events(
        gt,
        preds,
        tolerance_s=1.0,
        event_type_aliases={"pick_up": "pickup"},
    )
    assert result["precision"] == 1.0
    assert result["recall"] == 1.0
    assert result["f1"] == 1.0


def test_evaluate_events_rejects_wrong_type() -> None:
    gt = [
        Event(event_type="pickup", start_time=10.0, end_time=11.0, object_label="shoes")
    ]
    preds = [
        Event(
            event_type="placement", start_time=10.5, end_time=11.0, object_label="shoes"
        )
    ]
    result = evaluate_events(gt, preds, tolerance_s=1.0)
    assert result["f1"] == 0.0
    assert result["counts"]["false_negatives"] == 1
    assert result["counts"]["false_positives"] == 1


def _pose(frame_id: int, x: float, timestamp: float) -> dict:
    return {
        "frame_id": frame_id,
        "timestamp": timestamp,
        "matrix": [
            [1.0, 0.0, 0.0, x],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
    }


def test_evaluate_rooms_accuracy_and_change() -> None:
    footprint_one = [[-1, 0, -1], [1, 0, -1], [1, 0, 1], [-1, 0, 1]]
    footprint_two = [[1, 0, -1], [3, 0, -1], [3, 0, 1], [1, 0, 1]]
    graph = {
        "rooms": [
            {
                "room_id": 1,
                "label": "Room #1",
                "room_type": "Room",
                "centroid": [0, 0, 0],
                "footprint": footprint_one,
            },
            {
                "room_id": 2,
                "label": "Room #2",
                "room_type": "Room",
                "centroid": [2, 0, 0],
                "footprint": footprint_two,
            },
        ],
        "events": [
            {
                "event_id": "rc1",
                "event_type": "room_change",
                "start_time": 2.0,
                "end_time": 2.0,
                "source_room": "Room #1",
                "destination_room": "Room #2",
            }
        ],
        "timeline": {},
        "anchors": [],
    }
    annotations = {
        "rooms": [
            {
                "room_id": 1,
                "label": "Room #1",
                "centroid": [0, 0, 0],
                "footprint": footprint_one,
            },
            {
                "room_id": 2,
                "label": "Room #2",
                "centroid": [2, 0, 0],
                "footprint": footprint_two,
            },
        ],
        "frame_rooms": [
            {"frame_id": 0, "room_id": 1},
            {"frame_id": 10, "room_id": 2},
        ],
        "room_changes": [{"timestamp": 2.0, "from_room_id": 1, "to_room_id": 2}],
    }
    poses = [_pose(0, 0.0, 0.0), _pose(10, 2.0, 2.0)]
    result = evaluate_rooms(graph, annotations, poses)
    assert result["accuracy"] == pytest.approx(1.0)
    assert result["regions"]["available"] is True
    assert result["regions"]["region_recall"] == pytest.approx(1.0)
    assert result["room_change"]["f1"] == pytest.approx(1.0)
