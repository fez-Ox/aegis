"""Video and live-capture ingestion utilities."""

from aegis.ingestion.live_pipeline import (
    LiveIngestionConfig,
    LiveIngestionResult,
    ingest_live,
    new_live_session_id,
)
from aegis.ingestion.live_source import (
    DecodedFrame,
    FrameSource,
    OpenCVMjpegSource,
    safe_url,
)
from aegis.ingestion.live_storage import LiveSessionWriter
from aegis.ingestion.video import preprocess_video

__all__ = [
    "DecodedFrame",
    "FrameSource",
    "LiveIngestionConfig",
    "LiveIngestionResult",
    "LiveSessionWriter",
    "OpenCVMjpegSource",
    "ingest_live",
    "new_live_session_id",
    "preprocess_video",
    "safe_url",
]
