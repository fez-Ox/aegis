"""Read access to memory graphs for the API.

``JsonGraphRepository`` wraps one ``r4d_scene_graph.json`` (schema v1 with a
per-keyframe ``timeline``, or v2 with ``latest_states``). Loaded graphs are
cached per dataset and reloaded automatically when the file changes on disk;
a corrupt file is reported as "not ready" and is not cached.
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class MemoryRepository(Protocol):
    ready: bool

    def anchors(self) -> list[dict[str, Any]]: ...
    def rooms(self) -> list[dict[str, Any]]: ...
    def events(self) -> list[dict[str, Any]]: ...
    def latest_states(self) -> dict[int, dict[str, Any]]: ...
    def rename_room(self, room_id: int, label: str) -> dict[str, Any]: ...
    def keyframe_count(self) -> int: ...


def latest_states_from_graph(data: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """Last-known state per instance for a v1 or v2 graph."""

    if isinstance(data.get("latest_states"), list):
        latest = {
            int(state["instance_id"]): dict(state)
            for state in data["latest_states"]
            if isinstance(state, dict) and state.get("instance_id") is not None
        }
        # Session graphs have no wall clock, but state runs and events carry
        # everything the ranker needs (observation counts, first placement,
        # movement history). Without this the salience ranker sees a vector of
        # zeroes on the JSON path and silently stops ranking at all. Relative
        # seconds are mapped onto a fixed epoch; only ages within the session
        # are compared, so the choice of epoch is arbitrary.
        from datetime import UTC, datetime, timedelta

        epoch = datetime(2000, 1, 1, tzinfo=UTC)

        def wallclock(seconds: float | None) -> str | None:
            if seconds is None:
                return None
            try:
                return (epoch + timedelta(seconds=float(seconds))).isoformat()
            except (TypeError, ValueError, OverflowError):
                return None

        def run_time(run: dict[str, Any]) -> float:
            moment = run.get("end_time")
            if moment is None:
                moment = run.get("start_time")
            try:
                return float(moment) if moment is not None else 0.0
            except (TypeError, ValueError):
                return 0.0

        runs: dict[int, list[dict[str, Any]]] = {}
        for run in data.get("state_runs", []) or []:
            if isinstance(run, dict) and run.get("instance_id") is not None:
                runs.setdefault(int(run["instance_id"]), []).append(run)
        movements: dict[int, list[float]] = {}
        placements: dict[int, int] = {}
        for event in data.get("events", []) or []:
            if not isinstance(event, dict) or event.get("instance_id") is None:
                continue
            instance_id = int(event["instance_id"])
            if event.get("event_type") in {
                "placement",
                "anchor_change",
                "moved_while_unobserved",
            }:
                moment = event.get("end_time")
                if moment is None:
                    moment = event.get("start_time")
                if moment is not None:
                    try:
                        movements.setdefault(instance_id, []).append(float(moment))
                    except (TypeError, ValueError):
                        pass
            if event.get("event_type") == "placement":
                placements[instance_id] = placements.get(instance_id, 0) + 1
        references = [run_time(run) for group in runs.values() for run in group]
        reference = max(references, default=0.0)

        for instance_id, state in latest.items():
            ordered = sorted(runs.get(instance_id, []), key=run_time)
            if ordered:
                first, last = ordered[0], ordered[-1]
                if state.get("observation_count") is None:
                    state["observation_count"] = int(last.get("observation_count") or 0)
                if last.get("evidence"):
                    state.setdefault("evidence_id", 1)
                if state.get("last_seen_wallclock") is None:
                    state["last_seen_wallclock"] = wallclock(run_time(last))
                    state["last_seen_relative"] = run_time(last)
                if state.get("first_room_id") is None:
                    state["first_room_id"] = first.get("room_id")
                if state.get("first_anchor_id") is None:
                    state["first_anchor_id"] = first.get("anchor_id")
            if state.get("last_moved_wallclock") is None and movements.get(instance_id):
                state["last_moved_wallclock"] = wallclock(max(movements[instance_id]))
            if state.get("placement_count") is None:
                state["placement_count"] = placements.get(instance_id, 0)
            state["reference_relative"] = reference
        return latest
    timeline = data.get("timeline", {}) or {}
    try:
        frames = sorted(timeline, key=int)
    except (TypeError, ValueError):
        frames = list(timeline)
    latest: dict[int, dict[str, Any]] = {}
    for frame in frames:
        for entry in timeline.get(frame, []) or []:
            if isinstance(entry, dict) and entry.get("instance_id") is not None:
                latest[int(entry["instance_id"])] = entry
    return latest


class JsonGraphRepository:
    """One dataset's scene graph file."""

    def __init__(
        self,
        dataset_id: str,
        data: dict[str, Any] | None = None,
        *,
        path: Path | None = None,
        ready: bool = True,
    ) -> None:
        self.dataset_id = dataset_id
        self.path = path
        self.ready = ready and data is not None
        self.data: dict[str, Any] = (
            data
            if data is not None
            else {
                "dataset_id": dataset_id,
                "anchors": [],
                "rooms": [],
                "events": [],
                "timeline": {},
            }
        )
        self.data.setdefault("dataset_id", dataset_id)
        self.data["scene_graph_ready"] = self.ready
        self._latest = latest_states_from_graph(self.data)

    # --------------------------------------------------------------- reads
    def anchors(self) -> list[dict[str, Any]]:
        return list(self.data.get("anchors", []))

    def rooms(self) -> list[dict[str, Any]]:
        return list(self.data.get("rooms", []))

    def events(self) -> list[dict[str, Any]]:
        return list(self.data.get("events", []))

    def latest_states(self) -> dict[int, dict[str, Any]]:
        return self._latest

    def keyframe_count(self) -> int:
        session = self.data.get("session") or {}
        if "keyframe_count" in session:
            return int(session["keyframe_count"])
        return len(self.data.get("timeline", {}) or {})

    # -------------------------------------------------------------- writes
    def apply_simulated_state(
        self, instance_id: int, state: dict[str, Any], event: dict[str, Any]
    ) -> None:
        """In-memory change used by the demo simulator (never written to disk)."""

        self._latest[instance_id] = state
        self.data.setdefault("events", []).append(event)

    def rename_room(self, room_id: int, label: str) -> dict[str, Any]:
        """Rename one room everywhere it is referenced and persist the file."""

        if self.path is None or not self.ready:
            raise FileNotFoundError(f"no scene graph for dataset {self.dataset_id!r}")
        room = next(
            (r for r in self.data.get("rooms", []) if r.get("room_id") == room_id),
            None,
        )
        if room is None:
            raise KeyError(room_id)
        old_label = room.get("label")
        room["label"] = label

        def relabel(records: Sequence[dict[str, Any]]) -> None:
            for record in records:
                if isinstance(record, dict) and record.get("room_id") == room_id:
                    record["room_label"] = label

        relabel(self.data.get("anchors", []))
        relabel(self.data.get("latest_states", []) or [])
        relabel(self.data.get("state_runs", []) or [])
        relabel(self.data.get("room_visits", []) or [])
        for entries in (self.data.get("timeline", {}) or {}).values():
            relabel(entries)
        relabel(list(self._latest.values()))

        for event in self.data.get("events", []):
            for side in ("source", "destination"):
                id_key, label_key = f"{side}_room_id", f"{side}_room"
                if id_key in event:
                    if event[id_key] == room_id:
                        event[label_key] = label
                elif old_label is not None and event.get(label_key) == old_label:
                    # v1 graphs have no room ids on events: exact label match only.
                    event[label_key] = label

        payload = {k: v for k, v in self.data.items() if k != "scene_graph_ready"}
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        temporary.replace(self.path)
        _remember(self.dataset_id, self)
        return room


