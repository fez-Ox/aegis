"""Tests for overlapping-window VGGT alignment and configuration."""

from __future__ import annotations

import numpy as np
import pytest

from aegis.core.config import RuntimeConfig
from aegis.remote.workers import (
    _apply_similarity_points,
    _apply_similarity_pose,
    _similarity_3d,
)


def test_similarity_recovers_rotation_scale_translation() -> None:
    rng = np.random.default_rng(7)
    source = rng.normal(size=(12, 3)) * 3
    rotation = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    scale, translation = 1.7, np.array([4.0, -2.0, 1.0])
    target = _apply_similarity_points(source, rotation, scale, translation)
    got_rotation, got_scale, got_translation = _similarity_3d(source, target)
    aligned = _apply_similarity_points(source, got_rotation, got_scale, got_translation)
    assert np.allclose(aligned, target, atol=1e-6)
    assert got_scale == pytest.approx(scale)


def test_pose_transform_moves_origin_and_orientation() -> None:
    pose = np.eye(4)
    rotation = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=float)
    result = _apply_similarity_pose(pose, rotation, 2.0, np.array([1.0, 2.0, 3.0]))
    assert np.allclose(result[:3, :3], rotation)
    assert np.allclose(result[:3, 3], [1.0, 2.0, 3.0])


def test_window_config_validation() -> None:
    config = RuntimeConfig.from_mapping(
        {"vggt": {"window_size": 60, "window_overlap": 12}}
    )
    assert config.vggt.window_size == 60
    with pytest.raises(ValueError):
        RuntimeConfig.from_mapping({"vggt": {"window_size": 20, "window_overlap": 20}})
    with pytest.raises(ValueError):
        RuntimeConfig.from_mapping({"vggt": {"window_overlap": 1}})
