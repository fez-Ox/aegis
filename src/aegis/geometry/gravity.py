"""Per-session gravity frame: up direction, floor height and a scale unit.

VGGT-Ω places the world origin at the first keyframe's camera (OpenCV axes:
+X right, +Y down, +Z forward). "Up" is therefore only -Y when the phone
started level, which it usually did not. This module estimates the real up
direction from the reconstructed floor and stores it *beside* the raw
coordinates; coordinates are never rotated.

Derived quantities:

* ``elevation(p) = dot(p, up)``
* ``height(p) = elevation(p) - floor_offset`` (height above the floor)
* ``horizontal(p)`` = coordinates in the floor plane, basis ``(e1, e2)``
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

_ASSUMED_UP = (0.0, -1.0, 0.0)


def _unit(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm < 1e-12:
        raise ValueError("cannot normalise a zero vector")
    return vector / norm


@dataclass(frozen=True, slots=True)
class GravityFrame:
    """Gravity-aligned reference frame of one reconstructed session."""

    up: tuple[float, float, float]
    floor_offset: float | None
    source: str
    confidence: float
    inlier_ratio: float = 0.0
    camera_height: float | None = None

    @classmethod
    def assumed(cls) -> GravityFrame:
        """Legacy assumption: up is -Y of the first camera, floor unknown."""

        return cls(
            up=_ASSUMED_UP,
            floor_offset=None,
            source="assumed",
            confidence=0.0,
        )

    # ------------------------------------------------------------- geometry
    def basis(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return ``(e1, e2, up)``; right-handed with ``cross(e1, e2) == up``.

        For the assumed frame this gives ``e1 = +X`` and ``e2 = +Z``, so
        :meth:`horizontal` reproduces the legacy ``(x, z)`` floor plane.
        """

        up = _unit(np.asarray(self.up, dtype=np.float64))
        x_axis = np.array([1.0, 0.0, 0.0])
        e1 = x_axis - float(np.dot(x_axis, up)) * up
        if float(np.linalg.norm(e1)) < 0.1:
            z_axis = np.array([0.0, 0.0, 1.0])
            e1 = z_axis - float(np.dot(z_axis, up)) * up
        e1 = _unit(e1)
        e2 = np.cross(up, e1)
        return e1, e2, up

    def elevation(self, point: Any) -> float:
        _e1, _e2, up = self.basis()
        return float(np.dot(np.asarray(point, dtype=np.float64), up))

    def height(self, point: Any) -> float | None:
        if self.floor_offset is None:
            return None
        return self.elevation(point) - self.floor_offset

    def horizontal(self, point: Any) -> tuple[float, float]:
        e1, e2, _up = self.basis()
        p = np.asarray(point, dtype=np.float64)
        return float(np.dot(p, e1)), float(np.dot(p, e2))

    def from_horizontal(self, h1: float, h2: float, elevation: float) -> np.ndarray:
        e1, e2, up = self.basis()
        return h1 * e1 + h2 * e2 + elevation * up

    # ---------------------------------------------------------- reliability
    def is_reliable(self, min_confidence: float) -> bool:
        return self.source == "floor_plane" and self.confidence >= min_confidence

    def unit(self, assumed_camera_height: float, min_confidence: float) -> float:
        """Factor turning metre-like thresholds into this session's units."""

        if (
            not self.is_reliable(min_confidence)
            or self.camera_height is None
            or self.camera_height <= 0
            or assumed_camera_height <= 0
        ):
            return 1.0
        return float(min(2.0, max(0.5, self.camera_height / assumed_camera_height)))

    # -------------------------------------------------------- serialisation
    def as_dict(self) -> dict[str, Any]:
        return {
            "up": [float(v) for v in self.up],
            "floor_offset": self.floor_offset,
            "source": self.source,
            "confidence": float(self.confidence),
            "inlier_ratio": float(self.inlier_ratio),
            "camera_height": self.camera_height,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any] | None) -> GravityFrame:
        if not raw or "up" not in raw:
            return cls.assumed()
        up = _unit(np.asarray(raw["up"], dtype=np.float64))
        floor_offset = raw.get("floor_offset")
        camera_height = raw.get("camera_height")
        return cls(
            up=(float(up[0]), float(up[1]), float(up[2])),
            floor_offset=None if floor_offset is None else float(floor_offset),
            source=str(raw.get("source", "assumed")),
            confidence=float(raw.get("confidence", 0.0)),
            inlier_ratio=float(raw.get("inlier_ratio", 0.0)),
            camera_height=None if camera_height is None else float(camera_height),
        )


def _angle_degrees(a: np.ndarray, b: np.ndarray) -> float:
    cosine = float(np.clip(np.dot(_unit(a), _unit(b)), -1.0, 1.0))
    return math.degrees(math.acos(cosine))


def _prior_up(camera_rotations: np.ndarray | None) -> np.ndarray:
    if camera_rotations is not None and len(camera_rotations) > 0:
        rotations = np.asarray(camera_rotations, dtype=np.float64)
        mean_up = np.mean(-rotations[:, :, 1], axis=0)
        if float(np.linalg.norm(mean_up)) > 1e-6:
            return _unit(mean_up)
    return np.asarray(_ASSUMED_UP, dtype=np.float64)


