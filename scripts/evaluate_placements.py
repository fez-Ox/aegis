"""P6 (AC-04): last-known placement of known objects in a home store.

Ground truth JSON: [{"object": "keys", "anchor": "desk", "relation": "on_surface"}, ...]
(vocabulary ids; relation names from aegis.memory.relations).
Pass: accuracy >= 0.70 and duplicate_rate <= 0.20.

Usage:
    uv run python scripts/evaluate_placements.py --home-id home01 \
        --ground-truth data/placements.json --laptop ... --phone ...
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _evidence import add_common_arguments, run_header, write_result

from aegis.evaluation import placement_accuracy
from aegis.memory.store import open_store


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home-id", required=True)
    parser.add_argument("--store-root", default=None)
    parser.add_argument("--ground-truth", type=Path, required=True)
    add_common_arguments(parser)
    args = parser.parse_args()
    header = run_header(
        config_path=args.config_path,
        laptop=args.laptop,
        phone=args.phone,
        gpu=args.gpu,
        operator=args.operator,
    )
    store = open_store(args.home_id, args.store_root)
    try:
        result = placement_accuracy(
            store.latest_states(), json.loads(args.ground_truth.read_text())
        )
    finally:
        store.close()
    result["pass"] = bool(
        result["accuracy"] is not None
        and result["accuracy"] >= 0.70
        and result["duplicate_rate"] <= 0.20
    )
    write_result(
        args.out or Path("outputs/evaluation") / f"placements_{args.home_id}.json",
        header,
        result,
    )


if __name__ == "__main__":
    main()
