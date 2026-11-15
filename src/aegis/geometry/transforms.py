"""Pose conversion utilities."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def quaternion_xyzw_to_matrix(
    translation: Sequence[float], quaternion: Sequence[float]
) -> np.ndarray:
    """Convert translation plus an ``[x, y, z, w]`` quaternion to 4x4.

    DROID-SLAM/LieTorch stores its quaternion with the real component last.
    The returned matrix maps camera-frame points into the trajectory frame when
    the input pose is a camera-to-world pose.
    """

    if len(translation) != 3 or len(quaternion) != 4:
        raise ValueError("translation must have 3 values and quaternion 4 values")
    tx, ty, tz = (float(value) for value in translation)
    qx, qy, qz, qw = (float(value) for value in quaternion)
    norm = float(np.linalg.norm([qx, qy, qz, qw]))
    if norm <= np.finfo(np.float64).eps:
        raise ValueError("quaternion norm must be non-zero")
    qx, qy, qz, qw = (value / norm for value in (qx, qy, qz, qw))

    matrix = np.eye(4, dtype=np.float64)
    matrix[0, 0] = 1 - 2 * (qy * qy + qz * qz)
    matrix[0, 1] = 2 * (qx * qy - qz * qw)
    matrix[0, 2] = 2 * (qx * qz + qy * qw)
    matrix[1, 0] = 2 * (qx * qy + qz * qw)
    matrix[1, 1] = 1 - 2 * (qx * qx + qz * qz)
    matrix[1, 2] = 2 * (qy * qz - qx * qw)
    matrix[2, 0] = 2 * (qx * qz - qy * qw)
    matrix[2, 1] = 2 * (qy * qz + qx * qw)
    matrix[2, 2] = 1 - 2 * (qx * qx + qy * qy)
    matrix[:3, 3] = (tx, ty, tz)
    return matrix


def scale_pose_translation(matrix: np.ndarray, scale: float) -> np.ndarray:
    """Return a copy of a pose with its translation scaled."""

    if matrix.shape != (4, 4):
        raise ValueError("matrix must have shape (4, 4)")
    if scale <= 0:
        raise ValueError("scale must be positive")
    scaled = matrix.astype(np.float64, copy=True)
    scaled[:3, 3] *= scale
    return scaled


def quaternion_from_matrix(matrix: np.ndarray) -> tuple[float, float, float, float]:
    """Convert a 3x3 rotation matrix to an ``(x, y, z, w)`` quaternion.

    Uses Shepperd's method (numerically stable for every rotation). The
    result is normalised and has ``w >= 0``.
    """

    m = np.asarray(matrix, dtype=np.float64)
    if m.shape != (3, 3):
        raise ValueError("rotation matrix must have shape (3, 3)")
    trace = float(m[0, 0] + m[1, 1] + m[2, 2])
    if trace > 0.0:
        s = 2.0 * np.sqrt(trace + 1.0)
        w = 0.25 * s
        x = (m[2, 1] - m[1, 2]) / s
        y = (m[0, 2] - m[2, 0]) / s
        z = (m[1, 0] - m[0, 1]) / s
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = 2.0 * np.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2])
        w = (m[2, 1] - m[1, 2]) / s
        x = 0.25 * s
        y = (m[0, 1] + m[1, 0]) / s
        z = (m[0, 2] + m[2, 0]) / s
    elif m[1, 1] > m[2, 2]:
        s = 2.0 * np.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2])
        w = (m[0, 2] - m[2, 0]) / s
        x = (m[0, 1] + m[1, 0]) / s
        y = 0.25 * s
        z = (m[1, 2] + m[2, 1]) / s
    else:
        s = 2.0 * np.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1])
        w = (m[1, 0] - m[0, 1]) / s
        x = (m[0, 2] + m[2, 0]) / s
        y = (m[1, 2] + m[2, 1]) / s
        z = 0.25 * s
    quat = np.array([x, y, z, w], dtype=np.float64)
    quat /= float(np.linalg.norm(quat))
    if quat[3] < 0:
        quat = -quat
    return (float(quat[0]), float(quat[1]), float(quat[2]), float(quat[3]))
