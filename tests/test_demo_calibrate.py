"""Local tests for the one-command demo calibration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from demo import calibrate

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_local_vggt_evidence_from_existing_runs(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    _write(
        outputs / "demo04" / "benchmark_stats.json",
        {
            "stages": {
                "vggt": {
                    "keyframe_count": 117,
                    "peak_vram_gb": 14.79,
                    "elapsed_seconds": 234.49,
                }
            }
        },
    )
    rows, spk = calibrate.local_vggt_evidence(outputs, 22.06)
    assert len(rows) == 1
    assert rows[0]["keyframes"] == 117
    assert rows[0]["ok"] is True
    assert rows[0]["vram_fraction"] == 0.67
    assert spk == pytest.approx(2.005, abs=0.01)


def test_choose_segment_frames_respects_the_ceiling() -> None:
    assert calibrate.choose_segment_frames(120, 0.5, 90) == 40
    assert calibrate.choose_segment_frames(30, 2.0, 90) == 30
    assert calibrate.choose_segment_frames(10, 0.5, 90) == 10


def test_calibrate_writes_result_and_conf_without_a_gpu(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    outputs = tmp_path / "outputs"
    _write(
        outputs / "demo04" / "benchmark_stats.json",
        {
            "stages": {
                "vggt": {
                    "keyframe_count": 117,
                    "peak_vram_gb": 14.79,
                    "elapsed_seconds": 234.49,
                }
            }
        },
    )
    code = calibrate.main(
        [
            "--outputs-root",
            str(outputs),
            "--config-path",
            str(REPO_ROOT / "config" / "live.yaml"),
        ]
    )
    assert code == 0
    result = json.loads(
        (tmp_path / "outputs/evaluation/vggt_window.json").read_text(encoding="utf-8")
    )
    assert result["recommended_max_keyframes"] == 117
    assert 0 < result["segment_frames"] <= 117
    assert result["accepted_rate_source"].startswith("assumption")
    assert "SEGMENT_FRAMES=" in (tmp_path / "demo/demo.conf").read_text(
        encoding="utf-8"
    )


def test_calibrate_refuses_an_oversized_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _write(
        tmp_path / "outputs" / "demo04" / "benchmark_stats.json",
        {
            "stages": {
                "vggt": {
                    "keyframe_count": 60,
                    "peak_vram_gb": 14.0,
                    "elapsed_seconds": 120.0,
                }
            }
        },
    )
    code = calibrate.main(
        [
            "--outputs-root",
            str(tmp_path / "outputs"),
            "--config-path",
            str(REPO_ROOT / "config" / "live.yaml"),
            "--segment-frames",
            "120",
        ]
    )
    assert code == 2
