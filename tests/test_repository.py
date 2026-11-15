"""Tests for the JSON graph repository."""

from __future__ import annotations

import json

from aegis.memory.repository import clear_cache, get_repository


def test_v1_and_v2_graphs_give_latest_states(tmp_path) -> None:
    v1 = tmp_path / "v1.json"
    v1.write_text(
        json.dumps(
            {
                "timeline": {
                    "2": [{"instance_id": 1, "label": "Keys #1", "relation": "inside"}],
                    "10": [
                        {"instance_id": 1, "label": "Keys #1", "relation": "on_surface"}
                    ],
                }
            }
        )
    )
    v2 = tmp_path / "v2.json"
    v2.write_text(
        json.dumps(
            {
                "latest_states": [
                    {"instance_id": 1, "label": "Keys #1", "relation": "on_surface"}
                ]
            }
        )
    )
    clear_cache()
    assert get_repository("a", [v1]).latest_states()[1]["relation"] == "on_surface"
    assert get_repository("b", [v2]).latest_states()[1]["relation"] == "on_surface"


def test_corrupt_graph_is_not_cached(tmp_path) -> None:
    path = tmp_path / "g.json"
    path.write_text("{oops")
    clear_cache()
    assert get_repository("c", [path]).ready is False
    path.write_text(json.dumps({"latest_states": []}))
    assert get_repository("c", [path]).ready is True


def test_graph_of_another_dataset_is_ignored(tmp_path) -> None:
    path = tmp_path / "g.json"
    path.write_text(json.dumps({"dataset_id": "other", "latest_states": []}))
    clear_cache()
    assert get_repository("mine", [path]).ready is False


def test_json_graph_survives_restart(tmp_path) -> None:
    from fastapi.testclient import TestClient

    from aegis.remote.api import app

    client = TestClient(app)
    before = client.get("/api/v1/query?item=cooking pot&dataset_id=demo03").json()
    timeline_before = client.get("/api/v1/timeline?dataset_id=demo03").json()
    clear_cache()  # what a process restart loses
    after = client.get("/api/v1/query?item=cooking pot&dataset_id=demo03").json()
    assert after == before
    assert client.get("/api/v1/timeline?dataset_id=demo03").json() == timeline_before
