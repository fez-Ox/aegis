"""Guards for the Modal serving app: small image, one app, no pipeline import,
and the NLQ lexicon actually ships with it."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

PROBE = """
import importlib.util
import sys

spec = importlib.util.spec_from_file_location(
    "aegis_serve_probe", "src/aegis/remote/serve.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

assert module.app.name == "aegis-memory-api", module.app.name
assert "aegis.remote.modal_app" not in sys.modules, "pipeline app was imported"
assert module.SERVE_ENV["AEGIS_VOCABULARY_FILE"] == module.VOCABULARY_REMOTE
print(module.VOCABULARY_REMOTE)
print(module.NLQ_DATA_REMOTE)
print("ok")
"""


def _probe() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", PROBE],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


def test_serve_is_its_own_small_app():
    result = _probe()
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_serve_ships_the_nlq_lexicon():
    """The lexicon is data, not Python: without it the deployed app answers
    "I don't know that word" for every label outside the tiny built-in list."""

    result = _probe()
    assert result.returncode == 0, result.stderr
    vocabulary_remote, nlq_data_remote, _ = result.stdout.split()
    assert vocabulary_remote.startswith("/root/")
    assert nlq_data_remote.startswith("/root/")

    # Both sources exist in the repo (so the build cannot silently ship nothing).
    assert (REPO_ROOT / "config" / "vocabulary.yaml").is_file()
    assert (REPO_ROOT / "src" / "aegis" / "nlq" / "data" / "dictionary.json").is_file()

    # And the package-relative path the engine reads matches where we copy it.
    assert nlq_data_remote == "/root/aegis/nlq/data"
