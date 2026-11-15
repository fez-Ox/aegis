"""P3 (AC-02): were the scripted scene changes kept as keyframes?

Write the change times (seconds from the first frame) to
captures/<session>/scene_changes.json as [{"t": 12.0}, ...].

Usage:
    uv run python scripts/evaluate_keyframes.py captures/<session> --laptop ... --phone ...
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _evidence import add_common_arguments, run_header, write_result

from aegis.core.timeutil import parse_iso
from aegis.evaluation import keyframe_hits
from aegis.ingestion.contracts import read_live_index


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path)
    parser.add_argument("--window", type=float, default=2.0)
    add_common_arguments(parser)
    args = parser.parse_args()
    header = run_header(
        config_path=args.config_path,
        laptop=args.laptop,
        phone=args.phone,
        gpu=args.gpu,
        operator=args.operator,
    )
    frames = [
        r
        for r in read_live_index(args.session / "index.jsonl")
        if r.get("record_type", "frame") == "frame"
    ]
    origin = min(parse_iso(r["capture_timestamp"]) for r in frames)
    kept = [
        (parse_iso(r["capture_timestamp"]) - origin).total_seconds() for r in frames
    ]
    changes = [
        float(c["t"])
        for c in json.loads((args.session / "scene_changes.json").read_text())
    ]
    result = keyframe_hits(kept, changes, window=args.window)
    write_result(
        args.out or Path("outputs/evaluation") / f"keyframes_{args.session.name}.json",
        header,
        result,
    )


if __name__ == "__main__":
    main()