def _fallback(
    points: np.ndarray, camera_positions: np.ndarray, prior: np.ndarray
) -> GravityFrame:
    floor_offset = float(np.percentile(points @ prior, 2.0))
    camera_height = float(np.median(camera_positions @ prior) - floor_offset)
    return GravityFrame(
        up=(float(prior[0]), float(prior[1]), float(prior[2])),
        floor_offset=floor_offset,
        source="camera_prior",
        confidence=0.2,
        inlier_ratio=0.0,
        camera_height=camera_height,
    )


def estimate_gravity(
    points: np.ndarray,
    camera_positions: np.ndarray,
    camera_rotations: np.ndarray | None = None,
    *,
    iterations: int = 500,
    seed: int = 0,
    max_candidates: int = 20000,
    inlier_fraction_of_scale: float = 0.02,
    max_tilt_degrees: float = 60.0,
    max_below_fraction: float = 0.10,
    min_inliers: int = 200,
    min_inlier_ratio: float = 0.08,
    path_disagreement_degrees: float = 25.0,
) -> GravityFrame:
    """Estimate up and floor height from a fused cloud and the camera path.

    A RANSAC plane fit on points below the cameras finds the floor. Planes
    with many points beneath them (table tops) are rejected. The result is
    cross-checked against the plane of the camera path when the wearer moved
    enough for that plane to be well defined. Without a usable floor the
    camera orientation prior is returned with low confidence.
    """

    pts = np.asarray(points, dtype=np.float64).reshape(-1, 3)
    pts = pts[np.isfinite(pts).all(axis=1)]
    cams = np.asarray(camera_positions, dtype=np.float64).reshape(-1, 3)
    cams = cams[np.isfinite(cams).all(axis=1)]
    if len(pts) < 50 or len(cams) == 0:
        return GravityFrame.assumed()

    rotations = None if camera_rotations is None else np.asarray(camera_rotations)
    prior = _prior_up(rotations)

    camera_median = np.median(cams, axis=0)
    scale = float(np.median(np.linalg.norm(pts - camera_median, axis=1)))
    if not math.isfinite(scale) or scale <= 0:
        return GravityFrame.assumed()
    tau = inlier_fraction_of_scale * scale

    rng = np.random.default_rng(seed)
    candidates = pts[(pts - camera_median) @ prior < 0.0]
    if len(candidates) > max_candidates:
        chosen = rng.choice(len(candidates), size=max_candidates, replace=False)
        candidates = candidates[chosen]
    if len(candidates) < min_inliers:
        return _fallback(pts, cams, prior)

    min_cos = math.cos(math.radians(max_tilt_degrees))
    best_count = 0
    best_normal: np.ndarray | None = None
    best_point: np.ndarray | None = None
    for _ in range(iterations):
        sample = rng.choice(len(candidates), size=3, replace=False)
        p0, p1, p2 = candidates[sample]
        normal = np.cross(p1 - p0, p2 - p0)
        norm = float(np.linalg.norm(normal))
        if norm < 1e-12:
            continue
        normal = normal / norm
        if float(np.dot(normal, prior)) < 0:
            normal = -normal
        if float(np.dot(normal, prior)) < min_cos:
            continue
        distances = (candidates - p0) @ normal
        inliers = np.abs(distances) < tau
        below = distances < -3.0 * tau
        if float(below.mean()) > max_below_fraction:
            continue
        count = int(inliers.sum())
        if count > best_count:
            best_count = count
            best_normal = normal
            best_point = p0

    if (
        best_normal is None
        or best_point is None
        or best_count < min_inliers
        or best_count / len(candidates) < min_inlier_ratio
    ):
        return _fallback(pts, cams, prior)

    inlier_points = candidates[np.abs((candidates - best_point) @ best_normal) < tau]
    centred = inlier_points - inlier_points.mean(axis=0)
    _u, _s, vt = np.linalg.svd(centred, full_matrices=False)
    normal = vt[-1]
    if float(np.dot(normal, prior)) < 0:
        normal = -normal
    normal = _unit(normal)
    floor_offset = float(np.mean(inlier_points @ normal))
    refined_inliers = np.abs(candidates @ normal - floor_offset) < tau
    inlier_ratio = float(refined_inliers.mean())

    heights = cams @ normal - floor_offset
    if float((heights > 0).mean()) < 0.95:
        return _fallback(pts, cams, prior)
    camera_height = float(np.median(heights))

    agree = True
    if len(cams) >= 10:
        centred_cams = cams - cams.mean(axis=0)
        _cu, singular, cam_vt = np.linalg.svd(centred_cams, full_matrices=False)
        if len(singular) == 3 and singular[1] > 0 and singular[2] / singular[1] < 0.3:
            path_normal = cam_vt[2]
            if float(np.dot(path_normal, prior)) < 0:
                path_normal = -path_normal
            agree = _angle_degrees(normal, path_normal) <= path_disagreement_degrees

    confidence = min(1.0, inlier_ratio / 0.30) * (1.0 if agree else 0.5)
    return GravityFrame(
        up=(float(normal[0]), float(normal[1]), float(normal[2])),
        floor_offset=floor_offset,
        source="floor_plane",
        confidence=float(confidence),
        inlier_ratio=inlier_ratio,
        camera_height=camera_height,
    )
