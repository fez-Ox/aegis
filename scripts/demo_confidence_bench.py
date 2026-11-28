"""Confidence/abstention A/B on hand-labelled queries from the five demo videos.

Ground truth in `evaluation/annotations/demo_queries.json` was written from
visual inspection of extracted frames, not from Aegis output. Each query is
scored against that video's R4DSG scene graph with the shipped benchmark
config and with the pre-change baseline; every setting is generic.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from aegis.core.config import ConfidenceConfig
from aegis.memory.reasoning import rank_candidates
from aegis.memory.repository import latest_states_from_graph

BANK = Path("evaluation/annotations/demo_queries.json")
OUTPUTS = Path("outputs")


def matches(states: list[dict[str, Any]], item: str) -> list[dict[str, Any]]:
    target = item.strip().lower()
    return [
        state
        for state in states
        if str(state.get("canonical") or "").lower() == target
        or (
            not state.get("canonical")
            and target in str(state.get("label") or "").lower()
        )
    ]


def place_correct(query: dict[str, Any], candidate: dict[str, Any] | None) -> bool:
    places = query.get("expect_place") or []
    if not candidate or not places:
        return False
    text = " ".join(
        str(candidate.get(key) or "")
        for key in ("anchor_label", "room_label", "relation")
    ).lower()
    return any(str(place).lower() in text for place in places)


def score(
    bank: list[dict[str, Any]],
    graphs: dict[str, dict[str, Any]],
    config: ConfidenceConfig,
) -> dict[str, Any]:
    direct = wrong = withheld = should = true_positive = 0
    by_video: dict[str, dict[str, Any]] = {}
    for query in bank:
        states = graphs[query["dataset_id"]]
        candidates = matches(states, query["item"])
        ranking = rank_candidates(candidates, query["item"], confidence_config=config)
        top = ranking["candidates"][0] if ranking["candidates"] else None
        correct = place_correct(query, top)
        want_withhold = bool(query["ambiguity_expected"]) or not correct
        should += int(want_withhold)
        withhold = ranking["resolution_mode"] in (
            "abstain",
            "disambiguate",
            "not_found",
        )
        withheld += int(withhold)
        true_positive += int(withhold and want_withhold)
        if not withhold:
            direct += 1
            wrong += int(not correct)

        video = query["dataset_id"]
        bucket = by_video.setdefault(
            video, {"direct": 0, "wrong": 0, "withheld": 0, "should": 0, "tp": 0}
        )
        bucket["direct"] += int(not withhold)
        bucket["wrong"] += int(not withhold and not correct)
        bucket["withheld"] += int(withhold)
        bucket["should"] += int(want_withhold)
        bucket["tp"] += int(withhold and want_withhold)

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
        "by_video": {name: summarise(part) for name, part in sorted(by_video.items())},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bank", type=Path, default=BANK)
    parser.add_argument("--outputs", type=Path, default=OUTPUTS)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    document = json.loads(args.bank.read_text())
    bank = document["queries"]
    if "dataset_id" in document:
        for query in bank:
            query.setdefault("dataset_id", document["dataset_id"])
    graphs: dict[str, list[dict[str, Any]]] = {}
    for dataset_id in sorted({query["dataset_id"] for query in bank}):
        graph = json.loads(
            (args.outputs / dataset_id / "objects" / "r4d_scene_graph.json").read_text()
        )
        graphs[dataset_id] = list(latest_states_from_graph(graph).values())

    base = ConfidenceConfig()
    variants = {
        "baseline": replace(base, abstain_below=0.0, uncertain_identity=1.0),
        "shipped": base,
    }
    report: dict[str, Any] = {
        "ground_truth": {"bank": str(args.bank), "queries": len(bank)},
        "variants": {},
    }
    for name, config in variants.items():
        report["variants"][name] = {
            "config": asdict(config),
            "metrics": score(bank, graphs, config),
        }
        metrics = report["variants"][name]["metrics"]["overall"]
        print(
            f"{name:<10} direct={metrics['direct']} wrong={metrics['wrong_direct']} "
            f"recall={metrics['withhold_recall']} F1={metrics['withhold_f1']}"
        )
        for video, part in report["variants"][name]["metrics"]["by_video"].items():
            print(
                f"  {video:<18} direct={part['direct']} wrong={part['wrong_direct']} F1={part['withhold_f1']}"
            )

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
