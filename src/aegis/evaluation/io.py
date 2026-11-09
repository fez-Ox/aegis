"""Annotation and artifact loaders for the evaluation harness.

All schemas are intentionally friendly to hand editing and to CVAT/MOT
exports. JSONL files may contain either one detection per line or one frame
per line with an ``objects`` array; both forms are accepted by the detection
loader so an annotator can choose whichever export is convenient.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from aegis.evaluation.schema import (
    Detection,
    Event,
    Measurement,
    PersistenceCase,
    QuerySpec,
)


class AnnotationError(ValueError):
    """Raised when an annotation file is missing required fields."""


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


def read_json(path: str | Path) -> dict[str, Any]:
    """Read a JSON object and fail with a useful path in the message."""

    file_path = Path(path)
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AnnotationError(f"Annotation file does not exist: {file_path}") from exc
    except json.JSONDecodeError as exc:
        raise AnnotationError(f"Invalid JSON in {file_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise AnnotationError(f"{file_path} must contain a JSON object")
    return data


def iter_jsonl(path: str | Path) -> Iterable[tuple[int, dict[str, Any]]]:
    """Yield ``(line_number, object)`` for a JSONL file, skipping blanks."""

    file_path = Path(path)
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise AnnotationError(f"Annotation file does not exist: {file_path}") from exc

    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise AnnotationError(
                f"Invalid JSON on line {line_number} of {file_path}: {exc}"
            ) from exc
        if not isinstance(record, dict):
            raise AnnotationError(
                f"Line {line_number} of {file_path} must be a JSON object"
            )
        yield line_number, record


def write_json(path: str | Path, payload: Any) -> Path:
    """Write stable, human-readable JSON and return the path."""

    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=_json_default) + "\n",
        encoding="utf-8",
    )
    return file_path


def file_sha256(path: str | Path) -> str:
    """Return a short content hash for provenance records."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_default(value: Any) -> Any:
    if hasattr(value, "item"):
        return value.item()
    if hasattr(value, "tolist"):
        return value.tolist()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _as_float(value: Any, field: str, path: str | Path) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise AnnotationError(
            f"{path}: {field} must be numeric, got {value!r}"
        ) from exc
    if not math.isfinite(number):
        raise AnnotationError(f"{path}: {field} must be finite, got {value!r}")
    return number


def _as_int(value: Any, field: str, path: str | Path) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise AnnotationError(
            f"{path}: {field} must be an integer, got {value!r}"
        ) from exc


def _bbox(
    value: Any, path: str | Path, *, strict: bool
) -> tuple[float, float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise AnnotationError(f"{path}: bbox must be [x1, y1, x2, y2]")
    x1, y1, x2, y2 = (_as_float(v, "bbox", path) for v in value)
    if strict and (x2 < x1 or y2 < y1):
        raise AnnotationError(f"{path}: bbox must have x2 >= x1 and y2 >= y1")
    return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))


def _resolve_child(path: str | Path, child: str | None) -> str | None:
    if not child:
        return None
    child_path = Path(child)
    return str(
        child_path if child_path.is_absolute() else Path(path).parent / child_path
    )


