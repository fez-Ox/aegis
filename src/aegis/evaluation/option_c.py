"""Option C: an honest readiness assessment for an Ego4D benchmark comparison.

Option C is *not* silently claimed.  Before Aegis can report a public-benchmark
number, four things must be true: access is granted, the benchmark subset is
local, an adapter converts Ego4D annotations into Aegis queries, and the
scoring is validated against the official task definitions.

This module provides two useful pieces that are testable without the dataset:

* Ego4D-style temporal scoring for NLQ (natural-language query) windows and
  VQ2D (visual query 2D) tracks.  These are *readiness estimates*, not a
  replacement for the official Ego4D evaluation code.
* A weighted readiness scorecard that turns a checklist into go / conditional-go
  / no-go, with explicit blockers and effort estimates.

Usage::

    python -m aegis.evaluation.option_c \
        --facts evaluation/configs/option_c_facts.yaml \
        --output-dir evaluation/reports/option_c
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from aegis.evaluation.io import write_json

# ---------------------------------------------------------------------------
# Ego4D-style temporal scoring (readiness estimates)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class NLQAnnotation:
    """One natural-language query with its ground-truth temporal window."""

    query_id: str
    query: str
    start_time: float
    end_time: float

    @property
    def window(self) -> tuple[float, float]:
        return (self.start_time, self.end_time)


@dataclass(frozen=True, slots=True)
class NLQPrediction:
    """Predicted temporal window for one query."""

    query_id: str
    start_time: float
    end_time: float

    @property
    def window(self) -> tuple[float, float]:
        return (self.start_time, self.end_time)


@dataclass(frozen=True, slots=True)
class BoxObservation:
    """One 2D box at one timestamp (xyxy pixels)."""

    timestamp: float
    bbox: tuple[float, float, float, float]


def temporal_iou(first: tuple[float, float], second: tuple[float, float]) -> float:
    """Intersection-over-union of two ``[start, end]`` intervals."""

    first_start, first_end = sorted((float(first[0]), float(first[1])))
    second_start, second_end = sorted((float(second[0]), float(second[1])))
    intersection = max(0.0, min(first_end, second_end) - max(first_start, second_start))
    union = max(first_end, second_end) - min(first_start, second_start)
    return intersection / union if union > 0 else 0.0


def _xyxy(box: Sequence[float]) -> tuple[float, float, float, float]:
    values = tuple(float(value) for value in box)
    if len(values) == 4:
        return values  # type: ignore[return-value]
    raise ValueError("a box must contain four values")


def _box_iou(first: Sequence[float], second: Sequence[float]) -> float:
    ax1, ay1, ax2, ay2 = _xyxy(first)
    bx1, by1, bx2, by2 = _xyxy(second)
    inter_w = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    inter_h = max(0.0, min(ay2, by2) - max(ay1, by1))
    intersection = inter_w * inter_h
    union = (
        max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
        + max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
        - intersection
    )
    return intersection / union if union > 0 else 0.0


def score_nlq(
    annotations: Sequence[NLQAnnotation],
    predictions: Sequence[NLQPrediction],
    *,
    thresholds: Sequence[float] = (0.3, 0.5),
) -> dict[str, Any]:
    """Score NLQ temporal localisation with mean IoU and Recall@tIoU.

    Ego4D reports R@1 at temporal IoU 0.3 and 0.5.  This function implements
    exactly that computation for a set of (query, window) pairs.  It does not
    attempt the official leaderboard protocol, which also fixes query sampling
    and video splits.
    """

    by_query = {prediction.query_id: prediction for prediction in predictions}
    rows: list[dict[str, Any]] = []
    ious: list[float] = []
    missing = 0
    for annotation in annotations:
        prediction = by_query.get(annotation.query_id)
        if prediction is None:
            missing += 1
            iou = 0.0
        else:
            iou = temporal_iou(annotation.window, prediction.window)
        ious.append(iou)
        rows.append(
            {
                "query_id": annotation.query_id,
                "query": annotation.query,
                "ground_truth": list(annotation.window),
                "prediction": (
                    list(prediction.window) if prediction is not None else None
                ),
                "temporal_iou": iou,
                "hits": {str(threshold): iou >= threshold for threshold in thresholds},
            }
        )

    values = np.asarray(ious, dtype=np.float64) if ious else np.array([])
    total = len(annotations)
    recall = {
        str(threshold): (float(np.mean(values >= threshold)) if values.size else 0.0)
        for threshold in thresholds
    }
    return {
        "available": total > 0,
        "counts": {
            "queries": total,
            "predictions": len(predictions),
            "missing_predictions": missing,
        },
        "mean_temporal_iou": float(np.mean(values)) if values.size else None,
        "median_temporal_iou": float(np.median(values)) if values.size else None,
        "recall_at": recall,
        "queries": rows,
        "note": (
            "Ego4D-style readiness estimate. Official Ego4D metrics must be "
            "computed with the official evaluation code and official splits."
        ),
    }


def score_vq2d(
    ground_truth: Sequence[BoxObservation],
    predictions: Sequence[BoxObservation],
    *,
    iou_threshold: float = 0.5,
    time_tolerance_s: float = 0.5,
) -> dict[str, Any]:
    """Score a visual-query response track by timestamp-matched box IoU.

    The official VQ2D metric evaluates a predicted response track over the
    annotated clip.  This simplified check answers a narrower question: when
    the object is annotated, does Aegis's 2D grounding put a box on it?
    """

    if not ground_truth:
        return {"available": False, "reason": "No ground-truth VQ2D boxes."}
    if not predictions:
        return {
            "available": True,
            "counts": {
                "ground_truth_boxes": len(ground_truth),
                "predicted_boxes": 0,
                "matched_boxes": 0,
            },
            "presence_rate": 0.0,
            "mean_iou": 0.0,
            "fraction_at_or_above_threshold": 0.0,
            "iou_threshold": iou_threshold,
            "time_tolerance_s": time_tolerance_s,
            "note": "No predictions were supplied for this response track.",
        }

    sorted_predictions = sorted(predictions, key=lambda item: item.timestamp)
    rows: list[dict[str, Any]] = []
    matched_ious: list[float] = []
    present = 0
    for target in sorted(ground_truth, key=lambda item: item.timestamp):
        nearest = min(
            sorted_predictions,
            key=lambda item: abs(item.timestamp - target.timestamp),
        )
        within_tolerance = abs(nearest.timestamp - target.timestamp) <= time_tolerance_s
        iou = _box_iou(target.bbox, nearest.bbox) if within_tolerance else 0.0
        if within_tolerance:
            present += 1
            matched_ious.append(iou)
        rows.append(
            {
                "timestamp": target.timestamp,
                "matched_timestamp": nearest.timestamp,
                "within_tolerance": within_tolerance,
                "iou": iou,
                "passed": iou >= iou_threshold,
            }
        )

    values = (
        np.asarray(matched_ious, dtype=np.float64) if matched_ious else np.array([])
    )
    total = len(ground_truth)
    return {
        "available": True,
        "counts": {
            "ground_truth_boxes": total,
            "predicted_boxes": len(predictions),
            "matched_boxes": present,
        },
        "presence_rate": present / total if total else 0.0,
        "mean_iou": float(np.mean(values)) if values.size else 0.0,
        "fraction_at_or_above_threshold": (
            float(np.mean(values >= iou_threshold)) if values.size else 0.0
        ),
        "iou_threshold": iou_threshold,
        "time_tolerance_s": time_tolerance_s,
        "boxes": rows,
        "note": (
            "Timestamp-matched box IoU is a readiness check, not the official "
            "VQ2D response-track metric."
        ),
    }


# ---------------------------------------------------------------------------
# Readiness scorecard
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReadinessFact:
    """One prerequisite for a defensible Ego4D comparison."""

    key: str
    label: str
    category: str
    weight: int
    blocker: bool = False
    effort_weeks: float = 0.0
    hint: str = ""


DEFAULT_FACTS: tuple[ReadinessFact, ...] = (
    ReadinessFact(
        "license_approved",
        "Ego4D license approved and credentials issued",
        "access",
        20,
        blocker=True,
        effort_weeks=0.3,
        hint="Apply through the Ego4D portal (Lab22); approval is typically ~48 h after signing.",
    ),
    ReadinessFact(
        "credentials_valid",
        "Benchmark credentials valid for the evaluation window",
        "access",
        5,
        effort_weeks=0.2,
        hint="Credentials last ~14 days; confirm the window covers download, annotation, and scoring.",
    ),
    ReadinessFact(
        "video_subset_downloaded",
        "Held-out benchmark videos downloaded locally",
        "data",
        10,
        blocker=True,
        effort_weeks=1.5,
        hint="Plan storage and transfer time; the benchmark subset is order ~1 TB.",
    ),
    ReadinessFact(
        "annotations_downloaded",
        "Official annotations and splits downloaded",
        "data",
        10,
        blocker=True,
        effort_weeks=0.3,
        hint="Use official splits; do not re-split videos that share scenes.",
    ),
    ReadinessFact(
        "adapter_implemented",
        "Aegis -> Ego4D annotation adapter implemented",
        "engineering",
        15,
        blocker=True,
        effort_weeks=4.0,
        hint="Map queries, temporal windows, tracks, and video/clip identifiers; budget 3–6 weeks.",
    ),
    ReadinessFact(
        "query_mapping_defined",
        "Aegis query and memory outputs mapped to benchmark answers",
        "engineering",
        5,
        effort_weeks=1.0,
        hint="Decide whether NLQ answers use anchors, rooms, or raw windows.",
    ),
    ReadinessFact(
        "metric_scoring_validated",
        "Scoring validated against official task definitions",
        "science",
        10,
        effort_weeks=1.0,
        hint="Compare on a small official sample before running the full subset.",
    ),
    ReadinessFact(
        "compute_budget_confirmed",
        "GPU and storage budget confirmed for the subset",
        "engineering",
        10,
        effort_weeks=0.5,
        hint="Estimate Modal cost from measured per-video runtime, not optimism.",
    ),
    ReadinessFact(
        "ethics_review_complete",
        "Ethics/privacy review covers benchmark and demo data",
        "governance",
        5,
        effort_weeks=1.0,
        hint="Keep the public benchmark and the care demo data separate.",
    ),
    ReadinessFact(
        "evaluation_protocol_frozen",
        "Benchmark protocol and success criteria frozen before scoring",
        "science",
        5,
        effort_weeks=0.5,
        hint="Same freeze discipline as the held-out Aegis video.",
    ),
    ReadinessFact(
        "domain_risk_mitigated",
        "Domain mismatch risk stated and bounded",
        "science",
        5,
        effort_weeks=0.5,
        hint="Ego4D is not an assistive-care dataset; do not over-claim transfer.",
    ),
)

_GO_SCORE = 80.0
_CONDITIONAL_SCORE = 50.0


def score_readiness(facts: Mapping[str, bool]) -> dict[str, Any]:
    """Turn the prerequisite checklist into a go / conditional-go / no-go call."""

    known = {fact.key: fact for fact in DEFAULT_FACTS}
    unknown = sorted(set(facts) - set(known))
    if unknown:
        raise ValueError(f"Unknown readiness facts: {', '.join(unknown)}")

    rows: list[dict[str, Any]] = []
    earned = 0
    maximum = sum(fact.weight for fact in DEFAULT_FACTS)
    missing: list[dict[str, Any]] = []
    blockers_missing: list[str] = []
    effort_weeks = 0.0
    by_category: dict[str, dict[str, Any]] = {}

    for fact in DEFAULT_FACTS:
        satisfied = bool(facts.get(fact.key, False))
        points = fact.weight if satisfied else 0
        earned += points
        if not satisfied:
            missing.append(
                {
                    "key": fact.key,
                    "label": fact.label,
                    "category": fact.category,
                    "blocker": fact.blocker,
                    "effort_weeks": fact.effort_weeks,
                    "hint": fact.hint,
                }
            )
            effort_weeks += fact.effort_weeks
            if fact.blocker:
                blockers_missing.append(fact.key)
        category = by_category.setdefault(
            fact.category, {"earned": 0, "maximum": 0, "items": 0, "satisfied": 0}
        )
        category["earned"] += points
        category["maximum"] += fact.weight
        category["items"] += 1
        category["satisfied"] += int(satisfied)
        rows.append(
            {
                "key": fact.key,
                "label": fact.label,
                "category": fact.category,
                "weight": fact.weight,
                "satisfied": satisfied,
                "earned": points,
                "blocker": fact.blocker,
            }
        )

    percentage = 100.0 * earned / maximum if maximum else 0.0
    if not blockers_missing and percentage >= _GO_SCORE:
        decision = "go"
        rationale = (
            "All blockers are cleared and the weighted checklist is at or above "
            f"{_GO_SCORE:.0f}%. A benchmark run is defensible."
        )
    elif percentage >= _CONDITIONAL_SCORE:
        decision = "conditional_go"
        rationale = (
            "The remaining work is bounded, but the run is not yet defensible. "
            "Clear the listed blockers and re-score before committing compute."
        )
    else:
        decision = "no_go"
        rationale = (
            "Too many prerequisites are missing to justify a benchmark claim. "
            "Report Option C as future work instead."
        )

    return {
        "decision": decision,
        "readiness_score": percentage,
        "points_earned": earned,
        "points_maximum": maximum,
        "blockers_missing": blockers_missing,
        "estimated_effort_weeks": round(effort_weeks, 1),
        "rationale": rationale,
        "categories": {
            key: {
                **value,
                "score": 100.0 * value["earned"] / value["maximum"]
                if value["maximum"]
                else 0.0,
            }
            for key, value in sorted(by_category.items())
        },
        "facts": rows,
        "missing": missing,
        "thresholds": {"go": _GO_SCORE, "conditional_go": _CONDITIONAL_SCORE},
    }


# ---------------------------------------------------------------------------
# Adapter contract
# ---------------------------------------------------------------------------


def adapter_contract() -> dict[str, Any]:
    """Describe the exact conversion Aegis needs before an Ego4D run.

    The contract is intentionally declarative so a future adapter can be tested
    against it without downloading the dataset.
    """

    return {
        "version": 1,
        "purpose": (
            "Convert official Ego4D clips and annotations into Aegis pipeline "
            "inputs and evaluation records without changing benchmark semantics."
        ),
        "inputs": {
            "video": "<ego4d_root>/videos/<video_uid>.mp4",
            "clips": "<ego4d_root>/annotations/nlq_train.json | nlq_val.json",
            "vq2d": "<ego4d_root>/annotations/vq_train.json | vq_val.json",
            "official_splits": "official train/val/test split files; never re-split",
        },
        "clip_record": {
            "required": ["clip_uid", "video_uid", "video_start_sec", "video_end_sec"],
            "notes": (
                "Aegis processes the clip window; timestamps in queries are "
                "relative to the clip start unless the adapter records otherwise."
            ),
        },
        "query_record": {
            "required": ["query_id", "clip_uid", "query", "start_time", "end_time"],
            "maps_to": "aegis.evaluation.schema.QuerySpec for NLQ-style checks",
            "notes": (
                "Keep the original query text. Do not paraphrase benchmark "
                "queries after the protocol is frozen."
            ),
        },
        "vq2d_record": {
            "required": ["query_id", "clip_uid", "response_track"],
            "response_track_item": ["timestamp", "x", "y", "w", "h"],
            "maps_to": "aegis.evaluation.option_c.BoxObservation (xyxy pixels)",
        },
        "aegis_outputs": {
            "scene_graph": "outputs/<clip_uid>/objects/r4d_scene_graph.json",
            "detections": "outputs/<clip_uid>/objects/detected_objects_3d.json",
            "poses": "outputs/<clip_uid>/geometry/poses.json",
        },
        "scoring": {
            "nlq": "score_nlq(...) with temporal IoU thresholds 0.3 and 0.5",
            "vq2d": "score_vq2d(...) with timestamp tolerance and box IoU 0.5",
            "official_parity_required": (
                "Before publishing, re-score with the official Ego4D evaluation "
                "code on the official val/test splits."
            ),
        },
        "must_not_do": [
            "Mix clips from one video across splits.",
            "Tune prompts, classes, or thresholds on the benchmark test split.",
            "Report Aegis-specific metrics as official Ego4D leaderboard numbers.",
            "Treat Ego4D results as clinical or assistive-care validation.",
        ],
    }


def load_facts(path: str | Path) -> dict[str, Any]:
    """Load a facts YAML/JSON file with a ``facts`` mapping and notes."""

    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Option C facts file not found: {file_path}")
    if file_path.suffix.lower() == ".json":
        import json

        payload = json.loads(file_path.read_text(encoding="utf-8"))
    else:
        payload = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise TypeError(f"{file_path} must contain a mapping")
    facts = payload.get("facts", {})
    if not isinstance(facts, dict):
        raise TypeError(f"{file_path}: 'facts' must be a mapping")
    return {
        "facts": {str(key): bool(value) for key, value in facts.items()},
        "constraints": payload.get("constraints", {}),
        "notes": payload.get("notes"),
    }


def build_markdown(report: dict[str, Any]) -> str:
    readiness = report.get("readiness", {})
    lines = [
        "# Option C — Ego4D benchmark readiness",
        "",
        f"**Decision:** `{str(readiness.get('decision', 'unknown')).upper()}`  ",
        (
            f"**Readiness score:** {readiness.get('readiness_score', 0):.1f}% "
            f"({readiness.get('points_earned', 0)}/{readiness.get('points_maximum', 0)} points)  "
        ),
        (
            f"**Estimated remaining effort:** "
            f"{readiness.get('estimated_effort_weeks', 0):.1f} weeks"
        ),
        "",
        f"> {readiness.get('rationale', '')}",
        "",
        "## Why Option C is a research extension, not a quick add-on",
        "",
        "- Ego4D access is licensed and gated; approval is not instant.",
        "- The benchmark subset is large (order of ~1 TB), so transfer and GPU time are real costs.",
        "- Ego4D is an egocentric *general* dataset, not an assistive-care dataset. A score there supports generalisation of perception/grounding, not clinical usefulness.",
        "- The official leaderboard requires the official splits, official metrics, and no test-set tuning.",
        "",
        "## Readiness checklist",
        "",
        "| Category | Prerequisite | Weight | Done | Blocker |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for fact in readiness.get("facts", []):
        lines.append(
            f"| {fact.get('category')} | {fact.get('label')} | "
            f"{fact.get('weight')} | {'yes' if fact.get('satisfied') else 'NO'} | "
            f"{'yes' if fact.get('blocker') else ''} |"
        )
    lines.append("")

    categories = readiness.get("categories", {})
    if categories:
        lines.extend(
            [
                "## Category scores",
                "",
                "| Category | Score | Points |",
                "| --- | ---: | ---: |",
            ]
        )
        for name, values in categories.items():
            lines.append(
                f"| {name} | {values.get('score', 0):.0f}% | "
                f"{values.get('earned', 0)}/{values.get('maximum', 0)} |"
            )
        lines.append("")

    missing = readiness.get("missing", [])
    if missing:
        lines.extend(
            [
                "## Remaining work",
                "",
                "| Prerequisite | Blocker | Effort (weeks) | What to do |",
                "| --- | --- | ---: | --- |",
            ]
        )
        for item in missing:
            lines.append(
                f"| {item.get('label')} | {'YES' if item.get('blocker') else ''} | "
                f"{item.get('effort_weeks', 0):.1f} | {item.get('hint', '')} |"
            )
        lines.append("")

    nlq = report.get("nlq")
    if nlq and nlq.get("available"):
        lines.extend(
            [
                "## NLQ temporal scoring sanity check",
                "",
                f"- Queries: {nlq['counts']['queries']}",
                f"- Mean temporal IoU: {nlq.get('mean_temporal_iou', 0):.3f}",
            ]
        )
        for threshold, value in nlq.get("recall_at", {}).items():
            lines.append(f"- Recall at tIoU {threshold}: {value * 100:.1f}%")
        lines.append("")

    vq2d = report.get("vq2d")
    if vq2d and vq2d.get("available"):
        lines.extend(
            [
                "## VQ2D box scoring sanity check",
                "",
                f"- Presence rate: {vq2d.get('presence_rate', 0) * 100:.1f}%",
                f"- Mean IoU: {vq2d.get('mean_iou', 0):.3f}",
                (
                    f"- Fraction at or above IoU threshold: "
                    f"{vq2d.get('fraction_at_or_above_threshold', 0) * 100:.1f}%"
                ),
                "",
            ]
        )

    constraints = report.get("constraints") or {}
    if constraints:
        lines.extend(["## Recorded constraints", ""])
        for key, value in constraints.items():
            lines.append(f"- **{key}:** {value}")
        lines.append("")

    lines.extend(
        [
            "## Adapter contract",
            "",
            "```json",
            yaml.safe_dump(
                report.get("adapter_contract", {}), sort_keys=False, width=100
            ).rstrip(),
            "```",
            "",
            "## Bottom line for the panel",
            "",
            (
                "Option C is **future work with a concrete plan**, not a result. "
                "The defensible move is to report the score above, show the adapter "
                "contract, and state that no Ego4D number exists yet. Inventing a "
                "number from a different dataset would not survive review."
            ),
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def run_option_c(
    facts_path: str | Path,
    *,
    nlq_annotations: Sequence[NLQAnnotation] | None = None,
    nlq_predictions: Sequence[NLQPrediction] | None = None,
    vq2d_ground_truth: Sequence[BoxObservation] | None = None,
    vq2d_predictions: Sequence[BoxObservation] | None = None,
) -> dict[str, Any]:
    payload = load_facts(facts_path)
    readiness = score_readiness(payload["facts"])
    report: dict[str, Any] = {
        "schema": "aegis.option_c.readiness.v1",
        "facts_path": str(facts_path),
        "readiness": readiness,
        "constraints": payload.get("constraints", {}),
        "notes": payload.get("notes"),
        "adapter_contract": adapter_contract(),
    }
    if nlq_annotations:
        report["nlq"] = score_nlq(nlq_annotations, nlq_predictions or [])
    if vq2d_ground_truth:
        report["vq2d"] = score_vq2d(vq2d_ground_truth, vq2d_predictions or [])
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Score Ego4D benchmark readiness for Option C."
    )
    parser.add_argument(
        "--facts",
        default="evaluation/configs/option_c_facts.yaml",
        help="YAML/JSON readiness checklist.",
    )
    parser.add_argument("--output-dir", default="evaluation/reports/option_c")
    arguments = parser.parse_args(argv)

    report = run_option_c(arguments.facts)
    output_dir = Path(arguments.output_dir)
    write_json(output_dir / "summary.json", report)
    (output_dir / "summary.md").write_text(build_markdown(report), encoding="utf-8")
    readiness = report["readiness"]
    print(f"decision: {readiness['decision']}")
    print(f"readiness: {readiness['readiness_score']:.1f}%")
    print(f"remaining effort: {readiness['estimated_effort_weeks']:.1f} weeks")
    print(f"summary: {output_dir / 'summary.json'}")
    print(f"markdown: {output_dir / 'summary.md'}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
