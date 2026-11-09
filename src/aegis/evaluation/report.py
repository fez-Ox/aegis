"""Human-readable and machine-readable report generation."""

from __future__ import annotations

import platform
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from aegis.evaluation.io import write_json

COMPARATORS = {"gte": "≥", "lte": "≤"}


def _pct(value: Any, digits: int = 1) -> str:
    if value is None:
        return "—"
    return f"{float(value) * 100:.{digits}f}%"


def _number(value: Any, digits: int = 3) -> str:
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}"


def _ci(pair: Sequence[float] | None) -> str:
    if not pair:
        return ""
    return f"{_pct(pair[0])}–{_pct(pair[1])}"


def _table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    lines = [
        "| " + " | ".join(str(header) for header in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(lines)


def _section(results: dict[str, Any], name: str) -> dict[str, Any]:
    value = results.get(name)
    return value if isinstance(value, dict) else {}


def _available(section: dict[str, Any]) -> bool:
    return bool(section.get("available", False))


def build_scorecard(
    results: dict[str, Any], targets: dict[str, float]
) -> list[dict[str, Any]]:
    """Turn section metrics into a compact, verdict-bearing scorecard."""

    rows: list[dict[str, Any]] = []

    def add(
        claim: str,
        metric: str,
        value: Any,
        target_key: str,
        *,
        comparator: str = "gte",
        n: int | None = None,
        ci: Sequence[float] | None = None,
        note: str | None = None,
    ) -> None:
        target = targets.get(target_key)
        verdict = "NOT RUN"
        if value is not None and target is not None:
            passed = (
                float(value) >= target
                if comparator == "gte"
                else float(value) <= target
            )
            verdict = "PASS" if passed else "FAIL"
        rows.append(
            {
                "claim": claim,
                "metric": metric,
                "value": value,
                "target": target,
                "comparator": comparator,
                "n": n,
                "ci": list(ci) if ci else None,
                "verdict": verdict,
                "note": note,
            }
        )

    detection = _section(results, "detection")
    if _available(detection):
        counts = detection.get("counts", {})
        add(
            "Finds the right objects",
            "Detection precision",
            detection.get("precision"),
            "detection_precision",
            n=counts.get("true_positives", 0) + counts.get("false_positives", 0),
            ci=detection.get("precision_ci"),
        )
        add(
            "Does not miss objects",
            "Detection recall",
            detection.get("recall"),
            "detection_recall",
            n=counts.get("true_positives", 0) + counts.get("false_negatives", 0),
            ci=detection.get("recall_ci"),
        )
        add(
            "Balances misses and false alarms",
            "Detection F1",
            detection.get("f1"),
            "detection_f1",
            n=counts.get("ground_truth"),
        )

    tracking = _section(results, "tracking")
    if _available(tracking):
        counts = tracking.get("counts", {})
        add(
            "Keeps the same name on the same object",
            "IDF1",
            tracking.get("idf1"),
            "tracking_idf1",
            n=counts.get("ground_truth_detections"),
            note=f"{counts.get('id_switches', 0)} ID switches",
        )

    events = _section(results, "events")
    if _available(events):
        counts = events.get("counts", {})
        add(
            "Detects pickups and placements at the right time",
            "Event F1",
            events.get("f1"),
            "event_f1",
            n=counts.get("ground_truth"),
            ci=events.get("recall_ci"),
        )

    rooms = _section(results, "rooms")
    if _available(rooms):
        counts = rooms.get("counts", {})
        add(
            "Knows which room it is in",
            "Room accuracy",
            rooms.get("accuracy"),
            "room_accuracy",
            n=counts.get("evaluated_frames"),
            ci=rooms.get("accuracy_ci"),
        )
        room_change = rooms.get("room_change", {})
        if room_change.get("available"):
            add(
                "Detects room transitions",
                "Room-change F1",
                room_change.get("f1"),
                "room_change_f1",
                n=room_change.get("counts", {}).get("ground_truth"),
            )

    persistence = _section(results, "persistence")
    if _available(persistence):
        counts = persistence.get("counts", {})
        add(
            "Remembers an object after it is hidden",
            "Persistence state recall",
            persistence.get("state_recall"),
            "persistence_state_recall",
            n=counts.get("total"),
            ci=persistence.get("state_recall_ci"),
        )
        add(
            "Answers correctly from remembered state",
            "Persistence query recall",
            persistence.get("query_recall"),
            "persistence_query_recall",
            n=counts.get("total"),
            ci=persistence.get("query_recall_ci"),
        )

    queries = _section(results, "queries")
    if _available(queries):
        counts = queries.get("counts", {})
        add(
            "Answers held-out questions correctly",
            "Grounded answer accuracy",
            queries.get("answer_accuracy"),
            "query_accuracy",
            n=counts.get("total"),
            ci=queries.get("answer_accuracy_ci"),
            note=(
                f"{counts.get('false_found', 0)} false-found, "
                f"{counts.get('false_not_found', 0)} false-not-found"
            ),
        )

    leakage = _section(results, "leakage")
    if leakage.get("cases"):
        add(
            "Does not use another dataset's memory",
            "Cross-dataset leakage",
            leakage.get("leakage_rate"),
            "leakage_rate",
            comparator="lte",
            n=leakage.get("cases"),
            note=f"{leakage.get('leaks', 0)} leaks in {leakage.get('cases', 0)} probes",
        )

    latency = _section(results, "latency")
    if latency.get("count"):
        add(
            "Answers quickly enough",
            "p95 latency",
            latency.get("p95_ms"),
            "latency_p95_ms",
            comparator="lte",
            n=latency.get("count"),
            note=f"p50 {latency.get('p50_ms', 0):.1f} ms",
        )
    return rows


def build_markdown(results: dict[str, Any]) -> str:
    """Render a panel-ready Markdown report from the result dictionary."""

    status = str(results.get("status", "unknown")).upper()
    lines: list[str] = [
        f"# {results.get('title', 'Aegis evaluation report')}",
        "",
        f"**Dataset:** `{results.get('dataset_id', '')}`  ",
        f"**Generated:** {results.get('generated_at', '')}  ",
        f"**Status:** {status}",
        "",
    ]
    if results.get("status") == "not_ready":
        lines.extend(_readiness_section(results))
        return "\n".join(lines).rstrip() + "\n"

    missing = results.get("skipped_sections", [])
    if missing:
        lines.append(
            "> Some sections were skipped because annotations or artifacts were "
            "not present. Skipped sections are shown as NOT RUN; they are not "
            "silently scored as zero."
        )
        lines.append("")

    scorecard = results.get("scorecard", [])
    lines.extend(["## 1. Scorecard", ""])
    rows = []
    for row in scorecard:
        target = row.get("target")
        target_text = (
            "—"
            if target is None
            else (
                f"{_pct(target)}"
                if row.get("comparator") == "lte" and row["metric"] != "p95 latency"
                else f"{_number(target, 2)}"
            )
        )
        value_text = _number(row.get("value")) if row.get("value") is not None else "—"
        if row.get("metric") in {
            "Detection precision",
            "Detection recall",
            "Detection F1",
            "Event F1",
            "Room accuracy",
            "Room-change F1",
            "Persistence state recall",
            "Persistence query recall",
            "Grounded answer accuracy",
            "Cross-dataset leakage",
        }:
            value_text = _pct(row.get("value"))
            target_text = _pct(target) if target is not None else "—"
        if row.get("metric") == "p95 latency":
            value_text = (
                f"{float(row['value']):.1f} ms" if row.get("value") is not None else "—"
            )
            target_text = f"≤ {target:.0f} ms" if target is not None else "—"
        elif row.get("comparator") == "lte" and target is not None:
            target_text = f"≤ {_pct(target)}"
        ci = _ci(row.get("ci"))
        rows.append(
            [
                row.get("claim", ""),
                row.get("metric", ""),
                f"{value_text}{(' (' + ci + ')') if ci else ''}",
                target_text,
                row.get("verdict", ""),
                row.get("n", "—"),
                row.get("note") or "",
            ]
        )
    lines.append(
        _table(
            ["Claim", "Metric", "Result", "Target", "Verdict", "n", "Note"],
            rows,
        )
    )
    lines.append("")

    inputs = results.get("inputs", [])
    if inputs:
        lines.extend(["## 2. Inputs and readiness", ""])
        lines.append(
            _table(
                ["Input", "Path", "Present", "SHA-256 (short)"],
                [
                    [
                        item.get("name", ""),
                        f"`{item.get('path', '')}`",
                        "yes" if item.get("exists") else "NO",
                        (item.get("sha256") or "")[:12] or "—",
                    ]
                    for item in inputs
                ],
            )
        )
        lines.append("")

    detection = _section(results, "detection")
    lines.extend(["## 3. Object detection", ""])
    if _available(detection):
        lines.append(
            f"Box IoU threshold **{detection.get('iou_threshold')}**, class-aware matching. "
            f"Micro precision {_pct(detection.get('precision'))}, recall "
            f"{_pct(detection.get('recall'))}, F1 {_pct(detection.get('f1'))}; "
            f"macro F1 {_pct(detection.get('macro_f1'))}. "
            f"mAP@0.5 {_number(detection.get('mean_average_precision'))}."
        )
        lines.append("")
        per_class = detection.get("per_class", {})
        lines.append(
            _table(
                [
                    "Class",
                    "GT",
                    "Pred",
                    "TP",
                    "FP",
                    "FN",
                    "Precision",
                    "Recall",
                    "F1",
                    "AP@0.5",
                ],
                [
                    [
                        label,
                        summary.get("counts", {}).get("ground_truth", 0),
                        summary.get("counts", {}).get("predictions", 0),
                        summary.get("counts", {}).get("true_positives", 0),
                        summary.get("counts", {}).get("false_positives", 0),
                        summary.get("counts", {}).get("false_negatives", 0),
                        _pct(summary.get("precision")),
                        _pct(summary.get("recall")),
                        _pct(summary.get("f1")),
                        _number(summary.get("average_precision")),
                    ]
                    for label, summary in sorted(per_class.items())
                ],
            )
        )
        lines.append("")
        mask = detection.get("mask_iou", {})
        if mask.get("available"):
            lines.append(
                f"Mask IoU: mean **{_number(mask.get('mean_iou'))}** over "
                f"{mask.get('count')} matched masks; "
                f"{_pct(mask.get('fraction_at_or_above_threshold'))} at or above "
                f"{mask.get('threshold')}."
            )
        else:
            lines.append(
                "Mask IoU was not scored: no matched pair had both a ground-truth "
                "and a predicted mask."
            )
        lines.append("")
    else:
        lines.extend([_skipped_text(detection), ""])

    tracking = _section(results, "tracking")
    lines.extend(["## 4. Identity and tracking", ""])
    if _available(tracking):
        counts = tracking.get("counts", {})
        lines.append(
            f"IDF1 **{_pct(tracking.get('idf1'))}**, MOTA "
            f"{_number(tracking.get('mota'))}, {counts.get('id_switches', 0)} ID "
            f"switches, {counts.get('fragmentation', 0)} track fragments across "
            f"{counts.get('gt_tracks', 0)} GT tracks."
        )
        lines.append("")
        lines.append(
            "> HOTA is not approximated here. The harness can export MOT rows so "
            "TrackEval can compute the full HOTA family independently."
        )
        lines.append("")
    else:
        lines.extend([_skipped_text(tracking), ""])

    events = _section(results, "events")
    lines.extend(["## 5. Events", ""])
    if _available(events):
        counts = events.get("counts", {})
        lines.append(
            f"Boundary tolerance ±{events.get('tolerance_s')} s. Precision "
            f"{_pct(events.get('precision'))}, recall {_pct(events.get('recall'))}, "
            f"F1 {_pct(events.get('f1'))} from {counts.get('ground_truth')} labelled "
            f"events."
        )
        lines.append("")
        failure_rows = []
        for event in events.get("false_negatives", [])[:5]:
            failure_rows.append(
                [
                    "missed event",
                    event.get("event_type"),
                    event.get("object"),
                    event.get("start_time"),
                ]
            )
        for event in events.get("false_positives", [])[:5]:
            failure_rows.append(
                [
                    "extra event",
                    event.get("event_type"),
                    event.get("object"),
                    event.get("start_time"),
                ]
            )
        if failure_rows:
            lines.append(
                _table(["Failure", "Type", "Object", "Time (s)"], failure_rows)
            )
            lines.append("")
    else:
        lines.extend([_skipped_text(events), ""])

    rooms = _section(results, "rooms")
    lines.extend(["## 6. Rooms", ""])
    if _available(rooms):
        counts = rooms.get("counts", {})
        lines.append(
            f"Per-keyframe room accuracy **{_pct(rooms.get('accuracy'))}** over "
            f"{counts.get('evaluated_frames')} frames "
            f"({counts.get('gt_rooms')} GT rooms, {counts.get('predicted_rooms')} "
            f"predicted rooms). Predicted room IDs were mapped onto GT IDs by "
            f"maximum frame agreement."
        )
        lines.append("")
        confusion = rooms.get("confusion", {})
        if confusion:
            predicted_labels = sorted(
                {label for row in confusion.values() for label in row}
            )
            lines.append(
                _table(
                    ["GT room"] + predicted_labels,
                    [
                        [gt] + [row.get(label, 0) for label in predicted_labels]
                        for gt, row in sorted(confusion.items())
                    ],
                )
            )
            lines.append("")
        regions = rooms.get("regions", {})
        if regions.get("available"):
            lines.append(
                f"Region containment recall {_pct(regions.get('region_recall'))}, "
                f"typed-region recall {_pct(regions.get('typed_region_recall'))}, "
                f"region precision {_pct(regions.get('region_precision'))}."
            )
            lines.append("")
        room_change = rooms.get("room_change", {})
        if room_change.get("available"):
            lines.append(
                f"Room-change events: precision {_pct(room_change.get('precision'))}, "
                f"recall {_pct(room_change.get('recall'))}, F1 "
                f"{_pct(room_change.get('f1'))} (±{room_change.get('tolerance_s')} s)."
            )
            lines.append("")
    else:
        lines.extend([_skipped_text(rooms), ""])

    persistence = _section(results, "persistence")
    lines.extend(["## 7. Object permanence and persistence", ""])
    if _available(persistence):
        counts = persistence.get("counts", {})
        lines.append(
            f"State recall **{_pct(persistence.get('state_recall'))}**, query recall "
            f"**{_pct(persistence.get('query_recall'))}**, identity consistency "
            f"{_pct(persistence.get('identity_consistency'))}, false-merge rate "
            f"{_pct(persistence.get('false_merge_rate'))} across "
            f"{counts.get('total')} labelled occlusion/relocation cases."
        )
        lines.append("")
        failures = persistence.get("failures", [])[:10]
        if failures:
            lines.append(
                _table(
                    ["Case", "Query", "Check frame", "State", "Query", "Reason"],
                    [
                        [
                            case.get("case_id"),
                            case.get("query"),
                            case.get("resolved_frame"),
                            "pass" if case.get("state_correct") else "FAIL",
                            "pass" if case.get("query_correct") else "FAIL",
                            case.get("failure_reason") or "",
                        ]
                        for case in failures
                    ],
                )
            )
            lines.append("")
    else:
        lines.extend([_skipped_text(persistence), ""])

    queries = _section(results, "queries")
    lines.extend(["## 8. Query answers", ""])
    if _available(queries):
        counts = queries.get("counts", {})
        lines.append(
            f"Grounded answer accuracy **{_pct(queries.get('answer_accuracy'))}** "
            f"({counts.get('grounded_correct')}/{counts.get('total')}); "
            f"found/not-found decision accuracy {_pct(queries.get('found_accuracy'))}. "
            f"False-found rate {_pct(queries.get('false_found_rate'))}, "
            f"false-not-found rate {_pct(queries.get('false_not_found_rate'))}."
        )
        lines.append("")
        failures = queries.get("failures", [])[:10]
        if failures:
            lines.append(
                _table(
                    ["ID", "Question", "Expected", "Actual", "Reason"],
                    [
                        [
                            item.get("query_id"),
                            item.get("query"),
                            _short_expected(item),
                            _short_actual(item),
                            item.get("failure_reason") or "",
                        ]
                        for item in failures
                    ],
                )
            )
            lines.append("")
    else:
        lines.extend([_skipped_text(queries), ""])

    latency = _section(results, "latency")
    leakage = _section(results, "leakage")
    lines.extend(["## 9. Latency and dataset isolation", ""])
    if latency.get("count"):
        lines.append(
            f"p50 **{latency.get('p50_ms', 0):.1f} ms**, p95 "
            f"**{latency.get('p95_ms', 0):.1f} ms**, max "
            f"{latency.get('max_ms', 0):.1f} ms over {latency.get('count')} requests "
            f"({latency.get('mode', 'in-process')})."
        )
    else:
        lines.append("Latency was not measured.")
    lines.append("")
    if leakage.get("cases"):
        lines.append(
            f"Cross-dataset probes: **{leakage.get('cases')}**, leaks: "
            f"**{leakage.get('leaks')}**, leakage rate "
            f"**{_pct(leakage.get('leakage_rate'))}**. Target must be 0%."
        )
        examples = leakage.get("examples", [])[:5]
        if examples:
            lines.append("")
            lines.append(
                _table(
                    ["Target dataset", "Probe", "Returned"],
                    [
                        [
                            example.get("target_dataset"),
                            example.get("probe"),
                            example.get("answer", {}).get("instance_label"),
                        ]
                        for example in examples
                    ],
                )
            )
        lines.append("")
    else:
        lines.append("Dataset isolation was not evaluated.")
        lines.append("")

    ablations = _section(results, "ablations")
    lines.extend(["## 10. Ablations", ""])
    if ablations:
        rows = []
        for name, values in ablations.items():
            rows.append(
                [
                    name,
                    _pct(values.get("answer_accuracy")),
                    _pct(values.get("found_accuracy")),
                    values.get("false_found", 0),
                    values.get("false_not_found", 0),
                    _pct(values.get("persistence_state_recall")),
                    _pct(values.get("persistence_query_recall")),
                ]
            )
        lines.append(
            _table(
                [
                    "Memory variant",
                    "Answer accuracy",
                    "Found accuracy",
                    "False found",
                    "False not-found",
                    "Persistence state",
                    "Persistence query",
                ],
                rows,
            )
        )
        lines.append("")
        lines.append(
            "Ablations are diagnostic, not proof by themselves: they show which "
            "memory component the score depends on. `no_memory` answers only from "
            "the final camera view; `no_persistence` drops remembered states that "
            "are not currently visible; `no_rooms` removes room grounding."
        )
        lines.append("")
    else:
        lines.append("Ablations were not run.")
        lines.append("")

    lines.extend(["## 11. Failure gallery", ""])
    gallery_rows = _failure_gallery(results)
    if gallery_rows:
        lines.append(_table(["Layer", "What happened"], gallery_rows))
    else:
        lines.append("No failure examples were recorded.")
    lines.append("")

    lines.extend(["## 12. Method and limitations", ""])
    lines.extend(
        [
            "- Ground truth must come from a human annotator or a physical measurement, not from this pipeline.",
            "- Boxes are matched class-aware at the configured IoU; tracking is scored with IDF1, ID switches, and fragmentation. HOTA is left to TrackEval.",
            "- 3D centre errors in the controlled-room experiment are **scale-aligned**. Monocular reconstruction is scale-ambiguous; do not read them as absolute metres unless the scale factor is near 1 and the protocol says so.",
            "- Confidence intervals are Wilson 95% intervals. They describe sampling uncertainty in the labelled cases, not annotation error.",
            "- This harness does not replace a usability study, clinical validation, or a public-benchmark comparison.",
        ]
    )
    lines.append("")

    provenance = results.get("provenance", {})
    if provenance:
        lines.extend(["## 13. Provenance", ""])
        lines.append(
            _table(
                ["Field", "Value"],
                [[key, value] for key, value in provenance.items()],
            )
        )
        lines.append("")

    lines.extend(["## 14. Reproduce", ""])
    lines.append("```bash")
    lines.append(
        results.get(
            "reproduce_command",
            "uv run python -m aegis.evaluation.run --config <config>",
        )
    )
    lines.append("```")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _skipped_text(section: dict[str, Any]) -> str:
    reason = section.get("reason") if section else "No section result was produced."
    return f"*Skipped:* {reason or 'inputs were not available.'}"


def _short_expected(item: dict[str, Any]) -> str:
    expected = item.get("expected", {})
    parts = [
        f"{key}={value}" for key, value in expected.items() if value not in (None, "")
    ]
    return "; ".join(parts) or "found"


def _short_actual(item: dict[str, Any]) -> str:
    actual = item.get("actual", {})
    return (
        f"{actual.get('instance_label') or 'not found'} / "
        f"{actual.get('anchor') or '—'} / {actual.get('room') or '—'} / "
        f"{actual.get('relation') or '—'}"
    )


def _failure_gallery(results: dict[str, Any]) -> list[list[str]]:
    rows: list[list[str]] = []
    detection = _section(results, "detection")
    for item in detection.get("false_negatives", [])[:4]:
        rows.append(
            [
                "detection",
                (
                    f"Missed `{item.get('label')}` at frame {item.get('frame_id')} "
                    f"(bbox {item.get('bbox')})"
                ),
            ]
        )
    for item in detection.get("false_positives", [])[:4]:
        rows.append(
            [
                "detection",
                (
                    f"Extra `{item.get('label')}` at frame {item.get('frame_id')} "
                    f"(bbox {item.get('bbox')}, confidence {item.get('confidence')})"
                ),
            ]
        )
    events = _section(results, "events")
    for item in events.get("false_negatives", [])[:3]:
        rows.append(
            [
                "events",
                (
                    f"Missed `{item.get('event_type')}` for `{item.get('object')}` "
                    f"at {item.get('start_time')} s"
                ),
            ]
        )
    for item in events.get("false_positives", [])[:3]:
        rows.append(
            [
                "events",
                (
                    f"Extra `{item.get('event_type')}` for `{item.get('object')}` "
                    f"at {item.get('start_time')} s"
                ),
            ]
        )
    queries = _section(results, "queries")
    for item in queries.get("failures", [])[:4]:
        rows.append(
            [
                "query",
                (
                    f"`{item.get('query')}` — {item.get('failure_reason')} "
                    f"(expected {_short_expected(item)}; got {_short_actual(item)})"
                ),
            ]
        )
    persistence = _section(results, "persistence")
    for item in persistence.get("failures", [])[:3]:
        rows.append(
            [
                "persistence",
                (
                    f"`{item.get('query')}` at frame {item.get('resolved_frame')}: "
                    f"{item.get('failure_reason')}"
                ),
            ]
        )
    return rows[:16]


def _readiness_section(results: dict[str, Any]) -> list[str]:
    lines = ["## Readiness", ""]
    lines.append(
        "This run did **not** produce accuracy scores. The harness refuses to "
        "invent ground truth: scores appear only after the annotation files exist."
    )
    lines.append("")
    missing = results.get("missing_inputs", [])
    if missing:
        lines.append(
            _table(
                ["Section", "Missing input", "What to do"],
                [
                    [
                        item.get("section", ""),
                        f"`{item.get('path', '')}`",
                        item.get("hint", ""),
                    ]
                    for item in missing
                ],
            )
        )
        lines.append("")
    lines.append("### Next steps")
    lines.append("")
    lines.append(
        "1. Copy the templates in `evaluation/templates/` into the annotation "
        "directory for this dataset."
    )
    lines.append(
        "2. Annotate the frozen test video. Do not tune the pipeline on it after "
        "this point."
    )
    lines.append(
        "3. Re-run the command in the readiness JSON. The report will replace "
        "this page with scored sections."
    )
    lines.append("")
    return lines


def write_report(results: dict[str, Any], output_dir: str | Path) -> dict[str, Path]:
    """Write ``summary.json`` and ``summary.md`` (plus readiness alias)."""

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    json_path = write_json(directory / "summary.json", results)
    markdown = build_markdown(results)
    markdown_path = directory / "summary.md"
    markdown_path.write_text(markdown, encoding="utf-8")
    paths = {"json": json_path, "markdown": markdown_path}
    if results.get("status") == "not_ready":
        readiness_path = directory / "readiness.md"
        readiness_path.write_text(markdown, encoding="utf-8")
        paths["readiness"] = readiness_path
    return paths


def runtime_metadata() -> dict[str, str]:
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }
