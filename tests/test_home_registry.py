"""Tests for the home_map.json room registry mirror."""

from __future__ import annotations

from pathlib import Path

from aegis.memory.home_registry import (
    HomeRoomRecord,
    HomeRoomRegistry,
    export_registry,
    load_registry,
    registry_path,
    save_registry,
    seed_store_from_registry,
)
from aegis.memory.ingest import ingest_session
from aegis.memory.store import open_store
from tests._graphs import make_session_graph


def test_registry_roundtrip(tmp_path: Path) -> None:
    registry = HomeRoomRegistry(
        home_id="home01",
        rooms=[
            HomeRoomRecord(
                room_id=3,
                label="Mum's Kitchen",
                room_type="Kitchen",
                signature=["Refrigerator"],
                label_source="caregiver",
            )
        ],
    )
    path = save_registry(registry, tmp_path)
    assert path == registry_path(tmp_path, "home01")
    loaded = load_registry("home01", tmp_path)
    assert loaded.rooms == registry.rooms
    assert loaded.updated_at


def test_corrupt_registry_falls_back_to_empty(tmp_path: Path) -> None:
    path = registry_path(tmp_path, "home01")
    path.parent.mkdir(parents=True)
    path.write_text("{broken")
    assert load_registry("home01", tmp_path).rooms == []


def test_export_matches_room_table(tmp_path: Path) -> None:
    store = open_store("home01", tmp_path)
    ingest_session(store, make_session_graph("s1"))
    path = export_registry(store)
    registry = load_registry("home01", tmp_path)
    assert path.exists()
    assert [(r.room_id, r.label) for r in registry.rooms] == [
        (row["room_id"], row["label"]) for row in store.rooms()
    ]
    store.close()


def test_seed_store_from_registry(tmp_path: Path) -> None:
    registry = HomeRoomRegistry(
        home_id="home01",
        rooms=[
            HomeRoomRecord(
                room_id=4, label="Study", room_type="Room", label_source="caregiver"
            )
        ],
    )
    save_registry(registry, tmp_path)
    store = open_store("home01", tmp_path)  # empty store seeds itself
    rows = store.rooms()
    assert [(r["room_id"], r["label"], r["label_source"]) for r in rows] == [
        (4, "Study", "caregiver")
    ]
    assert seed_store_from_registry(store, registry) == 0  # not twice
    store.close()
