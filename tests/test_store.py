"""Tests for the SQLite home store."""

from __future__ import annotations

import sqlite3

import pytest

from aegis.memory.store import SCHEMA_VERSION, open_store


def test_schema_created_and_reopened(tmp_path) -> None:
    store = open_store("home01", tmp_path)
    assert store.counts()["session"] == 0
    store.close()
    again = open_store("home01", tmp_path)
    assert again.one("SELECT value FROM meta WHERE key='home_id'")[0] == "home01"
    again.close()


def test_unknown_schema_version_raises(tmp_path) -> None:
    store = open_store("home01", tmp_path)
    store.execute(f"PRAGMA user_version={SCHEMA_VERSION + 1}")
    store.close()
    with pytest.raises(RuntimeError, match="schema version"):
        open_store("home01", tmp_path)


def test_transaction_rolls_back_on_error(tmp_path) -> None:
    store = open_store("home01", tmp_path)
    with pytest.raises(sqlite3.IntegrityError), store.transaction():
        store.insert(
            "room",
            {
                "label": "Kitchen",
                "room_type": "Kitchen",
                "label_source": "auto",
                "signature": "[]",
                "created_at": "x",
                "updated_at": "x",
            },
        )
        store.insert(
            "room",
            {
                "label": "Bad",
                "room_type": "Room",
                "label_source": "invalid",
                "signature": "[]",
                "created_at": "x",
                "updated_at": "x",
            },
        )
    assert store.counts()["room"] == 0
    store.close()


def test_invalid_home_id_is_rejected(tmp_path) -> None:
    with pytest.raises(ValueError):
        open_store("../escape", tmp_path)
