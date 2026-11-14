"""Tests for absolute (wall-clock) time handling."""

from __future__ import annotations

import json

import pytest

from aegis.core.config import RuntimeConfig
from aegis.core.paths import dataset_paths
from aegis.core.timeutil import parse_iso, shift_iso, to_utc_iso
from aegis.ingestion.download import set_recorded_at
from aegis.remote.workers import _wallclock_by_frame


def test_to_utc_iso_fixed_format() -> None:
    assert to_utc_iso("2026-11-15T10:00:00+05:00") == "2026-11-15T05:00:00.000000+00:00"
    assert to_utc_iso("2026-11-15T05:00:00Z") == "2026-11-15T05:00:00.000000+00:00"
    assert (
        shift_iso("2026-11-15T05:00:00+00:00", 1.5)
        == "2026-11-15T05:00:01.500000+00:00"
    )
    with pytest.raises(ValueError):
        parse_iso("2026-11-15T05:00:00")


def _paths(tmp_path):
    config = RuntimeConfig.from_mapping({"storage": {"data_mount": str(tmp_path)}})
    return dataset_paths(config, "ds")


def test_live_frames_use_capture_timestamps(tmp_path) -> None:
    frames = [
        {
            "frame_id": 0,
            "timestamp": 0.0,
            "capture_timestamp": "2026-11-15T10:00:00+05:00",
        },
        {
            "frame_id": 1,
            "timestamp": 0.5,
            "capture_timestamp": "2026-11-15T10:00:00.5+05:00",
        },
    ]
    wallclock, source = _wallclock_by_frame(_paths(tmp_path), frames)
    assert source == "capture"
    assert wallclock[1] == "2026-11-15T05:00:00.500000+00:00"


def test_batch_video_uses_recorded_at(tmp_path) -> None:
    paths = _paths(tmp_path)
    set_recorded_at(paths.root, "2026-11-15T09:00:00+05:00")
    assert json.loads(paths.source_metadata.read_text())["recorded_at"].endswith(
        "+00:00"
    )
    wallclock, source = _wallclock_by_frame(paths, [{"frame_id": 3, "timestamp": 2.0}])
    assert source == "recorded_at"
    assert wallclock[3] == "2026-11-15T04:00:02.000000+00:00"


def test_no_time_information_gives_none(tmp_path) -> None:
    wallclock, source = _wallclock_by_frame(
        _paths(tmp_path), [{"frame_id": 0, "timestamp": 0.0}]
    )
    assert (wallclock, source) == ({}, "none")
