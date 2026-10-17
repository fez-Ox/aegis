"""Unit and integration tests for the Aegis FastAPI gateway."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from aegis.remote.api import app

client = TestClient(app)


def test_health_endpoint() -> None:
    """Test health check returns status ok and loaded scene graph metadata."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"
    assert data["num_anchors"] >= 1
    assert data["num_events"] >= 1


def test_anchors_endpoint() -> None:
    """Test anchors endpoint returns spatial anchors with contained objects."""
    response = client.get("/api/v1/anchors")
    assert response.status_code == 200
    anchors = response.json()
    assert isinstance(anchors, list)
    assert len(anchors) >= 1
    cabinet = anchors[0]
    assert "Storage Cabinet" in cabinet["label"]
    assert len(cabinet["center"]) == 3
    assert len(cabinet["size"]) == 3
    assert "Shoes #1 [Active Pair]" in cabinet["contained_objects"]


def test_query_shoes_endpoint() -> None:
    """Test memory query for shoes returns accurate 3D anchor and plain-English summary."""
    response = client.get("/api/v1/query?item=shoes")
    assert response.status_code == 200
    res = response.json()
    assert res["found"] is True
    assert "Shoes #1" in res["instance_label"]
    assert res["relation"] == "inside"
    assert "Storage Cabinet #1" in res["anchor_label"]
    assert "Storage Cabinet #1" in res["location_summary"]
    assert "inside" in res["location_summary"].lower()
    assert res["crop_url"] is not None
    assert (
        res["is_persistent_memory"] is True
    )  # In frame 642, shoes are occluded / stored


def test_query_unfound_item() -> None:
    """Test querying an unobserved object returns clear not-found explanation without error."""
    response = client.get("/api/v1/query?item=wallet")
    assert response.status_code == 200
    res = response.json()
    assert res["found"] is False
    assert "wallet" in res["location_summary"]


def test_timeline_endpoint() -> None:
    """Test timeline endpoint returns chronological events with plain-language summaries."""
    response = client.get("/api/v1/timeline")
    assert response.status_code == 200
    events = response.json()
    assert isinstance(events, list)
    assert len(events) >= 1
    first_ev = events[0]
    assert "event_id" in first_ev
    assert "Shoes #1" in first_ev["object"]
    assert "summary" in first_ev


def test_crops_endpoint() -> None:
    """Test crop endpoint returns image content with valid headers."""
    response = client.get("/api/v1/crops/1")
    assert response.status_code == 200
    assert "image/svg+xml" in response.headers["content-type"]
    assert "Shoes #1" in response.text


def test_query_latency_performance_claim() -> None:
    """Test AC-03: Memory query latency is well under 500ms target."""
    start_time = time.perf_counter()
    response = client.get("/api/v1/query?item=shoes")
    duration = time.perf_counter() - start_time
    assert response.status_code == 200
    # Strict validation of Acceptance Criteria AC-03
    assert duration < 0.500, (
        f"Query took {duration * 1000:.1f}ms, exceeding 500ms limit"
    )


def test_query_bottle_occlusion_endpoint() -> None:
    """Test a dataset-scoped bottle query returns Demo06 3D location."""
    response = client.get("/api/v1/query?item=water bottle&dataset_id=Demo06-Self")
    assert response.status_code == 200
    res = response.json()
    assert res["found"] is True
    assert "Bottle #1" in res["instance_label"]
    assert res["relation"] == "on_surface"
    assert "Desk" in res["anchor_label"]
    assert "bottle" in res["location_summary"].lower()


def test_simulate_bottle_occlusion() -> None:
    """Test simulating bottle occlusion updates state to persistent memory."""
    response = client.get("/api/v1/simulate/bottle_occluded")
    assert response.status_code == 200
    res = response.json()
    assert res["status"] == "ok"
    assert res["is_persistent_memory"] is True
    assert "Desk #1" in res["anchor_label"]

    # Verify query reflects occlusion persistence
    q_res = client.get("/api/v1/query?item=bottle&dataset_id=Demo06-Self").json()
    assert q_res["found"] is True
    assert q_res["is_persistent_memory"] is True
    assert "remembers" in q_res["location_summary"].lower()


