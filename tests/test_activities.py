"""Tests for activity history (FR3.3)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from aegis.core.timeutil import parse_iso, shift_iso
from aegis.memory.activities import ActivityDraft, activity_summary, build_activities
from aegis.memory.homes import close_stores
from aegis.memory.ingest import ingest_session
from aegis.memory.store import open_store
from aegis.remote.api import app
from tests._graphs import make_session_graph

T0 = "2026-11-15T04:00:00.000000+00:00"  # 09:00 in Asia/Karachi


def _at(seconds: float) -> str:
    return shift_iso(T0, seconds)


def _visit(room, start, end):
    return {"room_id": room, "start_at": _at(start), "end_at": _at(end)}


def _event(event_id, end, kind="placement"):
    return {"event_id": event_id, "event_type": kind, "end_at": _at(end)}


def _build(visits, events):
    return build_activities(visits, events, session_start=_at(0), session_end=_at(600))


def test_two_rooms_give_two_activities() -> None:
    drafts = _build([_visit(1, 0, 100), _visit(2, 100, 300)], [])
    assert [(d.room_id, d.start_at, d.end_at) for d in drafts] == [
        (1, _at(0), _at(100)),
        (2, _at(100), _at(300)),
    ]


def test_short_gap_between_same_room_visits_is_merged() -> None:
    drafts = _build([_visit(1, 0, 100), _visit(1, 105, 200)], [])
    assert len(drafts) == 1
    assert drafts[0].end_at == _at(200)


def test_events_are_assigned_by_end_time() -> None:
    drafts = _build(
        [_visit(1, 0, 100), _visit(2, 100, 300)],
        [_event(7, 50), _event(8, 250), _event(9, 400), _event(10, 150, "room_change")],
    )
    assert drafts[0].event_ids == [7]
    assert drafts[1].event_ids == [8, 9]


def test_session_without_rooms_has_one_home_activity() -> None:
    drafts = _build([], [_event(1, 30)])
    assert len(drafts) == 1
    assert drafts[0].room_id is None
    assert (
        activity_summary(drafts[0], None, []) == "09:00–09:10 Home: no objects moved."
    )


def test_summary_is_deterministic_and_caps_clauses() -> None:
    draft = ActivityDraft(2, _at(600), _at(2400))
    events = [
        {
            "event_type": "placement",
            "object": f"Mug #{i}",
            "destination_anchor": "Desk #1",
            "destination_relation": "on_surface",
            "destination_room": "Kitchen",
        }
        for i in range(8)
    ]
    text = activity_summary(draft, "Kitchen", events)
    assert text.startswith("09:10–09:40 Kitchen: Mug #0 was placed on Desk #1; ")
    assert "in the Kitchen" not in text
    assert text.endswith("and 3 more changes.")
    assert text == activity_summary(draft, "Kitchen", events)


def _scripted_graph():
    # Ten ground-truth actions: alternate pickups and placements of five objects.
    objects = []
    truth = []
    for index, canonical in enumerate(("keys", "mug", "wallet", "book", "watch")):
        t = 20.0 + index * 60.0
        objects.append(
            {
                "instance_id": index + 1,
                "canonical": canonical,
                "runs": [
                    ("on_surface", 1, 1, 0.0, t, 3),
                    ("carried_by_user", None, 1, t + 5.0, t + 20.0, 3),
                    ("inside", 2, 1, t + 30.0, t + 50.0, 3),
                ],
            }
        )
        truth += [
            (f"{canonical.title()} #", "pickup", t + 5.0),
            (f"{canonical.title()} #", "placement", t + 30.0),
        ]
    graph = make_session_graph(
        "scripted",
        T0,
        anchors=[
            {"anchor_id": 1, "canonical": "desk"},
            {"anchor_id": 2, "canonical": "drawer"},
        ],
        objects=objects,
        visits=[(1, 0.0, 400.0)],
        duration=400.0,
    )
    return graph, sorted(truth, key=lambda item: item[2])


def test_scripted_sequence_order_and_times(tmp_path) -> None:
    """AC-05 harness: >= 7 of 10 actions in order within +/-1 s."""

    graph, truth = _scripted_graph()
    store = open_store("homeS", tmp_path)
    ingest_session(store, graph)
    events = [e for e in store.events() if e["event_type"] in {"pickup", "placement"}]
    store.close()
    correct = 0
    for (prefix, kind, t), event in zip(truth, events, strict=False):
        expected = _at(t)
        offset = parse_iso(event["end_wallclock"]) - parse_iso(expected)
        same_time = abs(offset.total_seconds()) <= 1.0
        if (
            event["object"].startswith(prefix)
            and event["event_type"] == kind
            and same_time
        ):
            correct += 1
    assert len(events) == 10
    assert correct >= 7


def test_activities_endpoint_and_timeline_link(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AEGIS_STORE_ROOT", str(tmp_path))
    graph, _truth = _scripted_graph()
    store = open_store("homeS", tmp_path)
    report = ingest_session(store, graph)
    store.close()
    assert report.activities == 1
    client = TestClient(app)
    activities = client.get("/api/v1/activities?home_id=homeS").json()
    assert len(activities) == 1
    activity = activities[0]
    assert activity["event_count"] == 10
    assert activity["summary"].startswith("09:00–09:06 Room #1: Keys #")
    timeline = client.get("/api/v1/timeline?home_id=homeS").json()
    assert all(item["activity_id"] == activity["activity_id"] for item in timeline)
    later = client.get(
        "/api/v1/activities?home_id=homeS&start=2026-11-16T00:00:00Z"
    ).json()
    assert later == []
    close_stores()
