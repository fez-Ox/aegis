"""Room-level spatial region estimation (Level 1 of the R4DSG hierarchy).

Rooms sit above spatial anchors in the memory hierarchy:

    Room -> Spatial Anchor -> Object Instance

Rooms are estimated from the camera wearer's trajectory (Hydra-style
spatially-gated clustering of keyframe positions) and typed from the
composition of room-defining landmarks (bed, sofa, door, ...) detected by
the open-vocabulary detector (cf. HOV-SG's room classification). The
representation is deliberately lightweight: a floor-plane footprint per
room, not dense geometry, in line with the R4DSG principle of avoiding
noisy dense point-cloud memories.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from aegis.core.models import BoundingBox3D

# Horizontal axes of the raw VGGT-Ω world frame (OpenCV-style: X right,
# Y down, Z forward). "Up" is therefore -Y and the floor plane is (X, Z).
_HORIZONTAL_AXES = (0, 2)

# Room-defining landmarks and the room type each one votes for. These are
# architectural / room-level classes, never personal-object memories.
ROOM_LANDMARK_ROOM_TYPES: dict[str, str] = {
    "bed": "Bedroom",
    "wardrobe": "Bedroom",
    "nightstand": "Bedroom",
    "sofa": "Living Room",
    "couch": "Living Room",
    "television": "Living Room",
    "tv": "Living Room",
    "coffee table": "Living Room",
    "refrigerator": "Kitchen",
    "fridge": "Kitchen",
    "kitchen counter": "Kitchen",
    "kitchen island": "Kitchen",
    "stove": "Kitchen",
    "oven": "Kitchen",
    "toilet": "Bathroom",
    "bathtub": "Bathroom",
    "shower": "Bathroom",
    "bathroom sink": "Bathroom",
    "dining table": "Dining Room",
    "door": "Entryway",
    "front door": "Entryway",
    "stairs": "Stairway",
    "staircase": "Stairway",
}


@dataclass
class RoomRegion:
    """A room-level spatial region with a floor-plane footprint."""

    room_id: int
    label: str
    room_type: str
    centroid: tuple[float, float, float]
    footprint: list[tuple[float, float, float]] = field(default_factory=list)
    evidence_labels: list[str] = field(default_factory=list)
    keyframe_count: int = 0
    start_timestamp: float = 0.0
    end_timestamp: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "room_id": self.room_id,
            "label": self.label,
            "room_type": self.room_type,
            "centroid": list(self.centroid),
            "footprint": [list(point) for point in self.footprint],
            "evidence_labels": list(self.evidence_labels),
            "keyframe_count": self.keyframe_count,
            "start_timestamp": self.start_timestamp,
            "end_timestamp": self.end_timestamp,
        }


def normalise_landmark_label(label: str) -> str:
    """Normalise a raw detection label for room-landmark matching."""

    normalized = " ".join(str(label).lower().strip().split())
    if normalized in {"television", "tv"}:
        return "television"
    if normalized in {"sofa", "couch"}:
        return "sofa"
    if normalized in {"refrigerator", "fridge"}:
        return "refrigerator"
    if normalized in {"stairs", "staircase"}:
        return "stairs"
    return normalized


def is_room_landmark_label(label: str) -> bool:
    """Return True when the label is a room-defining landmark class.

    Room landmarks are architectural evidence for room estimation. They are
    intentionally excluded from the object-level memory timeline: a door is
    context for "which room", not an item the patient can misplace.
    """

    return normalise_landmark_label(label) in ROOM_LANDMARK_ROOM_TYPES


def parse_camera_positions(
    camera_poses: Any,
) -> list[tuple[int, float, np.ndarray]]:
    """Parse flexible camera-pose inputs into ordered (frame_id, timestamp, position).

    Accepts a mapping of frame_id -> 4x4 matrix, a sequence of ``Pose``
    records, or a sequence of dicts with ``frame_id``/``matrix`` keys, mirroring
    the pose formats consumed by the scene graph builder.
    """

    raw_items: list[tuple[int, float, Any]] = []
    if camera_poses is None:
        return []
    if isinstance(camera_poses, Mapping):
        for key, value in camera_poses.items():
            matrix = value["matrix"] if isinstance(value, Mapping) else value
            timestamp = (
                float(value.get("timestamp", 0.0))
                if isinstance(value, Mapping)
                else 0.0
            )
            raw_items.append((int(key), timestamp, matrix))
    else:
        for item in camera_poses:
            if hasattr(item, "frame_id"):
                matrix = getattr(item, "matrix", None)
                if matrix is None:
                    continue
                raw_items.append(
                    (int(item.frame_id), float(getattr(item, "timestamp", 0.0)), matrix)
                )
            elif isinstance(item, Mapping) and "frame_id" in item and "matrix" in item:
                raw_items.append(
                    (
                        int(item["frame_id"]),
                        float(item.get("timestamp", 0.0)),
                        item["matrix"],
                    )
                )

    ordered: list[tuple[int, float, np.ndarray]] = []
    for frame_id, timestamp, matrix in raw_items:
        m = np.asarray(matrix, dtype=np.float64)
        if m.shape != (4, 4):
            continue
        ordered.append((frame_id, timestamp, m[:3, 3].copy()))
    ordered.sort(key=lambda item: item[0])
    return ordered


def _horizontal_distance(first: np.ndarray, second: np.ndarray) -> float:
    """Distance on the floor plane (X, Z) of the raw VGGT world frame."""

    dx = float(first[0] - second[0])
    dz = float(first[2] - second[2])
    return float(np.hypot(dx, dz))


def convex_hull_2d(points: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    """Andrew's monotone chain convex hull (counter-clockwise, no SciPy)."""

    unique_points = sorted(set(points))
    if len(unique_points) <= 2:
        return unique_points

    def cross(
        origin: tuple[float, float],
        a: tuple[float, float],
        b: tuple[float, float],
    ) -> float:
        return (a[0] - origin[0]) * (b[1] - origin[1]) - (a[1] - origin[1]) * (
            b[0] - origin[0]
        )

    lower: list[tuple[float, float]] = []
    for point in unique_points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper: list[tuple[float, float]] = []
    for point in reversed(unique_points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def _point_in_footprint(
    point: tuple[float, float], footprint: Sequence[tuple[float, float]]
) -> bool:
    """Inside test for a counter-clockwise convex hull on the floor plane."""

    if len(footprint) < 3:
        return False
    px, pz = point
    for index in range(len(footprint)):
        ax, az = footprint[index]
        bx, bz = footprint[(index + 1) % len(footprint)]
        if (bx - ax) * (pz - az) - (bz - az) * (px - ax) < -1e-9:
            return False
    return True


class _Zone:
    """Internal trajectory cluster: one candidate room zone."""

    __slots__ = ("_sum", "keyframe_ids", "positions", "timestamps")

    def __init__(
        self, position: np.ndarray, keyframe_id: int, timestamp: float
    ) -> None:
        self.positions: list[np.ndarray] = [position]
        self.keyframe_ids: list[int] = [keyframe_id]
        self.timestamps: list[float] = [timestamp]
        self._sum = position.copy()

    def add(self, position: np.ndarray, keyframe_id: int, timestamp: float) -> None:
        self.positions.append(position)
        self.keyframe_ids.append(keyframe_id)
        self.timestamps.append(timestamp)
        self._sum += position

    @property
    def centroid(self) -> np.ndarray:
        return self._sum / len(self.positions)


def extract_room_regions(
    camera_poses: Any,
    boxes_3d: Sequence[BoundingBox3D],
    *,
    zone_link_radius: float = 1.5,
    min_zone_keyframes: int = 3,
) -> list[RoomRegion]:
    """Estimate room regions from the wearer trajectory and room landmarks.

    1. Cluster keyframe camera positions online on the floor plane; a new
       zone starts when the wearer moves further than ``zone_link_radius``
       from every existing zone (doorway crossings create natural splits).
    2. Merge zones whose centroids are within ``zone_link_radius`` so
       revisits to the same room join one region.
    3. Type each zone by majority vote of nearby room-defining landmarks;
       untyped zones fall back to neutral "Room #N" labels.
    """

    if zone_link_radius <= 0:
        raise ValueError("zone_link_radius must be positive")
    if min_zone_keyframes < 1:
        raise ValueError("min_zone_keyframes must be at least 1")

    keyframes = parse_camera_positions(camera_poses)
    if not keyframes:
        return []

    zones: list[_Zone] = []
    for frame_id, timestamp, position in keyframes:
        best_zone: _Zone | None = None
        best_distance = float("inf")
        for zone in zones:
            distance = _horizontal_distance(position, zone.centroid)
            if distance < best_distance:
                best_distance = distance
                best_zone = zone
        if best_zone is not None and best_distance <= zone_link_radius:
            best_zone.add(position, frame_id, timestamp)
        else:
            zones.append(_Zone(position, frame_id, timestamp))

    # Merge revisited zones (single-linkage over zone centroids).
    merge_parent = list(range(len(zones)))

    def _find(index: int) -> int:
        while merge_parent[index] != index:
            merge_parent[index] = merge_parent[merge_parent[index]]
            index = merge_parent[index]
        return index

    for i in range(len(zones)):
        for j in range(i + 1, len(zones)):
            if _horizontal_distance(zones[i].centroid, zones[j].centroid) <= (
                zone_link_radius
            ):
                merge_parent[_find(j)] = _find(i)

    merged: dict[int, _Zone] = {}
    for index, zone in enumerate(zones):
        root = _find(index)
        if root == index:
            merged[root] = zone
        else:
            merged[root].positions.extend(zone.positions)
            merged[root].keyframe_ids.extend(zone.keyframe_ids)
            merged[root].timestamps.extend(zone.timestamps)
            merged[root]._sum = merged[root]._sum + zone._sum

    valid_zones = [
        zone for zone in merged.values() if len(zone.positions) >= min_zone_keyframes
    ]
    if not valid_zones:
        valid_zones = [max(merged.values(), key=lambda zone: len(zone.positions))]

    # Collect landmark evidence votes per zone.
    votes: list[dict[str, int]] = [{} for _ in valid_zones]
    evidence: list[set[str]] = [set() for _ in valid_zones]
    for box in boxes_3d:
        landmark = normalise_landmark_label(box.label)
        if landmark not in ROOM_LANDMARK_ROOM_TYPES:
            continue
        center = np.asarray(box.center, dtype=np.float64)
        best_index = -1
        best_distance = float("inf")
        for zone_index, zone in enumerate(valid_zones):
            distance = _horizontal_distance(center, zone.centroid)
            if distance < best_distance:
                best_distance = distance
                best_index = zone_index
        if best_index >= 0 and best_distance <= max(zone_link_radius, 2.0):
            room_type = ROOM_LANDMARK_ROOM_TYPES[landmark]
            votes[best_index][room_type] = votes[best_index].get(room_type, 0) + 1
            evidence[best_index].add(landmark.title())

    # Deterministic room IDs in temporal order of first observation.
    valid_zones.sort(key=lambda zone: min(zone.timestamps))
    regions: list[RoomRegion] = []
    typed_counts: dict[str, int] = {}
    fallback_index = 0
    for zone_index, zone in enumerate(valid_zones):
        room_id = zone_index + 1
        centroid = np.median(np.asarray(zone.positions), axis=0)
        ordered_positions = [
            (float(position[0]), float(position[2])) for position in zone.positions
        ]
        hull = convex_hull_2d(ordered_positions)
        plane_y = float(np.median([float(position[1]) for position in zone.positions]))
        footprint = [(float(x), plane_y, float(z)) for x, z in hull]

        if votes[zone_index]:
            room_type = min(
                votes[zone_index].items(), key=lambda item: (-item[1], item[0])
            )[0]
            typed_counts[room_type] = typed_counts.get(room_type, 0) + 1
            label = (
                room_type
                if typed_counts[room_type] == 1
                else (f"{room_type} #{typed_counts[room_type]}")
            )
        else:
            fallback_index += 1
            room_type = "Room"
            label = f"Room #{fallback_index}"

        regions.append(
            RoomRegion(
                room_id=room_id,
                label=label,
                room_type=room_type,
                centroid=tuple(float(value) for value in centroid),
                footprint=footprint,
                evidence_labels=sorted(evidence[zone_index]),
                keyframe_count=len(zone.positions),
                start_timestamp=float(min(zone.timestamps)),
                end_timestamp=float(max(zone.timestamps)),
            )
        )
    return regions


def room_for_point(
    point: tuple[float, float, float] | np.ndarray,
    rooms: Sequence[RoomRegion],
    *,
    max_distance: float | None = None,
) -> RoomRegion | None:
    """Assign a 3D point to a room by footprint containment or nearest centroid.

    With ``max_distance=None`` the nearest room is always returned (best-guess
    binding for anchors and the camera wearer). With a finite
    ``max_distance`` far-away points return None instead of a misleading
    binding.
    """

    if not rooms:
        return None
    center = np.asarray(point, dtype=np.float64)
    horizontal = (float(center[0]), float(center[2]))

    for room in rooms:
        footprint = [(point_3d[0], point_3d[2]) for point_3d in room.footprint]
        if _point_in_footprint(horizontal, footprint):
            return room

    best = min(
        rooms,
        key=lambda room: _horizontal_distance(center, np.asarray(room.centroid)),
    )
    if max_distance is None:
        return best
    if _horizontal_distance(center, np.asarray(best.centroid)) <= max_distance:
        return best
    return None


def implicit_room_from_anchors(
    anchor_centers: Sequence[tuple[float, float, float]],
) -> list[RoomRegion]:
    """Fallback single room when no trajectory is available (e.g. static tests).

    Keeps room-grounded answers available for anchor-only memories: with a
    single implicit room every anchor and object resolves into "Room #1"
    rather than an unhelpful None.
    """

    if not anchor_centers:
        return []
    centers = np.asarray(anchor_centers, dtype=np.float64)
    centroid = np.median(centers, axis=0)
    margin = 1.0
    horizontal = [(float(c[0]), float(c[2])) for c in centers]
    min_x = min(x for x, _ in horizontal) - margin
    max_x = max(x for x, _ in horizontal) + margin
    min_z = min(z for _, z in horizontal) - margin
    max_z = max(z for _, z in horizontal) + margin
    footprint = [
        (min_x, float(centroid[1]), min_z),
        (max_x, float(centroid[1]), min_z),
        (max_x, float(centroid[1]), max_z),
        (min_x, float(centroid[1]), max_z),
    ]
    return [
        RoomRegion(
            room_id=1,
            label="Room #1",
            room_type="Room",
            centroid=tuple(float(value) for value in centroid),
            footprint=footprint,
        )
    ]
