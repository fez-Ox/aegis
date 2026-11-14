"""Tests for the event scoring helpers."""

from aegis.evaluation import match_events, precision_recall


def test_match_events_is_one_to_one_within_tolerance() -> None:
    assert match_events([1.0, 1.2, 5.0], [1.1, 4.0], tolerance=0.5) == 1
    assert match_events([1.0, 2.0], [1.0, 2.0], tolerance=0.1) == 2


def test_precision_recall_arithmetic() -> None:
    result = precision_recall([1.0, 3.0, 9.0], [1.0, 3.5, 6.0, 10.0], tolerance=1.0)
    assert result["matches"] == 3
    assert result["precision"] == 1.0
    assert result["recall"] == 0.75
    assert result["f1"] == round(2 * 0.75 / 1.75, 4)
    assert precision_recall([], [], tolerance=1.0)["recall"] == 1.0
