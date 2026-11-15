"""Tests for object-only evidence crops (A11)."""

from __future__ import annotations

import cv2
import numpy as np
from fastapi.testclient import TestClient

from aegis.core.config import RuntimeConfig
from aegis.memory.evidence import crop_box, write_run_crops
from aegis.memory.homes import close_stores
from aegis.memory.ingest import ingest_session
from aegis.memory.store import open_store
from aegis.remote.api import app
from tests._graphs import make_session_graph


def _frame(tmp_path, name="frame_000001.png", colour=(0, 0, 255)):
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    image[100:300, 200:400] = colour
    cv2.imwrite(str(tmp_path / name), image)
    return name


def _run(**kwargs):
    run = {
        "instance_id": 1,
        "relation": "on_surface",
        "start_frame": 1,
        "best_frame": 1,
        "best_bbox_2d": [200.0, 100.0, 400.0, 300.0],
    }
    run.update(kwargs)
    return run


def test_crop_is_clipped_padded_and_resized(tmp_path) -> None:
    assert crop_box(640, 480, (600, 450, 700, 500), 0.15) == (585, 442, 640, 480)
    name = _frame(tmp_path)
    runs = [_run()]
    assert (
        write_run_crops(runs, tmp_path, {1: name}, tmp_path / "evidence", max_side=100)
        == 1
    )
    meta = runs[0]["evidence"]
    assert meta["path"] == "evidence/run_1_1.jpg"
    crop = cv2.imread(str(tmp_path / meta["path"]))
    assert max(crop.shape[:2]) == 100
    centre = crop[crop.shape[0] // 2, crop.shape[1] // 2]
    assert centre[2] > 200 and centre[0] < 60  # red object, not background


def test_missing_frame_gives_none_not_error(tmp_path) -> None:
    runs = [_run()]
    assert write_run_crops(runs, tmp_path, {1: "missing.png"}, tmp_path / "e") == 0
    assert runs[0]["evidence"] is None


def test_carried_runs_have_no_crop(tmp_path) -> None:
    name = _frame(tmp_path)
    runs = [_run(relation="carried_by_user")]
    assert write_run_crops(runs, tmp_path, {1: name}, tmp_path / "e") == 0
    assert runs[0]["evidence"] is None


def _graph_with_crop(tmp_path, session, start, size):
    folder = tmp_path / session
    (folder / "evidence").mkdir(parents=True)
    image = np.random.default_rng(size).integers(
        0, 255, size=(size, size, 3), dtype=np.uint8
    )
    cv2.imwrite(str(folder / "evidence" / "run_1_1.jpg"), image)
    graph = make_session_graph(
        session,
        start,
        anchors=[{"anchor_id": 1, "canonical": "desk"}],
        objects=[
            {
                "instance_id": 1,
                "canonical": "keys",
                "runs": [("on_surface", 1, 1, 1.0, 9.0, 3)],
            }
        ],
    )
    graph["state_runs"][0]["evidence"] = {
        "path": "evidence/run_1_1.jpg",
        "frame_id": 1,
        "width": size,
        "height": size,
    }
    return graph, folder


def test_ingest_copies_crop_and_links_it(tmp_path, monkeypatch) -> None:
    root = tmp_path / "homes"
    graph, folder = _graph_with_crop(tmp_path, "s1", "2026-11-15T09:00:00Z", 64)
    store = open_store("homeV", root)
    ingest_session(store, graph, evidence_root=folder)
    state = store.latest_states()[0]
    row = store.one(
        "SELECT * FROM evidence WHERE evidence_id = ?", (state["evidence_id"],)
    )
    assert row["path"] == "evidence/s1/run_1_1.jpg"
    assert (store.dir / row["path"]).is_file()
    store.close()

    monkeypatch.setenv("AEGIS_STORE_ROOT", str(root))
    client = TestClient(app)
    res = client.get("/api/v1/crops/1?home_id=homeV")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/jpeg"
    query = client.get("/api/v1/query?item=keys&home_id=homeV").json()
    assert query["crop_url"] == "/api/v1/crops/1?home_id=homeV"
    assert client.get("/api/v1/crops/99?home_id=homeV").status_code == 404
    close_stores()


def test_extended_run_keeps_better_crop(tmp_path) -> None:
    root = tmp_path / "homes"
    store = open_store("homeV", root)
    first, folder1 = _graph_with_crop(tmp_path, "s1", "2026-11-15T09:00:00Z", 32)
    ingest_session(store, first, evidence_root=folder1)
    second, folder2 = _graph_with_crop(tmp_path, "s2", "2026-11-15T10:00:00Z", 128)
    ingest_session(store, second, evidence_root=folder2)
    assert store.counts()["state_run"] == 1
    rows = store.query("SELECT * FROM evidence")
    assert len(rows) == 1
    assert rows[0]["path"] == "evidence/s2/run_1_1.jpg"
    assert rows[0]["session_id"] == "s1"  # owned by the run's session
    assert not (store.dir / "evidence/s1/run_1_1.jpg").exists()
    third, folder3 = _graph_with_crop(tmp_path, "s3", "2026-11-15T11:00:00Z", 8)
    ingest_session(store, third, evidence_root=folder3)
    assert (
        store.query("SELECT path FROM evidence")[0]["path"] == "evidence/s2/run_1_1.jpg"
    )
    store.close()


def test_query_without_evidence_has_no_crop_url(tmp_path, monkeypatch) -> None:
    root = tmp_path / "homes"
    store = open_store("homeN", root)
    ingest_session(
        store,
        make_session_graph(
            "s1",
            objects=[
                {
                    "instance_id": 1,
                    "canonical": "keys",
                    "runs": [("in_room", None, 1, 1.0, 9.0, 3)],
                }
            ],
        ),
    )
    store.close()
    monkeypatch.setenv("AEGIS_STORE_ROOT", str(root))
    answer = TestClient(app).get("/api/v1/query?item=keys&home_id=homeN").json()
    assert answer["found"] is True
    assert answer["crop_url"] is None
    close_stores()


def test_disabled_flag_is_configurable() -> None:
    config = RuntimeConfig.from_mapping({"memory": {"evidence": {"enabled": False}}})
    assert config.memory.evidence.enabled is False
