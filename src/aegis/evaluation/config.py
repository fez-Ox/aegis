"""Configuration for the standalone evaluation harness."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_TARGETS: dict[str, float] = {
    "detection_precision": 0.85,
    "detection_recall": 0.75,
    "detection_f1": 0.80,
    "tracking_idf1": 0.75,
    "event_f1": 0.75,
    "room_accuracy": 0.90,
    "room_change_f1": 0.70,
    "persistence_state_recall": 0.90,
    "persistence_query_recall": 0.90,
    "query_accuracy": 0.80,
    "leakage_rate": 0.0,
    "latency_p95_ms": 500.0,
}

DEFAULT_THRESHOLDS: dict[str, float] = {
    "detection_iou": 0.5,
    "tracking_iou": 0.5,
    "mask_iou": 0.5,
    "event_tolerance_s": 1.0,
    "room_change_tolerance_s": 1.0,
}


@dataclass(frozen=True, slots=True)
class EvaluationConfig:
    """Validated configuration for one held-out evaluation run."""

    path: Path
    dataset_id: str
    root: Path
    annotations_dir: Path
    output_dir: Path
    scene_graph: Path
    detections: Path | None
    poses: Path | None
    thresholds: dict[str, float] = field(default_factory=dict)
    targets: dict[str, float] = field(default_factory=dict)
    label_aliases: dict[str, str] = field(default_factory=dict)
    exclude_labels: tuple[str, ...] = ()
    event_type_aliases: dict[str, str] = field(default_factory=dict)
    event_types: tuple[str, ...] | None = None
    query_mode: str = "graph"
    latency_requests: int = 0
    leakage_enabled: bool = True
    leakage_max_datasets: int = 8
    ablations_enabled: bool = True
    report_title: str = "Aegis evaluation report"
    raw: dict[str, Any] = field(default_factory=dict)

    def annotation_path(self, filename: str) -> Path:
        return self.annotations_dir / filename


def _resolve(root: Path, value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else (root / path)


def load_evaluation_config(path: str | Path) -> EvaluationConfig:
    """Load and validate ``evaluation/configs/*.yaml``."""

    config_path = Path(path)
    if not config_path.is_file():
        raise FileNotFoundError(f"Evaluation config not found: {config_path}")
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise TypeError(f"{config_path} must contain a YAML mapping")

    dataset_id = str(raw.get("dataset_id", "")).strip()
    if not dataset_id:
        raise ValueError(f"{config_path}: dataset_id is required")

    root_value = raw.get("root", ".")
    root = Path(root_value).expanduser()
    if not root.is_absolute():
        root = (Path.cwd() / root).resolve()

    annotations_dir = _resolve(
        root, raw.get("annotations_dir", f"evaluation/annotations/{dataset_id}")
    )
    output_dir = _resolve(
        root, raw.get("report_dir", f"evaluation/reports/{dataset_id}")
    )
    predictions = raw.get("predictions", {}) or {}
    if not isinstance(predictions, dict):
        raise TypeError(f"{config_path}: predictions must be a mapping")
    scene_graph = _resolve(
        root,
        predictions.get(
            "scene_graph", f"outputs/{dataset_id}/objects/r4d_scene_graph.json"
        ),
    )
    detections = _resolve(
        root,
        predictions.get(
            "detections", f"outputs/{dataset_id}/objects/detected_objects_3d.json"
        ),
    )
    poses = _resolve(
        root,
        predictions.get("poses", f"outputs/{dataset_id}/geometry/poses.json"),
    )

    thresholds = {**DEFAULT_THRESHOLDS, **(raw.get("thresholds") or {})}
    targets = {**DEFAULT_TARGETS, **(raw.get("targets") or {})}
    labels = raw.get("labels", {}) or {}
    if not isinstance(labels, dict):
        raise TypeError(f"{config_path}: labels must be a mapping")
    aliases = labels.get("aliases", {}) or {}
    if not isinstance(aliases, dict):
        raise TypeError(f"{config_path}: labels.aliases must be a mapping")
    exclude = labels.get("exclude", []) or []
    if not isinstance(exclude, list):
        raise TypeError(f"{config_path}: labels.exclude must be a list")

    events = raw.get("events", {}) or {}
    if not isinstance(events, dict):
        raise TypeError(f"{config_path}: events must be a mapping")
    event_type_aliases = events.get("type_aliases", {}) or {}
    if not isinstance(event_type_aliases, dict):
        raise TypeError(f"{config_path}: events.type_aliases must be a mapping")
    event_types_raw = events.get("types")
    event_types = (
        tuple(str(item) for item in event_types_raw)
        if isinstance(event_types_raw, list)
        else None
    )

    query = raw.get("query", {}) or {}
    if not isinstance(query, dict):
        raise TypeError(f"{config_path}: query must be a mapping")
    query_mode = str(query.get("mode", "graph")).lower()
    if query_mode not in {"graph", "api"}:
        raise ValueError(f"{config_path}: query.mode must be 'graph' or 'api'")
    latency_requests = int(query.get("latency_requests", 0))

    leakage = raw.get("leakage", {}) or {}
    ablations = raw.get("ablations", {}) or {}
    report = raw.get("report", {}) or {}

    if annotations_dir is None or output_dir is None or scene_graph is None:
        raise ValueError(f"{config_path}: invalid path configuration")

    return EvaluationConfig(
        path=config_path,
        dataset_id=dataset_id,
        root=root,
        annotations_dir=annotations_dir,
        output_dir=output_dir,
        scene_graph=scene_graph,
        detections=detections,
        poses=poses,
        thresholds={key: float(value) for key, value in thresholds.items()},
        targets={key: float(value) for key, value in targets.items()},
        label_aliases={str(key): str(value) for key, value in aliases.items()},
        exclude_labels=tuple(str(item) for item in exclude),
        event_type_aliases={
            str(key): str(value) for key, value in event_type_aliases.items()
        },
        event_types=event_types,
        query_mode=query_mode,
        latency_requests=max(0, latency_requests),
        leakage_enabled=bool(leakage.get("enabled", True)),
        leakage_max_datasets=int(leakage.get("max_datasets", 8)),
        ablations_enabled=bool(ablations.get("enabled", True)),
        report_title=str(report.get("title", f"Aegis evaluation — {dataset_id}")),
        raw=raw,
    )
