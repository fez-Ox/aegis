"""Versioned artifact contracts shared by live capture and batch ingestion.

Milestone 1 freezes the handoff boundary between the phone/laptop capture path
and the Modal video pipeline. Every artifact written by :mod:`live_storage` or
:mod:`video` is validated here so a schema drift fails loudly instead of
silently producing an unusable memory graph downstream.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

LIVE_SESSION_SCHEMA_VERSION = 2
FRAME_RECORD_SCHEMA_VERSION = 2
GAP_RECORD_SCHEMA_VERSION = 2
SESSION_STATE_SCHEMA_VERSION = 2
NORMALIZED_DATASET_SCHEMA_VERSION = 2

RECORD_TYPE_FRAME = "frame"
RECORD_TYPE_GAP = "gap"

FRAME_TIMESTAMP_SOURCES = {
    "source_capture",
    "laptop_receive_decode",
    "ingestion",
    "unknown",
}
GAP_REASONS = {
    "disconnect",
    "pause",
    "storage_stall",
    "source_stall",
    "dropped_frames",
}
SESSION_STATUSES = {
    "running",
    "completed",
    "time_limit",
    "stopped",
    "disconnected",
    "storage_error",
}


class ContractError(ValueError):
    """Raised when a persisted artifact violates its frozen contract."""


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError(f"{name} must be a JSON object")
    return value


def _string(record: Mapping[str, Any], name: str, *, allow_empty: bool = False) -> str:
    value = record.get(name)
    if not isinstance(value, str):
        raise ContractError(f"{name} must be a string")
    if not allow_empty and not value.strip():
        raise ContractError(f"{name} must not be empty")
    return value


def _integer(
    record: Mapping[str, Any], name: str, *, minimum: int | None = None
) -> int:
    value = record.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractError(f"{name} must be an integer")
    if minimum is not None and value < minimum:
        raise ContractError(f"{name} must be >= {minimum}")
    return value


def _number(
    record: Mapping[str, Any], name: str, *, minimum: float | None = None
) -> float:
    value = record.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError(f"{name} must be a number")
    result = float(value)
    if minimum is not None and result < minimum:
        raise ContractError(f"{name} must be >= {minimum}")
    return result


def _timestamp(record: Mapping[str, Any], name: str) -> datetime:
    value = _string(record, name)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ContractError(f"{name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ContractError(f"{name} must include a timezone")
    return parsed


def _positive_pair(record: Mapping[str, Any], name: str) -> tuple[int, int]:
    value = record.get(name)
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 2
        or any(isinstance(item, bool) or not isinstance(item, int) for item in value)
        or value[0] <= 0
        or value[1] <= 0
    ):
        raise ContractError(f"{name} must be a pair of positive integers")
    return int(value[0]), int(value[1])


def validate_frame_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate one ``index.jsonl`` frame record and return it unchanged."""

    data = dict(_mapping(record, "frame record"))
    record_type = data.get("record_type", RECORD_TYPE_FRAME)
    if record_type != RECORD_TYPE_FRAME:
        raise ContractError("frame record_type must be 'frame'")

    _string(data, "session_id")
    _integer(data, "sequence", minimum=0)
    _string(data, "frame_path")
    _string(data, "source_id")
    _timestamp(data, "capture_timestamp")
    timestamp_source = _string(data, "timestamp_source")
    if timestamp_source not in FRAME_TIMESTAMP_SOURCES:
        raise ContractError(
            f"timestamp_source must be one of {sorted(FRAME_TIMESTAMP_SOURCES)}"
        )
    _timestamp(data, "ingestion_timestamp")
    _integer(data, "width", minimum=1)
    _integer(data, "height", minimum=1)
    _string(data, "encoding")
    _number(data, "sample_rate_target_hz", minimum=0.000001)
    _string(data, "source_protocol")

    if "received_at" in data:
        _timestamp(data, "received_at")
    if "keyframe" in data and data["keyframe"] is not None:
        _mapping(data["keyframe"], "keyframe")
    return data


def validate_gap_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate one gap marker (recovered gaps live in ``index.jsonl``)."""

    data = dict(_mapping(record, "gap record"))
    if data.get("record_type") != RECORD_TYPE_GAP:
        raise ContractError("gap record_type must be 'gap'")

    _string(data, "session_id")
    started = _timestamp(data, "gap_start")
    ended = _timestamp(data, "gap_end")
    if ended < started:
        raise ContractError("gap_end must not precede gap_start")
    _number(data, "duration_seconds", minimum=0)
    reason = _string(data, "reason")
    if reason not in GAP_REASONS:
        raise ContractError(f"gap reason must be one of {sorted(GAP_REASONS)}")
    _integer(data, "dropped_estimate", minimum=0)

    for name in ("sequence_before", "sequence_after"):
        if name in data and data[name] is not None:
            _integer(data, name, minimum=0)
    if "recovered" in data and not isinstance(data["recovered"], bool):
        raise ContractError("recovered must be a boolean")
    return data


def validate_pause_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate one pause interval stored in the session manifest."""

    data = dict(_mapping(record, "pause record"))
    _integer(data, "pause_id", minimum=1)
    started = _timestamp(data, "started_at")
    ended = _timestamp(data, "ended_at")
    if ended < started:
        raise ContractError("pause ended_at must not precede started_at")
    _number(data, "duration_seconds", minimum=0)
    return data


