"""Pause/resume of live capture from the app (FR1.3)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
from fastapi.testclient import TestClient

from aegis.ingestion.live_storage import LiveSessionWriter
from aegis.remote.api import app

client = TestClient(app)


def test_status_without_configuration_is_unavailable(monkeypatch) -> None:
    monkeypatch.delenv("AEGIS_CAPTURE_DIR", raising=False)
    monkeypatch.delenv("AEGIS_CAPTURE_PAUSE_FILE", raising=False)
    assert client.get("/api/v1/capture/status").json()["available"] is False
    assert client.post("/api/v1/capture/pause").status_code == 503


def test_pause_and_resume_are_idempotent(tmp_path, monkeypatch) -> None:
    captures = tmp_path / "captures"
    pause_file = tmp_path / "pause"
    writer = LiveSessionWriter(
        captures,
        "s1",
        {
            "schema_version": 2,
            "source_id": "phone",
            "source_protocol": "fixture",
            "sample_rate_target_hz": 2.0,
        },
    )
    writer.write(
        np.zeros((8, 8, 3), dtype=np.uint8),
        received_at=datetime(2026, 11, 15, tzinfo=UTC) + timedelta(seconds=1),
        source_id="phone",
        sample_rate=2.0,
        source_protocol="fixture",
    )
    writer.checkpoint(status="running")
    monkeypatch.setenv("AEGIS_CAPTURE_DIR", str(captures))
    monkeypatch.setenv("AEGIS_CAPTURE_PAUSE_FILE", str(pause_file))

    status = client.get("/api/v1/capture/status").json()
    assert status["available"] is True
    assert status["session_id"] == "s1"
    assert status["status"] == "running"
    assert status["paused"] is False

    for _ in range(2):
        assert client.post("/api/v1/capture/pause").json()["paused"] is True
        assert pause_file.exists()
    for _ in range(2):
        assert client.post("/api/v1/capture/resume").json()["paused"] is False
        assert not pause_file.exists()
