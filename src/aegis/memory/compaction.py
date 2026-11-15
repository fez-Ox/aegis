"""Tiered retention: compact old detail into verified text summaries.

Phase 1, per local calendar day older than ``hot_days``: build template
summaries for every object and activity of that day, verify them against
the source rows, then delete the day's runs, events, visits and activities.
Each day is its own transaction; a day that fails verification keeps all of
its rows and is logged as ``failed`` (UC-12 A1).

Never deleted: the ``instance`` table (each object's last-known state), the
run behind each last-known state (its geometry is cleared), rooms, anchors
and sessions. High-importance objects keep detail until
``important_hot_days`` (phase 2 removes it later without re-summarising).

Roll-up: day lines older than ``weekly_rollup_after_days`` merge into week
lines, week lines older than ``monthly_rollup_after_days`` into month lines.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from aegis.core.config import RetentionConfig
from aegis.core.timeutil import parse_iso, shift_iso, to_utc_iso
from aegis.memory.evidence import delete_evidence
from aegis.memory.summaries import (
    SummaryDraft,
    activity_day_summary,
    object_day_summary,
    rollup_activity_lines,
    rollup_object_lines,
)

PHASE_IMPORTANT = "phase=important"


class VerificationError(RuntimeError):
    """A summary did not preserve what the source rows say."""


@dataclass
class CompactionReport:
    days_compacted: list[str] = field(default_factory=list)
    days_failed: list[tuple[str, str]] = field(default_factory=list)
    runs_deleted: int = 0
    events_deleted: int = 0
    summaries_written: int = 0
    rollups_written: int = 0


def _bounds(day: date, timezone: str) -> tuple[str, str]:
    """UTC [start, end) of a local calendar day."""

    zone = ZoneInfo(timezone)
    start = datetime.combine(day, time.min, tzinfo=zone)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=zone)
    return to_utc_iso(start), to_utc_iso(end)


def _local_day(value: str, timezone: str) -> date:
    return parse_iso(value).astimezone(ZoneInfo(timezone)).date()


def _detail_days(store: Any, timezone: str) -> set[date]:
    days: set[date] = set()
    for table in ("state_run", "event", "room_visit", "activity"):
        for row in store.query(f"SELECT DISTINCT end_at FROM {table}"):
            days.add(_local_day(row[0], timezone))
    return days


def _logged(store: Any, day: date, detail: str | None) -> bool:
    if detail is None:
        row = store.one(
            "SELECT 1 FROM compaction_log WHERE day = ? AND status = 'ok' "
            "AND (detail IS NULL OR detail != ?)",
            (day.isoformat(), PHASE_IMPORTANT),
        )
    else:
        row = store.one(
            "SELECT 1 FROM compaction_log WHERE day = ? AND status = 'ok' AND detail = ?",
            (day.isoformat(), detail),
        )
    return row is not None


def _log(store: Any, day: date, status: str, **values: Any) -> None:
    store.insert(
        "compaction_log",
        {
            "ran_at": to_utc_iso(datetime.now().astimezone()),
            "day": day.isoformat(),
            "status": status,
            **values,
        },
    )


def _important_ids(store: Any) -> set[int]:
    return {
        int(row[0])
        for row in store.query(
            "SELECT instance_id FROM instance WHERE importance = 'high'"
        )
    }


def _protected_runs(store: Any) -> set[int]:
    return {
        int(row[0])
        for row in store.query(
            "SELECT last_run_id FROM instance WHERE last_run_id IS NOT NULL"
        )
    }


def _build_day(
    store: Any,
    start: str,
    end: str,
    timezone: str,
    summarizer: Callable[..., SummaryDraft],
) -> tuple[list[SummaryDraft], dict[str, Any]]:
    runs = [
        dict(r)
        for r in store.query(
            "SELECT * FROM state_run WHERE end_at >= ? AND end_at < ?", (start, end)
        )
    ]
    events = [e for e in store.events(start, shift_iso(end, -1e-6))]
    activities = [
        dict(a)
        for a in store.query(
            "SELECT * FROM activity WHERE end_at >= ? AND end_at < ?", (start, end)
        )
    ]
    instances = {int(r["instance_id"]): dict(r) for r in store.instances()}
    anchors = {int(r["anchor_id"]): r["label"] for r in store.anchors()}
    rooms = {int(r["room_id"]): r["label"] for r in store.rooms()}

    runs_by_instance: dict[int, list[dict[str, Any]]] = {}
    for run in runs:
        runs_by_instance.setdefault(int(run["instance_id"]), []).append(run)
    events_by_instance: dict[int, list[dict[str, Any]]] = {}
    for event in events:
        if event.get("instance_id"):
            events_by_instance.setdefault(int(event["instance_id"]), []).append(event)
    for instance_id in events_by_instance:
        if instance_id not in runs_by_instance:
            in_effect = store.one(
                "SELECT * FROM state_run WHERE instance_id = ? AND start_at < ? "
                "ORDER BY start_at DESC LIMIT 1",
                (instance_id, end),
            )
            if in_effect is not None:
                runs_by_instance[instance_id] = [dict(in_effect)]

    drafts: list[SummaryDraft] = []
    for instance_id, instance_runs in sorted(runs_by_instance.items()):
        drafts.append(
            summarizer(
                instances[instance_id],
                instance_runs,
                events_by_instance.get(instance_id, []),
                anchors=anchors,
                rooms=rooms,
                timezone=timezone,
            )
        )
    for activity in activities:
        linked = [e for e in events if e.get("activity_id") == activity["activity_id"]]
        drafts.append(activity_day_summary(activity, linked))
    context = {
        "runs_by_instance": runs_by_instance,
        "activities": activities,
        "anchors": anchors,
        "rooms": rooms,
        "runs": runs,
        "events": events,
    }
    return drafts, context


def _verify(drafts: list[SummaryDraft], context: dict[str, Any]) -> None:
    objects = {d.sidecar["instance_id"]: d for d in drafts if d.kind == "object"}
    for instance_id, runs in context["runs_by_instance"].items():
        draft = objects.get(instance_id)
        if draft is None:
            raise VerificationError(f"instance {instance_id} has no summary")
        final = max(runs, key=lambda r: (r["end_at"], r["run_id"]))
        expected = {
            "relation": final["relation"],
            "anchor_id": final["anchor_id"],
            "room_id": final["room_id"],
            "at": final["end_at"],
        }
        last = draft.sidecar["last"]
        if {k: last.get(k) for k in expected} != expected:
            raise VerificationError(
                f"instance {instance_id}: summary last state differs"
            )
    activity_ids = {d.subject_key for d in drafts if d.kind == "activity"}
    for activity in context["activities"]:
        if f"activity:{activity['activity_id']}" not in activity_ids:
            raise VerificationError(
                f"activity {activity['activity_id']} has no summary"
            )
    for draft in drafts:
        sidecar = draft.sidecar
        for room in [
            *sidecar.get("rooms", []),
            sidecar.get("room_id"),
            sidecar.get("last", {}).get("room_id"),
        ]:
            if room is not None and room not in context["rooms"]:
                raise VerificationError(f"room {room} does not exist")
        for anchor in [
            *sidecar.get("anchors", []),
            *sidecar.get("anchor_ids", []),
            sidecar.get("last", {}).get("anchor_id"),
        ]:
            if anchor is not None and anchor not in context["anchors"]:
                raise VerificationError(f"anchor {anchor} does not exist")
        if not draft.text.strip() or "None" in draft.text:
            raise VerificationError(
                f"summary {draft.subject_key} has empty or unresolved text"
            )


def _write_summary(
    store: Any,
    level: str,
    period_start: str,
    period_end: str,
    kind: str,
    key: str,
    text: str,
    sidecar: dict[str, Any],
) -> None:
    store.execute(
        "INSERT OR REPLACE INTO summary (level, period_start, period_end, kind, subject_key, text, sidecar, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            level,
            period_start,
            period_end,
            kind,
            key,
            text,
            json.dumps(sidecar, sort_keys=True),
            to_utc_iso(datetime.now().astimezone()),
        ),
    )


def _delete_runs(
    store: Any,
    runs: list[dict[str, Any]],
    *,
    protected: set[int],
    keep_last_evidence: bool,
) -> int:
    deleted = 0
    for run in runs:
        if run["run_id"] in protected:
            store.update(
                "state_run",
                "run_id",
                run["run_id"],
                {"center_x": None, "center_y": None, "center_z": None},
            )
            if not keep_last_evidence and run["evidence_id"] is not None:
                delete_evidence(store, run["evidence_id"])
                store.update(
                    "state_run", "run_id", run["run_id"], {"evidence_id": None}
                )
                store.execute(
                    "UPDATE instance SET last_evidence_id = NULL WHERE last_run_id = ?",
                    (run["run_id"],),
                )
            continue
        if run["evidence_id"] is not None:
            delete_evidence(store, run["evidence_id"])
        store.execute("DELETE FROM state_run WHERE run_id = ?", (run["run_id"],))
        deleted += 1
    return deleted


def compact(
    store: Any,
    *,
    now: datetime,
    config: RetentionConfig | None = None,
    summarizer: Callable[..., SummaryDraft] = object_day_summary,
) -> CompactionReport:
    """Compact every eligible day; see the module docstring."""

    settings = config or RetentionConfig()
    tz = settings.timezone
    today = now.astimezone(ZoneInfo(tz)).date()
    cutoff = today - timedelta(days=settings.hot_days)
    important_cutoff = today - timedelta(days=settings.important_hot_days)
    report = CompactionReport()
    important = _important_ids(store)

    for day in sorted(_detail_days(store, tz)):
        if day >= cutoff or _logged(store, day, None):
            continue
        start, end = _bounds(day, tz)
        keep_important = day >= important_cutoff
        try:
            with store.transaction():
                drafts, context = _build_day(store, start, end, tz, summarizer)
                _verify(drafts, context)
                for draft in drafts:
                    _write_summary(
                        store,
                        "day",
                        day.isoformat(),
                        day.isoformat(),
                        draft.kind,
                        draft.subject_key,
                        draft.text,
                        draft.sidecar,
                    )
                protected = _protected_runs(store)
                victims = [
                    r
                    for r in context["runs"]
                    if not (keep_important and int(r["instance_id"]) in important)
                ]
                runs_deleted = _delete_runs(
                    store,
                    victims,
                    protected=protected,
                    keep_last_evidence=settings.keep_last_evidence,
                )
                events_deleted = 0
                for event in store.query(
                    "SELECT event_id, instance_id FROM event WHERE end_at >= ? AND end_at < ?",
                    (start, end),
                ):
                    if keep_important and event["instance_id"] in important:
                        continue
                    store.execute(
                        "DELETE FROM event WHERE event_id = ?", (event["event_id"],)
                    )
                    events_deleted += 1
                store.execute(
                    "DELETE FROM room_visit WHERE end_at >= ? AND end_at < ?",
                    (start, end),
                )
                store.execute(
                    "DELETE FROM activity WHERE end_at >= ? AND end_at < ?",
                    (start, end),
                )
                _log(
                    store,
                    day,
                    "ok",
                    runs_deleted=runs_deleted,
                    events_deleted=events_deleted,
                    summaries_written=len(drafts),
                )
        except VerificationError as exc:
            _log(store, day, "failed", detail=str(exc))
            report.days_failed.append((day.isoformat(), str(exc)))
            continue
        report.days_compacted.append(day.isoformat())
        report.runs_deleted += runs_deleted
        report.events_deleted += events_deleted
        report.summaries_written += len(drafts)

    # Phase 2: high-importance detail past its longer window.
    for day in sorted(_detail_days(store, tz)):
        if (
            day >= important_cutoff
            or not _logged(store, day, None)
            or _logged(store, day, PHASE_IMPORTANT)
        ):
            continue
        start, end = _bounds(day, tz)
        with store.transaction():
            runs = [
                dict(r)
                for r in store.query(
                    "SELECT * FROM state_run WHERE end_at >= ? AND end_at < ?",
                    (start, end),
                )
            ]
            deleted = _delete_runs(
                store,
                runs,
                protected=_protected_runs(store),
                keep_last_evidence=settings.keep_last_evidence,
            )
            store.execute(
                "DELETE FROM event WHERE end_at >= ? AND end_at < ?", (start, end)
            )
            _log(store, day, "ok", runs_deleted=deleted, detail=PHASE_IMPORTANT)
        report.runs_deleted += deleted
    return report


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def rollup(store: Any, *, now: datetime, config: RetentionConfig | None = None) -> int:
    """Merge old day lines into weeks, and old week lines into months."""

    settings = config or RetentionConfig()
    today = now.astimezone(ZoneInfo(settings.timezone)).date()
    anchors = {int(r["anchor_id"]): r["label"] for r in store.anchors()}
    rooms = {int(r["room_id"]): r["label"] for r in store.rooms()}
    written = 0

    def merge(
        source: str,
        target: str,
        threshold: date,
        period_of: Callable[[date], tuple[date, date]],
        word: str,
    ) -> int:
        rows = [
            dict(r, sidecar=json.loads(r["sidecar"]))
            for r in store.query(
                "SELECT * FROM summary WHERE level = ? AND period_end < ?",
                (source, threshold.isoformat()),
            )
        ]
        groups: dict[tuple[date, str, str], list[dict[str, Any]]] = {}
        for row in rows:
            first, last = period_of(date.fromisoformat(row["period_start"]))
            if last >= threshold:
                continue
            key = (
                row["subject_key"] if row["kind"] == "object" else f"activity:{target}"
            )
            groups.setdefault((first, row["kind"], key), []).append(row)
        count = 0
        for (first, kind, key), members in sorted(groups.items()):
            _first, last = period_of(first)
            if kind == "object":
                text, sidecar = rollup_object_lines(
                    members[-1]["sidecar"]["label"],
                    members,
                    anchors=anchors,
                    rooms=rooms,
                    period_word=word,
                )
            else:
                text, sidecar = rollup_activity_lines(members, rooms=rooms)
            with store.transaction():
                _write_summary(
                    store,
                    target,
                    first.isoformat(),
                    last.isoformat(),
                    kind,
                    key,
                    text,
                    sidecar,
                )
                for member in members:
                    store.execute(
                        "DELETE FROM summary WHERE summary_id = ?",
                        (member["summary_id"],),
                    )
            count += 1
        return count

    def week(day: date) -> tuple[date, date]:
        first = _week_start(day)
        return first, first + timedelta(days=6)

    def month(day: date) -> tuple[date, date]:
        first = day.replace(day=1)
        following = (first + timedelta(days=32)).replace(day=1)
        return first, following - timedelta(days=1)

    written += merge(
        "day",
        "week",
        today - timedelta(days=settings.weekly_rollup_after_days),
        week,
        "week",
    )
    written += merge(
        "week",
        "month",
        today - timedelta(days=settings.monthly_rollup_after_days),
        month,
        "month",
    )
    return written


def compaction_ok(store: Any) -> bool:
    row = store.one("SELECT status FROM compaction_log ORDER BY id DESC LIMIT 1")
    return row is None or row["status"] != "failed"
