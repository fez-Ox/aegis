"""Memory-growth audit and run-length compaction prototype.

The production R4DSG timeline stores one entry per known instance per keyframe,
including instances that are currently occluded.  That is correct for object
permanence but grows as ``frames × known_instances``.  This module measures that
growth and tests a conservative compaction scheme:

* per-instance **state runs** (a new run only when semantic state changes),
* **sparse centre snapshots** for reconstruction accuracy,
* an exact **latest state** for each instance,
* unchanged anchors, rooms, events, and frame timestamps.

The prototype lives in the evaluation package on purpose: it is evidence and a
design study, not a silent change to the memory engine.
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import defaultdict
from collections.abc import Sequence
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np

from aegis.evaluation.io import load_queries, load_scene_graph, write_json
from aegis.evaluation.metrics import normalise_anchor, normalise_label, normalise_room
from aegis.evaluation.query import answer_query

STATE_FIELDS = (
    "label",
    "anchor_id",
    "anchor_label",
    "relation",
    "room_id",
    "room_label",
    "is_in_hand",
    "carrier",
    "held_by_hand_track_id",
)


def _timeline(graph: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    value = graph.get("timeline", {})
    return value if isinstance(value, dict) else {}


def _frame_key(graph: dict[str, Any], frame_id: int) -> str | int:
    timeline = _timeline(graph)
    if str(frame_id) in timeline:
        return str(frame_id)
    if frame_id in timeline:
        return frame_id
    return str(frame_id)


def _entries(graph: dict[str, Any], frame_id: int) -> list[dict[str, Any]]:
    timeline = _timeline(graph)
    return list(timeline.get(_frame_key(graph, frame_id), []))


def _sorted_frames(graph: dict[str, Any]) -> list[int]:
    return sorted(int(frame) for frame in _timeline(graph))


def _frame_timestamps(graph: dict[str, Any]) -> list[float]:
    """Timestamp per frame, carrying the last known value across empty frames."""

    frames = _sorted_frames(graph)
    known: dict[int, float] = {}
    for frame in frames:
        entries = _entries(graph, frame)
        if entries:
            known[frame] = float(entries[0].get("timestamp", 0.0))
    fallback = known[min(known)] if known else 0.0
    values: list[float] = []
    last = fallback
    for frame in frames:
        if frame in known:
            last = known[frame]
        values.append(last)
    return values


def _canonical_bytes(payload: Any) -> int:
    return len(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
            "utf-8"
        )
    )


def _gzip_bytes(payload: Any) -> int:
    raw = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return len(gzip.compress(raw, compresslevel=9))


def _entries_by_instance(
    graph: dict[str, Any],
) -> dict[int, list[tuple[int, dict[str, Any]]]]:
    by_instance: dict[int, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    for frame_id in _sorted_frames(graph):
        for entry in _entries(graph, frame_id):
            instance_id = entry.get("instance_id")
            if instance_id is not None:
                by_instance[int(instance_id)].append((frame_id, entry))
    for sequence in by_instance.values():
        sequence.sort(key=lambda item: item[0])
    return by_instance


def _state_key(entry: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(entry.get(field) for field in STATE_FIELDS)


def _state_runs(
    graph: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[int, list[list[int]]]]:
    frames = _sorted_frames(graph)
    frame_index = {frame: index for index, frame in enumerate(frames)}
    by_instance = _entries_by_instance(graph)

    runs: list[dict[str, Any]] = []
    active_ranges: dict[int, list[list[int]]] = {}
    for instance_id, sequence in sorted(by_instance.items()):
        # Contiguous semantic runs.
        run_start = 0
        for index in range(1, len(sequence) + 1):
            break_run = index == len(sequence)
            if not break_run:
                previous_frame, previous_entry = sequence[index - 1]
                current_frame, current_entry = sequence[index]
                if (
                    _state_key(previous_entry) != _state_key(current_entry)
                    or frame_index[current_frame] != frame_index[previous_frame] + 1
                ):
                    break_run = True
            if not break_run:
                continue
            start_frame, start_entry = sequence[run_start]
            end_frame, end_entry = sequence[index - 1]
            run = {
                "instance_id": instance_id,
                "start_frame": start_frame,
                "end_frame": end_frame,
                "start_timestamp": float(start_entry.get("timestamp", 0.0)),
                "end_timestamp": float(end_entry.get("timestamp", 0.0)),
            }
            for field in STATE_FIELDS:
                if field == "label":
                    run["label"] = start_entry.get("label")
                else:
                    run[field] = start_entry.get(field)
            for field in (
                "center",
                "size",
                "relative_vector",
                "relative_distance",
                "rotation",
                "yaw",
                "in_hand_offset",
            ):
                run[f"start_{field}"] = start_entry.get(field)
                run[f"end_{field}"] = end_entry.get(field)
            run["start_last_seen_timestamp"] = start_entry.get("last_seen_timestamp")
            run["end_last_seen_timestamp"] = end_entry.get("last_seen_timestamp")
            runs.append(run)
            run_start = index

        # Contiguous active-view ranges, used to reconstruct persistence and
        # last-seen timestamps without storing a boolean per frame.
        ranges: list[list[int]] = []
        current: list[int] | None = None
        previous_index: int | None = None
        for frame_id, entry in sequence:
            index = frame_index[frame_id]
            if entry.get("is_active_view", False):
                if (
                    current is not None
                    and previous_index is not None
                    and index == previous_index + 1
                ):
                    current[1] = frame_id
                else:
                    current = [frame_id, frame_id]
                    ranges.append(current)
            else:
                current = None
            previous_index = index
        active_ranges[instance_id] = ranges
    return runs, active_ranges


def compact_graph(
    graph: dict[str, Any], *, snapshot_interval: int = 10
) -> dict[str, Any]:
    """Build the compressed representation used by the feasibility study."""

    if snapshot_interval < 0:
        raise ValueError("snapshot_interval must be >= 0")
    frames = _sorted_frames(graph)
    frame_timestamps = _frame_timestamps(graph) if frames else []
    runs, active_ranges = _state_runs(graph)

    snapshots: dict[str, list[list[Any]]] = {}
    if snapshot_interval > 0 and frames:
        sampled = frames[::snapshot_interval]
        if sampled and sampled[-1] != frames[-1]:
            sampled.append(frames[-1])
        for frame_id in sampled:
            records = []
            for entry in _entries(graph, frame_id):
                records.append(
                    [
                        entry.get("instance_id"),
                        entry.get("center"),
                        entry.get("size"),
                        entry.get("relative_vector"),
                        entry.get("relative_distance"),
                        entry.get("rotation"),
                        entry.get("yaw"),
                    ]
                )
            snapshots[str(frame_id)] = records

    latest: dict[str, dict[str, Any]] = {}
    all_instances = set(_entries_by_instance(graph))
    for frame_id in reversed(frames):
        for entry in _entries(graph, frame_id):
            instance_id = entry.get("instance_id")
            if instance_id is not None and str(instance_id) not in latest:
                latest[str(instance_id)] = dict(entry)
        if latest and all(str(instance_id) in latest for instance_id in all_instances):
            break

    return {
        "schema": "aegis.r4dsg.compacted.v1",
        "dataset_id": graph.get("dataset_id"),
        "frame_ids": frames,
        "frame_timestamps": frame_timestamps,
        "state_fields": list(STATE_FIELDS),
        "snapshot_interval": snapshot_interval,
        "snapshot_fields": [
            "instance_id",
            "center",
            "size",
            "relative_vector",
            "relative_distance",
            "rotation",
            "yaw",
        ],
        "runs": runs,
        "active_ranges": {
            str(key): value for key, value in sorted(active_ranges.items())
        },
        "snapshots": snapshots,
        "latest": latest,
        "anchors": graph.get("anchors", []),
        "rooms": graph.get("rooms", []),
        "events": graph.get("events", []),
    }


def _interpolate(start: Any, end: Any, fraction: float) -> Any:
    if start is None and end is None:
        return None
    if start is None:
        return end
    if end is None:
        return start
    if isinstance(start, (int, float)) and isinstance(end, (int, float)):
        return float(start) + (float(end) - float(start)) * fraction
    start_array = np.asarray(start, dtype=np.float64)
    end_array = np.asarray(end, dtype=np.float64)
    if start_array.shape != end_array.shape:
        return start
    return (start_array + (end_array - start_array) * fraction).tolist()


def _active_last_seen(
    active_ranges: Sequence[Sequence[int]],
    frame_id: int,
    frame_timestamps: dict[int, float],
    fallback: float | None,
) -> tuple[bool, float | None]:
    last_seen = fallback
    active = False
    for start, end in active_ranges:
        if start <= frame_id <= end:
            active = True
            last_seen = frame_timestamps.get(frame_id, fallback)
            break
        if end < frame_id:
            last_seen = frame_timestamps.get(end, last_seen)
        if start > frame_id:
            break
    return active, last_seen


def _run_geometry(run: dict[str, Any], prefix: str) -> tuple[Any, ...]:
    return (
        run.get(f"{prefix}_center"),
        run.get(f"{prefix}_size"),
        run.get(f"{prefix}_relative_vector"),
        run.get(f"{prefix}_relative_distance"),
        run.get(f"{prefix}_rotation"),
        run.get(f"{prefix}_yaw"),
    )


def _sample_run_geometry(
    run: dict[str, Any],
    frame_id: int,
    frame_index: dict[int, int],
    snapshots: Sequence[tuple[int, Sequence[Any]]],
) -> tuple[Any, ...]:
    """Interpolate geometry between run endpoints and sparse snapshots."""

    start_frame = int(run["start_frame"])
    end_frame = int(run["end_frame"])
    anchors: dict[int, tuple[Any, ...]] = {
        start_frame: _run_geometry(run, "start"),
        end_frame: _run_geometry(run, "end"),
    }
    for snapshot_frame, record in snapshots:
        if start_frame <= snapshot_frame <= end_frame:
            anchors[snapshot_frame] = tuple(record[1:7])
    ordered = sorted(anchors.items())
    if len(ordered) == 1 or frame_id <= ordered[0][0]:
        return ordered[0][1]
    if frame_id >= ordered[-1][0]:
        return ordered[-1][1]
    for (left_frame, left), (right_frame, right) in pairwise(ordered):
        if left_frame <= frame_id <= right_frame:
            left_index = frame_index.get(left_frame, 0)
            right_index = frame_index.get(right_frame, left_index)
            fraction = (
                (frame_index.get(frame_id, left_index) - left_index)
                / (right_index - left_index)
                if right_index > left_index
                else 0.0
            )
            return tuple(
                _interpolate(first, second, fraction)
                for first, second in zip(left, right, strict=False)
            )
    return _run_geometry(run, "start")


def _reconstruct_runs(
    compacted: dict[str, Any],
) -> tuple[dict[int, list[dict[str, Any]]], dict[int, list[dict[str, Any]]]]:
    frame_ids = [int(frame) for frame in compacted.get("frame_ids", [])]
    frame_index = {frame: index for index, frame in enumerate(frame_ids)}
    frame_timestamps = {
        int(frame): float(timestamp)
        for frame, timestamp in zip(
            frame_ids, compacted.get("frame_timestamps", []), strict=False
        )
    }
    runs_by_instance: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for run in compacted.get("runs", []):
        runs_by_instance[int(run["instance_id"])].append(run)
    active_ranges = {
        int(instance_id): ranges
        for instance_id, ranges in compacted.get("active_ranges", {}).items()
    }

    snapshots: dict[int, dict[int, list[Any]]] = defaultdict(dict)
    for frame_text, records in compacted.get("snapshots", {}).items():
        frame_id = int(frame_text)
        for record in records:
            if record and record[0] is not None:
                snapshots[frame_id][int(record[0])] = record
    snapshots_by_instance: dict[int, list[tuple[int, Sequence[Any]]]] = defaultdict(
        list
    )
    for snapshot_frame, records in snapshots.items():
        for instance_id, record in records.items():
            snapshots_by_instance[instance_id].append((snapshot_frame, record))
    for sequence in snapshots_by_instance.values():
        sequence.sort(key=lambda item: item[0])

    reconstructed: dict[int, list[dict[str, Any]]] = {}
    for frame_id in frame_ids:
        entries: list[dict[str, Any]] = []
        for instance_id, instance_runs in runs_by_instance.items():
            run = next(
                (
                    candidate
                    for candidate in instance_runs
                    if int(candidate["start_frame"])
                    <= frame_id
                    <= int(candidate["end_frame"])
                ),
                None,
            )
            if run is None:
                continue
            start_index = frame_index.get(int(run["start_frame"]), 0)
            end_index = frame_index.get(int(run["end_frame"]), start_index)
            fraction = (
                (frame_index[frame_id] - start_index) / (end_index - start_index)
                if end_index > start_index
                else 0.0
            )
            (
                center,
                size,
                relative_vector,
                relative_distance,
                rotation,
                yaw,
            ) = _sample_run_geometry(
                run,
                frame_id,
                frame_index,
                snapshots_by_instance.get(instance_id, []),
            )
            is_active, last_seen = _active_last_seen(
                active_ranges.get(instance_id, []),
                frame_id,
                frame_timestamps,
                run.get("start_last_seen_timestamp"),
            )
            entries.append(
                {
                    "frame_id": frame_id,
                    "timestamp": frame_timestamps.get(
                        frame_id, run.get("start_timestamp", 0.0)
                    ),
                    "instance_id": instance_id,
                    "label": run.get("label"),
                    "center": center,
                    "size": size,
                    "anchor_id": run.get("anchor_id"),
                    "anchor_label": run.get("anchor_label"),
                    "relative_vector": relative_vector,
                    "relative_distance": relative_distance,
                    "relation": run.get("relation"),
                    "is_active_view": is_active,
                    "last_seen_timestamp": last_seen,
                    "is_in_hand": run.get("is_in_hand", False),
                    "carrier": run.get("carrier"),
                    "in_hand_offset": _interpolate(
                        run.get("start_in_hand_offset"),
                        run.get("end_in_hand_offset"),
                        fraction,
                    ),
                    "room_id": run.get("room_id"),
                    "room_label": run.get("room_label"),
                    "rotation": rotation,
                    "yaw": yaw,
                }
            )
        reconstructed[frame_id] = entries
    return reconstructed, runs_by_instance


def decompress_graph(
    compacted: dict[str, Any], *, frame_ids: Sequence[int] | None = None
) -> dict[str, Any]:
    """Reconstruct a queryable graph from the compact representation."""

    reconstructed, _ = _reconstruct_runs(compacted)
    selected = list(frame_ids) if frame_ids is not None else sorted(reconstructed)
    timeline = {str(frame_id): reconstructed.get(frame_id, []) for frame_id in selected}
    return {
        "dataset_id": compacted.get("dataset_id", "evaluation"),
        "anchors": compacted.get("anchors", []),
        "rooms": compacted.get("rooms", []),
        "timeline": timeline,
        "events": compacted.get("events", []),
    }


def latest_graph(compacted: dict[str, Any]) -> dict[str, Any]:
    """Return a graph containing the exact latest state of every instance."""

    frames = [int(frame) for frame in compacted.get("frame_ids", [])]
    if not frames:
        return {
            "dataset_id": compacted.get("dataset_id", "evaluation"),
            "anchors": compacted.get("anchors", []),
            "rooms": compacted.get("rooms", []),
            "timeline": {},
            "events": compacted.get("events", []),
        }
    latest_frame = frames[-1]
    latest_entries = [dict(entry) for entry in compacted.get("latest", {}).values()]
    return {
        "dataset_id": compacted.get("dataset_id", "evaluation"),
        "anchors": compacted.get("anchors", []),
        "rooms": compacted.get("rooms", []),
        "timeline": {str(latest_frame): latest_entries},
        "events": compacted.get("events", []),
    }


def audit_graph(
    graph: dict[str, Any], *, path: str | Path | None = None
) -> dict[str, Any]:
    """Measure size, duration, instance count, and state-run growth."""

    frames = _sorted_frames(graph)
    entries = [entry for frame in frames for entry in _entries(graph, frame)]
    instance_ids = {
        entry.get("instance_id")
        for entry in entries
        if entry.get("instance_id") is not None
    }
    runs, _ = _state_runs(graph)
    timestamps = [
        float(_entries(graph, frame)[0].get("timestamp", 0.0))
        for frame in frames
        if _entries(graph, frame)
    ]
    duration = max(timestamps) - min(timestamps) if len(timestamps) >= 2 else 0.0
    if duration <= 0 and len(frames) >= 2:
        deltas = np.diff(sorted(timestamps)) if len(timestamps) >= 2 else np.array([])
        duration = float(np.median(deltas) * (len(frames) - 1)) if deltas.size else 0.0
    source_bytes = (
        Path(path).stat().st_size if path is not None and Path(path).is_file() else None
    )
    canonical_bytes = _canonical_bytes(graph)
    gzip_size = _gzip_bytes(graph)
    projection = None
    if duration > 0:
        projection = {
            "basis": f"linear projection from {duration:.1f} s observed duration",
            "original_bytes_per_hour": canonical_bytes / duration * 3600.0,
            "entries_per_hour": len(entries) / duration * 3600.0,
            "state_runs_per_hour": len(runs) / duration * 3600.0,
            "original_bytes_8h": canonical_bytes / duration * 3600.0 * 8,
            "original_bytes_24h": canonical_bytes / duration * 3600.0 * 24,
            "caution": "Projection assumes a constant activity/state-change rate; it is not a measured long-term run.",
        }
    return {
        "dataset_id": graph.get("dataset_id"),
        "path": str(path) if path is not None else None,
        "frames": len(frames),
        "duration_s": duration,
        "entries": len(entries),
        "instances": len(instance_ids),
        "anchors": len(graph.get("anchors", [])),
        "rooms": len(graph.get("rooms", [])),
        "events": len(graph.get("events", [])),
        "state_runs": len(runs),
        "entries_per_frame": len(entries) / len(frames) if frames else 0.0,
        "entries_per_instance": (
            len(entries) / len(instance_ids) if instance_ids else 0.0
        ),
        "source_file_bytes": source_bytes,
        "canonical_json_bytes": canonical_bytes,
        "gzip_bytes": gzip_size,
        "bytes_per_frame": canonical_bytes / len(frames) if frames else None,
        "bytes_per_instance": (
            canonical_bytes / len(instance_ids) if instance_ids else None
        ),
        "entries_per_state_run": len(entries) / len(runs) if runs else None,
        "projection": projection,
    }


def evaluate_compaction(
    graph: dict[str, Any],
    *,
    snapshot_interval: int = 10,
    queries: Sequence[Any] | None = None,
    aliases: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Compact a graph, reconstruct it, and measure retention vs. size."""

    compacted = compact_graph(graph, snapshot_interval=snapshot_interval)
    reconstructed, _ = _reconstruct_runs(compacted)
    frames = _sorted_frames(graph)
    original_entries: dict[tuple[int, int], dict[str, Any]] = {}
    for frame_id in frames:
        for entry in _entries(graph, frame_id):
            instance_id = entry.get("instance_id")
            if instance_id is not None:
                original_entries[(frame_id, int(instance_id))] = entry

    semantic_matches = 0
    active_matches = 0
    last_seen_matches = 0
    label_matches = 0
    full_matches = 0
    compared = 0
    center_errors: list[float] = []
    relative_distance_errors: list[float] = []
    for (frame_id, instance_id), original in original_entries.items():
        reconstructed_entry = next(
            (
                entry
                for entry in reconstructed.get(frame_id, [])
                if int(entry.get("instance_id", -1)) == instance_id
            ),
            None,
        )
        compared += 1
        if reconstructed_entry is None:
            continue
        if _state_key(original) == _state_key(reconstructed_entry):
            semantic_matches += 1
        if normalise_label(original.get("label"), aliases) == normalise_label(
            reconstructed_entry.get("label"), aliases
        ):
            label_matches += 1
        if bool(original.get("is_active_view")) == bool(
            reconstructed_entry.get("is_active_view")
        ):
            active_matches += 1
        if (
            original.get("last_seen_timestamp") is not None
            and reconstructed_entry.get("last_seen_timestamp") is not None
            and abs(
                float(original["last_seen_timestamp"])
                - float(reconstructed_entry["last_seen_timestamp"])
            )
            <= 1e-6
        ):
            last_seen_matches += 1
        if (
            _state_key(original) == _state_key(reconstructed_entry)
            and bool(original.get("is_active_view"))
            == bool(reconstructed_entry.get("is_active_view"))
            and original.get("last_seen_timestamp") is not None
            and reconstructed_entry.get("last_seen_timestamp") is not None
            and abs(
                float(original["last_seen_timestamp"])
                - float(reconstructed_entry["last_seen_timestamp"])
            )
            <= 1e-6
        ):
            full_matches += 1
        original_center = np.asarray(
            original.get("center", [0.0, 0.0, 0.0]), dtype=np.float64
        )
        reconstructed_center = np.asarray(
            reconstructed_entry.get("center", [0.0, 0.0, 0.0]), dtype=np.float64
        )
        if original_center.shape == reconstructed_center.shape:
            center_errors.append(
                float(np.linalg.norm(original_center - reconstructed_center))
            )
        original_distance = original.get("relative_distance")
        reconstructed_distance = reconstructed_entry.get("relative_distance")
        if original_distance is not None and reconstructed_distance is not None:
            relative_distance_errors.append(
                abs(float(original_distance) - float(reconstructed_distance))
            )

    errors = (
        np.asarray(center_errors, dtype=np.float64) if center_errors else np.array([])
    )
    distance_errors = (
        np.asarray(relative_distance_errors, dtype=np.float64)
        if relative_distance_errors
        else np.array([])
    )
    original_bytes = _canonical_bytes(graph)
    compact_bytes = _canonical_bytes(compacted)
    original_gzip = _gzip_bytes(graph)
    compact_gzip = _gzip_bytes(compacted)
    latest_original = {
        int(entry["instance_id"]): entry
        for frame_id in frames
        for entry in _entries(graph, frame_id)
        if entry.get("instance_id") is not None
    }
    latest_reconstructed = {
        int(key): value for key, value in compacted.get("latest", {}).items()
    }
    latest_semantic_matches = sum(
        1
        for key, original in latest_original.items()
        if key in latest_reconstructed
        and _state_key(original) == _state_key(latest_reconstructed[key])
    )
    latest_center_errors = []
    for key, original in latest_original.items():
        reconstructed_latest = latest_reconstructed.get(int(key))
        if reconstructed_latest is None:
            continue
        latest_center_errors.append(
            float(
                np.linalg.norm(
                    np.asarray(original.get("center"), dtype=np.float64)
                    - np.asarray(reconstructed_latest.get("center"), dtype=np.float64)
                )
            )
        )

    query_agreement = None
    if queries is not None and frames:
        original_latest = {
            "dataset_id": graph.get("dataset_id", "evaluation"),
            "anchors": graph.get("anchors", []),
            "rooms": graph.get("rooms", []),
            "timeline": {str(frames[-1]): list(latest_original.values())},
            "events": graph.get("events", []),
        }
        compact_latest = latest_graph(compacted)
        agreements = 0
        query_rows = []
        for query in queries:
            before = answer_query(
                original_latest, query.query, graph.get("dataset_id", "evaluation")
            )
            after = answer_query(
                compact_latest, query.query, graph.get("dataset_id", "evaluation")
            )
            same = _answers_equal(before, after, aliases=aliases)
            agreements += int(same)
            query_rows.append(
                {
                    "query_id": query.query_id,
                    "query": query.query,
                    "same": same,
                    "before": _answer_summary(before),
                    "after": _answer_summary(after),
                }
            )
        query_agreement = {
            "total": len(queries),
            "agree": agreements,
            "agreement_rate": agreements / len(queries) if queries else None,
            "queries": query_rows,
        }

    return {
        "snapshot_interval": snapshot_interval,
        "counts": {
            "frames": len(frames),
            "entries": len(original_entries),
            "instances": len(latest_original),
            "state_runs": len(compacted.get("runs", [])),
            "snapshots": sum(
                len(records) for records in compacted.get("snapshots", {}).values()
            ),
        },
        "state_retention": {
            "semantic": semantic_matches / compared if compared else 0.0,
            "label": label_matches / compared if compared else 0.0,
            "active_view": active_matches / compared if compared else 0.0,
            "last_seen": last_seen_matches / compared if compared else 0.0,
            "full": full_matches / compared if compared else 0.0,
        },
        "center_error": {
            "mean": float(np.mean(errors)) if errors.size else None,
            "median": float(np.median(errors)) if errors.size else None,
            "p95": float(np.percentile(errors, 95)) if errors.size else None,
            "max": float(np.max(errors)) if errors.size else None,
            "within_0_01": float(np.mean(errors <= 0.01)) if errors.size else None,
            "within_0_05": float(np.mean(errors <= 0.05)) if errors.size else None,
            "within_0_10": float(np.mean(errors <= 0.10)) if errors.size else None,
        },
        "relative_distance_error": {
            "mean": float(np.mean(distance_errors)) if distance_errors.size else None,
            "p95": float(np.percentile(distance_errors, 95))
            if distance_errors.size
            else None,
        },
        "bytes": {
            "original_canonical": original_bytes,
            "compacted_canonical": compact_bytes,
            "original_gzip": original_gzip,
            "compacted_gzip": compact_gzip,
            "compression_ratio": original_bytes / compact_bytes
            if compact_bytes
            else None,
            "space_saved_pct": (1.0 - compact_bytes / original_bytes) * 100.0
            if original_bytes
            else None,
            "gzip_compression_ratio": original_gzip / compact_gzip
            if compact_gzip
            else None,
        },
        "latest_state": {
            "instances": len(latest_original),
            "exact_semantic_matches": latest_semantic_matches,
            "exact_semantic_rate": (
                latest_semantic_matches / len(latest_original)
                if latest_original
                else None
            ),
            "mean_center_error": float(np.mean(latest_center_errors))
            if latest_center_errors
            else None,
        },
        "query_agreement": query_agreement,
        "runs_per_instance": (
            len(compacted.get("runs", [])) / len(latest_original)
            if latest_original
            else None
        ),
    }


