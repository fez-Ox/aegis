"""End-to-end evaluation of the long unique session against hand-labelled GT."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from fastapi.testclient import TestClient

from aegis.core.config import RoomMemoryConfig
from aegis.evaluation import room_metrics
from aegis.geometry.gravity import GravityFrame
from aegis.memory.evidence import evidence_complete
from aegis.memory.rooms import extract_room_regions, room_for_point
from aegis.remote.api import app

GT = Path("evaluation/annotations/mid_eval_long_gt.json")
OUTPUTS = Path("outputs")
DATASET = "mid_eval_long"


def room_scores(graph: dict[str, Any], gt: dict[str, Any]) -> dict[str, Any]:
    poses = json.loads((OUTPUTS / DATASET / "geometry" / "poses.json").read_text())
    detections = json.loads(
        (OUTPUTS / DATASET / "objects" / "detected_objects_3d.json").read_text()
    )
    from dataclasses import fields

    from aegis.core.models import BoundingBox3D

    known = {item.name for item in fields(BoundingBox3D)}
    boxes = [
        BoundingBox3D(**{key: value for key, value in box.items() if key in known})
        for box in detections.get("boxes_3d", [])
    ]
    settings = RoomMemoryConfig()
    regions = extract_room_regions(
        poses["poses"],
        boxes,
        zone_link_radius=settings.zone_link_radius,
        min_zone_keyframes=settings.min_zone_keyframes,
        landmark_min_votes=settings.landmark_min_votes,
        landmark_min_confidence=settings.landmark_min_confidence,
        landmark_distinct_instances=settings.landmark_distinct_instances,
        gravity=GravityFrame.from_dict(detections.get("gravity")),
    )
    frame = GravityFrame.from_dict(detections.get("gravity"))
    keyframes: list[tuple[float, int | None]] = []
    for item in poses["poses"]:
        matrix = item.get("matrix")
        if matrix is None:
            continue
        position = np.asarray(matrix, dtype=float)[:3, 3]
        region = room_for_point(position, regions, gravity=frame)
        keyframes.append(
            (float(item.get("timestamp") or 0.0), region.room_id if region else None)
        )
    changes = [
        timestamp
        for index, (timestamp, room_id) in enumerate(keyframes)
        if index and room_id != keyframes[index - 1][1]
    ]
    metrics = room_metrics(
        keyframes,
        gt["rooms"],
        changes,
        [item["t"] for item in gt["transitions"]],
    )
    metrics["regions"] = [
        {
            "label": region.label,
            "type": region.room_type,
            "keyframes": region.keyframe_count,
        }
        for region in regions
    ]
    return metrics


def query_scores(gt: dict[str, Any]) -> dict[str, Any]:
    client = TestClient(app)
    rows = []
    for query in gt["queries"]:
        response = client.get(
            "/api/v1/query", params={"item": query["item"], "dataset_id": DATASET}
        )
        body = response.json() if response.status_code == 200 else {}
        answer_text = " ".join(
            str(body.get(key) or "")
            for key in ("anchor_label", "room_label", "location_summary")
        ).lower()
        places = query.get("expect_place") or []
        if places:
            correct = any(place.lower() in answer_text for place in places)
        else:
            correct = not body.get("found")
        evidence = body.get("evidence") or []
        rows.append(
            {
                "id": query["id"],
                "status": response.status_code,
                "found": bool(body.get("found")),
                "correct": correct,
                "resolution_mode": body.get("resolution_mode"),
                "evidence_complete": bool(evidence)
                and all(evidence_complete(record) for record in evidence),
            }
        )
    correct = sum(row["correct"] for row in rows)
    return {
        "accuracy": round(correct / len(rows), 4),
        "answered": sum(row["found"] for row in rows),
        "evidenced": sum(row["evidence_complete"] for row in rows),
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=Path("outputs/evaluation/mid_eval_report.json")
    )
    args = parser.parse_args()

    gt = json.loads(GT.read_text())
    graph = json.loads(
        (OUTPUTS / DATASET / "objects" / "r4d_scene_graph.json").read_text()
    )
    report: dict[str, Any] = {
        "dataset": DATASET,
        "duration": gt["duration"],
        "graph": {
            "rooms": len(graph.get("rooms", [])),
            "anchors": len(graph.get("anchors", [])),
            "instances": len(graph.get("latest_states", [])),
            "events": len(graph.get("events", [])),
        },
        "rooms": room_scores(graph, gt),
        "queries": query_scores(gt),
    }
    print(
        json.dumps({k: report[k] for k in ("graph", "rooms", "queries")}, indent=2)[
            :2000
        ]
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
