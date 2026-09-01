"""Deterministic video normalization executed inside Modal."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from aegis.poc.core.config import CameraConfig, VideoConfig


def _read_calibration(path: Path) -> list[float]:
    values = [float(value) for value in path.read_text(encoding="utf-8").split()]
    if len(values) < 4:
        raise ValueError(f"calibration file must contain at least four values: {path}")
    return values


def _scaled_calibration(
    values: Sequence[float],
    *,
    source_width: int,
    source_height: int,
    target_width: int,
    target_height: int,
) -> list[float]:
    scale_x = target_width / source_width
    scale_y = target_height / source_height
    normalized = [
        float(values[0]) * scale_x,
        float(values[1]) * scale_y,
        float(values[2]) * scale_x,
        float(values[3]) * scale_y,
    ]
    normalized.extend(float(value) for value in values[4:])
    return normalized


def _resolve_calibration(
    root: Path,
    camera: CameraConfig,
    *,
    source_width: int,
    source_height: int,
    target_width: int,
    target_height: int,
) -> tuple[list[float] | None, str]:
    if camera.intrinsics is not None:
        calibration = list(camera.intrinsics)
        calibration_resolution = camera.intrinsics_resolution or (
            source_width,
            source_height,
        )
        normalized = _scaled_calibration(
            calibration,
            source_width=calibration_resolution[0],
            source_height=calibration_resolution[1],
            target_width=target_width,
            target_height=target_height,
        )
        return normalized, "config"

    input_path = root / camera.calibration_filename
    if input_path.exists():
        values = _read_calibration(input_path)
        normalized = _scaled_calibration(
            values,
            source_width=source_width,
            source_height=source_height,
            target_width=target_width,
            target_height=target_height,
        )
        return normalized, str(input_path)

    if camera.allow_approximate:
        focal = 0.9 * max(target_width, target_height)
        return [focal, focal, target_width / 2, target_height / 2], "approximate"

    return None, "missing"


def preprocess_video(
    input_path: Path,
    output_dir: Path,
    metadata_path: Path,
    calibration_output: Path,
    video: VideoConfig,
    camera: CameraConfig,
    *,
    dataset_id: str,
) -> dict[str, Any]:
    """Sample and normalize a video, returning the generated metadata.

    The function intentionally contains no local fallback or model execution;
    callers run it from a Modal CPU worker so the weak development machine only
    submits the job.
    """

    import cv2

    if not input_path.exists():
        raise FileNotFoundError(
            f"input video does not exist in the mounted data Volume: {input_path}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    if calibration_output.exists():
        calibration_output.unlink()
    for stale_frame in output_dir.glob("frame_*.png"):
        stale_frame.unlink()

    capture = cv2.VideoCapture(str(input_path))
    if not capture.isOpened():
        raise RuntimeError(f"OpenCV could not open video: {input_path}")

    source_fps = float(capture.get(cv2.CAP_PROP_FPS))
    if source_fps <= 0:
        source_fps = 30.0
    source_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    source_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    source_frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if source_width <= 0 or source_height <= 0:
        capture.release()
        raise RuntimeError(f"video has invalid dimensions: {input_path}")

    frames: list[dict[str, Any]] = []
    source_index = 0
    next_sample_time = 0.0
    sample_period = 1.0 / video.sample_fps
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            timestamp = source_index / source_fps
            if timestamp + 1e-9 >= next_sample_time:
                normalized = cv2.resize(
                    frame,
                    (video.width, video.height),
                    interpolation=cv2.INTER_AREA,
                )
                frame_id = len(frames)
                filename = f"frame_{frame_id:06d}.png"
                frame_path = output_dir / filename
                if not cv2.imwrite(str(frame_path), normalized):
                    raise RuntimeError(
                        f"failed to write normalized frame: {frame_path}"
                    )
                frames.append(
                    {
                        "frame_id": frame_id,
                        "timestamp": round(timestamp, 6),
                        "filename": filename,
                    }
                )
                next_sample_time += sample_period
            source_index += 1
    finally:
        capture.release()

    if not frames:
        raise RuntimeError(f"video contained no decodable frames: {input_path}")

    normalized_calibration, calibration_source = _resolve_calibration(
        input_path.parent,
        camera,
        source_width=source_width,
        source_height=source_height,
        target_width=video.width,
        target_height=video.height,
    )
    if normalized_calibration is not None:
        calibration_output.parent.mkdir(parents=True, exist_ok=True)
        calibration_output.write_text(
            " ".join(f"{value:.10g}" for value in normalized_calibration) + "\n",
            encoding="utf-8",
        )

    metadata: dict[str, Any] = {
        "schema_version": 1,
        "dataset_id": dataset_id,
        "source_video": str(input_path),
        "source_fps": source_fps,
        "source_frame_count": source_frame_count,
        "source_resolution": [source_width, source_height],
        "sample_fps": video.sample_fps,
        "resolution": [video.width, video.height],
        "frame_count": len(frames),
        "duration_sec": frames[-1]["timestamp"],
        "frames": frames,
        "intrinsics": normalized_calibration[:4]
        if normalized_calibration is not None
        else None,
        "calibration_values": normalized_calibration,
        "calibration_source": calibration_source,
        "calibration_path": str(calibration_output)
        if normalized_calibration is not None
        else None,
    }
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return metadata
