"""Video and live-capture ingestion utilities."""

from aegis.ingestion.buffer import BufferedFrame, FrameBuffer
from aegis.ingestion.contracts import (
    ContractError,
    load_session_manifest,
    read_live_index,
    validate_frame_record,
    validate_gap_record,
    validate_normalized_metadata,
    validate_pause_record,
    validate_session_manifest,
    validate_session_state,
)
from aegis.ingestion.download import (
    EGOCENTRIC_PRESETS,
    download_file,
    ingest_video,
    probe_video,
    upload_dataset_to_modal_volume,
    upload_to_modal_volume,
)
from aegis.ingestion.keyframe import KeyframeDecision, KeyframeSelector
from aegis.ingestion.live_handoff import (
    PromotionResult,
    find_latest_live_session,
    promote_live_session,
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
    "BufferedFrame",
    "ContractError",
    "DecodedFrame",
    "FrameBuffer",
    "FrameSource",
    "KeyframeDecision",
    "KeyframeSelector",
    "LiveIngestionConfig",
    "LiveIngestionResult",
    "LiveSessionWriter",
    "OpenCVMjpegSource",
    "PromotionResult",
    "download_file",
    "find_latest_live_session",
    "ingest_live",
    "ingest_video",
    "load_session_manifest",
    "new_live_session_id",
    "preprocess_video",
    "probe_video",
    "promote_live_session",
    "read_live_index",
    "safe_url",
    "upload_dataset_to_modal_volume",
    "upload_to_modal_volume",
    "validate_frame_record",
    "validate_gap_record",
    "validate_normalized_metadata",
    "validate_pause_record",
    "validate_session_manifest",
    "validate_session_state",
]
