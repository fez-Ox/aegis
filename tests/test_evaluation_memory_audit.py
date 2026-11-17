"""Tests for the memory-growth audit and run-length compaction prototype."""

from __future__ import annotations

from typing import Any

import pytest

from aegis.evaluation.memory_audit import (
    audit_graph,
    compact_graph,
    decompress_graph,
    evaluate_compaction,
    latest_graph,
)
from aegis.evaluation.schema import QuerySpec


def _entry(
    frame_id: int,
    timestamp: float,
    instance_id: int,
    label: str,
    anchor: str,
    relation: str,
    center: list[float],
    *,
    active: bool,
    last_seen: float,
) -> dict[str, Any]:
    return {
        "frame_id": frame_id,
        "timestamp": timestamp,
        "instance_id": instance_id,
        "label": label,
        "center": center,
        "size": [0.2, 0.1, 0.1],
        "anchor_id": 1,
        "anchor_label": anchor,
        "relative_vector": [0.0, 0.0, 0.1],
        "relative_distance": 0.1,
        "relation": relation,
        "is_active_view": active,
        "last_seen_timestamp": last_seen,
        "is_in_hand": False,
        "carrier": None,
        "room_id": 1,
        "room_label": "Room #1",
    }


def _timeline_graph() -> dict[str, Any]:
    timeline: dict[str, list[dict[str, Any]]] = {}
    for frame in range(5):
        timestamp = float(frame)
        entries = [
            _entry(
                frame,
                timestamp,
                1,
                "Shoes #1 [Active Pair]",
                "Floor Entrance" if frame < 2 else "Storage Cabinet #1",
                "on_floor" if frame < 2 else "inside",
                [0.0, 0.0, 0.2],
                active=frame < 2,
                last_seen=float(min(frame, 1)),
            ),
            _entry(
                frame,
                timestamp,
                2,
                "Keys #1",
                "Desk #1",
                "on_surface",
                [0.1 * frame, 0.0, 0.5],
                active=True,
                last_seen=timestamp,
            ),
        ]
        timeline[str(frame)] = entries
    return {
        "dataset_id": "synthetic_timeline",
        "anchors": [],
        "rooms": [{"room_id": 1, "label": "Room #1"}],
        "events": [],
        "timeline": timeline,
    }


def test_audit_graph_counts_state_runs() -> None:
    audit = audit_graph(_timeline_graph())
    assert audit["frames"] == 5
    assert audit["entries"] == 10
    assert audit["instances"] == 2
    assert audit["state_runs"] == 3
    assert audit["duration_s"] == pytest.approx(4.0)
    assert audit["projection"]["original_bytes_24h"] > 0


def test_compaction_preserves_semantic_state_and_latest_state() -> None:
    queries = [
        QuerySpec(
            query_id="q1",
            query="Where are my shoes?",
            expected_anchor="Storage Cabinet #1",
            expected_room="Room #1",
            expected_relation="inside",
        ),
        QuerySpec(
            query_id="q2",
            query="Where are my keys?",
            expected_anchor="Desk #1",
            expected_room="Room #1",
            expected_relation="on_surface",
        ),
        QuerySpec(
            query_id="q3",
            query="Where is my wallet?",
            expected_found=False,
            negative=True,
        ),
    ]
    evaluation = evaluate_compaction(
        _timeline_graph(), snapshot_interval=0, queries=queries
    )
    assert evaluation["counts"]["state_runs"] == 3
    assert evaluation["state_retention"]["full"] == pytest.approx(1.0)
    assert evaluation["state_retention"]["semantic"] == pytest.approx(1.0)
    assert evaluation["state_retention"]["label"] == pytest.approx(1.0)
    assert evaluation["state_retention"]["active_view"] == pytest.approx(1.0)
    assert evaluation["center_error"]["max"] == pytest.approx(0.0, abs=1e-9)
    assert evaluation["latest_state"]["exact_semantic_rate"] == pytest.approx(1.0)
    assert evaluation["query_agreement"]["agreement_rate"] == pytest.approx(1.0)
    assert evaluation["bytes"]["compression_ratio"] > 1.0


def test_snapshots_reconstruct_geometry_and_roundtrip() -> None:
    graph = _timeline_graph()
    compacted = compact_graph(graph, snapshot_interval=2)
    assert set(compacted["snapshots"]) == {"0", "2", "4"}
    reconstructed = decompress_graph(compacted)
    assert sorted(reconstructed["timeline"], key=int) == ["0", "1", "2", "3", "4"]
    latest = latest_graph(compacted)
    assert len(latest["timeline"]["4"]) == 2
    labels = {entry["label"] for entry in latest["timeline"]["4"]}
    assert labels == {"Shoes #1 [Active Pair]", "Keys #1"}


def test_compaction_rejects_negative_interval() -> None:
    with pytest.raises(ValueError):
        compact_graph(_timeline_graph(), snapshot_interval=-1)
