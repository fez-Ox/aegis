"""Tests for the curated closed home vocabulary."""

from __future__ import annotations

import sys
from pathlib import Path

FOLDER_ROOT = Path(__file__).resolve().parents[1]
if str(FOLDER_ROOT) not in sys.path:
    sys.path.insert(0, str(FOLDER_ROOT))
if str(FOLDER_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(FOLDER_ROOT / "scripts"))

from build_dictionary import build_index, load_home_vocabulary
from nlq.dictionary import DictionaryIndex


def test_curated_home_vocabulary_is_large_and_consistent() -> None:
    items, rooms = load_home_vocabulary()
    assert len(items) >= 300
    assert sum(len(synonyms) for synonyms in items.values()) >= 900
    assert len(rooms) >= 15

    owners: dict[str, str] = {}
    for canonical, synonyms in items.items():
        assert canonical == canonical.strip().lower()
        assert canonical
        for term in [canonical, *synonyms]:
            assert term == term.strip().lower()
            assert term
            previous = owners.get(term)
            assert previous in (None, canonical), (
                f"synonym {term!r} is owned by both {previous!r} and {canonical!r}"
            )
            owners[term] = canonical


def test_build_index_includes_curated_and_legacy_terms() -> None:
    index, counts = build_index()
    assert counts["home_vocabulary"] >= 300
    assert counts["pipeline_classes"] > 0
    assert len(index.item_synonyms) >= 300
    assert sum(len(value) for value in index.item_synonyms.values()) >= 1000

    expected = {
        "where is my cup": "cup",
        "where is my mug": "cup",
        "where is my pan": "frying pan",
        "where is my pants": "pants",
        "where is my notebook": "notebook",
        "where is my bag": "bag",
        "where are my shades": "sunglasses",
        "where is my telly": "television",
        "where is my trash can": "trash bin",
        "where is my prescription": "medicine",
        "where is my throw": "blanket",
        "where is my kettle": "kettle",
        "where is my vacuum cleaner": "vacuum cleaner",
        "where is my toothbrush": "toothbrush",
    }
    for query, canonical in expected.items():
        assert index.lookup_item(query).item == canonical, query


def test_seeded_dictionary_prefers_curated_aliases() -> None:
    index = DictionaryIndex.seeded()
    assert index.lookup_item("where is my cup").item == "cup"
    assert index.lookup_item("where is my pan").item == "frying pan"
    assert index.lookup_item("where is my notebook").item == "notebook"
    assert index.lookup_item("where is my bag").item == "bag"
    assert index.lookup_item("where are my glasses").item == "glasses"
    assert index.lookup_item("where is my drinking glass").item == "drinking glass"
    assert index.lookup_item("where are my sneakers").item == "shoes"
    assert index.lookup_item("keys in the kitchen").room == "kitchen"
