"""Score pickup/placement events against hand-labelled times (M6 decision).

Ground truth JSON: [{"object": "shoes", "pickup": 12.4, "putdown": 18.0}, ...]
with times in seconds from the start of the video. Events come from the
dataset's outputs/<id>/objects/events.json.

Decision rule (todo M6): if pickup recall < 0.7, evaluate a dedicated
hand-object detector; otherwise keep the open-vocabulary hand prompt.

Usage:
    uv run python scripts/evaluate_hand_contact.py --dataset-id demo01 \
        --ground-truth data/demo01/hand_events.json --tolerance 1.0
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aegis.evaluation import precision_recall


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--tolerance", type=float, default=1.0)
    parser.add_argument("--outputs", type=Path, default=Path("outputs"))
    args = parser.parse_args()

    events = json.loads(
        (args.outputs / args.dataset_id / "objects" / "events.json").read_text()
    )["events"]
    truth = json.loads(args.ground_truth.read_text())
    result = {}
    for kind, key in (("pickup", "pickup"), ("placement", "putdown")):
        predicted = [float(e["end_time"]) for e in events if e["event_type"] == kind]
        expected = [float(item[key]) for item in truth if item.get(key) is not None]
        result[kind] = precision_recall(predicted, expected, tolerance=args.tolerance)
    result["decision"] = (
        "evaluate a dedicated hand-object detector"
        if result["pickup"]["recall"] < 0.7
        else "keep the open-vocabulary hand prompt"
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
