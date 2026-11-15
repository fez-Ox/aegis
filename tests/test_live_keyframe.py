"""Tests for criterion-based live keyframe selection."""

from __future__ import annotations

import numpy as np

from aegis.core.config import KeyframeConfig
from aegis.ingestion.keyframe import KeyframeSelector


def _noise(seed: int = 0, size: tuple[int, int] = (48, 64)) -> np.ndarray:
    generator = np.random.default_rng(seed)
    return generator.integers(0, 255, (*size, 3), dtype=np.uint8)


def test_rejects_dark_frames() -> None:
    selector = KeyframeSelector(KeyframeConfig())
    decision = selector.evaluate(np.zeros((48, 64, 3), dtype=np.uint8), timestamp=0.0)
    assert decision.accepted is False
    assert decision.reason == "too_dark"


def test_rejects_blurred_flat_frames() -> None:
    selector = KeyframeSelector(KeyframeConfig())
    image = np.full((48, 64, 3), 128, dtype=np.uint8)
    decision = selector.evaluate(image, timestamp=0.0)
    assert decision.accepted is False
    assert decision.reason == "blurred"


def test_accepts_first_sharp_frame_then_suppresses_duplicates() -> None:
    selector = KeyframeSelector(KeyframeConfig(max_interval_seconds=2.0))
    image = _noise(1)

    first = selector.evaluate(image, timestamp=0.0)
    assert first.accepted is True
    assert first.reason == "first_frame"

    duplicate = selector.evaluate(image, timestamp=0.5)
    assert duplicate.accepted is False
    assert duplicate.reason == "duplicate"

    changed = selector.evaluate(_noise(2), timestamp=1.0)
    assert changed.accepted is True
    assert changed.reason == "scene_change"


def test_forces_keyframe_after_max_interval() -> None:
    selector = KeyframeSelector(KeyframeConfig(max_interval_seconds=2.0))
    image = _noise(3)
    assert selector.evaluate(image, timestamp=0.0).accepted is True
    forced = selector.evaluate(image, timestamp=2.5)
    assert forced.accepted is True
    assert forced.reason == "max_interval"


def test_stats_report_rejections() -> None:
    selector = KeyframeSelector(KeyframeConfig())
    selector.evaluate(np.zeros((48, 64, 3), dtype=np.uint8), timestamp=0.0)
    selector.evaluate(_noise(4), timestamp=0.1)

    stats = selector.stats()
    assert stats["evaluated"] == 2
    assert stats["accepted"] == 1
    assert stats["rejected_by_reason"] == {"too_dark": 1}


def test_disabled_selector_accepts_everything() -> None:
    selector = KeyframeSelector(KeyframeConfig(enabled=False))
    decision = selector.evaluate(np.zeros((48, 64, 3), dtype=np.uint8), timestamp=0.0)
    assert decision.accepted is True
    assert decision.reason == "disabled"
