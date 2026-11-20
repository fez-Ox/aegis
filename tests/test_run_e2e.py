"""Tests for the end-to-end runner (dry-run only; no Modal, no network)."""

from __future__ import annotations

import importlib.util
import urllib.error
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_e2e.py"


@pytest.fixture(scope="module")
def runner_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("run_e2e", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dry_run_prints_the_whole_chain(runner_module, capsys):
    code = runner_module.main(
        ["--dry-run", "--video", "put_shoes", "--dataset-id", "shoes01"]
    )
    out = capsys.readouterr().out

    assert code == 0
    assert "run_pipeline.py" in out
    assert "--dataset-id shoes01" in out
    assert "modal deploy src/aegis/remote/serve.py" in out
    assert "/api/v1/ask" not in out  # the CLI is used, not a raw URL


def test_dry_run_live_capture_uses_the_session(runner_module, capsys):
    code = runner_module.main(
        [
            "--dry-run",
            "--skip-capture",
            "--dataset-id",
            "walk01",
            "--question",
            "where are my shoes",
        ]
    )
    out = capsys.readouterr().out

    assert code == 0
    assert "--stage live" in out
    assert "aegis-ingest" not in out
    assert "where are my shoes" in out


def test_dry_run_creates_no_state(runner_module):
    state = runner_module.STATE_FILE
    before = state.exists()
    runner_module.main(["--dry-run", "--video", "put_shoes"])
    assert state.exists() == before


def test_probe_stream_reports_unreachable(runner_module):
    ok, reason = runner_module.probe_stream("http://127.0.0.1:9/video", timeout=0.5)
    assert ok is False
    assert reason


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("192.168.1.23:8080", "http://192.168.1.23:8080/video"),
        ("http://192.168.1.23:8080/", "http://192.168.1.23:8080/video"),
        ("http://192.168.1.23:8080/video", "http://192.168.1.23:8080/video"),
        ("http://host:8080/videofeed?x=1", "http://host:8080/videofeed?x=1"),
        ("", ""),
    ],
)
def test_normalise_stream_url(runner_module, raw, expected):
    assert runner_module.normalise_stream_url(raw) == expected


def test_parser_documents_human_steps(runner_module):
    help_text = runner_module.build_parser().format_help()
    assert "--dry-run" in help_text
    assert "--skip-capture" in help_text
    assert "--resume-capture" in help_text
    assert "--cpu" in help_text


def _fake_runner(runner_module, monkeypatch, tmp_path):
    args = runner_module.build_parser().parse_args(["--dry-run", "--skip-capture"])
    monkeypatch.setattr(runner_module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(runner_module, "STATE_DIR", tmp_path / ".aegis")
    monkeypatch.setattr(runner_module, "STATE_FILE", tmp_path / ".aegis" / "state.json")
    return runner_module.Runner(args)


def test_latest_segment_dataset_reads_pipeline_state(
    runner_module, monkeypatch, tmp_path
):
    session = tmp_path / "captures" / "walk01"
    session.mkdir(parents=True)
    (session / "pipeline_state.json").write_text(
        '{"segments_done": ["walk01_seg0001", "walk01_seg0002"]}'
    )
    runner = _fake_runner(runner_module, monkeypatch, tmp_path)
    assert runner_module.latest_segment_dataset(runner, "walk01") == "walk01_seg0002"


def test_latest_segment_dataset_absent_or_empty(runner_module, monkeypatch, tmp_path):
    session = tmp_path / "captures" / "walk01"
    session.mkdir(parents=True)
    runner = _fake_runner(runner_module, monkeypatch, tmp_path)
    assert runner_module.latest_segment_dataset(runner, "walk01") is None

    (session / "pipeline_state.json").write_text("{not json")
    assert runner_module.latest_segment_dataset(runner, "walk01") is None

    (session / "pipeline_state.json").write_text('{"segments_done": []}')
    assert runner_module.latest_segment_dataset(runner, "walk01") is None


def test_base_dataset_id_is_not_the_last_segment(runner_module, monkeypatch, tmp_path):
    runner = _fake_runner(runner_module, monkeypatch, tmp_path)
    runner.state = {
        "session_id": "walk01",
        "base_dataset_id": "walk01",
        "dataset_id": "walk01_seg0002",
    }
    assert runner_module.dataset_for_session(runner, "walk01") == "walk01"


class _FakeResponse:
    def __init__(self, status=200):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_checkpoint_reachable_reports_gated_denial(runner_module, monkeypatch):
    def deny(request, timeout=None):
        raise urllib.error.HTTPError(
            request.full_url, 403, "Forbidden", hdrs=None, fp=None
        )

    monkeypatch.setattr(runner_module.urllib.request, "urlopen", deny)
    assert runner_module.checkpoint_reachable("facebook/VGGT-Omega", "hf_x") is False


def test_checkpoint_reachable_reports_success(runner_module, monkeypatch):
    monkeypatch.setattr(
        runner_module.urllib.request,
        "urlopen",
        lambda request, timeout=None: _FakeResponse(200),
    )
    assert runner_module.checkpoint_reachable("wincentIsMe/VGGT-Omega") is True


def test_checkpoint_reachable_returns_none_when_offline(runner_module, monkeypatch):
    def offline(request, timeout=None):
        raise urllib.error.URLError("no route to host")

    monkeypatch.setattr(runner_module.urllib.request, "urlopen", offline)
    assert runner_module.checkpoint_reachable("wincentIsMe/VGGT-Omega") is None
