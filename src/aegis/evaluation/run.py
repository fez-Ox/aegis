"""Option A: held-out video evaluation runner for Aegis.

The runner is intentionally conservative.  If annotations are absent it writes
a readiness report instead of fabricating scores.  If only some sections are
annotated it scores those sections and marks the rest NOT RUN.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from aegis.evaluation.config import EvaluationConfig, load_evaluation_config
from aegis.evaluation.io import (
    AnnotationError,
    events_from_scene_graph,
    file_sha256,
    load_detection_annotations,
    load_events,
    load_persistence_cases,
    load_poses,
    load_prediction_detections,
    load_queries,
    load_room_annotations,
    load_scene_graph,
)
from aegis.evaluation.metrics import (
    evaluate_detection,
    evaluate_events,
    evaluate_rooms,
    evaluate_tracking,
)
from aegis.evaluation.query import (
    evaluate_ablations,
    evaluate_leakage,
    evaluate_persistence,
    evaluate_queries,
)
from aegis.evaluation.report import build_scorecard, runtime_metadata, write_report

ANNOTATION_FILES = {
    "detections": ("detections.jsonl", "2D boxes/masks on frozen keyframes"),
    "events": ("events.jsonl", "pickup/placement/state-change intervals"),
    "rooms": ("rooms.json", "room regions, per-keyframe rooms, room changes"),
    "queries": ("queries.jsonl", "held-out question bank with expected answers"),
    "persistence": ("persistence.jsonl", "occlusion/relocation cases"),
}


def _git_value(arguments: Sequence[str]) -> str | None:
    try:
        output = subprocess.check_output(
            ["git", *arguments],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = output.strip()
    return value or None


def _input_record(
    name: str,
    path: Path | None,
    description: str,
    *,
    kind: str,
) -> dict[str, Any]:
    if path is None:
        return {
            "name": name,
            "path": "",
            "description": description,
            "kind": kind,
            "exists": False,
            "size_bytes": None,
            "sha256": None,
        }
    exists = path.is_file()
    return {
        "name": name,
        "path": str(path),
        "description": description,
        "kind": kind,
        "exists": exists,
        "size_bytes": path.stat().st_size if exists else None,
        "sha256": file_sha256(path) if exists else None,
    }


def _collect_inputs(config: EvaluationConfig) -> list[dict[str, Any]]:
    inputs = [
        _input_record(
            "scene_graph",
            config.scene_graph,
            "R4DSG memory artifact",
            kind="prediction",
        ),
        _input_record(
            "predictions",
            config.detections,
            "2D/3D detections and tracks",
            kind="prediction",
        ),
        _input_record(
            "poses", config.poses, "camera poses for room assignment", kind="prediction"
        ),
    ]
    for name, (filename, description) in ANNOTATION_FILES.items():
        inputs.append(
            _input_record(
                f"annotations/{name}",
                config.annotation_path(filename),
                description,
                kind="annotation",
            )
        )
    return inputs


def _missing_inputs(inputs: Sequence[dict[str, Any]]) -> list[dict[str, str]]:
    hints = {
        "scene_graph": "Run the pipeline for this dataset, then download the scene graph artifact.",
        "predictions": "Run the pipeline detection stage and download detected_objects_3d.json.",
        "poses": "Run the VGGT pose stage and download geometry/poses.json.",
        "annotations/detections": "Annotate 2D boxes and track IDs; see evaluation/templates/detections.jsonl.",
        "annotations/events": "Label event intervals; see evaluation/templates/events.jsonl.",
        "annotations/rooms": "Label rooms and per-keyframe room IDs; see evaluation/templates/rooms.json.",
        "annotations/queries": "Write the held-out question bank; see evaluation/templates/queries.jsonl.",
        "annotations/persistence": "Label occlusion/relocation cases; see evaluation/templates/persistence.jsonl.",
    }
    missing = []
    for item in inputs:
        if item["exists"]:
            continue
        missing.append(
            {
                "section": item["kind"],
                "name": item["name"],
                "path": item["path"],
                "hint": hints.get(item["name"], "Create this input before scoring."),
            }
        )
    return missing


def _section_skip(reason: str) -> dict[str, Any]:
    return {"available": False, "reason": reason}


def _load_optional(path: Path, loader: Any) -> Any:
    try:
        return loader(path)
    except AnnotationError as exc:
        raise AnnotationError(str(exc)) from exc


def _load_other_graphs(
    config: EvaluationConfig, target_graph: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    graphs: dict[str, dict[str, Any]] = {config.dataset_id: target_graph}
    outputs_root = config.root / "outputs"
    if not outputs_root.is_dir():
        return graphs
    for graph_path in sorted(outputs_root.glob("*/objects/r4d_scene_graph.json")):
        dataset_id = graph_path.parent.parent.name
        if (
            dataset_id == config.dataset_id
            or len(graphs) >= config.leakage_max_datasets
        ):
            continue
        try:
            graph = load_scene_graph(graph_path)
        except (AnnotationError, OSError):
            continue
        if not graph.get("timeline"):
            continue
        graphs[dataset_id] = graph
    return graphs


def _measure_api_latency(
    dataset_id: str,
    items: Sequence[str],
    requests: int,
) -> dict[str, Any]:
    from fastapi.testclient import TestClient

    from aegis.remote.api import app

    if not items:
        return _section_skip("No query text is available for latency measurement.")
    client = TestClient(app)
    health = client.get("/api/v1/health", params={"dataset_id": dataset_id})
    if health.status_code != 200:
        return _section_skip(f"API health returned HTTP {health.status_code}.")
    payload = health.json()
    if int(payload.get("total_timeline_frames", 0)) <= 0:
        return _section_skip(
            f"The API did not load a scene graph for '{dataset_id}'. "
            "Run the pipeline and place the artifact under outputs/."
        )
    # One warm-up request, then measure the requested number of calls.
    client.get("/api/v1/query", params={"item": items[0], "dataset_id": dataset_id})
    latencies: list[float] = []
    errors = 0
    for index in range(requests):
        item = items[index % len(items)]
        response = client.get(
            "/api/v1/query", params={"item": item, "dataset_id": dataset_id}
        )
        if response.status_code != 200:
            errors += 1
            continue
        latencies.append(float(response.elapsed.total_seconds() * 1000.0))
    if not latencies:
        return _section_skip("Every API latency request failed.")
    values = np.asarray(latencies, dtype=np.float64)
    return {
        "available": True,
        "mode": "FastAPI TestClient (HTTP)",
        "count": len(latencies),
        "errors": errors,
        "p50_ms": float(np.percentile(values, 50)),
        "p95_ms": float(np.percentile(values, 95)),
        "max_ms": float(np.max(values)),
        "mean_ms": float(np.mean(values)),
    }


def _scorecard_with_targets(
    results: dict[str, Any], config: EvaluationConfig
) -> list[dict[str, Any]]:
    return build_scorecard(results, config.targets)


def _evaluate_queries_for_config(
    config: EvaluationConfig,
    graph: dict[str, Any] | None,
    queries: Sequence[Any],
) -> dict[str, Any]:
    if config.query_mode == "api":
        from fastapi.testclient import TestClient

        from aegis.remote.api import app

        client = TestClient(app)
        health = client.get("/api/v1/health", params={"dataset_id": config.dataset_id})
        if health.status_code != 200:
            return _section_skip(f"API health returned HTTP {health.status_code}.")
        if int(health.json().get("total_timeline_frames", 0)) <= 0:
            return _section_skip(
                f"The API did not load a scene graph for '{config.dataset_id}'. "
                "Use graph mode for a synthetic graph, or process the dataset first."
            )
        return evaluate_queries(
            graph or {},
            queries,
            dataset_id=config.dataset_id,
            query_mode="api",
            aliases=config.label_aliases,
            client=client,
        )
    if graph is None:
        return _section_skip("The scene graph artifact is missing.")
    return evaluate_queries(
        graph,
        queries,
        dataset_id=config.dataset_id,
        query_mode="graph",
        aliases=config.label_aliases,
    )


def run_evaluation(
    config_path: str | Path,
    *,
    output_dir: str | Path | None = None,
    strict: bool = False,
) -> dict[str, Any]:
    """Run every section whose inputs are present and write a report."""

    config = load_evaluation_config(config_path)
    inputs = _collect_inputs(config)
    missing = _missing_inputs(inputs)
    report_dir = Path(output_dir) if output_dir else config.output_dir

    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    results: dict[str, Any] = {
        "title": config.report_title,
        "dataset_id": config.dataset_id,
        "generated_at": generated_at,
        "status": "unknown",
        "targets": config.targets,
        "thresholds": config.thresholds,
        "inputs": inputs,
        "missing_inputs": missing,
        "skipped_sections": [],
        "provenance": {
            "git_commit": _git_value(["rev-parse", "HEAD"]) or "unknown",
            "git_branch": _git_value(["rev-parse", "--abbrev-ref", "HEAD"])
            or "unknown",
            "git_dirty": bool(_git_value(["status", "--porcelain"])),
            "config": str(config.path),
            "dataset_id": config.dataset_id,
            "generated_at": generated_at,
            **runtime_metadata(),
        },
        "reproduce_command": (
            "uv run python -m aegis.evaluation.run "
            f"--config {config.path}"
            + (f" --output-dir {report_dir}" if output_dir else "")
        ),
    }

    annotation_present = any(
        item["exists"] for item in inputs if item["kind"] == "annotation"
    )
    prediction_present = any(
        item["exists"] and item["name"] in {"scene_graph", "predictions"}
        for item in inputs
        if item["kind"] == "prediction"
    )
    if not annotation_present or not prediction_present:
        results["status"] = "not_ready"
        results["scorecard"] = _scorecard_with_targets(results, config)
        paths = write_report(results, report_dir)
        results["report_paths"] = {key: str(value) for key, value in paths.items()}
        return results

    graph: dict[str, Any] | None = None
    if config.scene_graph.is_file():
        try:
            graph = load_scene_graph(config.scene_graph)
        except AnnotationError as exc:
            results["scene_graph_error"] = str(exc)

    predicted_detections = None
    if config.detections is not None and config.detections.is_file():
        try:
            predicted_detections = load_prediction_detections(config.detections)
        except AnnotationError as exc:
            results["detections_error"] = str(exc)

    def note_skip(section: str, reason: str) -> None:
        results[section] = _section_skip(reason)
        results["skipped_sections"].append({"section": section, "reason": reason})

    detection_gt = None
    detection_path = config.annotation_path("detections.jsonl")
    if detection_path.is_file():
        try:
            detection_gt = load_detection_annotations(detection_path)
        except AnnotationError as exc:
            note_skip("detection", str(exc))

    if detection_gt is not None and predicted_detections is not None:
        results["detection"] = evaluate_detection(
            detection_gt,
            predicted_detections,
            iou_threshold=config.thresholds["detection_iou"],
            aliases=config.label_aliases,
            exclude_labels=set(config.exclude_labels),
            mask_iou_threshold=config.thresholds["mask_iou"],
        )
    elif "detection" not in results:
        note_skip(
            "detection",
            "Needs annotations/detections.jsonl and a detected_objects_3d.json artifact.",
        )

    if detection_gt is not None and predicted_detections is not None:
        results["tracking"] = evaluate_tracking(
            detection_gt,
            predicted_detections,
            iou_threshold=config.thresholds["tracking_iou"],
            aliases=config.label_aliases,
            exclude_labels=set(config.exclude_labels),
        )
    else:
        note_skip(
            "tracking",
            "Needs annotations with instance IDs and predicted tracks.",
        )

    events_path = config.annotation_path("events.jsonl")
    if events_path.is_file() and graph is not None:
        try:
            events_gt = load_events(events_path)
            events_pred = events_from_scene_graph(graph, config.scene_graph)
            results["events"] = evaluate_events(
                events_gt,
                events_pred,
                tolerance_s=config.thresholds["event_tolerance_s"],
                aliases=config.label_aliases,
                event_type_aliases=config.event_type_aliases,
                event_types=set(config.event_types) if config.event_types else None,
            )
        except AnnotationError as exc:
            note_skip("events", str(exc))
    else:
        note_skip(
            "events",
            "Needs annotations/events.jsonl and a scene graph with predicted events.",
        )

    rooms_path = config.annotation_path("rooms.json")
    if (
        rooms_path.is_file()
        and graph is not None
        and config.poses is not None
        and config.poses.is_file()
    ):
        try:
            room_annotations = load_room_annotations(rooms_path)
            poses = load_poses(config.poses)
            results["rooms"] = evaluate_rooms(
                graph,
                room_annotations,
                poses,
                tolerance_s=config.thresholds["room_change_tolerance_s"],
                aliases=config.label_aliases,
            )
        except AnnotationError as exc:
            note_skip("rooms", str(exc))
    else:
        note_skip(
            "rooms",
            "Needs annotations/rooms.json, geometry/poses.json, and room regions in the graph.",
        )

    persistence_path = config.annotation_path("persistence.jsonl")
    persistence_cases = None
    if persistence_path.is_file() and graph is not None:
        try:
            persistence_cases = load_persistence_cases(persistence_path)
            results["persistence"] = evaluate_persistence(
                graph,
                persistence_cases,
                aliases=config.label_aliases,
            )
        except AnnotationError as exc:
            note_skip("persistence", str(exc))
    else:
        note_skip(
            "persistence",
            "Needs annotations/persistence.jsonl and a scene graph with a timeline.",
        )

    queries_path = config.annotation_path("queries.jsonl")
    queries = None
    if queries_path.is_file():
        try:
            queries = load_queries(queries_path)
            results["queries"] = _evaluate_queries_for_config(config, graph, queries)
            if not results["queries"].get("available", False):
                note_skip(
                    "queries", results["queries"].get("reason", "Query scoring failed.")
                )
        except AnnotationError as exc:
            note_skip("queries", str(exc))
    else:
        note_skip("queries", "Needs annotations/queries.jsonl.")

    # Latency: use the API when the dataset is available through the normal
    # outputs/ path.  Graph-mode query timings remain in the query section.
    latency: dict[str, Any] | None = None
    latency_requests = config.latency_requests
    if latency_requests > 0 and queries:
        latency = _measure_api_latency(
            config.dataset_id, [query.query for query in queries], latency_requests
        )
    if (
        latency is None
        and results.get("queries", {}).get("available")
        and config.query_mode == "api"
    ):
        latency = dict(results["queries"].get("latency", {}))
        latency["available"] = bool(latency.get("count"))
        latency["mode"] = "FastAPI HTTP route"
    if latency and latency.get("available"):
        results["latency"] = latency
    else:
        note_skip(
            "latency",
            "Set query.latency_requests > 0 (or query.mode: api) and provide a loaded dataset.",
        )

    if graph is not None and config.leakage_enabled:
        graphs = _load_other_graphs(config, graph)
        if len(graphs) > 1:
            results["leakage"] = evaluate_leakage(
                graphs,
                aliases=config.label_aliases,
                extra_probes=config.raw.get("leakage", {}).get("extra_probes", [])
                or [],
            )
            if not results["leakage"].get("cases"):
                note_skip(
                    "leakage", "No unique cross-dataset labels were available to probe."
                )
        else:
            note_skip("leakage", "Only one processed dataset was found.")
    else:
        note_skip(
            "leakage", "Needs a scene graph and at least one other processed dataset."
        )

    if (
        config.ablations_enabled
        and graph is not None
        and queries is not None
        and persistence_cases is not None
    ):
        results["ablations"] = evaluate_ablations(
            graph,
            queries,
            persistence_cases,
            aliases=config.label_aliases,
        )
    else:
        note_skip(
            "ablations",
            "Needs a scene graph, a question bank, and persistence cases.",
        )

    results["scorecard"] = _scorecard_with_targets(results, config)
    results["verdicts"] = {
        row["metric"]: row["verdict"] for row in results["scorecard"]
    }
    evaluated_sections = [
        name
        for name in (
            "detection",
            "tracking",
            "events",
            "rooms",
            "persistence",
            "queries",
            "latency",
            "leakage",
            "ablations",
        )
        if isinstance(results.get(name), dict)
        and results[name].get("available", bool(results[name]))
    ]
    results["sections_evaluated"] = evaluated_sections
    results["status"] = "ok" if not results["skipped_sections"] else "partial"

    paths = write_report(results, report_dir)
    results["report_paths"] = {key: str(value) for key, value in paths.items()}
    if strict and results["skipped_sections"]:
        results["strict_failure"] = True
    return results


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Score Aegis on a frozen, held-out annotated video."
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to evaluation/configs/<dataset>.yaml",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Override the report directory.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any section is skipped.",
    )
    arguments = parser.parse_args(argv)

    results = run_evaluation(
        arguments.config,
        output_dir=arguments.output_dir,
        strict=arguments.strict,
    )
    print(f"Status: {results['status']}")
    if results.get("report_paths"):
        for name, path in results["report_paths"].items():
            print(f"{name}: {path}")
    for row in results.get("scorecard", []):
        if row.get("value") is None:
            print(f"  {row['metric']}: NOT RUN")
        else:
            print(
                f"  {row['metric']}: {row['value']:.4f} "
                f"(target {row['target']}, {row['verdict']})"
            )
    if results["status"] == "not_ready":
        return 2
    if arguments.strict and results.get("strict_failure"):
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess
    sys.exit(main())
