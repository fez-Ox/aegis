"""A/B harness for generic place-evidence ranking priors.

Two hand-labelled banks are scored: the five demo videos (15 queries, place
labels written from extracted frames) and EgoLife (17 frozen queries with
independent place and ambiguity labels). All tested settings are generic:
no query-, object- or dataset-specific rule.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from aegis.core.config import RankingConfig
from aegis.memory.reasoning import rank_candidates
from aegis.memory.repository import latest_states_from_graph

DEMO_BANK = Path("evaluation/annotations/demo_queries.json")
EGO_BANK = Path("evaluation/annotations/egolife_queries.json")
EGO_REPORT = Path("outputs/evaluation/egolife_scored_tiered/report.json")
OUTPUTS = Path("outputs")


def place_ok(places: list[str], candidate: dict[str, Any] | None) -> bool:
    if not candidate or not places:
        return False
    text = " ".join(
        str(candidate.get(key) or "")
        for key in ("anchor_label", "room_label", "relation")
    ).lower()
    return any(str(place).lower() in text for place in places)


def evaluate(rows: list[dict[str, Any]], config: RankingConfig) -> dict[str, Any]:
    direct = wrong = withheld = should = true_positive = 0
    per_group: dict[str, dict[str, int]] = {}
    for row in rows:
        states = row["states"]
        ranking = rank_candidates(states, row["item"], config=config)
        top = ranking["candidates"][0] if ranking["candidates"] else None
        good = place_ok(row["expect_place"], top)
        want_withhold = bool(row["ambiguity_expected"]) or not good
        withhold = ranking["resolution_mode"] in (
            "abstain",
            "disambiguate",
            "not_found",
        )
        group = row["group"]
        bucket = per_group.setdefault(
            group, {"direct": 0, "wrong": 0, "withheld": 0, "should": 0, "tp": 0}
        )
        bucket["direct"] += int(not withhold)
        bucket["wrong"] += int(not withhold and not good)
        bucket["withheld"] += int(withhold)
        bucket["should"] += int(want_withhold)
        bucket["tp"] += int(withhold and want_withhold)
        should += int(want_withhold)
        withheld += int(withhold)
        true_positive += int(withhold and want_withhold)
        if not withhold:
            direct += 1
            wrong += int(not good)

    def summarise(part: dict[str, int]) -> dict[str, Any]:
        precision = part["tp"] / part["withheld"] if part["withheld"] else 0.0
        recall = part["tp"] / part["should"] if part["should"] else 0.0
        f1 = (
            2 * precision * recall / (precision + recall) if precision + recall else 0.0
        )
        return {
            "direct": part["direct"],
            "wrong_direct": part["wrong"],
            "withhold_recall": round(recall, 4),
            "withhold_f1": round(f1, 4),
        }

    return {
        "overall": summarise(
            {
                "direct": direct,
                "wrong": wrong,
                "withheld": withheld,
                "should": should,
                "tp": true_positive,
            }
        ),
        "by_group": {key: summarise(part) for key, part in sorted(per_group.items())},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=Path("outputs/evaluation/place_evidence_bench.json")
    )
    args = parser.parse_args()

    demo = json.loads(DEMO_BANK.read_text())["queries"]
    rows: list[dict[str, Any]] = []
    for query in demo:
        graph = json.loads(
            (
                OUTPUTS / query["dataset_id"] / "objects" / "r4d_scene_graph.json"
            ).read_text()
        )
        states = list(latest_states_from_graph(graph).values())
        rows.append(
            {
                "group": query["dataset_id"],
                "item": query["item"],
                "states": states,
                "expect_place": query.get("expect_place") or [],
                "ambiguity_expected": query["ambiguity_expected"],
            }
        )

    ego_bank = {q["id"]: q for q in json.loads(EGO_BANK.read_text())["queries"]}
    report = json.loads(EGO_REPORT.read_text())
    for entry in report["modes"]["full"]["T2"]["detail"]:
        q = ego_bank[entry["id"]]
        rows.append(
            {
                "group": f"ego_day{q['asked_day']}",
                "item": q["item"],
                "states": entry["candidates"],
                "expect_place": q.get("expect_place") or [],
                "ambiguity_expected": bool(
                    json.loads(
                        Path("evaluation/annotations/egolife_tiers.json").read_text()
                    )["annotations"][entry["id"]]["ambiguity_expected"]
                ),
            }
        )

    base = RankingConfig()
    variants: dict[str, RankingConfig] = {
        "baseline": base,
        "anchorless_.3": replace(base, anchorless_penalty=0.3),
        "anchorless_.6": replace(base, anchorless_penalty=0.6),
        "carried_.5": replace(base, carried_penalty=0.5),
        "require_anchor": replace(base, require_anchor_for_direct=True),
        "both_.5": replace(
            base,
            anchorless_penalty=0.5,
            carried_penalty=0.5,
            require_anchor_for_direct=True,
        ),
    }
    output: dict[str, Any] = {"variants": {}}
    for name, config in variants.items():
        metrics = evaluate(rows, config)
        output["variants"][name] = {"config": asdict(config), "metrics": metrics}
        overall = metrics["overall"]
        print(
            f"{name:<16} direct={overall['direct']:2d} wrong={overall['wrong_direct']:2d} "
            f"recall={overall['withhold_recall']:.3f} F1={overall['withhold_f1']:.3f}"
        )
        for group, part in metrics["by_group"].items():
            if group.startswith("demo"):
                print(
                    f"  {group:<18} wrong={part['wrong_direct']} F1={part['withhold_f1']}"
                )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
