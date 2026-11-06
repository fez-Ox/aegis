"""Tests for live-session promotion and timestamp-preserving preprocessing."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import cv2
import numpy as np

from aegis.core.config import (
    CameraConfig,
    RuntimeConfig,
    VideoConfig,
    config_to_dict,
)
from aegis.ingestion.live_handoff import (
    find_latest_live_session,
    promote_live_session,
)
from aegis.ingestion.live_storage import LiveSessionWriter
from aegis.ingestion.video import preprocess_video
from aegis.remote.workers import run_preprocess

BASE = datetime(2025, 1, 1, tzinfo=UTC)


def _make_session(root: Path, session_id: str = "session-1") -> Path:
    writer = LiveSessionWriter(
        root,
        session_id,
        {
            "schema_version": 2,
            "source_id": "phone",
            "source_protocol": "fixture",
            "sample_rate_target_hz": 2.0,
        },
    )
    for step, seconds in enumerate((0.0, 1.5, 3.0)):
        writer.write(
            np.full((24, 32, 3), 40 + step * 60, dtype=np.uint8),
            received_at=BASE + timedelta(seconds=seconds),
            source_id="phone",
            sample_rate=2.0,
            source_protocol="fixture",
        )
    writer.close(status="completed", ended_at=BASE + timedelta(seconds=3.5))
    return writer.session_dir


def test_promote_live_session_materialises_dataset(tmp_path) -> None:
    session = _make_session(tmp_path / "captures")
    result = promote_live_session(
        session,
        dataset_id="live_session_1",
        data_root=tmp_path / "data",
        video=VideoConfig(width=40, height=30),
    )

    assert result.frame_count == 3
    assert result.duration_sec == 3.0
    assert result.resolution == (40, 30)
    dataset = tmp_path / "data" / "live_session_1"
    assert (dataset / "frames" / "frame_000000.png").exists()
    assert (dataset / "frames" / "frame_000002.png").exists()
    assert (dataset / "source_metadata.json").exists()
    assert (dataset / "live_session.json").exists()
    assert (dataset / "live_timestamps.json").exists()

    metadata = json.loads((dataset / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["preprocess_source"] == "live_session"
    assert metadata["timebase"] == "capture"
    assert metadata["frame_count"] == 3
    assert metadata["resolution"] == [40, 30]
    assert [frame["timestamp"] for frame in metadata["frames"]] == [0.0, 1.5, 3.0]
    assert metadata["live_session_id"] == "session-1"

    image = cv2.imread(str(dataset / "frames" / "frame_000000.png"))
    assert image is not None
    assert image.shape[:2] == (30, 40)

    timestamps = json.loads(
        (dataset / "live_timestamps.json").read_text(encoding="utf-8")
    )
    assert len(timestamps["timestamps"]) == 3


def test_promotion_refuses_to_overwrite_batch_video(tmp_path) -> None:
    session = _make_session(tmp_path / "captures")
    dataset = tmp_path / "data" / "existing"
    dataset.mkdir(parents=True)
    (dataset / "video.mp4").write_bytes(b"not really a video")

    try:
        promote_live_session(
            session, dataset_id="existing", data_root=tmp_path / "data"
        )
    except ValueError as exc:
        assert "video.mp4" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected promotion to refuse an existing video")


def test_run_preprocess_accepts_promoted_live_dataset(tmp_path) -> None:
    session = _make_session(tmp_path / "captures")
    promote_live_session(
        session,
        dataset_id="live_session_1",
        data_root=tmp_path,
        video=VideoConfig(width=40, height=30),
    )
    config = RuntimeConfig.from_mapping({"storage": {"data_mount": str(tmp_path)}})

    result = run_preprocess("live_session_1", config_to_dict(config))

    assert result["preprocess_source"] == "live_session"
    assert result["timebase"] == "capture"
    assert result["frame_count"] == 3
    assert result["live_session_id"] == "session-1"
    assert (tmp_path / "live_session_1" / "outputs" / "benchmark_stats.json").exists()


def test_preprocess_video_preserves_supplied_capture_timestamps(tmp_path) -> None:
    input_path = tmp_path / "input.mp4"
    writer = cv2.VideoWriter(
        str(input_path), cv2.VideoWriter_fourcc(*"mp4v"), 2.0, (20, 12)
    )
    assert writer.isOpened()
    for value in range(5):
        writer.write(np.full((12, 20, 3), value * 40, dtype=np.uint8))
    writer.release()

    metadata = preprocess_video(
        input_path,
        tmp_path / "frames",
        tmp_path / "metadata.json",
        tmp_path / "calib.txt",
        VideoConfig(sample_fps=2, width=20, height=12),
        CameraConfig(allow_approximate=True),
        dataset_id="timestamped",
        source_timestamps=[100.0, 100.25, 100.5, 100.75, 101.0],
    )

    assert metadata["timebase"] == "capture"
    assert [frame["timestamp"] for frame in metadata["frames"]] == [0.0, 0.5, 1.0]
    assert metadata["frame_count"] == 3


def test_find_latest_live_session_prefers_newest(tmp_path) -> None:
    older = _make_session(tmp_path, "older")
    newer = _make_session(tmp_path, "newer")
    newer.touch()

    assert find_latest_live_session(tmp_path) == newer
    assert older.exists()


def test_promoted_session_manifest_is_copied(tmp_path) -> None:
    session = _make_session(tmp_path / "captures")
    promote_live_session(session, dataset_id="copy", data_root=tmp_path / "data")
    copied = json.loads(
        (tmp_path / "data" / "copy" / "live_session.json").read_text(encoding="utf-8")
    )
    assert copied["session_id"] == "session-1"
