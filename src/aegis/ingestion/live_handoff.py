"""Promote a live capture session into canonical dataset artifacts (M1.1).

The batch pipeline expects ``frames/frame_XXXXXX.png`` plus ``metadata.json``.
A live session stores JPEGs, an index, and capture timestamps. Promotion is the
explicit boundary between those two contracts: frames are re-encoded as PNGs,
capture timestamps are normalised to start at zero while remaining authoritative,
and the original session manifest is copied alongside the dataset.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from aegis.core.config import CameraConfig, VideoConfig
from aegis.core.paths import validate_dataset_id
from aegis.ingestion.contracts import (
    NORMALIZED_DATASET_SCHEMA_VERSION,
    RECORD_TYPE_FRAME,
    ContractError,
    load_session_manifest,
    read_live_index,
    validate_normalized_metadata,
    write_json_atomic,
)

_FRAME_GLOB = "frame_*.png"


@dataclass(frozen=True, slots=True)
class PromotionResult:
    """Summary of one live-session promotion."""

    dataset_id: str
    dataset_dir: Path
    session_id: str
    frame_count: int
    duration_sec: float
    gap_count: int
    pause_count: int
    resolution: tuple[int, int]


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ContractError("capture timestamp must include a timezone")
    return parsed


def _resize(image: Any, video: VideoConfig | None, source_size: tuple[int, int]) -> Any:
    if video is None or source_size == (video.width, video.height):
        return image
    import cv2

    return cv2.resize(image, (video.width, video.height), interpolation=cv2.INTER_AREA)


def _intrinsics(camera: CameraConfig | None, resolution: tuple[int, int]) -> Any:
    if camera is None or camera.intrinsics is None:
        return None
    source = camera.intrinsics_resolution or resolution
    scale_x = resolution[0] / source[0]
    scale_y = resolution[1] / source[1]
    values = [
        camera.intrinsics[0] * scale_x,
        camera.intrinsics[1] * scale_y,
        camera.intrinsics[2] * scale_x,
        camera.intrinsics[3] * scale_y,
    ]
    return values


def promote_live_session(
    session_dir: str | Path,
    *,
    dataset_id: str,
    data_root: str | Path = Path("data"),
    video: VideoConfig | None = None,
    camera: CameraConfig | None = None,
) -> PromotionResult:
    """Convert ``captures/<session>`` into ``data/<dataset_id>``.

    The destination must not already contain a batch video; promoting over one
    would silently mix two sources. Live-derived frame and metadata files are
    replaced atomically enough for a re-run (stale PNGs are removed first).
    """

    import cv2

    session_path = Path(session_dir)
    if not session_path.is_dir():
        raise FileNotFoundError(
            f"live session directory does not exist: {session_path}"
        )
    safe_id = validate_dataset_id(dataset_id)
    manifest = load_session_manifest(session_path)

    index_path = session_path / "index.jsonl"
    if not index_path.exists():
        raise ContractError(f"live session index is missing: {index_path}")
    records = [
        record
        for record in read_live_index(index_path)
        if record.get("record_type", RECORD_TYPE_FRAME) == RECORD_TYPE_FRAME
    ]
    if not records:
        raise ContractError(f"live session contains no frame records: {session_path}")

    records.sort(key=lambda record: int(record["sequence"]))
    sequences = [int(record["sequence"]) for record in records]
    if len(set(sequences)) != len(sequences):
        raise ContractError("live session contains duplicate frame sequences")

    dataset_dir = Path(data_root) / safe_id
    if (dataset_dir / "video.mp4").exists():
        raise ValueError(
            f"dataset {safe_id} already contains video.mp4; choose a new dataset_id"
        )
    frames_dir = dataset_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for stale in frames_dir.glob(_FRAME_GLOB):
        stale.unlink()

    first_image = cv2.imread(str(session_path / str(records[0]["frame_path"])))
    if first_image is None:
        raise ContractError(f"could not decode live frame: {records[0]['frame_path']}")
    source_height, source_width = first_image.shape[:2]
    target_resolution = (
        (video.width, video.height)
        if video is not None
        else (source_width, source_height)
    )

    origin = _timestamp(str(records[0]["capture_timestamp"]))
    metadata_frames: list[dict[str, Any]] = []
    timestamp_records: list[dict[str, Any]] = []
    output_bytes = 0
    previous_timestamp = 0.0

    for frame_id, record in enumerate(records):
        relative = Path(str(record["frame_path"]))
        image = cv2.imread(str(session_path / relative))
        if image is None:
            raise ContractError(f"could not decode live frame: {relative}")
        height, width = image.shape[:2]
        image = _resize(image, video, (width, height))
        filename = f"frame_{frame_id:06d}.png"
        output_path = frames_dir / filename
        if not cv2.imwrite(str(output_path), image):
            raise OSError(f"could not write promoted frame: {output_path}")
        output_bytes += output_path.stat().st_size

        captured = _timestamp(str(record["capture_timestamp"]))
        timestamp = max(previous_timestamp, (captured - origin).total_seconds())
        previous_timestamp = timestamp
        metadata_frames.append(
            {
                "frame_id": frame_id,
                "timestamp": round(timestamp, 6),
                "filename": filename,
                "sequence": int(record["sequence"]),
                "capture_timestamp": record["capture_timestamp"],
                "timestamp_source": record["timestamp_source"],
            }
        )
        timestamp_records.append(
            {
                "frame_id": frame_id,
                "sequence": int(record["sequence"]),
                "timestamp": round(timestamp, 6),
                "capture_timestamp": record["capture_timestamp"],
                "received_at": record.get("received_at"),
            }
        )

    duration = metadata_frames[-1]["timestamp"]
    sample_fps = float(manifest.get("sample_rate_target_hz", 1.0))
    source_fps = (
        round(max(0.0, (len(metadata_frames) - 1) / duration), 6)
        if duration > 0
        else sample_fps
    )
    timestamp_sources = sorted({str(record["timestamp_source"]) for record in records})
    gaps = list(manifest.get("gaps", []))
    pauses = list(manifest.get("pauses", []))
    intrinsics = _intrinsics(camera, target_resolution)

    metadata: dict[str, Any] = {
        "schema_version": NORMALIZED_DATASET_SCHEMA_VERSION,
        "dataset_id": safe_id,
        "source_video": None,
        "preprocess_source": "live_session",
        "live_session_id": str(manifest["session_id"]),
        "live_session_dir": str(session_path),
        "source_fps": source_fps,
        "source_frame_count": len(records),
        "source_resolution": [source_width, source_height],
        "sample_fps": sample_fps,
        "resolution": [target_resolution[0], target_resolution[1]],
        "frame_count": len(metadata_frames),
        "duration_sec": duration,
        "timebase": "capture",
        "authoritative_timestamp_field": "capture_timestamp",
        "timestamp_source": (
            timestamp_sources[0] if len(timestamp_sources) == 1 else "mixed"
        ),
        "frames": metadata_frames,
        "intrinsics": intrinsics,
        "calibration_values": intrinsics,
        "calibration_source": (
            "config"
            if camera is not None and camera.intrinsics is not None
            else "unavailable"
        ),
        "calibration_path": None,
        "gaps": gaps,
        "gap_count": len(gaps),
        "pauses": pauses,
        "pause_count": len(pauses),
        "keyframe_selection": manifest.get("keyframe_selection", {"enabled": False}),
    }
    validate_normalized_metadata(metadata)

    source_metadata = {
        "dataset_id": safe_id,
        "source": f"live_session:{manifest['session_id']}",
        "source_url": manifest.get("source_url"),
        "task": f"Live egocentric capture {manifest['session_id']}",
        "duration_seconds": round(duration, 6),
        "fps": source_fps,
        "resolution": [target_resolution[0], target_resolution[1]],
        "frame_count": len(metadata_frames),
        "size_mb": round(output_bytes / (1024**2), 3),
        "preset": None,
        "capture_source_id": manifest.get("source_id"),
        "session_status": manifest.get("status"),
        "timestamp_source": metadata["timestamp_source"],
    }
    live_timestamps = {
        "schema_version": NORMALIZED_DATASET_SCHEMA_VERSION,
        "session_id": manifest["session_id"],
        "timebase": "capture",
        "origin": records[0]["capture_timestamp"],
        "authoritative_timestamp_field": "capture_timestamp",
        "timestamps": timestamp_records,
    }

    write_json_atomic(dataset_dir / "metadata.json", metadata)
    write_json_atomic(dataset_dir / "source_metadata.json", source_metadata)
    write_json_atomic(dataset_dir / "live_session.json", manifest)
    write_json_atomic(dataset_dir / "live_timestamps.json", live_timestamps)

    return PromotionResult(
        dataset_id=safe_id,
        dataset_dir=dataset_dir,
        session_id=str(manifest["session_id"]),
        frame_count=len(metadata_frames),
        duration_sec=duration,
        gap_count=len(gaps),
        pause_count=len(pauses),
        resolution=(int(target_resolution[0]), int(target_resolution[1])),
    )


def find_latest_live_session(
    output_root: str | Path = Path("captures"),
) -> Path | None:
    """Return the most recently modified resumable camera session directory."""

    root = Path(output_root)
    if not root.is_dir():
        return None
    candidates = [
        child
        for child in root.iterdir()
        if child.is_dir()
        and (
            (child / "session.json").exists() or (child / "session_state.json").exists()
        )
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def dataset_manifest_summary(session_dir: str | Path) -> dict[str, Any]:
    """Small JSON-serialisable summary used by the CLI and docs."""

    manifest = load_session_manifest(Path(session_dir))
    return {
        "session_id": manifest["session_id"],
        "status": manifest["status"],
        "started_at": manifest["started_at"],
        "ended_at": manifest.get("ended_at"),
        "frame_count": manifest.get(
            "frame_count", manifest.get("emitted_frame_count", 0)
        ),
        "gap_count": manifest.get("gap_count", 0),
        "pause_count": manifest.get("pause_count", 0),
    }


def copy_session_manifest(session_dir: str | Path, destination: Path) -> None:
    """Copy ``session.json`` without mutating the original capture."""

    manifest = load_session_manifest(Path(session_dir))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def reset_live_dataset(dataset_dir: str | Path) -> None:
    """Remove promoted live artifacts so a session can be re-promoted."""

    frames_dir = Path(dataset_dir) / "frames"
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
