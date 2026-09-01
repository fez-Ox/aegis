"""Unit tests for Relative 4D Scene Graph (R4DSG) Memory."""

from aegis.poc.core.models import BoundingBox3D
from aegis.poc.memory.scene_graph import (
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
