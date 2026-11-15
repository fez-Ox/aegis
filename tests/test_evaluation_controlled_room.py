"""Tests for the Option D controlled-room alignment and scoring."""

from __future__ import annotations

import numpy as np
import pytest

from aegis.evaluation.controlled_room import (
    evaluate_controlled_room,
    umeyama_similarity,
)
from aegis.evaluation.schema import Measurement


def _measurement(
    object_id: str,
    label: str,
    center: tuple[float, float, float],
    *,
    room: str = "Room #1",
    anchor: str = "Shelf #1",
    relation: str = "inside",
) -> Measurement:
    return Measurement(
        object_id=object_id,
        label=label,
        x=center[0],
        y=center[1],
        z=center[2],
        room=room,
        anchor=anchor,
        relation=relation,
    )


def _prediction(
    instance_id: int,
    label: str,
    center: np.ndarray,
    *,
    room: str = "Room #1",
    anchor: str = "Shelf #1",
    relation: str = "inside",
) -> dict:
    return {
        "instance_id": instance_id,
        "label": label,
        "center": [float(value) for value in center],
        "size": [0.2, 0.1, 0.1],
        "anchor_label": anchor,
        "room_label": room,
        "relation": relation,
        "is_active_view": True,
        "last_seen_timestamp": 1.0,
    }


def test_umeyama_recovers_known_similarity() -> None:
    source = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    angle = np.pi / 3.0
    rotation = np.array(
        [
            [np.cos(angle), 0.0, np.sin(angle)],
            [0.0, 1.0, 0.0],
            [-np.sin(angle), 0.0, np.cos(angle)],
        ]
    )
    target = 2.5 * source @ rotation.T + np.array([1.0, -2.0, 0.5])
    scale, fitted_rotation, translation = umeyama_similarity(source, target)
    assert scale == pytest.approx(2.5)
    assert np.allclose(fitted_rotation, rotation, atol=1e-8)
    assert np.allclose(translation, [1.0, -2.0, 0.5], atol=1e-8)


def test_controlled_room_scores_perfect_alignment() -> None:
    measurements = [
        _measurement("o1", "shoes", (0.40, 0.00, 1.00)),
        _measurement("o2", "water bottle", (1.10, 0.70, 0.30)),
        _measurement("o3", "keys", (0.80, 0.00, 0.60)),
    ]
    angle = np.pi / 2.0
    rotation = np.array(
        [
            [np.cos(angle), 0.0, np.sin(angle)],
            [0.0, 1.0, 0.0],
            [-np.sin(angle), 0.0, np.cos(angle)],
        ]
    )
    translation = np.array([0.30, -0.10, 0.20])
    scale = 2.0
    predictions = []
    labels = {"shoes": "Shoes #1", "water bottle": "Water Bottle #1", "keys": "Keys #1"}
    for index, measurement in enumerate(measurements, start=1):
        ground_truth = np.asarray(measurement.center)
        predicted = rotation.T @ (ground_truth - translation) / scale
        predictions.append(_prediction(index, labels[measurement.label], predicted))
    graph = {
        "dataset_id": "controlled",
        "anchors": [],
        "rooms": [],
        "events": [],
        "timeline": {"0": predictions},
    }

    result = evaluate_controlled_room(measurements, graph)
    assert result["inputs"]["matched"] == 3
    assert result["inputs"]["coverage"] == pytest.approx(1.0)
    # Predictions were shrunk by 1/scale, so the fitted predicted->measured
    # similarity must recover the original scale.
    assert result["alignment"]["scale_factor"] == pytest.approx(scale, rel=1e-6)
    assert result["center_error_m"]["mean"] == pytest.approx(0.0, abs=1e-6)
    assert result["relation_accuracy"] == pytest.approx(1.0)
    assert result["anchor_accuracy"] == pytest.approx(1.0)
    assert result["room_accuracy"] == pytest.approx(1.0)
    assert result["verdicts"]["center_error"] == "PASS"
    assert result["verdicts"]["relation"] == "PASS"


def test_controlled_room_reports_unmatched_and_metric_scale_verdict() -> None:
    measurements = [
        _measurement("o1", "shoes", (0.40, 0.00, 1.00)),
        _measurement("o2", "wallet", (0.20, 0.00, 0.50)),
    ]
    predictions = [
        _prediction(1, "Shoes #1", np.array([0.20, 0.00, 0.50])),
    ]
    graph = {"timeline": {"0": predictions}, "anchors": [], "rooms": [], "events": []}
    result = evaluate_controlled_room(measurements, graph, assume_metric_scale=True)
    assert result["inputs"]["matched"] == 1
    assert result["inputs"]["coverage"] == pytest.approx(0.5)
    assert [item["object_id"] for item in result["unmatched"]] == ["o2"]
    assert result["alignment"]["metric_scale_verdict"] == "INSUFFICIENT"
