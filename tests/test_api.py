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
    """Test memory query for bottle returns Demo06 3D location and occlusion status."""
    response = client.get("/api/v1/query?item=water bottle")
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
