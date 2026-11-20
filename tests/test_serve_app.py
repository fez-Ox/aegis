"""Guards for the Modal serving app: small image, one app, no pipeline import."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_serve_is_its_own_small_app():
    code = """
import importlib.util
import sys

spec = importlib.util.spec_from_file_location(
    "aegis_serve_probe", "src/aegis/remote/serve.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

assert module.app.name == "aegis-memory-api", module.app.name
assert "aegis.remote.modal_app" not in sys.modules, "pipeline app was imported"
print("ok")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout
