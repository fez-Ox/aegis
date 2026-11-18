"""NL Querying package: hybrid closed-vocabulary question answering.

Public surface: ``HybridNLQEngine`` + ``DictionaryIndex`` + ``AskResult``.
See ``NL Querying/README.md`` for the architecture status.
"""

from .dictionary import DictionaryIndex, Slots
from .engine import AskResult, HybridNLQEngine, Intent

__all__ = [
    "AskResult",
    "DictionaryIndex",
    "HybridNLQEngine",
    "Intent",
    "Slots",
]
