"""Criterion-based live keyframe selection (FR2.1 / TC3).

Fixed-rate sampling alone keeps near-duplicate and unusable frames. This
selector keeps a frame only when it is exposed, sharp, and visually novel, and
forces one frame after ``max_interval_seconds`` so a static scene is still
represented in memory.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from time import monotonic
from typing import Any

from aegis.core.config import KeyframeConfig

_COMPARISON_SIZE = (64, 36)


@dataclass(frozen=True, slots=True)
class KeyframeDecision:
    """Outcome of evaluating one sampled frame."""

    accepted: bool
    reason: str
    sharpness: float
    brightness: float
    visual_change: float | None
    timestamp: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class KeyframeSelector:
    """Stateful sharpness/exposure/novelty gate for one capture session."""

    def __init__(self, config: KeyframeConfig | None = None):
        self.config = config or KeyframeConfig()
        self._last_gray: Any | None = None
        self._last_accepted_timestamp: float | None = None
        self._evaluated = 0
        self._accepted = 0
        self._rejected: dict[str, int] = {}

    def evaluate(
        self, image: Any, *, timestamp: float | None = None
    ) -> KeyframeDecision:
        """Evaluate a BGR (or grayscale) frame and remember accepted evidence."""

        if not self.config.enabled:
            moment = monotonic() if timestamp is None else float(timestamp)
            return KeyframeDecision(True, "disabled", 0.0, 0.0, None, moment)

        import cv2
        import numpy as np

        moment = monotonic() if timestamp is None else float(timestamp)
        gray = (
            image
            if getattr(image, "ndim", 3) == 2
            else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        )
        brightness = float(np.asarray(gray, dtype=np.float32).mean())
        sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        decision = self._decide(gray, brightness, sharpness, moment)
        self._evaluated += 1
        if decision.accepted:
            self._accepted += 1
            self._last_gray = cv2.resize(
                gray, _COMPARISON_SIZE, interpolation=cv2.INTER_AREA
            ).astype(np.float32)
            self._last_accepted_timestamp = moment
        else:
            self._rejected[decision.reason] = self._rejected.get(decision.reason, 0) + 1
        return decision

    def _decide(
        self,
        gray: Any,
        brightness: float,
        sharpness: float,
        timestamp: float,
    ) -> KeyframeDecision:
        import cv2
        import numpy as np

        if brightness < self.config.min_brightness:
            return KeyframeDecision(
                False, "too_dark", sharpness, brightness, None, timestamp
            )
        if brightness > self.config.max_brightness:
            return KeyframeDecision(
                False, "too_bright", sharpness, brightness, None, timestamp
            )
        if sharpness < self.config.min_sharpness:
            return KeyframeDecision(
                False, "blurred", sharpness, brightness, None, timestamp
            )

        if self._last_gray is None or self._last_accepted_timestamp is None:
            return KeyframeDecision(
                True, "first_frame", sharpness, brightness, None, timestamp
            )

        small = cv2.resize(gray, _COMPARISON_SIZE, interpolation=cv2.INTER_AREA).astype(
            np.float32
        )
        visual_change = float(np.mean(np.abs(small - self._last_gray) / 255.0))
        elapsed = timestamp - self._last_accepted_timestamp
        if (
            visual_change < self.config.min_visual_change
            and elapsed < self.config.max_interval_seconds
        ):
            return KeyframeDecision(
                False,
                "duplicate",
                sharpness,
                brightness,
                visual_change,
                timestamp,
            )
        reason = (
            "max_interval"
            if visual_change < self.config.min_visual_change
            else "scene_change"
        )
        return KeyframeDecision(
            True, reason, sharpness, brightness, visual_change, timestamp
        )

    @property
    def accepted(self) -> int:
        return self._accepted

    @property
    def rejected(self) -> int:
        return self._evaluated - self._accepted

    def stats(self) -> dict[str, Any]:
        """Serialisable selection summary stored in the session manifest."""

        return {
            "enabled": self.config.enabled,
            "evaluated": self._evaluated,
            "accepted": self._accepted,
            "rejected": self.rejected,
            "rejected_by_reason": dict(sorted(self._rejected.items())),
            "config": asdict(self.config),
        }
