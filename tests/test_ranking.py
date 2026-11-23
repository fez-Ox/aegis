"""Tests for candidate-aware ranking, cues, and the minimal personal registry."""

from __future__ import annotations

from datetime import UTC, datetime

from aegis.core.config import RankingConfig
from aegis.evaluation.metrics import recall_at_k, reciprocal_rank
from aegis.memory.personal import (
    enroll,
    enrolled_instances,
    enrolled_items,
    personal_ids_for_query,
    resolve_alias,
)
from aegis.memory.reasoning import parse_query_cues, rank_candidates
from aegis.memory.store import open_store

NOW = datetime(2026, 1, 11, 12, 59, tzinfo=UTC)


def state(instance_id, *, last_seen, anchor, room=1, canonical="mug", **extra):
    base = {
        "instance_id": instance_id,
        "label": f"Mug #{instance_id}",
        "canonical": canonical,
        "room_id": room,
        "room_label": f"Room #{room}",
        "anchor_id": anchor,
        "anchor_label": f"Table #{anchor}",
        "relation": "on",
        "relation_certain": True,
        "confidence": 0.9,
        "last_seen_wallclock": last_seen,
        "placement_count": 0,
        "pickup_count": 0,
        "observation_count": 1,
        "evidence_id": instance_id,
    }
    base.update(extra)
    return base


def test_parse_query_cues_days_and_activity() -> None:
    cues = parse_query_cues("Where is the mug I used two days ago?", now=NOW)
    assert cues.days_ago == 2
    assert cues.window_start == "2026-01-09T00:00:00.000000+00:00"
    assert cues.window_end == "2026-01-10T00:00:00.000000+00:00"

    cues = parse_query_cues("Where is the mug after lunch?", now=NOW)
    assert cues.activity == "after lunch"
    assert cues.window_start == "2026-01-11T13:00:00.000000+00:00"


def test_recency_only_picks_most_recent() -> None:
    states = [
        state(1, last_seen="2026-01-07T12:00:00+00:00", anchor=1),
        state(2, last_seen="2026-01-10T12:00:00+00:00", anchor=2),
    ]
    result = rank_candidates(states, "mug", mode="recency_only", now=NOW)
    assert result["resolution_mode"] == "direct"
    assert result["candidates"][0]["instance_id"] == 2


def test_salience_can_outrank_recency() -> None:
    states = [
        state(
            1,
            last_seen="2026-01-07T12:00:00+00:00",
            anchor=1,
            last_moved_wallclock="2026-01-10T12:00:00+00:00",
            placement_count=2,
            first_room_id=2,
        ),
        state(2, last_seen="2026-01-10T12:00:00+00:00", anchor=2),
    ]
    result = rank_candidates(states, "mug", mode="salience", now=NOW)
    assert result["candidates"][0]["instance_id"] == 1
    breakdown = result["candidates"][0]["score_breakdown"]
    assert breakdown["interaction"] > 0
    assert breakdown["displacement"] == 1.0


def test_vip_registry_and_ambiguity() -> None:
    states = [
        state(1, last_seen="2026-01-10T12:00:00+00:00", anchor=1),
        state(2, last_seen="2026-01-10T12:00:00+00:00", anchor=2),
    ]
    plain = rank_candidates(states, "mug", mode="full", now=NOW)
    assert plain["is_ambiguous"] is True
    assert plain["resolution_mode"] == "disambiguate"

    vip = rank_candidates(states, "mug", mode="full", now=NOW, personal_ids=[2])
    assert vip["resolution_mode"] == "direct"
    assert vip["candidates"][0]["instance_id"] == 2
    assert vip["candidates"][0]["score_breakdown"]["vip"] == 1.0


def test_room_cue_filters_candidates() -> None:
    states = [
        state(1, last_seen="2026-01-10T12:00:00+00:00", anchor=1, room=1),
        state(2, last_seen="2026-01-10T12:00:00+00:00", anchor=2, room=2),
    ]
    cues = parse_query_cues("Where is the mug in room 2?", now=NOW)
    result = rank_candidates(states, "mug", cues=cues, now=NOW)
    assert [candidate["instance_id"] for candidate in result["candidates"]] == [2]


def test_visual_cue_boosts_a_captioned_candidate() -> None:
    cues = parse_query_cues("Where is the blue mug?", now=NOW)
    assert cues.visual_terms == ("blue",)
    states = [
        state(1, last_seen="2026-01-10T12:00:00+00:00", anchor=1),
        state(
            2,
            last_seen="2026-01-10T12:00:00+00:00",
            anchor=2,
            visual_caption="blue ceramic mug",
        ),
    ]
    plain = rank_candidates(states, "mug", mode="full", now=NOW)
    boosted = rank_candidates(states, "mug", mode="full", now=NOW, cues=cues)
    assert plain["is_ambiguous"] is True
    assert boosted["is_ambiguous"] is False
    assert boosted["candidates"][0]["instance_id"] == 2
    assert boosted["candidates"][0]["visual_tag"] == "blue ceramic mug"


