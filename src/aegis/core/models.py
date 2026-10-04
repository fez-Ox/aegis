"""Small, serializable data contracts shared by pipeline stages."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite
from typing import Any


@dataclass(frozen=True, slots=True)
class CameraIntrinsics:
    """Pinhole camera intrinsics in pixel units."""

    fx: float
    fy: float
    cx: float
    cy: float

    def __post_init__(self) -> None:
        values = (self.fx, self.fy, self.cx, self.cy)
        if not all(isfinite(value) for value in values):
            raise ValueError("camera intrinsics must be finite")
        if self.fx <= 0 or self.fy <= 0:
            raise ValueError("focal lengths must be positive")

    def as_list(self) -> list[float]:
        """Return the conventional ``[fx, fy, cx, cy]`` representation."""

        return [self.fx, self.fy, self.cx, self.cy]


@dataclass(frozen=True, slots=True)
class Frame:
    """A normalized RGB video frame and its source timestamp."""

    frame_id: int
    timestamp: float
    path: str
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.frame_id < 0:
            raise ValueError("frame_id must be non-negative")
        if self.timestamp < 0:
            raise ValueError("timestamp must be non-negative")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("frame dimensions must be positive")


@dataclass(frozen=True, slots=True)
class Pose:
    """A camera pose represented as a homogeneous 4x4 matrix."""

    frame_id: int
    timestamp: float
    matrix: tuple[tuple[float, ...], ...]
    convention: str = "T_world_camera"
    source: str = "unknown"

    def __post_init__(self) -> None:
        if len(self.matrix) != 4 or any(len(row) != 4 for row in self.matrix):
            raise ValueError("pose matrix must have shape 4x4")
        if self.frame_id < 0 or self.timestamp < 0:
            raise ValueError("pose frame_id and timestamp must be non-negative")

    @classmethod
    def from_matrix(
        cls,
        frame_id: int,
        timestamp: float,
        matrix: Sequence[Sequence[float]],
        *,
        convention: str = "T_world_camera",
        source: str = "unknown",
    ) -> Pose:
        """Construct a pose while converting matrix values to JSON-safe tuples."""

        normalized = tuple(tuple(float(value) for value in row) for row in matrix)
        return cls(
            frame_id=frame_id,
            timestamp=timestamp,
            matrix=normalized,
            convention=convention,
            source=source,
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable pose record."""

        return {
            "frame_id": self.frame_id,
            "timestamp": self.timestamp,
            "matrix": [list(row) for row in self.matrix],
            "convention": self.convention,
            "source": self.source,
        }


@dataclass(frozen=True, slots=True)
class Detection2D:
    """A 2D bounding box detection with track identifier and optional segmentation mask."""

    frame_id: int
    timestamp: float
    track_id: int
    label: str
    confidence: float
    bbox: tuple[float, float, float, float]  # (x1, y1, x2, y2)
    mask: Any = None  # Optional binary np.ndarray mask (H, W)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable 2D detection record."""
        return {
            "frame_id": self.frame_id,
            "timestamp": self.timestamp,
            "track_id": self.track_id,
            "label": self.label,
            "confidence": self.confidence,
            "bbox": list(self.bbox),
        }


@dataclass(frozen=True, slots=True)
class BoundingBox3D:
    """A lifted 3D bounding box associated with an identified object."""

    frame_id: int
    timestamp: float
    track_id: int
    label: str
    confidence: float
    center: tuple[float, float, float]  # (x, y, z)
    size: tuple[float, float, float]  # (dx, dy, dz)
    bbox_2d: tuple[float, float, float, float]  # (x1, y1, x2, y2)
    spatial_state: str = "on_surface"
    container_relation: str | None = None
    rotation: tuple[float, float, float, float] | None = None  # Quaternion (x, y, z, w)
    yaw: float | None = None  # Yaw angle in radians around vertical Z axis

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable 3D bounding box record."""
        data: dict[str, Any] = {
            "frame_id": self.frame_id,
            "timestamp": self.timestamp,
            "track_id": self.track_id,
            "label": self.label,
            "confidence": self.confidence,
            "center": list(self.center),
            "size": list(self.size),
            "bbox_2d": list(self.bbox_2d),
            "spatial_state": self.spatial_state,
            "container_relation": self.container_relation,
        }
        if self.rotation is not None:
            data["rotation"] = list(self.rotation)
        if self.yaw is not None:
            data["yaw"] = self.yaw
        return data

