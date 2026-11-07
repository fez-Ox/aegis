"""Bounded outbound frame buffer for short storage/stall recovery (FR2.4).

The live loop copies accepted frames into this queue before persistence. When
storage stalls, later frames accumulate up to ``capacity``; the oldest frames
are dropped (and counted) rather than growing memory without bound. A recovered
stall drains the queue and is recorded as a gap.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class BufferedFrame:
    """One accepted frame waiting for persistence."""

    image: Any
    received_at: datetime
    timestamp: float
    captured_at: datetime | None = None
    keyframe: dict[str, Any] | None = None


class FrameBuffer:
    """A bounded FIFO queue with explicit drop and backlog accounting."""

    def __init__(self, capacity: int = 30):
        if capacity <= 0:
            raise ValueError("buffer capacity must be positive")
        self.capacity = int(capacity)
        self._frames: deque[BufferedFrame] = deque()
        self.dropped = 0
        self.total_pushed = 0
        self.total_popped = 0
        self.max_backlog = 0

    def push(self, frame: BufferedFrame) -> bool:
        """Append a frame; return ``True`` when the oldest frame was dropped."""

        self.total_pushed += 1
        dropped = False
        if len(self._frames) >= self.capacity:
            self._frames.popleft()
            self.dropped += 1
            dropped = True
        self._frames.append(frame)
        self.max_backlog = max(self.max_backlog, len(self._frames))
        return dropped

    def peek(self) -> BufferedFrame | None:
        return self._frames[0] if self._frames else None

    def pop(self) -> BufferedFrame | None:
        if not self._frames:
            return None
        self.total_popped += 1
        return self._frames.popleft()

    def drain(self) -> list[BufferedFrame]:
        frames = list(self._frames)
        self._frames.clear()
        self.total_popped += len(frames)
        return frames

    def backlog_seconds(self, sample_fps: float) -> float:
        """Approximate unprocessed backlog in seconds at the target rate."""

        if sample_fps <= 0:
            return 0.0
        return len(self._frames) / sample_fps

    def __len__(self) -> int:
        return len(self._frames)

    def __bool__(self) -> bool:
        return bool(self._frames)

    def stats(self) -> dict[str, Any]:
        return {
            "capacity": self.capacity,
            "backlog": len(self._frames),
            "max_backlog": self.max_backlog,
            "dropped": self.dropped,
            "total_pushed": self.total_pushed,
            "total_popped": self.total_popped,
        }
