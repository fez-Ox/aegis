"""Depth-map backprojection and rigid point transforms."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from aegis.poc.core.models import CameraIntrinsics


def _as_intrinsics(value: CameraIntrinsics | Sequence[float]) -> CameraIntrinsics:
    if isinstance(value, CameraIntrinsics):
        return value
    if len(value) != 4:
        raise ValueError("intrinsics must contain [fx, fy, cx, cy]")
    return CameraIntrinsics(*(float(item) for item in value))


def backproject_depth(
    depth: np.ndarray,
    intrinsics: CameraIntrinsics | Sequence[float],
    *,
    mask: np.ndarray | None = None,
    depth_min: float = 0.1,
    depth_max: float = 100.0,
    max_points: int | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Backproject valid depth pixels into camera coordinates.

    Returns ``(points, pixels)`` where points has shape ``(N, 3)`` and pixels
    contains the corresponding ``(row, column)`` integer coordinates. Sampling
    is deterministic so repeated remote jobs produce identical artifacts.
    """

    if depth.ndim != 2:
        raise ValueError("depth must be a two-dimensional array")
    if depth_min <= 0 or depth_max <= depth_min:
        raise ValueError("depth range is invalid")
    if max_points is not None and max_points <= 0:
        raise ValueError("max_points must be positive when supplied")

    camera = _as_intrinsics(intrinsics)
    valid = np.isfinite(depth) & (depth > depth_min) & (depth <= depth_max)
    if mask is not None:
        if mask.shape != depth.shape or mask.dtype != np.bool_:
            raise ValueError("mask must be a boolean array matching depth")
        valid &= mask

    rows, cols = np.nonzero(valid)
    if max_points is not None and len(rows) > max_points:
        selected = np.linspace(0, len(rows) - 1, max_points, dtype=np.int64)
        rows = rows[selected]
        cols = cols[selected]

    z = depth[rows, cols].astype(np.float32, copy=False)
    x = (cols.astype(np.float32) - camera.cx) * z / camera.fx
    y = (rows.astype(np.float32) - camera.cy) * z / camera.fy
    points = np.column_stack((x, y, z)).astype(np.float32, copy=False)
    pixels = np.column_stack((rows, cols)).astype(np.int32, copy=False)
    return points, pixels


def transform_points(points: np.ndarray, transform: np.ndarray) -> np.ndarray:
    """Apply a homogeneous 4x4 transform to an ``(N, 3)`` point array."""

    if points.ndim != 2 or points.shape[1] != 3:
        raise ValueError("points must have shape (N, 3)")
    if transform.shape != (4, 4):
        raise ValueError("transform must have shape (4, 4)")
    if len(points) == 0:
        return points.astype(np.float32, copy=True)

    homogeneous = np.concatenate(
        (points.astype(np.float64, copy=False), np.ones((len(points), 1))),
        axis=1,
    )
    transformed = homogeneous @ transform.astype(np.float64, copy=False).T
    if not np.allclose(transformed[:, 3], 1.0, atol=1e-5):
        transformed[:, :3] /= transformed[:, 3:4]
    return transformed[:, :3].astype(np.float32)
