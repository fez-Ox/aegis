"""Deterministic tests for the live FR1/FR2 ingestion boundary."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import numpy as np

from aegis.core.config import KeyframeConfig
from aegis.ingestion.contracts import load_session_manifest, read_live_index
from aegis.ingestion.live_pipeline import LiveIngestionConfig, ingest_live
from aegis.ingestion.live_source import safe_url
from aegis.ingestion.live_storage import LiveSessionWriter

BASE = datetime(2025, 1, 1, tzinfo=UTC)


def test_safe_url_redacts_credentials() -> None:
    assert safe_url("http://user:secret@192.168.1.20:8080/video") == (
        "http://192.168.1.20:8080/video"
    )


def test_live_session_writer_persists_frame_contract(tmp_path) -> None:
    writer = LiveSessionWriter(tmp_path, "session-1", {"schema_version": 1})
    now = datetime(2025, 1, 1, tzinfo=UTC)
    record = writer.write(
        np.zeros((12, 20, 3), dtype=np.uint8),
        received_at=now,
        source_id="test-source",
        sample_rate=2.0,
        source_protocol="fixture",
    )
    writer.close(status="completed", ended_at=now)

    frame_path = tmp_path / "session-1" / record["frame_path"]
    assert frame_path.read_bytes()[:2] == b"\xff\xd8"
    index_record = json.loads(
        (tmp_path / "session-1" / "index.jsonl").read_text(encoding="utf-8")
    )
    assert index_record["sequence"] == 0
    assert index_record["width"] == 20
    assert index_record["timestamp_source"] == "laptop_receive_decode"


def test_live_ingestion_samples_at_target_rate(tmp_path) -> None:
    frames = [
        SimpleNamespace(
            image=np.zeros((4, 5, 3), dtype=np.uint8),
            received_at=BASE + timedelta(seconds=i * 0.25),
            captured_at=None,
        )
        for i in range(5)
    ]

    class FiniteSource:
        def frames(self):
            yield from frames

    result = ingest_live(
        lambda: FiniteSource(),
        LiveIngestionConfig(
            output_root=tmp_path,
            sample_fps=2,
            max_duration_seconds=10,
            reconnect_timeout_seconds=0,
        ),
        session_id="sample-test",
        sleep_fn=lambda _: None,
    )

    assert result.status == "disconnected"
    assert result.frames == 3
    assert (
        len(
            (tmp_path / "sample-test" / "index.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        )
        == 3
    )


def test_each_live_session_has_unique_output_directory(tmp_path) -> None:
    config = LiveIngestionConfig(output_root=tmp_path, max_duration_seconds=0)

    first = ingest_live(lambda: None, config)
    second = ingest_live(lambda: None, config)

    assert first.output_dir != second.output_dir
    assert first.output_dir.exists() and second.output_dir.exists()


class _Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value


def _source_frame(seconds: float, image: Any | None = None) -> Any:
    return SimpleNamespace(
        image=(np.full((8, 12, 3), 127, dtype=np.uint8) if image is None else image),
        received_at=BASE + timedelta(seconds=seconds),
        captured_at=None,
    )


def test_pause_skips_frames_and_records_gap(tmp_path) -> None:
    clock = _Clock()

    class PausableSource:
        def frames(self):
            for step in range(13):
                clock.value = step * 0.25
                yield _source_frame(step * 0.25)

    result = ingest_live(
        lambda: PausableSource(),
        LiveIngestionConfig(
            output_root=tmp_path,
            sample_fps=2,
            max_duration_seconds=30,
            reconnect_timeout_seconds=0,
            checkpoint_every=1,
        ),
        session_id="paused",
        sleep_fn=lambda _: None,
        clock=clock,
        pause_check=lambda: 1.0 <= clock.value < 2.0,
    )

    assert result.frames == 5
    assert result.pauses == 1
    records = read_live_index(tmp_path / "paused" / "index.jsonl")
    pause_gaps = [
        record
        for record in records
        if record.get("reason") == "pause" and record["record_type"] == "gap"
    ]
    assert len(pause_gaps) == 1
    assert pause_gaps[0]["dropped_estimate"] == 2

    manifest = load_session_manifest(tmp_path / "paused")
    assert manifest["pause_count"] == 1
    assert manifest["pauses"][0]["duration_seconds"] >= 0


def test_terminal_disconnect_gap_is_manifest_only(tmp_path) -> None:
    class FiniteSource:
        def frames(self):
            for step in range(5):
                yield _source_frame(step * 0.25)

    result = ingest_live(
        lambda: FiniteSource(),
        LiveIngestionConfig(
            output_root=tmp_path,
            sample_fps=2,
            max_duration_seconds=10,
            reconnect_timeout_seconds=0,
        ),
        session_id="terminal",
        sleep_fn=lambda _: None,
    )

    assert result.status == "disconnected"
    records = read_live_index(tmp_path / "terminal" / "index.jsonl")
    assert all(record["record_type"] == "frame" for record in records)
    manifest = load_session_manifest(tmp_path / "terminal")
    disconnect_gaps = [gap for gap in manifest["gaps"] if gap["reason"] == "disconnect"]
    assert len(disconnect_gaps) == 1
    assert disconnect_gaps[0]["recovered"] is False


def test_recovered_disconnect_records_index_gap(tmp_path) -> None:
    clock = _Clock()

    class FailingSource:
        def __init__(self, count: int):
            self.count = count

        def frames(self):
            for step in range(self.count):
                clock.value = step * 0.5
                yield _source_frame(step * 0.5)
            raise ConnectionError("stream dropped")

    calls = 0

    def factory():
        nonlocal calls
        calls += 1
        if calls == 1:
            return FailingSource(2)
        if calls == 2:

            class GoodSource:
                def frames(self):
                    for step in range(2, 5):
                        clock.value = step * 0.5
                        yield _source_frame(step * 0.5)

            return GoodSource()
        clock.value += 100.0
        return FailingSource(0)

    result = ingest_live(
        factory,
        LiveIngestionConfig(
            output_root=tmp_path,
            sample_fps=2,
            max_duration_seconds=1000,
            reconnect_interval_seconds=0,
            reconnect_timeout_seconds=30,
        ),
        session_id="recovered",
        sleep_fn=lambda _: None,
        clock=clock,
    )

    assert result.status == "disconnected"
    assert result.frames == 5
    assert result.reconnects >= 1
    records = read_live_index(tmp_path / "recovered" / "index.jsonl")
    recovered = [
        record
        for record in records
        if record.get("record_type") == "gap"
        and record.get("reason") == "disconnect"
        and record.get("recovered") is True
    ]
    assert len(recovered) == 1


def test_disconnect_reconnects_within_fifteen_seconds(tmp_path) -> None:
    clock = _Clock()

    class DroppingSource:
        def frames(self):
            raise ConnectionError("link down")
            yield  # pragma: no cover - keeps this method a generator

    class RecoveredSource:
        def frames(self):
            for _step in range(3):
                clock.value += 0.5
                yield _source_frame(clock.value)

    calls = 0

    def factory():
        nonlocal calls
        calls += 1
        if calls <= 4:
            return DroppingSource()
        if calls == 5:
            return RecoveredSource()
        return DroppingSource()

    def fake_sleep(seconds: float) -> None:
        clock.value += seconds

    result = ingest_live(
        factory,
        LiveIngestionConfig(
            output_root=tmp_path,
            sample_fps=2,
            max_duration_seconds=1000,
            reconnect_interval_seconds=3,
            reconnect_timeout_seconds=30,
        ),
        session_id="fast-recovery",
        sleep_fn=fake_sleep,
        clock=clock,
    )

    assert result.status == "disconnected"
    assert result.reconnects >= 4
    records = read_live_index(tmp_path / "fast-recovery" / "index.jsonl")
    recovered = [
        record
        for record in records
        if record.get("record_type") == "gap"
        and record.get("reason") == "disconnect"
        and record.get("recovered") is True
    ]
    assert len(recovered) == 1
    outage_seconds = recovered[0]["dropped_estimate"] / 2
    assert outage_seconds <= 15


def test_stall_buffer_recovers_and_records_gap(tmp_path) -> None:
    remaining = {"failures": 3}

    class FlakyWriter(LiveSessionWriter):
        def write(self, *args, **kwargs):
            if remaining["failures"] > 0:
                remaining["failures"] -= 1
                raise OSError("disk busy")
            return super().write(*args, **kwargs)

    def factory(root, session_id, manifest, **kwargs):
        return FlakyWriter(root, session_id, manifest, **kwargs)

    class Source:
        def frames(self):
            for step in range(8):
                yield _source_frame(step * 0.25)

    result = ingest_live(
        lambda: Source(),
        LiveIngestionConfig(
            output_root=tmp_path,
            sample_fps=2,
            max_duration_seconds=10,
            reconnect_timeout_seconds=0,
            buffer_capacity=30,
        ),
        session_id="stalled",
        sleep_fn=lambda _: None,
        writer_factory=factory,
    )

    assert result.frames == 4
    assert result.dropped_frames == 0
    records = read_live_index(tmp_path / "stalled" / "index.jsonl")
    stall_gaps = [
        record
        for record in records
        if record.get("record_type") == "gap"
        and record.get("reason") == "storage_stall"
    ]
    assert len(stall_gaps) == 1
    assert stall_gaps[0]["recovered"] is True


def test_resume_after_crash_continues_sequence(tmp_path) -> None:
    manifest = {
        "schema_version": 2,
        "source_id": "phone",
        "source_protocol": "fixture",
        "sample_rate_target_hz": 2.0,
    }
    writer = LiveSessionWriter(tmp_path, "crash-session", manifest, checkpoint_every=1)
    for step in range(2):
        writer.write(
            np.full((8, 12, 3), 127, dtype=np.uint8),
            received_at=BASE + timedelta(seconds=step * 0.5),
            source_id="phone",
            sample_rate=2.0,
            source_protocol="fixture",
        )
    writer._index.close()
    with (tmp_path / "crash-session" / "index.jsonl").open("ab") as handle:
        handle.write(b'{"partial":')

    class ResumedSource:
        def frames(self):
            for step in range(2, 5):
                yield _source_frame(step * 0.5)

    result = ingest_live(
        lambda: ResumedSource(),
        LiveIngestionConfig(
            output_root=tmp_path,
            sample_fps=2,
            max_duration_seconds=10,
            reconnect_timeout_seconds=0,
        ),
        session_id="crash-session",
        resume=True,
        sleep_fn=lambda _: None,
    )

    assert result.resumed is True
    assert result.frames == 3
    assert result.total_frames == 5
    records = read_live_index(tmp_path / "crash-session" / "index.jsonl")
    sequences = [record["sequence"] for record in records if "sequence" in record]
    assert sequences == [0, 1, 2, 3, 4]
    manifest = load_session_manifest(tmp_path / "crash-session")
    assert manifest["resumed"] is True


def test_keyframe_selection_filters_duplicates(tmp_path) -> None:
    first = np.random.default_rng(7).integers(0, 255, (48, 64, 3), dtype=np.uint8)
    second = np.random.default_rng(8).integers(0, 255, (48, 64, 3), dtype=np.uint8)
    images = [first, first, first, first, second]

    class Source:
        def frames(self):
            for step, image in enumerate(images):
                yield _source_frame(step * 0.25, image=image)

    result = ingest_live(
        lambda: Source(),
        LiveIngestionConfig(
            output_root=tmp_path,
            sample_fps=2,
            max_duration_seconds=10,
            reconnect_timeout_seconds=0,
            keyframe=KeyframeConfig(max_interval_seconds=10.0),
        ),
        session_id="keyframes",
        sleep_fn=lambda _: None,
    )

    assert result.frames == 2
    assert result.rejected_frames == 1
    manifest = load_session_manifest(tmp_path / "keyframes")
    assert manifest["keyframe_selection"]["evaluated"] == 3
    assert manifest["keyframe_selection"]["rejected"] == 1


def test_simulated_one_hour_session(tmp_path) -> None:
    clock = _Clock()
    total_frames = 3600

    class HourSource:
        def frames(self):
            for step in range(total_frames + 1):
                clock.value = float(step)
                yield _source_frame(step)

    result = ingest_live(
        lambda: HourSource(),
        LiveIngestionConfig(
            output_root=tmp_path,
            sample_fps=1,
            max_duration_seconds=3600,
            reconnect_timeout_seconds=0,
            checkpoint_every=100,
        ),
        session_id="soak",
        sleep_fn=lambda _: None,
        clock=clock,
    )

    assert result.status == "time_limit"
    assert result.frames == total_frames
    assert result.gaps == 0
    assert result.pauses == 0
    manifest = load_session_manifest(tmp_path / "soak")
    assert manifest["frame_count"] == total_frames
    assert manifest["status"] == "time_limit"
