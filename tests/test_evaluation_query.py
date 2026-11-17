"""Tests for query scoring, persistence, ablations, and isolation."""

from __future__ import annotations

from typing import Any

import pytest

from aegis.evaluation.query import (
    answer_query,
    apply_ablation,
    evaluate_ablations,
    evaluate_leakage,
    evaluate_persistence,
    evaluate_queries,
)
from aegis.evaluation.schema import PersistenceCase, QuerySpec


def _entry(
    frame_id: int,
    timestamp: float,
    instance_id: int,
    label: str,
    anchor: str,
    room: str,
    relation: str,
    *,
    active: bool,
    last_seen: float,
    center: tuple[float, float, float] = (0.0, 0.0, 0.0),
    in_hand: bool = False,
) -> dict[str, Any]:
    return {
        "frame_id": frame_id,
        "timestamp": timestamp,
        "instance_id": instance_id,
        "label": label,
        "center": list(center),
        "size": [0.2, 0.1, 0.1],
        "anchor_id": 1 if "Cabinet" in anchor else 2,
        "anchor_label": anchor,
        "relative_vector": [0.0, 0.0, 0.0],
        "relative_distance": 0.2,
        "relation": relation,
        "is_active_view": active,
        "last_seen_timestamp": last_seen,
        "is_in_hand": in_hand,
        "carrier": "camera_wearer" if in_hand else None,
        "room_id": 1,
        "room_label": room,
    }


def _graph() -> dict[str, Any]:
    timeline: dict[str, list[dict[str, Any]]] = {
        "0": [
            _entry(
                0,
                0.0,
                1,
                "Shoes #1 [Active Pair]",
                "Floor Entrance",
                "Room #1",
                "on_floor",
                active=True,
                last_seen=0.0,
            ),
            _entry(
                0,
                0.0,
                2,
                "Keys #1",
                "Desk #1",
                "Room #1",
                "on_surface",
                active=True,
                last_seen=0.0,
            ),
        ],
        "1": [
            _entry(
                1,
                1.0,
                1,
                "Shoes #1 [Active Pair]",
                "Floor Entrance",
                "Room #1",
                "on_floor",
                active=True,
                last_seen=1.0,
            ),
            _entry(
                1,
                1.0,
                2,
                "Keys #1",
                "Desk #1",
                "Room #1",
                "on_surface",
                active=True,
                last_seen=1.0,
            ),
        ],
        "2": [
            _entry(
                2,
                2.0,
                1,
                "Shoes #1 [Active Pair]",
                "Storage Cabinet #1",
                "Room #1",
                "inside",
                active=False,
                last_seen=1.0,
            ),
            _entry(
                2,
                2.0,
                2,
                "Keys #1",
                "Desk #1",
                "Room #1",
                "on_surface",
                active=True,
                last_seen=2.0,
            ),
        ],
        "3": [
            _entry(
                3,
                3.0,
                1,
                "Shoes #1 [Active Pair]",
                "Storage Cabinet #1",
                "Room #1",
                "inside",
                active=False,
                last_seen=1.0,
            ),
            _entry(
                3,
                3.0,
                2,
                "Keys #1",
                "Desk #1",
                "Room #1",
                "on_surface",
                active=True,
                last_seen=3.0,
            ),
        ],
        "4": [
            _entry(
                4,
                4.0,
                1,
                "Shoes #1 [Active Pair]",
                "Storage Cabinet #1",
                "Room #1",
                "inside",
                active=False,
                last_seen=1.0,
            ),
            _entry(
                4,
                4.0,
                2,
                "Keys #1",
                "Desk #1",
                "Room #1",
                "on_surface",
                active=True,
                last_seen=4.0,
            ),
        ],
    }
    return {
        "dataset_id": "synthetic",
        "anchors": [],
        "rooms": [{"room_id": 1, "label": "Room #1"}],
        "timeline": timeline,
        "events": [
            {
                "event_id": "e1",
                "event_type": "placement",
                "object": "Shoes #1 [Active Pair]",
                "instance_id": 1,
                "start_time": 1.5,
                "end_time": 2.0,
                "source_anchor": "Floor Entrance",
                "destination_anchor": "Storage Cabinet #1",
                "source_relation": "on_floor",
                "destination_relation": "inside",
                "source_room": "Room #1",
                "destination_room": "Room #1",
            }
        ],
    }


def test_answer_query_uses_persistent_state() -> None:
    answer = answer_query(_graph(), "Where are my shoes?", "synthetic")
    assert answer["found"] is True
    assert answer["instance_label"] == "Shoes #1 [Active Pair]"
    assert answer["anchor_label"] == "Storage Cabinet #1"
    assert answer["room_label"] == "Room #1"
    assert answer["relation"] == "inside"
    assert answer["is_persistent_memory"] is True
    assert "Room #1" in answer["location_summary"]


def test_answer_query_unknown_item_is_not_found() -> None:
    answer = answer_query(_graph(), "Where is my wallet?", "synthetic")
    assert answer["found"] is False
    assert "couldn't locate" in answer["location_summary"]


