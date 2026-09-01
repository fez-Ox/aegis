"""Canonical paths for data and artifacts on the mounted Modal Volumes."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from aegis.poc.core.config import RuntimeConfig

_DATASET_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


@dataclass(frozen=True, slots=True)
class DatasetPaths:
    """All paths belonging to one dataset inside the data Volume."""

    root: Path
    input_video: Path
    calibration_input: Path
    calibration_normalized: Path
    frames: Path
    metadata: Path
    depth: Path
    depth_manifest: Path
    poses: Path
    pointcloud_npz: Path
    pointcloud_ply: Path
    pointcloud_metadata: Path
    pointmaps_npz: Path
    objects_json: Path
    rerun_recording: Path
    viewer_manifest: Path


def validate_dataset_id(dataset_id: str) -> str:
    """Validate a dataset identifier before using it in a mounted path."""

    if not _DATASET_ID.fullmatch(dataset_id):
        raise ValueError(
            "dataset_id must contain only letters, numbers, '.', '_' or '-'; "
            "path separators are not allowed"
        )
    return dataset_id


def _dataset_file(root: Path, filename: str) -> Path:
    path = Path(filename)
    if path.is_absolute():
        return path
    return root / path


def dataset_paths(config: RuntimeConfig, dataset_id: str) -> DatasetPaths:
    """Resolve the canonical input and output paths for ``dataset_id``."""

    safe_id = validate_dataset_id(dataset_id)
    root = Path(config.storage.data_mount) / safe_id
    outputs = root / "outputs"
    geometry = outputs / "geometry"
    objects = outputs / "objects"
    viewer = outputs / "viewer"
    return DatasetPaths(
        root=root,
        input_video=_dataset_file(root, config.video.filename),
        calibration_input=_dataset_file(root, config.camera.calibration_filename),
        calibration_normalized=root / "calib_normalized.txt",
        frames=root / "frames",
        metadata=root / "metadata.json",
        depth=outputs / "depth",
        depth_manifest=outputs / "depth_manifest.json",
        poses=geometry / "poses.json",
        pointcloud_npz=geometry / "pointcloud.npz",
        pointcloud_ply=geometry / "pointcloud.ply",
        pointcloud_metadata=geometry / "pointcloud_metadata.json",
        pointmaps_npz=geometry / "pointmaps.npz",
        objects_json=objects / "detected_objects_3d.json",
        rerun_recording=viewer / "demo.rrd",
        viewer_manifest=viewer / "manifest.json",
    )


def model_paths(config: RuntimeConfig) -> tuple[Path, Path, Path]:
    """Return model-cache root, Hugging Face cache, and DROID weight paths."""

    root = Path(config.storage.model_mount)
    hf_cache = root / "huggingface"
    droid_weights = root / "droid" / config.pose.weights_filename
    return root, hf_cache, droid_weights


def dust3r_model_path(config: RuntimeConfig) -> Path:
    """Return the DUSt3R checkpoint path in the model Volume."""

    return (
        Path(config.storage.model_mount)
        / "dust3r"
        / config.dust3r.weights_filename
    )


def calibration_model_path(config: RuntimeConfig) -> Path:
    """Return the self-calibration checkpoint path in the model Volume."""

    return (
        Path(config.storage.model_mount)
        / "droid-calib"
        / config.camera.self_calibration_weights_filename
    )

