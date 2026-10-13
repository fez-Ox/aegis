"""Video and live-capture ingestion utilities."""

from aegis.ingestion.download import (
    EGOCENTRIC_PRESETS,
    download_file,
    ingest_video,
    probe_video,
    upload_to_modal_volume,
)
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
    "EGOCENTRIC_PRESETS",
    "DecodedFrame",
    "FrameSource",
    "LiveIngestionConfig",
    "LiveIngestionResult",
    "LiveSessionWriter",
    "OpenCVMjpegSource",
    "download_file",
    "ingest_live",
    "ingest_video",
    "new_live_session_id",
    "preprocess_video",
    "probe_video",
    "safe_url",
    "upload_to_modal_volume",
]