# ---------------------------------------------------------------- caching
_CACHE: dict[str, tuple[Path, int, int, JsonGraphRepository]] = {}
_LOCK = threading.Lock()


def _remember(dataset_id: str, repository: JsonGraphRepository) -> None:
    if repository.path is None:
        return
    stat = repository.path.stat()
    with _LOCK:
        _CACHE[dataset_id] = (
            repository.path,
            stat.st_mtime_ns,
            stat.st_size,
            repository,
        )


def clear_cache(dataset_id: str | None = None) -> None:
    with _LOCK:
        if dataset_id is None:
            _CACHE.clear()
        else:
            _CACHE.pop(dataset_id, None)


def get_repository(
    dataset_id: str, search_paths: Sequence[Path]
) -> JsonGraphRepository:
    """Repository for ``dataset_id``; reloads when the file changed on disk."""

    with _LOCK:
        cached = _CACHE.get(dataset_id)
    for path in search_paths:
        if not path.is_file():
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        if (
            cached is not None
            and cached[0] == path
            and cached[1] == stat.st_mtime_ns
            and cached[2] == stat.st_size
        ):
            return cached[3]
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to parse %s: %s", path, exc)
            return JsonGraphRepository(dataset_id, None, ready=False)
        if not isinstance(data, dict):
            logger.warning("Scene graph %s is not a JSON object", path)
            return JsonGraphRepository(dataset_id, None, ready=False)
        owner = data.get("dataset_id")
        if owner and owner != dataset_id:
            logger.warning(
                "Ignoring scene graph for %s at %s (graph belongs to %s)",
                dataset_id,
                path,
                owner,
            )
            continue
        repository = JsonGraphRepository(dataset_id, data, path=path)
        with _LOCK:
            _CACHE[dataset_id] = (path, stat.st_mtime_ns, stat.st_size, repository)
        return repository
    clear_cache(dataset_id)
    return JsonGraphRepository(dataset_id, None, ready=False)


