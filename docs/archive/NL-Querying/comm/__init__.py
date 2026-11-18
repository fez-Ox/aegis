"""Communication package for the NL Querying module.

Public surface: ``AegisCommClient`` plus the transport implementations it
routes through. See ``NL Querying/README.md`` for usage.
"""

from .client import AegisCommClient
from .llm import LLMClient, LLMConfig, LLMError, parse_json_object
from .transports import (
    DatasetNotFoundError,
    LocalGraphSource,
    ModalGraphSource,
    RemoteUnavailableError,
    TransportError,
    create_source,
    fold_latest_states,
)

__all__ = [
    "AegisCommClient",
    "DatasetNotFoundError",
    "LLMClient",
    "LLMConfig",
    "LLMError",
    "LocalGraphSource",
    "ModalGraphSource",
    "RemoteUnavailableError",
    "TransportError",
    "create_source",
    "fold_latest_states",
    "parse_json_object",
]
