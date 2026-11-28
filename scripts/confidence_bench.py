"""A/B harness for answer confidence calibration and abstention (P1.2).

Consumes the frozen 17-query EgoLife bank, its independent ambiguity sidecar,
and a rescore report produced by::

    uv run python scripts/egolife_eval.py --home egolife_jake --rescore \
        --days 1-7 --ranker full

Ground truth is *not* derived from Aegis: `expect_place` comes from EgoLife
DenseCaption SRT files and `ambiguity_expected` from a manual caption pass.
Every tested setting is generic (no query-, object- or day-specific rule) and
must improve or hold every ask-day slice to be adopted.

The reported "withhold" class means the system must not give one confident
answer: either the place is wrong or the class is genuinely ambiguous.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from aegis.core.config import ConfidenceConfig
from aegis.core.timeutil import parse_iso
from aegis.memory.reasoning import calibrated_confidence

BANK = Path("evaluation/annotations/egolife_queries.json")
SIDECAR = Path("evaluation/annotations/egolife_tiers.json")
REPORT = Path("outputs/evaluation/egolife_scored_tiered/report.json")


def place_matches(query: dict[str, Any], candidate: dict[str, Any]) -> bool:
    text = (
        str(candidate.get("anchor_label") or "")
        + " "
        + str(candidate.get("room_label") or "")
    ).lower()
    return any(
        str(place).lower() in text for place in (query.get("expect_place") or [])
    )


def score(
    details: list[dict[str, Any]],
    queries: dict[str, dict[str, Any]],
    ambiguity: dict[str, dict[str, Any]],
    config: ConfidenceConfig,
) -> dict[str, Any]:
    direct = wrong = withheld = should = true_positive = 0
    confidences: list[float] = []
    for row in details:
        query = queries[row["id"]]
        candidates = row["candidates"]
        good = bool(candidates) and place_matches(query, candidates[0])
        should += int(not good or bool(ambiguity[row["id"]]["ambiguity_expected"]))

        reason = (
            calibrated_confidence(candidates[0], parse_iso(row["asked_at"]), config)[
                "reason"
            ]
            if candidates
            else "not_found"
        )
        # The shipped ranker already withholds on score-margin ambiguity.
        withhold = reason is not None or row["is_ambiguous"]
        withheld += int(withhold)
        true_positive += int(
            withhold and (not good or bool(ambiguity[row["id"]]["ambiguity_expected"]))
        )
        if not withhold:
            direct += 1
            wrong += int(not good)
            if candidates:
                confidences.append(
                    calibrated_confidence(
                        candidates[0], parse_iso(row["asked_at"]), config
                    )["score"]
                )

    precision = true_positive / withheld if withheld else 0.0
    recall = true_positive / should if should else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "n": len(details),
        "direct_answers": direct,
        "wrong_direct_answers": wrong,
        "false_confidence_rate": round(wrong / direct, 4) if direct else None,
        "withheld": withheld,
        "withhold_precision": round(precision, 4),
        "withhold_recall": round(recall, 4),
        "withhold_f1": round(f1, 4),
        "mean_answered_confidence": round(sum(confidences) / len(confidences), 4)
        if confidences
        else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bank", type=Path, default=BANK)
    parser.add_argument("--sidecar", type=Path, default=SIDECAR)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    queries = {
        item["id"]: item for item in json.loads(args.bank.read_text())["queries"]
    }
    ambiguity = json.loads(args.sidecar.read_text())["annotations"]
    report = json.loads(args.report.read_text())
    details = report["modes"]["full"]["T2"]["detail"]

    base = ConfidenceConfig()
    variants: dict[str, ConfidenceConfig] = {
        # Pre-change behaviour: no threshold abstention, no identity veto.
        "baseline": replace(base, abstain_below=0.0, uncertain_identity=1.0),
        "shipped": base,
        "soft_identity": replace(base, uncertain_identity=0.5),
        "strict_identity": replace(base, uncertain_identity=0.0),
        "high_threshold": replace(base, abstain_below=0.7),
    }
    days = sorted({queries[row["id"]]["asked_day"] for row in details})
    output: dict[str, Any] = {
        "ground_truth": {
            "bank_sha256": report["bank_sha256"],
            "sidecar_sha256": report["sidecar_sha256"],
            "queries": len(queries),
        },
        "variants": {},
    }
    for name, config in variants.items():
        overall = score(details, queries, ambiguity, config)
        by_day = {
            str(day): score(
                [row for row in details if queries[row["id"]]["asked_day"] == day],
                queries,
                ambiguity,
                config,
            )
            for day in days
        }
        output["variants"][name] = {
            "config": asdict(config),
            "metrics": overall,
            "by_day": by_day,
        }
        print(
            f"{name:<16} direct={overall['direct_answers']} "
            f"wrong={overall['wrong_direct_answers']} "
            f"withhold_F1={overall['withhold_f1']} "
            f"recall={overall['withhold_recall']}"
        )

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
        print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
