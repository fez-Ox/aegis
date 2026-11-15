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
    assert reasoning["explanation"] == (
        "Your shoes were last seen inside Storage Cabinet #1."
    )


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
    assert reasoning["explanation"] == (
        "Your keys are on the floor beside Entrance Console Table."
    )


def test_extract_target_item_ignores_room_words() -> None:
    """Room mentions constrain the search, they are never the target item."""
    assert QueryReasoningEngine.extract_target_item("keys in the kitchen") == "keys"
    assert (
        QueryReasoningEngine.extract_target_item("shoes in the living room") == "shoes"
    )
    assert (
        QueryReasoningEngine.extract_target_item("where is my pills in the bedroom")
        == "medicine"
    )


def test_extract_room_filter() -> None:
    """Room constraints parse from natural language."""
    assert QueryReasoningEngine.extract_room_filter("keys in the kitchen") == "kitchen"
    assert (
        QueryReasoningEngine.extract_room_filter("bottle in the living room")
        == "living room"
    )
    assert QueryReasoningEngine.extract_room_filter("shoes in room 1") == "room #1"
    assert QueryReasoningEngine.extract_room_filter("shoes in room #2") == "room #2"
    assert QueryReasoningEngine.extract_room_filter("where is my bottle") is None


def test_reason_appends_room_clause() -> None:
    """Room-grounded memories explain the containing room."""
    primary = {
        "label": "Keys #1",
        "anchor_label": "Coffee Table #1",
        "relation": "on_surface",
        "relative_distance": 0.08,
        "is_active_view": True,
        "room_label": "Living Room",
    }
    reasoning = QueryReasoningEngine.reason_spatio_temporal_state("keys", primary, [])
    assert "on Coffee Table #1 in the Living Room" in reasoning["explanation"]
    assert reasoning["room_label"] == "Living Room"


def test_reason_skips_room_clause_when_anchor_names_the_room() -> None:
    """No redundancy: 'Kitchen Counter #1' already implies the Kitchen."""
    primary = {
        "label": "Pills #1",
        "anchor_label": "Kitchen Counter #1",
        "relation": "on_surface",
        "relative_distance": 0.1,
        "is_active_view": True,
        "room_label": "Kitchen",
    }
    reasoning = QueryReasoningEngine.reason_spatio_temporal_state(
        "medicine", primary, []
    )
    assert "in the Kitchen" not in reasoning["explanation"]
    assert reasoning["room_label"] == "Kitchen"


def test_reason_neutral_room_label_grammar() -> None:
    """'Room #1' labels read as 'in Room #1', not 'in the #1'."""
    primary = {
        "label": "Bottle #1",
        "anchor_label": "Desk #1",
        "relation": "on_surface",
        "relative_distance": 0.05,
        "is_active_view": True,
        "room_label": "Room #2",
    }
    reasoning = QueryReasoningEngine.reason_spatio_temporal_state("bottle", primary, [])
    assert "on Desk #1 in Room #2" in reasoning["explanation"]


def _state(relation, anchor="Desk #1", *, in_view=True, room=None, certain=None):
    return {
        "label": "Keys #1",
        "anchor_label": anchor,
        "relation": relation,
        "is_active_view": in_view,
        "room_label": room,
        "relation_certain": certain,
    }


def _say(item, state):
    return QueryReasoningEngine.reason_spatio_temporal_state(item, state, [])[
        "explanation"
    ]


def test_templates_for_every_relation() -> None:
    assert _say("keys", _state("under", "Bed #1")) == "Your keys are under Bed #1."
    assert _say("keys", _state("above", in_view=False)) == (
        "Your keys were last seen above Desk #1."
    )
    assert _say("mug", _state("next_to")) == "Your mug is next to Desk #1."
    assert _say("mug", _state("near", in_view=False)) == (
        "Your mug was last seen near Desk #1."
    )
    assert _say("keys", _state("on_floor", None, room="Kitchen")) == (
        "Your keys are on the floor in the Kitchen."
    )
    assert _say("keys", _state("in_room", None, room="Room #2")) == (
        "Your keys are in Room #2."
    )
    assert _say("mug", _state("in_room", None)) == (
        "I have seen your mug, but I can't tell where it is."
    )
    assert _say("keys", _state("carried_by_user", None)) == "You are holding your keys."
    assert _say("keys", _state("carried_by_user", None, in_view=False)) == (
        "You were last seen carrying your keys."
    )


def test_uncertain_relation_says_so() -> None:
    answer = _say("keys", _state("near", certain=False))
    assert answer.endswith("I'm not fully sure about the exact spot.")


def test_no_answer_exceeds_two_sentences_or_overclaims() -> None:
    relations = [
        "inside",
        "on_surface",
        "under",
        "above",
        "next_to",
        "on_floor",
        "near",
        "in_room",
        "carried_by_user",
    ]
    for relation in relations:
        for in_view in (True, False):
            for certain in (True, False):
                answer = _say(
                    "keys",
                    _state(relation, in_view=in_view, room="Kitchen", certain=certain),
                )
                assert answer.count(".") <= 2, answer
                assert "safely" not in answer and "securely" not in answer


def test_event_summaries() -> None:
    from aegis.memory.reasoning import event_summary

    assert (
        event_summary(
            {"event_type": "pickup", "object": "Keys #1", "source_anchor": "Desk #1"}
        )
        == "Keys #1 was picked up from Desk #1."
    )
    assert (
        event_summary(
            {
                "event_type": "placement",
                "object": "Keys #1",
                "destination_anchor": "Drawer #2",
                "destination_relation": "inside",
                "destination_room": "Kitchen",
            }
        )
        == "Keys #1 was placed inside Drawer #2 in the Kitchen."
    )
    assert (
        event_summary(
            {
                "event_type": "placement",
                "object": "Keys #1",
                "destination_relation": "in_room",
            }
        )
        == "Keys #1 was put down."
    )
    assert (
        event_summary(
            {
                "event_type": "room_change",
                "source_room": "Room #1",
                "destination_room": "Kitchen",
            }
        )
        == "You moved from Room #1 to the Kitchen."
    )
