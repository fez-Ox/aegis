"""Local live-capture session persistence and FR3 handoff records.

Schema v2 adds explicit gap and pause records, an after-each-frame crash
checkpoint, and append-only resume. The frame record shape is frozen in
:mod:`aegis.ingestion.contracts`; downstream promotion and tests validate it.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aegis.core.paths import validate_dataset_id
from aegis.ingestion.contracts import (
    FRAME_RECORD_SCHEMA_VERSION,
    GAP_RECORD_SCHEMA_VERSION,
    LIVE_SESSION_SCHEMA_VERSION,
    RECORD_TYPE_FRAME,
    RECORD_TYPE_GAP,
    SESSION_STATE_SCHEMA_VERSION,
    read_json_object,
    read_live_index,
    validate_frame_record,
    validate_gap_record,
    validate_pause_record,
    validate_session_manifest,
    write_json_atomic,
)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


class LiveSessionWriter:
    """Persist sampled live frames as JPEGs plus JSONL/session metadata."""

    def __init__(
        self,
        root: Path,
        session_id: str,
        manifest: dict[str, Any],
        *,
        resume: bool = False,
        checkpoint_every: int = 1,
    ):
        self.session_id = validate_dataset_id(session_id)
        self.session_dir = Path(root) / self.session_id
        self.index_path = self.session_dir / "index.jsonl"
        self.manifest_path = self.session_dir / "session.json"
        self.state_path = self.session_dir / "session_state.json"
        self.resumed = bool(resume)
        self._checkpoint_every = max(1, int(checkpoint_every))
        self._closed = False
        self._last_frame_path: str | None = None
        self.count = 0
        self.total_count = 0
        self._next_sequence = 0
        self.gaps: list[dict[str, Any]] = []
        self.pauses: list[dict[str, Any]] = []
        self.resumed_from_sequence: int | None = None

        existing_manifest: dict[str, Any] = {}
        state: dict[str, Any] = {}
        if resume:
            if not self.session_dir.is_dir():
                raise FileNotFoundError(
                    f"cannot resume missing live session: {self.session_dir}"
                )
            if self.manifest_path.exists():
                existing_manifest = read_json_object(self.manifest_path)
            if self.state_path.exists():
                state = read_json_object(self.state_path)
            self._truncate_partial_index_line()
            records = (
                read_live_index(self.index_path) if self.index_path.exists() else []
            )
            frame_sequences = [
                int(record["sequence"])
                for record in records
                if record.get("record_type", RECORD_TYPE_FRAME) == RECORD_TYPE_FRAME
            ]
            self.total_count = len(frame_sequences)
            last_index_sequence = max(frame_sequences, default=-1)
            state_sequence = int(state.get("last_sequence", -1))
            self._next_sequence = max(last_index_sequence, state_sequence) + 1
            self.resumed_from_sequence = self._next_sequence - 1
            self.gaps = list(existing_manifest.get("gaps", []))
            self.pauses = list(existing_manifest.get("pauses", []))
            self._index = self.index_path.open("a", encoding="utf-8")
        else:
            self.session_dir.mkdir(parents=True, exist_ok=False)
            self._index = self.index_path.open("w", encoding="utf-8")

        now = _iso(datetime.now(UTC))
        self.manifest: dict[str, Any] = dict(existing_manifest)
        self.manifest.update(dict(manifest))
        if existing_manifest.get("started_at"):
            self.manifest["started_at"] = existing_manifest["started_at"]
        self.manifest["schema_version"] = LIVE_SESSION_SCHEMA_VERSION
        self.manifest["session_id"] = self.session_id
        self.manifest.setdefault("started_at", now)
        self.manifest.setdefault("source_id", "unknown")
        self.manifest.setdefault("source_protocol", "unknown")
        self.manifest.setdefault("sample_rate_target_hz", 1.0)
        self.manifest.setdefault("max_duration_seconds", 0.0)
        self.manifest["resumed"] = self.resumed
        if self.resumed:
            history = list(self.manifest.get("resumed_at", []))
            history.append(now)
            self.manifest["resumed_at"] = history
            self.manifest["resumed_from_sequence"] = self.resumed_from_sequence
        self.manifest["gaps"] = self.gaps
        self.manifest["pauses"] = self.pauses
        self.manifest["gap_count"] = len(self.gaps)
        self.manifest["pause_count"] = len(self.pauses)
        self.manifest["frame_count"] = self.total_count
        self.manifest["status"] = "running"
        self.checkpoint()

    # ------------------------------------------------------------------ writing
    def write(
        self,
        image: Any,
        *,
        received_at: datetime,
        source_id: str,
        sample_rate: float,
        source_protocol: str,
        captured_at: datetime | None = None,
        keyframe: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Write one JPEG frame and append its JSONL metadata record."""

        import cv2

        height, width = image.shape[:2]
        authoritative = captured_at or received_at
        timestamp = authoritative.astimezone(UTC)
        stamp = timestamp.strftime("%Y%m%dT%H%M%S.%fZ")[:-3]
        sequence = self._next_sequence
        filename = f"frame_{sequence:08d}_{stamp}.jpg"
        path = self.session_dir / filename
        if not cv2.imwrite(str(path), image, [cv2.IMWRITE_JPEG_QUALITY, 90]):
            raise OSError(f"could not write frame: {path}")

        record: dict[str, Any] = {
            "record_type": RECORD_TYPE_FRAME,
            "record_schema_version": FRAME_RECORD_SCHEMA_VERSION,
            "session_id": self.session_id,
            "sequence": sequence,
            "frame_path": filename,
            "source_id": source_id,
            "capture_timestamp": _iso(timestamp),
            "timestamp_source": (
                "source_capture" if captured_at is not None else "laptop_receive_decode"
            ),
            "received_at": _iso(received_at),
            "ingestion_timestamp": _iso(datetime.now(UTC)),
            "width": int(width),
            "height": int(height),
            "encoding": "jpeg",
            "sample_rate_target_hz": float(sample_rate),
            "source_protocol": source_protocol,
        }
        if keyframe is not None:
            record["keyframe"] = dict(keyframe)
        validate_frame_record(record)

        self._index.write(json.dumps(record, sort_keys=True) + "\n")
        self._index.flush()
        self.count += 1
        self.total_count += 1
        self._next_sequence = sequence + 1
        self._last_frame_path = filename
        if self.count % self._checkpoint_every == 0:
            self.checkpoint()
        return record

    def record_gap(
        self,
        *,
        gap_start: datetime,
        gap_end: datetime,
        reason: str,
        dropped_estimate: int = 0,
        sequence_before: int | None = None,
        sequence_after: int | None = None,
        recovered: bool = True,
        index: bool = True,
    ) -> dict[str, Any]:
        """Record one gap in the manifest and, when recovered, in the index."""

        record: dict[str, Any] = {
            "record_type": RECORD_TYPE_GAP,
            "record_schema_version": GAP_RECORD_SCHEMA_VERSION,
            "session_id": self.session_id,
            "gap_start": _iso(gap_start),
            "gap_end": _iso(gap_end),
            "duration_seconds": max(0.0, (gap_end - gap_start).total_seconds()),
            "reason": reason,
            "dropped_estimate": max(0, int(dropped_estimate)),
            "sequence_before": sequence_before,
            "sequence_after": sequence_after,
            "recovered": bool(recovered),
        }
        validate_gap_record(record)
        self.gaps.append(record)
        self.manifest["gap_count"] = len(self.gaps)
        if index and not self._closed:
            gap_line = dict(record)
            gap_line["duration_seconds"] = round(float(gap_line["duration_seconds"]), 6)
            self._index.write(json.dumps(gap_line, sort_keys=True) + "\n")
            self._index.flush()
        self.checkpoint()
        return record

    def record_pause(
        self, *, started_at: datetime, ended_at: datetime
    ) -> dict[str, Any]:
        """Record one pause interval in the session manifest."""

        record: dict[str, Any] = {
            "pause_id": len(self.pauses) + 1,
            "started_at": _iso(started_at),
            "ended_at": _iso(ended_at),
            "duration_seconds": max(0.0, (ended_at - started_at).total_seconds()),
        }
        validate_pause_record(record)
        self.pauses.append(record)
        self.manifest["pause_count"] = len(self.pauses)
        self.checkpoint()
        return record

    # --------------------------------------------------------------- checkpoint
    def checkpoint(self, *, status: str = "running") -> None:
        """Persist enough state to resume after a process crash."""

        if self._closed:
            return
        write_json_atomic(
            self.state_path,
            {
                "schema_version": SESSION_STATE_SCHEMA_VERSION,
                "session_id": self.session_id,
                "source_id": self.manifest.get("source_id", "unknown"),
                "source_protocol": self.manifest.get("source_protocol", "unknown"),
                "sample_rate_target_hz": self.manifest.get(
                    "sample_rate_target_hz", 1.0
                ),
                "started_at": self.manifest.get("started_at"),
                "status": status,
                "last_sequence": self._next_sequence - 1,
                "frame_count": self.total_count,
                "count_this_process": self.count,
                "last_frame_path": self._last_frame_path,
                "gap_count": len(self.gaps),
                "pause_count": len(self.pauses),
                "updated_at": _iso(datetime.now(UTC)),
            },
        )

    def close(
        self,
        *,
        status: str,
        ended_at: datetime,
        error: str | None = None,
    ) -> None:
        """Finalize the session manifest and close the index file."""

        if self._closed:
            return
        if not self._index.closed:
            self._index.close()
        self._closed = True

        self.manifest.update(
            {
                "ended_at": _iso(ended_at),
                "emitted_frame_count": self.count,
                "total_frame_count": self.total_count,
                "frame_count": self.total_count,
                "gap_count": len(self.gaps),
                "pause_count": len(self.pauses),
                "last_sequence": self._next_sequence - 1,
                "status": status,
            }
        )
        if error:
            self.manifest["last_error"] = error
        validate_session_manifest(self.manifest)
        write_json_atomic(self.manifest_path, self.manifest)
        write_json_atomic(
            self.state_path,
            {
                "schema_version": SESSION_STATE_SCHEMA_VERSION,
                "session_id": self.session_id,
                "source_id": self.manifest.get("source_id", "unknown"),
                "source_protocol": self.manifest.get("source_protocol", "unknown"),
                "sample_rate_target_hz": self.manifest.get(
                    "sample_rate_target_hz", 1.0
                ),
                "started_at": self.manifest.get("started_at"),
                "status": status,
                "last_sequence": self._next_sequence - 1,
                "frame_count": self.total_count,
                "count_this_process": self.count,
                "last_frame_path": self._last_frame_path,
                "gap_count": len(self.gaps),
                "pause_count": len(self.pauses),
                "updated_at": _iso(ended_at),
            },
        )

    # ----------------------------------------------------------------- internals
    def _truncate_partial_index_line(self) -> None:
        """Drop a half-written trailing line left by a process crash."""

        if not self.index_path.exists():
            return
        payload = self.index_path.read_bytes()
        if not payload or payload.endswith(b"\n"):
            return
        newline = payload.rfind(b"\n")
        self.index_path.write_bytes(payload[: newline + 1] if newline >= 0 else b"")
