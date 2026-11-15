"""CLI entry point for local live egocentric capture."""

from __future__ import annotations

import argparse
import logging
import os
import signal
import threading
from pathlib import Path
from typing import Any

from aegis.core.config import LiveCaptureConfig, load_config
from aegis.ingestion.live_handoff import promote_live_session
from aegis.ingestion.live_pipeline import LiveIngestionConfig, ingest_live
from aegis.ingestion.live_source import OpenCVMjpegSource, safe_url

logger = logging.getLogger(__name__)


def _install_pause_signals(pause_event: threading.Event) -> None:
    """SIGUSR1 pauses capture; SIGUSR2 resumes it (POSIX only)."""

    if not hasattr(signal, "SIGUSR1") or not hasattr(signal, "SIGUSR2"):
        return

    def _pause(_signum: int, _frame: Any) -> None:
        pause_event.set()

    def _resume(_signum: int, _frame: Any) -> None:
        pause_event.clear()

    signal.signal(signal.SIGUSR1, _pause)
    signal.signal(signal.SIGUSR2, _resume)


def _live_defaults(config_path: str | None) -> LiveCaptureConfig:
    if not config_path:
        return LiveCaptureConfig()
    return load_config(config_path).live


def _resolve(cli_value: Any, env_name: str, config_value: Any, cast: Any) -> Any:
    """Resolve a setting as CLI flag > environment variable > config value."""

    if cli_value is not None:
        return cli_value
    env_value = os.getenv(env_name)
    if env_value is not None:
        return cast(env_value)
    return config_value


