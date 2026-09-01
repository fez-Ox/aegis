"""Tests for deterministic geometry utilities."""

import numpy as np
import pytest

from aegis.poc.geometry.backproject import backproject_depth, transform_points
from aegis.poc.geometry.transforms import quaternion_xyzw_to_matrix


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
