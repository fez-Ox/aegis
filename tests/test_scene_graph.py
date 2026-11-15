"""Unit tests for Relative 4D Scene Graph (R4DSG) Memory."""

import json

import numpy as np

from aegis.core.models import BoundingBox3D
from aegis.geometry.gravity import GravityFrame
from aegis.memory.scene_graph import (
    build_relative_4d_scene_graph,
    extract_spatial_anchors,
)

# Level Y-down session: up = -Y, floor at y = 1.4, camera height 1.4.
FLOOR = GravityFrame(
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


def _gbox(
    frame_id: int,
    track_id: int,
    label: str,
    x: float,
    z: float,
    up_min: float,
    up_max: float,
    length: float = 0.3,
    width: float = 0.2,
    *,
    rotation: np.ndarray | None = None,
    support: float | None = None,
    confidence: float = 0.9,
    **kwargs,
) -> BoundingBox3D:
    """Gravity-aligned box given floor-plane position and elevations."""

    centre = np.array([x, -(up_min + up_max) / 2.0, z])
    if rotation is not None:
        centre = rotation @ centre
    return BoundingBox3D(
        frame_id=frame_id,
        timestamp=frame_id * 0.1,
        track_id=track_id,
        label=label,
        confidence=confidence,
        center=tuple(float(v) for v in centre),
        size=(length, width, up_max - up_min),
        bbox_2d=(10.0, 10.0, 50.0, 50.0),
        yaw=0.0,
        up_min=up_min,
        up_max=up_max,
        support_up=support,
        **kwargs,
    )


def _entry(graph, frame_id: int, word: str):
    return next(e for e in graph.memory_timeline[frame_id] if word in e.label.lower())


def _identity_pose(frame_id: int, x: float, y: float, z: float) -> dict:
    return {
        "frame_id": frame_id,
        "timestamp": frame_id * 0.4,
        "matrix": [
            [1.0, 0.0, 0.0, x],
            [0.0, 1.0, 0.0, y],
            [0.0, 0.0, 1.0, z],
            [0.0, 0.0, 0.0, 1.0],
        ],
    }


def test_extract_spatial_anchors() -> None:
    cab1 = BoundingBox3D(
        frame_id=1,
        timestamp=0.2,
        track_id=1,
        label="cabinet",
        confidence=0.9,
        center=(0.0, 0.0, 1.0),
        size=(1.0, 1.0, 1.0),
        bbox_2d=(10.0, 10.0, 100.0, 100.0),
    )
    cab2 = BoundingBox3D(
        frame_id=2,
        timestamp=0.4,
        track_id=1,
        label="cabinet",
        confidence=0.95,
        center=(0.02, 0.01, 1.01),
        size=(1.0, 1.0, 1.0),
        bbox_2d=(10.0, 10.0, 100.0, 100.0),
    )

    anchors = extract_spatial_anchors([cab1, cab2])
    assert len(anchors) == 1
    assert anchors[0].anchor_id == 1
    assert "Cabinet" in anchors[0].label
    assert anchors[0].observations_count == 2


def test_multi_instance_object_persistence() -> None:
    cab = BoundingBox3D(
        frame_id=1,
        timestamp=0.2,
        track_id=1,
        label="cabinet",
        confidence=0.9,
        center=(0.0, 0.0, 1.0),
        size=(1.0, 1.0, 1.0),
        bbox_2d=(10.0, 10.0, 100.0, 100.0),
    )
    boxes = [cab]
    for frame_id in (1, 2):
        boxes.append(
            BoundingBox3D(
                frame_id=frame_id,
                timestamp=0.2 * frame_id,
                track_id=2,
                label="shoes",
                confidence=0.85,
                center=(0.05, 0.05, 1.0),
                size=(0.2, 0.2, 0.2),
                bbox_2d=(30.0, 30.0, 50.0, 50.0),
            )
        )
        boxes.append(
            BoundingBox3D(
                frame_id=frame_id,
                timestamp=0.2 * frame_id,
                track_id=3,
                label="shoes",
                confidence=0.90,
                center=(-0.12, 0.0, 0.2),
                size=(0.05, 0.05, 0.05),
                bbox_2d=(60.0, 30.0, 80.0, 50.0),
            )
        )

    graph = build_relative_4d_scene_graph(boxes, [1, 2, 3], [0.2, 0.4, 0.6])
    assert len(graph.anchors) == 1
    assert {e.instance_id for e in graph.memory_timeline[1]} == {1, 2}
    assert all(e.is_active_view for e in graph.memory_timeline[2])
    # Both pairs persist in memory after leaving view.
    f3 = graph.memory_timeline[3]
    assert len(f3) == 2
    assert all(e.is_active_view is False for e in f3)
    assert len(graph.latest_states) == 2


def test_long_term_reidentification_reuses_instance_id() -> None:
    """A detector track restart must not create a new semantic object ID."""
    signature = (0.8, 0.1, 0.1)
    first = BoundingBox3D(
        frame_id=1,
        timestamp=0.2,
        track_id=4,
        label="garbage bag",
        confidence=0.9,
        center=(0.0, 0.0, 0.4),
        size=(0.2, 0.2, 0.3),
        bbox_2d=(10.0, 10.0, 40.0, 50.0),
        appearance=signature,
    )
    reappeared = BoundingBox3D(
        frame_id=10,
        timestamp=2.0,
        track_id=99,
        label="garbage bag",
        confidence=0.9,
        center=(0.8, 0.2, 0.4),
        size=(0.2, 0.2, 0.3),
        bbox_2d=(100.0, 10.0, 130.0, 50.0),
        appearance=signature,
    )

    graph = build_relative_4d_scene_graph([first, reappeared], [1, 10], [0.2, 2.0])
    active_entries = [
        entry
        for entries in graph.memory_timeline.values()
        for entry in entries
        if entry.is_active_view
    ]
    assert [entry.instance_id for entry in active_entries] == [1, 1]
    assert graph.events == []


def test_kitchen_objects_r4dsg() -> None:
    counter = BoundingBox3D(
        frame_id=1,
        timestamp=0.2,
        track_id=1,
        label="kitchen counter",
        confidence=0.9,
        center=(0.0, 0.0, 1.0),
        size=(1.5, 0.8, 0.9),
        bbox_2d=(10.0, 10.0, 100.0, 100.0),
    )
    pot1 = BoundingBox3D(
        frame_id=1,
        timestamp=0.2,
        track_id=2,
        label="cooking pot",
        confidence=0.88,
        center=(0.1, 0.2, 1.0),
        size=(0.25, 0.25, 0.2),
        bbox_2d=(30.0, 30.0, 60.0, 60.0),
    )
    pot2 = BoundingBox3D(
        frame_id=2,
        timestamp=0.4,
        track_id=2,
        label="cooking pot",
        confidence=0.89,
        center=(0.11, 0.21, 1.0),
        size=(0.25, 0.25, 0.2),
        bbox_2d=(32.0, 30.0, 62.0, 60.0),
    )
    graph = build_relative_4d_scene_graph(
        [counter, pot1, pot2], [1, 2, 3], [0.2, 0.4, 0.6]
    )
    assert len(graph.anchors) >= 1
    assert "Kitchen Counter" in graph.anchors[0].label

    # Frame 1: Pot is active
    f1 = graph.memory_timeline[1]
    assert len(f1) == 1
    assert f1[0].is_active_view is True

    # Frame 2: Pot is active
    f2 = graph.memory_timeline[2]
    assert len(f2) == 1
    assert f2[0].is_active_view is True

    # Frame 3: Pot is not in view, but persists because count >= 2!
    f3 = graph.memory_timeline[3]
    assert len(f3) == 1
    assert f3[0].is_active_view is False


def test_in_hand_kinematic_attachment_during_occlusion() -> None:
    cab = BoundingBox3D(
        frame_id=1,
        timestamp=0.1,
        track_id=10,
        label="storage cabinet",
        confidence=0.9,
        center=(0.0, 3.0, 1.0),
        size=(1.0, 0.6, 1.5),
        bbox_2d=(10.0, 10.0, 100.0, 100.0),
    )
    held = [
        BoundingBox3D(
            frame_id=frame_id,
            timestamp=timestamp,
            track_id=1,
            label="shoes",
            confidence=0.9,
            center=(0.0, 0.5, 0.2),
            size=(0.2, 0.2, 0.2),
            bbox_2d=(50.0, 50.0, 120.0, 120.0),
            spatial_state="in_hand",
            is_in_hand=True,
        )
        for frame_id, timestamp in ((300, 20.0), (310, 20.7))
    ]

    def pose(ty: float) -> list[list[float]]:
        return [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, ty],
            [0.0, 0.0, 1.0, 1.0],
            [0.0, 0.0, 0.0, 1.0],
        ]

    poses = {300: pose(0.0), 310: pose(0.0), 350: pose(1.0), 400: pose(2.0)}
    graph = build_relative_4d_scene_graph(
        [cab, *held],
        [300, 310, 350, 400],
        [20.0, 20.7, 23.3, 26.6],
        camera_poses=poses,
    )

    shoes_300 = _entry(graph, 300, "shoe")
    assert shoes_300.is_in_hand is True
    assert shoes_300.relation == "carried_by_user"
    assert shoes_300.carrier == "camera_wearer"

    # Occluded while carried: the object moves with the camera.
    shoes_350 = _entry(graph, 350, "shoe")
    assert shoes_350.is_active_view is False
    assert shoes_350.relation == "carried_by_user"
    assert abs(shoes_350.center[1] - (shoes_300.center[1] + 1.0)) < 0.01
    shoes_400 = _entry(graph, 400, "shoe")
    assert abs(shoes_400.center[1] - (shoes_300.center[1] + 2.0)) < 0.01