def _answer_summary(answer: dict[str, Any]) -> dict[str, Any]:
    return {
        "found": bool(answer.get("found")),
        "instance_label": answer.get("instance_label"),
        "anchor": answer.get("anchor_label"),
        "room": answer.get("room_label"),
        "relation": answer.get("relation"),
    }


def _answers_equal(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    aliases: dict[str, str] | None,
) -> bool:
    if bool(before.get("found")) != bool(after.get("found")):
        return False
    if not before.get("found"):
        return True
    return (
        normalise_label(before.get("instance_label"), aliases)
        == normalise_label(after.get("instance_label"), aliases)
        and normalise_anchor(before.get("anchor_label"), aliases)
        == normalise_anchor(after.get("anchor_label"), aliases)
        and normalise_room(before.get("room_label"), aliases)
        == normalise_room(after.get("room_label"), aliases)
        and str(before.get("relation")) == str(after.get("relation"))
    )


def _projection(evaluation: dict[str, Any], duration_s: float) -> dict[str, Any] | None:
    if duration_s <= 0:
        return None
    original_bytes = evaluation["bytes"]["original_canonical"]
    compact_bytes = evaluation["bytes"]["compacted_canonical"]
    runs = evaluation["counts"]["state_runs"]
    return {
        "basis": f"linear projection from {duration_s:.1f} s observed duration",
        "original_bytes_per_hour": original_bytes / duration_s * 3600.0,
        "compacted_bytes_per_hour": compact_bytes / duration_s * 3600.0,
        "original_bytes_8h": original_bytes / duration_s * 3600.0 * 8,
        "compacted_bytes_8h": compact_bytes / duration_s * 3600.0 * 8,
        "original_bytes_24h": original_bytes / duration_s * 3600.0 * 24,
        "compacted_bytes_24h": compact_bytes / duration_s * 3600.0 * 24,
        "state_runs_per_hour": runs / duration_s * 3600.0,
        "caution": "Projection, not a measured long-term session. Real state-change rates may differ.",
    }


