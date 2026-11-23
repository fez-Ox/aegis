"""Run the EgoLife 7-day memory evaluation: process, ingest, score.

Each day contributes a contiguous window (default 12:00-13:00, the hour every
day has footage for). Segments are processed and ingested in chronological
order, so ``HomeStore.latest_states()`` is exactly "what the system knew at the
end of this day" -- no ``as_of`` parameter is needed, and the run also yields
an accuracy-vs-days curve.

    uv run python scripts/egolife_eval.py --days 1 --execute
    uv run python scripts/egolife_eval.py --days 1-7 --execute --cleanup

Without ``--execute`` it prints the plan and cost estimate only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx

from aegis.core.config import load_config
from aegis.evaluation.egolife import (
    Query,
    dataset_id,
    group_segments,
    parse_clip,
    score_bank,
    segment_start,
    select_window,
    snapshot,
    summarise,
)
from aegis.memory.store import home_dir, open_store

API = "https://huggingface.co/api/datasets/lmms-lab/EgoLife/tree/main"
DATA_VOLUME = "aegis-poc-data"
GPU_STAGES = {"vggt", "detect_and_lift"}
L4_USD_PER_HOUR = 0.80
# Measured on demo04 (117 keyframes): VGGT 2.00 s/kf + detect 0.55 s/kf.
SECONDS_PER_KEYFRAME = 2.55


def parse_days(text: str) -> list[int]:
    days: set[int] = set()
    for part in text.split(","):
        part = part.strip()
        if "-" in part:
            low, high = part.split("-", 1)
            days.update(range(int(low), int(high) + 1))
        elif part:
            days.add(int(part))
    return sorted(days)


def plan_segments(
    client: httpx.Client, participant: str, days: list[int], args: argparse.Namespace
) -> list[tuple[int, int, str, Any, int]]:
    """Return ``(day, index, dataset_id, start, clip_count)`` per segment."""

    plan: list[tuple[int, int, str, Any, int]] = []
    for day in days:
        response = client.get(f"{API}/{participant}/DAY{day}?recursive=true")
        response.raise_for_status()
        clips = []
        for item in response.json():
            if item.get("type") != "file":
                continue
            parsed = parse_clip(item["path"], int(item.get("size", 0)))
            if parsed is not None and parsed[0] == day:
                clips.append(parsed[1])
        window = select_window(clips, args.start, args.minutes)
        for index, segment in enumerate(
            group_segments(window, args.start, args.segment_minutes, min_clips=3)
        ):
            plan.append(
                (
                    day,
                    index,
                    dataset_id(day, index),
                    segment_start(day, segment[0].stamp, args.base_date),
                    len(segment),
                )
            )
    return plan


def segment_cost(dataset: str) -> dict[str, float]:
    """Read the per-stage timings the pipeline already wrote for this segment."""

    path = Path("outputs") / dataset / "benchmark_stats.json"
    if not path.exists():
        return {"gpu_hours": 0.0, "cpu_hours": 0.0}
    stages = json.loads(path.read_text(encoding="utf-8")).get("stages", {})
    gpu = sum(
        float(stage.get("elapsed_seconds", 0.0))
        for name, stage in stages.items()
        if name in GPU_STAGES
    )
    cpu = sum(
        float(stage.get("elapsed_seconds", 0.0))
        for name, stage in stages.items()
        if name not in GPU_STAGES
    )
    return {"gpu_hours": gpu / 3600.0, "cpu_hours": cpu / 3600.0}


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# EgoLife multi-day memory evaluation",
        "",
        (
            f"Participant: `{report['protocol']['participant']}` · "
            f"window: {report['protocol']['start']}+{report['protocol']['minutes']}m/day · "
            f"segments: {report['protocol']['segments']} · "
            f"keyframe interval: {report['protocol']['keyframe_seconds']}s"
        ),
        "",
        "| Day | Rooms | Anchors | Instances | Anchor match quality |",
        "|---|---|---|---|---|",
    ]
    for day in report["days"]:
        counts = day["snapshot"]["counts"]
        quality = ", ".join(
            f"{key}={value}"
            for key, value in sorted(day["snapshot"]["anchor_match_quality"].items())
        )
        lines.append(
            f"| {day['day']} | {counts.get('room', 0)} | {counts.get('anchor', 0)} "
            f"| {counts.get('instance', 0)} | {quality or '-'} |"
        )

    if report.get("queries"):
        lines += [
            "",
            "| Day | n | Present | Place | Present (24 h) | Place (24 h) |",
            "|---|---|---|---|---|---|",
        ]
        for day in report["days"]:
            scores = day.get("scores")
            if not scores:
                continue
            full = scores["summary"]
            recent = scores["last_24h"]
            lines.append(
                f"| {day['day']} | {full['n']} | "
                f"{_fmt(full['present'])} | {_fmt(full['place'])} | "
                f"{_fmt(recent['present'])} | {_fmt(recent['place'])} |"
            )

    cost = report["cost"]
    lines += [
        "",
        (
            f"Measured GPU time: {cost['gpu_hours']:.2f} h "
            f"(~${cost['usd']:.2f} at ${L4_USD_PER_HOUR}/h L4). "
            f"CPU time: {cost['cpu_hours']:.2f} h."
        ),
        "",
        (
            "Room and anchor counts should stay bounded as days accumulate. "
            "Linear growth means cross-day matching is creating new identities "
            "instead of recognising the same house."
        ),
        "",
    ]
    path.with_suffix(".md").write_text("\n".join(lines), encoding="utf-8")


def _fmt(rate: dict[str, Any]) -> str:
    if rate["accuracy"] is None:
        return "n/a"
    return f"{rate['correct']}/{rate['n']} ({rate['accuracy']:.0%})"


def _fmt_number(value: Any) -> str:
    return "n/a" if value is None or isinstance(value, str) else f"{value:.3f}"


def write_tier_report(path: Path, report: dict[str, Any]) -> None:
    """Write the tiered rescore as JSON plus a compact Markdown table."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# EgoLife tiered, as-of evaluation",
        "",
        (
            f"Bank SHA-256 `{report['bank_sha256']}` · tier sidecar "
            f"`{report['sidecar_sha256']}`"
        ),
        "",
        f"Store at scoring time: {report['counts']}",
        "",
        "| Ranker | Tier | n | Presence | Top-1 | R@3 | MRR | Ambiguity F1 | FCR | Crops | CuePrec | Temporal |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for mode, tiers in report["modes"].items():
        for tier, payload in tiers.items():
            summary = payload["summary"]
            if not summary["n"]:
                lines.append(
                    f"| {mode} | {tier} | 0 | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |"
                )
                continue
            ambiguity = summary["ambiguity_f1"]
            fcr = summary["false_confidence"]
            temporal = summary.get("temporal_index")
            if isinstance(temporal, dict):
                temporal_text = (
                    f"{temporal['correct']}/{temporal['n']} "
                    f"({temporal['accuracy']:.3f})"
                )
            else:
                temporal_text = "n/a"
            lines.append(
                f"| {mode} | {tier} | {summary['n']} | {_fmt(summary['present'])} "
                f"| {_fmt(summary['top1'])} | {_fmt_number(summary['recall_at_3'])} "
                f"| {_fmt_number(summary['mrr'])} "
                f"| {(ambiguity['f1'] if isinstance(ambiguity, dict) else ambiguity)} "
                f"| {(fcr['rate'] if isinstance(fcr, dict) else fcr)} "
                f"| {_fmt_number(summary['crop_rate'])} "
                f"| {_fmt_number(summary.get('cue_filter_precision'))} "
                f"| {temporal_text} |"
            )
    lines += [
        "",
        (
            "T1 is NOT RUN on EgoLife: there is no enrolled personal object or "
            "independent T1 ground truth. Visual-trait and activity cues are NOT "
            "IMPLEMENTED on this dataset: the captions have no per-instance labels."
        ),
        "",
    ]
    path.with_suffix(".md").write_text("\n".join(lines), encoding="utf-8")


