"""Unit tests for room-level spatial region estimation."""

from __future__ import annotations

import numpy as np

from aegis.core.models import BoundingBox3D
from aegis.memory.rooms import (
    extract_room_regions,
    implicit_room_from_anchors,
    is_room_landmark_label,
    parse_camera_positions,
    room_for_point,
)


def _pose(frame_id: int, timestamp: float, x: float, y: float, z: float) -> dict:
    return {
        "frame_id": frame_id,
        "timestamp": timestamp,
        "matrix": [
            [1.0, 0.0, 0.0, x],
            [0.0, 1.0, 0.0, y],
            [0.0, 0.0, 1.0, z],
            [0.0, 0.0, 0.0, 1.0],
        ],
    }


def _box(
    frame_id: int,
    track_id: int,
    label: str,
    center: tuple[float, float, float],
) -> BoundingBox3D:
    return BoundingBox3D(
        frame_id=frame_id,
        timestamp=0.2 * frame_id,
        track_id=track_id,
        label=label,
        confidence=0.9,
        center=center,
        size=(0.2, 0.2, 0.2),
        bbox_2d=(10.0, 10.0, 40.0, 40.0),
    )


def test_parse_camera_positions_supports_dict_and_records() -> None:
    poses = {
        1: _pose(1, 0.0, 0.0, 0.0, 0.0)["matrix"],
        2: _pose(2, 0.4, 5.0, 0.0, 0.0)["matrix"],
    }
    ordered = parse_camera_positions(poses)
    assert [item[0] for item in ordered] == [1, 2]
    assert ordered[1][2][0] == 5.0


def test_two_spatial_clusters_form_two_rooms() -> None:
    poses = []
    frame_id = 0
    for _ in range(5):
        poses.append(_pose(frame_id, frame_id * 0.4, 0.0, 1.5, 0.0))
        frame_id += 1
    for _ in range(5):
        poses.append(_pose(frame_id, frame_id * 0.4, 6.0, 1.5, 0.0))
        frame_id += 1

    rooms = extract_room_regions(poses, [])
    assert len(rooms) == 2
    assert [room.room_id for room in rooms] == [1, 2]
    # Temporal order: the room visited first gets id 1.
    assert rooms[0].centroid[0] < 1.0
    assert rooms[1].centroid[0] > 5.0
    assert [room.label for room in rooms] == ["Room #1", "Room #2"]


def test_revisit_merges_into_one_room() -> None:
    positions = (0.0, 0.1, 0.2, 6.0, 6.1, 6.2, 0.0, 0.1, 0.2)
    poses = [
        _pose(index, index * 0.4, x, 1.5, 0.0) for index, x in enumerate(positions)
    ]

    rooms = extract_room_regions(poses, [])
    assert len(rooms) == 2
    room_positions = sorted(room.centroid[0] for room in rooms)
    assert room_positions[0] < 1.0
    assert room_positions[1] > 5.0


def test_landmark_evidence_types_rooms() -> None:
    poses = []
    frame_id = 0
    for _ in range(4):
        poses.append(_pose(frame_id, frame_id * 0.4, 0.0, 1.5, 0.0))
        frame_id += 1
    for _ in range(4):
        poses.append(_pose(frame_id, frame_id * 0.4, 6.0, 1.5, 0.0))
        frame_id += 1

    bed = _box(1, 1, "bed", (0.2, 1.0, 0.1))
    door = _box(2, 2, "door", (5.9, 1.0, 0.2))
    rooms = extract_room_regions(poses, [bed, door])

    labels = {room.room_id: room.label for room in rooms}
    evidence = {room.room_id: room.evidence_labels for room in rooms}
    assert labels[1] == "Bedroom"
    assert labels[2] == "Entryway"
    assert evidence[1] == ["Bed"]
    assert evidence[2] == ["Door"]


def test_room_for_point_footprint_and_distance() -> None:
    # A square walk: 4 corner keyframes spanning ~1.2 m per side.
    poses = [
        _pose(0, 0.0, 0.0, 1.5, 0.0),
        _pose(1, 0.4, 1.2, 1.5, 0.0),
        _pose(2, 0.8, 1.2, 1.5, 1.2),
        _pose(3, 1.2, 0.0, 1.5, 1.2),
    ]
    rooms = extract_room_regions(poses, [])
    assert len(rooms) == 1

    # Inside the room footprint on the floor plane.
    inside = room_for_point((0.6, 1.5, 0.6), rooms)
    assert inside is not None and inside.room_id == 1
    # Far away with a bounded assignment distance -> no misleading binding.
    assert room_for_point((50.0, 1.5, 50.0), rooms, max_distance=2.5) is None
    # ... but unbounded nearest-centroid binding stays a best guess.
    assert room_for_point((50.0, 1.5, 50.0), rooms) is not None


def test_no_poses_returns_no_rooms_and_implicit_fallback() -> None:
    assert extract_room_regions(None, []) == []

    fallback = implicit_room_from_anchors([(0.0, 0.0, 0.8), (2.0, 0.0, 0.8)])
    assert len(fallback) == 1
    assert fallback[0].label == "Room #1"
    assigned = room_for_point((1.0, 0.0, 0.8), fallback)
    assert assigned is not None and assigned.label == "Room #1"


def test_room_landmark_label_gate() -> None:
    assert is_room_landmark_label("bed")
    assert is_room_landmark_label("Television")
    assert is_room_landmark_label("fridge")
    assert not is_room_landmark_label("shoes")
    assert not is_room_landmark_label("storage cabinet")


def test_footprints_are_planar_polygons() -> None:
    poses = [
        _pose(0, 0.0, x, 1.5, z)
        for x, z in ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
    ]
    rooms = extract_room_regions(poses, [])
    assert len(rooms) == 1
    footprint = rooms[0].footprint
    assert len(footprint) >= 3
    assert all(point[1] == footprint[0][1] for point in footprint)
    area = 0.0
    values = [(p[0], p[2]) for p in footprint]
    for (ax, az), (bx, bz) in zip(values, values[1:] + values[:1], strict=True):
        area += ax * bz - bx * az
    assert abs(abs(area) / 2 - 1.0) < 0.1  # ~1 m² room


def test_deterministic_room_ids_and_labels() -> None:
    poses = [
        _pose(i, i * 0.4, x, 1.5, 0.0)
        for i, x in enumerate((0.0, 0.1, 0.2, 6.0, 6.1, 6.2))
    ]
    rooms_a = extract_room_regions(poses, [])
    rooms_b = extract_room_regions(poses, [])
    assert [r.as_dict() for r in rooms_a] == [r.as_dict() for r in rooms_b]
    assert np.all([abs(r.centroid[1] - 1.5) < 0.1 for r in rooms_a])
