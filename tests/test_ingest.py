"""Tests for merging session graphs into the home store."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from aegis.memory.ingest import ingest_session
from aegis.memory.store import open_store
from tests._graphs import make_session_graph

BEDROOM = [
    {
        "room_id": 1,
        "label": "Bedroom",
        "room_type": "Bedroom",
        "evidence_labels": ["Bed"],
    }
]
ANCHORS = [{"anchor_id": 1, "canonical": "bed"}, {"anchor_id": 2, "canonical": "desk"}]


@pytest.fixture
def store(tmp_path):
    home = open_store("home01", tmp_path)
    yield home
    home.close()


def _keys(runs, instance_id=1, appearance=None):
    return {
        "instance_id": instance_id,
        "canonical": "keys",
        "runs": runs,
        "appearance": appearance,
    }


def _session(name, start, runs, **kwargs):
    return make_session_graph(
        name, start, rooms=BEDROOM, anchors=ANCHORS, objects=[_keys(runs)], **kwargs
    )


def test_room_signature_is_case_normalised(store) -> None:
    ingest_session(
        store,
        _session("s1", "2026-11-15T09:00:00Z", [("on_surface", 2, 1, 1.0, 50.0, 10)]),
    )
    signature = set(json.loads(store.rooms()[0]["signature"]))
    assert "bed" in signature
    assert "Bed" not in signature


def test_first_session_creates_rooms_anchors_instances(store) -> None:
    report = ingest_session(
        store,
        _session("s1", "2026-11-15T09:00:00Z", [("on_surface", 2, 1, 1.0, 50.0, 10)]),
    )
    assert (report.rooms_created, report.anchors_created, report.instances_created) == (
        1,
        2,
        1,
    )
    state = store.latest_states()[0]
    assert state["label"] == "Keys #1"
    assert (state["relation"], state["anchor_label"], state["room_label"]) == (
        "on_surface",
        "Desk #1",
        "Bedroom",
    )
    assert state["last_seen_wallclock"] == "2026-11-15T09:00:50.000000+00:00"


def test_reingest_same_graph_is_noop(store) -> None:
    graph = _session(
        "s1", "2026-11-15T09:00:00Z", [("on_surface", 2, 1, 1.0, 50.0, 10)]
    )
    ingest_session(store, graph)
    before = store.counts()
    assert ingest_session(store, graph).status == "unchanged"
    assert store.counts() == before


def test_reingest_changed_graph_replaces_only_that_session(store) -> None:
    ingest_session(
        store,
        _session("s1", "2026-11-15T09:00:00Z", [("on_surface", 2, 1, 1.0, 50.0, 10)]),
    )
    ingest_session(
        store,
        _session(
            "s2",
            "2026-11-15T10:00:00Z",
            [("on_surface", 2, 1, 1.0, 5.0, 2), ("inside", None, 1, 10.0, 40.0, 5)],
        ),
    )
    changed = _session("s2", "2026-11-15T10:00:00Z", [("under", 1, 1, 1.0, 40.0, 5)])
    assert ingest_session(store, changed).status == "replaced"
    sessions = {row["session_id"] for row in store.sessions()}
    assert sessions == {"s1", "s2"}
    state = store.latest_states()[0]
    assert (state["relation"], state["anchor_label"]) == ("under", "Bed #1")
    assert {
        r["session_id"] for r in store.query("SELECT session_id FROM state_run")
    } == {
        "s1",
        "s2",
    }


def test_second_session_same_place_extends_run_and_adds_no_event(store) -> None:
    ingest_session(
        store,
        _session("s1", "2026-11-15T09:00:00Z", [("on_surface", 2, 1, 1.0, 50.0, 10)]),
    )
    report = ingest_session(
        store,
        _session("s2", "2026-11-15T12:00:00Z", [("on_surface", 2, 1, 1.0, 30.0, 4)]),
    )
    assert report.runs_extended == 1
    assert report.runs_inserted == 0
    assert store.counts()["state_run"] == 1
    assert store.counts()["event"] == 0
    run = store.query("SELECT * FROM state_run")[0]
    assert run["observation_count"] == 14
    assert run["end_at"] == "2026-11-15T12:00:30.000000+00:00"


def test_second_session_moved_object_adds_moved_while_unobserved_event(store) -> None:
    ingest_session(
        store,
        _session("s1", "2026-11-15T09:00:00Z", [("on_surface", 2, 1, 1.0, 50.0, 10)]),
    )
    ingest_session(
        store, _session("s2", "2026-11-15T12:00:00Z", [("under", 1, 1, 1.0, 30.0, 4)])
    )
    events = store.events()
    assert [e["event_type"] for e in events] == ["moved_while_unobserved"]
    assert events[0]["source_anchor"] == "Desk #1"
    assert events[0]["destination_anchor"] == "Bed #1"
    assert store.latest_states()[0]["relation"] == "under"


def test_instance_ids_are_stable_across_sessions(store) -> None:
    for index, start in enumerate(("09", "10", "11")):
        ingest_session(
            store,
            _session(
                f"s{index}",
                f"2026-11-15T{start}:00:00Z",
                [("on_surface", 2, 1, 1.0, 9.0, 3)],
            ),
        )
    assert [s["instance_id"] for s in store.latest_states()] == [1]
    assert store.counts()["anchor"] == 2
    assert store.counts()["room"] == 1


def test_out_of_order_session_is_rejected(store) -> None:
    ingest_session(
        store,
        _session("late", "2026-11-15T12:00:00Z", [("on_surface", 2, 1, 1.0, 9.0, 3)]),
    )
    with pytest.raises(ValueError, match="chronological"):
        ingest_session(
            store,
            _session(
                "early", "2026-11-15T09:00:00Z", [("on_surface", 2, 1, 1.0, 9.0, 3)]
            ),
        )
    assert {row["session_id"] for row in store.sessions()} == {"late"}


def test_session_without_wallclock_is_labelled_ingest_time(store) -> None:
    graph = _session(
        "s1",
        "2026-11-15T09:00:00Z",
        [("on_surface", 2, 1, 1.0, 50.0, 10)],
        time_source="none",
    )
    now = datetime(2026, 11, 15, 18, 0, tzinfo=UTC)
    ingest_session(store, graph, now=now)
    session = store.sessions()[0]
    assert session["time_source"] == "ingest"
    assert session["ended_at"] == "2026-11-15T18:00:00.000000+00:00"
    assert session["started_at"] == "2026-11-15T17:59:00.000000+00:00"


def test_store_rows_grow_with_changes_not_keyframes(store, tmp_path) -> None:
    ingest_session(
        store,
        _session(
            "a1",
            "2026-11-15T09:00:00Z",
            [("on_surface", 2, 1, 1.0, 9.0, 20)],
            keyframes=20,
        ),
    )
    small = store.counts()
    other = open_store("home02", tmp_path)
    ingest_session(
        other,
        _session(
            "a1",
            "2026-11-15T09:00:00Z",
            [("on_surface", 2, 1, 1.0, 999.0, 2000)],
            keyframes=2000,
        ),
    )
    large = other.counts()
    other.close()
    assert small == large


def test_v1_graph_is_rejected(store) -> None:
    with pytest.raises(ValueError, match="v1"):
        ingest_session(store, {"dataset_id": "old", "timeline": {}})


def test_contiguous_segments_share_room_and_carried_object(store) -> None:
    rooms = [
        {"room_id": 1, "label": "Room #1", "room_type": "Room", "evidence_labels": []}
    ]
    first = make_session_graph(
        "seg1",
        "2026-11-15T09:00:00Z",
        rooms=rooms,
        anchors=[{"anchor_id": 1, "canonical": "desk"}],
        objects=[
            {
                "instance_id": 1,
                "canonical": "mug",
                "runs": [
                    ("on_surface", 1, 1, 1.0, 20.0, 5),
                    ("carried_by_user", None, 1, 25.0, 58.0, 4),
                ],
            }
        ],
        visits=[(1, 0.0, 60.0)],
    )
    rooms2 = [
        {"room_id": 1, "label": "Room #1", "room_type": "Room", "evidence_labels": []},
        {
            "room_id": 2,
            "label": "Kitchen",
            "room_type": "Kitchen",
            "evidence_labels": ["Refrigerator"],
        },
    ]
    second = make_session_graph(
        "seg2",
        "2026-11-15T09:01:02Z",
        rooms=rooms2,
        anchors=[{"anchor_id": 1, "canonical": "refrigerator", "room_id": 2}],
        objects=[
            {
                "instance_id": 1,
                "canonical": "mug",
                "runs": [
                    ("carried_by_user", None, 1, 0.0, 10.0, 3),
                    ("inside", 1, 2, 20.0, 30.0, 4),
                ],
            }
        ],
        visits=[(1, 0.0, 15.0), (2, 15.0, 40.0)],
    )
    ingest_session(store, first)
    ingest_session(store, second)
    assert store.counts()["instance"] == 1
    assert store.counts()["room"] == 2
    events = [e["event_type"] for e in store.events()]
    assert events.count("pickup") == 1
    assert events.count("placement") == 1
    state = store.latest_states()[0]
    assert (state["relation"], state["anchor_label"], state["room_label"]) == (
        "inside",
        "Refrigerator #1",
        "Kitchen",
    )
