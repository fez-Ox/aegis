"""P1.4: every non-abstaining answer carries complete evidence."""

from __future__ import annotations

from fastapi.testclient import TestClient

from aegis.memory.evidence import answer_evidence, evidence_complete
from aegis.remote.api import app


def test_builder_falls_back_to_text_when_no_crop() -> None:
    record = answer_evidence(
        {
            "instance_id": 7,
            "last_seen_at": "2026-01-07T12:00:00+00:00",
            "anchor_label": "Desk #1",
            "room_label": "Kitchen",
        },
        description="Mug #7 on Desk #1",
    )
    assert evidence_complete(record)
    assert record["observation_id"] == "state:7"
    assert record["crop_url"] is None
    assert "No image crop available" in record["text_fallback"]


def test_incomplete_records_are_detected() -> None:
    assert not evidence_complete(
        {"observation_id": "state:1", "observed_at": None, "room_label": "Kitchen"}
    )


def test_query_and_ask_answers_are_fully_evidenced() -> None:
    client = TestClient(app)
    for dataset_id, item in (
        ("demo01_sam3", "shoes"),
        ("demo03_sam3", "cooking pot"),
        ("demo05_sam3", "basket"),
    ):
        response = client.get(
            "/api/v1/query", params={"item": item, "dataset_id": dataset_id}
        )
        assert response.status_code == 200
        body = response.json()
        if body["found"]:
            assert body["evidence"]
            assert all(evidence_complete(record) for record in body["evidence"])

    for question in (
        "where is the cooking pot",
        "when did I last see my shoes",
        "what did I do this morning",
    ):
        response = client.get(
            "/api/v1/ask",
            params={"text": question, "dataset_id": "demo03_sam3"},
        )
        assert response.status_code == 200
        body = response.json()
        if body["found"]:
            assert body["evidence"]
            assert all(evidence_complete(record) for record in body["evidence"])


def test_home_answers_are_fully_evidenced() -> None:
    client = TestClient(app)
    for params in (
        {"text": "where is my mug", "home_id": "egolife_jake"},
        {
            "text": "when did I last see the mug",
            "home_id": "egolife_jake",
            "as_of": "2026-01-08T12:59:00Z",
        },
        {
            "text": "what did I do around then",
            "home_id": "egolife_jake",
            "at": "2026-01-07T12:05:45Z",
        },
    ):
        response = client.get("/api/v1/ask", params=params)
        assert response.status_code == 200
        body = response.json()
        if body["found"]:
            assert body["evidence"]
            assert all(evidence_complete(record) for record in body["evidence"])
