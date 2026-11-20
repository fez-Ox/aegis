"""Tests for the end-to-end runner (dry-run only; no Modal, no network)."""

from __future__ import annotations

import importlib.util
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
    assert runner_module.probe_stream("http://127.0.0.1:9/video", timeout=0.5) is False


def test_parser_documents_human_steps(runner_module):
    help_text = runner_module.build_parser().format_help()
    assert "--dry-run" in help_text
    assert "--skip-capture" in help_text
    assert "--cpu" in help_text
