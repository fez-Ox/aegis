"""A/B harness for room segmentation and typing (AC-22 / SC9).

Ground truth in `evaluation/annotations/rooms_ground_truth.json` was written
from 12-frame contact sheets viewed manually for each video. All re-extraction
settings are generic (no dataset-specific radius or threshold).
"""

from __future__ import annotations

import argparse
import itertools
import json
from dataclasses import fields
from pathlib import Path
from typing import Any

from aegis.core.config import RoomMemoryConfig
from aegis.core.models import BoundingBox3D
from aegis.evaluation import room_metrics
from aegis.geometry.gravity import GravityFrame
from aegis.memory.rooms import extract_room_regions, room_for_point

GT = Path("evaluation/annotations/rooms_ground_truth.json")
OUTPUTS = Path("outputs")
KNOWN_BOX_FIELDS = {item.name for item in fields(BoundingBox3D)}


def load_dataset(
    dataset_id: str,
) -> tuple[dict[str, Any], list[BoundingBox3D], GravityFrame]:
    poses = json.loads((OUTPUTS / dataset_id / "geometry" / "poses.json").read_text())
    detections = json.loads(
        (OUTPUTS / dataset_id / "objects" / "detected_objects_3d.json").read_text()
    )
    boxes = [
        BoundingBox3D(
            **{key: value for key, value in box.items() if key in KNOWN_BOX_FIELDS}
        )
        for box in detections.get("boxes_3d", [])
    ]
    frame = GravityFrame.from_dict(detections.get("gravity"))
    return poses, boxes, frame


def transitions(values: list[int], times: list[float]) -> list[float]:
    return [
        times[index]
        for index in range(1, len(values))
        if values[index] != values[index - 1]
    ]


def evaluate(
    dataset_id: str,
    truth: dict[str, Any],
    params: dict[str, Any],
) -> dict[str, Any]:
    poses, boxes, frame = load_dataset(dataset_id)
    regions = extract_room_regions(poses["poses"], boxes, gravity=frame, **params)
    positions = poses["poses"]
    times = [float(item.get("timestamp") or 0.0) for item in positions]
    predicted_rooms: list[int | None] = []
    for item in positions:
        matrix = item.get("matrix")
        if matrix is None:
            predicted_rooms.append(None)
            continue
        import numpy as np

        position = np.asarray(matrix, dtype=float)[:3, 3]
        region = room_for_point(position, regions, gravity=frame)
        predicted_rooms.append(region.room_id if region else None)

    metrics = room_metrics(
        list(zip(times, predicted_rooms, strict=True)),
        truth["rooms"],
        transitions(predicted_rooms, times),
        [item["t"] for item in truth["transitions"]],
    )
    # Typing: for each truth interval, what fraction of keyframes land in a
    # region whose room_type matches the truth room name?
    typed_hits = typed_total = 0
    for room in truth["rooms"]:
        for start, end in room["intervals"]:
            for timestamp, predicted in zip(times, predicted_rooms, strict=True):
                if not start <= timestamp < end or predicted is None:
                    continue
                region = next((r for r in regions if r.room_id == predicted), None)
                typed_total += 1
                if region and region.room_type.lower() == room["name"].lower():
                    typed_hits += 1
    metrics["typing_accuracy"] = (
        round(typed_hits / typed_total, 4) if typed_total else None
    )
    metrics["regions"] = len(regions)
    metrics["labels"] = [region.label for region in regions]
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=Path("outputs/evaluation/room_bench.json")
    )
    args = parser.parse_args()

    truth = json.loads(GT.read_text())["datasets"]
    grid = [
        {
            "zone_link_radius": radius,
            "min_zone_keyframes": min_kf,
            "landmark_radius": landmark,
        }
        for radius, min_kf, landmark in itertools.product(
            (0.5, 1.0, 1.5, 2.5, 4.0),
            (1, 2, 3, 5),
            (None, 2.0, 3.0, 5.0),
        )
    ]
    grid += [
        {
            "zone_link_radius": radius,
            "min_zone_keyframes": min_kf,
            "landmark_min_votes": 2,
            "landmark_min_confidence": 0.8,
            "landmark_distinct_instances": True,
            "merge_same_type": True,
        }
        for radius, min_kf in ((1.0, 2), (1.0, 3), (1.5, 2), (1.5, 3))
    ]
    grid += [
        {
            "zone_link_radius": 2.5,
            "min_zone_keyframes": 3,
            "landmark_min_votes": 2,
            "landmark_min_confidence": 0.8,
            "landmark_distinct_instances": True,
            "doorway_step": step,
            "merge_same_type": True,
        }
        for step in (0.8, 1.0, 1.2)
    ]
    grid += [
        {
            "zone_link_radius": 2.5,
            "min_zone_keyframes": 3,
            "landmark_min_votes": 2,
            "landmark_min_confidence": 0.8,
            "landmark_distinct_instances": True,
            "doorway_step": step,
        }
        for step in (0.6, 0.8, 1.0, 1.2, 1.5)
    ]
    grid += [
        {
            "zone_link_radius": radius,
            "min_zone_keyframes": 3,
            "landmark_min_votes": votes,
            "landmark_min_confidence": confidence,
            "landmark_distinct_instances": distinct,
        }
        for radius, votes, confidence, distinct in itertools.product(
            (1.5, 2.5), (1, 2, 3, 4), (0.0, 0.6, 0.8), (False, True)
        )
    ]
    defaults = RoomMemoryConfig()
    shipped = {
        "zone_link_radius": defaults.zone_link_radius,
        "min_zone_keyframes": defaults.min_zone_keyframes,
        "landmark_min_votes": defaults.landmark_min_votes,
        "landmark_min_confidence": defaults.landmark_min_confidence,
        "landmark_distinct_instances": defaults.landmark_distinct_instances,
    }
    grid.insert(0, shipped)
    report: dict[str, Any] = {"variants": {}}
    for params in grid:
        key = "r{}_k{}".format(
            params["zone_link_radius"], params["min_zone_keyframes"]
        ) + "".join(
            f"_{name}{value}"
            for name, value in params.items()
            if name not in {"zone_link_radius", "min_zone_keyframes"}
        )
        results = {}
        for dataset_id, dataset_truth in truth.items():
            if not (OUTPUTS / dataset_id / "geometry" / "poses.json").exists():
                continue
            results[dataset_id] = evaluate(dataset_id, dataset_truth, params)
        report["variants"][key] = {"params": params, "results": results}

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {args.out} ({len(grid)} variants)")


if __name__ == "__main__":
    main()
