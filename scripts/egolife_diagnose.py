"""GT-assisted instance diagnostic for the EgoLife run (no GPU).

The frozen headline scores class-level queries: ``find_state("mug")`` returns
the most recently seen mug, which in a six-person house is usually a different
object from the one whose placement is the ground truth. This script answers a
different, explicitly oracle-assisted question: did the *specific instance*
placed at ``observed_at`` survive in the store until the ask day?

It never changes the frozen query bank or the headline score.
"""

from __future__ import annotations

import argparse
import json
from datetime import timedelta
from pathlib import Path
from typing import Any

from aegis.core.config import load_config
from aegis.core.timeutil import parse_iso
from aegis.evaluation.egolife import place_of
from aegis.memory.store import open_store


def closest_instance(
    store: Any, item: str, canonical: str, observed: Any, tolerance: int
):
    """Instance with a state run nearest the GT placement timestamp."""

    best = None
    for state in store.latest_states():
        if (
            state.get("canonical") != canonical
            and canonical not in str(state.get("label", "")).lower()
        ):
            continue
        for run in store.runs_for_instance(state["instance_id"]):
            start, end = parse_iso(run["start_at"]), parse_iso(run["end_at"])
            delta = min(abs(start - observed), abs(end - observed))
            if delta <= timedelta(seconds=tolerance) and (
                best is None or delta < best[0]
            ):
                best = (delta, state, run)
    return best


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-path", default="config/egolife.yaml")
    parser.add_argument("--home-id", default="egolife_jake_replay")
    parser.add_argument(
        "--bank", type=Path, default=Path("evaluation/annotations/egolife_queries.json")
    )
    parser.add_argument(
        "--out", type=Path, default=Path("outputs/evaluation/egolife_scored")
    )
    parser.add_argument("--tolerance", type=int, default=240, help="seconds")
    args = parser.parse_args(argv)

    config = load_config(args.config_path)
    vocab = config.vocab()
    bank = json.loads(args.bank.read_text(encoding="utf-8"))
    store = open_store(args.home_id, config.memory.store_root)
    results: list[dict[str, Any]] = []
    try:
        latest = {s["instance_id"]: s for s in store.latest_states()}
        for query in bank["queries"]:
            if not query.get("observed_at"):
                continue
            observed = parse_iso(query["observed_at"])
            entry = vocab.resolve_query(query["item"])
            canonical = entry.id if entry else query["item"]
            hit = closest_instance(
                store, query["item"], canonical, observed, args.tolerance
            )
            if hit is None:
                results.append({"id": query["id"], "instance_found": False})
                continue
            delta, state, run = hit
            results.append(
                {
                    "id": query["id"],
                    "item": query["item"],
                    "instance_found": True,
                    "instance_id": state["instance_id"],
                    "label": state["label"],
                    "match_delta_seconds": int(delta.total_seconds()),
                    "anchor_at_observation": place_of(
                        next(
                            (
                                a["label"]
                                for a in store.anchors()
                                if a["anchor_id"] == run["anchor_id"]
                            ),
                            None,
                        )
                    ),
                    "last_seen": state["last_seen_wallclock"],
                    "still_in_store": state["instance_id"] in latest,
                    "anchor_at_ask": state["anchor_label"],
                }
            )
    finally:
        store.close()

    found = [r for r in results if r["instance_found"]]
    retained = [r for r in found if r["still_in_store"]]
    summary = {
        "queries_with_gt_placement": len(results),
        "instance_matched": len(found),
        "instance_still_in_store_at_ask_day": len(retained),
        "placement_anchor_correct": sum(
            1
            for r in found
            if r["anchor_at_observation"]
            and any(
                noun in r["anchor_at_observation"]
                for noun in next(
                    q["expect_place"] for q in bank["queries"] if q["id"] == r["id"]
                )
            )
        ),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "instance_diagnostic.json").write_text(
        json.dumps({"summary": summary, "detail": results}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
