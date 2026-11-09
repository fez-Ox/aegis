"""Option D: controlled-room spatial experiment.

A monocular reconstruction has no absolute scale.  This module therefore
aligns predicted object centres to hand measurements with a similarity
transform (scale + rotation + translation) before reporting errors, and it
states that caveat in the report.  If the room is measured with a 1 m grid and
a known-size reference, the fitted scale factor itself becomes useful evidence:
a value near 1 supports the pipeline's metric scale; a large deviation says the
reconstruction is only up to scale.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

from aegis.evaluation.io import load_measurements, load_scene_graph, write_json
from aegis.evaluation.metrics import (
    linear_sum_assignment,
    normalise_anchor,
    normalise_label,
    normalise_room,
    wilson_interval,
)
from aegis.evaluation.schema import Measurement


def umeyama_similarity(
    source: np.ndarray, target: np.ndarray
) -> tuple[float, np.ndarray, np.ndarray]:
    """Least-squares similarity transform ``target ≈ s R source + t``."""

    source = np.asarray(source, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)
    if source.shape != target.shape or source.ndim != 2 or source.shape[1] != 3:
        raise ValueError("source and target must be N x 3 arrays")
    count = source.shape[0]
    if count == 0:
        raise ValueError("at least one correspondence is required")
    if count == 1:
        return 1.0, np.eye(3), target[0] - source[0]

    source_mean = source.mean(axis=0)
    target_mean = target.mean(axis=0)
    source_centred = source - source_mean
    target_centred = target - target_mean
    covariance = target_centred.T @ source_centred / count
    u, singular_values, vt = np.linalg.svd(covariance)
    rotation = u @ vt
    if np.linalg.det(rotation) < 0:
        u[:, -1] *= -1.0
        rotation = u @ vt
    source_variance = float(np.sum(source_centred**2) / count)
    scale = (
        float(np.sum(singular_values) / source_variance) if source_variance > 0 else 1.0
    )
    translation = target_mean - scale * rotation @ source_mean
    return scale, rotation, translation


def _apply_similarity(
    points: np.ndarray, scale: float, rotation: np.ndarray, translation: np.ndarray
) -> np.ndarray:
    return scale * (points @ rotation.T) + translation


def _prediction_states(
    graph: dict[str, Any], frame_id: int | None = None
) -> list[dict[str, Any]]:
    timeline = graph.get("timeline", {})
    if frame_id is not None:
        frames = sorted(int(frame) for frame in timeline)
        eligible = [frame for frame in frames if frame <= frame_id]
        if eligible:
            entries = timeline.get(str(eligible[-1]), timeline.get(eligible[-1], []))
            return [dict(entry) for entry in entries]
    from aegis.remote.api import find_latest_objects_state

    return [dict(state) for state in find_latest_objects_state(graph).values()]


def _normalise_relation(value: str | None) -> str:
    if not value:
        return ""
    aliases = {
        "on": "on_surface",
        "on top": "on_surface",
        "on_top": "on_surface",
        "carried": "carried_by_user",
        "in_hand": "carried_by_user",
        "floor": "on_floor",
        "inside": "inside",
    }
    text = " ".join(value.lower().strip().split())
    return aliases.get(text, text)


def _pair_measurements(
    measurements: Sequence[Measurement],
    predictions: Sequence[dict[str, Any]],
    *,
    aliases: dict[str, str] | None,
    transform: tuple[float, np.ndarray, np.ndarray] | None = None,
    fixed_pairs: dict[str, int] | None = None,
) -> list[tuple[Measurement, dict[str, Any]]]:
    """Pair by canonical label and nearest transformed centre, one-to-one."""

    scale, rotation, translation = transform or (
        1.0,
        np.eye(3),
        np.zeros(3, dtype=np.float64),
    )
    used: set[int] = set()
    pairs: list[tuple[Measurement, dict[str, Any]]] = []
    fixed_pairs = fixed_pairs or {}

    for measurement in measurements:
        if measurement.object_id in fixed_pairs:
            index = fixed_pairs[measurement.object_id]
            if 0 <= index < len(predictions) and index not in used:
                used.add(index)
                pairs.append((measurement, predictions[index]))

    by_label: dict[str, list[Measurement]] = defaultdict(list)
    for measurement in measurements:
        if measurement.object_id in fixed_pairs:
            continue
        by_label[normalise_label(measurement.label, aliases)].append(measurement)

    for label, group in by_label.items():
        candidates = [
            (index, prediction)
            for index, prediction in enumerate(predictions)
            if index not in used
            and normalise_label(prediction.get("label"), aliases) == label
        ]
        if not candidates:
            continue
        measurement_centres = np.asarray(
            [item.center for item in group], dtype=np.float64
        )
        prediction_centres = np.asarray(
            [prediction.get("center", [0.0, 0.0, 0.0]) for _, prediction in candidates],
            dtype=np.float64,
        )
        transformed = _apply_similarity(
            prediction_centres, scale, rotation, translation
        )
        distances = np.linalg.norm(
            measurement_centres[:, None, :] - transformed[None, :, :], axis=2
        )
        assignment = linear_sum_assignment(distances)
        for row, column in enumerate(assignment):
            if column < 0:
                continue
            index, prediction = candidates[column]
            if index in used:
                continue
            used.add(index)
            pairs.append((group[row], prediction))
    return pairs


def _refine_alignment(
    measurements: Sequence[Measurement],
    predictions: Sequence[dict[str, Any]],
    *,
    aliases: dict[str, str] | None,
    iterations: int = 5,
) -> tuple[
    list[tuple[Measurement, dict[str, Any]]],
    float,
    np.ndarray,
    np.ndarray,
]:
    fixed = {
        measurement.object_id: measurement.predicted_instance_id
        for measurement in measurements
        if measurement.predicted_instance_id is not None
    }
    # ``fixed`` is by instance id, not list index; convert after first lookup.
    instance_index = {
        int(prediction.get("instance_id")): index
        for index, prediction in enumerate(predictions)
        if prediction.get("instance_id") is not None
    }
    fixed_indices = {
        object_id: instance_index[instance_id]
        for object_id, instance_id in fixed.items()
        if instance_id in instance_index
    }
    pairs = _pair_measurements(
        measurements,
        predictions,
        aliases=aliases,
        fixed_pairs=fixed_indices,
    )
    if len(pairs) < 1:
        raise ValueError("No measured objects could be matched to predicted instances")

    scale, rotation, translation = 1.0, np.eye(3), np.zeros(3, dtype=np.float64)
    for _ in range(iterations):
        source = np.asarray(
            [prediction.get("center", [0.0, 0.0, 0.0]) for _, prediction in pairs],
            dtype=np.float64,
        )
        target = np.asarray(
            [measurement.center for measurement, _ in pairs], dtype=np.float64
        )
        scale, rotation, translation = umeyama_similarity(source, target)
        refined = _pair_measurements(
            measurements,
            predictions,
            aliases=aliases,
            transform=(scale, rotation, translation),
            fixed_pairs=fixed_indices,
        )
        if len(refined) <= len(pairs):
            pairs = refined
            break
        pairs = refined
    source = np.asarray(
        [prediction.get("center", [0.0, 0.0, 0.0]) for _, prediction in pairs],
        dtype=np.float64,
    )
    target = np.asarray(
        [measurement.center for measurement, _ in pairs], dtype=np.float64
    )
    if len(pairs) >= 1:
        scale, rotation, translation = umeyama_similarity(source, target)
    return pairs, scale, rotation, translation


def _room_mapping(
    measurements: Sequence[Measurement],
    pairs: Sequence[tuple[Measurement, dict[str, Any]]],
    *,
    aliases: dict[str, str] | None,
) -> dict[str, str]:
    measured_rooms = sorted(
        {normalise_room(item.room, aliases) for item in measurements if item.room}
    )
    predicted_rooms = sorted(
        {
            normalise_room(prediction.get("room_label"), aliases)
            for _, prediction in pairs
            if prediction.get("room_label")
        }
    )
    if not measured_rooms or not predicted_rooms:
        return {}
    counts = np.zeros((len(measured_rooms), len(predicted_rooms)), dtype=np.float64)
    measured_index = {value: index for index, value in enumerate(measured_rooms)}
    predicted_index = {value: index for index, value in enumerate(predicted_rooms)}
    for measurement, prediction in pairs:
        measured = normalise_room(measurement.room, aliases)
        predicted = normalise_room(prediction.get("room_label"), aliases)
        if measured in measured_index and predicted in predicted_index:
            counts[measured_index[measured], predicted_index[predicted]] += 1
    assignment = linear_sum_assignment(-counts)
    mapping: dict[str, str] = {}
    for row, column in enumerate(assignment):
        if column >= 0 and counts[row, column] > 0:
            mapping[predicted_rooms[column]] = measured_rooms[row]
    return mapping


def evaluate_controlled_room(
    measurements: Sequence[Measurement],
    graph: dict[str, Any],
    *,
    aliases: dict[str, str] | None = None,
    target_center_error_m: float = 0.30,
    target_relation_accuracy: float = 0.80,
    target_room_accuracy: float = 0.90,
    target_anchor_accuracy: float = 0.80,
    assume_metric_scale: bool = False,
) -> dict[str, Any]:
    """Align predicted centres to physical measurements and score the scene."""

    predictions = _prediction_states(graph)
    if not predictions:
        raise ValueError("The scene graph has no object instances to measure.")

    pairs, scale, rotation, translation = _refine_alignment(
        measurements, predictions, aliases=aliases
    )
    paired_ids = {measurement.object_id for measurement, _ in pairs}
    unmatched = [
        measurement
        for measurement in measurements
        if measurement.object_id not in paired_ids
    ]

    aligned_errors: list[float] = []
    raw_errors: list[float] = []
    relation_correct = 0
    relation_total = 0
    anchor_correct = 0
    anchor_total = 0
    room_correct = 0
    room_total = 0
    room_map = _room_mapping(measurements, pairs, aliases=aliases)
    object_rows: list[dict[str, Any]] = []

    for measurement, prediction in pairs:
        predicted_center = np.asarray(
            prediction.get("center", [0.0, 0.0, 0.0]), dtype=np.float64
        )
        aligned = _apply_similarity(
            predicted_center[None, :], scale, rotation, translation
        )[0]
        error = float(np.linalg.norm(aligned - np.asarray(measurement.center)))
        raw_error = float(
            np.linalg.norm(predicted_center - np.asarray(measurement.center))
        )
        aligned_errors.append(error)
        raw_errors.append(raw_error)

        relation_ok = None
        if measurement.relation:
            relation_total += 1
            relation_ok = _normalise_relation(
                measurement.relation
            ) == _normalise_relation(prediction.get("relation"))
            relation_correct += int(relation_ok)

        anchor_ok = None
        if measurement.anchor:
            anchor_total += 1
            anchor_ok = normalise_anchor(
                measurement.anchor, aliases
            ) == normalise_anchor(prediction.get("anchor_label"), aliases)
            anchor_correct += int(anchor_ok)

        room_ok = None
        if measurement.room:
            room_total += 1
            measured_room = normalise_room(measurement.room, aliases)
            predicted_room = normalise_room(prediction.get("room_label"), aliases)
            room_ok = room_map.get(predicted_room, predicted_room) == measured_room
            room_correct += int(room_ok)

        object_rows.append(
            {
                "object_id": measurement.object_id,
                "label": measurement.label,
                "measured_center": list(measurement.center),
                "predicted_center_raw": list(predicted_center),
                "predicted_center_aligned": [float(value) for value in aligned],
                "aligned_error_m": error,
                "raw_error_units": raw_error,
                "measured_room": measurement.room,
                "predicted_room": prediction.get("room_label"),
                "room_correct": room_ok,
                "measured_anchor": measurement.anchor,
                "predicted_anchor": prediction.get("anchor_label"),
                "anchor_correct": anchor_ok,
                "measured_relation": measurement.relation,
                "predicted_relation": prediction.get("relation"),
                "relation_correct": relation_ok,
            }
        )

    errors = (
        np.asarray(aligned_errors, dtype=np.float64) if aligned_errors else np.array([])
    )
    raw = np.asarray(raw_errors, dtype=np.float64) if raw_errors else np.array([])
    coverage = len(pairs) / len(measurements) if measurements else 0.0
    center_mean = float(np.mean(errors)) if errors.size else None
    center_median = float(np.median(errors)) if errors.size else None
    center_rmse = float(np.sqrt(np.mean(errors**2))) if errors.size else None
    center_p95 = float(np.percentile(errors, 95)) if errors.size else None
    center_max = float(np.max(errors)) if errors.size else None
    within_target = int(np.sum(errors <= target_center_error_m)) if errors.size else 0
    relation_accuracy = relation_correct / relation_total if relation_total else None
    anchor_accuracy = anchor_correct / anchor_total if anchor_total else None
    room_accuracy = room_correct / room_total if room_total else None

    result = {
        "available": True,
        "inputs": {
            "measurements": len(measurements),
            "predicted_instances": len(predictions),
            "matched": len(pairs),
            "unmatched": len(unmatched),
            "coverage": coverage,
        },
        "alignment": {
            "method": "Umeyama similarity (scale, rotation, translation)",
            "scale_factor": scale,
            "scale_error_pct_vs_metric": abs(scale - 1.0) * 100.0,
            "assume_metric_scale": assume_metric_scale,
            "rotation_matrix": rotation.tolist(),
            "translation": translation.tolist(),
            "note": (
                "Scale-aligned errors. Monocular reconstruction is scale-ambiguous; "
                "only interpret metres as absolute when the protocol and scale factor support it."
            ),
        },
        "center_error_m": {
            "mean": center_mean,
            "median": center_median,
            "rmse": center_rmse,
            "p95": center_p95,
            "max": center_max,
            "within_target": within_target,
            "target_m": target_center_error_m,
            "within_target_fraction": (within_target / len(pairs) if pairs else None),
            "raw_unscaled_mean_units": float(np.mean(raw)) if raw.size else None,
        },
        "relation_accuracy": relation_accuracy,
        "relation_accuracy_ci": (
            wilson_interval(relation_correct, relation_total)
            if relation_total
            else None
        ),
        "anchor_accuracy": anchor_accuracy,
        "anchor_accuracy_ci": (
            wilson_interval(anchor_correct, anchor_total) if anchor_total else None
        ),
        "room_accuracy": room_accuracy,
        "room_accuracy_ci": (
            wilson_interval(room_correct, room_total) if room_total else None
        ),
        "room_mapping": room_map,
        "targets": {
            "center_error_m": target_center_error_m,
            "relation_accuracy": target_relation_accuracy,
            "room_accuracy": target_room_accuracy,
            "anchor_accuracy": target_anchor_accuracy,
        },
        "verdicts": {
            "center_error": (
                "PASS"
                if center_mean is not None and center_mean <= target_center_error_m
                else "FAIL"
            ),
            "relation": (
                "PASS"
                if relation_accuracy is not None
                and relation_accuracy >= target_relation_accuracy
                else "NOT RUN"
                if relation_accuracy is None
                else "FAIL"
            ),
            "room": (
                "PASS"
                if room_accuracy is not None and room_accuracy >= target_room_accuracy
                else "NOT RUN"
                if room_accuracy is None
                else "FAIL"
            ),
            "anchor": (
                "PASS"
                if anchor_accuracy is not None
                and anchor_accuracy >= target_anchor_accuracy
                else "NOT RUN"
                if anchor_accuracy is None
                else "FAIL"
            ),
        },
        "objects": object_rows,
        "unmatched": [
            {
                "object_id": measurement.object_id,
                "label": measurement.label,
                "reason": "no predicted instance with the same canonical label",
            }
            for measurement in unmatched
        ],
    }
    if assume_metric_scale:
        # A single correspondence always fits with scale 1.0, so a metric
        # verdict needs at least three non-collinear points before it means
        # anything.
        source = np.asarray(
            [prediction.get("center", [0.0, 0.0, 0.0]) for _, prediction in pairs],
            dtype=np.float64,
        ).reshape(-1, 3)
        centred = source - source.mean(axis=0) if len(source) else source
        has_support = (
            len(source) >= 3
            and centred.size > 0
            and int(np.linalg.matrix_rank(centred)) >= 2
        )
        if not has_support:
            result["alignment"]["metric_scale_verdict"] = "INSUFFICIENT"
            result["alignment"]["metric_scale_note"] = (
                "At least three non-collinear object centres are required to "
                "judge absolute metric scale. The fitted scale is not evidence."
            )
        else:
            result["alignment"]["metric_scale_verdict"] = (
                "PASS" if abs(scale - 1.0) <= 0.10 else "FAIL"
            )
    return result


def build_markdown(result: dict[str, Any], *, title: str) -> str:
    lines = [
        f"# {title}",
        "",
        (
            "> Controlled-room experiment. Predicted centres are aligned to physical "
            "measurements with a similarity transform; read the scale caveat before "
            "quoting metres."
        ),
        "",
        "## Scorecard",
        "",
    ]
    targets = result.get("targets", {})
    center = result.get("center_error_m", {})
    rows = [
        [
            "3D centre error (aligned)",
            _fmt(center.get("mean")) + " m",
            f"≤ {targets.get('center_error_m')} m",
            result.get("verdicts", {}).get("center_error", "—"),
            f"{center.get('within_target')}/{result.get('inputs', {}).get('matched')} within target",
        ],
        [
            "Relation accuracy",
            _pct(result.get("relation_accuracy")),
            _pct(targets.get("relation_accuracy")),
            result.get("verdicts", {}).get("relation", "—"),
            "",
        ],
        [
            "Room accuracy",
            _pct(result.get("room_accuracy")),
            _pct(targets.get("room_accuracy")),
            result.get("verdicts", {}).get("room", "—"),
            "",
        ],
        [
            "Anchor accuracy",
            _pct(result.get("anchor_accuracy")),
            _pct(targets.get("anchor_accuracy")),
            result.get("verdicts", {}).get("anchor", "—"),
            "",
        ],
    ]
    lines.append(_table(["Claim", "Result", "Target", "Verdict", "Detail"], rows))
    lines.append("")

    alignment = result.get("alignment", {})
    lines.extend(
        [
            "## Alignment",
            "",
            (
                f"- Matched {result.get('inputs', {}).get('matched')} of "
                f"{result.get('inputs', {}).get('measurements')} measured objects "
                f"(coverage {_pct(result.get('inputs', {}).get('coverage'))})."
            ),
            (
                f"- Fitted scale factor: **{_fmt(alignment.get('scale_factor'))}** "
                f"(deviation from 1: {_fmt(alignment.get('scale_error_pct_vs_metric'))}%)."
            ),
            (
                f"- Mean aligned error **{_fmt(center.get('mean'))} m**, median "
                f"{_fmt(center.get('median'))} m, RMSE {_fmt(center.get('rmse'))} m, "
                f"p95 {_fmt(center.get('p95'))} m, max {_fmt(center.get('max'))} m."
            ),
            (
                f"- Raw unscaled mean error: {_fmt(center.get('raw_unscaled_mean_units'))} "
                "scene units."
            ),
            "",
            (
                "The scale factor is evidence about the reconstruction, not a free pass: "
                "a value far from 1 means the pipeline's 3D units are not metres without "
                "calibration."
            ),
            "",
        ]
    )

    objects = result.get("objects", [])
    lines.extend(["## Per-object results", ""])
    if objects:
        lines.append(
            _table(
                [
                    "Object",
                    "Label",
                    "Aligned error (m)",
                    "Room",
                    "Anchor",
                    "Relation",
                ],
                [
                    [
                        item.get("object_id"),
                        item.get("label"),
                        _fmt(item.get("aligned_error_m")),
                        _ok(item.get("room_correct")),
                        _ok(item.get("anchor_correct")),
                        _ok(item.get("relation_correct")),
                    ]
                    for item in objects
                ],
            )
        )
        lines.append("")
    unmatched = result.get("unmatched", [])
    if unmatched:
        lines.extend(["## Unmatched measurements", ""])
        lines.append(
            _table(
                ["Object", "Label", "Reason"],
                [
                    [item.get("object_id"), item.get("label"), item.get("reason")]
                    for item in unmatched
                ],
            )
        )
        lines.append("")

    lines.extend(
        [
            "## Method and limitations",
            "",
            "- The floor grid and known-size reference should be visible during recording; this is what makes scale calibration credible.",
            "- Alignment uses a similarity transform, so the reported centre error is **scale-aligned**. It measures shape and relative placement, not absolute metric accuracy, unless `assume_metric_scale` is enabled and the fitted scale is close to 1.",
            "- Relation, anchor, and room accuracy are categorical checks and do not depend on the alignment.",
            "- A single room and a small object set are enough for a panel demonstration, but they are not a generalisation study.",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}"


def _pct(value: Any) -> str:
    if value is None:
        return "—"
    return f"{float(value) * 100:.1f}%"


def _ok(value: Any) -> str:
    if value is None:
        return "—"
    return "pass" if value else "FAIL"


def _table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    lines = [
        "| " + " | ".join(str(header) for header in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Controlled-room 3D/room/anchor/relation evaluation."
    )
    parser.add_argument(
        "--measurements", required=True, help="CSV of hand measurements."
    )
    parser.add_argument("--scene-graph", required=True, help="r4d_scene_graph.json")
    parser.add_argument("--output-dir", default="evaluation/reports/controlled_room")
    parser.add_argument("--title", default="Controlled-room spatial accuracy")
    parser.add_argument("--target-center-error-m", type=float, default=0.30)
    parser.add_argument("--target-relation-accuracy", type=float, default=0.80)
    parser.add_argument("--target-room-accuracy", type=float, default=0.90)
    parser.add_argument("--target-anchor-accuracy", type=float, default=0.80)
    parser.add_argument("--assume-metric-scale", action="store_true")
    arguments = parser.parse_args(argv)

    measurements = load_measurements(arguments.measurements)
    graph = load_scene_graph(arguments.scene_graph)
    result = evaluate_controlled_room(
        measurements,
        graph,
        target_center_error_m=arguments.target_center_error_m,
        target_relation_accuracy=arguments.target_relation_accuracy,
        target_room_accuracy=arguments.target_room_accuracy,
        target_anchor_accuracy=arguments.target_anchor_accuracy,
        assume_metric_scale=arguments.assume_metric_scale,
    )
    result["measurements_path"] = str(Path(arguments.measurements))
    result["scene_graph_path"] = str(Path(arguments.scene_graph))
    output_dir = Path(arguments.output_dir)
    write_json(output_dir / "summary.json", result)
    markdown = build_markdown(result, title=arguments.title)
    (output_dir / "summary.md").write_text(markdown, encoding="utf-8")
    print(f"summary: {output_dir / 'summary.json'}")
    print(f"markdown: {output_dir / 'summary.md'}")
    print(f"mean aligned centre error: {_fmt(result['center_error_m']['mean'])} m")
    print(f"scale factor: {_fmt(result['alignment']['scale_factor'])}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