def _first(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in record and record[key] is not None:
            return record[key]
    return None


# ---------------------------------------------------------------------------
# Detection annotations and predictions
# ---------------------------------------------------------------------------


def _detection_from_record(
    record: dict[str, Any],
    path: str | Path,
    *,
    strict: bool,
    inherited_frame_id: int | None = None,
) -> Detection:
    frame_value = record.get("frame_id", inherited_frame_id)
    if frame_value is None:
        raise AnnotationError(f"{path}: every detection needs a frame_id")
    frame_id = _as_int(frame_value, "frame_id", path)
    label = _first(record, "label", "class", "category")
    if not isinstance(label, str) or not label.strip():
        raise AnnotationError(f"{path}: detection at frame {frame_id} needs a label")
    bbox_value = _first(record, "bbox", "bbox_2d", "box")
    bbox = _bbox(bbox_value, path, strict=strict)
    instance_value = _first(record, "instance_id", "track_id", "id")
    instance_id = (
        _as_int(instance_value, "instance_id", path)
        if instance_value is not None
        else None
    )
    confidence_value = _first(record, "confidence", "score", "probability")
    confidence = (
        _as_float(confidence_value, "confidence", path)
        if confidence_value is not None
        else 1.0
    )
    mask_path = _resolve_child(
        path, _first(record, "mask_path", "mask", "segmentation")
    )
    visibility = str(record.get("visibility", "visible"))
    occluded = bool(
        record.get("occluded", visibility.lower() in {"occluded", "hidden"})
    )
    known = {
        "frame_id",
        "label",
        "class",
        "category",
        "bbox",
        "bbox_2d",
        "box",
        "instance_id",
        "track_id",
        "id",
        "confidence",
        "score",
        "probability",
        "mask_path",
        "mask",
        "segmentation",
        "visibility",
        "occluded",
        "timestamp",
    }
    extra = {key: value for key, value in record.items() if key not in known}
    return Detection(
        frame_id=frame_id,
        label=label.strip(),
        bbox=bbox,
        instance_id=instance_id,
        confidence=confidence,
        mask_path=mask_path,
        visibility=visibility,
        occluded=occluded,
        extra=extra,
    )


def load_detection_annotations(path: str | Path) -> list[Detection]:
    """Load human-authored 2D box/mask annotations from JSONL."""

    detections: list[Detection] = []
    for _, record in iter_jsonl(path):
        objects = record.get("objects")
        if isinstance(objects, list):
            inherited = record.get("frame_id")
            for obj in objects:
                if not isinstance(obj, dict):
                    raise AnnotationError(
                        f"{path}: objects entries must be JSON objects"
                    )
                detections.append(
                    _detection_from_record(
                        obj, path, strict=True, inherited_frame_id=inherited
                    )
                )
        else:
            detections.append(_detection_from_record(record, path, strict=True))
    if not detections:
        raise AnnotationError(f"{path}: no detection annotations found")
    return detections


def load_prediction_detections(path: str | Path) -> list[Detection]:
    """Load pipeline predictions from ``detected_objects_3d.json`` or JSONL."""

    file_path = Path(path)
    if file_path.suffix.lower() == ".jsonl":
        detections = [
            _detection_from_record(record, file_path, strict=False)
            for _, record in iter_jsonl(file_path)
        ]
    else:
        data = read_json(file_path)
        boxes = data.get("boxes_3d", data.get("detections", []))
        if not isinstance(boxes, list):
            raise AnnotationError(f"{file_path}: 'boxes_3d' must be a list")
        detections = [
            _detection_from_record(box, file_path, strict=False) for box in boxes
        ]
    if not detections:
        raise AnnotationError(f"{file_path}: no predicted detections found")
    return detections


# ---------------------------------------------------------------------------
# Event annotations
# ---------------------------------------------------------------------------


def _event_from_record(
    record: dict[str, Any],
    path: str | Path,
    *,
    default_type: str = "state_change",
) -> Event:
    event_type = str(record.get("event_type", default_type))
    if "timestamp" in record:
        start = _as_float(record["timestamp"], "timestamp", path)
        end = start
    else:
        start_value = _first(record, "start_time", "start")
        end_value = _first(record, "end_time", "end")
        if start_value is None:
            raise AnnotationError(f"{path}: event needs timestamp or start_time")
        start = _as_float(start_value, "start_time", path)
        end = _as_float(end_value, "end_time", path) if end_value is not None else start
    if end < start:
        raise AnnotationError(f"{path}: event end_time precedes start_time")
    object_value = _first(record, "object", "object_label", "label", "item")
    object_label = str(object_value) if object_value is not None else None
    instance_value = _first(record, "instance_id", "track_id")
    instance_id = (
        _as_int(instance_value, "instance_id", path)
        if instance_value is not None
        else None
    )
    known = {
        "event_id",
        "event_type",
        "timestamp",
        "start_time",
        "end_time",
        "start",
        "end",
        "object",
        "object_label",
        "label",
        "item",
        "instance_id",
        "track_id",
        "source_anchor",
        "destination_anchor",
        "source_room",
        "destination_room",
    }
    extra = {key: value for key, value in record.items() if key not in known}
    return Event(
        event_type=event_type,
        start_time=start,
        end_time=end,
        object_label=object_label,
        instance_id=instance_id,
        source_anchor=_optional_str(record.get("source_anchor")),
        destination_anchor=_optional_str(record.get("destination_anchor")),
        source_room=_optional_str(record.get("source_room")),
        destination_room=_optional_str(record.get("destination_room")),
        event_id=_optional_str(record.get("event_id")),
        extra=extra,
    )


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def load_events(path: str | Path) -> list[Event]:
    """Load ground-truth events from a JSON array or JSONL file."""

    file_path = Path(path)
    records: list[dict[str, Any]]
    if file_path.suffix.lower() == ".jsonl":
        records = [record for _, record in iter_jsonl(file_path)]
    else:
        data = read_json(file_path)
        raw = data.get("events", [])
        if not isinstance(raw, list):
            raise AnnotationError(f"{file_path}: 'events' must be a list")
        records = raw
    events = [_event_from_record(record, file_path) for record in records]
    return events


def events_from_scene_graph(
    graph: dict[str, Any], path: str | Path | None = None
) -> list[Event]:
    """Convert a scene-graph event list to typed evaluation events."""

    raw_events = graph.get("events", [])
    if not isinstance(raw_events, list):
        raise AnnotationError("scene graph 'events' must be a list")
    source = path or Path("<scene_graph>")
    return [_event_from_record(record, source) for record in raw_events]


# ---------------------------------------------------------------------------
# Question bank
# ---------------------------------------------------------------------------


def load_queries(path: str | Path) -> list[QuerySpec]:
    """Load the held-out question bank from JSONL."""

    queries: list[QuerySpec] = []
    seen: set[str] = set()
    for line_number, record in iter_jsonl(path):
        query = record.get("query")
        if not isinstance(query, str) or not query.strip():
            raise AnnotationError(f"{path}:{line_number}: query text is required")
        query_id = str(record.get("query_id", f"q{len(queries) + 1:03d}"))
        if query_id in seen:
            raise AnnotationError(
                f"{path}:{line_number}: duplicate query_id {query_id}"
            )
        seen.add(query_id)
        negative = bool(record.get("negative", False))
        expected_found = bool(record.get("expected_found", not negative))
        queries.append(
            QuerySpec(
                query_id=query_id,
                query=query.strip(),
                expected_found=expected_found,
                expected_anchor=_optional_str(record.get("expected_anchor")),
                expected_room=_optional_str(record.get("expected_room")),
                expected_relation=_optional_str(record.get("expected_relation")),
                expected_instance_label=_optional_str(
                    record.get("expected_instance_label")
                ),
                negative=negative,
                notes=_optional_str(record.get("notes")),
            )
        )
    if not queries:
        raise AnnotationError(f"{path}: no queries found")
    return queries


def load_persistence_cases(path: str | Path) -> list[PersistenceCase]:
    """Load occlusion/relocation cases for object-permanence scoring."""

    cases: list[PersistenceCase] = []
    seen: set[str] = set()
    for line_number, record in iter_jsonl(path):
        case_id = str(record.get("case_id", f"p{len(cases) + 1:03d}"))
        if case_id in seen:
            raise AnnotationError(f"{path}:{line_number}: duplicate case_id {case_id}")
        seen.add(case_id)
        query = record.get("query")
        if not isinstance(query, str) or not query.strip():
            raise AnnotationError(f"{path}:{line_number}: query text is required")
        instance_value = record.get("expected_instance_id")
        cases.append(
            PersistenceCase(
                case_id=case_id,
                query=query.strip(),
                expected_instance_id=(
                    _as_int(instance_value, "expected_instance_id", path)
                    if instance_value is not None
                    else None
                ),
                expected_label=_optional_str(record.get("expected_label")),
                expected_anchor=_optional_str(record.get("expected_anchor")),
                expected_room=_optional_str(record.get("expected_room")),
                expected_relation=_optional_str(record.get("expected_relation")),
                check_frame=(
                    _as_int(record["check_frame"], "check_frame", path)
                    if record.get("check_frame") is not None
                    else None
                ),
                occlusion_start=(
                    _as_float(record["occlusion_start"], "occlusion_start", path)
                    if record.get("occlusion_start") is not None
                    else None
                ),
                occlusion_end=(
                    _as_float(record["occlusion_end"], "occlusion_end", path)
                    if record.get("occlusion_end") is not None
                    else None
                ),
                expect_persistent=bool(record.get("expect_persistent", False)),
                notes=_optional_str(record.get("notes")),
            )
        )
    if not cases:
        raise AnnotationError(f"{path}: no persistence cases found")
    return cases


# ---------------------------------------------------------------------------
# Room annotations
# ---------------------------------------------------------------------------


def load_room_annotations(path: str | Path) -> dict[str, Any]:
    """Load room regions and per-keyframe room labels.

    Expected shape::

        {
          "rooms": [
            {"room_id": 1, "label": "Kitchen",
             "footprint": [[x, y, z], ...] or "polygon_xz": [[x, z], ...]}
          ],
          "frame_rooms": [{"frame_id": 0, "room_id": 1}, ...],
          "room_changes": [
            {"timestamp": 12.3, "from_room_id": 1, "to_room_id": 2}
          ]
        }
    """

    data = read_json(path)
    rooms = data.get("rooms")
    if not isinstance(rooms, list) or not rooms:
        raise AnnotationError(f"{path}: 'rooms' must be a non-empty list")
    frame_rooms = data.get("frame_rooms", [])
    if not isinstance(frame_rooms, list):
        raise AnnotationError(f"{path}: 'frame_rooms' must be a list")
    changes = data.get("room_changes", [])
    if not isinstance(changes, list):
        raise AnnotationError(f"{path}: 'room_changes' must be a list")
    return data


# ---------------------------------------------------------------------------
# Controlled-room measurements
# ---------------------------------------------------------------------------


def load_measurements(path: str | Path) -> list[Measurement]:
    """Load hand-measured object positions from a CSV file."""

    file_path = Path(path)
    try:
        handle = file_path.open("r", encoding="utf-8", newline="")
    except FileNotFoundError as exc:
        raise AnnotationError(f"Measurements file does not exist: {file_path}") from exc

    measurements: list[Measurement] = []
    with handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise AnnotationError(f"{file_path}: missing CSV header")
        required = {"object_id", "label", "x", "y", "z"}
        missing = required.difference(reader.fieldnames)
        if missing:
            raise AnnotationError(
                f"{file_path}: missing columns {', '.join(sorted(missing))}"
            )
        for row_number, row in enumerate(reader, start=2):
            if not any((value or "").strip() for value in row.values()):
                continue
            measurements.append(
                Measurement(
                    object_id=str(row["object_id"]).strip(),
                    label=str(row["label"]).strip(),
                    x=_as_float(row["x"], "x", file_path),
                    y=_as_float(row["y"], "y", file_path),
                    z=_as_float(row["z"], "z", file_path),
                    room=_optional_str(row.get("room")),
                    anchor=_optional_str(row.get("anchor")),
                    relation=_optional_str(row.get("relation")),
                    size_x=_optional_float(row.get("size_x")),
                    size_y=_optional_float(row.get("size_y")),
                    size_z=_optional_float(row.get("size_z")),
                    predicted_instance_id=_optional_int(
                        row.get("predicted_instance_id")
                    ),
                    frame_id=_optional_int(row.get("frame_id")),
                    notes=_optional_str(row.get("notes")),
                )
            )
    if not measurements:
        raise AnnotationError(f"{file_path}: no measurements found")
    return measurements


def _optional_float(value: Any) -> float | None:
    if value is None or not str(value).strip():
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise AnnotationError(f"Expected a number, got {value!r}") from exc


def _optional_int(value: Any) -> int | None:
    if value is None or not str(value).strip():
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise AnnotationError(f"Expected an integer, got {value!r}") from exc


# ---------------------------------------------------------------------------
# Pipeline artifacts
# ---------------------------------------------------------------------------


def load_scene_graph(path: str | Path) -> dict[str, Any]:
    """Load an R4DSG scene graph artifact."""

    data = read_json(path)
    if not isinstance(data.get("timeline", {}), dict):
        raise AnnotationError(f"{path}: 'timeline' must be an object")
    if not isinstance(data.get("anchors", []), list):
        raise AnnotationError(f"{path}: 'anchors' must be a list")
    return data


def load_poses(path: str | Path) -> list[dict[str, Any]]:
    """Load camera poses from ``poses.json`` or a list of pose records."""

    data = read_json(path)
    poses = data.get("poses", [])
    if not isinstance(poses, list):
        raise AnnotationError(f"{path}: 'poses' must be a list")
    return poses


def load_detections_jsonl_or_json(path: str | Path) -> list[Detection]:
    """Compatibility alias used by the CLI."""

    return load_prediction_detections(path)