def test_unprocessed_demo04_has_no_foreign_memories() -> None:
    """An input-only video must not inherit the demo01 fixture or another graph."""
    res = client.get("/api/v1/query?item=shoes&dataset_id=demo04").json()
    assert res["found"] is False
    assert "demo04" in res["location_summary"]


def test_demo06_scene_graph_isolation() -> None:
    """Verify Demo06-Self strictly uses its own scene graph without shoe artifacts."""
    # 1. Anchors must be Desks, not Cabinet
    anchors_res = client.get("/api/v1/anchors?dataset_id=Demo06-Self")
    assert anchors_res.status_code == 200
    anchors = anchors_res.json()
    anchor_labels = [a["label"] for a in anchors]
    assert "Desk #1" in anchor_labels
    assert "Desk #2" in anchor_labels
    for label in anchor_labels:
        assert "cabinet" not in label.lower()

    # 2. Timeline must reflect bottle relocation between desks
    tl_res = client.get("/api/v1/timeline?dataset_id=Demo06-Self")
    assert tl_res.status_code == 200
    events = tl_res.json()
    assert len(events) >= 1
    reloc_ev = events[0]
    assert reloc_ev["object"] == "Bottle #1"
    assert "Desk #1" in reloc_ev["source_anchor"]
    assert "Desk #2" in reloc_ev["destination_anchor"]
    assert "moved from Desk #1 to Desk #2" in reloc_ev["summary"]

    # 3. Querying shoes in Demo06 must NOT return shoes from demo01
    shoes_res = client.get("/api/v1/query?item=shoes&dataset_id=Demo06-Self").json()
    assert shoes_res["found"] is False
    assert shoes_res.get("instance_label") is None

    # 4. Crop for instance 1 in Demo06 must be Bottle #1, not Shoes #1
    crop_res = client.get("/api/v1/crops/1?dataset_id=Demo06-Self")
    assert crop_res.status_code == 200
    assert "Bottle #1" in crop_res.text
    assert "Shoes" not in crop_res.text


def test_scene_graph_full_endpoint() -> None:
    """Verify /api/v1/scene_graph returns complete dataset scene graph payload."""
    res = client.get("/api/v1/scene_graph?dataset_id=Demo06-Self")
    assert res.status_code == 200
    data = res.json()
    assert data["dataset_id"] == "Demo06-Self"
    assert len(data["anchors"]) == 2
    assert len(data["latest_objects"]) >= 1
    assert data["latest_objects"][0]["label"] == "Bottle #1"


def test_datasets_discovery_endpoint() -> None:
    """Verify /api/v1/datasets discovers all datasets and returns summaries."""
    res = client.get("/api/v1/datasets")
    assert res.status_code == 200
    data = res.json()
    assert "active_dataset" in data
    assert "available_datasets" in data
    assert data["total_datasets"] >= 2
    dataset_ids = [d["dataset_id"] for d in data["available_datasets"]]
    assert "demo01" in dataset_ids
    assert "Demo06-Self" in dataset_ids


def test_query_generic_demo03_dataset() -> None:
    """Verify querying demo03 dataset returns kitchen objects and anchors accurately."""
    res = client.get("/api/v1/query?item=cooking pot&dataset_id=demo03")
    assert res.status_code == 200
    data = res.json()
    assert data["found"] is True
    assert "Cooking Pot" in data["instance_label"]
    assert "Sink" in data["anchor_label"] or "Refrigerator" in data["anchor_label"]


def test_demo04_scene_graph_queries_and_timeline() -> None:
    """Verify demo04 accurately queries garbage bags and returns pipeline timeline events."""
    # 1. Query garbage bag in demo04
    res = client.get("/api/v1/query?item=garbage bag&dataset_id=demo04").json()
    assert res["found"] is True
    assert "Garbage Bag" in res["instance_label"]
    assert "Storage Cabinet #1" in res["anchor_label"]

    # 2. Query food container in demo04
    food_res = client.get("/api/v1/query?item=food container&dataset_id=demo04").json()
    assert food_res["found"] is True
    assert "Food Container #2" in food_res["instance_label"]
    assert "Storage Cabinet #1" in food_res["anchor_label"]

    # 3. Timeline events
    tl_res = client.get("/api/v1/timeline?dataset_id=demo04")
    assert tl_res.status_code == 200
    events = tl_res.json()
    assert len(events) >= 1
    assert any("Garbage Bag" in e["object"] for e in events)


