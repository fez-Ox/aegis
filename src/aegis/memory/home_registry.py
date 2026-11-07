"""Per-home room registry for calibration and cross-session persistence.

A patient's home is calibrated once (caregiver walks the patient through the
rooms, then names them via ``POST /api/v1/rooms/rename``). The named rooms are
persisted in ``home_map.json`` on the data volume per ``home_id`` so later
sessions can match their freshly estimated ``RoomRegion`` set onto the
patient's stable room identity instead of inventing new "Room #N" labels each
session.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aegis.core.paths import validate_dataset_id
from aegis.memory.rooms import RoomRegion

HOME_MAP_FILENAME = "home_map.json"


@dataclass
class HomeRoomRecord:
    """A caregiver-named room that is stable across recording sessions."""

    label: str
    room_type: str
    centroid: tuple[float, float, float]
    evidence_labels: list[str] = field(default_factory=list)
    session_count: int = 1
    last_seen_session: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "room_type": self.room_type,
            "centroid": list(self.centroid),
            "evidence_labels": list(self.evidence_labels),
            "session_count": self.session_count,
            "last_seen_session": self.last_seen_session,
        }


@dataclass
class HomeRoomRegistry:
    """The persisted room identity map of one patient's home."""

    home_id: str
    rooms: list[HomeRoomRecord] = field(default_factory=list)
    updated_at: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "home_id": self.home_id,
            "rooms": [room.as_dict() for room in self.rooms],
            "updated_at": self.updated_at,
        }


def empty_registry(home_id: str) -> HomeRoomRegistry:
    return HomeRoomRegistry(home_id=validate_dataset_id(home_id))


def registry_path(base_dir: str | Path, home_id: str) -> Path:
    """Canonical path of ``<base_dir>/<home_id>/home_map.json``."""

    return Path(base_dir) / validate_dataset_id(home_id) / HOME_MAP_FILENAME


def save_registry(registry: HomeRoomRegistry, base_dir: str | Path) -> Path:
    """Persist the registry atomically and return the written path."""

    path = registry_path(base_dir, registry.home_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    registry.updated_at = datetime.now(UTC).isoformat()
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(registry.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return path


def load_registry(home_id: str, base_dir: str | Path) -> HomeRoomRegistry:
    """Load a home registry; a missing or unreadable map yields an empty one."""

    path = registry_path(base_dir, home_id)
    safe_id = validate_dataset_id(home_id)
    if not path.is_file():
        return empty_registry(safe_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_registry(safe_id)

    rooms = [
        HomeRoomRecord(
            label=str(room.get("label", "Room")),
            room_type=str(room.get("room_type", "Room")),
            centroid=tuple(float(c) for c in room.get("centroid", (0.0, 0.0, 0.0))),
            evidence_labels=[str(label) for label in room.get("evidence_labels", [])],
            session_count=int(room.get("session_count", 1)),
            last_seen_session=str(room.get("last_seen_session", "")),
        )
        for room in data.get("rooms", [])
        if isinstance(room, Mapping)
    ]
    return HomeRoomRegistry(
        home_id=safe_id, rooms=rooms, updated_at=str(data.get("updated_at", ""))
    )


def _bev_distance(first: Sequence[float], second: Sequence[float]) -> float:
    return float(((first[0] - second[0]) ** 2 + (first[2] - second[2]) ** 2) ** 0.5)


def match_room_into_registry(
    registry: HomeRoomRegistry,
    room: RoomRegion,
    *,
    session_id: str = "",
    distance_threshold: float = 2.5,
) -> int:
    """Match a freshly estimated room into the registry, or register it as new.

    Matching prefers landmark-evidence overlap (the room's semantic signature)
    and falls back to floor-plane proximity of the centroids. Returns the index
    of the matched registry room, or -1 when a new record was appended.
    """

    best_index = -1
    best_score = float("-inf")
    for index, record in enumerate(registry.rooms):
        evidence_overlap = len(set(record.evidence_labels) & set(room.evidence_labels))
        distance = _bev_distance(record.centroid, room.centroid)
        # Landmarks dominate; proximity only breaks ties between bare rooms.
        score = evidence_overlap * 10.0 - distance
        if distance <= distance_threshold and score > best_score:
            best_score = score
            best_index = index

    centroid = tuple(float(value) for value in room.centroid)
    if best_index >= 0:
        record = registry.rooms[best_index]
        record.session_count += 1
        if session_id:
            record.last_seen_session = session_id
        # Slow-moving centroid keeps the map aligned with furniture moves.
        blended = [
            0.8 * old + 0.2 * new
            for old, new in zip(record.centroid, centroid, strict=True)
        ]
        record.centroid = (blended[0], blended[1], blended[2])
        if room.evidence_labels and not record.evidence_labels:
            record.evidence_labels = sorted(room.evidence_labels)
        return best_index

    registry.rooms.append(
        HomeRoomRecord(
            label=room.label,
            room_type=room.room_type,
            centroid=centroid,
            evidence_labels=list(room.evidence_labels),
            session_count=1,
            last_seen_session=session_id,
        )
    )
    return -1


def calibrate_from_rooms(
    home_id: str,
    rooms: Sequence[RoomRegion],
    *,
    base_dir: str | Path,
    session_id: str = "",
) -> HomeRoomRegistry:
    """Register every room observed during a calibration walkthrough."""

    registry = empty_registry(home_id)
    for room in rooms:
        match_room_into_registry(registry, room, session_id=session_id)
    save_registry(registry, base_dir)
    return registry


def registry_records(registry: HomeRoomRegistry) -> list[dict[str, Any]]:
    """JSON-safe list of registry records (for API responses)."""

    return [
        asdict(record) | {"centroid": list(record.centroid)}
        for record in registry.rooms
    ]
