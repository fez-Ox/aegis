"""P1/P2/P4: summarise a capture (soak, disconnect recovery, backlog).

Pass criteria (context/plan.md WP15):
  P1 soak:       wall duration >= 3600 s, effective received FPS >= 1, status not storage_error
  P2 disconnect: every disconnect resumes in <= 15 s and is recorded as a gap
  P4 backlog:    max_backlog_seconds <= 30 with the stall recorded

Usage:
    uv run python scripts/summarise_live_session.py captures/<session> \
        --laptop "..." --phone "Pixel 6, Android 14"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _evidence import add_common_arguments, run_header, write_result

from aegis.evaluation import summarise_live_session


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path)
    add_common_arguments(parser)
    args = parser.parse_args()
    header = run_header(
        config_path=args.config_path,
        laptop=args.laptop,
        phone=args.phone,
        gpu=args.gpu,
        operator=args.operator,
    )
    summary = summarise_live_session(args.session)
    summary["checks"] = {
        "soak_one_hour": bool(
            (summary["wall_duration_seconds"] or 0) >= 3600
            and (summary["effective_received_fps"] or 0) >= 1
            and summary["status"] != "storage_error"
        ),
        "disconnects_resume_within_15s": all(
            d["resume_seconds"] is not None and d["resume_seconds"] <= 15
            for d in summary["disconnects"]
        ),
        "backlog_within_30s": (summary["max_backlog_seconds"] or 0) <= 30,
    }
    out = args.out or Path("outputs/evaluation") / f"live_{args.session.name}.json"
    write_result(out, header, summary)


if __name__ == "__main__":
    main()
