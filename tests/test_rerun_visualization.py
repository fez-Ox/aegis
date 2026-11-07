"""Tests for persistent-ID Rerun overlay association."""

from aegis.remote.workers import _associate_boxes_with_memory


def test_overlay_uses_nearest_r4dsg_instance_for_aliases() -> None:
    boxes = [
        {
            "label": "rubbish",
            "center": [0.0, 0.0, 0.4],
            "is_hand": False,
        },
        {
            "label": "hand",
            "center": [0.1, 0.0, 0.2],
            "is_hand": True,
        },
    ]
    entries = [
        {
            "label": "Garbage Bag #1",
            "center": [0.0, 0.0, 0.4],
            "instance_id": 1,
            "is_active_view": True,
        }
    ]

    associations = _associate_boxes_with_memory(boxes, entries)

    assert associations[0]["instance_id"] == 1
    assert 1 not in associations


def test_overlay_drops_duplicate_detection_without_r4dsg_instance() -> None:
    boxes = [
        {"label": "garbage bag", "center": [0.0, 0.0, 0.4]},
        {"label": "garbage bag", "center": [1.0, 1.0, 1.0]},
    ]
    entries = [
        {
            "label": "Garbage Bag #1",
            "center": [0.0, 0.0, 0.4],
            "instance_id": 1,
            "is_active_view": True,
        }
    ]

    associations = _associate_boxes_with_memory(boxes, entries)

    assert list(associations) == [0]