def _pickup_and_place_boxes(include_placement: bool = True) -> list[BoundingBox3D]:
    boxes = [
        _gbox(1, 10, "storage cabinet", 3.0, 0.25, -1.4, 0.4, 1.0, 0.5),
        _gbox(2, 10, "storage cabinet", 3.0, 0.25, -1.4, 0.4, 1.0, 0.5),
        _gbox(100, 1, "shoes", 0.0, 1.0, -1.4, -1.3),
        _gbox(110, 1, "shoes", 0.0, 1.0, -1.4, -1.3),
        _gbox(300, 1, "shoes", 0.5, 1.0, -0.5, -0.4, is_in_hand=True),
        _gbox(310, 1, "shoes", 0.5, 1.0, -0.5, -0.4, is_in_hand=True),
    ]
    if include_placement:
        boxes += [
            _gbox(480, 1, "shoes", 3.0, 0.25, -0.6, -0.5),
            _gbox(490, 1, "shoes", 3.0, 0.25, -0.6, -0.5),
        ]
    return boxes


def test_hybrid_release_gate_and_events() -> None:
    frames = [1, 2, 100, 110, 300, 310, 480, 490]
    graph = build_relative_4d_scene_graph(
        _pickup_and_place_boxes(),
        frames,
        [f * 0.1 for f in frames],
        gravity=FLOOR,
    )

    s100 = _entry(graph, 100, "shoe")
    assert s100.relation == "on_floor"
    assert s100.is_in_hand is False
    s300 = _entry(graph, 300, "shoe")
    assert s300.relation == "carried_by_user"
    assert s300.is_in_hand is True
    s480 = _entry(graph, 480, "shoe")
    assert s480.relation == "inside"
    assert s480.anchor_label == "Storage Cabinet #1"
    assert s480.is_in_hand is False

    event_types = [e["event_type"] for e in graph.events]
    assert event_types == ["pickup", "placement"]