def test_evaluate_queries_scores_grounded_fields() -> None:
    queries = [
        QuerySpec(
            query_id="q1",
            query="Where are my shoes?",
            expected_instance_label="Shoes #1",
            expected_anchor="Storage Cabinet #1",
            expected_room="Room #1",
            expected_relation="inside",
        ),
        QuerySpec(
            query_id="q2",
            query="Where are my keys?",
            expected_anchor="Desk #1",
            expected_room="Room #1",
            expected_relation="on_surface",
        ),
        QuerySpec(
            query_id="q3",
            query="Where is my wallet?",
            expected_found=False,
            negative=True,
        ),
        QuerySpec(
            query_id="q4",
            query="Where are my shoes in the kitchen?",
            expected_found=False,
            negative=True,
        ),
        QuerySpec(
            query_id="q5",
            query="Where are my shoes?",
            expected_anchor="Desk #1",
            notes="Deliberately wrong expectation to exercise the failure path.",
        ),
    ]
    result = evaluate_queries(_graph(), queries, dataset_id="synthetic")
    assert result["counts"]["total"] == 5
    assert result["counts"]["grounded_correct"] == 4
    assert result["answer_accuracy"] == pytest.approx(0.8)
    assert result["counts"]["false_found"] == 0
    assert result["failures"][0]["query_id"] == "q5"
    assert result["failures"][0]["failure_reason"].startswith("anchor expected")


def test_persistence_scoring_and_failures() -> None:
    cases = [
        PersistenceCase(
            case_id="p1",
            query="Where are my shoes?",
            expected_instance_id=1,
            expected_label="Shoes #1",
            expected_anchor="Storage Cabinet #1",
            expected_room="Room #1",
            expected_relation="inside",
            check_frame=4,
            expect_persistent=True,
        ),
        PersistenceCase(
            case_id="p2",
            query="Where are my keys?",
            expected_label="Keys #1",
            expected_anchor="Desk #1",
            expected_room="Room #1",
            expected_relation="on_surface",
            check_frame=4,
            expect_persistent=False,
        ),
        PersistenceCase(
            case_id="p3",
            query="Where are my shoes?",
            expected_label="Shoes #1",
            expected_anchor="Floor Entrance",
            check_frame=4,
        ),
    ]
    result = evaluate_persistence(_graph(), cases)
    assert result["counts"]["total"] == 3
    assert result["state_recall"] == pytest.approx(2 / 3)
    assert result["query_recall"] == pytest.approx(2 / 3)
    assert result["identity_consistency"] == pytest.approx(1.0)
    assert {failure["case_id"] for failure in result["failures"]} == {"p3"}


def test_ablations_reduce_persistence_and_room_scores() -> None:
    queries = [
        QuerySpec(
            query_id="q1",
            query="Where are my shoes?",
            expected_anchor="Storage Cabinet #1",
            expected_room="Room #1",
            expected_relation="inside",
        ),
        QuerySpec(
            query_id="q2",
            query="Where are my keys?",
            expected_anchor="Desk #1",
            expected_room="Room #1",
            expected_relation="on_surface",
        ),
        QuerySpec(
            query_id="q3",
            query="Where is my wallet?",
            expected_found=False,
            negative=True,
        ),
    ]
    cases = [
        PersistenceCase(
            case_id="p1",
            query="Where are my shoes?",
            expected_instance_id=1,
            expected_label="Shoes #1",
            expected_anchor="Storage Cabinet #1",
            check_frame=4,
            expect_persistent=True,
        )
    ]
    result = evaluate_ablations(_graph(), queries, cases)
    assert result["full"]["answer_accuracy"] == pytest.approx(1.0)
    assert result["full"]["persistence_state_recall"] == pytest.approx(1.0)
    assert result["no_persistence"]["answer_accuracy"] < 1.0
    assert result["no_persistence"]["persistence_state_recall"] < 1.0
    assert result["no_memory"]["answer_accuracy"] < 1.0
    assert result["no_rooms"]["answer_accuracy"] < 1.0

    full = apply_ablation(_graph(), "full")
    full["timeline"]["4"][0]["label"] = "mutated"
    assert _graph()["timeline"]["4"][0]["label"] == "Shoes #1 [Active Pair]"


def test_leakage_is_zero_for_disjoint_graphs() -> None:
    shoes_graph = _graph()
    shoes_graph["timeline"] = {
        "4": [
            entry for entry in shoes_graph["timeline"]["4"] if entry["instance_id"] == 1
        ]
    }
    keys_graph = _graph()
    keys_graph["timeline"] = {
        "4": [
            entry for entry in keys_graph["timeline"]["4"] if entry["instance_id"] == 2
        ]
    }
    result = evaluate_leakage({"shoes_only": shoes_graph, "keys_only": keys_graph})
    assert result["cases"] >= 2
    assert result["leaks"] == 0
    assert result["leakage_rate"] == 0.0
