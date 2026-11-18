"""Tests for the single NLQ engine, the /ask endpoint and the CLI."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aegis.nlq import AnswerEngine, DictionaryIndex, memory_view_from_graph
from aegis.nlq.cli import main as ask_main

FIXTURE = (
    Path(__file__).parent / "fixtures" / "demo01" / "objects" / "r4d_scene_graph.json"
)


@pytest.fixture(scope="module")
def memory():
    graph = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return memory_view_from_graph(graph, "demo01")


@pytest.fixture(scope="module")
def engine():
    return AnswerEngine(DictionaryIndex.seeded())


def test_dictionary_resolves_item_and_room():
    index = DictionaryIndex.seeded()
    slots = index.lookup_item("where are my water bottle in the kitchen")
    assert slots.item in {"bottle", "water bottle"}
    assert slots.room == "kitchen"


def test_dictionary_suggestions_are_canonical():
    index = DictionaryIndex.seeded()
    suggestions = index.suggestions_for("sneekers")
    assert "shoes" in suggestions


def test_locate_returns_grounded_answer(engine, memory):
    result = engine.ask("where are my shoes", memory)
    assert result.abstained is False
    assert result.status == "answered"
    assert "shoes" in result.answer.lower()
    assert result.anchor_label == "Storage Cabinet #1"
    assert result.evidence and result.evidence[0]["description"]
    assert len(re.findall(r"[.!?](?:\s|$)", result.answer)) <= 2


def test_unknown_item_abstains_without_location(engine, memory):
    result = engine.ask("where is my teleporter", memory)
    assert result.abstained
    assert result.abstain_reason == "item_not_in_dictionary"
    assert result.anchor_label is None and result.room_label is None


def test_known_but_unobserved_item_abstains(engine, memory):
    result = engine.ask("where are my keys", memory)
    assert result.abstained
    assert result.abstain_reason == "not_observed_in_memory"


def test_temporal_and_activity_stub_abstain(engine, memory):
    when = engine.ask("when did I last see my shoes", memory)
    what = engine.ask("what did I do this morning", memory)
    assert when.abstained and when.abstain_reason == "temporal_handler_not_implemented"
    assert what.abstained and what.abstain_reason == "activity_handler_not_implemented"


def test_ask_endpoint_answers_and_abstains():
    client = TestClient(app_module())
    ok = client.get(
        "/api/v1/ask", params={"text": "where are my shoes", "dataset_id": "demo01"}
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["found"] is True
    assert body["anchor_label"] == "Storage Cabinet #1"
    assert body["evidence"]
    no = client.get(
        "/api/v1/ask", params={"text": "where are my keys", "dataset_id": "demo01"}
    )
    assert no.status_code == 200
    assert no.json()["abstained"] is True


def test_ask_endpoint_post():
    client = TestClient(app_module())
    response = client.post(
        "/api/v1/ask", json={"text": "where are my shoes", "dataset_id": "demo01"}
    )
    assert response.status_code == 200
    assert response.json()["found"] is True


def test_cli_local_mode(capsys):
    code = ask_main(
        [
            "where",
            "are",
            "my",
            "shoes",
            "--dataset-id",
            "demo01",
            "--transport",
            "local",
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "shoes" in out.lower()


def app_module():
    from aegis.remote.api import app

    return app