def test_object_not_seen_after_pickup_stays_carried() -> None:
    frames = [1, 2, 100, 110, 300, 310, 400, 500]
    graph = build_relative_4d_scene_graph(
        _pickup_and_place_boxes(include_placement=False),
        frames,
        [f * 0.1 for f in frames],
        gravity=FLOOR,
    )
    assert _entry(graph, 500, "shoe").relation == "carried_by_user"
    assert graph.latest_states[0]["relation"] == "carried_by_user"
    assert graph.latest_states[0]["anchor_id"] is None


def test_bottle_occlusion_and_relocation_r4dsg() -> None:
    """Occlusion of a bottle on a desk, then relocation to another desk."""
    desk1 = BoundingBox3D(
        frame_id=10,
        timestamp=1.0,
        track_id=1,
        label="desk",
        confidence=0.9,
        center=(-0.2, 0.2, 0.3),
        size=(0.3, 0.1, 0.1),
        bbox_2d=(10.0, 10.0, 100.0, 100.0),
    )
    desk2 = BoundingBox3D(
        frame_id=30,
        timestamp=3.0,
        track_id=2,
        label="desk",
        confidence=0.9,
        center=(-0.8, -0.1, 0.8),
        size=(0.3, 0.1, 0.1),
        bbox_2d=(10.0, 10.0, 100.0, 100.0),
    )

    def bottle(frame_id: int, track_id: int, label: str, center) -> BoundingBox3D:
        return BoundingBox3D(
            frame_id=frame_id,
            timestamp=frame_id * 0.1,
            track_id=track_id,
            label=label,
            confidence=0.9,
            center=center,
            size=(0.05, 0.05, 0.1),
            bbox_2d=(20.0, 20.0, 40.0, 60.0),
        )

    # Bottles stand on each desk's top (y is down, so "on top" is smaller y).
    boxes = [
        desk1,
        desk2,
        bottle(10, 3, "bottle", (-0.2, 0.1, 0.3)),
        bottle(12, 3, "bottle", (-0.2, 0.1, 0.3)),
        bottle(30, 4, "water bottle", (-0.8, -0.2, 0.8)),
        bottle(32, 4, "water bottle", (-0.8, -0.2, 0.8)),
    ]
    all_frames = [10, 12, 20, 30, 32]
    graph = build_relative_4d_scene_graph(boxes, all_frames, [1.0, 1.2, 2.0, 3.0, 3.2])

    assert len(graph.anchors) == 2
    assert {a.label for a in graph.anchors} == {"Desk #1", "Desk #2"}

    b10 = _entry(graph, 10, "bottle")
    assert b10.is_active_view is True
    assert b10.anchor_label == "Desk #1"
    assert b10.relation == "on_surface"

    b20 = _entry(graph, 20, "bottle")
    assert b20.is_active_view is False
    assert b20.anchor_label == "Desk #1"
    assert b20.relation == "on_surface"
    assert b20.instance_id == 1

    b30 = _entry(graph, 30, "bottle")
    assert b30.is_active_view is True
    assert b30.anchor_label == "Desk #2"
    assert b30.relation == "on_surface"
    assert b30.instance_id == 1

    ev = next(e for e in graph.events if "bottle" in e["object"].lower())
    assert ev["event_type"] == "anchor_change"
    assert ev["source_anchor"] == "Desk #1"
    assert ev["destination_anchor"] == "Desk #2"


