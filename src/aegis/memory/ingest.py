"""Merge one session's scene graph (schema v2) into a home store.

Rooms, anchors and objects are matched onto the home's stable identities
(:mod:`aegis.memory.matching`); runs, events and room visits are stored with
absolute UTC times. Re-ingesting the same graph is a no-op; ingesting a
changed graph for an existing session replaces that session's rows.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from aegis.core.timeutil import parse_iso, shift_iso, to_utc_iso, utc_now
from aegis.core.vocabulary import Vocabulary, default_vocabulary
from aegis.geometry.gravity import GravityFrame
from aegis.memory.matching import (
    AnchorInfo,
    InstanceInfo,
    RoomInfo,
    match_anchors,
    match_instances,
    match_rooms,
)
from aegis.memory.store import HomeStore, dumps, now_iso

CONTIGUOUS_SECONDS = 10.0


@dataclass
class IngestReport:
    session_id: str
    status: str = "ingested"
    rooms_created: int = 0
    rooms_matched: int = 0
    anchors_created: int = 0
    anchors_matched: int = 0
    instances_created: int = 0
    instances_matched: int = 0
    runs_inserted: int = 0
    runs_extended: int = 0
    events_inserted: int = 0
    events_skipped: int = 0
    detail: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def graph_sha256(graph: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(graph, sort_keys=True).encode()).hexdigest()


class _Clock:
    """Converts a session's relative seconds into absolute UTC text."""

    def __init__(self, session: Mapping[str, Any], now: datetime) -> None:
        duration = float(session.get("duration_seconds") or 0.0)
        self.first = float(session.get("first_timestamp") or 0.0)
        source = session.get("time_source")
        if source in {"capture", "recorded_at"} and session.get("started_at"):
            self.source = str(source)
            self.started = to_utc_iso(str(session["started_at"]))
            ended = session.get("ended_at")
            self.ended = (
                to_utc_iso(str(ended)) if ended else shift_iso(self.started, duration)
            )
        else:
            # The only synthesised time in the system, and it is labelled.
            self.source = "ingest"
            self.ended = to_utc_iso(now)
            self.started = shift_iso(self.ended, -duration)

    def at(self, relative: Any, wallclock: Any = None) -> str:
        if wallclock and self.source != "ingest":
            return to_utc_iso(str(wallclock))
        return shift_iso(self.started, float(relative or 0.0) - self.first)


def _new_room_label(room_type: str, existing: set[str]) -> str:
    if room_type == "Room":
        n = 1
        while f"Room #{n}" in existing:
            n += 1
        return f"Room #{n}"
    if room_type not in existing:
        return room_type
    k = 2
    while f"{room_type} #{k}" in existing:
        k += 1
    return f"{room_type} #{k}"


def ingest_session(
    store: HomeStore,
    graph: Mapping[str, Any],
    *,
    vocabulary: Vocabulary | None = None,
    now: datetime | None = None,
) -> IngestReport:
    """Merge ``graph`` into ``store``; see the module docstring."""

    vocab = vocabulary or default_vocabulary()
    if int(graph.get("schema_version", 1)) != 2:
        raise ValueError("re-run the detect stage: scene graph v1 cannot be ingested")
    session = graph.get("session") or {}
    session_id = str(session.get("dataset_id") or graph.get("dataset_id") or "")
    if not session_id:
        raise ValueError("scene graph has no session dataset_id")
    report = IngestReport(session_id=session_id)
    sha = graph_sha256(graph)

    existing = store.get_session(session_id)
    if existing is not None and existing["graph_sha256"] == sha:
        report.status = "unchanged"
        return report

    clock = _Clock(session, now or utc_now())
    with store.transaction():
        if existing is not None:
            report.status = "replaced"
            report.detail.append(
                "runs of earlier sessions extended by the replaced ingest keep their extension"
            )
            for instance_id in store.delete_session_rows(session_id):
                store.recompute_last_known(instance_id)

        latest = store.one(
            "SELECT * FROM session WHERE session_id != ? ORDER BY ended_at DESC LIMIT 1",
            (session_id,),
        )
        if latest is not None and clock.started < shift_iso(latest["ended_at"], -1.0):
            raise ValueError("sessions must be ingested in chronological order")

        store.insert(
            "session",
            {
                "session_id": session_id,
                "started_at": clock.started,
                "ended_at": clock.ended,
                "time_source": clock.source,
                "ingested_at": now_iso(),
                "graph_sha256": sha,
                "keyframe_count": int(session.get("keyframe_count") or 0),
                "gravity_confidence": (graph.get("gravity") or {}).get("confidence"),
            },
        )

        room_map = _ingest_rooms(store, graph, session_id, latest, clock, report)
        anchor_map = _ingest_anchors(store, graph, session_id, room_map, vocab, report)
        instance_map = _ingest_instances(store, graph, anchor_map, vocab, report)
        _ingest_runs(
            store, graph, session_id, room_map, anchor_map, instance_map, clock, report
        )
        _ingest_events(
            store, graph, session_id, room_map, anchor_map, instance_map, clock, report
        )
        last_room = _ingest_visits(store, graph, session_id, room_map, clock)
        store.update(
            "session", "session_id", session_id, {"last_wearer_room_id": last_room}
        )
        for home_iid in set(instance_map.values()):
            if home_iid is not None:
                store.recompute_last_known(home_iid)
    return report


