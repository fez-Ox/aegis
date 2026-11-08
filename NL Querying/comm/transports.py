"""Transport layer for communicating with the Aegis spatio-temporal memory.

Two interchangeable sources live behind one interface, so the NLQ engine can
run identically in every environment:

* ``ModalGraphSource``  -- HTTPS calls to the deployed Modal web endpoint
  (see ``comm/modal_serve.py``). This is the production path once the
  workspace access is set up.
* ``LocalGraphSource``  -- offline development against real artifact sets:
  ``sample_outputs/``, ``outputs/`` and ``tests/fixtures/`` scene-graph JSONs.
  Zero network, zero Modal spend.

Both return one common "memory view" dict::

    {
        "dataset_id": str,
        "anchors": [...],        # spatial anchors (label, center, size, room)
        "rooms": [...],          # room regions (footprints, labels)
        "events": [...],         # spatial event stream (state changes)
        "latest_objects": [...], # last known state per object instance
        "timeline_frames": int,  # number of ingested timeline frames
        "transport": str,        # which source produced this view
    }

The common shape mirrors ``aegis.remote.api`` responses so a future parity
test can diff local vs remote answers.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import httpx

# Byte-for-byte identical artifacts across offline roots.
SCENE_GRAPH_FILENAME = "objects/r4d_scene_graph.json"

REPO_ROOT = Path(__file__).resolve().parents[2]

# Priority order for offline development: artifacts produced for NLQ first,
# then real remote-produced artifacts, downloaded outputs, and CI fixtures.
NLQ_OUTPUTS_ROOT = Path(__file__).resolve().parents[1] / "outputs"
LOCAL_ROOTS: tuple[Path, ...] = (
    NLQ_OUTPUTS_ROOT,
    REPO_ROOT / "sample_outputs",
    REPO_ROOT / "outputs",
    REPO_ROOT / "tests" / "fixtures",
)

ENV_TRANSPORT = "AEGIS_COMM_TRANSPORT"  # "auto" | "modal" | "local"
ENV_MODAL_BASE_URL = "AEGIS_MODAL_BASE_URL"


class TransportError(RuntimeError):
    """Base class for communication failures."""


class DatasetNotFoundError(TransportError):
    """The requested dataset's scene graph does not exist at the source."""


class RemoteUnavailableError(TransportError):
    """The remote (Modal) endpoint is unreachable or misconfigured."""


def fold_latest_states(graph: dict[str, Any]) -> list[dict[str, Any]]:
    """Fold a raw per-frame timeline into last-known states per instance.

    Mirrors ``aegis.remote.api.find_latest_objects_state`` so that the offline
    transport produces exactly what the Modal ``/api/v1/scene_graph`` response
    exposes as ``latest_objects``.
    """
    timeline = graph.get("timeline", {})
    try:
        frame_keys = sorted(timeline, key=int)
    except (TypeError, ValueError):
        frame_keys = list(timeline)

    latest: dict[int, dict[str, Any]] = {}
    for key in frame_keys:
        for obj in timeline.get(key, []):
            instance_id = obj.get("instance_id")
            if instance_id is not None:
                latest[int(instance_id)] = obj
    return list(latest.values())


class SceneGraphSource(ABC):
    """Abstract communication channel to one memory store."""

    transport: str = "abstract"

    @abstractmethod
    def health(self) -> dict[str, Any]:
        """Return a small status payload (fast, no heavy data)."""

    @abstractmethod
    def list_datasets(self) -> list[str]:
        """Dataset ids the source can serve."""

    @abstractmethod
    def load_memory(self, dataset_id: str) -> dict[str, Any]:
        """Load the common memory-view dict for ``dataset_id``."""