def rescore(
    args: argparse.Namespace, config: Any, queries: list[Query], home_id: str
) -> int:
    """Score an existing store against all four tiers without re-ingesting."""

    from aegis.evaluation.egolife import (
        apply_tier_annotations,
        load_tier_sidecar,
        score_tiered_bank,
        summarise_tier,
    )
    from aegis.memory.personal import enrolled_instances

    if not args.sidecar.exists():
        raise FileNotFoundError(f"tier sidecar missing: {args.sidecar}")
    sidecar = load_tier_sidecar(args.sidecar, args.bank)
    annotated = apply_tier_annotations(queries, sidecar)
    modes = (
        ["recency_only", "salience", "full"] if args.ranker == "all" else [args.ranker]
    )

    store = open_store(home_id, config.memory.store_root)
    report: dict[str, Any] = {
        "protocol": {
            "home_id": home_id,
            "ranker_modes": modes,
            "scoring": "states_as_of(asked_at); T4 state_at(observed_at)",
        },
        "bank_sha256": hashlib.sha256(args.bank.read_bytes()).hexdigest(),
        "sidecar_sha256": hashlib.sha256(args.sidecar.read_bytes()).hexdigest(),
        "counts": store.counts(),
        "modes": {},
    }
    try:
        personal = enrolled_instances(store)
        for mode in modes:
            tiered = score_tiered_bank(
                store,
                annotated,
                config.vocab(),
                mode=mode,
                personal_ids=personal,
            )
            report["modes"][mode] = {
                tier: {"summary": summarise_tier(rows), "detail": rows}
                for tier, rows in tiered.items()
            }
        legacy = score_tiered_bank(
            store,
            annotated,
            config.vocab(),
            mode=modes[-1],
            personal_ids=personal,
            legacy_24h=True,
        )
        report["ablation_24h"] = {
            tier: {"summary": summarise_tier(rows), "detail": rows}
            for tier, rows in legacy.items()
        }
    finally:
        store.close()

    write_tier_report(args.tier_out / "report.json", report)
    print(f"Wrote {args.tier_out / 'report.json'} and report.md")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-path", default="config/egolife.yaml")
    parser.add_argument("--participant", default="A1_JAKE")
    parser.add_argument("--days", default="1-7")
    parser.add_argument("--start", default="12:00")
    parser.add_argument("--minutes", type=int, default=60)
    parser.add_argument("--segment-minutes", type=int, default=5)
    parser.add_argument("--base-date", default="2026-01-05")
    parser.add_argument("--home-id", default=None)
    parser.add_argument(
        "--bank", type=Path, default=Path("evaluation/annotations/egolife_queries.json")
    )
    parser.add_argument("--out", type=Path, default=Path("outputs/evaluation/egolife"))
    parser.add_argument("--execute", action="store_true", help="actually run Modal")
    parser.add_argument(
        "--cleanup", action="store_true", help="delete frames from the Volume"
    )
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="videos are already in the Modal volume (Modal-hosted fetch)",
    )
    parser.add_argument(
        "--replay",
        action="store_true",
        help="re-ingest downloaded graphs into a fresh store and score, no Modal",
    )
    parser.add_argument(
        "--rescore",
        action="store_true",
        help="score an existing store as-of each query time; no ingest, no Modal",
    )
    parser.add_argument(
        "--sidecar",
        type=Path,
        default=Path("evaluation/annotations/egolife_tiers.json"),
    )
    parser.add_argument(
        "--ranker",
        default="full",
        choices=("recency_only", "salience", "full", "all"),
    )
    parser.add_argument(
        "--tier-out",
        type=Path,
        default=Path("outputs/evaluation/egolife_scored_tiered"),
    )
    args = parser.parse_args(argv)

    config = load_config(args.config_path)
    home_id = args.home_id or config.memory.home_id
    active_home = f"{home_id}_replay" if args.replay else home_id
    bank_hash = (
        hashlib.sha256(args.bank.read_bytes()).hexdigest()
        if args.bank.exists()
        else None
    )
    queries = []
    if args.bank.exists():
        payload = json.loads(args.bank.read_text(encoding="utf-8"))
        queries = [Query(**item) for item in payload.get("queries", [])]

    if args.rescore:
        return rescore(args, config, queries, home_id)

    with httpx.Client(follow_redirects=True, timeout=120) as client:
        plan = plan_segments(client, args.participant, parse_days(args.days), args)

    keyframes = sum(item[4] for item in plan) * 30 // 3
    estimate = keyframes * SECONDS_PER_KEYFRAME / 3600.0 * L4_USD_PER_HOUR
    print(
        f"{len(plan)} segments, ~{keyframes} keyframes, estimated ~${estimate:.2f} GPU"
    )
    if not args.execute and not args.replay:
        for day, index, name, start, clips in plan:
            print(
                f"  DAY{day} s{index:02d} {name} from {start.isoformat()} "
                f"({clips} clips)"
            )
        print("Dry run. Add --execute to run Modal.")
        return 0

    if args.replay:
        fresh = home_dir(active_home, config.memory.store_root)
        if fresh.exists():
            shutil.rmtree(fresh)
        print(f"replaying {len(plan)} graphs into {active_home}")

    store = open_store(active_home, config.memory.store_root)
    report: dict[str, Any] = {
        "protocol": {
            "participant": args.participant,
            "start": args.start,
            "minutes": args.minutes,
            "segment_minutes": args.segment_minutes,
            "segments": len(plan),
            "keyframe_seconds": 3,
            "base_date": args.base_date,
        },
        "days": [],
        "queries": bool(queries),
        "bank_sha256": bank_hash,
        "ground_truth": "EgoLife DenseCaption SRT, 12:00 hour, A1_JAKE DAY1-7",
        "coverage": {
            str(day): {
                "segments": sum(1 for item in plan if item[0] == day),
                "clips": sum(item[4] for item in plan if item[0] == day),
            }
            for day in parse_days(args.days)
        },
        "cost": {"gpu_hours": 0.0, "cpu_hours": 0.0, "usd": 0.0},
    }
    cost = {"gpu_hours": 0.0, "cpu_hours": 0.0}

    try:
        for day in parse_days(args.days):
            for _, _, name, start, _clips in [item for item in plan if item[0] == day]:
                if args.replay:
                    graph = Path("outputs") / name / "objects" / "r4d_scene_graph.json"
                    if not graph.exists():
                        raise FileNotFoundError(
                            f"{graph} missing; wait for the run to produce it"
                        )
                    print(f"--- replay {name}")
                    subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "aegis.memory.cli",
                            "ingest",
                            str(graph),
                            "--config-path",
                            args.config_path,
                            "--home-id",
                            active_home,
                        ],
                        check=True,
                    )
                    measured = segment_cost(name)
                    cost["gpu_hours"] += measured["gpu_hours"]
                    cost["cpu_hours"] += measured["cpu_hours"]
                    continue
                video = Path("data") / name / "video.mp4"
                if not args.no_upload and not video.exists():
                    raise FileNotFoundError(
                        f"{video} missing; run scripts/egolife_fetch.py first"
                    )
                if args.skip_existing and store.get_session(name) is not None:
                    print(f"skip {name} (already ingested)")
                    continue
                print(f"--- {name} from {start.isoformat()}")
                command = [
                    sys.executable,
                    "run_pipeline.py",
                    "--config-path",
                    args.config_path,
                    "--dataset-id",
                    name,
                    "--recorded-at",
                    start.isoformat(),
                    "--stage",
                    "full",
                    "--home-id",
                    home_id,
                ]
                if args.no_upload:
                    command.append("--no-upload")
                else:
                    command.extend(["--video", str(video)])
                subprocess.run(command, check=True)
                measured = segment_cost(name)
                cost["gpu_hours"] += measured["gpu_hours"]
                cost["cpu_hours"] += measured["cpu_hours"]
                if args.cleanup:
                    subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "modal",
                            "volume",
                            "rm",
                            DATA_VOLUME,
                            f"{name}/frames",
                            "-r",
                        ],
                        check=False,
                    )

            day_queries = [query for query in queries if query.asked_day == day]
            scores = None
            if day_queries:
                scored = score_bank(store, day_queries, config.vocab())
                scores = {
                    "summary": summarise(scored["full"]),
                    "last_24h": summarise(scored["last_24h"]),
                    "detail": scored["full"],
                }
            report["days"].append(
                {
                    "day": day,
                    "snapshot": snapshot(store),
                    "scores": scores,
                }
            )
            (args.out / f"day{day}_states.json").parent.mkdir(
                parents=True, exist_ok=True
            )
            (args.out / f"day{day}_states.json").write_text(
                json.dumps(store.latest_states(), indent=2) + "\n", encoding="utf-8"
            )
    finally:
        store.close()

    report["cost"] = {
        **cost,
        "usd": round(cost["gpu_hours"] * L4_USD_PER_HOUR, 2),
    }
    write_report(args.out / "report.json", report)
    print(f"Wrote {args.out / 'report.json'} and report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
