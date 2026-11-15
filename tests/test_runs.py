"""Tests for debounced state runs and their events."""

from __future__ import annotations

from aegis.core.config import MemoryBuildConfig
from aegis.core.models import BoundingBox3D
from aegis.memory.runs import Observation, build_events, build_state_runs


def _obs(frame_id, relation, anchor_id=1, *, hand=False, certain=True, confidence=0.9):
    box = BoundingBox3D(
        frame_id=frame_id,
        timestamp=float(frame_id),
        track_id=1,
        label="keys",
        confidence=confidence,
        center=(0.0, 0.0, 0.0),
        size=(0.1, 0.1, 0.1),
        bbox_2d=(0.0, 0.0, 1.0, 1.0),
    )
    return Observation(
        frame_id=frame_id,
        timestamp=float(frame_id),
        instance_id=1,
        box=box,
        relation=relation,
        anchor_id=anchor_id,
        certain=certain,
        hand_cue=hand,
    )


def _relations(observations):
    runs = build_state_runs(observations)
    return [(r.relation, r.anchor_id, r.observation_count) for r in runs.get(1, [])]


def test_single_flicker_does_not_create_a_run() -> None:
    obs = [
        _obs(1, "on_surface"),
        _obs(2, "under"),
        _obs(3, "on_surface"),
        _obs(4, "on_surface"),
    ]
    assert _relations(obs) == [("on_surface", 1, 4)]


def test_two_consecutive_observations_change_state() -> None:
    obs = [_obs(1, "on_surface"), _obs(2, "inside", 2), _obs(3, "inside", 2)]
    assert _relations(obs) == [("on_surface", 1, 1), ("inside", 2, 2)]


def test_trailing_single_observation_commits_only_when_confident_and_certain() -> None:
    confident = [_obs(1, "on_surface"), _obs(2, "on_surface"), _obs(3, "inside", 2)]
    assert _relations(confident)[-1] == ("inside", 2, 1)
    weak = [
        _obs(1, "on_surface"),
        _obs(2, "on_surface"),
        _obs(3, "inside", 2, confidence=0.3),
    ]
    assert _relations(weak) == [("on_surface", 1, 3)]
    uncertain = [
        _obs(1, "on_surface"),
        _obs(2, "on_surface"),
        _obs(3, "near", 2, certain=False),
    ]
    assert _relations(uncertain) == [("on_surface", 1, 3)]


def test_unconfirmed_instance_yields_nothing() -> None:
    assert build_state_runs([_obs(1, "on_surface")]) == {}
    relaxed = MemoryBuildConfig(min_observations=1)
    assert len(build_state_runs([_obs(1, "on_surface")], settings=relaxed)[1]) == 1


def test_pickup_then_placement_events() -> None:
    obs = [
        _obs(1, "on_floor", None),
        _obs(2, "on_floor", None),
        _obs(3, "near", hand=True),
        _obs(4, "near", hand=True),
        _obs(5, "inside", 2),
        _obs(6, "inside", 2),
    ]
    runs = build_state_runs(obs)
    events = build_events(
        runs,
        names={1: "Keys #1"},
        anchor_labels={2: "Drawer #2"},
        room_labels={},
        wallclock=lambda _frame: None,
    )
    assert [e["event_type"] for e in events] == ["pickup", "placement"]
    assert events[1]["destination_anchor"] == "Drawer #2"
    assert events[1]["source_relation"] == "carried_by_user"
