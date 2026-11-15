"""Tests for the per-session gravity frame estimator."""

from __future__ import annotations

import math

import numpy as np
import pytest

from aegis.geometry.gravity import GravityFrame, estimate_gravity


def _rot_x(degrees: float) -> np.ndarray:
    a = math.radians(degrees)
    c, s = math.cos(a), math.sin(a)
    return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])


def make_room(tilt_deg: float, seed: int = 0, *, floor: bool = True):
    """Room in a level Y-down frame (floor at y=0, up=-Y), then pitched.

    Returns world points, camera positions, camera rotations and the true up.
    """

    rng = np.random.default_rng(seed)
    parts = []
    if floor:
        xz = rng.uniform(-2.0, 2.0, size=(4000, 2))
        parts.append(np.column_stack([xz[:, 0], np.zeros(4000), xz[:, 1]]))
    # Table top 0.75 above the floor (y = -0.75 because up is -Y).
    txz = rng.uniform(-0.5, 0.5, size=(600, 2))
    parts.append(np.column_stack([txz[:, 0], np.full(600, -0.75), txz[:, 1] + 1.0]))
    # Two walls from the floor to 2.5 high.
    wy = rng.uniform(-2.5, 0.0, size=1500)
    wx = rng.uniform(-2.0, 2.0, size=1500)
    parts.append(np.column_stack([wx, wy, np.full(1500, 2.0)]))
    wy2 = rng.uniform(-2.5, 0.0, size=1500)
    wz = rng.uniform(-2.0, 2.0, size=1500)
    parts.append(np.column_stack([np.full(1500, -2.0), wy2, wz]))
    points = np.concatenate(parts) + rng.normal(
        0.0, 0.005, size=(sum(len(p) for p in parts), 3)
    )

    path_x = np.linspace(-1.0, 1.0, 10)
    path_z = np.sin(path_x * 2.0) * 0.8
    cams = np.column_stack([path_x, -1.4 + rng.normal(0.0, 0.03, size=10), path_z])

    rotation = _rot_x(tilt_deg)
    world_points = points @ rotation.T
    world_cams = cams @ rotation.T
    rotations = np.repeat(rotation[None], len(cams), axis=0)
    true_up = rotation @ np.array([0.0, -1.0, 0.0])
    return world_points, world_cams, rotations, true_up


def _angle(a, b) -> float:
    a = np.asarray(a) / np.linalg.norm(a)
    b = np.asarray(b) / np.linalg.norm(b)
    return math.degrees(math.acos(float(np.clip(np.dot(a, b), -1.0, 1.0))))


@pytest.mark.parametrize("tilt", [0.0, 40.0])
def test_recovers_up_for_level_and_pitched_camera(tilt: float) -> None:
    points, cams, rotations, true_up = make_room(tilt)
    gravity = estimate_gravity(points, cams, rotations)
    assert gravity.source == "floor_plane"
    assert _angle(gravity.up, true_up) < 2.0
    assert gravity.confidence >= 0.5
    assert gravity.camera_height is not None
    assert abs(gravity.camera_height - 1.4) < 0.05


def test_table_top_is_not_chosen_as_floor() -> None:
    points, cams, rotations, _true_up = make_room(25.0)
    gravity = estimate_gravity(points, cams, rotations)
    floor_point = _rot_x(25.0) @ np.array([0.3, 0.0, -0.4])
    table_point = _rot_x(25.0) @ np.array([0.0, -0.75, 1.0])
    assert abs(gravity.height(floor_point)) < 0.03
    assert abs(gravity.height(table_point) - 0.75) < 0.03


def test_no_floor_falls_back_with_low_confidence() -> None:
    points, cams, rotations, _true_up = make_room(10.0, floor=False)
    # Remove the table too: only walls remain below the cameras.
    gravity = estimate_gravity(points[600:], cams, rotations, min_inliers=2000)
    assert gravity.source == "camera_prior"
    assert gravity.confidence < 0.5
    assert not gravity.is_reliable(0.5)


def test_empty_input_returns_assumed() -> None:
    gravity = estimate_gravity(np.zeros((0, 3)), np.zeros((0, 3)))
    assert gravity == GravityFrame.assumed()


