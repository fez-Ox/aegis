"""Implementation of the remote Aegis Phase 1 workers.

Every function in this module is called by a Modal Function. Heavy imports are
kept inside the relevant worker so importing the local orchestration module
never initializes CUDA, OpenCV, or a model.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from aegis.core.config import RuntimeConfig
from aegis.core.models import BoundingBox3D
from aegis.core.paths import (
    DatasetPaths,
    dataset_paths,
)
from aegis.ingestion.contracts import validate_normalized_metadata
from aegis.ingestion.video import preprocess_video as preprocess_video_file


def _config(raw_config: Mapping[str, Any]) -> RuntimeConfig:

    return RuntimeConfig.from_mapping(raw_config)


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise TypeError(f"expected a JSON object: {path}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _require_metadata(paths: DatasetPaths) -> dict[str, Any]:
    if not paths.metadata.exists():
        raise FileNotFoundError(
            f"metadata is missing: run the preprocess stage before using {paths.root}"
        )
    return _read_json(paths.metadata)


def _record_benchmark_stats(
    paths: DatasetPaths, dataset_id: str, stage: str, stats: Mapping[str, Any]
) -> None:
    """Record execution duration, VRAM, and metrics to benchmark_stats.json."""
    current: dict[str, Any] = {
        "schema_version": 1,
        "dataset_id": dataset_id,
        "stages": {},
    }
    if paths.benchmark_stats.exists():
        try:
            current = _read_json(paths.benchmark_stats)
        except (ValueError, TypeError, OSError):
            current = {"schema_version": 1, "dataset_id": dataset_id, "stages": {}}

    stages = current.setdefault("stages", {})
    stages[stage] = dict(stats)

    total_runtime = sum(
        float(s.get("elapsed_seconds", 0.0))
        for s in stages.values()
        if isinstance(s, dict)
    )
    current["total_pipeline_seconds"] = round(total_runtime, 2)
    _write_json(paths.benchmark_stats, current)


def _clear_downstream_artifacts(paths: DatasetPaths) -> None:
    """Remove artifacts derived from a previous run, keeping frames/metadata."""

    for stale_file in (
        paths.poses,
        paths.pointcloud_npz,
        paths.pointcloud_ply,
        paths.pointcloud_metadata,
        paths.pointmaps_npz,
        paths.pointmaps_index,
        paths.gravity,
        paths.objects_json,
        paths.events_json,
        paths.rerun_recording,
        paths.viewer_manifest,
        paths.benchmark_stats,
        paths.objects_json.parent / "r4d_scene_graph.json",
        paths.objects_json.parent / "spatial_memory_graph.json",
        paths.objects_json.parent / "r4d_timeline.json",
    ):
        if stale_file.exists():
            stale_file.unlink()
    if paths.pointmaps_dir.exists():
        shutil.rmtree(paths.pointmaps_dir)
    evidence_dir = paths.objects_json.parent / "evidence"
    if evidence_dir.exists():
        shutil.rmtree(evidence_dir)


def _live_dataset_metadata(paths: DatasetPaths) -> dict[str, Any] | None:
    """Return validated live-promoted metadata, or ``None`` for a batch video."""

    if not paths.metadata.exists():
        return None
    try:
        candidate = _read_json(paths.metadata)
    except (ValueError, TypeError, OSError):
        # A corrupt metadata file is recreated by the normal preprocess path.
        return None
    if candidate.get("preprocess_source") != "live_session":
        return None
    metadata = validate_normalized_metadata(candidate)
    missing = [
        str(frame["filename"])
        for frame in metadata["frames"]
        if not (paths.frames / str(frame["filename"])).is_file()
    ]
    if missing:
        preview = ", ".join(missing[:5])
        raise FileNotFoundError(
            f"live dataset frames are missing ({len(missing)}): {preview}"
        )
    return metadata


def _wallclock_by_frame(
    paths: DatasetPaths, frame_records: Sequence[Mapping[str, Any]]
) -> tuple[dict[int, str], str]:
    """Absolute capture time per frame, and where it came from.

    Live datasets carry ``capture_timestamp`` per frame. Batch videos use
    ``recorded_at`` from ``source_metadata.json`` plus the frame offset when
    the operator supplied it. Otherwise no wall-clock time exists.
    """

    from aegis.core.timeutil import shift_iso, to_utc_iso

    captured = {
        int(rec["frame_id"]): to_utc_iso(str(rec["capture_timestamp"]))
        for rec in frame_records
        if rec.get("capture_timestamp")
    }
    if captured and len(captured) == len(frame_records):
        return captured, "capture"
    recorded_at = None
    if paths.source_metadata.exists():
        try:
            recorded_at = _read_json(paths.source_metadata).get("recorded_at")
        except (ValueError, TypeError, OSError):
            recorded_at = None
    if recorded_at:
        return (
            {
                int(rec["frame_id"]): shift_iso(
                    str(recorded_at), float(rec["timestamp"])
                )
                for rec in frame_records
            },
            "recorded_at",
        )
    return {}, "none"


def run_preprocess(dataset_id: str, raw_config: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a video, or accept a pre-materialized live dataset."""

    t0 = time.perf_counter()
    config = _config(raw_config)
    paths = dataset_paths(config, dataset_id)
    live_metadata = _live_dataset_metadata(paths)
    _clear_downstream_artifacts(paths)

    if live_metadata is None:
        metadata = preprocess_video_file(
            paths.input_video,
            paths.frames,
            paths.metadata,
            paths.calibration_normalized,
            config.video,
            config.camera,
            dataset_id=dataset_id,
        )
        preprocess_source = "source_video"
    else:
        metadata = live_metadata
        preprocess_source = "live_session"

    elapsed = time.perf_counter() - t0
    frame_count = int(metadata["frame_count"])
    fps = round(frame_count / max(elapsed, 0.001), 1)

    stage_result = {
        "stage": "preprocess",
        "dataset_id": dataset_id,
        "frame_count": frame_count,
        "elapsed_seconds": round(elapsed, 2),
        "throughput_fps": fps,
        "preprocess_source": preprocess_source,
        "timebase": metadata.get("timebase", "source_video"),
        "live_session_id": metadata.get("live_session_id"),
        "gap_count": int(metadata.get("gap_count", 0)),
        "metadata": str(paths.metadata),
        "frames": str(paths.frames),
        "calibration": str(paths.calibration_normalized)
        if metadata.get("calibration_values") is not None
        else None,
    }
    _record_benchmark_stats(paths, dataset_id, "preprocess", stage_result)
    return stage_result


