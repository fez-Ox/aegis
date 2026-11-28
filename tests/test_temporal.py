"""Temporal answers and freshness wording (P1.1 / P1.3)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from aegis.core.timeutil import time_ago, to_utc_iso
from aegis.nlq.engine import AnswerEngine, memory_view_from_graph
from aegis.remote.api import app

NOW = datetime(2026, 1, 11, 12, 0, tzinfo=UTC)


def _iso(hours_ago: float) -> str:
    return to_utc_iso(NOW - timedelta(hours=hours_ago))


@pytest.mark.parametrize(
    ("hours", "expected"),
    [
        (0.0, "just now"),
        (0.5, "30 minutes ago"),
        (2.0, "2 hours ago"),
        (24.0, "yesterday"),
        (72.0, "3 days ago"),
        (240.0, "over a week ago"),
    ],
)
def test_time_ago_buckets(hours: float, expected: str) -> None:
    assert time_ago(_iso(hours), NOW) == expected


def test_time_ago_handles_missing_and_bad_values() -> None:
    assert time_ago(None, NOW) is None
    assert time_ago("not-a-time", NOW) is None
    assert time_ago("2026-01-11T13:00:00+00:00", NOW) == "just now"


def _memory(wallclock: str) -> dict[str, object]:
    return memory_view_from_graph(
        {
            "dataset_id": "d1",
            "anchors": [],
            "rooms": [],
            "events": [],
            "latest_states": [
                {
                    "instance_id": 1,
                    "label": "Mug #1",
                    "canonical": "mug",
                    "relation": "on_surface",
                    "anchor_label": "Desk #1",
                    "room_label": "Kitchen",
                    "confidence": 0.9,
                    "last_seen_wallclock": wallclock,
                    "evidence_id": 1,
                }
            ],
        }
    )


def test_when_question_returns_time_and_place() -> None:
    memory = _memory(_iso(26.0))
    memory["as_of"] = to_utc_iso(NOW)
    result = AnswerEngine().ask("when did I last see my cup?", memory)
    assert result.intent == "temporal"
    assert result.status == "answered"
    assert "yesterday" in result.answer
    assert "Desk #1" in result.answer
    assert result.last_seen_wallclock is not None
    assert result.evidence


def test_when_question_abstains_without_timestamp() -> None:
    memory = _memory(_iso(2.0))
    memory["latest_objects"][0]["last_seen_wallclock"] = None
    result = AnswerEngine().ask("when did I last see my cup?", memory)
    assert result.abstained
    assert result.abstain_reason == "no_timestamp"


def test_as_of_does_not_peek_into_future_evidence() -> None:
    memory = _memory(_iso(2.0))
    memory["as_of"] = to_utc_iso(NOW - timedelta(hours=24))
    result = AnswerEngine().ask("when did I last see my cup?", memory)
    assert result.abstained
    assert result.abstain_reason == "no_timestamp"


def test_oracle_episode_interval_accepts_cue_inside_run() -> None:
    memory = _memory(_iso(2.0))
    memory["latest_objects"][0]["run_start_wallclock"] = _iso(3.0)
    focus = _iso(2.5)
    memory["focus_time"] = focus
    result = AnswerEngine().ask("when did I see my cup?", memory)
    assert result.status == "answered"
    assert result.answer.startswith("At that time")


def test_oracle_abstains_outside_episode() -> None:
    memory = _memory(_iso(2.0))
    memory["latest_objects"][0]["run_start_wallclock"] = _iso(3.0)
    memory["focus_time"] = _iso(100.0)
    result = AnswerEngine().ask("when did I see my cup?", memory)
    assert result.abstained
    assert result.abstain_reason == "no_evidence_at_time"


def test_query_endpoint_exposes_freshness_on_all_datasets() -> None:
    client = TestClient(app)
    for dataset_id in (
        "demo01_sam3",
        "demo03_sam3",
        "demo04_sam3",
        "demo05_sam3",
        "demo_pots_sam3",
    ):
        response = client.get(
            "/api/v1/query", params={"item": "shoes", "dataset_id": dataset_id}
        )
        assert response.status_code == 200
        body = response.json()
        if body["found"]:
            assert (
                body["last_seen_time_ago"]
                in {"just now", "yesterday", "3 days ago", "over a week ago"}
                or "ago" in body["last_seen_time_ago"]
            )


def test_ask_endpoint_supports_as_of_and_at_parameters() -> None:
    client = TestClient(app)
    for params in (
        {
            "text": "when did I last see the mug",
            "home_id": "egolife_jake",
            "as_of": "2026-01-08T12:59:00Z",
        },
        {
            "text": "when did I see the mug",
            "home_id": "egolife_jake",
            "at": "2026-01-07T12:02:07Z",
        },
        {
            "text": "when did I see the mug",
            "home_id": "egolife_jake",
            "at": "not-a-time",
        },
    ):
        response = client.get("/api/v1/ask", params=params)
        assert response.status_code == 200
        assert isinstance(response.json()["abstained"], bool)
    bad = client.get(
        "/api/v1/ask",
        params={
            "text": "when did I last see the mug",
            "home_id": "egolife_jake",
            "as_of": "garbage",
        },
    )
    assert bad.status_code == 200
    assert bad.json()["abstain_reason"] == "invalid_as_of"