def test_basis_for_assumed_frame_is_x_and_z() -> None:
    gravity = GravityFrame.assumed()
    e1, e2, up = gravity.basis()
    np.testing.assert_allclose(e1, [1.0, 0.0, 0.0])
    np.testing.assert_allclose(e2, [0.0, 0.0, 1.0])
    np.testing.assert_allclose(np.cross(e1, e2), up)
    assert gravity.horizontal((1.0, 2.0, 3.0)) == (1.0, 3.0)
    assert gravity.elevation((1.0, 2.0, 3.0)) == -2.0
    assert gravity.height((1.0, 2.0, 3.0)) is None
    np.testing.assert_allclose(gravity.from_horizontal(1.0, 3.0, -2.0), [1.0, 2.0, 3.0])


def test_basis_is_right_handed_for_arbitrary_up() -> None:
    gravity = GravityFrame(
        up=(0.0, -0.6, 0.8),
        floor_offset=0.0,
        source="floor_plane",
        confidence=1.0,
    )
    e1, e2, up = gravity.basis()
    np.testing.assert_allclose(np.cross(e1, e2), up, atol=1e-12)
    assert abs(float(np.dot(e1, up))) < 1e-12


def test_unit_scaling_and_clamp() -> None:
    base = {"up": (0.0, -1.0, 0.0), "floor_offset": 0.0, "source": "floor_plane"}
    reliable = GravityFrame(**base, confidence=1.0, camera_height=2.1)
    assert reliable.unit(1.4, 0.5) == pytest.approx(1.5)
    tall = GravityFrame(**base, confidence=1.0, camera_height=10.0)
    assert tall.unit(1.4, 0.5) == 2.0
    weak = GravityFrame(**base, confidence=0.1, camera_height=2.1)
    assert weak.unit(1.4, 0.5) == 1.0
    assert GravityFrame.assumed().unit(1.4, 0.5) == 1.0


def test_round_trip_dict() -> None:
    points, cams, rotations, _ = make_room(15.0)
    gravity = estimate_gravity(points, cams, rotations)
    rebuilt = GravityFrame.from_dict(gravity.as_dict())
    np.testing.assert_allclose(rebuilt.up, gravity.up)
    assert rebuilt.floor_offset == pytest.approx(gravity.floor_offset)
    assert rebuilt.source == gravity.source
    assert GravityFrame.from_dict(None) == GravityFrame.assumed()
    assert GravityFrame.from_dict({}) == GravityFrame.assumed()


def test_deterministic_for_fixed_seed() -> None:
    points, cams, rotations, _ = make_room(30.0)
    first = estimate_gravity(points, cams, rotations, seed=3)
    second = estimate_gravity(points, cams, rotations, seed=3)
    assert first == second


def test_vggt_fallback_requires_opt_in(monkeypatch, tmp_path) -> None:
    import builtins

    cv2 = pytest.importorskip("cv2")
    from aegis.core.config import VggtConfig
    from aegis.geometry.vggt_runner import run_vggt_reconstruction

    image = tmp_path / "frame.png"
    cv2.imwrite(str(image), np.zeros((32, 32, 3), dtype=np.uint8))
    real_import = builtins.__import__

    def _no_vggt(name, *args, **kwargs):
        if name.startswith("vggt_omega"):
            raise ImportError("vggt_omega missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _no_vggt)
    monkeypatch.delenv("AEGIS_ALLOW_SYNTHETIC_VGGT", raising=False)
    with pytest.raises(RuntimeError, match="reconstruction failed"):
        run_vggt_reconstruction([image, image], VggtConfig())


def test_vggt_synthetic_scene_is_marked_when_opted_in(monkeypatch, tmp_path) -> None:
    import builtins

    cv2 = pytest.importorskip("cv2")
    from aegis.core.config import VggtConfig
    from aegis.geometry.vggt_runner import run_vggt_reconstruction

    image = tmp_path / "frame.png"
    cv2.imwrite(str(image), np.full((32, 32, 3), 128, dtype=np.uint8))
    real_import = builtins.__import__

    def _no_vggt(name, *args, **kwargs):
        if name.startswith("vggt_omega"):
            raise ImportError("vggt_omega missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _no_vggt)
    monkeypatch.setenv("AEGIS_ALLOW_SYNTHETIC_VGGT", "1")
    result = run_vggt_reconstruction([image, image], VggtConfig(image_size=32))
    assert result["synthetic"] is True
