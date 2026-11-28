"""Tests for generic cross-session matching settings and continuity rules."""

from __future__ import annotations

import pytest

from aegis.core.config import MatchingConfig, RuntimeConfig
from aegis.memory.matching import (
    AnchorInfo,
    InstanceInfo,
    RoomInfo,
    match_instances,
    match_rooms,
)


def test_matching_defaults_are_the_measured_values() -> None:
    config = MatchingConfig()
    assert config.room_pair_bare is True
    assert config.singleton_requires_evidence is True
    assert config.carried_requires_appearance is True
    assert config.appearance_threshold == 0.25
    assert RuntimeConfig.from_mapping({}).memory.matching == config


@pytest.mark.parametrize(
    "override",
    [
        {"room_min_similarity": 1.5},
        {"room_min_overlap": 0},
        {"appearance_threshold": -0.1},
        {"appearance_margin": 2.0},
    ],
)
def test_invalid_matching_settings_are_rejected(override: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        MatchingConfig(**override)


def test_bare_rooms_are_paired_when_enabled() -> None:
    session = [RoomInfo(1, "Room"), RoomInfo(2, "Room")]
    home = [RoomInfo(10, "Room"), RoomInfo(11, "Room")]
    assert match_rooms(session, home, pair_bare_rooms=False) == {1: None, 2: None}
    assert match_rooms(session, home, pair_bare_rooms=True) == {1: 10, 2: 11}


def _instances(anchor_id: int | None, room_id: int | None):
    return InstanceInfo(
        instance_id=1,
        canonical="keys",
        relation="on_surface",
        anchor_id=anchor_id,
        room_id=room_id,
    )


def test_singleton_can_match_by_room_when_anchor_moved() -> None:
    session = [_instances(2, 1)]
    home = [_instances(1, 1)]
    mapping = match_instances(
        session,
        home,
        lambda anchor_id: anchor_id,
        {1: 1},
        singleton_requires_evidence=True,
    )
    assert mapping == {1: 1}


def test_singleton_without_shared_context_is_not_merged() -> None:
    session = [_instances(None, None)]
    home = [_instances(None, None)]
    mapping = match_instances(
        session,
        home,
        lambda anchor_id: None,
        {},
        singleton_requires_evidence=True,
    )
    assert mapping == {1: None}


def test_carried_match_survives_missing_appearance() -> None:
    session = [
        InstanceInfo(1, "mug", "carried_by_user", None, None, 1),
    ]
    home = [
        InstanceInfo(9, "mug", "carried_by_user", None, None, 1),
    ]
    mapping = match_instances(
        session,
        home,
        lambda anchor_id: None,
        {1: 1},
        carried_requires_appearance=True,
    )
    assert mapping == {1: 9}


def test_anchor_with_no_position_still_matches_by_resident() -> None:
    from aegis.memory.matching import match_anchors

    session = [
        AnchorInfo(1, "desk", 1, None, frozenset({"keys"})),
    ]
    home = [
        AnchorInfo(10, "desk", 1, None, frozenset({"keys"})),
        AnchorInfo(11, "desk", 1, None, frozenset({"mug"})),
    ]
    result = match_anchors(session, home, {1: 1})
    assert result.mapping[1] == (10, "resident")
