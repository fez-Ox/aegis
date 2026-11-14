"""Tests for detector post-processing and the batched frame loop."""

from __future__ import annotations

import cv2
import numpy as np

from aegis.core.config import PerceptionConfig, Sam2Config
from aegis.perception.detector import (
    DetectorModels,
    _dormant_match_cost,
    _TrackState,
    choose_mask,
    detect_and_track_objects,
    embedding_distance,
    mask_area_ratio,
    suppress_duplicates,
)


def test_different_classes_never_suppress_each_other() -> None:
    boxes = [
        ("shoes", 0.9, (10.0, 10.0, 50.0, 50.0)),
        ("storage cabinet", 0.8, (8.0, 8.0, 52.0, 52.0)),
        ("hand", 0.7, (12.0, 12.0, 48.0, 48.0)),
    ]
    assert len(suppress_duplicates(boxes, duplicate_iou=0.5, max_detections=30)) == 3


def test_overlapping_same_label_keeps_the_more_confident() -> None:
    boxes = [
        ("shoes", 0.6, (10.0, 10.0, 50.0, 50.0)),
        ("shoes", 0.9, (11.0, 11.0, 51.0, 51.0)),
        ("shoes", 0.8, (200.0, 10.0, 240.0, 50.0)),
    ]
    kept = suppress_duplicates(boxes, duplicate_iou=0.5, max_detections=30)
    assert [b[1] for b in kept] == [0.9, 0.8]


def test_detection_cap_is_honoured() -> None:
    boxes = [
        ("mug", 0.5 + i / 100, (i * 20.0, 0.0, i * 20.0 + 10, 10.0)) for i in range(10)
    ]
    assert len(suppress_duplicates(boxes, duplicate_iou=0.5, max_detections=4)) == 4


def test_mask_choice_for_fallback_mode() -> None:
    full = np.zeros((100, 200), dtype=bool)
    full[20:60, 40:120] = True  # fills its box exactly
    bbox = (40.0, 20.0, 120.0, 60.0)
    # Mask at half resolution: ratio is resolution independent.
    half = full[::2, ::2]
    assert abs(mask_area_ratio(half, bbox, (200, 100)) - 1.0) < 0.05
    assert choose_mask(full, bbox, (200, 100), min_area_ratio=0.15)[1] is False
    sliver = np.zeros_like(full)
    sliver[20:22, 40:44] = True
    assert choose_mask(sliver, bbox, (200, 100), min_area_ratio=0.15)[1] is True
    assert choose_mask(None, bbox, (200, 100), min_area_ratio=0.15) == (None, True)


def test_embedding_distance_and_dormant_match() -> None:
    a = (1.0, 0.0)
    b = (0.0, 1.0)
    assert embedding_distance(a, a) == 0.0
    assert embedding_distance(a, b) == 1.0
    assert embedding_distance(a, (1.0, 0.0, 0.0)) is None
    state = _TrackState(label="mug", bbox=(0.0, 0.0, 10.0, 10.0), embedding=a)
    near = _dormant_match_cost(
        state, "mug", (0.0, 0.0, 10.0, 10.0), None, 0.35, a, 0.35
    )
    far = _dormant_match_cost(state, "mug", (0.0, 0.0, 10.0, 10.0), None, 0.35, b, 0.35)
    assert near is not None and far is None


class _Value:
    def __init__(self, value):
        self.value = value

    def item(self):
        return self.value

    def tolist(self):
        return list(self.value)


class _Boxes:
    def __init__(self, rows):
        self.cls = [_Value(r[0]) for r in rows]
        self.conf = [_Value(r[1]) for r in rows]
        self.xyxy = [_Value(r[2]) for r in rows]

    def __len__(self):
        return len(self.cls)


class _Result:
    def __init__(self, rows):
        self.boxes = _Boxes(rows)
        self.names = {}
        self.masks = None


class _FakeDetector:
    """Returns one 'keys' box per frame, moving 5 px per frame."""

    def __init__(self):
        self.calls = []

    def set_classes(self, classes):
        self.classes = classes

    def predict(self, images, **kwargs):
        self.calls.append((len(images), kwargs.get("retina_masks")))
        results = []
        for image in images:
            offset = float(image[0, 0, 0])
            results.append(
                _Result([(0, 0.9, (10.0 + offset, 10.0, 40.0 + offset, 40.0))])
            )
        return results


def test_batched_loop_tracks_one_object(tmp_path) -> None:
    records = []
    for i in range(5):
        name = f"frame_{i:06d}.jpg"
        cv2.imwrite(str(tmp_path / name), np.full((60, 80, 3), i * 5, dtype=np.uint8))
        records.append({"frame_id": i, "timestamp": i * 0.5, "filename": name})
    fake = _FakeDetector()
    config = PerceptionConfig(target_classes=("keys",), batch_size=2)
    detections = detect_and_track_objects(
        records,
        tmp_path,
        config,
        sam2_config=Sam2Config(mode="off"),
        models=DetectorModels(detector=fake),
    )
    assert [n for n, _retina in fake.calls] == [2, 2, 1]
    assert all(retina is True for _n, retina in fake.calls)
    assert [d.frame_id for d in detections] == [0, 1, 2, 3, 4]
    assert {d.track_id for d in detections} == {1}
    assert all(d.label == "keys" for d in detections)
