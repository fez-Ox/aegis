"""Tests for the interactive terminal application (NL Querying/app.py)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

FOLDER_ROOT = Path(__file__).resolve().parents[1]
if str(FOLDER_ROOT) not in sys.path:
    sys.path.insert(0, str(FOLDER_ROOT))

import app
from nlq.dictionary import DictionaryIndex
from nlq.engine import AskResult, Intent


def test_app_help_flag() -> None:
    with pytest.raises(SystemExit) as exc:
        app.main(["--help"])
    assert exc.value.code == 0


def test_app_ask_flag_local_dataset(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = app.main(
        [
            "--ask",
            "where is my water bottle",
            "--dataset",
            "Demo06-Self",
            "--transport",
            "local",
            "--no-llm",
        ]
    )
    assert exit_code == 0


def test_vocab_search_summary(capsys: pytest.CaptureFixture[str]) -> None:
    dictionary = DictionaryIndex.seeded()
    app.display_vocab_search(dictionary, None)
    app.display_vocab_search(dictionary, "laptop")
    app.display_vocab_search(dictionary, "nonexistentxyz123")


def test_display_answer_found() -> None:
    res = AskResult(
        query="where is my laptop",
        intent=Intent.LOCATE,
        found=True,
        abstained=False,
        abstain_reason=None,
        answer_text="Your laptop is on Desk #1.",
        item="laptop",
        instance_label="Laptop #1",
        anchor_label="Desk #1",
        room_label="Bedroom",
        relation="on_surface",
        last_seen_timestamp=10.0,
        other_instances=[],
        suggestions=[],
        llm_used=False,
    )
    app.display_answer(res)


def test_display_answer_abstained() -> None:
    res = AskResult(
        query="where is my hovercraft",
        intent=Intent.UNKNOWN,
        found=False,
        abstained=True,
        abstain_reason="item_not_in_dictionary",
        answer_text="I don't know that item.",
        item=None,
        instance_label=None,
        anchor_label=None,
        room_label=None,
        relation=None,
        last_seen_timestamp=None,
        other_instances=[],
        suggestions=["hoverboard"],
        llm_used=False,
    )
    app.display_answer(res)
