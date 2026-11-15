"""Tests for the gravity-frame relation classifier (the elevation problem)."""

from __future__ import annotations

import numpy as np
import pytest

from aegis.core.models import BoundingBox3D
from aegis.geometry.gravity import GravityFrame
from aegis.memory.relations import AnchorShape, box_footprint, classify_relation

# Level frame: up = -Y, floor at y = 1.4 (elevation -1.4), camera at y = 0.
LEVEL = GravityFrame(
    up=(0.0, -1.0, 0.0),
    floor_offset=-1.4,
    source="floor_plane",
    confidence=1.0,
    camera_height=1.4,
)


def _rot_x(degrees: float) -> np.ndarray:
    a = np.radians(degrees)
    c, s = np.cos(a), np.sin(a)
    return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])


def _box(
    x: float,
    z: float,
    length: float,
    width: float,
    up_min: float,
    up_max: float,
    *,
    support: float | None = None,
    rotation: np.ndarray | None = None,
    label: str = "shoes",
) -> BoundingBox3D:
    centre = np.array([x, -(up_min + up_max) / 2.0, z])
    if rotation is not None:
        centre = rotation @ centre
    return BoundingBox3D(
        frame_id=1,
        timestamp=0.0,
        track_id=1,
        label=label,
        confidence=0.9,
        center=tuple(float(v) for v in centre),
        size=(length, width, up_max - up_min),
        bbox_2d=(0.0, 0.0, 1.0, 1.0),
        yaw=0.0,
        up_min=up_min,
        up_max=up_max,
        support_up=support,
    )


def _scene(rotation: np.ndarray | None = None):
    bed = _box(
        0.0, 3.0, 2.0, 2.0, -1.4, -0.8, support=-0.9, rotation=rotation, label="bed"
    )
    cabinet = _box(3.5, 0.25, 1.0, 0.5, -1.4, 0.4, rotation=rotation, label="cabinet")
    return bed, cabinet


def _classify(
    obj: BoundingBox3D, gravity: GravityFrame, anchors
) -> tuple[str, int | None, bool]:
    bed, cabinet = anchors
    shapes = [
        AnchorShape(
            1, box_footprint(bed, gravity), support_surface=True, open_underneath=True
        ),
        AnchorShape(
            2, box_footprint(cabinet, gravity), container=True, support_surface=True
        ),
    ]
    result = classify_relation(box_footprint(obj, gravity), shapes, gravity)
    return result.relation, result.anchor_id, result.certain


CASES = {
    "on_bed": ((0.0, 3.0, -0.9, -0.8), ("on_surface", 1, True)),
    "under_bed": ((0.0, 3.0, -1.4, -1.3), ("under", 1, True)),
    "floor_beside_bed": ((1.3, 3.0, -1.4, -1.3), ("on_floor", 1, True)),
    "next_to_bed": ((1.3, 3.0, -0.9, -0.8), ("next_to", 1, True)),
    "above_bed": ((0.0, 3.0, -0.3, -0.2), ("above", 1, True)),
    "inside_cabinet": ((3.5, 0.25, -0.6, -0.5), ("inside", 2, True)),
    "on_top_of_cabinet": ((3.5, 0.25, 0.4, 0.5), ("on_surface", 2, True)),
    "far_away": ((20.0, 20.0, -0.9, -0.8), ("in_room", None, True)),
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_relation_cases(name: str) -> None:
    (x, z, low, high), expected = CASES[name]
    shoes = _box(x, z, 0.3, 0.2, low, high)
    assert _classify(shoes, LEVEL, _scene()) == expected


@pytest.mark.parametrize("name", sorted(CASES))
def test_pitched_frame_gives_same_answers(name: str) -> None:
    rotation = _rot_x(40.0)
    up = rotation @ np.array([0.0, -1.0, 0.0])
    pitched = GravityFrame(
        up=tuple(float(v) for v in up),
        floor_offset=-1.4,
        source="floor_plane",
        confidence=1.0,
        camera_height=1.4,
    )
    (x, z, low, high), expected = CASES[name]
    shoes = _box(x, z, 0.3, 0.2, low, high, rotation=rotation)
    assert _classify(shoes, pitched, _scene(rotation)) == expected


def test_low_gravity_confidence_never_asserts_under_or_floor() -> None:
    weak = GravityFrame(
        up=(0.0, -1.0, 0.0),
        floor_offset=-1.4,
        source="camera_prior",
        confidence=0.2,
        camera_height=1.4,
    )
    under = _box(0.0, 3.0, 0.3, 0.2, -1.4, -1.3)
    assert _classify(under, weak, _scene()) == ("near", 1, False)
    beside = _box(1.3, 3.0, 0.3, 0.2, -1.4, -1.3)
    relation, _anchor, certain = _classify(beside, weak, _scene())
    assert relation == "next_to"
    assert certain is False


def test_no_anchors() -> None:
    floor_shoes = _box(0.0, 0.0, 0.3, 0.2, -1.4, -1.3)
    result = classify_relation(box_footprint(floor_shoes, LEVEL), [], LEVEL)
    assert (result.relation, result.anchor_id) == ("on_floor", None)
    table_height = _box(0.0, 0.0, 0.3, 0.2, -0.7, -0.6)
    result = classify_relation(box_footprint(table_height, LEVEL), [], LEVEL)
    assert (result.relation, result.anchor_id) == ("in_room", None)


def test_legacy_box_without_vertical_extent_uses_centre_and_size() -> None:
    legacy = BoundingBox3D(
        frame_id=1,
        timestamp=0.0,
        track_id=1,
        label="shoes",
        confidence=0.9,
        center=(0.0, 1.0, 0.0),
        size=(0.2, 0.2, 0.2),
        bbox_2d=(0.0, 0.0, 1.0, 1.0),
    )
    footprint = box_footprint(legacy, LEVEL)
    assert footprint.up_min == pytest.approx(-1.1)
    assert footprint.up_max == pytest.approx(-0.9)
