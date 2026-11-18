"""Tests for the generated closed-vocabulary dictionary."""

from __future__ import annotations

import sys
from pathlib import Path

FOLDER_ROOT = Path(__file__).resolve().parents[1]
if str(FOLDER_ROOT) not in sys.path:
    sys.path.insert(0, str(FOLDER_ROOT))

from nlq.dictionary import (
    DEFAULT_DICTIONARY_PATH,
    DictionaryIndex,
)


def test_generated_dictionary_exists_and_loads() -> None:
    assert DEFAULT_DICTIONARY_PATH.is_file(), (
        "run: uv run python 'NL Querying/scripts/build_dictionary.py'"
    )
    index = DictionaryIndex.load(DEFAULT_DICTIONARY_PATH)
    assert "shoes" in index.item_synonyms
    assert "garbage bag" in index.item_synonyms
    assert "storage cabinet" in index.item_synonyms
    assert "kitchen" in index.room_keywords


def test_seeded_merges_live_tables_and_generated_vocabulary() -> None:
    index = DictionaryIndex.seeded()
    assert index.lookup_item("where are my sneakers").item == "shoes"
    assert index.lookup_item("where is the garbage bag").item == "garbage bag"
    assert index.lookup_item("keys in the kitchen").room == "kitchen"


def test_unknown_word_stays_gated() -> None:
    index = DictionaryIndex.seeded()
    slots = index.lookup_item("where is my qwarrion")
    assert slots.item is None
    assert slots.item_raw


def test_save_load_round_trip(tmp_path) -> None:
    index = DictionaryIndex()
    index.add_item("mug", ["cup", "coffee cup"])
    index.add_room("kitchen", ["cookhouse"])
    path = index.save(tmp_path / "dictionary.json")
    loaded = DictionaryIndex.load(path)
    assert loaded.lookup_item("where is my cup").item == "mug"
    assert loaded.lookup_room("in the cookhouse") == "kitchen"