# ----------------------------------------------------------------- rooms
def _ingest_rooms(
    store, graph, session_id, previous, clock, report
) -> dict[int, int | None]:
    anchors = graph.get("anchors", [])
    session_rooms: list[RoomInfo] = []
    for room in graph.get("rooms", []):
        rid = int(room["room_id"])
        signature = set(room.get("evidence_labels") or [])
        signature |= {
            str(a.get("canonical") or a.get("label", "").split("#")[0].strip().lower())
            for a in anchors
            if a.get("room_id") == rid
        }
        session_rooms.append(
            RoomInfo(rid, str(room.get("room_type", "Room")), frozenset(signature))
        )
    home_rooms = [
        RoomInfo(
            int(r["room_id"]), r["room_type"], frozenset(json.loads(r["signature"]))
        )
        for r in store.rooms()
    ]

    continuity = None
    visits = graph.get("room_visits") or []
    if previous is not None and previous["last_wearer_room_id"] is not None and visits:
        gap = (
            parse_iso(clock.started) - parse_iso(previous["ended_at"])
        ).total_seconds()
        if 0 <= gap <= CONTIGUOUS_SECONDS:
            continuity = (
                int(visits[0]["room_id"]),
                int(previous["last_wearer_room_id"]),
            )

    mapping = match_rooms(session_rooms, home_rooms, continuity=continuity)
    labels = {r["label"] for r in store.rooms()}
    stamp = now_iso()
    result: dict[int, int | None] = {}
    for info in session_rooms:
        home_id = mapping.get(info.room_id)
        if home_id is None:
            label = _new_room_label(info.room_type, labels)
            labels.add(label)
            home_id = store.insert(
                "room",
                {
                    "label": label,
                    "room_type": info.room_type,
                    "label_source": "auto",
                    "signature": dumps(sorted(info.signature)),
                    "session_count": 1,
                    "last_seen_session": session_id,
                    "created_at": stamp,
                    "updated_at": stamp,
                },
            )
            report.rooms_created += 1
        else:
            row = store.one("SELECT * FROM room WHERE room_id = ?", (home_id,))
            merged = sorted(set(json.loads(row["signature"])) | info.signature)
            values: dict[str, Any] = {
                "signature": dumps(merged),
                "session_count": int(row["session_count"]) + 1,
                "last_seen_session": session_id,
                "updated_at": stamp,
            }
            if row["room_type"] == "Room" and info.room_type != "Room":
                values["room_type"] = info.room_type
            store.update("room", "room_id", home_id, values)
            report.rooms_matched += 1
        result[info.room_id] = home_id
    return result


# --------------------------------------------------------------- anchors
def _first_runs(graph) -> dict[int, Mapping[str, Any]]:
    first: dict[int, Mapping[str, Any]] = {}
    for run in sorted(
        graph.get("state_runs", []), key=lambda r: (r["start_time"], r["instance_id"])
    ):
        first.setdefault(int(run["instance_id"]), run)
    return first


def _canonical_of(state: Mapping[str, Any], vocab: Vocabulary) -> str:
    if state.get("canonical"):
        return str(state["canonical"])
    return vocab.canonical(str(state.get("label", "")).split("#")[0].strip())