def _auto_queries(graph: dict[str, Any]) -> list[Any]:
    """Build label probes so query agreement can be checked without a file."""

    from aegis.evaluation.schema import QuerySpec

    labels: list[str] = []
    seen: set[str] = set()
    for frame_id in _sorted_frames(graph):
        for entry in _entries(graph, frame_id):
            label = normalise_label(entry.get("label"))
            if label and label not in seen:
                seen.add(label)
                labels.append(label)
    queries = [
        QuerySpec(query_id=f"auto_{index:03d}", query=f"Where are my {label}?")
        for index, label in enumerate(sorted(labels), start=1)
    ]
    queries.append(
        QuerySpec(
            query_id="auto_negative",
            query="Where are my keys?",
            expected_found=False,
            negative=True,
        )
    )
    return queries


def audit_paths(
    paths: Sequence[str | Path],
    *,
    snapshot_intervals: Sequence[int] = (0, 1, 10, 30),
    queries: Sequence[Any] | None = None,
    aliases: dict[str, str] | None = None,
) -> dict[str, Any]:
    datasets: list[dict[str, Any]] = []
    for path in paths:
        graph = load_scene_graph(path)
        audit = audit_graph(graph, path=path)
        auto_queries = queries is None
        dataset_queries = _auto_queries(graph) if auto_queries else queries
        evaluations = []
        for interval in snapshot_intervals:
            evaluation = evaluate_compaction(
                graph,
                snapshot_interval=interval,
                queries=dataset_queries,
                aliases=aliases,
            )
            if auto_queries and evaluation.get("query_agreement"):
                evaluation["query_agreement"]["source"] = "auto-generated label probes"
            evaluation["projection"] = _projection(
                evaluation, audit.get("duration_s", 0.0)
            )
            evaluations.append(evaluation)
        datasets.append(
            {
                "dataset_id": graph.get("dataset_id", Path(path).parent.parent.name),
                "path": str(path),
                "audit": audit,
                "evaluations": evaluations,
            }
        )
    return {
        "schema": "aegis.memory_control.v1",
        "datasets": datasets,
        "snapshot_intervals": list(snapshot_intervals),
        "recommendation": _recommend(datasets),
    }


