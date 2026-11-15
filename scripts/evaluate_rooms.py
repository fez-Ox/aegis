"""P7 (AC-22, SC9): room segmentation, regions and room_change events.

Ground truth JSON (times in seconds from the dataset's first frame):
  {"rooms": [{"name": "Kitchen", "intervals": [[0.0, 41.5]]}, ...],
   "transitions": [{"t": 41.5}, ...]}
Targets: segmentation >= 0.90, room_change F1 >= 0.70. The correct-room
query rate is measured with the API after renaming rooms to the ground
truth names (see docs/evaluation_plan.md).

Usage:
    uv run python scripts/evaluate_rooms.py --dataset-id <id> \
        --ground-truth data/<id>/rooms_ground_truth.json --laptop ... --phone ...
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _evidence import add_common_arguments, run_header, write_result

from aegis.evaluation import room_metrics
from aegis.memory.rooms import RoomRegion, room_for_point


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--outputs", type=Path, default=Path("outputs"))
    parser.add_argument("--tolerance", type=float, default=1.0)
    add_common_arguments(parser)
    args = parser.parse_args()
    header = run_header(
        config_path=args.config_path,
        laptop=args.laptop,
        phone=args.phone,
        gpu=args.gpu,
        operator=args.operator,
    )

    base = args.outputs / args.dataset_id
    graph = json.loads((base / "objects" / "r4d_scene_graph.json").read_text())
    poses = json.loads((base / "geometry" / "poses.json").read_text())["poses"]
    from aegis.geometry.gravity import GravityFrame

    gravity = GravityFrame.from_dict(graph.get("gravity"))
    rooms = [
        RoomRegion(
            room_id=int(r["room_id"]),
            label=r["label"],
            room_type=r.get("room_type", "Room"),
            centroid=tuple(r["centroid"]),
            footprint=[tuple(p) for p in r.get("footprint", [])],
        )
        for r in graph.get("rooms", [])
    ]
    keyframes = []
    for pose in poses:
        room = room_for_point(
            [row[3] for row in pose["matrix"][:3]], rooms, gravity=gravity
        )
        keyframes.append((float(pose["timestamp"]), room.room_id if room else None))
    predicted_changes = [
        float(e["end_time"])
        for e in graph.get("events", [])
        if e["event_type"] == "room_change"
    ]
    truth = json.loads(args.ground_truth.read_text())
    result = room_metrics(
        keyframes,
        truth["rooms"],
        predicted_changes,
        [float(t["t"]) for t in truth.get("transitions", [])],
        tolerance=args.tolerance,
    )
    write_result(
        args.out or Path("outputs/evaluation") / f"rooms_{args.dataset_id}.json",
        header,
        result,
    )


if __name__ == "__main__":
    main()
