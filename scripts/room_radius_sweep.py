"""Generic room-radius sweep across every dataset with hand-labelled room GT."""

from __future__ import annotations

import argparse
import json
from dataclasses import fields
from pathlib import Path
from typing import Any

import numpy as np

from aegis.core.models import BoundingBox3D
from aegis.evaluation import room_metrics
from aegis.geometry.gravity import GravityFrame
from aegis.memory.rooms import extract_room_regions, room_for_point

OUTPUTS = Path("outputs")
GT_FILES = (
    "evaluation/annotations/rooms_ground_truth.json",
    "evaluation/annotations/mid_eval_long_gt.json",
)
KNOWN = {item.name for item in fields(BoundingBox3D)}


def load_data(dataset_id: str) -> dict[str, Any]:
    base = OUTPUTS / dataset_id
    poses = json.loads((base / "geometry" / "poses.json").read_text())
    detections = json.loads((base / "objects" / "detected_objects_3d.json").read_text())
    return {
        "poses": poses["poses"],
        "boxes": [
            BoundingBox3D(**{k: v for k, v in box.items() if k in KNOWN})
            for box in detections.get("boxes_3d", [])
        ],
        "gravity": GravityFrame.from_dict(detections.get("gravity")),
    }


def score(
    data: dict[str, Any], truth: dict[str, Any], params: dict[str, Any]
) -> dict[str, Any]:
    regions = extract_room_regions(
        data["poses"],
        data["boxes"],
        gravity=data["gravity"],
        landmark_min_votes=2,
        landmark_min_confidence=0.8,
        landmark_distinct_instances=True,
        **params,
    )
    keyframes: list[tuple[float, int | None]] = []
    changes: list[float] = []
    for index, item in enumerate(data["poses"]):
        matrix = item.get("matrix")
        if matrix is None:
            continue
        position = np.asarray(matrix, dtype=float)[:3, 3]
        region = room_for_point(position, regions, gravity=data["gravity"])
        room_id = region.room_id if region else None
        keyframes.append((float(item.get("timestamp") or 0.0), room_id))
        if index and room_id != keyframes[-2][1]:
            changes.append(keyframes[-1][0])
    return room_metrics(
        keyframes,
        truth["rooms"],
        changes,
        [item["t"] for item in truth["transitions"]],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=Path("outputs/evaluation/room_radius_sweep.json")
    )
    args = parser.parse_args()

    truth_by_dataset: dict[str, Any] = {}
    for path in GT_FILES:
        document = json.loads(Path(path).read_text())
        for dataset_id, truth in document.get("datasets", {}).items():
            truth_by_dataset[dataset_id] = truth
        if "dataset_id" in document:
            truth_by_dataset[document["dataset_id"]] = document
    data = {name: load_data(name) for name in sorted(truth_by_dataset)}

    report: dict[str, Any] = {"variants": {}}
    for radius in (0.3, 0.5, 0.7, 1.0, 1.5, 2.5):
        params = {"zone_link_radius": radius}
        results = {
            name: score(dataset, truth_by_dataset[name], params)
            for name, dataset in data.items()
        }
        segs = [value["segmentation_accuracy"] or 0 for value in results.values()]
        recalls = [value["region_recall"] or 0 for value in results.values()]
        changes = [
            (value["room_change"] or {}).get("f1") or 0 for value in results.values()
        ]
        report["variants"][str(radius)] = {
            "params": params,
            "results": results,
            "mean": {
                "segmentation": round(sum(segs) / len(segs), 4),
                "region_recall": round(sum(recalls) / len(recalls), 4),
                "change_f1": round(sum(changes) / len(changes), 4),
            },
        }
        print(radius, report["variants"][str(radius)]["mean"])
        for name, value in results.items():
            print(
                "  ",
                name,
                "seg",
                value["segmentation_accuracy"],
                "regions",
                value["regions"] if "regions" in value else value["region_recall"],
                "change",
                value["room_change"]["f1"],
            )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
