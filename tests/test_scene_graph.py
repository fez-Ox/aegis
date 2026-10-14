"""Unit tests for Relative 4D Scene Graph (R4DSG) Memory."""

from aegis.core.models import BoundingBox3D
from aegis.memory.scene_graph import (
    build_relative_4d_scene_graph,
    extract_spatial_anchors,
)


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
    # Shoes #1 on floor
    shoes1 = BoundingBox3D(
        frame_id=1,
        timestamp=0.2,
        track_id=2,
        label="shoes",
        confidence=0.85,
        center=(0.05, 0.05, 1.0),
        size=(0.2, 0.2, 0.2),
        bbox_2d=(30.0, 30.0, 50.0, 50.0),
    )
    # Shoes #2 on left shelf
    shoes2 = BoundingBox3D(
        frame_id=2,
        timestamp=0.4,
        track_id=3,
        label="shoes",
        confidence=0.90,
        center=(-0.12, 0.0, 0.2),
        size=(0.05, 0.05, 0.05),
        bbox_2d=(30.0, 30.0, 50.0, 50.0),
    )

    all_frames = [1, 2, 3]
    all_ts = [0.2, 0.4, 0.6]

    graph = build_relative_4d_scene_graph([cab, shoes1, shoes2], all_frames, all_ts)
    assert len(graph.anchors) == 1

    # In frame 1: Shoes #1 active
    f1 = graph.memory_timeline[1]
    assert len(f1) == 1
    assert f1[0].instance_id == 1
    assert f1[0].is_active_view is True

    # In frame 2: Shoes #2 active, Shoes #1 persistent!
    f2 = graph.memory_timeline[2]
    assert len(f2) == 2
    f2_instances = {e.instance_id: e for e in f2}
    assert f2_instances[2].is_active_view is True
    assert f2_instances[1].is_active_view is False

    # In frame 3: Both Shoes #1 and Shoes #2 PERSIST in 3D memory!
    f3 = graph.memory_timeline[3]
    assert len(f3) == 2
    for e in f3:
        assert e.is_active_view is False


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
    # Cabinet anchor
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
    # Shoe lifted in hand at frame 300
    shoes_in_hand = BoundingBox3D(
        frame_id=300,
        timestamp=20.0,
        track_id=1,
        label="shoes",
        confidence=0.9,
        center=(0.0, 0.5, 0.2),
        size=(0.2, 0.2, 0.2),
        bbox_2d=(50.0, 50.0, 120.0, 120.0),
        spatial_state="in_hand",
        is_in_hand=True,
    )

    poses = {
        300: [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 1.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        350: [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 1.0],  # Camera moved 1m forward
            [0.0, 0.0, 1.0, 1.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        400: [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 2.0],  # Camera moved 2m forward
            [0.0, 0.0, 1.0, 1.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
    }

    all_frames = [300, 350, 400]
    all_ts = [20.0, 23.3, 26.6]

    graph = build_relative_4d_scene_graph(
        [cab, shoes_in_hand], all_frames, all_ts, camera_poses=poses
    )

    # Frame 300: active in hand
    f300 = graph.memory_timeline[300]
    shoes_300 = next(e for e in f300 if "shoe" in e.label.lower())
    assert shoes_300.is_in_hand is True
    assert shoes_300.relation == "carried_by_user"
    assert shoes_300.carrier == "camera_wearer"

    # Frame 350: completely occluded (not detected), but kinematically transported with camera!
    f350 = graph.memory_timeline[350]
    shoes_350 = next(e for e in f350 if "shoe" in e.label.lower())
    assert shoes_350.is_active_view is False  # Natural obstruction / occluded!
    assert shoes_350.is_in_hand is True
    assert shoes_350.relation == "carried_by_user"
    assert abs(shoes_350.center[1] - (shoes_300.center[1] + 1.0)) < 0.01

    # Frame 400: still occluded, moved +2.0m forward with camera
    f400 = graph.memory_timeline[400]
    shoes_400 = next(e for e in f400 if "shoe" in e.label.lower())
    assert shoes_400.is_in_hand is True
    assert abs(shoes_400.center[1] - (shoes_300.center[1] + 2.0)) < 0.01


def test_hybrid_release_gate_and_events() -> None:
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
    # Shoe on floor initially at frame 100
    shoes_floor = BoundingBox3D(
        frame_id=100,
        timestamp=6.6,
        track_id=1,
        label="shoes",
        confidence=0.9,
        center=(0.0, 0.0, 0.1),
        size=(0.2, 0.2, 0.2),
        bbox_2d=(50.0, 50.0, 120.0, 120.0),
        spatial_state="on_surface",
    )
    # Shoe lifted in hand at frame 300
    shoes_lifted = BoundingBox3D(
        frame_id=300,
        timestamp=20.0,
        track_id=1,
        label="shoes",
        confidence=0.9,
        center=(0.0, 0.5, 0.3),
        size=(0.2, 0.2, 0.2),
        bbox_2d=(50.0, 50.0, 120.0, 120.0),
        spatial_state="in_hand",
        is_in_hand=True,
    )

    all_frames = [100, 300, 480]
    all_ts = [6.6, 20.0, 32.0]

    graph = build_relative_4d_scene_graph(
        [cab, shoes_floor, shoes_lifted], all_frames, all_ts
    )

    # Frame 100: on floor
    f100 = graph.memory_timeline[100]
    s100 = next(e for e in f100 if "shoe" in e.label.lower())
    assert s100.relation == "on_floor"
    assert s100.is_in_hand is False

    # Frame 300: carried by user
    f300 = graph.memory_timeline[300]
    s300 = next(e for e in f300 if "shoe" in e.label.lower())
    assert s300.relation == "carried_by_user"
    assert s300.is_in_hand is True

    # Frame 480: placed inside cabinet
    f480 = graph.memory_timeline[480]
    s480 = next(e for e in f480 if "shoe" in e.label.lower())
    assert s480.relation == "inside"
    assert s480.is_in_hand is False

    # Events should record pickup and placement
    event_types = [e["event_type"] for e in graph.events]
    assert "pickup" in event_types
    assert "placement" in event_types


def test_bottle_occlusion_and_relocation_r4dsg() -> None:
    """Test AC: Occlusion of bottle from table is handled by the spatio-temporal memory engine."""
    # Desk 1 (Source)
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
    # Desk 2 (Destination)
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
    # Bottle on Desk 1 in frame 10 (observation 1)
    bottle_frame10 = BoundingBox3D(
        frame_id=10,
        timestamp=1.0,
        track_id=3,
        label="bottle",
        confidence=0.88,
        center=(-0.14, 0.15, 0.26),
        size=(0.05, 0.05, 0.1),
        bbox_2d=(20.0, 20.0, 40.0, 60.0),
        spatial_state="on_surface",
    )
    # Bottle on Desk 1 in frame 12 (observation 2)
    bottle_frame12 = BoundingBox3D(
        frame_id=12,
        timestamp=1.2,
        track_id=3,
        label="bottle",
        confidence=0.90,
        center=(-0.14, 0.15, 0.26),
        size=(0.05, 0.05, 0.1),
        bbox_2d=(20.0, 20.0, 40.0, 60.0),
        spatial_state="on_surface",
    )
    # Bottle on Desk 2 in frame 30
    bottle_frame30 = BoundingBox3D(
        frame_id=30,
        timestamp=3.0,
        track_id=4,
        label="water bottle",
        confidence=0.92,
        center=(-0.75, -0.1, 0.82),
        size=(0.05, 0.05, 0.1),
        bbox_2d=(20.0, 20.0, 40.0, 60.0),
        spatial_state="on_surface",
    )

    all_frames = [10, 12, 20, 30]
    all_ts = [1.0, 1.2, 2.0, 3.0]

    graph = build_relative_4d_scene_graph(
        [desk1, desk2, bottle_frame10, bottle_frame12, bottle_frame30],
        all_frames,
        all_ts,
    )

    # 1. Verify two spatially separated anchors
    assert len(graph.anchors) == 2
    anchor_labels = [a.label for a in graph.anchors]
    assert "Desk #1" in anchor_labels
    assert "Desk #2" in anchor_labels

    # 2. Frame 10: Bottle #1 is active on Desk #1
    f10 = graph.memory_timeline[10]
    b10 = next(e for e in f10 if "bottle" in e.label.lower())
    assert b10.is_active_view is True
    assert b10.anchor_label == "Desk #1"
    assert b10.relation == "on_surface"

    # 3. Frame 20: OCCLUSION HANDLING: Bottle is occluded, but preserved in 3D memory!
    f20 = graph.memory_timeline[20]
    b20 = next(e for e in f20 if "bottle" in e.label.lower())
    assert b20.is_active_view is False  # Flagged as persistent memory during occlusion
    assert b20.anchor_label == "Desk #1"
    assert b20.relation == "on_surface"
    assert b20.instance_id == 1

    # 4. Frame 30: Bottle #1 relocated to Desk #2
    f30 = graph.memory_timeline[30]
    b30 = next(e for e in f30 if "bottle" in e.label.lower())
    assert b30.is_active_view is True
    assert b30.anchor_label == "Desk #2"
    assert b30.relation == "on_surface"
    assert b30.instance_id == 1

    # 5. Transition event between anchors
    assert len(graph.events) >= 1
    ev = next(e for e in graph.events if "bottle" in e["object"].lower())
    assert "Desk #1" in ev["source_anchor"]
    assert "Desk #2" in ev["destination_anchor"]
