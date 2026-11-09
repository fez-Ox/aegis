"""End-to-end test of the Option A runner with synthetic ground truth."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from aegis.evaluation.run import run_evaluation


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )


def _entry(
    frame_id: int,
    timestamp: float,
    *,
    active: bool,
    anchor: str,
    relation: str,
    center: tuple[float, float, float],
    last_seen: float,
) -> dict[str, Any]:
    return {
        "frame_id": frame_id,
        "timestamp": timestamp,
        "instance_id": 1,
        "label": "Shoes #1 [Active Pair]",
        "center": list(center),
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


def _pose(frame_id: int, timestamp: float) -> dict[str, Any]:
    return {
        "frame_id": frame_id,
        "timestamp": timestamp,
        "filename": f"frame_{frame_id:06d}.png",
        "matrix": [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
    }


def test_run_evaluation_end_to_end(tmp_path: Path, monkeypatch) -> None:
    # Keep the API from accidentally reading repository fixtures.
    monkeypatch.setenv("AEGIS_TEST_FIXTURE_ROOT", str(tmp_path / "no-fixtures"))
    root = tmp_path / "workspace"
    annotations = root / "annotations"
    outputs = root / "outputs" / "synthetic"
    reports = root / "reports"

    footprint = [[-1, 0, -1], [1, 0, -1], [1, 0, 1], [-1, 0, 1]]
    graph = {
        "dataset_id": "synthetic",
        "schema_version": "test",
        "anchors": [
            {
                "anchor_id": 1,
                "label": "Storage Cabinet #1",
                "center": [0.0, 0.0, 0.0],
                "size": [0.5, 0.5, 0.5],
                "room_id": 1,
                "room_label": "Room #1",
            }
        ],
        "rooms": [
            {
                "room_id": 1,
                "label": "Room #1",
                "room_type": "Room",
                "centroid": [0.0, 0.0, 0.0],
                "footprint": footprint,
            }
        ],
        "timeline": {
            "0": [
                _entry(
                    0,
                    0.0,
                    active=True,
                    anchor="Floor Entrance",
                    relation="on_floor",
                    center=(0.0, 0.0, 0.2),
                    last_seen=0.0,
                )
            ],
            "1": [
                _entry(
                    1,
                    1.0,
                    active=True,
                    anchor="Floor Entrance",
                    relation="on_floor",
                    center=(0.0, 0.0, 0.2),
                    last_seen=1.0,
                )
            ],
            "2": [
                _entry(
                    2,
                    2.0,
                    active=False,
                    anchor="Storage Cabinet #1",
                    relation="inside",
                    center=(0.0, 0.0, 0.2),
                    last_seen=1.0,
                )
            ],
        },
        "events": [
            {
                "event_id": "event_0001",
                "event_type": "placement",
                "object": "Shoes #1 [Active Pair]",
                "instance_id": 1,
                "start_time": 1.0,
                "end_time": 1.5,
                "source_anchor": "Floor Entrance",
                "destination_anchor": "Storage Cabinet #1",
                "source_room": "Room #1",
                "destination_room": "Room #1",
                "source_relation": "on_floor",
                "destination_relation": "inside",
            }
        ],
    }
    _write_json(outputs / "objects" / "r4d_scene_graph.json", graph)
    _write_json(
        outputs / "objects" / "detected_objects_3d.json",
        {
            "dataset_id": "synthetic",
            "boxes_3d": [
                {
                    "frame_id": 0,
                    "label": "shoes",
                    "bbox_2d": [10, 10, 30, 30],
                    "track_id": 10,
                    "confidence": 0.95,
                },
                {
                    "frame_id": 1,
                    "label": "shoes",
                    "bbox_2d": [12, 10, 32, 30],
                    "track_id": 10,
                    "confidence": 0.90,
                },
            ],
        },
    )
    _write_json(
        outputs / "geometry" / "poses.json",
        {
            "dataset_id": "synthetic",
            "poses": [_pose(0, 0.0), _pose(1, 1.0), _pose(2, 2.0)],
        },
    )

    _write_jsonl(
        annotations / "detections.jsonl",
        [
            {
                "frame_id": 0,
                "objects": [
                    {
                        "label": "shoes",
                        "bbox": [10, 10, 30, 30],
                        "instance_id": 1,
                    }
                ],
            },
            {
                "frame_id": 1,
                "objects": [
                    {
                        "label": "shoes",
                        "bbox": [12, 10, 32, 30],
                        "instance_id": 1,
                    }
                ],
            },
        ],
    )
    _write_jsonl(
        annotations / "events.jsonl",
        [
            {
                "event_id": "e1",
                "event_type": "placement",
                "object": "shoes",
                "instance_id": 1,
                "start_time": 1.0,
                "end_time": 1.5,
                "source_anchor": "Floor Entrance",
                "destination_anchor": "Storage Cabinet #1",
                "source_room": "Room #1",
                "destination_room": "Room #1",
            }
        ],
    )
    _write_json(
        annotations / "rooms.json",
        {
            "rooms": [
                {
                    "room_id": 1,
                    "label": "Room #1",
                    "centroid": [0.0, 0.0, 0.0],
                    "footprint": footprint,
                }
            ],
            "frame_rooms": [
                {"frame_id": 0, "room_id": 1},
                {"frame_id": 2, "room_id": 1},
            ],
            "room_changes": [],
        },
    )
    _write_jsonl(
        annotations / "queries.jsonl",
        [
            {
                "query_id": "q1",
                "query": "Where are my shoes?",
                "expected_anchor": "Storage Cabinet #1",
                "expected_room": "Room #1",
                "expected_relation": "inside",
            },
            {
                "query_id": "q2",
                "query": "Where is my wallet?",
                "expected_found": False,
                "negative": True,
            },
        ],
    )
    _write_jsonl(
        annotations / "persistence.jsonl",
        [
            {
                "case_id": "p1",
                "query": "Where are my shoes?",
                "expected_instance_id": 1,
                "expected_label": "Shoes #1",
                "expected_anchor": "Storage Cabinet #1",
                "expected_room": "Room #1",
                "expected_relation": "inside",
                "check_frame": 2,
                "expect_persistent": True,
            }
        ],
    )

    config = {
        "dataset_id": "synthetic",
        "root": str(root),
        "annotations_dir": "annotations",
        "report_dir": "reports",
        "predictions": {
            "scene_graph": "outputs/synthetic/objects/r4d_scene_graph.json",
            "detections": "outputs/synthetic/objects/detected_objects_3d.json",
            "poses": "outputs/synthetic/geometry/poses.json",
        },
        "labels": {"aliases": {}, "exclude": []},
        "events": {"types": ["placement"], "type_aliases": {}},
        "query": {"mode": "graph", "latency_requests": 0},
        "leakage": {"enabled": True},
        "ablations": {"enabled": True},
        "report": {"title": "Aegis synthetic evaluation"},
    }
    config_path = root / "eval.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

    results = run_evaluation(config_path, output_dir=reports)

    assert results["status"] == "partial"
    assert results["detection"]["precision"] == 1.0
    assert results["detection"]["recall"] == 1.0
    assert results["tracking"]["idf1"] == 1.0
    assert results["events"]["f1"] == 1.0
    assert results["rooms"]["accuracy"] == 1.0
    assert results["persistence"]["state_recall"] == 1.0
    assert results["persistence"]["query_recall"] == 1.0
    assert results["queries"]["answer_accuracy"] == 1.0
    assert results["ablations"]["full"]["answer_accuracy"] == 1.0
    assert results["ablations"]["no_persistence"]["answer_accuracy"] < 1.0
    assert (reports / "summary.json").is_file()
    assert (reports / "summary.md").is_file()
    markdown = (reports / "summary.md").read_text(encoding="utf-8")
    assert "Aegis synthetic evaluation" in markdown
    assert "Detection precision" in markdown
    assert "PASS" in markdown
    assert any(
        item["name"] == "annotations/detections" and item["sha256"]
        for item in results["inputs"]
    )
