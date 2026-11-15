"""Builders of schema-v2 session graphs for store tests."""

from __future__ import annotations

from itertools import pairwise
from typing import Any

from aegis.core.timeutil import shift_iso, to_utc_iso


def make_session_graph(
    session_id: str,
    start: str = "2026-11-15T09:00:00+00:00",
    *,
    rooms: list[dict[str, Any]] | None = None,
    anchors: list[dict[str, Any]] | None = None,
    objects: list[dict[str, Any]] | None = None,
    visits: list[tuple[int, float, float]] | None = None,
    duration: float = 60.0,
    keyframes: int = 10,
    time_source: str = "capture",
) -> dict[str, Any]:
    """objects: {"instance_id", "canonical", "runs": [(relation, anchor_id,
    room_id, t0, t1, count)], "appearance"?}"""

    start = to_utc_iso(start)
    rooms = (
        rooms
        if rooms is not None
        else [
            {
                "room_id": 1,
                "label": "Room #1",
                "room_type": "Room",
                "evidence_labels": [],
            }
        ]
    )
    anchors = anchors or []
    objects = objects or []

    def wall(t: float) -> str | None:
        return shift_iso(start, t) if time_source == "capture" else None

    runs, latest, events = [], [], []
    for obj in objects:
        canonical = obj["canonical"]
        label = f"{canonical.title()} #{obj['instance_id']}"
        object_runs = []
        for relation, anchor_id, room_id, t0, t1, count in obj["runs"]:
            run = {
                "instance_id": obj["instance_id"],
                "relation": relation,
                "relation_certain": True,
                "anchor_id": anchor_id,
                "room_id": room_id,
                "start_time": t0,
                "end_time": t1,
                "start_wallclock": wall(t0),
                "end_wallclock": wall(t1),
                "observation_count": count,
                "confidence": 0.9,
                "center": [0.0, 0.0, 0.0],
                "height_above_floor": None,
                "start_frame": int(t0),
                "end_frame": int(t1),
            }
            object_runs.append(run)
        runs.extend(object_runs)
        for prev, cur in pairwise(object_runs):
            kind = (
                "pickup"
                if cur["relation"] == "carried_by_user"
                else (
                    "placement"
                    if prev["relation"] == "carried_by_user"
                    else "anchor_change"
                )
            )
            events.append(
                {
                    "event_type": kind,
                    "instance_id": obj["instance_id"],
                    "object": label,
                    "source_relation": prev["relation"],
                    "destination_relation": cur["relation"],
                    "source_anchor_id": prev["anchor_id"],
                    "destination_anchor_id": cur["anchor_id"],
                    "source_room_id": prev["room_id"],
                    "destination_room_id": cur["room_id"],
                    "start_time": prev["end_time"],
                    "end_time": cur["start_time"],
                    "start_wallclock": wall(prev["end_time"]),
                    "end_wallclock": wall(cur["start_time"]),
                    "confidence": 0.9,
                }
            )
        last = object_runs[-1]
        latest.append(
            {
                "instance_id": obj["instance_id"],
                "label": label,
                "canonical": canonical,
                "relation": last["relation"],
                "anchor_id": last["anchor_id"],
                "room_id": last["room_id"],
                "appearance": obj.get("appearance"),
                "confidence": 0.9,
            }
        )
    room_visits = [
        {
            "room_id": room_id,
            "start_time": t0,
            "end_time": t1,
            "start_wallclock": wall(t0),
            "end_wallclock": wall(t1),
        }
        for room_id, t0, t1 in (visits or [])
    ]
    return {
        "schema_version": 2,
        "dataset_id": session_id,
        "session": {
            "dataset_id": session_id,
            "started_at": start if time_source == "capture" else None,
            "ended_at": shift_iso(start, duration)
            if time_source == "capture"
            else None,
            "time_source": time_source,
            "keyframe_count": keyframes,
            "duration_seconds": duration,
            "first_timestamp": 0.0,
        },
        "gravity": {"up": [0.0, -1.0, 0.0], "source": "assumed", "confidence": 0.0},
        "anchors": [
            {
                "anchor_id": a["anchor_id"],
                "canonical": a["canonical"],
                "label": f"{a['canonical'].title()} #{a['anchor_id']}",
                "room_id": a.get("room_id", 1),
                "center": list(a.get("center", (0.0, 0.0, 0.0))),
                "size": [1.0, 1.0, 1.0],
            }
            for a in anchors
        ],
        "rooms": rooms,
        "state_runs": runs,
        "latest_states": latest,
        "events": events,
        "room_visits": room_visits,
    }
