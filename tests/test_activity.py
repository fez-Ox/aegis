"""Activity/routine answer tests (P1.1)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from aegis.nlq.engine import AnswerEngine
from aegis.remote.api import app


def _memory(activities: list[dict]) -> dict:
    return {
        "dataset_id": "home01",
        "latest_objects": [],
        "anchors": [],
        "rooms": [],
        "events": [],
        "activities": activities,
    }


def test_activity_answer_uses_room_and_events() -> None:
    memory = _memory(
        [
            {
                "activity_id": 1,
                "room_label": "Kitchen",
                "start_at": "2026-01-07T12:00:00+00:00",
                "end_at": "2026-01-07T12:05:00+00:00",
                "summary": "12:00–12:05 Kitchen: Mug #1 placed on Desk #2.",
            }
        ]
    )
    memory["as_of"] = "2026-01-07T12:03:00Z"
    result = AnswerEngine().ask("what did I do this morning", memory)
    assert result.intent == "activity"
    assert result.status == "answered"
    assert "Kitchen" in result.answer
    assert "Mug #1" in result.answer
    assert "12:00" not in result.answer  # clock range prefix stripped
    assert result.evidence


def test_activity_abstains_without_history() -> None:
    result = AnswerEngine().ask("what did I do this morning", _memory([]))
    assert result.abstained
    assert result.abstain_reason == "no_activity_history"


def test_activity_window_filters_out_other_times() -> None:
    memory = _memory(
        [
            {
                "activity_id": 1,
                "room_label": "Kitchen",
                "start_at": "2026-01-07T08:00:00+00:00",
                "end_at": "2026-01-07T08:05:00+00:00",
                "summary": "08:00–08:05 Kitchen: Mug #1 moved.",
            }
        ]
    )
    memory["focus_time"] = "2026-01-07T12:05:00Z"
    result = AnswerEngine().ask("what did I do around then", memory)
    assert result.abstained
    assert result.abstain_reason == "no_activities_in_window"


def test_activity_endpoint_for_home_and_graph() -> None:
    client = TestClient(app)
    home = client.get(
        "/api/v1/ask",
        params={
            "text": "what did I do around then",
            "home_id": "egolife_jake",
            "at": "2026-01-07T12:05:45Z",
        },
    )
    assert home.status_code == 200
    assert home.json()["status"] == "answered"
    assert home.json()["evidence"]

    graph = client.get(
        "/api/v1/ask",
        params={"text": "what did I do this morning", "dataset_id": "demo03_sam3"},
    )
    assert graph.status_code == 200
    assert graph.json()["abstained"]
    assert graph.json()["abstain_reason"] == "no_activity_history"
