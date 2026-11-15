"""Live egocentric capture sampling, pause/gap control, and persistence.

The loop keeps the FR1/FR2 source boundary replaceable while adding the
Milestone 1 reliability features: bounded stall buffering, explicit gap and
pause records, criterion-based keyframes, and crash-safe resume.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic, sleep
from uuid import uuid4

from aegis.core.config import KeyframeConfig
from aegis.ingestion.buffer import BufferedFrame, FrameBuffer
from aegis.ingestion.contracts import ContractError, load_session_manifest
from aegis.ingestion.keyframe import KeyframeSelector
from aegis.ingestion.live_source import FrameSource
from aegis.ingestion.live_storage import LiveSessionWriter

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LiveIngestionConfig:
    """Configuration for local live FR1/FR2 ingestion sessions."""

    output_root: Path
    source_id: str = "android-ip-webcam-01"
    sample_fps: float = 2.0
    max_duration_seconds: float = 600.0
    reconnect_interval_seconds: float = 3.0
    reconnect_timeout_seconds: float = 30.0
    source_protocol: str = "http-mjpeg"
    source_url: str | None = None
    buffer_capacity: int = 30
    checkpoint_every: int = 1
    keyframe: KeyframeConfig | None = None
    pause_file: Path | None = None

    def __post_init__(self) -> None:
        if self.sample_fps <= 0:
            raise ValueError("sample_fps must be positive")
        if self.max_duration_seconds < 0:
            raise ValueError("max_duration_seconds must be non-negative")
        if self.reconnect_interval_seconds < 0:
            raise ValueError("reconnect_interval_seconds must be non-negative")
        if self.reconnect_timeout_seconds < 0:
            raise ValueError("reconnect_timeout_seconds must be non-negative")
        if self.buffer_capacity <= 0:
            raise ValueError("buffer_capacity must be positive")
        if self.checkpoint_every <= 0:
            raise ValueError("checkpoint_every must be positive")


@dataclass(frozen=True, slots=True)
class LiveIngestionResult:
    """Summary returned after one live ingestion session."""

    session_id: str
    output_dir: Path
    frames: int
    status: str
    total_frames: int = 0
    gaps: int = 0
    pauses: int = 0
    dropped_frames: int = 0
    rejected_frames: int = 0
    reconnects: int = 0
    resumed: bool = False
    max_backlog: int = 0


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def ingest_live(
    source_factory: Callable[[], FrameSource],
    config: LiveIngestionConfig,
    *,
    session_id: str | None = None,
    sleep_fn: Callable[[float], None] = sleep,
    clock: Callable[[], float] = monotonic,
    resume: bool = False,
    pause_check: Callable[[], bool] | None = None,
    writer_factory: Callable[..., LiveSessionWriter] | None = None,
) -> LiveIngestionResult:
    """Ingest a live frame source into one sampled local session.

    The source factory, clock, sleep, pause predicate, and writer factory are
    injected so tests can be deterministic and do not require a phone, network,
    or OpenCV stream.
    """

    session_id = session_id or new_live_session_id()
    started_at = datetime.now(UTC)
    if resume:
        try:
            existing = load_session_manifest(config.output_root / session_id)
            started_at = datetime.fromisoformat(str(existing["started_at"]))
        except (ContractError, FileNotFoundError, ValueError):
            pass

    manifest = {
        "schema_version": 2,
        "session_id": session_id,
        "source_id": config.source_id,
        "source_protocol": config.source_protocol,
        "source_url": config.source_url,
        "started_at": _iso(started_at),
        "sample_rate_target_hz": config.sample_fps,
        "max_duration_seconds": config.max_duration_seconds,
        "buffer_capacity": config.buffer_capacity,
        "checkpoint_every": config.checkpoint_every,
        "authoritative_timestamp_field": "capture_timestamp",
    }
    factory = writer_factory or LiveSessionWriter
    writer = factory(
        config.output_root,
        session_id,
        manifest,
        resume=resume,
        checkpoint_every=config.checkpoint_every,
    )

    selector = (
        KeyframeSelector(config.keyframe)
        if config.keyframe is not None and config.keyframe.enabled
        else None
    )
    buffer = FrameBuffer(config.buffer_capacity)

    deadline = clock() + config.max_duration_seconds
    next_emit = float("-inf")
    reconnect_deadline: float | None = None
    reconnects = 0
    status = "completed"
    error: str | None = None
    rejected = 0

    disconnect_started_at: datetime | None = None
    disconnect_started_clock: float | None = None
    disconnect_dropped = 0
    disconnect_sequence_before = 0

    stall_started_at: datetime | None = None
    stall_dropped = 0
    stall_dropped_baseline = 0
    stall_sequence_before = 0

    pause_started_at: datetime | None = None
    pause_dropped = 0

    def is_paused() -> bool:
        if pause_check is not None and pause_check():
            return True
        return bool(config.pause_file is not None and config.pause_file.exists())

    def close_stall(*, recovered: bool = True) -> None:
        nonlocal stall_started_at, stall_dropped
        if stall_started_at is None:
            return
        ended = datetime.now(UTC)
        try:
            writer.record_gap(
                gap_start=stall_started_at,
                gap_end=ended,
                reason="storage_stall",
                dropped_estimate=stall_dropped,
                sequence_before=stall_sequence_before,
                sequence_after=writer.total_count,
                recovered=recovered,
                index=recovered,
            )
        except OSError:
            logger.exception("could not persist storage-stall gap")
        stall_started_at = None
        stall_dropped = 0

    def flush_buffer() -> bool:
        nonlocal stall_started_at, stall_dropped
        nonlocal stall_dropped_baseline, stall_sequence_before
        while len(buffer):
            frame = buffer.peek()
            if frame is None:
                break
            try:
                writer.write(
                    frame.image,
                    received_at=frame.received_at,
                    source_id=config.source_id,
                    sample_rate=config.sample_fps,
                    source_protocol=config.source_protocol,
                    captured_at=frame.captured_at,
                    keyframe=frame.keyframe,
                )
            except OSError:
                if stall_started_at is None:
                    stall_started_at = datetime.now(UTC)
                    stall_dropped = 0
                    stall_dropped_baseline = buffer.dropped
                    stall_sequence_before = writer.total_count
                return False
            buffer.pop()
        close_stall()
        return True

    def close_disconnect(*, recovered: bool) -> None:
        nonlocal disconnect_started_at, disconnect_started_clock, disconnect_dropped
        nonlocal error
        if disconnect_started_at is None:
            return
        ended = datetime.now(UTC)
        dropped = disconnect_dropped
        if disconnect_started_clock is not None and dropped == 0:
            dropped = max(
                0,
                round(max(0.0, clock() - disconnect_started_clock) * config.sample_fps),
            )
        try:
            writer.record_gap(
                gap_start=disconnect_started_at,
                gap_end=ended,
                reason="disconnect",
                dropped_estimate=dropped,
                sequence_before=disconnect_sequence_before,
                sequence_after=writer.total_count,
                recovered=recovered,
                index=recovered,
            )
        except OSError:
            logger.exception("could not persist disconnect gap")
        if recovered:
            # The stream came back; do not report it as a terminal error.
            error = None
        disconnect_started_at = None
        disconnect_started_clock = None
        disconnect_dropped = 0

    def finalize_pause(*, recovered: bool = True) -> None:
        nonlocal pause_started_at, pause_dropped
        if pause_started_at is None:
            return
        ended = datetime.now(UTC)
        try:
            writer.record_pause(started_at=pause_started_at, ended_at=ended)
            writer.record_gap(
                gap_start=pause_started_at,
                gap_end=ended,
                reason="pause",
                dropped_estimate=pause_dropped,
                sequence_before=writer.total_count,
                sequence_after=writer.total_count,
                recovered=recovered,
                index=recovered,
            )
        except OSError:
            logger.exception("could not persist pause gap")
        pause_started_at = None
        pause_dropped = 0

    def update_pause() -> None:
        nonlocal pause_started_at, pause_dropped
        if not is_paused():
            finalize_pause()
            return
        if pause_started_at is None:
            pause_started_at = datetime.now(UTC)
            pause_dropped = 0

    try:
        while clock() < deadline:
            try:
                for frame in source_factory().frames():
                    reconnect_deadline = None
                    if disconnect_started_at is not None:
                        close_disconnect(recovered=True)
                    if clock() >= deadline:
                        status = "time_limit"
                        break

                    update_pause()
                    timestamp = frame.received_at.timestamp()
                    if timestamp < next_emit:
                        continue
                    next_emit = timestamp + (1.0 / config.sample_fps)
                    if pause_started_at is not None:
                        pause_dropped += 1
                        continue

                    captured_at = getattr(frame, "captured_at", None)
                    decision = None
                    if selector is not None:
                        decision = selector.evaluate(frame.image, timestamp=timestamp)
                        if not decision.accepted:
                            rejected += 1
                            continue
                    # Drain any backlog first. If storage is still stalled the
                    # new frame queues behind it and the oldest frame is dropped.
                    flush_buffer()
                    dropped_oldest = buffer.push(
                        BufferedFrame(
                            image=frame.image,
                            received_at=frame.received_at,
                            captured_at=captured_at,
                            timestamp=timestamp,
                            keyframe=decision.as_dict() if decision else None,
                        )
                    )
                    if dropped_oldest and stall_started_at is not None:
                        stall_dropped = buffer.dropped - stall_dropped_baseline
                    flush_buffer()

                if status == "time_limit":
                    break
                raise ConnectionError("source ended")
            except (ConnectionError, OSError) as exc:
                if stall_started_at is not None:
                    # A storage failure must not masquerade as a source disconnect.
                    logger.warning("storage still unavailable: %s", exc)
                    if clock() >= deadline:
                        status = "time_limit"
                        break
                    sleep_fn(config.reconnect_interval_seconds)
                    continue
                error = str(exc)
                if reconnect_deadline is None:
                    reconnect_deadline = clock() + config.reconnect_timeout_seconds
                    disconnect_started_at = datetime.now(UTC)
                    disconnect_started_clock = clock()
                    disconnect_sequence_before = writer.total_count
                    disconnect_dropped = 0
                if clock() >= reconnect_deadline:
                    status = "disconnected"
                    break
                reconnects += 1
                sleep_fn(config.reconnect_interval_seconds)
        else:
            status = "time_limit"
    except KeyboardInterrupt:
        status = "stopped"
    finally:
        finalize_pause(recovered=False)
        close_disconnect(recovered=False)
        if status != "disconnected" and not flush_buffer():
            status = "storage_error"
            error = error or "storage remained unavailable at session end"
            close_stall(recovered=False)
        if status == "disconnected" and stall_started_at is not None:
            close_stall(recovered=False)
        writer.manifest["reconnect_count"] = reconnects
        writer.manifest["dropped_frame_count"] = buffer.dropped
        writer.manifest["rejected_frame_count"] = rejected
        writer.manifest["buffer"] = buffer.stats()
        writer.manifest["keyframe_selection"] = (
            selector.stats() if selector is not None else {"enabled": False}
        )
        writer.close(status=status, ended_at=datetime.now(UTC), error=error)

    return LiveIngestionResult(
        session_id=session_id,
        output_dir=writer.session_dir,
        frames=writer.count,
        status=status,
        total_frames=writer.total_count,
        gaps=len(writer.gaps),
        pauses=len(writer.pauses),
        dropped_frames=buffer.dropped,
        rejected_frames=rejected,
        reconnects=reconnects,
        resumed=resume,
        max_backlog=buffer.max_backlog,
    )


def new_live_session_id() -> str:
    """Create a collision-resistant human-readable live session ID."""

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}_{uuid4().hex[:6]}"
