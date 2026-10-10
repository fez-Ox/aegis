"""Tests for Mid-1 Prototype dynamic spatial simulation and edge case endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from aegis.remote.api import app

client = TestClient(app)


def test_baseline_occlusion_persistence() -> None:
    """Validate baseline state demonstrates occlusion persistence."""
    client.post("/api/v1/reset")
    resp = client.get("/api/v1/query?item=shoes")
    assert resp.status_code == 200
    data = resp.json()
    assert data["found"] is True
    assert "Shoes #1" in data["instance_label"]
    assert data["relation"] == "inside"
    assert data["is_persistent_memory"] is True
    assert "safely put away inside Storage Cabinet #1" in data["location_summary"]


def test_dynamic_transition_to_floor() -> None:
    """Validate dynamic transition to on_floor updates query and timeline immediately."""
    # Reset first
    client.post("/api/v1/reset")

    # Trigger transition to floor
    sim_resp = client.get("/api/v1/simulate/floor")
    assert sim_resp.status_code == 200
    sim_data = sim_resp.json()
    assert sim_data["status"] == "ok"
    assert sim_data["new_relation"] == "on_floor"
    assert sim_data["is_persistent_memory"] is False

    # Check that memory query now reflects floor state
    query_resp = client.get("/api/v1/query?item=shoes")
    assert query_resp.status_code == 200
    query_data = query_resp.json()
    assert query_data["relation"] == "on_floor"
    assert "on the floor" in query_data["location_summary"].lower()

    # Check that timeline event is recorded
    tl_resp = client.get("/api/v1/timeline")
    assert tl_resp.status_code == 200
    events = tl_resp.json()
    latest_event = events[-1]
    assert latest_event["destination_relation"] == "on_floor"
    assert "on the floor" in latest_event["summary"].lower()


def test_dynamic_transition_to_in_hand() -> None:
    """Validate in-hand transition reflects kinematic carrying edge case."""
    client.post("/api/v1/reset")

    # Trigger transition to in_hand
    sim_resp = client.get("/api/v1/simulate/in_hand")
    assert sim_resp.status_code == 200
    sim_data = sim_resp.json()
    assert sim_data["new_relation"] == "carried_by_user"

    # Check memory query
    query_resp = client.get("/api/v1/query?item=shoes")
    assert query_resp.status_code == 200
    query_data = query_resp.json()
    assert query_data["relation"] == "carried_by_user"
    assert "carrying" in query_data["location_summary"].lower() or "holding" in query_data["location_summary"].lower()


def test_reset_memory_reverts_state() -> None:
    """Validate reset endpoint restores baseline memory graph cleanly."""
    # Move to floor
    client.get("/api/v1/simulate/floor")
    q1 = client.get("/api/v1/query?item=shoes").json()
    assert q1["relation"] == "on_floor"

    # Reset
    reset_resp = client.post("/api/v1/reset")
    assert reset_resp.status_code == 200
    assert reset_resp.json()["status"] == "ok"

    # Check restored state
    q2 = client.get("/api/v1/query?item=shoes").json()
    assert q2["relation"] == "inside"
    assert q2["is_persistent_memory"] is True
