"""Live egocentric capture sampling and persistence orchestration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic, sleep
from uuid import uuid4

from aegis.ingestion.live_source import FrameSource
from aegis.ingestion.live_storage import LiveSessionWriter


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

    def __post_init__(self) -> None:
        if self.sample_fps <= 0:
            raise ValueError("sample_fps must be positive")
        if self.max_duration_seconds < 0:
            raise ValueError("max_duration_seconds must be non-negative")
        if self.reconnect_interval_seconds < 0:
            raise ValueError("reconnect_interval_seconds must be non-negative")
        if self.reconnect_timeout_seconds < 0:
            raise ValueError("reconnect_timeout_seconds must be non-negative")


@dataclass(frozen=True, slots=True)
class LiveIngestionResult:
    """Summary returned after one live ingestion session."""

    session_id: str
    output_dir: Path
    frames: int
    status: str


def ingest_live(
    source_factory: Callable[[], FrameSource],
    config: LiveIngestionConfig,
    *,
    session_id: str | None = None,
    sleep_fn: Callable[[float], None] = sleep,
    clock: Callable[[], float] = monotonic,
) -> LiveIngestionResult:
    """Ingest a live frame source into one sampled local session.

    The source factory and clock/sleep functions are injected so tests can be
    deterministic and do not require a phone, network, or OpenCV stream.
    """

    session_id = session_id or new_live_session_id()
    started = datetime.now(UTC)
    writer = LiveSessionWriter(
        config.output_root,
        session_id,
        {
            "schema_version": 1,
            "session_id": session_id,
            "source_id": config.source_id,
            "source_protocol": config.source_protocol,
            "source_url": config.source_url,
            "started_at": started.isoformat().replace("+00:00", "Z"),
            "sample_rate_target_hz": config.sample_fps,
            "max_duration_seconds": config.max_duration_seconds,
        },
    )

    deadline = clock() + config.max_duration_seconds
    next_emit = float("-inf")
    reconnect_deadline: float | None = None
    reconnects = 0
    status = "completed"
    error = None

    try:
        while clock() < deadline:
            try:
                for frame in source_factory().frames():
                    reconnect_deadline = None
                    if clock() >= deadline:
                        status = "time_limit"
                        break

                    timestamp = frame.received_at.timestamp()
                    if timestamp >= next_emit:
                        writer.write(
                            frame.image,
                            received_at=frame.received_at,
                            source_id=config.source_id,
                            sample_rate=config.sample_fps,
                            source_protocol=config.source_protocol,
                        )
                        next_emit = timestamp + (1.0 / config.sample_fps)
                else:
                    raise ConnectionError("source ended")

                if status == "time_limit":
                    break
            except (ConnectionError, OSError) as exc:
                error = str(exc)
                if reconnect_deadline is None:
                    reconnect_deadline = clock() + config.reconnect_timeout_seconds
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
        writer.manifest["reconnect_count"] = reconnects
        writer.close(status=status, ended_at=datetime.now(UTC), error=error)

    return LiveIngestionResult(session_id, writer.session_dir, writer.count, status)


def new_live_session_id() -> str:
    """Create a collision-resistant human-readable live session ID."""

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}_{uuid4().hex[:6]}"
