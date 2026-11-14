"""Measure home-store size over simulated days (AC-07, NFR-P3, FR4.4).

The event stream is SYNTHETIC (aegis.memory.synthetic): no video is involved.
It runs the real ingest and compaction code, so the curve shows how the
store grows with retention in place. The 'projected_old_timeline_bytes'
column is a projection of the previous per-keyframe JSON design (1.1 KB per
entry, measured on the demo04 fixture), not a measurement.

Usage:
    uv run python scripts/measure_store_growth.py --days 14 --objects 100 \
        --changes-per-day 1000 --sessions-per-day 144
"""

from __future__ import annotations

import argparse
import csv
import tempfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from aegis.core.config import RetentionConfig
from aegis.memory.compaction import compact, rollup
from aegis.memory.ingest import ingest_session
from aegis.memory.store import TABLES, open_store
from aegis.memory.synthetic import SyntheticHome

BYTES_PER_OLD_ENTRY = 1100  # measured on tests/fixtures/demo04 (294 KB / 268 entries)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--objects", type=int, default=100)
    parser.add_argument("--changes-per-day", type=int, default=1000)
    parser.add_argument("--sessions-per-day", type=int, default=144)
    parser.add_argument("--hours-per-day", type=float, default=12.0)
    parser.add_argument("--keyframes-per-second", type=float, default=0.5)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--out", type=Path, default=Path("outputs/evaluation/store_growth.csv")
    )
    args = parser.parse_args()

    retention = RetentionConfig()
    simulator = SyntheticHome(
        objects=args.objects,
        changes_per_day=args.changes_per_day,
        sessions_per_day=args.sessions_per_day,
        hours_per_day=args.hours_per_day,
        seed=args.seed,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    keyframes_per_day = args.hours_per_day * 3600 * args.keyframes_per_second
    with (
        tempfile.TemporaryDirectory() as root,
        args.out.open("w", newline="") as handle,
    ):
        store = open_store("growth", root)
        writer = csv.writer(handle)
        writer.writerow(
            [
                "day",
                "db_bytes",
                "summary_text_bytes",
                "projected_old_timeline_bytes",
                *TABLES,
            ]
        )
        for offset in range(args.days):
            day = date(2026, 1, 1) + timedelta(days=offset)
            for graph in simulator.sessions(day):
                ingest_session(store, graph)
            now = datetime(day.year, day.month, day.day, 23, 30, tzinfo=UTC)
            compact(store, now=now, config=retention)
            rollup(store, now=now, config=retention)
            counts = store.counts()
            text_bytes = int(
                store.one("SELECT COALESCE(SUM(LENGTH(text)), 0) FROM summary")[0]
            )
            projected = int(
                (offset + 1) * keyframes_per_day * args.objects * BYTES_PER_OLD_ENTRY
            )
            writer.writerow(
                [
                    offset + 1,
                    store.db_size_bytes(),
                    text_bytes,
                    projected,
                    *(counts[t] for t in TABLES),
                ]
            )
            handle.flush()
            print(
                f"day {offset + 1}: {store.db_size_bytes() / 1e6:.2f} MB, rows {counts}"
            )
        store.close()
    print(f"wrote {args.out}")
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return
    rows = list(csv.DictReader(args.out.open()))
    plt.plot([int(r["day"]) for r in rows], [int(r["db_bytes"]) / 1e6 for r in rows])
    plt.xlabel("simulated day")
    plt.ylabel("memory.db (MB)")
    plt.title("Home store size with 3-day retention (synthetic stream)")
    plt.savefig(args.out.with_suffix(".png"), dpi=120)


if __name__ == "__main__":
    main()
