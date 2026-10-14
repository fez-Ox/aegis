"""Shared test setup for lightweight tracked scene-graph fixtures."""

import os
from pathlib import Path

# CI intentionally does not download large Modal-volume artifacts. The API
# reads these fixtures only when this test-only environment variable is set.
os.environ.setdefault("AEGIS_TEST_FIXTURE_ROOT", str(Path(__file__).parent / "fixtures"))
