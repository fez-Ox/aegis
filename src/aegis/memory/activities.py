"""Activities: one stay of the wearer in one room plus the object events in it.

Activities are the unit behind "what did I do this morning?" and the daily
summary. Summaries are deterministic templates over stored rows.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from zoneinfo import ZoneInfo

from aegis.core.timeutil import parse_iso
from aegis.memory.reasoning import event_summary

MAX_CLAUSES = 6
DEFAULT_TIMEZONE = "Asia/Karachi"


@dataclass
class ActivityDraft:
    room_id: int | None
    start_at: str
    end_at: str
    event_ids: list[int] = field(default_factory=list)


def build_activities(
    visits: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    *,
    session_start: str,
    session_end: str,
    min_gap_seconds: float = 10.0,
) -> list[ActivityDraft]:
    """Merge short gaps between same-room visits and attach events by end time.

    ``visits`` need ``room_id``, ``start_at``, ``end_at``; ``events`` need
    ``event_id``, ``event_type`` and ``end_at``. A session without visits
    becomes one activity with no room.
    """

    drafts: list[ActivityDraft] = []
    for visit in sorted(visits, key=lambda v: v["start_at"]):
        if drafts and drafts[-1].room_id == visit["room_id"]:
            gap = (
                parse_iso(visit["start_at"]) - parse_iso(drafts[-1].end_at)
            ).total_seconds()
            if gap < min_gap_seconds:
                drafts[-1].end_at = max(drafts[-1].end_at, visit["end_at"])
                continue
        drafts.append(
            ActivityDraft(visit["room_id"], visit["start_at"], visit["end_at"])
        )
    if not drafts:
        drafts.append(ActivityDraft(None, session_start, session_end))

    for event in sorted(events, key=lambda e: (e["end_at"], e["event_id"])):
        if event.get("event_type") == "room_change":
            continue
        end = event["end_at"]
        containing = [d for d in drafts if d.start_at <= end <= d.end_at]
        if containing:
            target = containing[0]
        else:
            moment = parse_iso(end)
            target = min(
                drafts,
                key=lambda d: min(
                    abs((parse_iso(d.start_at) - moment).total_seconds()),
                    abs((parse_iso(d.end_at) - moment).total_seconds()),
                ),
            )
        target.event_ids.append(int(event["event_id"]))
    return drafts


def _clock(value: str, timezone: str) -> str:
    return parse_iso(value).astimezone(ZoneInfo(timezone)).strftime("%H:%M")


def activity_summary(
    draft: ActivityDraft,
    room_label: str | None,
    events: Sequence[Mapping[str, Any]],
    *,
    timezone: str = DEFAULT_TIMEZONE,
) -> str:
    """``"09:10–09:40 Kitchen: Mug #2 was placed on Desk #1; …"``"""

    room = room_label or "Home"
    span = f"{_clock(draft.start_at, timezone)}–{_clock(draft.end_at, timezone)} {room}"
    clauses = []
    for event in events:
        without_room = dict(event, destination_room=None, source_room=None)
        clauses.append(event_summary(without_room).rstrip("."))
    if not clauses:
        return f"{span}: no objects moved."
    if len(clauses) > MAX_CLAUSES:
        shown = clauses[: MAX_CLAUSES - 1]
        shown.append(f"and {len(clauses) - len(shown)} more changes")
        clauses = shown
    return f"{span}: {'; '.join(clauses)}."


def store_session_activities(
    store: Any, session_id: str, *, timezone: str = DEFAULT_TIMEZONE
) -> int:
    """Build, insert and link the activities of one ingested session."""

    session = store.get_session(session_id)
    visits = [
        dict(row)
        for row in store.query(
            "SELECT room_id, start_at, end_at FROM room_visit WHERE session_id = ? "
            "ORDER BY start_at",
            (session_id,),
        )
    ]
    raw_events = store.query(
        "SELECT event_id, event_type, end_at FROM event WHERE session_id = ?",
        (session_id,),
    )
    drafts = build_activities(
        visits,
        [dict(row) for row in raw_events],
        session_start=session["started_at"],
        session_end=session["ended_at"],
    )
    labelled = {
        int(event["event_id"].split("_")[-1]): event
        for event in store.events()
        if event["session_id"] == session_id
    }
    rooms = {row["room_id"]: row["label"] for row in store.rooms()}
    for draft in drafts:
        events = [labelled[i] for i in draft.event_ids if i in labelled]
        activity_id = store.insert(
            "activity",
            {
                "session_id": session_id,
                "room_id": draft.room_id,
                "start_at": draft.start_at,
                "end_at": draft.end_at,
                "event_count": len(events),
                "summary": activity_summary(
                    draft, rooms.get(draft.room_id), events, timezone=timezone
                ),
            },
        )
        for event_id in draft.event_ids:
            store.update("event", "event_id", event_id, {"activity_id": activity_id})
    return len(drafts)
