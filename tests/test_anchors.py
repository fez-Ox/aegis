"""Tests for anchor extraction."""

from __future__ import annotations

from aegis.core.models import BoundingBox3D
from aegis.memory.anchors import extract_spatial_anchors


def _box(frame_id, label, center, size=(1.0, 0.5, 0.8)):
    return BoundingBox3D(
        frame_id=frame_id,
        timestamp=0.1 * frame_id,
        track_id=1,
        label=label,
        confidence=0.9,
        center=center,
        size=size,
        bbox_2d=(0.0, 0.0, 1.0, 1.0),
        yaw=0.0,
    )


def test_no_anchor_boxes_gives_no_anchors() -> None:
    assert extract_spatial_anchors([_box(1, "keys", (0, 0, 0))]) == []


def test_two_cabinet_observations_make_one_anchor_with_footprint() -> None:
    anchors = extract_spatial_anchors(
        [_box(1, "cabinet", (0.0, 0.0, 1.0)), _box(2, "cupboard", (0.05, 0.0, 1.0))]
    )
    assert len(anchors) == 1
    anchor = anchors[0]
    assert anchor.label == "Storage Cabinet #1"
    assert anchor.canonical == "storage cabinet"
    assert anchor.observations_count == 2
    assert len(anchor.footprint) >= 4
    assert anchor.up_min is not None and anchor.up_max is not None


def test_bed_is_an_anchor() -> None:
    anchors = extract_spatial_anchors(
        [_box(1, "bed", (0, 0, 2), (2, 2, 0.6)), _box(2, "bed", (0, 0, 2), (2, 2, 0.6))]
    )
    assert [a.label for a in anchors] == ["Bed #1"]


def test_outlier_sized_member_is_dropped() -> None:
    boxes = [
        _box(1, "desk", (0.0, 0.0, 1.0)),
        _box(2, "desk", (0.0, 0.0, 1.0)),
        _box(3, "desk", (0.1, 0.0, 1.0), size=(4.0, 3.0, 2.0)),
    ]
    anchor = extract_spatial_anchors(boxes)[0]
    assert anchor.size == (1.0, 0.5, 0.8)
    assert anchor.observations_count == 3
