"""Per-home room identity: caregiver names persist (FR3.6, FR3.7, AC-31)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from aegis.memory.homes import close_stores
from aegis.memory.ingest import ingest_session
from aegis.memory.store import open_store
from aegis.remote.api import app
from tests._graphs import make_session_graph

ROOMS = [
    {
        "room_id": 1,
        "label": "Bedroom",
        "room_type": "Bedroom",
        "evidence_labels": ["Bed"],
    },
    {
        "room_id": 2,
        "label": "Kitchen",
        "room_type": "Kitchen",
        "evidence_labels": ["Refrigerator"],
    },
]
ANCHORS = [
    {"anchor_id": 1, "canonical": "bed", "room_id": 1},
    {"anchor_id": 2, "canonical": "refrigerator", "room_id": 2},
]


def _graph(
    name: str, start: str, relation: str = "on_surface", anchor: int = 1, room: int = 1
):
    return make_session_graph(
        name,
        start,
        rooms=ROOMS,
        anchors=ANCHORS,
        objects=[
            {
                "instance_id": 1,
                "canonical": "glasses",
                "runs": [(relation, anchor, room, 1.0, 9.0, 3)],
            }
        ],
    )


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AEGIS_STORE_ROOT", str(tmp_path))
    store = open_store("homeA", tmp_path)
    ingest_session(store, _graph("s1", "2026-11-15T08:00:00Z"))
    store.close()
    yield TestClient(app)
    close_stores()


def _room_id(client, label: str) -> int:
    rooms = client.get("/api/v1/rooms?home_id=homeA").json()
    return next(r["room_id"] for r in rooms if r["label"] == label)


def test_rename_writes_home_map_json(client, tmp_path) -> None:
    room_id = _room_id(client, "Bedroom")
    res = client.post(
        f"/api/v1/rooms/rename?home_id=homeA&room_id={room_id}&label=Mum's room"
    )
    assert res.status_code == 200
    data = json.loads((tmp_path / "homeA" / "home_map.json").read_text())
    record = next(r for r in data["rooms"] if r["room_id"] == room_id)
    assert record["label"] == "Mum's room"
    assert record["label_source"] == "caregiver"


def test_rename_survives_restart_and_new_session(client, tmp_path) -> None:
    room_id = _room_id(client, "Bedroom")
    client.post(
        f"/api/v1/rooms/rename?home_id=homeA&room_id={room_id}&label=Mum's room"
    )
    close_stores()

    store = open_store("homeA", tmp_path)
    ingest_session(store, _graph("s2", "2026-11-15T09:00:00Z"))
    assert [r["label"] for r in store.rooms()] == ["Mum's room", "Kitchen"]
    runs = store.query("SELECT DISTINCT room_id FROM state_run")
    assert [r[0] for r in runs] == [room_id]
    store.close()

    answer = client.get("/api/v1/query?item=glasses&home_id=homeA").json()
    assert answer["room_label"] == "Mum's room"
    assert "in the Mum's room" in answer["location_summary"]


def test_rename_unknown_room_is_404(client) -> None:
    assert (
        client.post("/api/v1/rooms/rename?home_id=homeA&room_id=99&label=X").status_code
        == 404
    )


def test_rename_duplicate_label_is_409(client) -> None:
    room_id = _room_id(client, "Bedroom")
    res = client.post(
        f"/api/v1/rooms/rename?home_id=homeA&room_id={room_id}&label=kitchen"
    )
    assert res.status_code == 409


def test_corrupt_home_map_is_ignored_and_rewritten(client, tmp_path) -> None:
    path = tmp_path / "homeA" / "home_map.json"
    path.write_text("{oops")
    room_id = _room_id(client, "Kitchen")
    assert (
        client.post(
            f"/api/v1/rooms/rename?home_id=homeA&room_id={room_id}&label=Pantry"
        ).status_code
        == 200
    )
    assert json.loads(path.read_text())["rooms"][1]["label"] == "Pantry"


def test_rename_survives_reingest_of_same_session(client, tmp_path) -> None:
    room_id = _room_id(client, "Bedroom")
    client.post(
        f"/api/v1/rooms/rename?home_id=homeA&room_id={room_id}&label=Guest room"
    )
    close_stores()
    store = open_store("homeA", tmp_path)
    changed = _graph("s1", "2026-11-15T08:00:00Z", relation="under")
    assert ingest_session(store, changed).status == "replaced"
    assert store.rooms()[0]["label"] == "Guest room"
    store.close()