def _candidate(dataset: dict[str, Any], evaluation: dict[str, Any]) -> dict[str, Any]:
    return {
        "dataset_id": dataset["dataset_id"],
        "snapshot_interval": evaluation["snapshot_interval"],
        "compression_ratio": evaluation["bytes"]["compression_ratio"],
        "space_saved_pct": evaluation["bytes"]["space_saved_pct"],
        "state_retention": evaluation["state_retention"],
        "center_error_p95": evaluation["center_error"]["p95"],
        "latest_exact_semantic_rate": evaluation["latest_state"]["exact_semantic_rate"],
        "compacted_bytes": evaluation["bytes"]["compacted_canonical"],
    }


def _recommend(datasets: Sequence[dict[str, Any]]) -> dict[str, Any]:
    exact_candidates: list[dict[str, Any]] = []
    balanced_candidates: list[dict[str, Any]] = []
    per_dataset: dict[str, dict[str, Any]] = {}
    for dataset in datasets:
        exact_for_dataset: list[dict[str, Any]] = []
        balanced_for_dataset: list[dict[str, Any]] = []
        for evaluation in dataset["evaluations"]:
            retention = evaluation["state_retention"]["full"]
            latest = evaluation["latest_state"]["exact_semantic_rate"]
            p95 = evaluation["center_error"]["p95"]
            ratio = evaluation["bytes"]["compression_ratio"]
            if retention < 0.999 or latest is None or latest < 0.999:
                continue
            candidate = _candidate(dataset, evaluation)
            if p95 is not None and p95 <= 0.05:
                exact_candidates.append(candidate)
                exact_for_dataset.append(candidate)
            if p95 is not None and p95 <= 0.25 and ratio >= 2.0:
                balanced_candidates.append(candidate)
                balanced_for_dataset.append(candidate)
        per_dataset[dataset["dataset_id"]] = {
            "exact": (
                min(exact_for_dataset, key=lambda item: item["compacted_bytes"])
                if exact_for_dataset
                else None
            ),
            "balanced": (
                max(balanced_for_dataset, key=lambda item: item["compression_ratio"])
                if balanced_for_dataset
                else None
            ),
        }

    exact = (
        min(exact_candidates, key=lambda item: item["compacted_bytes"])
        if exact_candidates
        else None
    )
    balanced = (
        max(balanced_candidates, key=lambda item: item["compression_ratio"])
        if balanced_candidates
        else None
    )
    if exact is not None:
        status = "feasible"
        reason = (
            "At least one interval preserved full semantic state and the exact latest "
            "state at a centre p95 <= 0.05 scene units. A sparser interval can trade "
            "some geometric fidelity for more compression."
        )
    elif balanced is not None:
        status = "feasible_with_tradeoff"
        reason = (
            "Full semantic state and exact latest state are preserved, but exact "
            "geometry needs denser snapshots. Sparse snapshots give bounded centre "
            "error and materially smaller storage."
        )
    else:
        status = "needs_attention"
        reason = (
            "No tested interval preserved full semantic state and latest state while "
            "keeping reconstruction error bounded."
        )
    selected = balanced or exact
    return {
        "status": status,
        "reason": reason,
        "exact": exact,
        "balanced": balanced,
        "per_dataset": per_dataset,
        # Keep a selected configuration at the top level for simple consumers.
        "dataset_id": selected["dataset_id"] if selected else None,
        "snapshot_interval": selected["snapshot_interval"] if selected else None,
        "compression_ratio": selected["compression_ratio"] if selected else None,
        "space_saved_pct": selected["space_saved_pct"] if selected else None,
        "state_retention": selected["state_retention"] if selected else None,
        "center_error_p95": selected["center_error_p95"] if selected else None,
        "latest_exact_semantic_rate": (
            selected["latest_exact_semantic_rate"] if selected else None
        ),
    }


