"""P1.4 evidence coverage across every non-abstaining answer path."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from aegis.memory.evidence import evidence_complete
from aegis.remote.api import app

DATASETS = (
    "demo01_sam3",
    "demo_pots_sam3",
    "demo03_sam3",
    "demo04_sam3",
    "demo05_sam3",
    "stress_egolife_s00",
)
ASK_QUESTIONS = (
    "where are my shoes",
    "where is the cooking pot",
    "when did I last see my shoes",
    "what did I do this morning",
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=Path("outputs/evaluation/evidence_bench.json")
    )
    args = parser.parse_args()

    client = TestClient(app)
    rows: list[dict[str, Any]] = []
    for dataset_id in DATASETS:
        for item in ("shoes", "cooking pot", "basket", "toilet"):
            response = client.get(
                "/api/v1/query", params={"item": item, "dataset_id": dataset_id}
            )
            body = response.json() if response.status_code == 200 else {}
            rows.append(
                {
                    "path": "query",
                    "source": dataset_id,
                    "question": item,
                    "status": response.status_code,
                    "found": bool(body.get("found")),
                    "evidence": body.get("evidence") or [],
                }
            )
        for question in ASK_QUESTIONS:
            response = client.get(
                "/api/v1/ask", params={"text": question, "dataset_id": dataset_id}
            )
            body = response.json() if response.status_code == 200 else {}
            rows.append(
                {
                    "path": "ask",
                    "source": dataset_id,
                    "question": question,
                    "status": response.status_code,
                    "found": bool(body.get("found")),
                    "evidence": body.get("evidence") or [],
                }
            )
    for question, extra in (
        ("where is my mug", {}),
        ("when did I last see the mug", {"as_of": "2026-01-08T12:59:00Z"}),
        ("what did I do around then", {"at": "2026-01-07T12:05:45Z"}),
    ):
        response = client.get(
            "/api/v1/ask",
            params={"text": question, "home_id": "egolife_jake", **extra},
        )
        body = response.json() if response.status_code == 200 else {}
        rows.append(
            {
                "path": "ask_home",
                "source": "egolife_jake",
                "question": question,
                "status": response.status_code,
                "found": bool(body.get("found")),
                "evidence": body.get("evidence") or [],
            }
        )

    answered = [row for row in rows if row["found"]]
    complete = [
        row
        for row in answered
        if row["evidence"] and all(map(evidence_complete, row["evidence"]))
    ]
    summary = {
        "responses": len(rows),
        "non_abstaining": len(answered),
        "fully_evidenced": len(complete),
        "coverage": round(len(complete) / len(answered), 4) if answered else None,
        "http_errors": [row for row in rows if row["status"] != 200],
        "incomplete": [
            {
                "path": row["path"],
                "source": row["source"],
                "question": row["question"],
                "evidence": row["evidence"],
            }
            for row in answered
            if row not in complete
        ],
    }
    print(json.dumps({k: v for k, v in summary.items() if k != "incomplete"}, indent=2))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