def _write_ply(path: Path, points: np.ndarray, colors: np.ndarray) -> None:
    """Binary little-endian PLY (x, y, z as float32; red, green, blue as uint8)."""

    if points.shape != (len(colors), 3):
        raise ValueError("point and color arrays have incompatible shapes")
    vertices = np.empty(
        len(points),
        dtype=[
            ("x", "<f4"),
            ("y", "<f4"),
            ("z", "<f4"),
            ("red", "u1"),
            ("green", "u1"),
            ("blue", "u1"),
        ],
    )
    vertices["x"], vertices["y"], vertices["z"] = points.astype(np.float32).T
    rgb = np.asarray(colors).astype(np.uint8)
    vertices["red"], vertices["green"], vertices["blue"] = rgb.T
    header = (
        "ply\nformat binary_little_endian 1.0\n"
        f"element vertex {len(points)}\n"
        "property float x\nproperty float y\nproperty float z\n"
        "property uchar red\nproperty uchar green\nproperty uchar blue\n"
        "end_header\n"
    )
    with path.open("wb") as handle:
        handle.write(header.encode("ascii"))
        vertices.tofile(handle)


def write_pointmaps(
    paths: DatasetPaths,
    keyframe_ids: Sequence[int],
    pointmaps: np.ndarray,
    confmaps: np.ndarray,
) -> None:
    """One compressed file per keyframe, so readers never load them all."""

    if paths.pointmaps_dir.exists():
        shutil.rmtree(paths.pointmaps_dir)
    paths.pointmaps_dir.mkdir(parents=True, exist_ok=True)
    for frame_id, points, conf in zip(keyframe_ids, pointmaps, confmaps, strict=True):
        np.savez_compressed(
            paths.pointmaps_dir / f"{int(frame_id)}.npz",
            points=points.astype(np.float32),
            conf=conf.astype(np.float32),
        )
    _write_json(
        paths.pointmaps_index,
        {"schema_version": 1, "keyframe_ids": [int(f) for f in keyframe_ids]},
    )


