"""CLI and upload contract tests for the live capture path."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from aegis.ingestion import download, live_cli
from aegis.ingestion.live_source import DecodedFrame


class _FakeSource:
    """Finite in-memory replacement for an MJPEG capture source."""

    def __init__(self, count: int = 3):
        self.count = count

    def frames(self):
        start = datetime(2025, 1, 1, tzinfo=UTC)
        for step in range(self.count):
            generator = np.random.default_rng(1000 + step)
            yield DecodedFrame(
                image=generator.integers(0, 255, (12, 16, 3), dtype=np.uint8),
                received_at=start + timedelta(seconds=step * 0.5),
            )


def test_cli_help_exits_cleanly() -> None:
    with pytest.raises(SystemExit) as excinfo:
        live_cli.main(["--help"])
    assert excinfo.value.code == 0


def test_cli_requires_url_and_session_for_resume() -> None:
    with pytest.raises(SystemExit) as excinfo:
        live_cli.main([])
    assert excinfo.value.code == 2

    with pytest.raises(SystemExit) as excinfo:
        live_cli.main(["--url", "http://phone/video", "--resume"])
    assert excinfo.value.code == 2


def test_cli_captures_and_promotes_a_session(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(live_cli, "OpenCVMjpegSource", lambda _url: _FakeSource(3))

    exit_code = live_cli.main(
        [
            "--url",
            "http://phone/video",
            "--output-root",
            str(tmp_path / "captures"),
            "--session-id",
            "cli-session",
            "--promote-dataset-id",
            "cli_dataset",
            "--promote-data-root",
            str(tmp_path / "data"),
            "--reconnect-interval",
            "0",
            "--reconnect-timeout",
            "0",
            "--no-keyframe-selection",
        ]
    )

    # The finite fixture ends, so the session terminates as disconnected.
    assert exit_code == 1
    session = tmp_path / "captures" / "cli-session"
    manifest = json.loads((session / "session.json").read_text(encoding="utf-8"))
    assert manifest["frame_count"] == 3
    assert manifest["status"] == "disconnected"

    dataset = tmp_path / "data" / "cli_dataset"
    metadata = json.loads((dataset / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["preprocess_source"] == "live_session"
    assert metadata["frame_count"] == 3
    assert (dataset / "frames" / "frame_000000.png").is_file()
    assert (dataset / "live_timestamps.json").is_file()


def test_cli_uses_config_defaults(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(live_cli, "OpenCVMjpegSource", lambda _url: _FakeSource(2))

    live_cli.main(
        [
            "--url",
            "http://phone/video",
            "--output-root",
            str(tmp_path / "captures"),
            "--session-id",
            "configured",
            "--config-path",
            "config/demo.yaml",
            "--reconnect-timeout",
            "0",
        ]
    )

    manifest = json.loads(
        (tmp_path / "captures" / "configured" / "session.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["sample_rate_target_hz"] == 2.0
    assert manifest["max_duration_seconds"] == 3600.0
    assert manifest["buffer_capacity"] == 30
    assert manifest["checkpoint_every"] == 5
    assert manifest["keyframe_selection"]["enabled"] is True
    assert manifest["keyframe_selection"]["accepted"] >= 1


def test_upload_dataset_uses_bare_dataset_id_as_remote_path(
    tmp_path, monkeypatch
) -> None:
    dataset = tmp_path / "data" / "live_session_1"
    dataset.mkdir(parents=True)
    (dataset / "metadata.json").write_text("{}", encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_put(local_path, remote_path, volume_name="aegis-poc-data", force=True):
        captured.update(
            local_path=Path(local_path),
            remote_path=remote_path,
            volume_name=volume_name,
            force=force,
        )
        return True

    monkeypatch.setattr(download, "upload_to_modal_volume", fake_put)

    assert download.upload_dataset_to_modal_volume(
        dataset, "live_session_1", volume_name="aegis-poc-data"
    )
    assert captured["local_path"] == dataset
    assert captured["remote_path"] == "live_session_1"
    assert captured["volume_name"] == "aegis-poc-data"


def test_upload_dataset_rejects_missing_directory(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        download.upload_dataset_to_modal_volume(tmp_path / "missing", "absent")


def test_upload_dataset_rejects_unsafe_dataset_id(tmp_path) -> None:
    dataset = tmp_path / "data" / "ok"
    dataset.mkdir(parents=True)
    with pytest.raises(ValueError):
        download.upload_dataset_to_modal_volume(dataset, "../escape")
