"""Small, pure scoring helpers shared by the measurement scripts."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def match_events(
    predicted: Sequence[float], truth: Sequence[float], *, tolerance: float
) -> int:
    """Greedy one-to-one matches of event times within ``tolerance`` seconds."""

    used: set[int] = set()
    matches = 0
    for t in sorted(truth):
        best = None
        for index, p in enumerate(predicted):
            if index in used or abs(p - t) > tolerance:
                continue
            if best is None or abs(p - t) < abs(predicted[best] - t):
                best = index
        if best is not None:
            used.add(best)
            matches += 1
    return matches


def precision_recall(
    predicted: Sequence[float], truth: Sequence[float], *, tolerance: float
) -> dict[str, Any]:
    hits = match_events(predicted, truth, tolerance=tolerance)
    precision = hits / len(predicted) if predicted else (1.0 if not truth else 0.0)
    recall = hits / len(truth) if truth else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "matches": hits,
        "predicted": len(predicted),
        "truth": len(truth),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


# --------------------------------------------------------------- live capture
def summarise_live_session(session_dir: Any) -> dict[str, Any]:
    """Soak (AC-01) and disconnect (AC-03) figures from a capture directory."""

    from pathlib import Path

    import numpy as np

    from aegis.core.timeutil import parse_iso
    from aegis.ingestion.contracts import load_session_manifest, read_live_index

    session = Path(session_dir)
    manifest = load_session_manifest(session)
    records = read_live_index(session / "index.jsonl")
    frames = [r for r in records if r.get("record_type", "frame") == "frame"]
    times = sorted(parse_iso(str(r["capture_timestamp"])) for r in frames)
    started = parse_iso(str(manifest["started_at"]))
    ended = parse_iso(str(manifest.get("ended_at") or manifest["started_at"]))
    duration = max((ended - started).total_seconds(), 0.0)
    intervals = (
        np.diff([t.timestamp() for t in times]) if len(times) > 1 else np.array([])
    )
    sizes = [
        (session / str(r["frame_path"])).stat().st_size
        for r in frames
        if (session / str(r["frame_path"])).is_file()
    ]
    gaps = list(manifest.get("gaps", []))
    by_reason: dict[str, dict[str, float]] = {}
    disconnects = []
    for gap in gaps:
        start, end = parse_iso(gap["gap_start"]), parse_iso(gap["gap_end"])
        entry = by_reason.setdefault(gap["reason"], {"count": 0, "seconds": 0.0})
        entry["count"] += 1
        entry["seconds"] += (end - start).total_seconds()
        if gap["reason"] == "disconnect":
            after = next((t for t in times if t >= end), None)
            disconnects.append(
                {
                    "gap_start": gap["gap_start"],
                    "gap_end": gap["gap_end"],
                    "resume_seconds": (
                        round((after - start).total_seconds(), 3) if after else None
                    ),
                }
            )
    buffer = manifest.get("buffer", {})
    total_frames = int(
        manifest.get("emitted_frame_count")
        or manifest.get("frame_count")
        or len(frames)
    )
    received = total_frames + int(manifest.get("rejected_frame_count", 0))
    return {
        "session_id": manifest["session_id"],
        "status": manifest.get("status"),
        "wall_duration_seconds": round(duration, 3),
        "frames_kept": len(frames),
        "frames_received": received,
        "effective_received_fps": round(received / duration, 3) if duration else None,
        "gaps_by_reason": by_reason,
        "max_interval_seconds": round(float(intervals.max()), 3)
        if intervals.size
        else None,
        "p95_interval_seconds": (
            round(float(np.percentile(intervals, 95)), 3) if intervals.size else None
        ),
        "bytes_on_disk": int(sum(sizes)),
        "mean_frame_bytes": int(sum(sizes) / len(sizes)) if sizes else None,
        "max_backlog_frames": buffer.get("max_backlog"),
        "max_backlog_seconds": buffer.get("max_backlog_seconds"),
        "dropped_frames": manifest.get("dropped_frame_count"),
        "disconnects": disconnects,
    }


def keyframe_hits(
    kept_times: Sequence[float], change_times: Sequence[float], *, window: float = 2.0
) -> dict[str, Any]:
    """AC-02: a scene change counts when a kept frame follows within ``window`` s."""

    detected = [
        t for t in change_times if any(t <= k <= t + window for k in kept_times)
    ]
    return {
        "changes": len(change_times),
        "detected": len(detected),
        "kept_frames": len(kept_times),
        "pass": len(detected) >= 0.8 * len(change_times) if change_times else False,
    }


# ------------------------------------------------------------------ placement
def placement_accuracy(
    states: Sequence[dict[str, Any]], truth: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    """AC-04: last-known anchor *and* relation per ground-truth object.

    ``states`` are store latest states (canonical, relation, anchor_label);
    ``truth`` items have object (canonical id), anchor (canonical anchor id)
    and relation. Duplicates = extra instances per ground-truth object.
    """

    rows = []
    duplicates = 0
    for item in truth:
        matching = [s for s in states if s.get("canonical") == item["object"]]
        duplicates += max(0, len(matching) - 1)
        best = max(
            matching, key=lambda s: s.get("last_seen_wallclock") or "", default=None
        )
        anchor = (best or {}).get("anchor_label") or ""
        anchor_canonical = anchor.split("#")[0].strip().lower()
        ok = bool(
            best
            and best.get("relation") == item["relation"]
            and anchor_canonical == str(item["anchor"]).lower()
        )
        rows.append(
            {
                "object": item["object"],
                "expected": f"{item['relation']} {item['anchor']}",
                "found": f"{(best or {}).get('relation')} {anchor or None}",
                "correct": ok,
            }
        )
    correct = sum(r["correct"] for r in rows)
    return {
        "objects": len(truth),
        "correct": correct,
        "accuracy": round(correct / len(truth), 4) if truth else None,
        "duplicate_rate": round(duplicates / len(truth), 4) if truth else None,
        "rows": rows,
    }


# ---------------------------------------------------------------------- rooms
def room_metrics(
    keyframes: Sequence[tuple[float, int | None]],
    truth_rooms: Sequence[dict[str, Any]],
    predicted_changes: Sequence[float],
    truth_changes: Sequence[float],
    *,
    tolerance: float = 1.0,
) -> dict[str, Any]:
    """AC-22 room metrics (docs/evaluation_suite.md, Rooms).

    ``keyframes``: (time, predicted room id). ``truth_rooms``: {"name",
    "intervals": [[start, end], ...]}. Predicted rooms are mapped one-to-one
    to the ground-truth room they overlap most (greedy by overlap).
    """

    def truth_at(t: float) -> str | None:
        for room in truth_rooms:
            # Half-open intervals: a transition instant belongs to the new room.
            if any(a <= t < b for a, b in room["intervals"]):
                return room["name"]
        return None

    overlap: dict[tuple[int, str], int] = {}
    for t, predicted in keyframes:
        name = truth_at(t)
        if predicted is not None and name is not None:
            overlap[(predicted, name)] = overlap.get((predicted, name), 0) + 1
    mapping: dict[int, str] = {}
    used: set[str] = set()
    for (predicted, name), _count in sorted(overlap.items(), key=lambda kv: -kv[1]):
        if predicted in mapping or name in used:
            continue
        mapping[predicted] = name
        used.add(name)

    labelled = [(t, p) for t, p in keyframes if truth_at(t) is not None]
    correct = sum(
        1 for t, p in labelled if p is not None and mapping.get(p) == truth_at(t)
    )
    predicted_ids = {p for _t, p in keyframes if p is not None}
    changes = precision_recall(predicted_changes, truth_changes, tolerance=tolerance)
    return {
        "segmentation_accuracy": round(correct / len(labelled), 4)
        if labelled
        else None,
        "region_precision": round(len(mapping) / len(predicted_ids), 4)
        if predicted_ids
        else None,
        "region_recall": round(len(used) / len(truth_rooms), 4)
        if truth_rooms
        else None,
        "room_change": changes,
        "mapping": {str(k): v for k, v in mapping.items()},
    }


def ordered_matches(
    predicted: Sequence[tuple[str, str, float]],
    truth: Sequence[tuple[str, str, float]],
    *,
    tolerance: float,
) -> int:
    """AC-05: count truth actions matched in order (object prefix, type, time)."""

    position = 0
    hits = 0
    for prefix, kind, t in truth:
        for index in range(position, len(predicted)):
            obj, p_kind, p_time = predicted[index]
            if (
                obj.lower().startswith(prefix.lower())
                and p_kind == kind
                and abs(p_time - t) <= tolerance
            ):
                hits += 1
                position = index + 1
                break
    return hits