def test_room_grounding_flows_to_anchors_and_entries() -> None:
    """Room binding: anchors inherit their room and objects follow their anchor."""
    desk1 = BoundingBox3D(
        frame_id=10,
        timestamp=1.0,
        track_id=1,
        label="desk",
        confidence=0.9,
        center=(0.1, 0.2, 0.3),
        size=(0.3, 0.1, 0.1),
        bbox_2d=(10.0, 10.0, 100.0, 100.0),
    )
    desk2 = BoundingBox3D(
        frame_id=30,
        timestamp=3.0,
        track_id=2,
        label="desk",
        confidence=0.9,
        center=(6.0, 0.0, 0.5),
        size=(0.3, 0.1, 0.1),
        bbox_2d=(10.0, 10.0, 100.0, 100.0),
    )

    def bottle(frame_id: int, center) -> BoundingBox3D:
        return BoundingBox3D(
            frame_id=frame_id,
            timestamp=frame_id * 0.1,
            track_id=3,
            label="bottle",
            confidence=0.9,
            center=center,
            size=(0.05, 0.05, 0.1),
            bbox_2d=(20.0, 20.0, 40.0, 60.0),
        )

    poses = [
        _identity_pose(0, 0.0, 1.5, 0.0),
        _identity_pose(1, 0.1, 1.5, 0.1),
        _identity_pose(2, 0.2, 1.5, 0.0),
        _identity_pose(3, 6.0, 1.5, 0.2),
        _identity_pose(4, 6.1, 1.5, 0.1),
        _identity_pose(5, 6.2, 1.5, 0.3),
    ]
    all_frames = [0, 1, 2, 3, 4, 5, 10, 12, 20, 30, 31]
    all_ts = [0.0, 0.4, 0.8, 1.2, 1.6, 2.0, 4.0, 4.8, 8.0, 12.0, 12.4]
    graph = build_relative_4d_scene_graph(
        [
            desk1,
            desk2,
            bottle(10, (0.12, 0.18, 0.28)),
            bottle(30, (5.95, 0.05, 0.55)),
            bottle(31, (5.95, 0.05, 0.55)),
        ],
        all_frames,
        all_ts,
        camera_poses=poses,
    )

    assert len(graph.rooms) == 2
    assert {room.label for room in graph.rooms} == {"Room #1", "Room #2"}
    desk1_anchor = next(a for a in graph.anchors if a.label == "Desk #1")
    desk2_anchor = next(a for a in graph.anchors if a.label == "Desk #2")
    assert desk1_anchor.room_label == "Room #1"
    assert desk2_anchor.room_label == "Room #2"

    assert _entry(graph, 10, "bottle").room_label == "Room #1"
    assert _entry(graph, 30, "bottle").room_label == "Room #2"

    data = graph.as_dict()
    assert len(data["rooms"]) == 2
    assert all("room_label" in anchor for anchor in data["anchors"])
    assert len(data["room_visits"]) == 2


