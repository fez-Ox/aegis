"""Per-process access to home stores and home-level operations."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from aegis.memory.store import HomeStore, now_iso, open_store, resolve_store_root

_STORES: dict[tuple[str, str], HomeStore] = {}
_LOCK = threading.Lock()


def get_store(home_id: str, store_root: str | Path | None = None) -> HomeStore:
    """One open store per (root, home) per process."""

    root = str(resolve_store_root(store_root))
    key = (root, home_id)
    with _LOCK:
        store = _STORES.get(key)
        if store is None:
            store = open_store(home_id, root)
            _STORES[key] = store
        return store


def close_stores() -> None:
    with _LOCK:
        for store in _STORES.values():
            store.close()
        _STORES.clear()


class DuplicateRoomLabelError(ValueError):
    """Another room of the home already uses this label."""


MAX_ROOM_LABEL = 40


def rename_home_room(store: HomeStore, room_id: int, label: str) -> dict[str, Any]:
    """Caregiver rename of a home room; mirrored to ``home_map.json``.

    Runs, events and objects reference the room id, so nothing else changes.
    A caregiver label is never overwritten by later ingests.
    """

    from aegis.memory.home_registry import export_registry

    clean = " ".join(label.split())
    if not clean or len(clean) > MAX_ROOM_LABEL:
        raise ValueError(f"room label must be 1-{MAX_ROOM_LABEL} characters")
    row = store.one("SELECT * FROM room WHERE room_id = ?", (room_id,))
    if row is None:
        raise KeyError(room_id)
    clash = store.one(
        "SELECT room_id FROM room WHERE lower(label) = lower(?) AND room_id != ?",
        (clean, room_id),
    )
    if clash is not None:
        raise DuplicateRoomLabelError(f"another room is already called {clean!r}")
    store.update(
        "room",
        "room_id",
        room_id,
        {"label": clean, "label_source": "caregiver", "updated_at": now_iso()},
    )
    export_registry(store)
    return dict(store.one("SELECT * FROM room WHERE room_id = ?", (room_id,)))
