"""Tests for persistent-ID Rerun overlay association."""

from aegis.visualization.rerun_scene import (
    _associate_boxes_with_memory,
    _v2_timeline,
)


def test_v2_state_runs_build_a_keyframe_timeline() -> None:
    graph = {
        "latest_states": [
            {"instance_id": 7, "label": "Mug #1", "size": [0.1, 0.1, 0.1]},
        ],
        "state_runs": [
            {
                "instance_id": 7,
                "instance_label": "Mug #1",
                "center": [0.2, 0.3, 0.4],
                "start_frame": 6,
                "end_frame": 18,
                "anchor_label": "Table #1",
                "room_label": "Kitchen",
                "relation": "on_surface",
            }
        ],
    }
    timeline = _v2_timeline(graph, {0, 6, 12, 18, 24})
    assert sorted(timeline) == ["12", "18", "6"]
    assert timeline["12"][0]["instance_id"] == 7
    assert timeline["12"][0]["size"] == [0.1, 0.1, 0.1]
    assert timeline["18"][0]["is_active_view"] is True
    assert "24" not in timeline


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
