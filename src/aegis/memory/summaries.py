"""Template summaries for compacted history (no language model).

Each summary has a short text line and a structured sidecar. The sidecar
keeps ids (instance, anchor, room) so names can be resolved later and tests
can check mechanically that identity, last location, room and event types
survived compaction (FR4.2).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from zoneinfo import ZoneInfo

from aegis.core.timeutil import parse_iso
from aegis.memory.reasoning import RELATION_PHRASES, event_summary, room_phrase

MOVE_TYPES = {
    "pickup",
    "placement",
    "anchor_change",
    "state_change",
    "moved_while_unobserved",
}


@dataclass
class SummaryDraft:
    kind: str  # "object" | "activity"
    subject_key: str
    text: str
    sidecar: dict[str, Any]


def local_clock(value: str, timezone: str) -> str:
    return parse_iso(value).astimezone(ZoneInfo(timezone)).strftime("%H:%M")


def _times(n: int) -> str:
    return "1 time" if n == 1 else f"{n} times"


def _place(relation: str | None, anchor: str | None, room: str | None) -> str:
    """'on Desk #1 in the Kitchen' / 'seen in the Kitchen' / 'seen being carried'."""

    if relation == "carried_by_user":
        return "seen being carried"
    if anchor:
        phrase = RELATION_PHRASES.get(str(relation), "near")
        return f"{phrase} {anchor}{room_phrase(room)}"
    if relation == "on_floor":
        return f"on the floor{room_phrase(room)}"
    return f"seen{room_phrase(room)}" if room else "seen"


def object_day_summary(
    instance: Mapping[str, Any],
    runs: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    *,
    anchors: Mapping[int, str],
    rooms: Mapping[int, str],
    timezone: str,
) -> SummaryDraft:
    """One line for one object on one day.

    ``runs`` are that day's runs of the instance (any order); ``events`` its
    events of that day with names resolved (store.events() shape).
    """

    ordered = sorted(runs, key=lambda r: (r["end_at"], r["run_id"]))
    last = ordered[-1]
    moves = [
        e
        for e in sorted(events, key=lambda e: e["end_wallclock"])
        if e["event_type"] in MOVE_TYPES
    ]
    last_room = rooms.get(last["room_id"]) if last["room_id"] is not None else None
    place = _place(last["relation"], anchors.get(last["anchor_id"]), last_room)
    text = (
        f"{instance['label']}: last {place} at {local_clock(last['end_at'], timezone)}"
    )
    text += f"; moved {_times(len(moves))}" if moves else "; not moved"
    other_rooms = sorted(
        {
            rooms[r["room_id"]]
            for r in ordered
            if r["room_id"] is not None
            and r["room_id"] != last["room_id"]
            and r["room_id"] in rooms
        }
    )
    if other_rooms:
        text += "; also seen in " + ", ".join(other_rooms[:3])
    text += "."
    important = instance.get("importance") == "high"
    if important and moves:
        clauses = [
            f"{local_clock(e['end_wallclock'], timezone)} {event_summary(e).rstrip('.')}"
            for e in moves
        ]
        text += " Moves: " + "; ".join(clauses) + "."

    sidecar = {
        "instance_id": instance["instance_id"],
        "canonical": instance["canonical"],
        "label": instance["label"],
        "last": {
            "relation": last["relation"],
            "relation_certain": bool(last["relation_certain"]),
            "anchor_id": last["anchor_id"],
            "room_id": last["room_id"],
            "at": last["end_at"],
        },
        "rooms": sorted({r["room_id"] for r in ordered if r["room_id"] is not None}),
        "anchors": sorted(
            {r["anchor_id"] for r in ordered if r["anchor_id"] is not None}
        ),
        "event_types": dict(Counter(e["event_type"] for e in moves)),
        "moves": [
            {
                "at": e["end_wallclock"],
                "type": e["event_type"],
                "to_anchor_id": e.get("destination_anchor_id"),
                "to_room_id": e.get("destination_room_id"),
                "to_relation": e.get("destination_relation"),
            }
            for e in moves
        ]
        if important
        else [],
        "source_runs": len(ordered),
        "source_events": len(moves),
    }
    return SummaryDraft("object", f"instance:{instance['instance_id']}", text, sidecar)


def activity_day_summary(
    activity: Mapping[str, Any], events: Sequence[Mapping[str, Any]]
) -> SummaryDraft:
    """The stored activity line, with a sidecar of what it involved."""

    return SummaryDraft(
        "activity",
        f"activity:{activity['activity_id']}",
        activity["summary"],
        {
            "room_id": activity["room_id"],
            "start_at": activity["start_at"],
            "end_at": activity["end_at"],
            "event_types": dict(Counter(e["event_type"] for e in events)),
            "instance_ids": sorted(
                {e["instance_id"] for e in events if e.get("instance_id")}
            ),
            "anchor_ids": sorted(
                {
                    a
                    for e in events
                    for a in (e.get("source_anchor_id"), e.get("destination_anchor_id"))
                    if a is not None
                }
            ),
        },
    )


def rollup_object_lines(
    label: str,
    days: Sequence[Mapping[str, Any]],
    *,
    anchors: Mapping[int, str],
    rooms: Mapping[int, str],
    period_word: str,
) -> tuple[str, dict[str, Any]]:
    """Merge day (or week) object sidecars of one instance into one line."""

    ordered = sorted(days, key=lambda d: d["period_start"])
    states = [
        (
            d["sidecar"]["last"]["relation"],
            d["sidecar"]["last"]["anchor_id"],
            d["sidecar"]["last"]["room_id"],
        )
        for d in ordered
    ]
    counts = Counter(states)
    common, k = counts.most_common(1)[0]
    place = _place(common[0], anchors.get(common[1]), rooms.get(common[2]))
    moved = sum(sum(d["sidecar"].get("event_types", {}).values()) for d in ordered)
    if len(counts) == 1:
        text = f"{label}: unchanged, {place}, all {period_word}."
    else:
        last_there = max(
            d["period_start"]
            for d, s in zip(ordered, states, strict=True)
            if s == common
        )
        text = (
            f"{label}: mostly {place} ({k} of {len(ordered)} days); last there on "
            f"{last_there}; moved {_times(moved)} this {period_word}."
        )
    last = ordered[-1]["sidecar"]
    event_types: Counter[str] = Counter()
    for d in ordered:
        event_types.update(d["sidecar"].get("event_types", {}))
    sidecar = {
        "instance_id": last["instance_id"],
        "canonical": last["canonical"],
        "label": label,
        "last": last["last"],
        "rooms": sorted({r for d in ordered for r in d["sidecar"].get("rooms", [])}),
        "anchors": sorted(
            {a for d in ordered for a in d["sidecar"].get("anchors", [])}
        ),
        "event_types": dict(event_types),
        "days": len(ordered),
    }
    return text, sidecar


def rollup_activity_lines(
    lines: Sequence[Mapping[str, Any]], *, rooms: Mapping[int, str]
) -> tuple[str, dict[str, Any]]:
    """Merge activity lines into '<n> room visits; most time in <room>.'"""

    durations: Counter[int | None] = Counter()
    visits = 0
    for line in lines:
        sidecar = line["sidecar"]
        if "visits" in sidecar:  # already a roll-up
            visits += int(sidecar["visits"])
            for room, seconds in sidecar.get("seconds_by_room", {}).items():
                durations[None if room == "none" else int(room)] += float(seconds)
            continue
        visits += 1
        seconds = (
            parse_iso(sidecar["end_at"]) - parse_iso(sidecar["start_at"])
        ).total_seconds()
        durations[sidecar.get("room_id")] += seconds
    top_room = durations.most_common(1)[0][0] if durations else None
    room_name = rooms.get(top_room) if top_room is not None else "Home"
    text = f"{visits} room visits; most time in {room_name or 'Home'}."
    return text, {
        "visits": visits,
        "seconds_by_room": {
            ("none" if r is None else str(r)): s for r, s in durations.items()
        },
    }
