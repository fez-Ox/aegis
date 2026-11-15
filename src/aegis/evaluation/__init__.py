"""Standalone, panel-defensible evaluation harness for Aegis.

The package is deliberately independent of the pipeline builder: it reads
prediction artifacts, compares them with human annotations or physical
measurements, and writes reproducible Markdown/JSON reports.

Entry points
------------
``python -m aegis.evaluation.run``             held-out video evaluation (Option A)
``python -m aegis.evaluation.controlled_room``  measured-room 3D experiment (Option D)
``python -m aegis.evaluation.memory_audit``     memory growth + compaction study
``python -m aegis.evaluation.option_c``         Ego4D benchmark readiness (Option C)
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
