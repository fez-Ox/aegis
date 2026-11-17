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

# Pure scoring helpers used by scripts/ and tests/. They live in this package
# (as of the evaluation-suite merge) so that ``aegis.evaluation`` has a single
# import location; the old top-level ``aegis/evaluation.py`` was removed.
from aegis.evaluation.measurements import (
    keyframe_hits,
    match_events,
    ordered_matches,
    placement_accuracy,
    precision_recall,
    room_metrics,
    summarise_live_session,
)

__all__ = [
    "__version__",
    "keyframe_hits",
    "match_events",
    "ordered_matches",
    "placement_accuracy",
    "precision_recall",
    "room_metrics",
    "summarise_live_session",
]

__version__ = "0.1.0"
