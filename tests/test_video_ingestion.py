"""Tests for video ingestion, downloading, and multi-dataset pipeline capabilities."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from aegis.ingestion.download import EGOCENTRIC_PRESETS, probe_video
from aegis.memory.reasoning import QueryReasoningEngine
from aegis.remote.api import app

client = TestClient(app)


def test_egocentric_presets_defined() -> None:
    """Verify standard indoor egocentric presets are configured with URLs."""
    assert "arrange_pots" in EGOCENTRIC_PRESETS
    assert "sort_clothes" in EGOCENTRIC_PRESETS
    assert "fridge_food" in EGOCENTRIC_PRESETS
    assert "make_coffee" in EGOCENTRIC_PRESETS

    preset = EGOCENTRIC_PRESETS["arrange_pots"]
    assert preset["url"].startswith("https://")
    assert (
        "egocentric" in preset["url"].lower() or "huggingface" in preset["url"].lower()
    )


def test_probe_video_on_demo_video() -> None:
    """Verify video inspection extracts valid dimensions, duration, and frame rate."""
    demo_video = Path("data/demo01/video.mp4")
    if demo_video.exists():
        info = probe_video(demo_video)
        assert info["fps"] > 0
        assert info["width"] == 1920
        assert info["height"] == 1080
        assert info["duration_seconds"] > 40.0
        assert info["size_mb"] > 60.0


def test_reasoning_synonyms_and_grammar() -> None:
    """Verify cognitive reasoning engine handles singular and plural queries correctly."""
    # Singular
    target_pot = QueryReasoningEngine.extract_target_item("Where is the cooking pot?")
    assert target_pot in {"cooking pot", "pot"}

    # Plural
    target_pots = QueryReasoningEngine.extract_target_item("Find the pots")
    assert target_pots in {"cooking pot", "pot", "pots"}

    # Reasoning explanation grammar
    explanation_single = QueryReasoningEngine.reason_spatio_temporal_state(
        "cooking pot",
        {
            "label": "Cooking Pot #1",
            "anchor_label": "Sink #2",
            "relation": "on_surface",
            "is_active_view": True,
            "relative_distance": 0.25,
        },
        [],
    )
    assert "is currently resting on Sink #2" in explanation_single["explanation"]

    explanation_plural = QueryReasoningEngine.reason_spatio_temporal_state(
        "shoes",
        {
            "label": "Shoes #1 [Active Pair]",
            "anchor_label": "Storage Cabinet #1",
            "relation": "inside",
            "is_active_view": False,
            "relative_distance": 0.09,
        },
        [],
    )
    assert (
        "are safely put away inside Storage Cabinet #1"
        in explanation_plural["explanation"]
    )


def test_datasets_endpoint_contains_summaries() -> None:
    """Verify /api/v1/datasets returns discovered datasets with titles and anchors."""
    resp = client.get("/api/v1/datasets")
    assert resp.status_code == 200
    data = resp.json()
    assert "active_dataset" in data
    assert "available_datasets" in data
    assert len(data["available_datasets"]) >= 1

    ds_map = {d["dataset_id"]: d for d in data["available_datasets"]}
    if "demo01" in ds_map:
        assert "Storage Cabinet #1" in ds_map["demo01"]["anchors"]
    if "demo03" in ds_map:
        assert "Refrigerator #1" in ds_map["demo03"]["anchors"]
        assert ds_map["demo03"]["num_events"] > 0


def test_dataset_selection_and_isolated_query() -> None:
    """Verify selecting a dataset isolates queries and timelines to that specific video."""
    # Select demo03
    select_resp = client.post("/api/v1/dataset/select?dataset_id=demo03")
    assert select_resp.status_code == 200
    assert select_resp.json()["active_dataset"] == "demo03"

    # Query pot in demo03
    pot_resp = client.get("/api/v1/query?item=pot")
    assert pot_resp.status_code == 200
    pot_data = pot_resp.json()
    assert pot_data["found"] is True
    assert "Cooking Pot" in pot_data["instance_label"]

    # Query bowls in demo03
    bowl_resp = client.get("/api/v1/query?item=bowls")
    assert bowl_resp.status_code == 200
    assert bowl_resp.json()["found"] is True

    # Timeline in demo03
    tl_resp = client.get("/api/v1/timeline")
    assert tl_resp.status_code == 200
    events = tl_resp.json()
    assert len(events) >= 1
    assert any("Cooking Pot" in ev["object"] or "Bowl" in ev["object"] for ev in events)

    # Re-select demo01
    client.post("/api/v1/dataset/select?dataset_id=demo01")
    shoes_resp = client.get("/api/v1/query?item=shoes")
    assert shoes_resp.status_code == 200
    assert shoes_resp.json()["found"] is True
    assert "Shoes #1" in shoes_resp.json()["instance_label"]
