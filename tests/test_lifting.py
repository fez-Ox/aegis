"""Tests for 3D bounding box lifting and motion trails."""

import numpy as np
import pytest

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
    shoes_static = BoundingBox3D(
        frame_id=1,
        timestamp=0.2,
        track_id=2,
        label="shoes",
        confidence=0.85,
        center=(0.1, -0.1, 1.0),
        size=(0.2, 0.2, 0.2),
        bbox_2d=(30.0, 30.0, 50.0, 50.0),
    )
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
        [cab, shoes_static, shoes_moving]
    )
    assert len(evaluated) == 3
    assert evaluated[0].spatial_state == "static_structure"
    # Relations to furniture are decided later in the gravity frame.
    assert all(box.container_relation is None for box in evaluated)
    assert evaluated[2].spatial_state == "in_motion"
    # Geometry is returned unchanged (smoothing only feeds velocities).
    assert evaluated[2].center == shoes_moving.center
    assert evaluated[1].size == shoes_static.size


def test_hand_proximity_marks_object_in_hand() -> None:
    from aegis.geometry.lifting import evaluate_spatial_containment_and_states

    hand = BoundingBox3D(
        frame_id=1,
        timestamp=0.1,
        track_id=9,
        label="hand",
        confidence=0.9,
        center=(0.0, 0.0, 0.5),
        size=(0.1, 0.1, 0.1),
        bbox_2d=(0.0, 0.0, 10.0, 10.0),
        is_hand=True,
    )
    keys = BoundingBox3D(
        frame_id=1,
        timestamp=0.1,
        track_id=3,
        label="keys",
        confidence=0.9,
        center=(0.1, 0.0, 0.5),
        size=(0.05, 0.05, 0.05),
        bbox_2d=(0.0, 0.0, 10.0, 10.0),
    )
    evaluated = evaluate_spatial_containment_and_states([hand, keys])
    assert evaluated[0].spatial_state == "hand"
    assert evaluated[1].spatial_state == "in_hand"
    assert evaluated[1].is_in_hand is True
    assert evaluated[1].held_by_hand_track_id == 9


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


def _rot_x(degrees: float) -> np.ndarray:
    angle = np.radians(degrees)
    c, s_ = np.cos(angle), np.sin(angle)
    return np.array([[1.0, 0.0, 0.0], [0.0, c, -s_], [0.0, s_, c]])


def _points_detection(label: str = "cabinet") -> Detection2D:
    return Detection2D(
        frame_id=1,
        timestamp=0.1,
        track_id=1,
        label=label,
        confidence=0.95,
        bbox=(0.0, 0.0, 100.0, 100.0),
    )


def _lift_points(points: np.ndarray, label: str = "cabinet", **kwargs):
    """Lift an explicit point set by placing it in a pointmap with a full mask."""

    side = int(np.ceil(np.sqrt(len(points))))
    pointmap = np.full((side, side, 3), np.nan, dtype=np.float32)
    mask = np.zeros((side, side), dtype=bool)
    flat = pointmap.reshape(-1, 3)
    flat[: len(points)] = points
    mask.reshape(-1)[: len(points)] = True
    return lift_detection_to_3d(
        _points_detection(label), pointmap, mask=mask, min_points=5, **kwargs
    )


def test_lift_detection_oriented_bounding_box() -> None:
    # Points along a 45-degree diagonal in the floor plane (x, z), constant y.
    t = np.linspace(-1.0, 1.0, 15)
    points = np.column_stack([t, np.full_like(t, 0.5), t]).astype(np.float32)

    box_3d = _lift_points(points)
    assert box_3d is not None
    assert box_3d.yaw is not None
    assert box_3d.rotation is not None
    np.testing.assert_allclose(abs(box_3d.yaw), np.pi / 4, atol=0.15)
    assert len(box_3d.rotation) == 4
    # Height (along up) is the minimum extent; length > width.
    assert box_3d.size[2] == pytest.approx(0.05)
    assert box_3d.size[0] > box_3d.size[1]