def build_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Long-term memory control and persistence",
        "",
        (
            "> Feasibility study for bounded memory growth. The compaction prototype "
            "lives in the evaluation package; it is not yet the production storage format."
        ),
        "",
        "## Why this matters",
        "",
        (
            "The current timeline writes one entry per known instance per keyframe, even "
            "when an object is occluded. That is what gives object permanence, but it "
            "grows as `frames × known instances`. Run-length encoding turns that into "
            "`state changes × instances`, while keeping every instance's latest state "
            "and every event."
        ),
        "",
        "## Measured results",
        "",
    ]
    rows = []
    for dataset in report.get("datasets", []):
        audit = dataset["audit"]
        for evaluation in dataset["evaluations"]:
            rows.append(
                [
                    dataset["dataset_id"],
                    evaluation["snapshot_interval"],
                    audit["frames"],
                    audit["entries"],
                    audit["instances"],
                    audit["state_runs"],
                    f"{evaluation['bytes']['original_canonical'] / 1024:.1f} KiB",
                    f"{evaluation['bytes']['compacted_canonical'] / 1024:.1f} KiB",
                    f"{evaluation['bytes']['compression_ratio']:.1f}×",
                    _pct(evaluation["state_retention"]["full"]),
                    _pct(evaluation["state_retention"]["semantic"]),
                    _num(evaluation["center_error"]["p95"], 3),
                    _pct(
                        evaluation["latest_state"]["exact_semantic_rate"]
                        if evaluation["latest_state"]["exact_semantic_rate"] is not None
                        else None
                    ),
                    _pct(
                        evaluation["query_agreement"]["agreement_rate"]
                        if evaluation.get("query_agreement")
                        else None
                    ),
                ]
            )
    lines.append(
        _table(
            [
                "Dataset",
                "Snapshot every",
                "Frames",
                "Entries",
                "Instances",
                "State runs",
                "Original",
                "Compacted",
                "Ratio",
                "Full retention",
                "Semantic retention",
                "Centre p95",
                "Latest exact",
                "Query agreement",
            ],
            rows,
        )
    )
    lines.append("")
    if any(
        evaluation.get("query_agreement", {}).get("source")
        == "auto-generated label probes"
        for dataset in report.get("datasets", [])
        for evaluation in dataset.get("evaluations", [])
    ):
        lines.append(
            "Query agreement is measured with auto-generated label probes when no "
            "`--queries` file is supplied. The same questions are answered from the "
            "original latest state and the compacted latest state."
        )
        lines.append("")

    projection_rows = []
    per_dataset = report.get("recommendation", {}).get("per_dataset", {})
    for dataset in report.get("datasets", []):
        choices = per_dataset.get(dataset["dataset_id"], {})
        selected = choices.get("balanced") or choices.get("exact")
        recommended_interval = selected["snapshot_interval"] if selected else None
        evaluations = dataset["evaluations"]
        chosen = next(
            (
                item
                for item in evaluations
                if item["snapshot_interval"] == recommended_interval
            ),
            evaluations[0] if evaluations else None,
        )
        if chosen and chosen.get("projection"):
            projection = chosen["projection"]
            projection_rows.append(
                [
                    dataset["dataset_id"],
                    f"{projection['original_bytes_per_hour'] / (1024 * 1024):.2f} MiB",
                    f"{projection['compacted_bytes_per_hour'] / (1024 * 1024):.2f} MiB",
                    f"{projection['original_bytes_8h'] / (1024 * 1024):.1f} MiB",
                    f"{projection['compacted_bytes_8h'] / (1024 * 1024):.1f} MiB",
                    f"{projection['original_bytes_24h'] / (1024 * 1024):.1f} MiB",
                    f"{projection['compacted_bytes_24h'] / (1024 * 1024):.1f} MiB",
                    f"{projection['state_runs_per_hour']:.1f}",
                ]
            )
    if projection_rows:
        lines.extend(["## Projected long-term growth", ""])
        lines.append(
            _table(
                [
                    "Dataset",
                    "Original / hour",
                    "Compacted / hour",
                    "Original 8 h",
                    "Compacted 8 h",
                    "Original 24 h",
                    "Compacted 24 h",
                    "State runs / hour",
                ],
                projection_rows,
            )
        )
        lines.append("")
        lines.append(
            "These are **linear projections** from the observed clip duration, not "
            "measured 8-hour or 24-hour sessions. They are labelled as such in the "
            "JSON. A real long-term study would replay or record a full day and report "
            "the same audit."
        )
        lines.append("")

    recommendation = report.get("recommendation", {})
    lines.extend(["## Feasibility verdict", ""])
    status = recommendation.get("status")
    if status in {"feasible", "feasible_with_tradeoff"}:
        if status == "feasible":
            lines.append(
                "**Feasible in principle.** At least one tested interval preserved "
                "full semantic state, every latest state exactly, and exact geometry "
                "(centre p95 <= 0.05 scene units)."
            )
        else:
            lines.append(
                "**Feasible with a stated trade-off.** Full semantic state and every "
                "latest state are preserved, but exact geometry needs denser "
                "snapshots than the most compressed setting."
            )
        if recommendation.get("exact"):
            exact = recommendation["exact"]
            lines.append(
                f"- Exact geometry: `snapshot_interval={exact['snapshot_interval']}` "
                f"on `{exact['dataset_id']}` — "
                f"{exact['compression_ratio']:.1f}× smaller, centre p95 "
                f"{_num(exact['center_error_p95'])} scene units."
            )
        if recommendation.get("balanced"):
            balanced = recommendation["balanced"]
            lines.append(
                f"- Balanced: `snapshot_interval={balanced['snapshot_interval']}` "
                f"on `{balanced['dataset_id']}` — "
                f"{balanced['compression_ratio']:.1f}× smaller "
                f"({balanced['space_saved_pct']:.1f}% saved), centre p95 "
                f"{_num(balanced['center_error_p95'])} scene units, full retention "
                f"{_pct(balanced['state_retention']['full'])}, latest-state exactness "
                f"{_pct(balanced['latest_exact_semantic_rate'])}."
            )
        lines.append(
            "Queries are served from the exact latest state, so answer agreement "
            "does not depend on interpolating historical geometry."
        )
    else:
        lines.append(
            "**Not yet demonstrated.** No tested interval preserved full semantic "
            "state and latest state while keeping reconstruction error bounded. "
            "Inspect the table and either increase snapshot density or accept and "
            "state an approximation."
        )
    lines.append("")

    lines.extend(
        [
            "## What this does and does not prove",
            "",
            "- **Proves:** the representation can preserve every instance's semantic state, latest state, events, anchors, and rooms while storing far fewer per-frame entries.",
            "- **Proves:** query answers on the compacted latest state can be compared with the original; exact semantic retention and query agreement are reported, not assumed.",
            "- **Does not prove:** real-world persistence accuracy over days. That needs a long recording with labelled occlusion/relocation events.",
            "- **Does not prove:** production database performance. The prototype serialises JSON; a real deployment should use SQLite/Parquet with indices.",
            "- The centre error is in **scene units**, not metres, because VGGT-Ω is scale-ambiguous. Use the controlled-room experiment for metric calibration.",
            "",
            "## Suggested integration",
            "",
            "1. Keep the full-resolution timeline as an append-only archive (or delete it after compaction).",
            "2. Serve queries from the compacted latest state and state runs.",
            "3. Keep a sparse snapshot every 10–30 keyframes for point-in-time reconstruction.",
            "4. Store events, anchors, and rooms unchanged; they are already small.",
            "5. Add a retention policy: keep all state runs, but downsample snapshots for sessions older than N days.",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _pct(value: Any) -> str:
    if value is None:
        return "—"
    return f"{float(value) * 100:.2f}%"


def _num(value: Any, digits: int = 3) -> str:
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}"


def _table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    lines = [
        "| " + " | ".join(str(header) for header in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(lines)


def discover_graphs(root: str | Path = "outputs") -> list[Path]:
    return sorted(Path(root).glob("*/objects/r4d_scene_graph.json"))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit scene-graph growth and test run-length compaction."
    )
    parser.add_argument(
        "--graphs",
        nargs="*",
        default=None,
        help="Scene graph JSON files; defaults to outputs/*/objects/r4d_scene_graph.json.",
    )
    parser.add_argument(
        "--snapshot-intervals",
        default="0,1,10,30",
        help="Comma-separated snapshot intervals; 0 means runs only.",
    )
    parser.add_argument(
        "--queries", default=None, help="Optional queries.jsonl for agreement checks."
    )
    parser.add_argument("--output-dir", default="evaluation/reports/memory_control")
    parser.add_argument("--write-compacted", action="store_true")
    arguments = parser.parse_args(argv)

    paths = (
        [Path(path) for path in arguments.graphs]
        if arguments.graphs
        else discover_graphs()
    )
    if not paths:
        parser.error("No scene graphs found.")
    intervals = [
        int(value) for value in arguments.snapshot_intervals.split(",") if value.strip()
    ]
    queries = load_queries(arguments.queries) if arguments.queries else None
    report = audit_paths(paths, snapshot_intervals=intervals, queries=queries)
    output_dir = Path(arguments.output_dir)
    write_json(output_dir / "summary.json", report)
    (output_dir / "summary.md").write_text(build_markdown(report), encoding="utf-8")
    print(f"summary: {output_dir / 'summary.json'}")
    print(f"markdown: {output_dir / 'summary.md'}")
    print(f"recommendation: {report['recommendation']}")
    if arguments.write_compacted:
        for path in paths:
            graph = load_scene_graph(path)
            compacted = compact_graph(graph, snapshot_interval=10)
            target = output_dir / f"{graph.get('dataset_id', path.stem)}.compacted.json"
            write_json(target, compacted)
            print(f"compacted: {target}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