def _ingest_anchors(
    store, graph, session_id, room_map, vocab, report
) -> dict[int, int]:
    gravity = GravityFrame.from_dict(graph.get("gravity"))
    canonical_by_instance = {
        int(s["instance_id"]): _canonical_of(s, vocab)
        for s in graph.get("latest_states", [])
    }
    residents: dict[int, set[str]] = {}
    for iid, run in _first_runs(graph).items():
        if run.get("anchor_id") is not None and iid in canonical_by_instance:
            residents.setdefault(int(run["anchor_id"]), set()).add(
                canonical_by_instance[iid]
            )

    session_anchors = [
        AnchorInfo(
            anchor_id=int(a["anchor_id"]),
            canonical=str(
                a.get("canonical") or vocab.canonical(a["label"].split("#")[0])
            ),
            room_id=a.get("room_id"),
            position=gravity.horizontal(a["center"]),
            residents=frozenset(residents.get(int(a["anchor_id"]), set())),
        )
        for a in graph.get("anchors", [])
    ]
    home_rows = store.anchors()
    home_residents: dict[int, set[str]] = {}
    for inst in store.instances():
        if inst["last_anchor_id"] is not None:
            home_residents.setdefault(int(inst["last_anchor_id"]), set()).add(
                inst["canonical"]
            )
    home_anchors = [
        AnchorInfo(
            anchor_id=int(r["anchor_id"]),
            canonical=r["canonical"],
            room_id=r["room_id"],
            position=(r["home_x"], r["home_y"]) if r["home_x"] is not None else None,
            residents=frozenset(home_residents.get(int(r["anchor_id"]), set())),
        )
        for r in home_rows
    ]
    first_frame = not any(a.position is not None for a in home_anchors)
    matched = match_anchors(session_anchors, home_anchors, room_map)
    transform = matched.transform

    result: dict[int, int] = {}
    for info in session_anchors:
        home_id, quality = matched.mapping[info.anchor_id]
        room = room_map.get(info.room_id) if info.room_id is not None else None
        position = None
        if transform is not None and info.position is not None:
            position = transform.apply(info.position)
        elif first_frame and info.position is not None:
            position = info.position
        if home_id is None:
            ordinal = (
                int(
                    store.one(
                        "SELECT COALESCE(MAX(ordinal), 0) FROM anchor WHERE canonical = ?",
                        (info.canonical,),
                    )[0]
                )
                + 1
            )
            home_id = store.insert(
                "anchor",
                {
                    "canonical": info.canonical,
                    "label": f"{vocab.display(info.canonical)} #{ordinal}",
                    "ordinal": ordinal,
                    "room_id": room,
                    "home_x": position[0] if position else None,
                    "home_y": position[1] if position else None,
                    "match_quality": "new",
                    "observations": 1,
                    "last_seen_session": session_id,
                },
            )
            report.anchors_created += 1
        else:
            row = store.one("SELECT * FROM anchor WHERE anchor_id = ?", (home_id,))
            values: dict[str, Any] = {
                "observations": int(row["observations"]) + 1,
                "last_seen_session": session_id,
                "match_quality": quality,
            }
            if row["room_id"] is None and room is not None:
                values["room_id"] = room
            if row["home_x"] is None and position is not None:
                values.update(home_x=position[0], home_y=position[1])
            store.update("anchor", "anchor_id", home_id, values)
            report.anchors_matched += 1
        result[info.anchor_id] = int(home_id)
    return result


# ------------------------------------------------------------- instances
def _ingest_instances(store, graph, anchor_map, vocab, report) -> dict[int, int | None]:
    first = _first_runs(graph)
    session_instances = []
    for state in graph.get("latest_states", []):
        iid = int(state["instance_id"])
        run = first.get(iid)
        appearance = state.get("appearance")
        session_instances.append(
            InstanceInfo(
                instance_id=iid,
                canonical=_canonical_of(state, vocab),
                relation=run["relation"] if run else None,
                anchor_id=run.get("anchor_id") if run else None,
                appearance=tuple(appearance) if appearance else None,
            )
        )
    home_instances = [
        InstanceInfo(
            instance_id=int(r["instance_id"]),
            canonical=r["canonical"],
            relation=r["last_relation"],
            anchor_id=r["last_anchor_id"],
            appearance=tuple(json.loads(r["appearance"])) if r["appearance"] else None,
        )
        for r in store.instances()
    ]
    mapping = match_instances(
        session_instances,
        home_instances,
        lambda sid: anchor_map.get(sid) if sid else None,
    )
    result: dict[int, int | None] = {}
    for info in session_instances:
        home_id = mapping.get(info.instance_id)
        appearance = dumps(list(info.appearance)) if info.appearance else None
        if home_id is None:
            entry = vocab.entry(info.canonical)
            home_id = store.insert(
                "instance",
                {
                    "canonical": info.canonical,
                    "label": "",
                    "importance": entry.importance,
                    "appearance": appearance,
                    "created_at": now_iso(),
                },
            )
            store.update(
                "instance",
                "instance_id",
                home_id,
                {"label": f"{entry.display} #{home_id}"},
            )
            report.instances_created += 1
        else:
            if appearance is not None:
                store.update(
                    "instance", "instance_id", home_id, {"appearance": appearance}
                )
            report.instances_matched += 1
        result[info.instance_id] = int(home_id)
    return result


