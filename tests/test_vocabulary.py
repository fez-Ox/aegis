"""Tests for the vocabulary ontology (config/vocabulary.yaml)."""

from __future__ import annotations

from pathlib import Path

import pytest

from aegis.core.config import RuntimeConfig, config_to_dict, load_config
from aegis.core.vocabulary import (
    VocabEntry,
    Vocabulary,
    default_vocabulary,
    normalise_label,
)


def test_file_loads_and_every_prompt_maps_to_one_entry() -> None:
    vocab = default_vocabulary()
    prompts = vocab.detector_prompts()
    assert len(prompts) == len(set(prompts))
    for prompt in prompts:
        entry = vocab.entry(prompt)
        assert entry.known
        assert prompt in entry.prompts
        assert entry.role in {"object", "anchor", "landmark", "hand"}


def test_roles_partition_labels() -> None:
    vocab = default_vocabulary()
    assert vocab.role("bed") == "anchor"
    assert vocab.room_type("bed") == "Bedroom"
    assert vocab.entry("bed").open_underneath
    assert vocab.role("window") == "landmark"
    assert vocab.role("Door") == "landmark"
    assert vocab.role("human hand") == "hand"
    assert vocab.role("shoe") == "object"
    assert vocab.canonical("shoe") == "shoes"
    assert vocab.canonical("Water_Bottle") == "bottle"
    assert vocab.canonical("cupboard") == "storage cabinet"
    assert vocab.display("table") == "Desk"


def test_unknown_label_is_object_and_marked_unknown() -> None:
    entry = default_vocabulary().entry("  Flux  Capacitor ")
    assert entry.id == "flux capacitor"
    assert entry.role == "object"
    assert entry.display == "Flux Capacitor"
    assert entry.known is False


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("where is my water bottle", "bottle"),
        ("my mug", "mug"),
        ("where did I leave my cup", "mug"),
        ("reading glasses", "glasses"),
        ("sneakers", "shoes"),
        ("where are my keys", "keys"),
        ("the trash bin", "trash bin"),
        ("my pills", "medicine"),
    ],
)
def test_resolve_query_longest_match(text: str, expected: str) -> None:
    entry = default_vocabulary().resolve_query(text)
    assert entry is not None
    assert entry.id == expected


def test_resolve_query_does_not_match_inside_words_or_non_objects() -> None:
    vocab = default_vocabulary()
    assert vocab.resolve_query("cupboard") is None
    assert vocab.resolve_query("the bed") is None
    assert vocab.resolve_query("") is None


def _entry(**kwargs) -> VocabEntry:
    defaults = {"id": "thing", "display": "Thing", "prompts": ("thing",)}
    defaults.update(kwargs)
    return VocabEntry(**defaults)


def test_validation_rejects_duplicate_prompt() -> None:
    with pytest.raises(ValueError, match="belongs to both"):
        Vocabulary(
            [
                _entry(id="a", prompts=("x",)),
                _entry(id="b", prompts=("x",)),
            ]
        )


def test_validation_rejects_anchor_flags_on_object() -> None:
    with pytest.raises(ValueError, match="only valid for anchors"):
        Vocabulary([_entry(container=True)])


def test_validation_rejects_unnormalised_and_bad_role() -> None:
    with pytest.raises(ValueError):
        Vocabulary([_entry(id="Thing")])
    with pytest.raises(ValueError):
        Vocabulary([_entry(role="furniture")])
    with pytest.raises(ValueError):
        Vocabulary([_entry(id="a"), _entry(id="b", prompts=("y",), synonyms=("a",))])


def test_round_trip_to_mapping() -> None:
    vocab = default_vocabulary()
    rebuilt = Vocabulary.from_mapping(vocab.to_mapping())
    assert rebuilt.to_mapping() == vocab.to_mapping()


def test_normalise_label() -> None:
    assert normalise_label("  Storage_Cabinet ") == "storage cabinet"


def test_config_carries_vocabulary() -> None:
    config = load_config(Path("config/demo.yaml"))
    raw = config_to_dict(config)
    rebuilt = RuntimeConfig.from_mapping(raw)
    assert rebuilt.vocab().to_mapping() == default_vocabulary().to_mapping()
    assert config.perception.target_classes == default_vocabulary().detector_prompts()


def test_task_scoped_config_keeps_its_prompts() -> None:
    config = load_config(Path("config/demo01.yaml"))
    assert config.perception.target_classes[0] == "shoes"
    assert "glasses" not in config.perception.target_classes
    assert config.vocabulary
