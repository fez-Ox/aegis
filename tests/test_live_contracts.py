"""Contract tests for the Milestone 1 artifact schemas."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from aegis.ingestion.contracts import (
    LIVE_SESSION_SCHEMA_VERSION,
    ContractError,
    load_session_manifest,
    read_live_index,
    validate_frame_record,
    validate_gap_record,
    validate_normalized_metadata,
    validate_pause_record,
    validate_session_manifest,
    write_json_atomic,
)

NOW = datetime(2025, 1, 1, tzinfo=UTC)


def _frame_record() -> dict:
    return {
        "record_type": "frame",
        "session_id": "session-1",
        "sequence": 0,
        "frame_path": "frame_00000000_20250101T000000.000Z.jpg",
        "source_id": "phone",
        "capture_timestamp": "2025-01-01T00:00:00Z",
        "timestamp_source": "laptop_receive_decode",
        "ingestion_timestamp": "2025-01-01T00:00:00.100Z",
        "width": 20,
        "height": 12,
        "encoding": "jpeg",
        "sample_rate_target_hz": 2.0,
        "source_protocol": "http-mjpeg",
    }


def _gap_record() -> dict:
    return {
        "record_type": "gap",
        "session_id": "session-1",
        "gap_start": "2025-01-01T00:00:10Z",
        "gap_end": "2025-01-01T00:00:15Z",
        "duration_seconds": 5.0,
        "reason": "disconnect",
        "dropped_estimate": 10,
        "sequence_before": 4,
        "sequence_after": 5,
        "recovered": True,
    }


def _manifest() -> dict:
    return {
        "schema_version": LIVE_SESSION_SCHEMA_VERSION,
        "session_id": "session-1",
        "source_id": "phone",
        "source_protocol": "http-mjpeg",
        "started_at": "2025-01-01T00:00:00Z",
        "status": "completed",
        "sample_rate_target_hz": 2.0,
        "emitted_frame_count": 1,
        "frame_count": 1,
        "gaps": [_gap_record()],
        "pauses": [
            {
                "pause_id": 1,
                "started_at": "2025-01-01T00:00:20Z",
                "ended_at": "2025-01-01T00:00:25Z",
                "duration_seconds": 5.0,
            }
        ],
    }


def test_frame_record_accepts_schema_v2() -> None:
    assert validate_frame_record(_frame_record())["sequence"] == 0


def test_frame_record_rejects_missing_fields() -> None:
    record = _frame_record()
    del record["capture_timestamp"]
    with pytest.raises(ContractError):
        validate_frame_record(record)


def test_frame_record_rejects_unknown_timestamp_source() -> None:
    record = _frame_record()
    record["timestamp_source"] = "phone_magic"
    with pytest.raises(ContractError):
        validate_frame_record(record)


def test_gap_record_requires_known_reason_and_ordered_window() -> None:
    record = _gap_record()
    record["reason"] = "unknown"
    with pytest.raises(ContractError):
        validate_gap_record(record)

    record = _gap_record()
    record["gap_end"] = "2025-01-01T00:00:01Z"
    with pytest.raises(ContractError):
        validate_gap_record(record)


def test_pause_record_is_ordered() -> None:
    with pytest.raises(ContractError):
        validate_pause_record(
            {
                "pause_id": 1,
                "started_at": "2025-01-01T00:00:10Z",
                "ended_at": "2025-01-01T00:00:05Z",
                "duration_seconds": 5.0,
            }
        )


def test_session_manifest_validates_v2() -> None:
    manifest = validate_session_manifest(_manifest())
    assert manifest["session_id"] == "session-1"


def test_session_manifest_rejects_bad_status() -> None:
    manifest = _manifest()
    manifest["status"] = "dead"
    with pytest.raises(ContractError):
        validate_session_manifest(manifest)


def test_read_live_index_rejects_malformed_lines(tmp_path) -> None:
    path = tmp_path / "index.jsonl"
    path.write_text(json.dumps(_frame_record()) + "\nnot-json\n", encoding="utf-8")
    with pytest.raises(ContractError):
        read_live_index(path)


def test_read_live_index_accepts_frames_and_gaps(tmp_path) -> None:
    path = tmp_path / "index.jsonl"
    path.write_text(
        json.dumps(_frame_record()) + "\n" + json.dumps(_gap_record()) + "\n",
        encoding="utf-8",
    )
    records = read_live_index(path)
    assert [record["record_type"] for record in records] == ["frame", "gap"]


def test_normalized_metadata_live_requires_capture_timebase() -> None:
    metadata = {
        "schema_version": 2,
        "dataset_id": "live_session_1",
        "preprocess_source": "live_session",
        "live_session_id": "session-1",
        "timebase": "source_video",
        "frame_count": 1,
        "resolution": [20, 12],
        "frames": [{"frame_id": 0, "timestamp": 0.0, "filename": "frame_000000.png"}],
    }
    with pytest.raises(ContractError):
        validate_normalized_metadata(metadata)

    metadata["timebase"] = "capture"
    assert validate_normalized_metadata(metadata)["frame_count"] == 1


def test_session_manifest_falls_back_to_checkpoint(tmp_path) -> None:
    session = tmp_path / "session-1"
    session.mkdir()
    write_json_atomic(
        session / "session_state.json",
        {
            "schema_version": 2,
            "session_id": "session-1",
            "source_id": "phone",
            "source_protocol": "http-mjpeg",
            "sample_rate_target_hz": 2.0,
            "started_at": "2025-01-01T00:00:00Z",
            "status": "running",
            "last_sequence": 4,
            "frame_count": 5,
            "updated_at": "2025-01-01T00:00:10Z",
        },
    )

    manifest = load_session_manifest(session)
    assert manifest["status"] == "running"
    assert manifest["frame_count"] == 5


def test_timestamp_round_trip_is_stable(tmp_path) -> None:
    path = tmp_path / "value.json"
    value = {"schema_version": 2, "written_at": NOW.isoformat()}
    write_json_atomic(path, value)
    assert json.loads(path.read_text(encoding="utf-8"))["written_at"] == (
        NOW.isoformat()
    )