def test_query_response_includes_room_grounding() -> None:
    """Memory queries surface the room alongside anchor and relation."""
    res = client.get("/api/v1/query?item=shoes").json()
    assert res["found"] is True
    assert res["room_id"] == 1
    assert res["room_label"] == "Room #1"
    assert "in Room #1" in res["location_summary"]

    # demo03 was room-typed "Kitchen" from refrigerator landmark evidence.
    res_kitchen = client.get("/api/v1/query?item=cooking pot&dataset_id=demo03").json()
    assert res_kitchen["found"] is True
    assert res_kitchen["room_label"] == "Kitchen"
    assert "in the Kitchen" in res_kitchen["location_summary"]


def test_query_with_room_constraint() -> None:
    """Room-constrained queries narrow candidates and report miss locations."""
    # Right room: found.
    res = client.get("/api/v1/query?item=shoes in room 1").json()
    assert res["found"] is True
    assert res["room_label"] == "Room #1"

    # Wrong room: not found, but the memory layer explains where it lives.
    res_wrong = client.get("/api/v1/query?item=shoes in the kitchen").json()
    assert res_wrong["found"] is False
    assert "kitchen" in res_wrong["location_summary"].lower()
    assert "Room #1" in res_wrong["location_summary"]


def test_rooms_endpoint() -> None:
    """Rooms endpoint lists room regions with their anchors and tracked objects."""
    res = client.get("/api/v1/rooms?dataset_id=demo03").json()
    assert isinstance(res, list)
    assert len(res) == 1
    room = res[0]
    assert room["label"] == "Kitchen"
    assert room["room_type"] == "Kitchen"
    assert "Refrigerator #1" in room["anchors"]
    assert any("Cooking Pot" in obj for obj in room["objects"])
    assert room["keyframe_count"] >= 1

    neutral = client.get("/api/v1/rooms?dataset_id=demo01").json()
    assert neutral[0]["label"] == "Room #1"


def test_rename_room_endpoint_persists(tmp_path, monkeypatch) -> None:
    """Caregiver room renames persist to the scene graph artifact."""
    import json as json_module

    import aegis.remote.api as api_module

    source = (
        __import__("pathlib").Path(__file__).parent
        / "fixtures"
        / "demo01"
        / "objects"
        / "r4d_scene_graph.json"
    )
    target_dir = tmp_path / "demo01" / "objects"
    target_dir.mkdir(parents=True)
    target = target_dir / "r4d_scene_graph.json"
    target.write_text(source.read_text())

    api_module._GRAPH_CACHE.pop("demo01", None)
    monkeypatch.setattr(
        api_module, "get_search_paths", lambda ds: [target_dir / "r4d_scene_graph.json"]
    )

    response = client.post(
        "/api/v1/rooms/rename?room_id=1&label=Hallway&dataset_id=demo01"
    )
    assert response.status_code == 200
    assert response.json()["label"] == "Hallway"

    saved = json_module.loads(target.read_text())
    assert saved["rooms"][0]["label"] == "Hallway"
    assert saved["anchors"][0]["room_label"] == "Hallway"
    first_entry = next(iter(saved["timeline"].values()))[0]
    assert first_entry["room_label"] == "Hallway"
    assert saved["events"][0]["destination_room"] == "Hallway"

    # The renamed room is visible in queries and room listings.
    query = client.get("/api/v1/query?item=shoes&dataset_id=demo01").json()
    assert query["room_label"] == "Hallway"
    rooms = client.get("/api/v1/rooms?dataset_id=demo01").json()
    assert rooms[0]["label"] == "Hallway"

    # Unknown rooms return a clean 404.
    missing = client.post("/api/v1/rooms/rename?room_id=99&label=X&dataset_id=demo01")
    assert missing.status_code == 404
