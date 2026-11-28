"""Controlled cross-session matching A/B benchmark.

Ground truth is exact by construction: a session is derived from a real scene
graph by applying a random similarity transform, renaming ids, perturbing room
signatures and appearance vectors, dropping some entries and adding distractors.
Every derived item therefore has a known true match (or None for new items).
Cross-video pairs are negative cases: nothing should match across different
homes. All tuned settings are generic.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import asdict
from pathlib import Path
from typing import Any

from aegis.core.config import MatchingConfig
from aegis.memory.matching import (
    AnchorInfo,
    InstanceInfo,
    RoomInfo,
    match_anchors,
    match_instances,
    match_rooms,
)

OUTPUTS = Path("outputs")
DATASETS = (
    "demo01_sam3",
    "demo_pots_sam3",
    "demo03_sam3",
    "demo04_sam3",
    "demo05_sam3",
    "stress_egolife_s00",
)


def horizontal(center: list[float]) -> tuple[float, float]:
    return (float(center[0]), float(center[2]))


def load_graph(dataset_id: str) -> dict[str, Any]:
    return json.loads(
        (OUTPUTS / dataset_id / "objects" / "r4d_scene_graph.json").read_text()
    )


def home_from_graph(graph: dict[str, Any]) -> dict[str, Any]:
    rooms = [
        RoomInfo(
            room["room_id"],
            room.get("room_type") or "Room",
            frozenset(room.get("evidence_labels") or ()),
        )
        for room in graph.get("rooms", [])
    ]
    instances = [
        InstanceInfo(
            state["instance_id"],
            state.get("canonical") or "object",
            state.get("relation"),
            state.get("anchor_id"),
            tuple(state["appearance"]) if state.get("appearance") else None,
            state.get("room_id"),
        )
        for state in graph.get("latest_states", [])
    ]
    residents: dict[int, set[str]] = {}
    for instance in instances:
        if instance.anchor_id is not None:
            residents.setdefault(instance.anchor_id, set()).add(instance.canonical)
    anchors = [
        AnchorInfo(
            anchor["anchor_id"],
            anchor["canonical"],
            anchor.get("room_id"),
            horizontal(anchor["center"]),
            frozenset(residents.get(anchor["anchor_id"], ())),
        )
        for anchor in graph.get("anchors", [])
    ]
    return {"rooms": rooms, "anchors": anchors, "instances": instances}


def derive_session(
    home: dict[str, Any], seed: int
) -> tuple[dict[str, Any], dict[str, dict[int, int | None]]]:
    rng = random.Random(seed)
    theta = rng.uniform(-math.pi, math.pi)
    scale = rng.uniform(0.8, 1.25)
    tx, ty = rng.uniform(-3, 3), rng.uniform(-3, 3)
    c, s = math.cos(theta), math.sin(theta)

    def transform(point: tuple[float, float]) -> tuple[float, float]:
        x, y = point
        return (scale * (c * x - s * y) + tx, scale * (s * x + c * y) + ty)

    truth: dict[str, dict[int, int | None]] = {
        "rooms": {},
        "anchors": {},
        "instances": {},
    }
    rooms = []
    room_id_map: dict[int | None, int | None] = {None: None}
    for index, room in enumerate(home["rooms"]):
        new_id = 100 + index
        signature = (
            frozenset(label for label in room.signature if rng.random() > 0.25)
            if room.signature
            else frozenset()
        )
        rooms.append(RoomInfo(new_id, room.room_type, signature))
        truth["rooms"][new_id] = room.room_id
        room_id_map[room.room_id] = new_id

    anchors = []
    anchor_id_map: dict[int | None, int | None] = {None: None}
    for index, anchor in enumerate(home["anchors"]):
        if rng.random() < 0.12:
            continue  # genuinely new anchor in this session
        new_id = 200 + index
        noise = (rng.gauss(0, 0.03), rng.gauss(0, 0.03))
        point = transform(anchor.position) if anchor.position else None
        if point:
            point = (point[0] + noise[0], point[1] + noise[1])
        anchors.append(
            AnchorInfo(
                new_id,
                anchor.canonical,
                room_id_map.get(anchor.room_id),
                point,
                anchor.residents,
            )
        )
        truth["anchors"][new_id] = anchor.anchor_id
        anchor_id_map[anchor.anchor_id] = new_id

    instances = []
    for index, instance in enumerate(home["instances"]):
        if rng.random() < 0.15:
            continue
        new_id = 300 + index
        appearance = instance.appearance
        if appearance and rng.random() < 0.5:
            appearance = tuple(value + rng.gauss(0, 0.02) for value in appearance)
        instances.append(
            InstanceInfo(
                new_id,
                instance.canonical,
                instance.relation,
                anchor_id_map.get(instance.anchor_id),
                appearance,
                room_id_map.get(instance.room_id),
            )
        )
        truth["instances"][new_id] = instance.instance_id

    # Distractors are new and must not match anything.
    for offset in range(2):
        new_id = 900 + offset
        anchors.append(
            AnchorInfo(new_id, "novel anchor", None, transform((offset + 4.0, 4.0)))
        )
        truth["anchors"][new_id] = None
        instances.append(InstanceInfo(new_id + 100, "novel object", None, None, None))
        truth["instances"][new_id + 100] = None
    return {"rooms": rooms, "anchors": anchors, "instances": instances}, truth


def score(predicted: dict[Any, Any], truth: dict[int, int | None]) -> dict[str, float]:
    true_positive = false_positive = false_negative = 0
    for key, expected in truth.items():
        got = predicted.get(key)
        if expected is None:
            if got is not None:
                false_positive += 1
        elif got == expected:
            true_positive += 1
        else:
            false_negative += 1
    precision = (
        true_positive / (true_positive + false_positive)
        if true_positive + false_positive
        else 0.0
    )
    recall = (
        true_positive / (true_positive + false_negative)
        if true_positive + false_negative
        else 0.0
    )
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": true_positive,
        "fp": false_positive,
        "fn": false_negative,
    }


def evaluate(
    home: dict[str, Any],
    session: dict[str, Any],
    truth: dict[str, dict[int, int | None]],
    config: MatchingConfig,
) -> dict[str, dict[str, float]]:
    room_map = match_rooms(
        session["rooms"],
        home["rooms"],
        min_similarity=config.room_min_similarity,
        min_margin=config.room_min_margin,
        min_overlap=config.room_min_overlap,
        pair_bare_rooms=config.room_pair_bare,
    )
    anchor_result = match_anchors(
        session["anchors"],
        home["anchors"],
        room_map,
        max_residual_fraction=config.anchor_max_residual_fraction,
    )
    anchor_map = lambda key: (
        anchor_result.mapping.get(key, (None, "new"))[0] if key is not None else None
    )
    instance_map = match_instances(
        session["instances"],
        home["instances"],
        anchor_map,
        room_map,
        appearance_threshold=config.appearance_threshold,
        appearance_margin=config.appearance_margin,
        singleton_requires_evidence=config.singleton_requires_evidence,
        carried_requires_appearance=config.carried_requires_appearance,
    )
    return {
        "rooms": score(room_map, truth["rooms"]),
        "anchors": score(
            {key: value[0] for key, value in anchor_result.mapping.items()},
            truth["anchors"],
        ),
        "instances": score(instance_map, truth["instances"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=Path("outputs/evaluation/matching_bench.json")
    )
    args = parser.parse_args()

    graphs = {name: home_from_graph(load_graph(name)) for name in DATASETS}
    scenarios: list[
        tuple[str, dict[str, Any], dict[str, Any], dict[str, dict[int, int | None]]]
    ] = []
    for name, home in graphs.items():
        for seed in (1, 2, 3):
            session, truth = derive_session(home, seed)
            scenarios.append((f"{name}_s{seed}", home, session, truth))
    # Cross-home negatives: a session from one video against another video's
    # home; every prediction should be None.
    for index, name in enumerate(DATASETS):
        other = graphs[DATASETS[(index + 1) % len(DATASETS)]]
        session, truth = derive_session(other, 7)
        truth = {
            level: {key: None for key in mapping} for level, mapping in truth.items()
        }
        scenarios.append((f"{name}_crosshome", graphs[name], session, truth))

    base = MatchingConfig()
    legacy = replace_config(
        base,
        room_pair_bare=False,
        singleton_requires_evidence=False,
        carried_requires_appearance=False,
        appearance_threshold=0.35,
    )
    variants: dict[str, MatchingConfig] = {
        "legacy": legacy,
        "baseline": base,
        "thresh25_only": replace_config(legacy, appearance_threshold=0.25),
        "pair_and_thresh": replace_config(
            legacy, room_pair_bare=True, appearance_threshold=0.25
        ),
        "strict_rooms": replace_config(
            base, room_min_similarity=0.7, room_min_overlap=2
        ),
        "loose_rooms": replace_config(
            base, room_min_similarity=0.35, room_min_margin=0.02
        ),
        "strict_appearance": replace_config(
            base, appearance_threshold=0.2, appearance_margin=0.2
        ),
        "loose_appearance": replace_config(
            base, appearance_threshold=0.5, appearance_margin=0.05
        ),
        "singleton_evidence": replace_config(base, singleton_requires_evidence=True),
        "carried_appearance": replace_config(base, carried_requires_appearance=True),
        "corroborated": replace_config(
            base,
            singleton_requires_evidence=True,
            carried_requires_appearance=True,
        ),
        "corr_margin15": replace_config(
            base,
            singleton_requires_evidence=True,
            carried_requires_appearance=True,
            appearance_margin=0.15,
        ),
        "corr_margin20": replace_config(
            base,
            singleton_requires_evidence=True,
            carried_requires_appearance=True,
            appearance_margin=0.2,
        ),
        "corr_thresh25": replace_config(
            base,
            singleton_requires_evidence=True,
            carried_requires_appearance=True,
            appearance_threshold=0.25,
        ),
        "corr_bare_pair": replace_config(
            base,
            singleton_requires_evidence=True,
            carried_requires_appearance=True,
            appearance_threshold=0.25,
            room_pair_bare=True,
        ),
        "corr_thresh30": replace_config(
            base,
            singleton_requires_evidence=True,
            carried_requires_appearance=True,
            appearance_threshold=0.3,
        ),
        "corroborated_loose_appearance": replace_config(
            base,
            singleton_requires_evidence=True,
            carried_requires_appearance=True,
            appearance_threshold=0.5,
            appearance_margin=0.05,
        ),
        "strict_all": replace_config(
            base,
            room_min_similarity=0.7,
            room_min_overlap=2,
            appearance_threshold=0.2,
            appearance_margin=0.2,
            anchor_max_residual_fraction=0.15,
            singleton_requires_evidence=True,
            carried_requires_appearance=True,
        ),
    }
    report: dict[str, Any] = {"scenarios": len(scenarios), "variants": {}}
    for variant_name, config in variants.items():
        results = {}
        for label, home, session, truth in scenarios:
            results[label] = evaluate(home, session, truth, config)
        report["variants"][variant_name] = {
            "config": asdict(config),
            "results": results,
        }
        summary = summarize(results)
        print(variant_name, summary)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {args.out}")


def replace_config(config: MatchingConfig, **changes: Any) -> MatchingConfig:
    from dataclasses import replace

    return replace(config, **changes)


def summarize(results: dict[str, dict[str, dict[str, float]]]) -> str:
    parts = []
    for level in ("rooms", "anchors", "instances"):
        values = [item[level] for item in results.values()]
        parts.append(
            f"{level} F1={sum(v['f1'] for v in values) / len(values):.3f} "
            f"FP={sum(v['fp'] for v in values)}"
        )
    return " ".join(parts)


if __name__ == "__main__":
    main()
