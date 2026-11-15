"""Tiered retention: compaction, summaries and roll-ups (FR4, AC-07/08/23)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from aegis.core.config import RetentionConfig
from aegis.memory import compaction as compaction_module
from aegis.memory.compaction import compact, compaction_ok, rollup
from aegis.memory.homes import close_stores, rename_home_room
from aegis.memory.ingest import ingest_session
from aegis.memory.store import open_store
from aegis.memory.summaries import object_day_summary
from aegis.memory.synthetic import SyntheticHome
from aegis.remote.api import app
from tests._graphs import make_session_graph

ROOMS = [
    {
        "room_id": 1,
        "label": "Kitchen",
        "room_type": "Kitchen",
        "evidence_labels": ["Refrigerator"],
    }
]
ANCHORS = [
    {"anchor_id": 1, "canonical": "desk"},
    {"anchor_id": 2, "canonical": "drawer"},
]
CONFIG = RetentionConfig()


def _local_noon(day: int) -> datetime:
    # 12:00 Asia/Karachi (UTC+5) on 2026-11-<day>.
    return datetime(2026, 11, day, 7, 0, tzinfo=UTC)


def _day_graph(day: int, keys_anchor: int, *, crop_root=None):
    start = f"2026-11-{day:02d}T05:00:00Z"  # 10:00 local
    graph = make_session_graph(
        f"d{day}",
        start,
        rooms=ROOMS,
        anchors=ANCHORS,
        objects=[
            {
                "instance_id": 1,
                "canonical": "keys",
                "runs": [("on_surface", keys_anchor, 1, 1.0, 50.0, 4)],
            },
            {
                "instance_id": 2,
                "canonical": "mug",
                "runs": [("on_surface", 1, 1, 1.0, 50.0, 4)],
            },
            {
                "instance_id": 3,
                "canonical": "glasses",
                "runs": [("inside", keys_anchor, 1, 1.0, 50.0, 4)],
            },
        ],
        visits=[(1, 0.0, 60.0)],
    )
    if crop_root is not None:
        folder = crop_root / f"d{day}"
        (folder / "evidence").mkdir(parents=True, exist_ok=True)
        for run in graph["state_runs"]:
            name = f"run_{run['instance_id']}_{day}.jpg"
            size = 16 + day
            cv2.imwrite(
                str(folder / "evidence" / name), np.full((size, size, 3), day, np.uint8)
            )
            run["evidence"] = {
                "path": f"evidence/{name}",
                "frame_id": 1,
                "width": size,
                "height": size,
            }
        return graph, folder
    return graph, None


@pytest.fixture
def store(tmp_path):
    home = open_store("homeC", tmp_path)
    # Keys alternate between the desk and the drawer every day.
    for day in range(8, 15):
        graph, folder = _day_graph(
            day, 1 if day % 2 == 0 else 2, crop_root=tmp_path / "graphs"
        )
        ingest_session(home, graph, evidence_root=folder)
    yield home
    home.close()


def _days_with_runs(store) -> set[str]:
    return {row[0][:10] for row in store.query("SELECT end_at FROM state_run")}


def test_rows_inside_hot_window_are_untouched(store) -> None:
    before = store.query("SELECT * FROM state_run WHERE end_at >= '2026-11-12'")
    report = compact(store, now=_local_noon(15), config=CONFIG)
    assert report.days_compacted == [
        "2026-11-08",
        "2026-11-09",
        "2026-11-10",
        "2026-11-11",
    ]
    after = store.query("SELECT * FROM state_run WHERE end_at >= '2026-11-12'")
    assert [dict(r) for r in after] == [dict(r) for r in before]


def test_summary_content_has_identity_location_room_event_types(store) -> None:
    compact(store, now=_local_noon(15), config=CONFIG)
    line = next(
        s
        for s in store.summaries()
        if s["period_start"] == "2026-11-09" and s["subject_key"] == "instance:1"
    )
    assert line["text"] == (
        "Keys #1: last on Drawer #1 in the Kitchen at 10:00; moved 1 time."
        " Moves: 10:00 Keys #1 moved from Desk #1 to Drawer #1 in the Kitchen."
    )
    sidecar = line["sidecar"]
    assert sidecar["instance_id"] == 1
    assert sidecar["last"]["anchor_id"] == 2
    assert sidecar["last"]["room_id"] == 1
    assert sidecar["event_types"] == {"moved_while_unobserved": 1}


def test_last_known_state_survives_compaction(store, monkeypatch, tmp_path) -> None:
    compact(store, now=datetime(2026, 12, 31, tzinfo=UTC), config=CONFIG)
    assert store.counts()["event"] == 0
    states = {s["label"]: s for s in store.latest_states()}
    assert (states["Keys #1"]["relation"], states["Keys #1"]["anchor_label"]) == (
        "on_surface",
        "Desk #1",
    )
    assert states["Mug #2"]["room_label"] == "Kitchen"
    monkeypatch.setenv("AEGIS_STORE_ROOT", str(tmp_path))
    answer = TestClient(app).get("/api/v1/query?item=keys&home_id=homeC").json()
    assert (
        answer["location_summary"]
        == "Your keys were last seen on Desk #1 in the Kitchen."
    )
    close_stores()


def test_room_labels_survive_compaction(store) -> None:
    compact(store, now=_local_noon(15), config=CONFIG)
    rename_home_room(store, 1, "Pantry")
    line = next(s for s in store.summaries() if s["subject_key"] == "instance:1")
    room_id = line["sidecar"]["last"]["room_id"]
    assert {r["room_id"]: r["label"] for r in store.rooms()}[room_id] == "Pantry"


def test_summarised_items_are_flagged(store, monkeypatch, tmp_path) -> None:
    compact(store, now=_local_noon(15), config=CONFIG)
    monkeypatch.setenv("AEGIS_STORE_ROOT", str(tmp_path))
    timeline = TestClient(app).get("/api/v1/timeline?home_id=homeC").json()
    tiers = {item["tier"] for item in timeline}
    assert tiers == {"summarised", "detailed"}
    summary = next(item for item in timeline if item["tier"] == "summarised")
    assert summary["event_type"] == "summary"
    assert summary["period_start"]
    close_stores()


def test_failed_verification_keeps_source_rows(store, monkeypatch, tmp_path) -> None:
    def broken(instance, runs, events, **kwargs):
        draft = object_day_summary(instance, runs, events, **kwargs)
        draft.sidecar["last"]["anchor_id"] = 999
        return draft

    before = store.counts()
    report = compact(store, now=_local_noon(15), config=CONFIG, summarizer=broken)
    assert report.days_compacted == []
    assert len(report.days_failed) == 4
    after = store.counts()
    assert {k: after[k] for k in ("state_run", "event", "room_visit")} == {
        k: before[k] for k in ("state_run", "event", "room_visit")
    }
    assert after["summary"] == 0
    assert compaction_ok(store) is False
    monkeypatch.setenv("AEGIS_STORE_ROOT", str(tmp_path))
    assert (
        TestClient(app).get("/api/v1/health?home_id=homeC").json()["compaction_ok"]
        is False
    )
    close_stores()


def test_compaction_is_idempotent(store) -> None:
    compact(store, now=_local_noon(15), config=CONFIG)
    first = store.counts()
    report = compact(store, now=_local_noon(15), config=CONFIG)
    assert report.days_compacted == []
    second = store.counts()
    assert {k: v for k, v in second.items() if k != "compaction_log"} == {
        k: v for k, v in first.items() if k != "compaction_log"
    }


def test_high_importance_instances_keep_detail_longer(store) -> None:
    compact(store, now=_local_noon(15), config=CONFIG)
    glasses = store.query(
        "SELECT end_at FROM state_run r JOIN instance i USING(instance_id) WHERE i.canonical='glasses'"
    )
    mug_days = store.query(
        "SELECT end_at FROM state_run r JOIN instance i USING(instance_id) WHERE i.canonical='mug'"
    )
    assert min(r[0] for r in glasses) < "2026-11-12"  # glasses keep 7 days
    assert all(r[0] >= "2026-11-12" for r in mug_days)
    # Past the longer window the detail goes too.
    compact(store, now=_local_noon(20), config=CONFIG)
    remaining = store.query(
        "SELECT end_at FROM state_run r JOIN instance i USING(instance_id) "
        "WHERE i.canonical='glasses' AND r.run_id NOT IN "
        "(SELECT last_run_id FROM instance WHERE last_run_id IS NOT NULL)"
    )
    assert all(r[0] >= "2026-11-13" for r in remaining)


def test_run_spanning_cutoff_is_kept(tmp_path) -> None:
    home = open_store("homeX", tmp_path)
    graph = make_session_graph(
        "long",
        "2026-11-10T05:00:00Z",
        rooms=ROOMS,
        anchors=ANCHORS,
        objects=[
            {
                "instance_id": 1,
                "canonical": "mug",
                "runs": [("on_surface", 1, 1, 0.0, 3 * 86400.0, 9)],
            }
        ],
        duration=3 * 86400.0,
    )
    ingest_session(home, graph)
    compact(home, now=_local_noon(15), config=CONFIG)
    assert home.counts()["state_run"] == 1
    home.close()


def test_evidence_files_are_deleted_with_runs_and_kept_for_last_known(store) -> None:
    compact(store, now=datetime(2026, 12, 31, tzinfo=UTC), config=CONFIG)
    rows = store.query("SELECT * FROM evidence")
    last_known = {
        int(r[0]) for r in store.query("SELECT last_evidence_id FROM instance") if r[0]
    }
    assert {int(r["evidence_id"]) for r in rows} == last_known
    files = sorted(p.name for p in (store.dir / "evidence").rglob("*.jpg"))
    assert len(files) == len(rows)


def test_weekly_rollup_reduces_rows_and_says_unchanged(store) -> None:
    compact(store, now=datetime(2027, 2, 1, tzinfo=UTC), config=CONFIG)
    day_rows = len([s for s in store.summaries() if s["level"] == "day"])
    written = rollup(store, now=datetime(2027, 2, 1, tzinfo=UTC), config=CONFIG)
    assert written >= 1
    summaries = store.summaries()
    assert len(summaries) < day_rows
    mug = next(
        s
        for s in summaries
        if s["subject_key"] == "instance:2" and s["level"] == "week"
    )
    assert mug["text"] == "Mug #2: unchanged, on Desk #1 in the Kitchen, all week."
    keys = next(
        s
        for s in summaries
        if s["subject_key"] == "instance:1"
        and s["level"] == "week"
        and s["sidecar"]["days"] > 1
    )
    assert "this week" in keys["text"]
    assert keys["text"].startswith("Keys #1: mostly ")


def test_growth_is_bounded(tmp_path) -> None:
    home = open_store("homeG", tmp_path)
    sim = SyntheticHome(objects=20, changes_per_day=40, sessions_per_day=4, seed=1)
    detail_rows = []
    summary_rows = []
    for offset in range(10):
        day = date(2026, 11, 1) + timedelta(days=offset)
        for graph in sim.sessions(day):
            ingest_session(home, graph)
        now = datetime(day.year, day.month, day.day, 23, 0, tzinfo=UTC)
        compact(home, now=now, config=CONFIG)
        counts = home.counts()
        detail_rows.append(
            counts["state_run"]
            + counts["event"]
            + counts["room_visit"]
            + counts["activity"]
        )
        summary_rows.append(counts["summary"])
    home.close()
    assert detail_rows[9] <= 1.2 * detail_rows[3]
    per_day = [b - a for a, b in pairwise(summary_rows[3:])]
    assert max(per_day) <= 20 + 4


def test_accuracy_before_and_after_compaction(store) -> None:
    """AC-08 harness: 'where' answers do not change after compaction."""

    def answers():
        return {
            s["label"]: (s["relation"], s["anchor_id"], s["room_id"])
            for s in store.latest_states()
        }

    before = answers()
    compact(store, now=datetime(2026, 12, 31, tzinfo=UTC), config=CONFIG)
    after = answers()
    correct = sum(before[k] == after.get(k) for k in before)
    assert correct / len(before) >= 0.85
    assert after == before


def test_day_bounds_follow_local_time() -> None:
    start, end = compaction_module._bounds(date(2026, 11, 15), "Asia/Karachi")
    assert start == "2026-11-14T19:00:00.000000+00:00"
    assert end == "2026-11-15T19:00:00.000000+00:00"
    assert json.dumps(CONFIG.timezone) == '"Asia/Karachi"'
