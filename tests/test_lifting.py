"""Tests for 3D bounding box lifting and motion trails."""

import numpy as np

from aegis.core.models import BoundingBox3D, Detection2D
from aegis.geometry.lifting import (
    compute_motion_trails,
    lift_detection_to_3d,
    serialize_boxes_3d,
)


def test_lift_detection_to_3d_basic() -> None:

    # 10x10 pointmap where (y, x) has 3D coords (x*0.1, y*0.1, 1.0)
    y, x = np.mgrid[0:10, 0:10]
    pointmap = np.stack([x * 0.1, y * 0.1, np.ones_like(x)], axis=-1).astype(np.float32)

    det = Detection2D(
        frame_id=1,
        timestamp=0.2,
        track_id=1,
        label="shoes",
        confidence=0.9,
        bbox=(2.0, 2.0, 6.0, 6.0),
    )

    box_3d = lift_detection_to_3d(det, pointmap, min_points=5)
    assert box_3d is not None
    assert box_3d.track_id == 1
    assert box_3d.label == "shoes"
    # Centroid should be around x=0.35..0.4, y=0.35..0.4, z=1.0
    np.testing.assert_allclose(box_3d.center[2], 1.0, atol=1e-3)
    assert 0.2 <= box_3d.center[0] <= 0.6
    assert 0.2 <= box_3d.center[1] <= 0.6


def test_lift_detection_to_3d_low_points_returns_none() -> None:
    pointmap = np.full((10, 10, 3), np.nan, dtype=np.float32)
    det = Detection2D(
        frame_id=1,
        timestamp=0.2,
        track_id=1,
        label="shoes",
        confidence=0.9,
        bbox=(2.0, 2.0, 4.0, 4.0),
    )
    box_3d = lift_detection_to_3d(det, pointmap, min_points=5)
    assert box_3d is None


def test_lift_detection_with_confmap() -> None:
    pointmap = np.ones((10, 10, 3), dtype=np.float32)
    confmap = np.zeros((10, 10), dtype=np.float32)
    # Set only 3 pixels to have high confidence
    confmap[3:5, 3:5] = 2.0  # 4 pixels

    det = Detection2D(
        frame_id=1,
        timestamp=0.2,
        track_id=1,
        label="shoes",
        confidence=0.9,
        bbox=(2.0, 2.0, 6.0, 6.0),
    )
    # Requires min_points=10 -> should return None
    box_3d = lift_detection_to_3d(
        det, pointmap, confmap=confmap, min_conf_thr=1.5, min_points=10
    )
    assert box_3d is None

    # With min_points=3 -> should succeed
    box_3d = lift_detection_to_3d(
        det, pointmap, confmap=confmap, min_conf_thr=1.5, min_points=3
    )
    assert box_3d is not None


def test_compute_motion_trails_and_serialization() -> None:
    box1 = BoundingBox3D(
        frame_id=1,
        timestamp=0.2,
        track_id=1,
        label="shoes",
        confidence=0.9,
        center=(0.0, 0.0, 1.0),
        size=(0.2, 0.2, 0.2),
        bbox_2d=(10.0, 10.0, 50.0, 50.0),
    )
    box2 = BoundingBox3D(
        frame_id=2,
        timestamp=0.4,
        track_id=1,
        label="shoes",
        confidence=0.85,
        center=(0.5, 0.2, 1.2),
        size=(0.2, 0.2, 0.2),
        bbox_2d=(20.0, 15.0, 60.0, 55.0),
    )
    box3 = BoundingBox3D(
        frame_id=1,
        timestamp=0.2,
        track_id=2,
        label="cabinet",
        confidence=0.95,
        center=(1.5, 0.0, 2.0),
        size=(0.6, 0.8, 1.2),
        bbox_2d=(100.0, 50.0, 200.0, 180.0),
    )

    trails = compute_motion_trails([box1, box2, box3])
    assert len(trails) == 2
    assert trails[1] == [(0.0, 0.0, 1.0), (0.5, 0.2, 1.2)]
    assert trails[2] == [(1.5, 0.0, 2.0)]

    serialized = serialize_boxes_3d([box1, box2])
    assert len(serialized) == 2
    assert serialized[0]["track_id"] == 1
    assert serialized[0]["label"] == "shoes"
    assert serialized[0]["center"] == [0.0, 0.0, 1.0]


def test_lift_detection_with_frame_size_scaling() -> None:
    # 10x10 pointmap representing a 3D grid
    y, x = np.mgrid[0:10, 0:10]
    pointmap = np.stack([x * 0.1, y * 0.1, np.ones_like(x)], axis=-1).astype(np.float32)

    # Detection on a 100x100 source frame
    det = Detection2D(
        frame_id=1,
        timestamp=0.2,
        track_id=1,
        label="shoes",
        confidence=0.9,
        bbox=(20.0, 20.0, 60.0, 60.0),
    )

    # Lift with frame_size=(100, 100) -> should scale (20..60) to (2..6) on 10x10 grid
    box_3d = lift_detection_to_3d(det, pointmap, frame_size=(100, 100), min_points=5)
    assert box_3d is not None
    assert box_3d.track_id == 1
    assert box_3d.bbox_2d == (20.0, 20.0, 60.0, 60.0)
    np.testing.assert_allclose(box_3d.center[2], 1.0, atol=1e-3)
    assert 0.2 <= box_3d.center[0] <= 0.6
    assert 0.2 <= box_3d.center[1] <= 0.6


