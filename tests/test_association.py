"""Tests for session instance association (same rules for every class)."""

from __future__ import annotations

from aegis.core.models import BoundingBox3D
from aegis.core.vocabulary import default_vocabulary
from aegis.memory.association import associate_instances


def _box(frame_id, track_id, label, center, *, appearance=None, confidence=0.9):
    return BoundingBox3D(
        frame_id=frame_id,
        timestamp=0.1 * frame_id,
        track_id=track_id,
        label=label,
        confidence=confidence,
        center=center,
        size=(0.2, 0.2, 0.2),
        bbox_2d=(0.0, 0.0, 1.0, 1.0),
        appearance=appearance,
    )


def _ids(boxes):
    assignment, instances = associate_instances(boxes, vocabulary=default_vocabulary())
    return [assignment[i] for i in range(len(boxes))], instances


def test_same_track_reuses_instance() -> None:
    ids, _ = _ids([_box(1, 7, "mug", (0, 0, 0)), _box(2, 7, "cup", (3, 0, 0))])
    assert ids == [1, 1]


def test_track_restart_within_radius_reuses_instance() -> None:
    boxes = [
        _box(1, 1, "keys", (0, 0, 0)),
        _box(1, 2, "keys", (5, 0, 0)),
        _box(3, 9, "keys", (0.2, 0, 0)),
    ]
    ids, _ = _ids(boxes)
    assert ids[2] == ids[0]


def test_two_far_objects_with_different_appearance_get_two_ids() -> None:
    boxes = [
        _box(1, 1, "mug", (0, 0, 0), appearance=(1.0, 0.0)),
        _box(1, 2, "mug", (3, 0, 0), appearance=(0.0, 1.0)),
        _box(2, 5, "mug", (3.1, 0, 0), appearance=(0.0, 1.0)),
    ]
    ids, instances = _ids(boxes)
    assert len(instances) == 2
    assert ids[2] == ids[1]


def test_single_known_instance_relocates() -> None:
    ids, _ = _ids([_box(1, 1, "wallet", (0, 0, 0)), _box(9, 4, "wallet", (4, 0, 0))])
    assert ids == [1, 1]


def test_boxes_in_one_frame_never_share_an_instance() -> None:
    boxes = [_box(1, 1, "keys", (0, 0, 0)), _box(1, 2, "keys", (0.1, 0, 0))]
    ids, _ = _ids(boxes)
    assert len(set(ids)) == 2


def test_shoes_follow_the_same_rules_as_any_class() -> None:
    boxes = []
    for frame_id in (1, 2):
        for track_id, x in ((1, -2.0), (2, 0.0), (3, 2.0)):
            boxes.append(_box(frame_id, track_id, "shoes", (x, 0, 0)))
    ids, instances = _ids(boxes)
    assert len(instances) == 3
    assert ids[:3] == ids[3:]
    assert {t.display_name for t in instances.values()} == {
        "Shoes #1",
        "Shoes #2",
        "Shoes #3",
    }
