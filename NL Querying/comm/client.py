"""Single entry point for all communication with the Aegis memory.

``AegisCommClient`` is what NLQ answering code (and the future smoke test /
CLI) should depend on; it hides which transport is actually in use.
"""

from __future__ import annotations

from typing import Any

from .transports import (
    SceneGraphSource,
    create_source,
)


class AegisCommClient:
    """Thin, transport-agnostic facade over the scene-graph memory.

    TODO(comm):
        * add ``timeline(dataset_id)`` once temporal queries land (M3.2);
        * add ``remote_query_parity()`` to diff against ``GET /api/v1/query``.
    """

    def __init__(self, source: SceneGraphSource | None = None) -> None:
        self._source = source or create_source()
        self._memory_cache: dict[str, dict[str, Any]] = {}

    # -- properties -------------------------------------------------------
    @property
    def transport(self) -> str:
        return self._source.transport

    # -- communication ----------------------------------------------------
    def health(self) -> dict[str, Any]:
        return self._source.health()

    def list_datasets(self) -> list[str]:
        return self._source.list_datasets()

    def load_memory(self, dataset_id: str) -> dict[str, Any]:
        """Load (and cache) the common memory view for one dataset.

        Dataset isolation: exactly one dataset per call, never merged.
        """
        if dataset_id not in self._memory_cache:
            self._memory_cache[dataset_id] = self._source.load_memory(dataset_id)
        return self._memory_cache[dataset_id]

    def scene_summary(self, dataset_id: str) -> dict[str, Any]:
        """Compact human/LLM-readable summary of one dataset's memory."""
        memory = self.load_memory(dataset_id)
        labels = sorted(
            {
                str(obj.get("label"))
                for obj in memory["latest_objects"]
                if obj.get("label")
            }
        )
        rooms = sorted(
            {str(room.get("label")) for room in memory["rooms"] if room.get("label")}
        )
        anchors = sorted(
            {
                str(anchor.get("label"))
                for anchor in memory["anchors"]
                if anchor.get("label")
            }
        )
        return {
            "dataset_id": memory["dataset_id"],
            "transport": memory["transport"],
            "anchors": anchors,
            "rooms": rooms,
            "tracked_objects": labels,
            "num_events": len(memory["events"]),
            "timeline_frames": memory["timeline_frames"],
        }
