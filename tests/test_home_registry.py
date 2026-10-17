"""Unit tests for the per-home room registry and cross-session room matching."""

from __future__ import annotations

from pathlib import Path

from aegis.memory.home_registry import (
    HomeRoomRecord,
    calibrate_from_rooms,
    load_registry,
    match_room_into_registry,
    registry_path,
    save_registry,
)
from aegis.memory.rooms import RoomRegion


def _region(
    room_id: int,
    label: str,
    room_type: str,
    centroid: tuple[float, float, float],
    evidence: list[str] | None = None,
) -> RoomRegion:
    return RoomRegion(
        room_id=room_id,
        label=label,
        room_type=room_type,
        centroid=centroid,
        footprint=[],
        evidence_labels=evidence or [],
    )


def test_registry_roundtrip(tmp_path: Path) -> None:
    registry = load_registry("home01", tmp_path)
    assert registry.rooms == []
    assert registry_path(tmp_path, "home01").name == "home_map.json"

    registry.rooms.append(
        HomeRoomRecord(
            label="Kitchen",
            room_type="Kitchen",
            centroid=(1.0, 0.0, 2.0),
            evidence_labels=["Refrigerator"],
        )
    )
    saved_path = save_registry(registry, tmp_path)
    assert saved_path.exists()

    reloaded = load_registry("home01", tmp_path)
    assert reloaded.rooms[0].label == "Kitchen"
    assert reloaded.rooms[0].evidence_labels == ["Refrigerator"]


def test_corrupt_registry_falls_back_to_empty(tmp_path: Path) -> None:
    path = registry_path(tmp_path, "home01")
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")
    registry = load_registry("home01", tmp_path)
    assert registry.rooms == []


def test_match_by_landmark_evidence_over_distance() -> None:
    registry = load_registry("home01", Path("/tmp/nonexistent"))
    index = match_room_into_registry(
        registry,
        _region(1, "Kitchen", "Kitchen", (0.0, 0.0, 0.0), ["Refrigerator"]),
        session_id="session-a",
    )
    assert index == -1  # Appended as a new record

    # Same room revisited in a later session, slightly moved but with the
    # same semantic evidence -> matches the calibrated record.
    index = match_room_into_registry(
        registry,
        _region(1, "Room #1", "Kitchen", (0.4, 0.0, 0.3), ["Refrigerator"]),
        session_id="session-b",
    )
    assert index == 0
    assert registry.rooms[0].label == "Kitchen"
    assert registry.rooms[0].session_count == 2
    assert registry.rooms[0].last_seen_session == "session-b"


def test_untyped_room_matches_by_proximity() -> None:
    registry = load_registry("home01", Path("/tmp/nonexistent"))
    match_room_into_registry(
        registry,
        _region(1, "Room #1", "Room", (3.0, 0.0, 3.0)),
    )
    index = match_room_into_registry(
        registry,
        _region(1, "Room #1", "Room", (3.4, 0.0, 3.3)),
    )
    assert index == 0

    # A far-away room with no shared evidence becomes a new record.
    index = match_room_into_registry(
        registry,
        _region(2, "Room #2", "Room", (20.0, 0.0, 20.0)),
    )
    assert index == -1
    assert len(registry.rooms) == 2


def test_calibrate_walkthrough_persists(tmp_path: Path) -> None:
    rooms = [
        _region(1, "Kitchen", "Kitchen", (0.0, 0.0, 0.0), ["Refrigerator"]),
        _region(2, "Bedroom", "Bedroom", (8.0, 0.0, 0.0), ["Bed"]),
    ]
    registry = calibrate_from_rooms(
        "home01", rooms, base_dir=tmp_path, session_id="calibration"
    )
    assert len(registry.rooms) == 2

    persisted = load_registry("home01", tmp_path)
    labels = sorted(record.label for record in persisted.rooms)
    assert labels == ["Bedroom", "Kitchen"]
    assert persisted.rooms[0].last_seen_session == "calibration"