def test_carried_object_inherits_wearer_room_and_room_change_event() -> None:
    cabinet = BoundingBox3D(
        frame_id=1,
        timestamp=0.1,
        track_id=10,
        label="storage cabinet",
        confidence=0.9,
        center=(0.0, 3.0, 1.0),
        size=(1.0, 0.6, 1.5),
        bbox_2d=(10.0, 10.0, 100.0, 100.0),
    )
    held = [
        BoundingBox3D(
            frame_id=frame_id,
            timestamp=timestamp,
            track_id=1,
            label="shoes",
            confidence=0.9,
            center=(0.0, 0.5, 0.2),
            size=(0.2, 0.2, 0.2),
            bbox_2d=(50.0, 50.0, 120.0, 120.0),
            spatial_state="in_hand",
            is_in_hand=True,
        )
        for frame_id, timestamp in ((300, 20.0), (310, 20.7))
    ]
    poses = {
        300: _identity_pose(300, 0.0, 1.5, 0.0)["matrix"],
        310: _identity_pose(310, 0.0, 1.5, 0.0)["matrix"],
        350: _identity_pose(350, 0.0, 1.5, 8.0)["matrix"],  # Walked 8 m away
        400: _identity_pose(400, 0.0, 1.5, 8.1)["matrix"],
    }

    graph = build_relative_4d_scene_graph(
        [cabinet, *held],
        [300, 310, 350, 400],
        [20.0, 20.7, 23.3, 26.6],
        camera_poses=poses,
        min_zone_keyframes=1,
    )

    shoes_300 = _entry(graph, 300, "shoe")
    assert shoes_300.relation == "carried_by_user"
    assert shoes_300.room_label == "Room #1"
    shoes_350 = _entry(graph, 350, "shoe")
    assert shoes_350.relation == "carried_by_user"
    assert shoes_350.room_label == "Room #2"

    room_changes = [ev for ev in graph.events if ev["event_type"] == "room_change"]
    assert len(room_changes) == 1
    assert room_changes[0]["source_room"] == "Room #1"
    assert room_changes[0]["destination_room"] == "Room #2"
    assert room_changes[0]["source_room_id"] == 1
    assert room_changes[0]["destination_room_id"] == 2
    assert room_changes[0]["object"] == "Camera Wearer"


