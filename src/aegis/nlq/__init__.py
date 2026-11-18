"""Single rule-based natural-language query engine for Aegis.

``AnswerEngine`` answers from one memory view, never invents a location, and
abstains when there is no evidence. ``DictionaryIndex`` is the closed
vocabulary. Used by ``aegis.remote.api`` and by the ``aegis-ask`` CLI.
"""

from .dictionary import DictionaryIndex, Slots
from .engine import (
    AnswerEngine,
    AskResult,
    Intent,
    memory_view_from_graph,
    memory_view_from_repo,
)

__all__ = [
    "AnswerEngine",
    "AskResult",
    "DictionaryIndex",
    "Intent",
    "Slots",
    "memory_view_from_graph",
    "memory_view_from_repo",
]
