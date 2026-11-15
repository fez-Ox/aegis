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
from aegis.core.vocabulary import Vocabulary, default_vocabulary
from aegis.geometry.gravity import GravityFrame
from aegis.geometry.planar import convex_hull, point_in_convex

# The floor plane comes from the session gravity frame. Without one, the
# legacy assumption applies: up is -Y and the floor plane is (X, Z).


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


def is_room_landmark_label(label: str, vocabulary: Vocabulary | None = None) -> bool:
    """Return True when the label is a room landmark (door, window, stairs, ...).

    Room landmarks are architectural evidence for room estimation only. They
    are never anchors and never personal-object memories: a door is context
    for "which room", not an item the patient can misplace. Furniture such as
    a bed is an *anchor* that also votes for the room type.
    """

    vocab = vocabulary or default_vocabulary()
    return vocab.role(label) == "landmark"


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


def _horizontal_distance(
    first: np.ndarray, second: np.ndarray, gravity: GravityFrame | None = None
) -> float:
    """Distance between two points projected onto the floor plane."""

    frame = gravity or GravityFrame.assumed()
    a1, a2 = frame.horizontal(first)
    b1, b2 = frame.horizontal(second)
    return float(np.hypot(a1 - b1, a2 - b2))


def convex_hull_2d(points: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    """Counter-clockwise convex hull (kept for backward compatibility)."""

    return convex_hull(points)


def _point_in_footprint(
    point: tuple[float, float], footprint: Sequence[tuple[float, float]]
) -> bool:
    return point_in_convex(point, footprint)


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
    vocabulary: Vocabulary | None = None,
    gravity: GravityFrame | None = None,
    unit: float = 1.0,
) -> list[RoomRegion]:
    """Estimate room regions from the wearer trajectory and room landmarks.

    1. Cluster keyframe camera positions online on the floor plane; a new
       zone starts when the wearer moves further than ``zone_link_radius``
       from every existing zone (doorway crossings create natural splits).
    2. Merge zones whose centroids are within ``zone_link_radius`` so
       revisits to the same room join one region.
    3. Type each zone by majority vote of nearby labels that carry a
       ``room_type`` in the vocabulary (landmarks and typed anchors such as a
       bed); untyped zones fall back to neutral "Room #N" labels.
    """

    vocab = vocabulary or default_vocabulary()
    frame = gravity or GravityFrame.assumed()
    link_radius = zone_link_radius * unit
    frame = gravity or GravityFrame.assumed()
    link_radius = zone_link_radius * unit

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
            distance = _horizontal_distance(position, zone.centroid, frame)
            if distance < best_distance:
                best_distance = distance
                best_zone = zone
        if best_zone is not None and best_distance <= link_radius:
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
            if _horizontal_distance(zones[i].centroid, zones[j].centroid, frame) <= (
                link_radius
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
        entry = vocab.entry(box.label)
        if entry.room_type is None or entry.role not in {"landmark", "anchor"}:
            continue
        center = np.asarray(box.center, dtype=np.float64)
        best_index = -1
        best_distance = float("inf")
        for zone_index, zone in enumerate(valid_zones):
            distance = _horizontal_distance(center, zone.centroid, frame)
            if distance < best_distance:
                best_distance = distance
                best_index = zone_index
        if best_index >= 0 and best_distance <= max(link_radius, 2.0 * unit):
            room_type = entry.room_type
            votes[best_index][room_type] = votes[best_index].get(room_type, 0) + 1
            evidence[best_index].add(entry.display)

    # Deterministic room IDs in temporal order of first observation.
    valid_zones.sort(key=lambda zone: min(zone.timestamps))
    regions: list[RoomRegion] = []
    typed_counts: dict[str, int] = {}
    fallback_index = 0
    for zone_index, zone in enumerate(valid_zones):
        room_id = zone_index + 1
        centroid = np.median(np.asarray(zone.positions), axis=0)
        hull = convex_hull([frame.horizontal(position) for position in zone.positions])
        plane = float(np.median([frame.elevation(p) for p in zone.positions]))
        footprint = [
            tuple(float(v) for v in frame.from_horizontal(h1, h2, plane))
            for h1, h2 in hull
        ]

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
    gravity: GravityFrame | None = None,
) -> RoomRegion | None:
    """Assign a 3D point to a room by footprint containment or nearest centroid.

    With ``max_distance=None`` the nearest room is always returned (best-guess
    binding for anchors and the camera wearer). With a finite
    ``max_distance`` far-away points return None instead of a misleading
    binding.
    """

    if not rooms:
        return None
    frame = gravity or GravityFrame.assumed()
    center = np.asarray(point, dtype=np.float64)
    horizontal = frame.horizontal(center)

    for room in rooms:
        footprint = [frame.horizontal(point_3d) for point_3d in room.footprint]
        if point_in_convex(horizontal, footprint):
            return room

    best = min(
        rooms,
        key=lambda room: _horizontal_distance(center, np.asarray(room.centroid), frame),
    )
    if max_distance is None:
        return best
    if _horizontal_distance(center, np.asarray(best.centroid), frame) <= max_distance:
        return best
    return None


def implicit_room_from_anchors(
    anchor_centers: Sequence[tuple[float, float, float]],
    *,
    gravity: GravityFrame | None = None,
    unit: float = 1.0,
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
    frame = gravity or GravityFrame.assumed()
    margin = 1.0 * unit
    horizontal = [frame.horizontal(c) for c in centers]
    min_1 = min(h for h, _ in horizontal) - margin
    max_1 = max(h for h, _ in horizontal) + margin
    min_2 = min(h for _, h in horizontal) - margin
    max_2 = max(h for _, h in horizontal) + margin
    plane = frame.elevation(centroid)
    footprint = [
        tuple(float(v) for v in frame.from_horizontal(h1, h2, plane))
        for h1, h2 in ((min_1, min_2), (max_1, min_2), (max_1, max_2), (min_1, max_2))
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
