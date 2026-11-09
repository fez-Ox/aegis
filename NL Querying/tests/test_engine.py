"""Tests for the hybrid dictionary-based NLQ engine (offline)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

FOLDER_ROOT = Path(__file__).resolve().parents[1]
if str(FOLDER_ROOT) not in sys.path:
    sys.path.insert(0, str(FOLDER_ROOT))

from comm.client import AegisCommClient
from comm.llm import LLMError
from comm.transports import create_source
from nlq.dictionary import DictionaryIndex
from nlq.engine import AskResult, HybridNLQEngine, Intent

client = AegisCommClient(source=create_source(transport="local"))
DATASET = next(
    ds for ds in client.list_datasets() if client.load_memory(ds)["latest_objects"]
)


def test_dictionary_resolves_synonyms_to_canonical() -> None:
    dictionary = DictionaryIndex.seeded()
    assert dictionary.lookup_item("where is my sneaker").item == "shoes"
    assert dictionary.lookup_item("keys in the kitchen").room == "kitchen"


def test_unknown_word_is_gated_with_suggestions() -> None:
    dictionary = DictionaryIndex.seeded()
    slots = dictionary.lookup_item("where is my qwarrion")
    assert slots.item is None
    # Suggestions never invent a match; they may echo the raw phrase.
    assert all(isinstance(s, str) for s in dictionary.suggestions_for("qwarrion"))


def test_instance_matching_uses_word_boundaries() -> None:
    engine = HybridNLQEngine(client=client, llm=None)
    assert engine._match_instances("pan", [{"label": "pants #1"}]) == []
    assert engine._match_instances("cup", [{"label": "cupboard #1"}]) == []
    assert engine._match_instances("bed", [{"label": "bedroom #1"}]) == []
    assert engine._match_instances("mat", [{"label": "mattress #1"}]) == []


def test_intent_classification() -> None:
    engine = HybridNLQEngine(client=client, llm=None)
    assert engine.classify_intent("where is my shoes") is Intent.LOCATE
    assert engine.classify_intent("when did I last see my glasses") is (Intent.TEMPORAL)
    assert engine.classify_intent("what did I do this morning") is Intent.ACTIVITY


def test_locate_happy_path_is_grounded() -> None:
    engine = HybridNLQEngine(client=client, llm=None)
    # Pick an object that actually exists in the chosen fixture.
    label = engine.client.scene_summary(DATASET)["tracked_objects"][0]
    item = label.split("#")[0].split("[")[0].strip().lower()
    result = engine.ask(f"where is my {item}", DATASET)
    assert isinstance(result, AskResult)
    assert result.found and not result.abstained
    assert result.answer_text and result.anchor_label
    assert result.intent is Intent.LOCATE


def test_unknown_item_abstains_without_fabricating() -> None:
    engine = HybridNLQEngine(client=client, llm=None)
    result = engine.ask("where is my polymorphid flange", DATASET)
    assert result.abstained
    assert result.abstain_reason == "item_not_in_dictionary"
    assert result.anchor_label is None  # never invent a location


def test_known_item_not_in_dataset_reports_not_found() -> None:
    engine = HybridNLQEngine(client=client, llm=None)
    result = engine.ask("where is my medicine", DATASET)
    if result.found:
        assert result.answer_text  # dataset does contain it
    else:
        assert result.abstained and not result.found
        assert result.abstain_reason == "not_observed_in_memory"
        assert result.anchor_label is None


def test_room_constraint_without_match_abstains() -> None:
    engine = HybridNLQEngine(client=client, llm=None)
    result = engine.ask("where is my bottle in the bathroom", "demo04")
    assert result.abstained and not result.found
    assert result.abstain_reason == "not_observed_in_memory"
    assert result.anchor_label is None


def test_temporal_intent_honestly_abstains_for_now() -> None:
    engine = HybridNLQEngine(client=client, llm=None)
    result = engine.ask("when did I last see my glasses", DATASET)
    assert result.abstained
    assert result.abstain_reason == "temporal_handler_not_implemented"


def test_query_log_records_every_question() -> None:
    engine = HybridNLQEngine(client=client, llm=None)
    engine.ask("where is my shoes", DATASET)
    log = engine.query_log()
    assert log and log[-1]["query"] == "where is my shoes"


# ---------------------------------------------------------------------------
# LLM escape hatch: the LLM may map vocabulary, never write the answer.
# ---------------------------------------------------------------------------
class FakeLLM:
    """Duck-typed LLMClient: records prompts, returns a fixed decision."""

    available = True

    def __init__(self, decision: dict[str, object] | Exception) -> None:
        self.decision = decision
        self.calls: list[list[dict[str, object]]] = []

    def status(self) -> dict[str, object]:
        return {"available": True, "base_url": "fake", "model": "fake"}

    def chat_json(
        self, messages: list[dict[str, object]], **kwargs: object
    ) -> dict[str, object]:
        self.calls.append(messages)
        if isinstance(self.decision, Exception):
            raise self.decision
        return self.decision


def _dataset_containing(term: str) -> str | None:
    for dataset in client.list_datasets():
        labels = [
            str(obj.get("label", "")).lower()
            for obj in client.load_memory(dataset)["latest_objects"]
        ]
        if any(term in label for label in labels):
            return dataset
    return None


def test_llm_maps_unknown_word_to_validated_item() -> None:
    dataset = _dataset_containing("shoe")
    if dataset is None:  # pragma: no cover - fixtures always contain shoes
        pytest.skip("no offline fixture contains shoes")
    llm = FakeLLM({"intent": "locate", "item": "shoes", "room": None})
    engine = HybridNLQEngine(client=client, llm=llm)  # type: ignore[arg-type]
    result = engine.ask("where are my qwicks", dataset)
    assert result.found and not result.abstained
    assert result.llm_used and result.anchor_label
    assert llm.calls


def test_common_slang_is_in_closed_vocabulary() -> None:
    dataset = _dataset_containing("shoe")
    if dataset is None:  # pragma: no cover
        pytest.skip("no offline fixture contains shoes")
    engine = HybridNLQEngine(client=client, llm=None)
    result = engine.ask("where are my kicks", dataset)
    assert result.found and not result.abstained
    assert result.item == "shoes"
    assert not result.llm_used


def test_llm_cannot_invent_items_or_locations() -> None:
    dataset = _dataset_containing("shoe")
    if dataset is None:  # pragma: no cover
        pytest.skip("no offline fixture contains shoes")
    llm = FakeLLM({"intent": "locate", "item": "hoverboard", "room": "garage"})
    engine = HybridNLQEngine(client=client, llm=llm)  # type: ignore[arg-type]
    result = engine.ask("where is my hoverboard", dataset)
    assert result.abstained
    assert result.anchor_label is None  # never invent a location
    assert not result.llm_used


def test_llm_routes_unknown_intent_through_evidence_path() -> None:
    dataset = _dataset_containing("shoe")
    if dataset is None:  # pragma: no cover
        pytest.skip("no offline fixture contains shoes")
    llm = FakeLLM({"intent": "locate", "item": "shoes", "room": None})
    engine = HybridNLQEngine(client=client, llm=llm)  # type: ignore[arg-type]
    result = engine.ask("which spot has my shoes?", dataset)
    assert result.intent is Intent.LOCATE
    assert result.found and result.llm_used


def test_llm_time_mapping_still_abstains_honestly() -> None:
    dataset = _dataset_containing("shoe")
    if dataset is None:  # pragma: no cover
        pytest.skip("no offline fixture contains shoes")
    llm = FakeLLM({"intent": "temporal", "item": "glasses", "room": None})
    engine = HybridNLQEngine(client=client, llm=llm)  # type: ignore[arg-type]
    result = engine.ask("tell me the last moment I had my spectacles?", dataset)
    assert result.abstained
    assert result.abstain_reason == "temporal_handler_not_implemented"
    assert result.llm_used


def test_llm_room_must_be_explicit_in_the_question() -> None:
    llm = FakeLLM({"intent": "locate", "item": "bottle", "room": "room #1"})
    engine = HybridNLQEngine(client=client, llm=llm)  # type: ignore[arg-type]
    decision = engine._llm_fallback("where is my water vessel", "demo04")
    assert decision is not None and decision["item"] == "bottle"
    assert decision["room"] is None  # the user never named a room


def test_llm_keeps_room_when_the_question_mentions_it() -> None:
    rooms = client.load_memory("demo04")["rooms"]
    if not rooms:  # pragma: no cover - fixtures always contain a room
        pytest.skip("no room labels in demo04")
    label = str(rooms[0].get("label", "")).strip().lower()
    engine = HybridNLQEngine(
        client=client,
        llm=FakeLLM({"intent": "locate", "item": "bottle", "room": label}),
    )  # type: ignore[arg-type]
    decision = engine._llm_fallback(f"where is my water vessel in {label}", "demo04")
    assert decision is not None and decision["room"] == label


def test_llm_transport_failure_degrades_to_abstention() -> None:
    dataset = _dataset_containing("shoe")
    if dataset is None:  # pragma: no cover
        pytest.skip("no offline fixture contains shoes")
    llm = FakeLLM(LLMError("network down"))
    engine = HybridNLQEngine(client=client, llm=llm)  # type: ignore[arg-type]
    result = engine.ask("where is my hoverboard", dataset)
    assert result.abstained
    assert engine.last_llm_error == "network down"
    assert engine.llm_status()["available"] is True
