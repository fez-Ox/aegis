"""AC-06: memory answers are identical before and after a restart."""

from __future__ import annotations

from fastapi.testclient import TestClient

from aegis.memory.homes import close_stores
from aegis.memory.ingest import ingest_session
from aegis.memory.store import open_store
from aegis.remote.api import app
from tests._graphs import make_session_graph

ROOMS = [
    {
        "room_id": 1,
        "label": "Kitchen",
        "room_type": "Kitchen",
        "evidence_labels": ["Refrigerator"],
    }
]
ANCHORS = [
    {"anchor_id": 1, "canonical": "refrigerator"},
    {"anchor_id": 2, "canonical": "kitchen counter"},
]


def _seed(root) -> None:
    store = open_store("homeR", root)
    ingest_session(
        store,
        make_session_graph(
            "r1",
            "2026-11-15T08:00:00Z",
            rooms=ROOMS,
            anchors=ANCHORS,
            objects=[
                {
                    "instance_id": 1,
                    "canonical": "keys",
                    "runs": [("on_surface", 2, 1, 1.0, 9.0, 3)],
                },
                {
                    "instance_id": 2,
                    "canonical": "mug",
                    "runs": [("inside", 1, 1, 1.0, 9.0, 3)],
                },
            ],
        ),
    )
    ingest_session(
        store,
        make_session_graph(
            "r2",
            "2026-11-15T09:00:00Z",
            rooms=ROOMS,
            anchors=ANCHORS,
            objects=[
                {
                    "instance_id": 1,
                    "canonical": "keys",
                    "runs": [("inside", 1, 1, 1.0, 9.0, 3)],
                },
            ],
        ),
    )
    store.close()


def _snapshot(client: TestClient) -> dict:
    return {
        item: client.get(f"/api/v1/query?item={item}&home_id=homeR").json()
        for item in ("keys", "mug", "glasses")
    } | {"timeline": client.get("/api/v1/timeline?home_id=homeR").json()}


def test_store_survives_restart(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AEGIS_STORE_ROOT", str(tmp_path))
    _seed(tmp_path)
    client = TestClient(app)
    before = _snapshot(client)
    assert before["keys"]["found"] is True
    assert before["keys"]["anchor_label"] == "Refrigerator #1"
    assert before["keys"]["location_summary"] == (
        "Your keys were last seen inside Refrigerator #1 in the Kitchen."
    )
    assert before["glasses"]["found"] is False
    close_stores()  # what a process restart loses
    after = _snapshot(TestClient(app))
    assert after == before
    close_stores()


def test_invalid_home_id_is_rejected() -> None:
    client = TestClient(app)
    assert client.get("/api/v1/query?item=keys&home_id=../x").status_code == 400


def test_builder_output_ingests_end_to_end(tmp_path) -> None:
    from aegis.core.models import BoundingBox3D
    from aegis.memory.scene_graph import build_relative_4d_scene_graph

    def box(frame_id, label, center, track_id):
        return BoundingBox3D(
            frame_id=frame_id,
            timestamp=float(frame_id),
            track_id=track_id,
            label=label,
            confidence=0.9,
            center=center,
            size=(0.4, 0.4, 0.4),
            bbox_2d=(0.0, 0.0, 1.0, 1.0),
            yaw=0.0,
        )

    boxes = [box(f, "desk", (0.0, 0.5, 2.0), 1) for f in (1, 2)]
    boxes += [box(f, "keys", (0.0, 0.2, 2.0), 2) for f in (1, 2)]
    graph = build_relative_4d_scene_graph(
        boxes,
        [1, 2],
        [1.0, 2.0],
        wallclock_by_frame={1: "2026-11-15T09:00:01Z", 2: "2026-11-15T09:00:02Z"},
    )
    data = graph.as_dict()
    data["session"]["dataset_id"] = "e2e"
    store = open_store("homeE", tmp_path)
    report = ingest_session(store, data)
    assert report.instances_created == 1
    state = store.latest_states()[0]
    assert state["label"] == "Keys #1"
    assert state["anchor_label"] == "Desk #1"
    store.close()
