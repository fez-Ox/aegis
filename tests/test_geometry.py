"""Tests for deterministic geometry utilities."""

import numpy as np
import pytest

from aegis.geometry.backproject import backproject_depth, transform_points
from aegis.geometry.transforms import quaternion_xyzw_to_matrix


def test_backproject_depth_center_pixel() -> None:
    depth = np.ones((3, 3), dtype=np.float32)
    points, pixels = backproject_depth(
        depth,
        [1.0, 1.0, 1.0, 1.0],
        max_points=9,
    )

    center_index = np.where((pixels == [1, 1]).all(axis=1))[0][0]
    np.testing.assert_allclose(points[center_index], [0.0, 0.0, 1.0])


def test_backproject_depth_is_deterministically_capped() -> None:
    depth = np.ones((10, 10), dtype=np.float32)
    first_points, first_pixels = backproject_depth(
        depth, [10.0, 10.0, 5.0, 5.0], max_points=7
    )
    second_points, second_pixels = backproject_depth(
        depth, [10.0, 10.0, 5.0, 5.0], max_points=7
    )

    assert first_points.shape == (7, 3)
    np.testing.assert_array_equal(first_pixels, second_pixels)
    np.testing.assert_allclose(first_points, second_points)


def test_transform_points_applies_rotation_and_translation() -> None:
    points = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
    transform = quaternion_xyzw_to_matrix(
        [2.0, 3.0, 4.0], [0.0, 0.0, np.sin(np.pi / 4), np.cos(np.pi / 4)]
    )

    transformed = transform_points(points, transform)
    np.testing.assert_allclose(transformed, [[2.0, 4.0, 4.0]], atol=1e-6)


def test_invalid_depth_mask_is_rejected() -> None:
    with pytest.raises(ValueError, match="boolean array"):
        backproject_depth(
            np.ones((2, 2), dtype=np.float32),
            [1.0, 1.0, 0.0, 0.0],
            mask=np.ones((2, 2), dtype=np.uint8),
        )


def test_binary_ply_layout(tmp_path) -> None:
    from aegis.remote.workers import _write_ply

    points = np.array([[0.0, 1.0, 2.0], [3.0, 4.0, 5.0]], dtype=np.float32)
    colors = np.array([[255, 0, 0], [0, 255, 0]], dtype=np.uint8)
    path = tmp_path / "cloud.ply"
    _write_ply(path, points, colors)
    raw = path.read_bytes()
    header_end = raw.index(b"end_header\n") + len(b"end_header\n")
    header = raw[:header_end].decode()
    assert "format binary_little_endian 1.0" in header
    assert "element vertex 2" in header
    assert len(raw) == header_end + 15 * 2
    body = np.frombuffer(raw[header_end:], dtype=[("p", "<f4", 3), ("c", "u1", 3)])
    np.testing.assert_allclose(body["p"], points)
    np.testing.assert_array_equal(body["c"], colors)