def _box_points(length: float, width: float, height: float, n: int = 12) -> np.ndarray:
    """Surface-free filled box in a level Y-down frame (up = -Y), bottom at y=0."""

    a, b, v = np.meshgrid(
        np.linspace(-length / 2, length / 2, n),
        np.linspace(-width / 2, width / 2, n),
        np.linspace(0.0, height, n),
        indexing="ij",
    )
    return np.column_stack([a.ravel(), -v.ravel(), b.ravel()])


def test_obb_height_is_along_up_for_tilted_gravity() -> None:
    from aegis.geometry.gravity import GravityFrame

    rotation = _rot_x(40.0)
    points = _box_points(1.0, 0.5, 0.2) @ rotation.T
    up = rotation @ np.array([0.0, -1.0, 0.0])
    gravity = GravityFrame(
        up=tuple(up), floor_offset=0.0, source="floor_plane", confidence=1.0
    )
    box_3d = _lift_points(points.astype(np.float32), gravity=gravity)
    assert box_3d is not None
    np.testing.assert_allclose(box_3d.size, (0.9, 0.45, 0.18), rtol=0.12)
    assert box_3d.up_max - box_3d.up_min == pytest.approx(box_3d.size[2])
    assert box_3d.up_min == pytest.approx(0.01, abs=0.02)


def test_rotation_quaternion_matches_axes() -> None:
    from aegis.geometry.gravity import GravityFrame
    from aegis.geometry.transforms import quaternion_xyzw_to_matrix

    yaw = 0.6
    rotation = np.array(
        [
            [np.cos(yaw), 0.0, -np.sin(yaw)],
            [0.0, 1.0, 0.0],
            [np.sin(yaw), 0.0, np.cos(yaw)],
        ]
    )
    points = _box_points(1.2, 0.3, 0.4) @ rotation.T
    box_3d = _lift_points(points.astype(np.float32))
    assert box_3d is not None
    matrix = quaternion_xyzw_to_matrix((0.0, 0.0, 0.0), box_3d.rotation)[:3, :3]
    e1, e2, up = GravityFrame.assumed().basis()
    np.testing.assert_allclose(matrix[:, 2], up, atol=1e-9)
    expected_a = np.cos(box_3d.yaw) * e1 + np.sin(box_3d.yaw) * e2
    np.testing.assert_allclose(matrix[:, 0], expected_a, atol=1e-9)
    # The long side is recovered (direction known up to sign).
    assert abs(float(np.dot(matrix[:, 0], rotation @ np.array([1.0, 0.0, 0.0])))) > 0.99


def _table_points() -> np.ndarray:
    rng = np.random.default_rng(0)
    top_xz = rng.uniform(-0.5, 0.5, size=(2000, 2))
    top = np.column_stack([top_xz[:, 0], np.full(2000, -0.75), top_xz[:, 1]])
    legs = []
    for x, z in ((-0.45, -0.45), (0.45, -0.45), (-0.45, 0.45), (0.45, 0.45)):
        heights = rng.uniform(0.0, 0.75, size=100)
        legs.append(np.column_stack([np.full(100, x), -heights, np.full(100, z)]))
    return np.concatenate([top, *legs]).astype(np.float32)


def test_support_surface_of_table() -> None:
    desk = _lift_points(_table_points(), label="desk")
    assert desk is not None
    assert desk.support_up == pytest.approx(0.75, abs=0.03)
    shoes = _lift_points(_table_points(), label="shoes", unit=2.0)
    assert shoes is not None
    assert shoes.support_up is None


def test_max_extent_filter_uses_vocabulary() -> None:
    points = _box_points(1.5, 0.3, 0.3)
    assert _lift_points(points.astype(np.float32), label="shoes") is None
    assert _lift_points(points.astype(np.float32), label="desk") is not None


def test_quaternion_from_matrix_reference_vector() -> None:
    from aegis.geometry.transforms import quaternion_from_matrix

    matrix = np.column_stack([(1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0)])
    np.testing.assert_allclose(
        quaternion_from_matrix(matrix), (0.70710678, 0.0, 0.0, 0.70710678), atol=1e-8
    )