def test_room_landmarks_are_excluded_from_object_memory() -> None:
    """Furniture and doors are context, never misplaced objects."""
    sofa = BoundingBox3D(
        frame_id=1,
        timestamp=0.2,
        track_id=1,
        label="sofa",
        confidence=0.9,
        center=(0.0, 0.0, 0.5),
        size=(1.5, 0.8, 0.6),
        bbox_2d=(10.0, 10.0, 100.0, 100.0),
    )
    door = BoundingBox3D(
        frame_id=1,
        timestamp=0.2,
        track_id=5,
        label="door",
        confidence=0.9,
        center=(2.0, 0.0, 0.5),
        size=(0.9, 0.1, 2.0),
        bbox_2d=(10.0, 10.0, 100.0, 100.0),
    )
    keys = [
        BoundingBox3D(
            frame_id=frame_id,
            timestamp=0.2 * frame_id,
            track_id=2,
            label="keys",
            confidence=0.9,
            center=(0.2, 0.0, 0.7),
            size=(0.05, 0.05, 0.05),
            bbox_2d=(30.0, 30.0, 50.0, 50.0),
        )
        for frame_id in (1, 2)
    ]

    graph = build_relative_4d_scene_graph([sofa, door, *keys], [1, 2], [0.2, 0.4])
    labels = {
        entry.label for entries in graph.memory_timeline.values() for entry in entries
    }
    assert labels == {"Keys #1"}
    assert [a.label for a in graph.anchors] == ["Sofa #1"]
    assert all(room.label in {"Room #1", "Living Room"} for room in graph.rooms)


def test_no_anchor_is_fabricated() -> None:
    keys = [
        BoundingBox3D(
            frame_id=frame_id,
            timestamp=0.1 * frame_id,
            track_id=1,
            label="keys",
            confidence=0.9,
            center=(0.0, 0.0, 1.0),
            size=(0.05, 0.05, 0.05),
            bbox_2d=(0.0, 0.0, 5.0, 5.0),
        )
        for frame_id in (1, 2)
    ]
    graph = build_relative_4d_scene_graph(keys, [1, 2], [0.1, 0.2])
    assert graph.anchors == []
    state = graph.latest_states[0]
    assert state["anchor_id"] is None
    assert state["anchor_label"] is None
    assert state["relation"] == "in_room"
    assert "Cabinet" not in json.dumps(graph.as_dict())


def test_shoes_on_and_under_bed_in_pitched_session() -> None:
    rotation = _rot_x(40.0)
    up = rotation @ np.array([0.0, -1.0, 0.0])
    pitched = GravityFrame(
        up=tuple(float(v) for v in up),
        floor_offset=-1.4,
        source="floor_plane",
        confidence=1.0,
        camera_height=1.4,
    )
    boxes = []
    for frame_id in (1, 2):
        boxes.append(
            _gbox(
                frame_id,
                1,
                "bed",
                0.0,
                3.0,
                -1.4,
                -0.8,
                2.0,
                2.0,
                rotation=rotation,
                support=-0.9,
            )
        )
        boxes.append(
            _gbox(frame_id, 2, "shoes", -0.5, 3.0, -0.9, -0.8, rotation=rotation)
        )
        boxes.append(
            _gbox(frame_id, 3, "shoes", 0.5, 3.0, -1.4, -1.3, rotation=rotation)
        )
    graph = build_relative_4d_scene_graph(boxes, [1, 2], [0.1, 0.2], gravity=pitched)
    relations = {
        (state["label"], state["relation"], state["anchor_label"])
        for state in graph.latest_states
    }
    assert ("Shoes #1", "on_surface", "Bed #1") in relations or (
        "Shoes #2",
        "on_surface",
        "Bed #1",
    ) in relations
    assert sorted(state["relation"] for state in graph.latest_states) == [
        "on_surface",
        "under",
    ]
    under = next(s for s in graph.latest_states if s["relation"] == "under")
    assert under["height_above_floor"] < 0.05


