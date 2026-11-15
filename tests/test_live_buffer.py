"""Tests for the bounded live frame buffer."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pytest

from aegis.ingestion.buffer import BufferedFrame, FrameBuffer


def _frame(sequence: int) -> BufferedFrame:
    return BufferedFrame(
        image=np.zeros((4, 4, 3), dtype=np.uint8),
        received_at=datetime(2025, 1, 1, tzinfo=UTC),
        timestamp=float(sequence),
    )


def test_buffer_drops_oldest_when_capacity_is_reached() -> None:
    buffer = FrameBuffer(capacity=2)
    assert buffer.push(_frame(0)) is False
    assert buffer.push(_frame(1)) is False
    assert buffer.push(_frame(2)) is True

    assert len(buffer) == 2
    assert buffer.dropped == 1
    assert buffer.max_backlog == 2
    assert buffer.peek() is not None
    assert buffer.peek().timestamp == 1.0


def test_buffer_drains_and_reports_backlog() -> None:
    buffer = FrameBuffer(capacity=3)
    for sequence in range(2):
        buffer.push(_frame(sequence))

    assert buffer.backlog_seconds(2.0) == pytest.approx(1.0)
    frames = buffer.drain()
    assert [frame.timestamp for frame in frames] == [0.0, 1.0]
    assert len(buffer) == 0


def test_buffer_rejects_invalid_capacity() -> None:
    with pytest.raises(ValueError):
        FrameBuffer(capacity=0)