def test_voxel_downsample() -> None:
    from aegis.geometry.lifting import voxel_downsample

    # Create 100 points clustered around (0, 0, 0) and (1, 1, 1)
    pts1 = (
        np.random.default_rng(42)
        .normal(loc=0.0, scale=0.001, size=(50, 3))
        .astype(np.float32)
    )
    pts2 = (
        np.random.default_rng(42)
        .normal(loc=1.0, scale=0.001, size=(50, 3))
        .astype(np.float32)
    )
    points = np.concatenate([pts1, pts2], axis=0)
    colors = np.full((100, 3), 200, dtype=np.uint8)

    down_pts, down_cols = voxel_downsample(points, colors, voxel_size=0.05)
    # Should reduce to exactly 2 voxel centroids
    assert len(down_pts) == 2
    assert len(down_cols) == 2
    np.testing.assert_allclose(down_pts[0], [0.0, 0.0, 0.0], atol=0.01)
    np.testing.assert_allclose(down_pts[1], [1.0, 1.0, 1.0], atol=0.01)


def test_evaluate_spatial_containment_and_states() -> None:
    from aegis.geometry.lifting import evaluate_spatial_containment_and_states

    # Cabinet at center (0.0, 0.0, 1.0) with size (1.0, 1.0, 1.0)
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

    # Shoes inside cabinet bounds
    shoes_inside = BoundingBox3D(
        frame_id=1,
        timestamp=0.2,
        track_id=2,
        label="shoes",
        confidence=0.85,
        center=(0.1, -0.1, 1.0),
        size=(0.2, 0.2, 0.2),
        bbox_2d=(30.0, 30.0, 50.0, 50.0),
    )

    # Moving shoes in frame 2 outside cabinet
    shoes_moving = BoundingBox3D(
        frame_id=2,
        timestamp=0.4,
        track_id=2,
        label="shoes",
        confidence=0.85,
        center=(2.0, 0.0, 1.0),
        size=(0.2, 0.2, 0.2),
        bbox_2d=(150.0, 30.0, 170.0, 50.0),
    )

    evaluated = evaluate_spatial_containment_and_states(
        [cab, shoes_inside, shoes_moving]
    )
    assert len(evaluated) == 3
    # Check cabinet
    assert evaluated[0].spatial_state == "static_structure"
    # Check inside shoes
    assert evaluated[1].spatial_state == "inside_cabinet"
    assert evaluated[1].container_relation == "cabinet #1"
    # Check moving shoes
    assert evaluated[2].spatial_state == "in_motion"


def test_lift_detection_with_mask_excludes_background() -> None:
    # 20x20 pointmap
    pointmap = np.zeros((20, 20, 3), dtype=np.float32)
    # Background points at z = 5.0 (wall behind)
    pointmap[:, :, 2] = 5.0
    # Foreground object points at rows 5:10, cols 5:10 with z = 1.0
    pointmap[5:10, 5:10, 0] = 0.5
    pointmap[5:10, 5:10, 1] = 0.5
    pointmap[5:10, 5:10, 2] = 1.0

    # 2D Bounding box covering a large area [2, 2, 18, 18] that includes both foreground and background
    det = Detection2D(
        frame_id=1,
        timestamp=0.1,
        track_id=1,
        label="shoes",
        confidence=0.9,
        bbox=(2.0, 2.0, 18.0, 18.0),
    )

    # Without mask: box includes wall background points, median z is skewed towards 5.0
    box_no_mask = lift_detection_to_3d(det, pointmap, min_points=5)
    assert box_no_mask is not None
    assert box_no_mask.center[2] > 2.0  # background pulled depth

    # Create binary mask covering strictly the foreground pixels [5:10, 5:10]
    mask = np.zeros((20, 20), dtype=bool)
    mask[5:10, 5:10] = True

    # With mask: only foreground points are lifted
    box_with_mask = lift_detection_to_3d(det, pointmap, mask=mask, min_points=5)
    assert box_with_mask is not None
    np.testing.assert_allclose(box_with_mask.center[2], 1.0, atol=1e-2)
    np.testing.assert_allclose(box_with_mask.center[0], 0.5, atol=1e-2)
    np.testing.assert_allclose(box_with_mask.center[1], 0.5, atol=1e-2)


def test_lift_detection_oriented_bounding_box() -> None:
    # Create synthetic points oriented along a 45-degree diagonal line
    pointmap = np.zeros((20, 20, 3), dtype=np.float32)
    mask = np.zeros((20, 20), dtype=bool)

    t = np.linspace(-1.0, 1.0, 15)
    for idx, val in enumerate(t, start=2):
        row = idx
        col = idx
        mask[row, col] = True
        # 45-degree angle in (x, y)
        pointmap[row, col] = [float(val), float(val), 1.0]

    det = Detection2D(
        frame_id=1,
        timestamp=0.1,
        track_id=1,
        label="cabinet",
        confidence=0.95,
        bbox=(0.0, 0.0, 20.0, 20.0),
    )

    box_3d = lift_detection_to_3d(det, pointmap, mask=mask, min_points=5)
    assert box_3d is not None
    assert box_3d.yaw is not None
    assert box_3d.rotation is not None
    # Angle should be approx pi/4 (0.785 rad)
    np.testing.assert_allclose(abs(box_3d.yaw), np.pi / 4, atol=0.15)
    assert len(box_3d.rotation) == 4
