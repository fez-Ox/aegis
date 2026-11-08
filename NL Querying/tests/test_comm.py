"""Tests for the communication layer (offline transport only, no network)."""

from __future__ import annotations

import sys
from pathlib import Path

FOLDER_ROOT = Path(__file__).resolve().parents[1]
if str(FOLDER_ROOT) not in sys.path:
    sys.path.insert(0, str(FOLDER_ROOT))

from comm.transports import (
    DatasetNotFoundError,
    LocalGraphSource,
    create_source,
    fold_latest_states,
)


def test_auto_transport_defaults_to_local_without_base_url() -> None:
    source = create_source()  # no env / args set in CI
    assert isinstance(source, LocalGraphSource)


def test_local_source_discovers_tracked_fixture_datasets() -> None:
    source = LocalGraphSource()
    datasets = source.list_datasets()
    assert "demo04" in datasets or "Demo06-Self" in datasets


def test_load_memory_returns_common_view() -> None:
    source = LocalGraphSource()
    datasets = source.list_datasets()
    assert datasets, "no offline artifacts available"
    memory = source.load_memory(datasets[0])
    assert {
        "dataset_id",
        "anchors",
        "rooms",
        "events",
        "latest_objects",
        "timeline_frames",
        "transport",
    }.issubset(memory)
    assert memory["transport"] == "local"


def test_missing_dataset_raises_cleanly() -> None:
    source = LocalGraphSource()
    try:
        source.load_memory("definitely-not-a-dataset")
    except DatasetNotFoundError as exc:
        assert "definitely-not-a-dataset" in str(exc)
    else:  # pragma: no cover - executed only when the guard fails
        raise AssertionError("expected DatasetNotFoundError")


def test_fold_latest_states_picks_last_frame_per_instance() -> None:
    graph = {
        "timeline": {
            "1": [{"instance_id": 7, "label": "Shoes #1", "frame_id": 1}],
            "10": [{"instance_id": 7, "label": "Shoes #1", "frame_id": 10}],
            "2": [{"instance_id": 8, "label": "Bottle #1", "frame_id": 2}],
        }
    }
    latest = fold_latest_states(graph)
    by_id = {obj["instance_id"]: obj for obj in latest}
    assert by_id[7]["frame_id"] == 10
