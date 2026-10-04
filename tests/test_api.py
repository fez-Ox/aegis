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
    assert "Inside Storage Cabinet #1" in res["location_summary"]
    assert res["crop_url"] is not None
    assert res["is_persistent_memory"] is True  # In frame 642, shoes are occluded / stored


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
    assert duration < 0.500, f"Query took {duration*1000:.1f}ms, exceeding 500ms limit"