class StoreRepository:
    """Repository view of a home store (same dict shapes as the JSON graph)."""

    def __init__(self, store: Any) -> None:
        self.store = store
        self.ready = True
        self.dataset_id = store.home_id

    def anchors(self) -> list[dict[str, Any]]:
        rooms = {r["room_id"]: r["label"] for r in self.store.rooms()}
        return [
            {
                "anchor_id": row["anchor_id"],
                "label": row["label"],
                "canonical": row["canonical"],
                "center": [],
                "size": [],
                "room_id": row["room_id"],
                "room_label": rooms.get(row["room_id"]),
                "match_quality": row["match_quality"],
            }
            for row in self.store.anchors()
        ]

    def rooms(self) -> list[dict[str, Any]]:
        return [
            {
                "room_id": row["room_id"],
                "label": row["label"],
                "room_type": row["room_type"],
                "label_source": row["label_source"],
                "centroid": [],
                "keyframe_count": 0,
            }
            for row in self.store.rooms()
        ]

    def events(self) -> list[dict[str, Any]]:
        return self.events_between(None, None)

    def events_between(
        self, start: str | None, end: str | None
    ) -> list[dict[str, Any]]:
        from aegis.core.timeutil import parse_iso

        events = self.store.events(start, end)
        for event in events:
            event["start_time"] = parse_iso(event["start_wallclock"]).timestamp()
            event["end_time"] = parse_iso(event["end_wallclock"]).timestamp()
        return events

    def latest_states(self) -> dict[int, dict[str, Any]]:
        return {state["instance_id"]: state for state in self.store.latest_states()}

    def keyframe_count(self) -> int:
        return sum(int(row["keyframe_count"]) for row in self.store.sessions())

    def rename_room(self, room_id: int, label: str) -> dict[str, Any]:
        from aegis.memory.homes import rename_home_room

        return rename_home_room(self.store, room_id, label)