class PointmapReader:
    """Per-keyframe pointmaps; falls back to the legacy single ``.npz``."""

    def __init__(self, paths: DatasetPaths) -> None:
        self.paths = paths
        if paths.pointmaps_index.exists():
            self.keyframe_ids = [
                int(f) for f in _read_json(paths.pointmaps_index)["keyframe_ids"]
            ]
            self._legacy = None
        elif paths.pointmaps_npz.exists():
            data = np.load(paths.pointmaps_npz)
            self.keyframe_ids = [int(f) for f in data["keyframe_ids"].tolist()]
            self._legacy = data
        else:
            raise FileNotFoundError(
                f"pointmaps are missing; run the vggt stage first: {paths.pointmaps_dir}"
            )
        self._index = {fid: i for i, fid in enumerate(self.keyframe_ids)}

    def __contains__(self, frame_id: int) -> bool:
        return int(frame_id) in self._index

    def get(self, frame_id: int) -> tuple[np.ndarray, np.ndarray]:
        if self._legacy is not None:
            index = self._index[int(frame_id)]
            return self._legacy["pointmaps"][index], self._legacy["confmaps"][index]
        with np.load(self.paths.pointmaps_dir / f"{int(frame_id)}.npz") as data:
            return data["points"], data["conf"]


def run_vggt(
    dataset_id: str, raw_config: Mapping[str, Any], *, model: Any = None
) -> dict[str, Any]:
    """Execute VGGT-Ω feed-forward 3D reconstruction on keyframes."""

    t0 = time.perf_counter()
    config = _config(raw_config)
    paths = dataset_paths(config, dataset_id)
    metadata = _require_metadata(paths)
    frames = metadata.get("frames", [])
    if not frames:
        raise ValueError("metadata contains no frames")

    # Sample keyframes with stride
    keyframe_records = frames[:: config.vggt.keyframe_stride]
    if len(keyframe_records) < 2:
        keyframe_records = frames[: min(len(frames), 2)]
    if len(keyframe_records) > config.vggt.max_keyframes:
        raise ValueError(
            f"{len(keyframe_records)} keyframes exceed vggt.max_keyframes="
            f"{config.vggt.max_keyframes}; lower video.sample_fps, raise "
            "vggt.keyframe_stride, or process the capture with --segment-frames"
        )
    image_paths = [paths.frames / str(rec["filename"]) for rec in keyframe_records]

    gpu_device = "CPU"
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
            gpu_device = torch.cuda.get_device_name(0)
    except (ImportError, RuntimeError):
        pass

    from aegis.geometry.vggt_runner import run_vggt_reconstruction

    hf_token = (
        raw_config.get("hf_token")
        or os.getenv("HF_TOKEN")
        or os.getenv("HUGGING_FACE_HUB_TOKEN")
        or os.getenv("hf_token")
    )
    rec_result = run_vggt_reconstruction(
        image_paths, config.vggt, hf_token=hf_token, model=model
    )

    # Save pointmaps and confidence maps (one file per keyframe)
    paths.pointmaps_npz.parent.mkdir(parents=True, exist_ok=True)
    write_pointmaps(
        paths,
        [int(rec["frame_id"]) for rec in keyframe_records],
        rec_result["pointmaps"],
        rec_result["confmaps"],
    )

    # Save global point cloud
    paths.pointcloud_npz.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        paths.pointcloud_npz,
        points=rec_result["global_points"],
        colors=rec_result["global_colors"],
    )
    _write_ply(
        paths.pointcloud_ply, rec_result["global_points"], rec_result["global_colors"]
    )

    # Save camera poses
    pose_source = "synthetic" if rec_result.get("synthetic", False) else "VGGT-Omega"
    pose_records: list[dict[str, Any]] = []
    poses = rec_result["poses"]
    for matrix, rec in zip(poses, keyframe_records, strict=True):
        pose_records.append(
            {
                "frame_id": int(rec["frame_id"]),
                "timestamp": float(rec["timestamp"]),
                "filename": str(rec["filename"]),
                "matrix": matrix.tolist(),
                "convention": "T_world_camera",
                "source": pose_source,
            }
        )

    _write_json(
        paths.poses,
        {
            "schema_version": 1,
            "dataset_id": dataset_id,
            "source": pose_source,
            "convention": "T_world_camera",
            "frame_count": len(pose_records),
            "poses": pose_records,
        },
    )

    # Gravity frame (up direction + floor height), stored beside the raw
    # coordinates; the coordinates themselves are never rotated.
    from aegis.geometry.gravity import GravityFrame, estimate_gravity

    if config.memory.gravity.enabled and not rec_result.get("synthetic", False):
        gravity = estimate_gravity(
            rec_result["global_points"],
            poses[:, :3, 3],
            poses[:, :3, :3],
            iterations=config.memory.gravity.ransac_iterations,
        )
    else:
        gravity = GravityFrame.assumed()
    _write_json(
        paths.gravity,
        {"schema_version": 1, "dataset_id": dataset_id, **gravity.as_dict()},
    )

    _write_json(
        paths.pointcloud_metadata,
        {
            "schema_version": 1,
            "dataset_id": dataset_id,
            "source": "VGGT-Omega",
            "keyframe_count": len(keyframe_records),
            "point_count": len(rec_result["global_points"]),
            "confidence_threshold": 1.0,
        },
    )

    elapsed = time.perf_counter() - t0
    peak_vram_gb = 0.0
    reserved_vram_gb = 0.0
    try:
        import torch

        if torch.cuda.is_available():
            peak_vram_gb = round(torch.cuda.max_memory_allocated() / (1024**3), 3)
            reserved_vram_gb = round(torch.cuda.max_memory_reserved() / (1024**3), 3)
    except (ImportError, RuntimeError):
        pass

    kf_fps = round(len(keyframe_records) / max(elapsed, 0.001), 2)
    stage_result = {
        "stage": "vggt",
        "dataset_id": dataset_id,
        "model_id": config.vggt.model_id,
        "gpu_device": gpu_device,
        "keyframe_count": len(keyframe_records),
        "point_count": len(rec_result["global_points"]),
        "elapsed_seconds": round(elapsed, 2),
        "peak_vram_gb": peak_vram_gb,
        "reserved_vram_gb": reserved_vram_gb,
        "throughput_fps": kf_fps,
        "pointcloud": str(paths.pointcloud_ply),
        "poses": str(paths.poses),
        "pose_source": pose_source,
        "gravity_source": gravity.source,
        "gravity_confidence": round(gravity.confidence, 3),
        "camera_height": gravity.camera_height,
    }
    _record_benchmark_stats(paths, dataset_id, "vggt", stage_result)
    return stage_result