def test_moved_mug_beats_recent_static_mug_and_recovers_mrr() -> None:
    """T2: interaction beats passive sightings; Recall@3/MRR grade the ranking."""

    states = [
        state(
            1,
            last_seen="2026-01-07T12:00:00+00:00",
            anchor=1,
            last_moved_wallclock="2026-01-10T12:00:00+00:00",
            placement_count=2,
            first_room_id=2,
        ),
        state(2, last_seen="2026-01-10T12:00:00+00:00", anchor=2),
    ]
    ranked = rank_candidates(states, "mug", mode="salience", now=NOW)
    places = [str(item["anchor_label"]).lower() for item in ranked["candidates"]]
    assert ranked["candidates"][0]["instance_id"] == 1
    assert ranked["is_ambiguous"] is False
    assert recall_at_k(places, ["table #1"], k=3) == 1.0
    assert reciprocal_rank(places, ["table #1"]) == 1.0


def test_ranking_config_rejects_bad_weights() -> None:
    try:
        RankingConfig(w_vip=0.1)
    except ValueError:
        pass
    else:
        raise AssertionError("expected invalid weight order to fail")


def test_personal_registry_round_trip(tmp_path) -> None:
    store = open_store("home01", tmp_path)
    try:
        from tests._graphs import make_session_graph

        graph = make_session_graph(
            "s1",
            "2026-01-10T12:00:00+00:00",
            objects=[
                {
                    "instance_id": 7,
                    "canonical": "mug",
                    "runs": [("on", 1, 1, 0, 60, 2)],
                }
            ],
        )
        from aegis.memory.ingest import ingest_session

        ingest_session(store, graph)
        instance_id = store.one("SELECT instance_id FROM instance")["instance_id"]
        assert enrolled_instances(store) == []
        assert [item.instance_id for item in enroll(store, instance_id)] == [
            instance_id
        ]
        assert [item.instance_id for item in enroll(store, instance_id)] == [
            instance_id
        ]
        assert enrolled_instances(store) == [instance_id]
    finally:
        store.close()


def test_personal_registry_alias_class_and_cues(tmp_path) -> None:
    """Layer 1: alias, class, usual place and reference crop survive a round trip."""

    from aegis.memory.ingest import ingest_session
    from tests._graphs import make_session_graph

    store = open_store("home_alias", tmp_path)
    try:
        graph = make_session_graph(
            "s1",
            "2026-01-10T12:00:00+00:00",
            objects=[
                {
                    "instance_id": 7,
                    "canonical": "mug",
                    "runs": [("on", 1, 1, 0, 60, 2)],
                }
            ],
        )
        ingest_session(store, graph)
        instance_id = store.one("SELECT instance_id FROM instance")["instance_id"]
        items = enroll(
            store,
            instance_id,
            alias="dad's cup",
            usual_anchor="Kitchen Counter #1",
            usual_room="Kitchen",
            visual_crop="/evidence/mug7.jpg",
        )
        item = items[0]
        assert item.canonical_class == "mug"
        assert item.usual_anchor == "Kitchen Counter #1"
        assert item.usual_room == "Kitchen"
        assert item.visual_crop == "/evidence/mug7.jpg"
        assert enrolled_items(store) == items
        assert resolve_alias(store, "Where is dad's cup?") == instance_id
        assert resolve_alias(store, "Where is the mug?") is None
        assert personal_ids_for_query(store, "Where is dad's cup?", "mug") == [
            instance_id
        ]
        assert personal_ids_for_query(store, "Where is the mug?", "mug") == [
            instance_id
        ]
    finally:
        store.close()


def test_api_resolves_enrolled_alias_to_its_class(tmp_path, monkeypatch) -> None:
    """Layer 1 end to end: a patient's alias becomes a grounded answer."""

    from fastapi.testclient import TestClient

    from aegis.memory.ingest import ingest_session
    from aegis.memory.repository import StoreRepository
    from aegis.remote.api import app
    from tests._graphs import make_session_graph

    store = open_store("home_api_alias", tmp_path)
    try:
        graph = make_session_graph(
            "s1",
            "2026-01-10T12:00:00+00:00",
            objects=[
                {
                    "instance_id": 7,
                    "canonical": "mug",
                    "runs": [("on", 1, 1, 0, 60, 2)],
                }
            ],
        )
        ingest_session(store, graph)
        instance_id = store.one("SELECT instance_id FROM instance")["instance_id"]
        enroll(store, instance_id, alias="dad's cup")

        import aegis.remote.api as api_module

        monkeypatch.setattr(
            api_module,
            "resolve_repository",
            lambda dataset_id, home_id: (home_id or dataset_id, StoreRepository(store)),
        )
        response = TestClient(app).get(
            "/api/v1/query",
            params={"item": "Where is dad's cup?", "home_id": "home_api_alias"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["found"] is True
        assert body["instance_id"] == instance_id
        assert body["resolution_mode"] == "direct"
    finally:
        store.close()


def test_personal_registry_reads_legacy_id_list(tmp_path) -> None:
    store = open_store("home_legacy", tmp_path)
    try:
        store.execute(
            "INSERT INTO meta(key, value) VALUES (?, ?)",
            ("personal_items", "[3, 4]"),
        )
        assert enrolled_instances(store) == [3, 4]
    finally:
        store.close()
