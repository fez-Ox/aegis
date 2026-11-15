"""Tests for promoting a long live capture as bounded segments."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

from aegis.ingestion.contracts import validate_normalized_metadata
from aegis.ingestion.live_handoff import plan_segments, promote_live_segments
from aegis.ingestion.live_storage import LiveSessionWriter

BASE = datetime(2026, 11, 15, 9, 0, tzinfo=UTC)


def _session(root: Path, times: list[float]) -> Path:
    writer = LiveSessionWriter(
        root,
        "long",
        {
            "schema_version": 2,
            "source_id": "phone",
            "source_protocol": "fixture",
            "sample_rate_target_hz": 2.0,
        },
    )
    for step, seconds in enumerate(times):
        writer.write(
            np.full((12, 16, 3), step % 255, dtype=np.uint8),
            received_at=BASE + timedelta(seconds=seconds),
            source_id="phone",
            sample_rate=2.0,
            source_protocol="fixture",
        )
    writer.close(status="completed", ended_at=BASE + timedelta(seconds=times[-1] + 1))
    return writer.session_dir


def _records(times):
    return [
        {"sequence": i, "capture_timestamp": (BASE + timedelta(seconds=t)).isoformat()}
        for i, t in enumerate(times)
    ]


def test_segments_split_by_frame_count() -> None:
    segments = plan_segments(_records([i * 0.5 for i in range(28)]), segment_frames=10)
    assert [len(s) for s in segments] == [10, 10, 8]


def test_short_tail_is_merged() -> None:
    segments = plan_segments(_records([i * 0.5 for i in range(23)]), segment_frames=10)
    assert [len(s) for s in segments] == [10, 13]


def test_long_gap_starts_new_segment() -> None:
    times = [0, 1, 2, 3, 100, 101, 102]
    segments = plan_segments(_records(times), segment_frames=10, min_tail=2)
    assert [len(s) for s in segments] == [4, 3]
    # A short tail after a long gap is not merged across the gap.
    segments = plan_segments(_records([0, 1, 2, 3, 100]), segment_frames=10)
    assert [len(s) for s in segments] == [4, 1]


def test_start_sequence_skips_promoted_frames_and_tail_can_wait(tmp_path) -> None:
    session = _session(tmp_path / "captures", [i * 0.5 for i in range(25)])
    first = promote_live_segments(
        session,
        base_dataset_id="live",
        segment_frames=10,
        data_root=tmp_path / "data",
        include_tail=False,
    )
    assert [r.dataset_id for r in first] == ["live_seg0001", "live_seg0002"]
    assert first[-1].last_sequence == 19
    rest = promote_live_segments(
        session,
        base_dataset_id="live",
        segment_frames=10,
        data_root=tmp_path / "data",
        start_sequence=first[-1].last_sequence + 1,
        first_index=3,
    )
    assert [(r.dataset_id, r.frame_count) for r in rest] == [("live_seg0003", 5)]


def test_segment_metadata_validates_and_keeps_capture_timestamps(tmp_path) -> None:
    session = _session(tmp_path / "captures", [i * 0.5 for i in range(14)])
    results = promote_live_segments(
        session, base_dataset_id="live", segment_frames=6, data_root=tmp_path / "data"
    )
    metadata = json.loads((results[1].dataset_dir / "metadata.json").read_text())
    validate_normalized_metadata(metadata)
    assert metadata["frames"][0]["timestamp"] == 0.0
    assert metadata["frames"][0]["capture_timestamp"].startswith("2026-11-15T09:00:03")
    assert metadata["segment"] == {
        "index": 2,
        "base_dataset_id": "live",
        "first_sequence": 6,
        "last_sequence": 13,
    }


def _writer(root: Path) -> LiveSessionWriter:
    return LiveSessionWriter(
        root,
        "follow",
        {
            "schema_version": 2,
            "source_id": "phone",
            "source_protocol": "fixture",
            "sample_rate_target_hz": 2.0,
        },
    )


def _write_frames(writer: LiveSessionWriter, start: int, count: int) -> None:
    for step in range(start, start + count):
        writer.write(
            np.full((12, 16, 3), step % 255, dtype=np.uint8),
            received_at=BASE + timedelta(seconds=step * 0.5),
            source_id="phone",
            sample_rate=2.0,
            source_protocol="fixture",
        )


def test_pipeline_state_resume(tmp_path) -> None:
    from aegis.ingestion.segment_runner import load_state, run_live_segments

    session = _session(tmp_path / "captures", [i * 0.5 for i in range(25)])
    seen: list[str] = []

    def failing(result) -> None:
        seen.append(result.dataset_id)
        if result.dataset_id.endswith("seg0002"):
            raise RuntimeError("modal outage")

    try:
        run_live_segments(
            session,
            base_dataset_id="live",
            segment_frames=10,
            process=failing,
            data_root=tmp_path / "data",
        )
    except RuntimeError:
        pass
    state = load_state(session)
    assert state["segments_done"] == ["live_seg0001"]
    assert state["next_sequence"] == 10
    assert not (tmp_path / "data" / "live_seg0001" / "frames").exists()

    done = run_live_segments(
        session,
        base_dataset_id="live",
        segment_frames=10,
        process=lambda result: seen.append(result.dataset_id),
        data_root=tmp_path / "data",
    )
    assert done == ["live_seg0002"]
    assert seen == ["live_seg0001", "live_seg0002", "live_seg0002"]
    assert load_state(session)["segments_done"] == ["live_seg0001", "live_seg0002"]


def test_follow_mode_waits_for_tail_until_capture_stops(tmp_path) -> None:
    from aegis.ingestion.segment_runner import run_live_segments

    writer = _writer(tmp_path / "captures")
    _write_frames(writer, 0, 25)
    writer.checkpoint(status="running")
    processed: list[tuple[str, int]] = []

    def fake_sleep(_seconds: float) -> None:
        _write_frames(writer, 25, 10)
        writer.close(status="completed", ended_at=BASE + timedelta(seconds=40))

    done = run_live_segments(
        writer.session_dir,
        base_dataset_id="live",
        segment_frames=10,
        process=lambda r: processed.append((r.dataset_id, r.frame_count)),
        data_root=tmp_path / "data",
        follow=True,
        sleep=fake_sleep,
    )
    assert processed == [
        ("live_seg0001", 10),
        ("live_seg0002", 10),
        ("live_seg0003", 15),
    ]
    assert done == ["live_seg0001", "live_seg0002", "live_seg0003"]