def run_detect_and_lift(
    dataset_id: str, raw_config: Mapping[str, Any], *, models: Any = None
) -> dict[str, Any]:
    """Run open-vocabulary object perception and lift 2D detections to 3D bounding boxes."""

    t0 = time.perf_counter()
    config = _config(raw_config)
    paths = dataset_paths(config, dataset_id)
    metadata = _require_metadata(paths)
    pointmap_reader = PointmapReader(paths)
    frames = metadata.get("frames", [])
    keyframe_ids = pointmap_reader.keyframe_ids

    keyframe_id_set = set(keyframe_ids)
    keyframe_records = [f for f in frames if int(f["frame_id"]) in keyframe_id_set]

    gpu_device = "CPU"
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
            gpu_device = torch.cuda.get_device_name(0)
    except (ImportError, RuntimeError):
        pass

    from aegis.geometry.lifting import (
        compute_motion_trails,
        evaluate_spatial_containment_and_states,
        lift_detection_to_3d,
        serialize_boxes_3d,
    )
    from aegis.perception.detector import detect_and_track_objects

    weights_dir = Path(config.storage.model_mount) / "yolo"
    track_embeddings: dict[int, tuple[float, ...]] = {}
    detections_2d = detect_and_track_objects(
        keyframe_records,
        paths.frames,
        config.perception,
        sam2_config=config.sam2,
        weights_dir=weights_dir,
        vocabulary=config.vocab(),
        models=models,
        track_embeddings=track_embeddings,
    )

    frame_res = tuple(metadata["resolution"])
    from aegis.geometry.gravity import GravityFrame

    gravity = (
        GravityFrame.from_dict(_read_json(paths.gravity))
        if paths.gravity.exists()
        else GravityFrame.assumed()
    )
    gravity_cfg = config.memory.gravity
    unit = gravity.unit(gravity_cfg.assumed_camera_height, gravity_cfg.min_confidence)
    vocabulary = config.vocab()
    raw_lifted_boxes: list[BoundingBox3D] = []
    masks_generated = sum(1 for det in detections_2d if det.mask is not None)

    by_frame: dict[int, list[Any]] = {}
    for det in detections_2d:
        if det.frame_id in pointmap_reader:
            by_frame.setdefault(int(det.frame_id), []).append(det)
    # One pointmap in memory at a time.
    for frame_id, frame_detections in sorted(by_frame.items()):
        pm, cm = pointmap_reader.get(frame_id)
        for det in frame_detections:
            box_3d = lift_detection_to_3d(
                det,
                pm,
                mask=det.mask,
                confmap=cm,
                min_conf_thr=0.01,
                min_points=config.perception.min_points_in_box,
                frame_size=(int(frame_res[0]), int(frame_res[1])),
                gravity=gravity,
                vocabulary=vocabulary,
                unit=unit,
            )
            if box_3d is not None:
                raw_lifted_boxes.append(box_3d)
        del pm, cm

    # Layer 2: Evaluate 3D spatial containment and dynamic motion states
    lifted_boxes = evaluate_spatial_containment_and_states(
        raw_lifted_boxes,
        smoothing_alpha=config.perception.track_smoothing,
        vocabulary=vocabulary,
        unit=unit,
        hand_distance=config.perception.hand_contact_max_distance,
    )
    motion_trails = compute_motion_trails(lifted_boxes)

    # Build R4DSG Relative 4D Scene Graph Memory
    from aegis.memory.scene_graph import build_relative_4d_scene_graph

    all_kf_ids = [int(f["frame_id"]) for f in keyframe_records]
    all_ts = [float(f["timestamp"]) for f in keyframe_records]

    pose_records = None
    if paths.poses.exists():
        pose_data = _read_json(paths.poses)
        pose_records = pose_data.get("poses", [])

    wallclock_by_frame, time_source = _wallclock_by_frame(paths, keyframe_records)
    scene_graph = build_relative_4d_scene_graph(
        lifted_boxes,
        all_kf_ids,
        all_ts,
        camera_poses=pose_records,
        estimate_rooms=config.memory.rooms.enabled,
        zone_link_radius=config.memory.rooms.zone_link_radius,
        min_zone_keyframes=config.memory.rooms.min_zone_keyframes,
        vocabulary=vocabulary,
        gravity=gravity,
        wallclock_by_frame=wallclock_by_frame,
        settings=config.memory.build,
        assumed_camera_height=gravity_cfg.assumed_camera_height,
        min_gravity_confidence=gravity_cfg.min_confidence,
    )
    scene_graph.session.update(dataset_id=dataset_id, time_source=time_source)

    paths.objects_json.parent.mkdir(parents=True, exist_ok=True)
    _write_json(
        paths.objects_json,
        {
            "schema_version": 2,
            "dataset_id": dataset_id,
            "gravity": gravity.as_dict(),
            "total_detections_2d": len(detections_2d),
            "total_boxes_3d": len(lifted_boxes),
            "boxes_3d": serialize_boxes_3d(lifted_boxes),
            "motion_trails": {str(k): v for k, v in motion_trails.items()},
        },
    )

    evidence_dir = paths.objects_json.parent / "evidence"
    if evidence_dir.exists():
        shutil.rmtree(evidence_dir)
    crops_written = 0
    if config.memory.evidence.enabled:
        from aegis.memory.evidence import write_run_crops

        crops_written = write_run_crops(
            scene_graph.state_runs,
            paths.frames,
            {int(f["frame_id"]): str(f["filename"]) for f in frames},
            evidence_dir,
            max_side=config.memory.evidence.max_side,
            quality=config.memory.evidence.quality,
        )

    if track_embeddings:
        ids = sorted(track_embeddings)
        np.savez_compressed(
            paths.objects_json.parent / "track_embeddings.npz",
            track_ids=np.asarray(ids, dtype=np.int64),
            embeddings=np.asarray([track_embeddings[i] for i in ids], dtype=np.float32),
        )

    r4d_path = paths.objects_json.parent / "r4d_scene_graph.json"
    scene_graph_data = scene_graph.as_dict()
    # Store ownership in the artifact so the API can reject a stale graph
    # copied from another video instead of serving cross-scene memories.
    scene_graph_data["dataset_id"] = dataset_id
    _write_json(r4d_path, scene_graph_data)

    # The per-keyframe view grows with video length; it exists only for the
    # Rerun recording and is never downloaded or served.
    timeline_path = paths.objects_json.parent / "r4d_timeline.json"
    _write_json(
        timeline_path,
        {
            "schema_version": 1,
            "dataset_id": dataset_id,
            "timeline": scene_graph.timeline_dict(),
        },
    )

    _write_json(
        paths.events_json,
        {
            "schema_version": 1,
            "dataset_id": dataset_id,
            "events": scene_graph.events,
        },
    )

    # Small manifest pointing at the artifacts (no embedded copies).
    memory_graph_path = paths.objects_json.parent / "spatial_memory_graph.json"
    _write_json(
        memory_graph_path,
        {
            "schema_version": 2,
            "dataset_id": dataset_id,
            "pointcloud_file": paths.pointcloud_ply.name,
            "objects_file": paths.objects_json.name,
            "scene_graph_file": r4d_path.name,
            "timeline_file": timeline_path.name,
            "events_file": paths.events_json.name,
            "room_count": len(scene_graph.rooms),
            "anchor_count": len(scene_graph.anchors),
            "instance_count": len(scene_graph.latest_states),
            "state_run_count": len(scene_graph.state_runs),
            "event_count": len(scene_graph.events),
            "total_boxes_3d": len(lifted_boxes),
        },
    )

    # Pointmaps are transient (~4 MB per keyframe): drop them once lifted.
    if not config.vggt.keep_pointmaps:
        if paths.pointmaps_dir.exists():
            shutil.rmtree(paths.pointmaps_dir)
        paths.pointmaps_index.unlink(missing_ok=True)
        paths.pointmaps_npz.unlink(missing_ok=True)

    elapsed = time.perf_counter() - t0
    peak_vram_gb = 0.0
    reserved_vram_gb = 0.0
    try:
        import torch

        if torch.cuda.is_available():
            peak_vram_gb = round(torch.cuda.max_memory_allocated() / (1024**3), 3)
            reserved_vram_gb = round(torch.cuda.max_memory_reserved() / (1024**3), 3)
    except (ImportError, RuntimeError):
        pass

    det_fps = round(len(keyframe_records) / max(elapsed, 0.001), 2)
    stage_result = {
        "stage": "detect_and_lift",
        "dataset_id": dataset_id,
        "detector_model": config.perception.detector_model,
        "sam2_model": config.sam2.model_id if config.sam2 else None,
        "gpu_device": gpu_device,
        "keyframe_count": len(keyframe_records),
        "detections_2d": len(detections_2d),
        "sam2_masks_generated": masks_generated,
        "boxes_3d": len(lifted_boxes),
        "tracks": len(motion_trails),
        "elapsed_seconds": round(elapsed, 2),
        "peak_vram_gb": peak_vram_gb,
        "reserved_vram_gb": reserved_vram_gb,
        "throughput_fps": det_fps,
        "objects_file": str(paths.objects_json),
        "r4d_scene_graph": str(r4d_path),
        "events": len(scene_graph.events),
        "evidence_crops": crops_written,
        "events_file": str(paths.events_json),
        "spatial_memory_graph": str(memory_graph_path),
    }
    _record_benchmark_stats(paths, dataset_id, "detect_and_lift", stage_result)
    return stage_result


def run_rerun(dataset_id: str, raw_config: Mapping[str, Any]) -> dict[str, Any]:
    """Build the Rerun recording (see :mod:`aegis.visualization.rerun_scene`)."""

    from aegis.visualization.rerun_scene import run_rerun as build_recording

    return build_recording(dataset_id, raw_config)
