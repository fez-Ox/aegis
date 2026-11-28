"""Detailed per-segment diagnostics for the long unique-session stress run."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from aegis.core.config import RoomMemoryConfig
from aegis.memory.repository import latest_states_from_graph
from aegis.memory.rooms import extract_room_regions

OUTPUTS = Path("outputs")
DATASET = "mid_eval_long"


def percentile(values: list[float], value: float) -> float | None:
    if not values:
        return None
    return round(float(np.percentile(values, value)), 4)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=DATASET)
    args = parser.parse_args()

    base = OUTPUTS / args.dataset
    stats = json.loads((base / "benchmark_stats.json").read_text())
    detections = json.loads((base / "objects" / "detected_objects_3d.json").read_text())
    graph = json.loads((base / "objects" / "r4d_scene_graph.json").read_text())
    poses = json.loads((base / "geometry" / "poses.json").read_text())

    boxes = detections.get("boxes_3d", [])
    confidences = [float(box.get("confidence") or 0.0) for box in boxes]
    point_counts = [int(box.get("point_count") or 0) for box in boxes]
    sizes = [box.get("size") or [0, 0, 0] for box in boxes]
    tracks = {int(box.get("track_id", -1)) for box in boxes}
    positions = np.asarray(
        [np.asarray(pose["matrix"], dtype=float)[:3, 3] for pose in poses["poses"]],
        dtype=float,
    )
    steps = (
        np.linalg.norm(np.diff(positions, axis=0), axis=1) if len(positions) > 1 else []
    )

    from dataclasses import fields

    from aegis.core.models import BoundingBox3D

    known = {item.name for item in fields(BoundingBox3D)}
    box_objects = [
        BoundingBox3D(**{key: value for key, value in box.items() if key in known})
        for box in boxes
    ]
    settings = RoomMemoryConfig()
    regions = extract_room_regions(
        poses["poses"],
        box_objects,
        zone_link_radius=settings.zone_link_radius,
        min_zone_keyframes=settings.min_zone_keyframes,
        landmark_min_votes=settings.landmark_min_votes,
        landmark_min_confidence=settings.landmark_min_confidence,
        landmark_distinct_instances=settings.landmark_distinct_instances,
    )
    states = list(latest_states_from_graph(graph).values())

    report: dict[str, Any] = {
        "dataset": args.dataset,
        "timing": {
            name: stage.get("elapsed_seconds")
            for name, stage in sorted(stats.get("stages", {}).items())
        },
        "ingestion": {
            "duration_seconds": graph.get("session", {}).get("duration_seconds"),
            "keyframe_count": graph.get("session", {}).get("keyframe_count"),
            "frames": stats["stages"]["preprocess"].get("frame_count"),
            "sample_fps": stats["stages"]["preprocess"].get("throughput_fps"),
        },
        "vggt": {
            "poses": len(poses["poses"]),
            "trajectory_span_m": round(
                float(np.linalg.norm(positions.max(0) - positions.min(0))), 3
            )
            if len(positions)
            else None,
            "median_step_m": round(float(np.median(steps)), 4) if len(steps) else None,
            "max_step_m": round(float(steps.max()), 4) if len(steps) else None,
            "gravity_source": graph.get("gravity", {}).get("source"),
            "gravity_confidence": graph.get("gravity", {}).get("confidence"),
            "floor_inlier_ratio": graph.get("gravity", {}).get("inlier_ratio"),
            "camera_height_m": graph.get("gravity", {}).get("camera_height"),
        },
        "detection": {
            "detections_2d": detections.get("total_detections_2d"),
            "boxes_3d": len(boxes),
            "unique_tracks": len(tracks),
            "labels": dict(Counter(box.get("label") for box in boxes).most_common(15)),
            "confidence": {
                "mean": round(statistics.mean(confidences), 4),
                "p10": percentile(confidences, 10),
                "p50": percentile(confidences, 50),
                "p90": percentile(confidences, 90),
            },
            "points_per_box": {
                "mean": round(statistics.mean(point_counts), 2),
                "p10": percentile(point_counts, 10),
                "p50": percentile(point_counts, 50),
            },
            "box_volume_m3": {
                "mean": round(
                    statistics.mean(
                        float(size[0]) * float(size[1]) * float(size[2])
                        for size in sizes
                    ),
                    6,
                )
            },
            "spatial_states": dict(Counter(box.get("spatial_state") for box in boxes)),
        },
        "memory": {
            "rooms_predicted": [
                {
                    "label": region.label,
                    "type": region.room_type,
                    "keyframes": region.keyframe_count,
                    "evidence": region.evidence_labels,
                }
                for region in regions
            ],
            "anchors": [
                {
                    "label": anchor.get("label"),
                    "observations": anchor.get("observations_count"),
                }
                for anchor in graph.get("anchors", [])
            ],
            "instances": len(states),
            "instances_with_confidence": sum(
                state.get("confidence") is not None for state in states
            ),
            "instances_with_anchor": sum(
                state.get("anchor_id") is not None for state in states
            ),
            "state_runs": len(graph.get("state_runs", [])),
            "events": dict(
                Counter(event.get("event_type") for event in graph.get("events", []))
            ),
            "room_visits": len(graph.get("room_visits", [])),
        },
    }
    print(json.dumps(report, indent=2)[:6000])
    output = Path("outputs/evaluation/mid_eval_analysis.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
