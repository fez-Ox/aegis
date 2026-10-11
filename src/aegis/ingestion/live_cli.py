"""CLI entry point for local live egocentric capture."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from aegis.ingestion.live_pipeline import LiveIngestionConfig, ingest_live
from aegis.ingestion.live_source import OpenCVMjpegSource, safe_url

logger = logging.getLogger(__name__)


def main() -> int:
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
        "--sample-fps",
        type=float,
        default=float(os.getenv("AEGIS_SAMPLE_FPS", "2")),
    )
    parser.add_argument(
        "--max-duration",
        type=float,
        default=float(os.getenv("AEGIS_MAX_DURATION_SECONDS", "600")),
    )
    parser.add_argument(
        "--reconnect-interval",
        type=float,
        default=float(os.getenv("AEGIS_RECONNECT_INTERVAL_SECONDS", "3")),
    )
    parser.add_argument(
        "--reconnect-timeout",
        type=float,
        default=float(os.getenv("AEGIS_RECONNECT_TIMEOUT_SECONDS", "30")),
    )
    args = parser.parse_args()
    if not args.url:
        parser.error("--url or AEGIS_STREAM_URL is required")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    result = ingest_live(
        lambda: OpenCVMjpegSource(args.url),
        LiveIngestionConfig(
            output_root=args.output_root,
            source_id=args.source_id,
            sample_fps=args.sample_fps,
            max_duration_seconds=args.max_duration,
            reconnect_interval_seconds=args.reconnect_interval,
            reconnect_timeout_seconds=args.reconnect_timeout,
            source_url=safe_url(args.url),
        ),
    )
    logger.info(
        "session=%s status=%s frames=%d output=%s",
        result.session_id,
        result.status,
        result.frames,
        result.output_dir,
    )
    return 0 if result.status != "disconnected" else 1


if __name__ == "__main__":
    raise SystemExit(main())
