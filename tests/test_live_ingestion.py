"""Deterministic tests for the live FR1/FR2 ingestion boundary."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import numpy as np

from aegis.ingestion.live_pipeline import LiveIngestionConfig, ingest_live
from aegis.ingestion.live_source import safe_url
from aegis.ingestion.live_storage import LiveSessionWriter


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
    base = datetime(2025, 1, 1, tzinfo=UTC)
    frames = [
        type(
            "Frame",
            (),
            {
                "image": np.zeros((4, 5, 3), dtype=np.uint8),
                "received_at": base + timedelta(seconds=i * 0.25),
            },
        )()
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