def main(argv: list[str] | None = None) -> int:
    """Run a bounded local live-capture session."""

    parser = argparse.ArgumentParser(
        description="Pull an MJPEG stream into local Aegis frames"
    )
    parser.add_argument(
        "--url",
        default=os.getenv("AEGIS_STREAM_URL"),
        help="IP Webcam /video URL",
    )
    parser.add_argument(
        "--source-id",
        default=os.getenv("AEGIS_SOURCE_ID", "android-ip-webcam-01"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(os.getenv("AEGIS_OUTPUT_ROOT", "captures")),
    )
    parser.add_argument(
        "--session-id",
        default=os.getenv("AEGIS_SESSION_ID"),
        help="Explicit session ID (required with --resume)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Append to an existing session after a crash",
    )
    parser.add_argument(
        "--config-path",
        default=os.getenv("AEGIS_CONFIG_PATH"),
        help="Load live defaults from a runtime YAML (e.g. config/demo.yaml)",
    )
    parser.add_argument(
        "--sample-fps",
        type=float,
        default=None,
        help="Override live.sample_fps from the config",
    )
    parser.add_argument(
        "--max-duration",
        type=float,
        default=None,
        help="Override live.max_duration_seconds from the config",
    )
    parser.add_argument(
        "--reconnect-interval",
        type=float,
        default=None,
        help="Override live.reconnect_interval_seconds from the config",
    )
    parser.add_argument(
        "--reconnect-timeout",
        type=float,
        default=None,
        help="Override live.reconnect_timeout_seconds from the config",
    )
    parser.add_argument(
        "--buffer-capacity",
        type=int,
        default=None,
        help="Override live.buffer_capacity from the config",
    )
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=None,
        help="Override live.checkpoint_every from the config",
    )
    parser.add_argument(
        "--pause-file",
        type=Path,
        default=(
            Path(os.environ["AEGIS_PAUSE_FILE"])
            if os.getenv("AEGIS_PAUSE_FILE")
            else None
        ),
        help="Capture is paused while this file exists",
    )
    parser.add_argument(
        "--keyframe-selection",
        dest="keyframe_selection",
        action="store_const",
        const=True,
        default=None,
        help="Enable criterion-based keyframe selection",
    )
    parser.add_argument(
        "--no-keyframe-selection",
        dest="keyframe_selection",
        action="store_const",
        const=False,
        help="Disable criterion-based keyframe selection",
    )
    parser.add_argument(
        "--promote-dataset-id",
        default=None,
        help="After capture, promote to data/<dataset_id> ('auto' derives from session)",
    )
    parser.add_argument(
        "--promote-data-root",
        type=Path,
        default=Path("data"),
    )
    args = parser.parse_args(argv)

    if not args.url:
        parser.error("--url or AEGIS_STREAM_URL is required")
    if args.resume and not args.session_id:
        parser.error("--resume requires --session-id")

    live_defaults = _live_defaults(args.config_path)
    if args.keyframe_selection is True:
        keyframe = live_defaults.keyframe
    elif args.keyframe_selection is False:
        keyframe = None
    else:
        keyframe = live_defaults.keyframe if args.config_path else None

    sample_fps = _resolve(
        args.sample_fps, "AEGIS_SAMPLE_FPS", live_defaults.sample_fps, float
    )
    max_duration = _resolve(
        args.max_duration,
        "AEGIS_MAX_DURATION_SECONDS",
        live_defaults.max_duration_seconds,
        float,
    )
    reconnect_interval = _resolve(
        args.reconnect_interval,
        "AEGIS_RECONNECT_INTERVAL_SECONDS",
        live_defaults.reconnect_interval_seconds,
        float,
    )
    reconnect_timeout = _resolve(
        args.reconnect_timeout,
        "AEGIS_RECONNECT_TIMEOUT_SECONDS",
        live_defaults.reconnect_timeout_seconds,
        float,
    )
    buffer_capacity = _resolve(
        args.buffer_capacity,
        "AEGIS_BUFFER_CAPACITY",
        live_defaults.buffer_capacity,
        int,
    )
    checkpoint_every = _resolve(
        args.checkpoint_every,
        "AEGIS_CHECKPOINT_EVERY",
        live_defaults.checkpoint_every,
        int,
    )

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    pause_event = threading.Event()
    _install_pause_signals(pause_event)

    def pause_requested() -> bool:
        return pause_event.is_set() or (
            args.pause_file is not None and args.pause_file.exists()
        )

    result = ingest_live(
        lambda: OpenCVMjpegSource(args.url),
        LiveIngestionConfig(
            output_root=args.output_root,
            source_id=args.source_id,
            sample_fps=sample_fps,
            max_duration_seconds=max_duration,
            reconnect_interval_seconds=reconnect_interval,
            reconnect_timeout_seconds=reconnect_timeout,
            source_url=safe_url(args.url),
            buffer_capacity=buffer_capacity,
            checkpoint_every=checkpoint_every,
            keyframe=keyframe,
            pause_file=args.pause_file,
        ),
        session_id=args.session_id,
        resume=args.resume,
        pause_check=pause_requested,
    )
    logger.info(
        "session=%s status=%s frames=%d total=%d gaps=%d pauses=%d "
        "dropped=%d rejected=%d output=%s",
        result.session_id,
        result.status,
        result.frames,
        result.total_frames,
        result.gaps,
        result.pauses,
        result.dropped_frames,
        result.rejected_frames,
        result.output_dir,
    )

    if args.promote_dataset_id:
        dataset_id = args.promote_dataset_id
        if dataset_id == "auto":
            dataset_id = f"live_{result.session_id}".lower()
            dataset_id = "".join(
                char if (char.isalnum() or char in "._-") else "_"
                for char in dataset_id
            )
        promotion = promote_live_session(
            result.output_dir,
            dataset_id=dataset_id,
            data_root=args.promote_data_root,
        )
        logger.info(
            "promoted dataset=%s frames=%d duration=%.1fs dir=%s",
            promotion.dataset_id,
            promotion.frame_count,
            promotion.duration_sec,
            promotion.dataset_dir,
        )

    return 0 if result.status not in {"disconnected", "storage_error"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
