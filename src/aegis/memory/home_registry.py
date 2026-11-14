"""Per-home room registry file (``home_map.json``).

The home store's ``room`` table is the source of truth for room identity.
``home_map.json`` mirrors it after every room change so the calibrated room
names are readable outside the database and can restore an empty store.

Cross-session room *matching* lives in :mod:`aegis.memory.matching`; it is
symbolic because each session has its own coordinate origin.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aegis.core.paths import validate_dataset_id

HOME_MAP_FILENAME = "home_map.json"


@dataclass
class HomeRoomRecord:
    """A room that is stable across recording sessions."""

    room_id: int
    label: str
    room_type: str
    signature: list[str] = field(default_factory=list)
    label_source: str = "auto"
    session_count: int = 1
    last_seen_session: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


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
    if not isinstance(data, Mapping):
        return empty_registry(safe_id)

    rooms: list[HomeRoomRecord] = []
    for index, room in enumerate(data.get("rooms", []), start=1):
        if not isinstance(room, Mapping):
            continue
        source = str(room.get("label_source", "auto"))
        rooms.append(
            HomeRoomRecord(
                room_id=int(room.get("room_id", index)),
                label=str(room.get("label", "Room")),
                room_type=str(room.get("room_type", "Room")),
                signature=sorted(
                    str(item)
                    for item in room.get("signature", room.get("evidence_labels", []))
                ),
                label_source=source if source in {"auto", "caregiver"} else "auto",
                session_count=int(room.get("session_count", 1)),
                last_seen_session=str(room.get("last_seen_session", "")),
            )
        )
    return HomeRoomRegistry(
        home_id=safe_id, rooms=rooms, updated_at=str(data.get("updated_at", ""))
    )


def registry_records(registry: HomeRoomRegistry) -> list[dict[str, Any]]:
    """JSON-safe list of registry records (for API responses)."""

    return [record.as_dict() for record in registry.rooms]


# ------------------------------------------------------- store integration
def registry_from_store(store: Any) -> HomeRoomRegistry:
    registry = empty_registry(store.home_id)
    for row in store.rooms():
        registry.rooms.append(
            HomeRoomRecord(
                room_id=int(row["room_id"]),
                label=row["label"],
                room_type=row["room_type"],
                signature=sorted(json.loads(row["signature"])),
                label_source=row["label_source"],
                session_count=int(row["session_count"]),
                last_seen_session=row["last_seen_session"] or "",
            )
        )
    return registry


def export_registry(store: Any) -> Path:
    """Write ``home_map.json`` next to the store from its room table."""

    return save_registry(registry_from_store(store), store.dir.parent)


def seed_store_from_registry(store: Any, registry: HomeRoomRegistry) -> int:
    """Restore rooms into an empty store from a registry; returns rooms added."""

    if store.rooms() or not registry.rooms:
        return 0
    from aegis.memory.store import dumps, now_iso

    stamp = now_iso()
    with store.transaction():
        for record in registry.rooms:
            store.insert(
                "room",
                {
                    "room_id": record.room_id,
                    "label": record.label,
                    "room_type": record.room_type,
                    "label_source": record.label_source,
                    "signature": dumps(sorted(record.signature)),
                    "session_count": record.session_count,
                    "last_seen_session": record.last_seen_session or None,
                    "created_at": stamp,
                    "updated_at": stamp,
                },
            )
    return len(registry.rooms)
