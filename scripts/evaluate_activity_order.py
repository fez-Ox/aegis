"""P8 (AC-05): scripted actions recovered in order with correct times.

Ground truth JSON: [{"object": "Keys", "type": "pickup", "t": 12.0}, ...]
with t in seconds from the dataset's first frame. Use a 2 s tolerance for
hand-noted times and keep it in the result. Target: >= 70% matched.

Usage:
    uv run python scripts/evaluate_activity_order.py --dataset-id <id> \
        --ground-truth data/<id>/actions.json --tolerance 2.0 --laptop ... --phone ...
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _evidence import add_common_arguments, run_header, write_result

from aegis.evaluation import ordered_matches


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--tolerance", type=float, default=2.0)
    parser.add_argument("--outputs", type=Path, default=Path("outputs"))
    add_common_arguments(parser)
    args = parser.parse_args()
    header = run_header(
        config_path=args.config_path,
        laptop=args.laptop,
        phone=args.phone,
        gpu=args.gpu,
        operator=args.operator,
    )
    events = json.loads(
        (args.outputs / args.dataset_id / "objects" / "events.json").read_text()
    )["events"]
    predicted = sorted(
        (
            (e["object"], e["event_type"], float(e["end_time"]))
            for e in events
            if e["event_type"] != "room_change"
        ),
        key=lambda item: item[2],
    )
    truth = [
        (t["object"], t["type"], float(t["t"]))
        for t in json.loads(args.ground_truth.read_text())
    ]
    hits = ordered_matches(predicted, truth, tolerance=args.tolerance)
    result = {
        "actions": len(truth),
        "matched_in_order": hits,
        "rate": round(hits / len(truth), 4) if truth else None,
        "tolerance_seconds": args.tolerance,
    }
    result["pass"] = bool(result["rate"] is not None and result["rate"] >= 0.70)
    write_result(
        args.out
        or Path("outputs/evaluation") / f"activity_order_{args.dataset_id}.json",
        header,
        result,
    )


if __name__ == "__main__":
    main()
