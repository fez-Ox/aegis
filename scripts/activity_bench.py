"""Benchmark for activity/routine answers against caption-derived ground truth."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from aegis.remote.api import app

BANK = Path("evaluation/annotations/activity_queries.json")
HOME = "egolife_jake"


def contains(text: str, tokens: list[str]) -> bool:
    lowered = text.lower()
    return any(token.lower() in lowered for token in tokens)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=Path("outputs/evaluation/activity_bench.json")
    )
    args = parser.parse_args()

    bank = json.loads(BANK.read_text())["queries"]
    client = TestClient(app)
    rows: list[dict[str, Any]] = []
    for query in bank:
        response = client.get(
            "/api/v1/ask",
            params={
                "text": f"What did I do around {query['item']} time?",
                "home_id": HOME,
                "at": query["at"],
            },
        )
        body = response.json() if response.status_code == 200 else {}
        answer = body.get("answer") or ""
        rows.append(
            {
                "id": query["id"],
                "status": response.status_code,
                "abstained": body.get("abstained"),
                "answer": answer,
                "object_match": contains(answer, query["expect_tokens"]),
                "place_match": contains(answer, query["expect_place"]),
                "evidence_count": len(body.get("evidence") or []),
            }
        )
    summary = {
        "n": len(rows),
        "answered": sum(not row["abstained"] for row in rows),
        "object_match": sum(row["object_match"] for row in rows),
        "place_match": sum(row["place_match"] for row in rows),
        "with_evidence": sum(row["evidence_count"] > 0 for row in rows),
    }
    report = {"summary": summary, "rows": rows}
    print(summary)
    for row in rows[:3]:
        print(" ", row["id"], str(row["answer"])[:110])

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
