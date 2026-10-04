"""Tests for cognitive query disambiguation and spatio-temporal reasoning."""

from __future__ import annotations

from aegis.memory.reasoning import QueryReasoningEngine


def test_extract_target_item_synonyms() -> None:
    """Test natural language queries map to canonical items."""
    assert QueryReasoningEngine.extract_target_item("Where are my sneakers?") == "shoes"
    assert (
        QueryReasoningEngine.extract_target_item("Did I leave my car key somewhere?")
        == "keys"
    )
    assert QueryReasoningEngine.extract_target_item("Where is my eyewear?") == "glasses"
    assert (
        QueryReasoningEngine.extract_target_item("Where did I leave my pills?")
        == "medicine"
    )


def test_reason_occluded_object_permanence_edge_case() -> None:
    """Test Form 2 edge case: object occluded behind closed cabinet maintains permanence."""
    primary = {
        "label": "Shoes #1 [Active Pair]",
        "anchor_label": "Storage Cabinet #1",
        "relation": "inside",
        "relative_distance": 0.095,
        "is_active_view": False,  # Occluded / not in current camera view
    }
    events = [
        {
            "object": "Shoes #1",
            "source_relation": "on_floor",
            "destination_relation": "inside",
        }
    ]

    reasoning = QueryReasoningEngine.reason_spatio_temporal_state(
        "shoes", primary, events
    )
    assert reasoning["is_persistent_memory"] is True
    assert reasoning["edge_case_handled"] == "occlusion_object_permanence"
    assert "safely put away inside Storage Cabinet #1" in reasoning["explanation"]
    assert "Aegis remembers" in reasoning["explanation"]


def test_reason_visible_item() -> None:
    """Test visible item generates straightforward affirmative location."""
    primary = {
        "label": "Keys #1",
        "anchor_label": "Entrance Console Table",
        "relation": "on_floor",
        "relative_distance": 0.15,
        "is_active_view": True,
    }
    reasoning = QueryReasoningEngine.reason_spatio_temporal_state("keys", primary, [])
    assert reasoning["is_persistent_memory"] is False
    assert "on the floor right near Entrance Console Table" in reasoning["explanation"]