def _pot_on_counter(keyframes: int) -> BoundingBox3D:
    boxes = [
        _gbox(0, 1, "kitchen counter", 0.0, 0.0, -1.4, -0.5, 1.5, 0.6),
    ]
    for frame_id in range(keyframes):
        boxes.append(_gbox(frame_id, 2, "cooking pot", 0.0, 0.0, -0.5, -0.3))
    return boxes


def test_as_dict_has_no_timeline_and_has_runs() -> None:
    graph = build_relative_4d_scene_graph(
        _pot_on_counter(5), list(range(5)), [0.1 * i for i in range(5)], gravity=FLOOR
    )
    data = graph.as_dict()
    assert data["schema_version"] == 2
    assert "timeline" not in data
    assert len(data["state_runs"]) == 1
    run = data["state_runs"][0]
    assert run["relation"] == "on_surface"
    assert run["anchor_label"] == "Kitchen Counter #1"
    assert run["observation_count"] == 5
    assert data["gravity"]["source"] == "floor_plane"
    assert set(graph.timeline_dict()) == {str(i) for i in range(5)}


def test_graph_size_is_independent_of_keyframe_count() -> None:
    small = build_relative_4d_scene_graph(
        _pot_on_counter(10),
        list(range(10)),
        [float(i) for i in range(10)],
        gravity=FLOOR,
    )
    large = build_relative_4d_scene_graph(
        _pot_on_counter(200),
        list(range(200)),
        [float(i) for i in range(200)],
        gravity=FLOOR,
    )
    small_size = len(json.dumps(small.as_dict()))
    large_size = len(json.dumps(large.as_dict()))
    assert abs(large_size - small_size) / small_size < 0.05


def test_wallclock_is_carried_into_runs_and_events() -> None:
    frames = [1, 2, 100, 110, 300, 310, 480, 490]
    wallclock = {f: f"2026-11-15T10:00:{f % 60:02d}+05:00" for f in frames}
    graph = build_relative_4d_scene_graph(
        _pickup_and_place_boxes(),
        frames,
        [f * 0.1 for f in frames],
        gravity=FLOOR,
        wallclock_by_frame=wallclock,
    )
    first_run = graph.state_runs[0]
    assert first_run["start_wallclock"] == "2026-11-15T05:00:40.000000+00:00"
    assert graph.session["time_source"] == "capture"
    assert graph.session["started_at"] == "2026-11-15T05:00:01.000000+00:00"
    assert all(event["end_wallclock"] for event in graph.events)


def test_confidence_is_stored_on_entries_and_runs() -> None:
    graph = build_relative_4d_scene_graph(
        _pot_on_counter(3), [0, 1, 2], [0.0, 0.1, 0.2], gravity=FLOOR
    )
    assert graph.memory_timeline[2][0].confidence == 0.9
    assert graph.state_runs[0]["confidence"] == 0.9
    assert graph.latest_states[0]["confidence"] == 0.9
    assert graph.latest_states[0]["relation_certain"] is True


def test_event_carries_room_and_anchor_ids() -> None:
    frames = [1, 2, 100, 110, 300, 310, 480, 490]
    graph = build_relative_4d_scene_graph(
        _pickup_and_place_boxes(), frames, [f * 0.1 for f in frames], gravity=FLOOR
    )
    placement = next(e for e in graph.events if e["event_type"] == "placement")
    assert placement["destination_anchor_id"] == 1
    assert placement["destination_room_id"] == 1
    assert placement["source_anchor_id"] is None
