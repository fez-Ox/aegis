"""Tests for the generic room clustering and typing settings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aegis.core.config import RoomMemoryConfig, RuntimeConfig
from aegis.geometry.gravity import GravityFrame
from aegis.memory.rooms import extract_room_regions

OUTPUTS = Path("outputs")
BOX_FIELDS = {
    "frame_id",
    "timestamp",
    "track_id",
    "label",
    "confidence",
    "center",
    "size",
    "bbox_2d",
    "spatial_state",
    "container_relation",
    "rotation",
    "yaw",
    "is_hand",
    "is_in_hand",
    "carrier",
    "held_by_hand_track_id",
    "appearance",
    "up_min",
    "up_max",
    "support_up",
    "point_count",
}


def test_room_defaults_use_measured_values() -> None:
    rooms = RoomMemoryConfig()
    assert rooms.zone_link_radius == 2.5
    assert rooms.landmark_min_votes == 2
    assert rooms.landmark_min_confidence == 0.8
    assert rooms.landmark_distinct_instances is True
    assert RuntimeConfig.from_mapping({}).memory.rooms == rooms


@pytest.mark.parametrize(
    "override",
    [
        {"zone_link_radius": 0.0},
        {"landmark_min_votes": 0},
        {"landmark_min_confidence": 1.5},
    ],
)
def test_invalid_room_settings_are_rejected(override: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        extract_room_regions([], [], **override)


def test_single_confident_landmark_does_not_type_a_room() -> None:
    from aegis.core.models import BoundingBox3D

    poses = [
        {
            "frame_id": index,
            "timestamp": float(index),
            "matrix": [
                [1, 0, 0, float(index) * 0.1],
                [0, 1, 0, 0.0],
                [0, 0, 1, 0.0],
                [0, 0, 0, 1],
            ],
        }
        for index in range(5)
    ]
    box = BoundingBox3D(
        frame_id=0,
        timestamp=0.0,
        track_id=1,
        label="stove",
        confidence=0.95,
        center=(0.2, 0.0, 0.5),
        size=(0.5, 0.5, 0.5),
        bbox_2d=(0.0, 0.0, 10.0, 10.0),
    )
    strict = extract_room_regions(
        poses,
        [box],
        landmark_min_votes=2,
        landmark_min_confidence=0.8,
        landmark_distinct_instances=True,
    )
    assert strict and all(region.room_type == "Room" for region in strict)

    loose = extract_room_regions(poses, [box], landmark_min_votes=1)
    assert any(region.room_type == "Kitchen" for region in loose)


@pytest.mark.parametrize(
    "dataset_id",
    ["demo01_sam3", "demo03_sam3", "demo04_sam3", "demo05_sam3", "demo_pots_sam3"],
)
def test_shipped_room_settings_produce_bounded_regions(dataset_id: str) -> None:
    pose_path = OUTPUTS / dataset_id / "geometry" / "poses.json"
    box_path = OUTPUTS / dataset_id / "objects" / "detected_objects_3d.json"
    if not pose_path.exists() or not box_path.exists():
        pytest.skip("artifacts not downloaded")
    from aegis.core.models import BoundingBox3D

    poses = json.loads(pose_path.read_text())["poses"]
    detections = json.loads(box_path.read_text())
    boxes = [
        BoundingBox3D(**{key: value for key, value in box.items() if key in BOX_FIELDS})
        for box in detections.get("boxes_3d", [])
    ]
    settings = RoomMemoryConfig()
    regions = extract_room_regions(
        poses,
        boxes,
        zone_link_radius=settings.zone_link_radius,
        min_zone_keyframes=settings.min_zone_keyframes,
        landmark_min_votes=settings.landmark_min_votes,
        landmark_min_confidence=settings.landmark_min_confidence,
        landmark_distinct_instances=settings.landmark_distinct_instances,
        gravity=GravityFrame.from_dict(detections.get("gravity")),
    )
    assert regions
    assert all(region.keyframe_count >= 1 for region in regions)
    assert len({region.room_id for region in regions}) == len(regions)
