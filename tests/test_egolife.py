"""Tests for the EgoLife multi-day evaluation helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from aegis.core.config import load_config
from aegis.evaluation.egolife import (
    Clip,
    Query,
    dataset_id,
    find_state,
    group_segments,
    latest_recent_run,
    parse_clip,
    place_of,
    recent_state,
    score_bank,
    score_query,
    segment_start,
    select_window,
    snapshot,
    summarise,
)

CONFIG = Path(__file__).resolve().parent.parent / "config" / "egolife.yaml"


def clip(stamp: str) -> Clip:
    return Clip(path=f"A1_JAKE/DAY1/DAY1_A1_JAKE_{stamp}00.mp4", stamp=stamp)


def test_parse_clip_reads_day_and_stamp() -> None:
    parsed = parse_clip("A1_JAKE/DAY1/DAY1_A1_JAKE_11094208.mp4", 123)
    assert parsed is not None
    day, parsed_clip = parsed
    assert day == 1
    assert parsed_clip.stamp == "110942"
    assert parsed_clip.size_bytes == 123


def test_parse_clip_ignores_other_files() -> None:
    assert parse_clip("EgoLifeQA/EgoLifeQA_A1_JAKE.json") is None
    assert parse_clip("A1_JAKE/DAY1/notes.txt") is None


def test_select_window_is_inclusive_of_start_exclusive_of_end() -> None:
    clips = [
        clip("105959"),
        clip("110000"),
        clip("113000"),
        clip("115959"),
        clip("120000"),
    ]
    selected = select_window(clips, "11:00", 60)
    assert [item.stamp for item in selected] == ["110000", "113000", "115959"]


def test_select_window_sorts_unordered_input() -> None:
    selected = select_window([clip("113000"), clip("110000")], "11:00", 60)
    assert [item.stamp for item in selected] == ["110000", "113000"]


def test_group_segments_buckets_by_wall_clock() -> None:
    clips = [clip("110000"), clip("110430"), clip("110500"), clip("111000")]
    groups = group_segments(clips, "11:00", 5)
    assert [[item.stamp for item in group] for group in groups] == [
        ["110000", "110430"],
        ["110500"],
        ["111000"],
    ]


def test_group_segments_drops_short_buckets() -> None:
    groups = group_segments([clip("110000"), clip("112000")], "11:00", 5, min_clips=2)
    assert groups == []


def test_group_segments_keeps_buckets_at_the_minimum() -> None:
    clips = [clip("110000"), clip("110100"), clip("112000")]
    groups = group_segments(clips, "11:00", 5, min_clips=2)
    assert [[item.stamp for item in group] for group in groups] == [
        ["110000", "110100"]
    ]


def test_dataset_id_is_stable_and_zero_padded() -> None:
    assert dataset_id(3, 7) == "egolife_d3_s07"


def test_segment_start_uses_the_first_clip() -> None:
    assert segment_start(1, "110000", "2026-01-05") == datetime(
        2026, 1, 5, 11, 0, tzinfo=UTC
    )
    assert segment_start(3, "110430", "2026-01-05") == datetime(
        2026, 1, 7, 11, 4, 30, tzinfo=UTC
    )


def test_find_state_prefers_canonical_then_recency() -> None:
    states = [
        {"label": "Keys #1", "canonical": "keys", "last_seen_wallclock": "a"},
        {"label": "Keys #2", "canonical": "keys", "last_seen_wallclock": "b"},
        {"label": "Cup #1", "canonical": "cup", "last_seen_wallclock": "c"},
    ]
    assert find_state(states, "keys", "keys")["label"] == "Keys #2"
    assert find_state(states, "cup")["label"] == "Cup #1"
    assert find_state(states, "bottle") is None


def test_score_query_matches_expected_room_and_anchor() -> None:
    query = Query(
        id="q1",
        item="keys",
        asked_day=5,
        expect_room="Room #2",
        expect_anchor="Desk #1",
    )
    state = {
        "room_label": "Room #2",
        "anchor_label": "Desk #1",
        "last_seen_wallclock": "t",
    }
    score = score_query(query, state)
    assert score["found"] is True
    assert score["present_ok"] is True
    assert score["room_ok"] is True
    assert score["anchor_ok"] is True


def test_score_query_flags_wrong_room() -> None:
    query = Query(id="q2", item="keys", asked_day=5, expect_room="Room #2")
    state = {"room_label": "Room #4", "anchor_label": "Desk #1"}
    score = score_query(query, state)
    assert score["room_ok"] is False
    assert score["anchor_ok"] is None


def test_score_query_abstention_is_correct_when_item_absent() -> None:
    query = Query(id="q3", item="passport", asked_day=7, expect_present=False)
    score = score_query(query, None)
    assert score["found"] is False
    assert score["present_ok"] is True


def test_score_query_missing_item_is_wrong_when_expected() -> None:
    score = score_query(Query(id="q4", item="keys", asked_day=7), None)
    assert score["present_ok"] is False


def test_summarise_reports_rates_and_skips_unasked_checks() -> None:
    scores = [
        {"present_ok": True, "room_ok": True, "anchor_ok": None},
        {"present_ok": True, "room_ok": False, "anchor_ok": None},
    ]
    summary = summarise(scores)
    assert summary["n"] == 2
    assert summary["present"] == {"correct": 2, "n": 2, "accuracy": 1.0}
    assert summary["room"] == {"correct": 1, "n": 2, "accuracy": 0.5}
    assert summary["anchor"] == {"correct": 0, "n": 0, "accuracy": None}


def test_latest_recent_run_discards_old_evidence() -> None:
    runs = [
        {"end_at": "2026-01-05T11:30:00+00:00", "relation": "old"},
        {"end_at": "2026-01-09T11:30:00+00:00", "relation": "new"},
    ]
    assert latest_recent_run(runs, "2026-01-08T11:30:00+00:00")["relation"] == "new"
    assert latest_recent_run(runs, "2026-01-10T11:30:00+00:00") is None


def test_egolife_config_fits_the_keyframe_limit() -> None:
    config = load_config(CONFIG)
    assert (config.video.width, config.video.height) == (704, 704)
    assert config.video.sample_fps == 5
    per_segment = 5 * 60 * config.video.sample_fps // config.vggt.keyframe_stride
    assert per_segment <= config.vggt.max_keyframes
    assert config.memory.home_id == "egolife_jake"


class FakeStore:
    """The slice of HomeStore the scorers use."""

    def __init__(self, states, anchors=(), rooms=(), runs=None) -> None:
        self._states = list(states)
        self._anchors = list(anchors)
        self._rooms = list(rooms)
        self._runs = runs or {}

    def latest_states(self):
        return self._states

    def anchors(self):
        return self._anchors

    def rooms(self):
        return self._rooms

    def runs_for_instance(self, instance_id):
        return self._runs.get(instance_id, [])

    def counts(self):
        return {
            "room": len(self._rooms),
            "anchor": len(self._anchors),
            "instance": len(self._states),
        }


class FakeVocabulary:
    def resolve_query(self, text):
        return SimpleNamespace(id="cup") if text == "cup" else None


def test_snapshot_counts_and_anchor_quality() -> None:
    store = FakeStore(
        states=[{"label": "Cup #1"}],
        anchors=[{"match_quality": "unique"}, {"match_quality": "new"}],
        rooms=[{"label": "Kitchen"}],
    )
    result = snapshot(store)
    assert result["counts"] == {"room": 1, "anchor": 2, "instance": 1}
    assert result["anchor_match_quality"] == {"unique": 1, "new": 1}
    assert result["rooms"] == ["Kitchen"]


def test_recent_state_uses_the_newest_run_inside_the_window() -> None:
    store = FakeStore(
        states=[],
        anchors=[{"anchor_id": 7, "label": "Desk #1"}],
        rooms=[{"room_id": 3, "label": "Room #2"}],
        runs={
            5: [
                {"end_at": "2026-01-05T12:00:00+00:00", "anchor_id": 7, "room_id": 3},
                {"end_at": "2026-01-09T12:00:00+00:00", "anchor_id": 7, "room_id": 3},
            ]
        },
    )
    state = {"instance_id": 5, "room_label": "Room #2"}
    result = recent_state(store, state, "2026-01-08T00:00:00+00:00")
    assert result is not None
    assert result["anchor_label"] == "Desk #1"
    assert result["last_seen_wallclock"] == "2026-01-09T12:00:00+00:00"


def test_recent_state_is_none_when_all_evidence_is_old() -> None:
    store = FakeStore(
        states=[],
        runs={
            5: [{"end_at": "2026-01-05T12:00:00+00:00", "anchor_id": 7, "room_id": 3}]
        },
    )
    state = {"instance_id": 5}
    assert recent_state(store, state, "2026-01-08T00:00:00+00:00") is None


def test_place_of_strips_the_instance_suffix() -> None:
    assert place_of("Dining Table #3") == "dining table"
    assert place_of("Bed #1") == "bed"
    assert place_of(None) is None


def test_score_query_matches_the_caption_place_noun() -> None:
    query = Query(id="q5", item="mug", asked_day=7, expect_place=["table", "desk"])
    state = {"anchor_label": "Dining Table #2"}
    score = score_query(query, state)
    assert score["place"] == "dining table"
    assert score["place_ok"] is True


def test_score_query_rejects_a_different_place() -> None:
    query = Query(id="q6", item="mug", asked_day=7, expect_place=["table"])
    assert score_query(query, {"anchor_label": "Sofa #1"})["place_ok"] is False
    # A missing object cannot be in the expected place.
    assert score_query(query, None)["place_ok"] is False


def test_summarise_reports_the_place_rate() -> None:
    scores = [
        {"present_ok": True, "place_ok": True},
        {"present_ok": True, "place_ok": False},
    ]
    assert summarise(scores)["place"] == {"correct": 1, "n": 2, "accuracy": 0.5}


def test_frozen_bank_loads_and_is_well_formed() -> None:
    import json

    bank = (
        Path(__file__).resolve().parent.parent
        / "evaluation"
        / "annotations"
        / "egolife_queries.json"
    )
    payload = json.loads(bank.read_text(encoding="utf-8"))
    queries = [Query(**item) for item in payload["queries"]]
    assert len(queries) >= 15
    ids = [q.id for q in queries]
    assert len(ids) == len(set(ids))
    for query in queries:
        assert 1 <= query.asked_day <= 7
        assert query.asked_at is not None
        if query.expect_present:
            assert query.expect_place and query.observed_at
        else:
            assert query.expect_place is None


def test_score_bank_matches_by_canonical_and_runs_the_ablation() -> None:
    store = FakeStore(
        states=[
            {
                "instance_id": 5,
                "label": "Mug #1",
                "canonical": "cup",
                "room_label": "Room #2",
                "anchor_label": "Desk #1",
                "last_seen_wallclock": "2026-01-05T12:00:00+00:00",
            }
        ],
        anchors=[{"anchor_id": 7, "label": "Desk #1"}],
        rooms=[{"room_id": 3, "label": "Room #2"}],
        runs={
            5: [{"end_at": "2026-01-05T12:00:00+00:00", "anchor_id": 7, "room_id": 3}]
        },
    )
    query = Query(
        id="q1",
        item="cup",
        asked_day=7,
        asked_at="2026-01-11T12:00:00+00:00",
        expect_room="Room #2",
    )
    result = score_bank(store, [query], FakeVocabulary())
    assert result["full"][0]["found"] is True
    assert result["full"][0]["room_ok"] is True
    # Six-day-old evidence is outside the 24-hour ablation window.
    assert result["last_24h"][0]["found"] is False
    assert result["last_24h"][0]["present_ok"] is False