class LocalGraphSource(SceneGraphSource):
    """Reads scene graphs directly from local artifact directories."""

    transport = "local"

    def __init__(self, roots: Sequence[Path] | None = None) -> None:
        self._roots = [Path(r) for r in (roots or LOCAL_ROOTS)]

    # -- helpers ----------------------------------------------------------
    def _graph_path(self, dataset_id: str) -> Path | None:
        for root in self._roots:
            for candidate in (
                root / dataset_id / SCENE_GRAPH_FILENAME,
                root / dataset_id / "r4d_scene_graph.json",
            ):
                if candidate.is_file():
                    return candidate
        return None

    # -- interface --------------------------------------------------------
    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "transport": self.transport,
            "roots": [str(r) for r in self._roots],
            "datasets_found": len(self.list_datasets()),
        }

    def list_datasets(self) -> list[str]:
        found: set[str] = set()
        for root in self._roots:
            if not root.is_dir():
                continue
            for item in root.iterdir():
                if not item.is_dir():
                    continue
                if any(
                    p.is_file()
                    for p in (
                        item / SCENE_GRAPH_FILENAME,
                        item / "r4d_scene_graph.json",
                    )
                ):
                    found.add(item.name)
        return sorted(found)

    def load_memory(self, dataset_id: str) -> dict[str, Any]:
        path = self._graph_path(dataset_id)
        if path is None:
            raise DatasetNotFoundError(
                f"No scene graph for '{dataset_id}' under: "
                f"{[str(r) for r in self._roots]}"
            )
        with open(path, "r", encoding="utf-8") as handle:
            graph = json.load(handle)

        graph_dataset = graph.get("dataset_id")
        if graph_dataset and graph_dataset != dataset_id:
            raise DatasetNotFoundError(
                f"Graph at {path} belongs to '{graph_dataset}', not '{dataset_id}'."
            )

        return {
            "dataset_id": dataset_id,
            "anchors": graph.get("anchors", []),
            "rooms": graph.get("rooms", []),
            "events": graph.get("events", []),
            "latest_objects": fold_latest_states(graph),
            "timeline_frames": len(graph.get("timeline", {})),
            "transport": self.transport,
        }


class ModalGraphSource(SceneGraphSource):
    """HTTPS client for the memory API served from Modal (see modal_serve.py)."""

    transport = "modal"

    def __init__(self, base_url: str, timeout: float = 15.0) -> None:
        base_url = base_url.strip().rstrip("/")
        if not base_url.startswith(("http://", "https://")):
            raise RemoteUnavailableError(
                f"Modal base URL must start with http(s)://, got: {base_url!r}"
            )
        self.base_url = base_url
        self.timeout = timeout

    # -- helpers ----------------------------------------------------------
    def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        try:
            response = httpx.get(
                f"{self.base_url}{path}", params=params, timeout=self.timeout
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RemoteUnavailableError(
                f"Cannot reach {self.base_url}{path}: {exc}"
            ) from exc
        return response.json()

    # -- interface --------------------------------------------------------
    def health(self) -> dict[str, Any]:
        payload = self._get("/api/v1/health")
        payload["transport"] = self.transport
        payload["base_url"] = self.base_url
        return payload

    def list_datasets(self) -> list[str]:
        payload = self._get("/api/v1/datasets")
        entries = payload.get("available_datasets", payload.get("datasets", []))
        return [entry["dataset_id"] for entry in entries]

    def load_memory(self, dataset_id: str) -> dict[str, Any]:
        payload = self._get("/api/v1/scene_graph", params={"dataset_id": dataset_id})
        if not payload.get("anchors") and not payload.get("latest_objects"):
            # The remote server returns an empty graph for unseen datasets.
            raise DatasetNotFoundError(f"Remote has no scene graph for '{dataset_id}'.")
        return {
            "dataset_id": payload.get("dataset_id", dataset_id),
            "anchors": payload.get("anchors", []),
            "rooms": payload.get("rooms", []),
            "events": payload.get("events", []),
            "latest_objects": payload.get("latest_objects", []),
            "timeline_frames": payload.get("total_timeline_frames", 0),
            "transport": self.transport,
        }


def create_source(
    transport: str | None = None,
    base_url: str | None = None,
) -> SceneGraphSource:
    """Factory honouring environment variables for zero-config use.

    Resolution order: explicit argument > ``AEGIS_COMM_TRANSPORT`` /
    ``AEGIS_MODAL_BASE_URL`` env > auto (modal when base URL is known,
    otherwise local artifacts).
    """
    transport = (transport or os.environ.get(ENV_TRANSPORT) or "auto").lower()
    base_url = base_url or os.environ.get(ENV_MODAL_BASE_URL)

    if transport in {"modal", "http"}:
        if not base_url:
            raise RemoteUnavailableError(
                "modal transport requested without AEGIS_MODAL_BASE_URL "
                "(deploy with: uv run modal deploy 'NL Querying/comm/"
                "modal_serve.py')"
            )
        return ModalGraphSource(base_url)
    if transport in {"local", "offline"}:
        return LocalGraphSource()
    # auto
    if base_url:
        return ModalGraphSource(base_url)
    return LocalGraphSource()
