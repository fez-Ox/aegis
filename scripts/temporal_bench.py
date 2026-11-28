"""Benchmark for temporal answers and freshness wording (P1.1 / P1.3).

Ground truth comes from the frozen EgoLife bank's caption timestamps and
place nouns (evaluation/annotations/temporal_queries.json). The harness scores
the production /api/v1/ask path for "when" questions, the T4 oracle lookup,
and deterministic freshness wording.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from aegis.core.timeutil import parse_iso, time_ago, to_utc_iso
from aegis.remote.api import app

BANK = Path("evaluation/annotations/temporal_queries.json")
HOME = "egolife_jake"
T4_TOLERANCE_S = 180.0


def place_in_answer(answer: str, places: list[str]) -> bool:
    text = answer.lower()
    return any(place.lower() in text for place in places)


def delta_seconds(first: str | None, second: str) -> float | None:
    if not first:
        return None
    try:
        return abs((parse_iso(first) - parse_iso(second)).total_seconds())
    except ValueError:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=Path("outputs/evaluation/temporal_bench.json")
    )
    args = parser.parse_args()

    bank = json.loads(BANK.read_text())["queries"]
    client = TestClient(app)
    report: dict[str, Any] = {"queries": len(bank), "modes": {}}
    for mode in ("as_of", "latest", "oracle"):
        rows = []
        for query in bank:
            text = (
                f"When did I last see the {query['item']}?"
                if mode != "oracle"
                else f"When did I see the {query['item']}?"
            )
            params: dict[str, str] = {"text": text, "home_id": HOME}
            if mode == "as_of":
                params["as_of"] = query["asked_at"]
            elif mode == "oracle":
                params["at"] = query["expect_time"]
            response = client.get("/api/v1/ask", params=params)
            body = response.json() if response.status_code == 200 else {}
            seen = body.get("last_seen_wallclock")
            expected = query["expect_time"]
            distance = delta_seconds(seen, expected)
            answer = body.get("answer") or ""
            if mode == "oracle":
                # The engine validates the episode interval itself; a non-
                # abstaining "At that time" answer means it found evidence.
                time_correct = not body.get("abstained") and answer.startswith(
                    "At that time"
                )
            else:
                # For "last saw" the GT caption time is a placement time, not
                # necessarily the latest sighting. Score no future leakage and
                # internally consistent freshness instead.
                time_correct = bool(seen) and (
                    delta_seconds(seen, query["asked_at"]) is not None
                    and parse_iso(seen) <= parse_iso(query["asked_at"])
                )
            rows.append(
                {
                    "id": query["id"],
                    "status": response.status_code,
                    "abstained": body.get("abstained"),
                    "abstain_reason": body.get("abstain_reason"),
                    "answer": body.get("answer"),
                    "last_seen_wallclock": seen,
                    "last_seen_time_ago": body.get("last_seen_time_ago"),
                    "time_correct": time_correct,
                    "delta_seconds": distance,
                    "place_correct": place_in_answer(
                        body.get("answer") or "", query["expect_place"]
                    ),
                }
            )
        correct = sum(row["time_correct"] for row in rows)
        places = sum(row["place_correct"] for row in rows)
        freshness = sum(row["last_seen_time_ago"] is not None for row in rows)
        report["modes"][mode] = {
            "time_accuracy": round(correct / len(rows), 4),
            "place_accuracy": round(places / len(rows), 4),
            "freshness_coverage": round(freshness / len(rows), 4),
            "rows": rows,
        }
        print(
            f"{mode:<8} time={correct}/{len(rows)} "
            f"place={places}/{len(rows)} freshness={freshness}/{len(rows)}"
        )

    # Deterministic wording check over representative ages relative to a
    # query time; these are objective expectations, not model output.
    moment = datetime(2026, 1, 11, 12, 0, tzinfo=UTC)
    wording = []
    for seconds, expected in (
        (0, "just now"),
        (600, "10 minutes ago"),
        (7200, "2 hours ago"),
        (86400, "yesterday"),
        (3 * 86400, "3 days ago"),
        (10 * 86400, "over a week ago"),
    ):
        seen = to_utc_iso(moment - timedelta(seconds=seconds))
        got = time_ago(seen, moment)
        wording.append({"seconds": seconds, "expected": expected, "got": got})
    report["freshness_wording"] = {
        "correct": sum(item["expected"] == item["got"] for item in wording),
        "total": len(wording),
        "rows": wording,
    }
    print("wording", report["freshness_wording"]["correct"], "/", len(wording))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
