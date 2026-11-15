"""Tests for cross-session room, anchor and object matching."""

from __future__ import annotations

import math

import pytest

from aegis.memory.matching import (
    AnchorInfo,
    InstanceInfo,
    RoomInfo,
    estimate_similarity,
    match_anchors,
    match_instances,
    match_rooms,
)


def test_rooms_with_disjoint_signatures_are_not_merged() -> None:
    session = [RoomInfo(1, "Bedroom", frozenset({"Bed", "wardrobe"}))]
    home = [RoomInfo(10, "Kitchen", frozenset({"refrigerator", "sink"}))]
    assert match_rooms(session, home) == {1: None}


def test_rooms_match_by_signature_with_margin() -> None:
    session = [RoomInfo(1, "Bedroom", frozenset({"Bed", "wardrobe", "nightstand"}))]
    home = [
        RoomInfo(10, "Bedroom", frozenset({"Bed", "wardrobe", "nightstand"})),
        RoomInfo(11, "Bedroom", frozenset({"Bed"})),
    ]
    assert match_rooms(session, home) == {1: 10}


def test_ambiguous_signature_is_not_matched() -> None:
    session = [RoomInfo(1, "Room", frozenset({"desk"}))]
    home = [
        RoomInfo(10, "Room", frozenset({"desk"})),
        RoomInfo(11, "Room", frozenset({"desk"})),
    ]
    assert match_rooms(session, home) == {1: None}


def test_room_continuity_and_single_bare_room() -> None:
    session = [RoomInfo(1, "Room"), RoomInfo(2, "Room")]
    home = [RoomInfo(10, "Room"), RoomInfo(11, "Room")]
    assert match_rooms(session, home, continuity=(2, 11)) == {1: 10, 2: 11}
    assert match_rooms([RoomInfo(1, "Room")], [RoomInfo(7, "Room")]) == {1: 7}


def test_similarity_estimate_recovers_rotation_scale_translation() -> None:
    theta, scale = 0.7, 1.3
    src = [(0.0, 0.0), (1.0, 0.0), (0.0, 2.0)]

    def apply(p):
        c, s = math.cos(theta), math.sin(theta)
        return (
            scale * (c * p[0] - s * p[1]) + 2.0,
            scale * (s * p[0] + c * p[1]) - 1.0,
        )

    transform = estimate_similarity(src, [apply(p) for p in src])
    assert transform.scale == pytest.approx(scale)
    assert transform.theta == pytest.approx(theta)
    assert transform.apply((3.0, 4.0)) == pytest.approx(apply((3.0, 4.0)))


def _home_bedroom():
    return [
        AnchorInfo(100, "bed", 10, (0.0, 0.0)),
        AnchorInfo(101, "wardrobe", 10, (4.0, 0.0)),
        AnchorInfo(102, "desk", 10, (0.0, 3.0)),
        AnchorInfo(103, "desk", 10, (4.0, 3.0)),
    ]


def test_two_desks_matched_by_position_after_alignment() -> None:
    # Session frame = home frame rotated by 90 degrees and shifted.
    def to_session(p):
        return (-p[1] + 5.0, p[0] - 2.0)

    home = _home_bedroom()
    session = [
        AnchorInfo(1, "bed", 1, to_session((0.0, 0.0))),
        AnchorInfo(2, "wardrobe", 1, to_session((4.0, 0.0))),
        AnchorInfo(3, "desk", 1, to_session((4.0, 3.0))),
        AnchorInfo(4, "desk", 1, to_session((0.0, 3.0))),
    ]
    result = match_anchors(session, home, {1: 10})
    assert result.mapping[1] == (100, "unique")
    assert result.mapping[2] == (101, "unique")
    assert result.mapping[3] == (103, "aligned")
    assert result.mapping[4] == (102, "aligned")


def test_without_alignment_or_residents_desks_fall_to_ordinal() -> None:
    home = [AnchorInfo(102, "desk", 10), AnchorInfo(103, "desk", 10)]
    session = [AnchorInfo(4, "desk", 1), AnchorInfo(3, "desk", 1)]
    result = match_anchors(session, home, {1: 10})
    assert result.mapping == {3: (102, "ordinal"), 4: (103, "ordinal")}


def test_residents_identify_an_anchor() -> None:
    home = [
        AnchorInfo(102, "desk", 10, residents=frozenset({"keys"})),
        AnchorInfo(103, "desk", 10, residents=frozenset({"laptop"})),
    ]
    session = [AnchorInfo(1, "desk", 1, residents=frozenset({"laptop"}))]
    assert match_anchors(session, home, {1: 10}).mapping[1] == (103, "resident")


def test_anchor_in_new_room_is_new() -> None:
    result = match_anchors([AnchorInfo(1, "bed", 5)], _home_bedroom(), {5: None})
    assert result.mapping[1] == (None, "new")


def _no_map(anchor_id):
    return {1: 100, 2: 101}.get(anchor_id)


def test_instance_left_on_anchor_is_recognised() -> None:
    home = [InstanceInfo(7, "keys", "on_surface", 100)]
    session = [InstanceInfo(1, "keys", "on_surface", 1)]
    assert match_instances(session, home, _no_map) == {1: 7}


def test_moved_single_instance_matches_by_class() -> None:
    home = [InstanceInfo(7, "wallet", "on_surface", 100)]
    session = [InstanceInfo(1, "wallet", "inside", 2)]
    assert match_instances(session, home, _no_map) == {1: 7}


def test_carried_object_continues_across_segments() -> None:
    home = [
        InstanceInfo(7, "mug", "carried_by_user", None),
        InstanceInfo(8, "mug", "on_surface", 100),
    ]
    session = [InstanceInfo(1, "mug", "carried_by_user", None)]
    assert match_instances(session, home, _no_map) == {1: 7}


def test_identical_objects_are_not_merged_without_evidence() -> None:
    home = [
        InstanceInfo(7, "mug", "on_surface", 100),
        InstanceInfo(8, "mug", "inside", 101),
    ]
    session = [InstanceInfo(1, "mug", "next_to", 2), InstanceInfo(2, "mug", "under", 2)]
    assert match_instances(session, home, _no_map) == {1: None, 2: None}


def test_appearance_needs_a_margin() -> None:
    home = [
        InstanceInfo(7, "mug", "on_surface", 100, appearance=(1.0, 0.0)),
        InstanceInfo(8, "mug", "inside", 101, appearance=(0.0, 1.0)),
    ]
    session = [InstanceInfo(1, "mug", "next_to", None, appearance=(0.95, 0.05))]
    assert match_instances(session, home, _no_map) == {1: 7}


def test_continuity_does_not_override_signature_or_type() -> None:
    """Regression: back-to-back sessions must not merge rooms of different types."""
    home = [
        RoomInfo(10, "Kitchen", frozenset({"Kitchen landmark", "desk"})),
        RoomInfo(11, "Bedroom", frozenset({"Bedroom landmark", "desk"})),
    ]
    session = [RoomInfo(1, "Kitchen", frozenset({"Kitchen landmark", "desk"}))]
    # The previous session ended in the bedroom; the evidence says kitchen.
    assert match_rooms(session, home, continuity=(1, 11)) == {1: 10}
    typed = [RoomInfo(2, "Kitchen")]
    assert match_rooms(typed, home, continuity=(2, 11)) == {2: None}