def validate_session_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a ``session.json`` manifest (schema 1 is read-only compatible)."""

    data = dict(_mapping(manifest, "session manifest"))
    version = _integer(data, "schema_version", minimum=1)
    if version not in {1, LIVE_SESSION_SCHEMA_VERSION}:
        raise ContractError(
            f"unsupported live session schema_version: {version} "
            f"(expected 1 or {LIVE_SESSION_SCHEMA_VERSION})"
        )

    _string(data, "session_id")
    _timestamp(data, "started_at")
    status = _string(data, "status")
    if status not in SESSION_STATUSES:
        raise ContractError(f"status must be one of {sorted(SESSION_STATUSES)}")

    if version >= 2:
        _string(data, "source_id")
        _string(data, "source_protocol")
        _number(data, "sample_rate_target_hz", minimum=0.000001)
        _integer(data, "emitted_frame_count", minimum=0)
        _integer(data, "frame_count", minimum=0)
        for name in ("gaps", "pauses"):
            value = data.get(name, [])
            if not isinstance(value, list):
                raise ContractError(f"{name} must be a list")
        for gap in data.get("gaps", []):
            validate_gap_record(gap)
        for pause in data.get("pauses", []):
            validate_pause_record(pause)

    if "ended_at" in data and data["ended_at"] is not None:
        _timestamp(data, "ended_at")
    return data


def validate_session_state(state: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a crash-recovery checkpoint."""

    data = dict(_mapping(state, "session state"))
    version = _integer(data, "schema_version", minimum=1)
    if version != SESSION_STATE_SCHEMA_VERSION:
        raise ContractError(
            f"unsupported session state schema_version: {version} "
            f"(expected {SESSION_STATE_SCHEMA_VERSION})"
        )
    _string(data, "session_id")
    _integer(data, "last_sequence", minimum=-1)
    _integer(data, "frame_count", minimum=0)
    _timestamp(data, "updated_at")
    return data


def validate_normalized_metadata(metadata: Mapping[str, Any]) -> dict[str, Any]:
    """Validate normalised batch or promoted-live dataset metadata."""

    data = dict(_mapping(metadata, "metadata"))
    version = _integer(data, "schema_version", minimum=1)
    if version not in {1, NORMALIZED_DATASET_SCHEMA_VERSION}:
        raise ContractError(
            f"unsupported normalized dataset schema_version: {version} "
            f"(expected 1 or {NORMALIZED_DATASET_SCHEMA_VERSION})"
        )

    _string(data, "dataset_id")
    frame_count = _integer(data, "frame_count", minimum=1)
    _positive_pair(data, "resolution")
    frames = data.get("frames")
    if not isinstance(frames, list) or not frames:
        raise ContractError("frames must be a non-empty list")
    if len(frames) != frame_count:
        raise ContractError("frame_count does not match len(frames)")

    previous_timestamp = -1.0
    for index, frame in enumerate(frames):
        item = _mapping(frame, f"frames[{index}]")
        _integer(item, "frame_id", minimum=0)
        _string(item, "filename")
        timestamp = _number(item, "timestamp", minimum=0)
        if timestamp < previous_timestamp:
            raise ContractError("frame timestamps must be non-decreasing")
        previous_timestamp = timestamp

    preprocess_source = data.get("preprocess_source")
    if preprocess_source == "live_session":
        if version < NORMALIZED_DATASET_SCHEMA_VERSION:
            raise ContractError("live-promoted metadata requires schema_version 2")
        if data.get("timebase") != "capture":
            raise ContractError("live-promoted metadata must use timebase='capture'")
        _string(data, "live_session_id")
    return data


def read_json_object(path: Path) -> dict[str, Any]:
    """Read one JSON object, mapping malformed content onto ``ContractError``."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid JSON: {path}") from exc
    return dict(_mapping(value, str(path)))


def read_live_index(path: Path) -> list[dict[str, Any]]:
    """Read and validate every record in a live ``index.jsonl`` file."""

    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ContractError(f"invalid JSON at {path}:{line_number}") from exc
            if not isinstance(value, Mapping):
                raise ContractError(f"record at {path}:{line_number} must be an object")
            if value.get("record_type") == RECORD_TYPE_GAP:
                records.append(validate_gap_record(value))
            else:
                records.append(validate_frame_record(value))
    return records


def load_session_manifest(session_dir: Path) -> dict[str, Any]:
    """Load ``session.json``, falling back to a checkpoint after a crash."""

    manifest_path = session_dir / "session.json"
    if manifest_path.exists():
        return validate_session_manifest(read_json_object(manifest_path))

    state_path = session_dir / "session_state.json"
    if not state_path.exists():
        raise ContractError(
            f"live session has neither session.json nor session_state.json: {session_dir}"
        )
    state = validate_session_state(read_json_object(state_path))
    return validate_session_manifest(
        {
            "schema_version": LIVE_SESSION_SCHEMA_VERSION,
            "session_id": state["session_id"],
            "source_id": str(state.get("source_id", "unknown")),
            "source_protocol": str(state.get("source_protocol", "unknown")),
            "started_at": str(state.get("started_at", state["updated_at"])),
            "status": str(state.get("status", "running")),
            "sample_rate_target_hz": float(state.get("sample_rate_target_hz", 1.0)),
            "emitted_frame_count": int(state["frame_count"]),
            "frame_count": int(state["frame_count"]),
            "gaps": [],
            "pauses": [],
        }
    )


def write_json_atomic(path: Path, value: Mapping[str, Any]) -> None:
    """Write JSON through a temporary file so a crash cannot truncate it."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)
