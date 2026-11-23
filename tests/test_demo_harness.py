"""Local, GPU-free tests for the live showcase harness."""

from __future__ import annotations

import json
from pathlib import Path

from demo import pipeline_status, preflight

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_capture_status_reads_manifest_index_and_pipeline_state(tmp_path: Path) -> None:
    session = tmp_path / "captures" / "demo-1"
    session.mkdir(parents=True)
    _write(
        session / "session.json",
        {
            "session_id": "demo-1",
            "status": "running",
            "frame_count": 2,
            "gaps": [],
            "pauses": [],
        },
    )
    (session / "index.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"record_type": "frame", "sequence": 0}),
                json.dumps({"record_type": "frame", "sequence": 1}),
                json.dumps({"record_type": "gap", "reason": "pause"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _write(
        session / "pipeline_state.json",
        {"next_sequence": 120, "next_index": 2, "segments_done": ["live_demo_seg0001"]},
    )

    status = pipeline_status.capture_status(session)
    assert status["session_id"] == "demo-1"
    assert status["status"] == "running"
    assert status["frames_written"] == 2
    assert status["gap_reasons"] == {"pause": 1}
    assert status["segments_done"] == ["live_demo_seg0001"]
    assert status["next_sequence"] == 120


def test_capture_status_falls_back_to_checkpoint(tmp_path: Path) -> None:
    session = tmp_path / "demo-2"
    session.mkdir()
    _write(
        session / "session_state.json",
        {"session_id": "demo-2", "status": "running", "last_sequence": 7},
    )
    assert pipeline_status.capture_status(session)["session_id"] == "demo-2"


def test_segment_statuses_read_stage_timings(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    _write(
        outputs / "live_demo_seg0001" / "benchmark_stats.json",
        {
            "stages": {
                "vggt": {"elapsed_seconds": 234.49, "keyframe_count": 120},
                "detect_and_lift": {"elapsed_seconds": 64.53, "events": 3},
                "preprocess": {"elapsed_seconds": 33.52},
                "rerun": {"elapsed_seconds": 10.37, "total_rooms": 2},
            }
        },
    )
    rows = pipeline_status.segment_statuses("live_demo", outputs)
    assert len(rows) == 1
    assert rows[0]["segment"] == "live_demo_seg0001"
    assert rows[0]["vggt_s"] == 234.5
    assert rows[0]["events"] == 3
    assert rows[0]["rooms"] == 2


def test_store_status_does_not_create_a_database_when_absent(tmp_path: Path) -> None:
    store_root = tmp_path / "homes"
    result = pipeline_status.store_status("aegis-demo", store_root)
    assert result["db_exists"] is False
    assert not (store_root / "aegis-demo" / "memory.db").exists()


def test_render_shows_the_whole_chain(tmp_path: Path) -> None:
    session = tmp_path / "captures" / "demo-3"
    session.mkdir(parents=True)
    _write(session / "session.json", {"session_id": "demo-3", "status": "running"})
    outputs = tmp_path / "outputs"
    _write(
        outputs / "live_demo_seg0001" / "benchmark_stats.json",
        {"stages": {"vggt": {"elapsed_seconds": 12.0, "keyframe_count": 30}}},
    )
    rendered = pipeline_status.render(
        session, "live_demo", "aegis-demo", tmp_path / "homes", outputs
    )
    for heading in ("AEGIS LIVE MEMORY BACKBONE", "Capture:", "Home store:"):
        assert heading in rendered
    assert "live_demo_seg0001" in rendered


def test_preflight_checks_are_pure_and_local(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("HF_TOKEN=hf_test\n", encoding="utf-8")
    assert preflight.check_env_file(env).state == preflight.PASS
    env.write_text("HF_TOKEN=\n", encoding="utf-8")
    assert preflight.check_env_file(env).state == preflight.FAIL

    result = tmp_path / "vggt_window.json"
    _write(result, {"recommended_max_keyframes": 96})
    assert preflight.check_vggt_window(result, 60).state == preflight.PASS
    assert preflight.check_vggt_window(result, 120).state == preflight.WARN
    assert preflight.check_vggt_window(None, 60).state == preflight.WARN


def test_preflight_reads_the_real_live_config(tmp_path: Path) -> None:
    config = REPO_ROOT / "config" / "live.yaml"
    check = preflight.check_config(config, 60)
    assert check.state == preflight.PASS
    assert preflight.check_config(config, 9999).state == preflight.FAIL