# ------------------------------------------------------------------ runs
def _ingest_runs(
    store, graph, session_id, room_map, anchor_map, instance_map, clock, report
) -> None:
    by_instance: dict[int, list[Mapping[str, Any]]] = {}
    for run in graph.get("state_runs", []):
        by_instance.setdefault(int(run["instance_id"]), []).append(run)

    for sid, runs in by_instance.items():
        home_iid = instance_map.get(sid)
        if home_iid is None:
            continue
        runs.sort(key=lambda r: r["start_time"])
        total = 0
        for index, run in enumerate(runs):
            anchor = anchor_map.get(run["anchor_id"]) if run.get("anchor_id") else None
            room = (
                room_map.get(run["room_id"]) if run.get("room_id") is not None else None
            )
            start = clock.at(run["start_time"], run.get("start_wallclock"))
            end = clock.at(run["end_time"], run.get("end_wallclock"))
            count = int(run.get("observation_count") or 1)
            total += count
            inst = store.one(
                "SELECT * FROM instance WHERE instance_id = ?", (home_iid,)
            )
            if index == 0 and inst["last_relation"] is not None:
                previous = (
                    store.one(
                        "SELECT * FROM state_run WHERE run_id = ?",
                        (inst["last_run_id"],),
                    )
                    if inst["last_run_id"] is not None
                    else None
                )
                same_place = (
                    inst["last_relation"] == run["relation"]
                    and inst["last_anchor_id"] == anchor
                    and inst["last_room_id"] == room
                )
                if same_place and previous is not None:
                    store.update(
                        "state_run",
                        "run_id",
                        previous["run_id"],
                        {
                            "end_at": max(previous["end_at"], end),
                            "observation_count": int(previous["observation_count"])
                            + count,
                            "confidence": max(
                                float(previous["confidence"]), float(run["confidence"])
                            ),
                        },
                    )
                    report.runs_extended += 1
                    continue
                store.insert(
                    "event",
                    {
                        "session_id": session_id,
                        "event_type": "moved_while_unobserved",
                        "instance_id": home_iid,
                        "from_relation": inst["last_relation"],
                        "to_relation": run["relation"],
                        "from_anchor_id": inst["last_anchor_id"],
                        "to_anchor_id": anchor,
                        "from_room_id": inst["last_room_id"],
                        "to_room_id": room,
                        "start_at": inst["last_seen_at"] or start,
                        "end_at": start,
                        "confidence": float(run["confidence"]),
                    },
                )
                report.events_inserted += 1
            center = run.get("center") or [None, None, None]
            store.insert(
                "state_run",
                {
                    "instance_id": home_iid,
                    "session_id": session_id,
                    "relation": run["relation"],
                    "relation_certain": 1 if run.get("relation_certain", True) else 0,
                    "anchor_id": anchor,
                    "room_id": room,
                    "start_at": start,
                    "end_at": end,
                    "observation_count": count,
                    "confidence": float(run["confidence"]),
                    "height_above_floor": run.get("height_above_floor"),
                    "center_x": center[0],
                    "center_y": center[1],
                    "center_z": center[2],
                },
            )
            report.runs_inserted += 1
        store.execute(
            "UPDATE instance SET observation_count = observation_count + ? WHERE instance_id = ?",
            (total, home_iid),
        )


def _ingest_events(
    store, graph, session_id, room_map, anchor_map, instance_map, clock, report
) -> None:
    for event in graph.get("events", []):
        is_room_change = event.get("event_type") == "room_change"
        home_iid = None
        if not is_room_change:
            home_iid = instance_map.get(int(event.get("instance_id") or 0))
            if home_iid is None:
                report.events_skipped += 1
                continue

        def room_of(key: str, event=event) -> int | None:
            return _mapped(room_map, event.get(key))

        def anchor_of(key: str, event=event) -> int | None:
            return _mapped(anchor_map, event.get(key))

        store.insert(
            "event",
            {
                "session_id": session_id,
                "event_type": event.get("event_type", "state_change"),
                "instance_id": home_iid,
                "from_relation": event.get("source_relation"),
                "to_relation": event.get("destination_relation"),
                "from_anchor_id": anchor_of("source_anchor_id"),
                "to_anchor_id": anchor_of("destination_anchor_id"),
                "from_room_id": room_of("source_room_id"),
                "to_room_id": room_of("destination_room_id"),
                "start_at": clock.at(
                    event.get("start_time"), event.get("start_wallclock")
                ),
                "end_at": clock.at(event.get("end_time"), event.get("end_wallclock")),
                "confidence": event.get("confidence"),
            },
        )
        report.events_inserted += 1


def _mapped(mapping: Mapping[int, Any], value: Any) -> Any:
    return mapping.get(int(value)) if value is not None else None


def _ingest_visits(store, graph, session_id, room_map, clock) -> int | None:
    last_room = None
    for visit in graph.get("room_visits", []) or []:
        room = (
            room_map.get(int(visit["room_id"]))
            if visit.get("room_id") is not None
            else None
        )
        store.insert(
            "room_visit",
            {
                "session_id": session_id,
                "room_id": room,
                "start_at": clock.at(visit["start_time"], visit.get("start_wallclock")),
                "end_at": clock.at(visit["end_time"], visit.get("end_wallclock")),
            },
        )
        last_room = room
    return last_room
