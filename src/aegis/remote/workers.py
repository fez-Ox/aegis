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


def run_preprocess(dataset_id: str, raw_config: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a video and write frame metadata to the data Volume."""

    t0 = time.perf_counter()
    config = _config(raw_config)
    paths = dataset_paths(config, dataset_id)
    for stale_file in (
        paths.depth_manifest,
        paths.poses,
        paths.pointcloud_npz,
        paths.pointcloud_ply,
        paths.pointcloud_metadata,
        paths.pointmaps_npz,
        paths.objects_json,
        paths.events_json,
        paths.rerun_recording,
        paths.viewer_manifest,
        paths.benchmark_stats,
        paths.objects_json.parent / "r4d_scene_graph.json",
        paths.objects_json.parent / "spatial_memory_graph.json",
    ):
        if stale_file.exists():
            stale_file.unlink()
    if paths.depth.exists():
        shutil.rmtree(paths.depth)

    metadata = preprocess_video_file(
        paths.input_video,
        paths.frames,
        paths.metadata,
        paths.calibration_normalized,
        config.video,
        config.camera,
        dataset_id=dataset_id,
    )
    elapsed = time.perf_counter() - t0
    frame_count = int(metadata["frame_count"])
    fps = round(frame_count / max(elapsed, 0.001), 1)

    stage_result = {
        "stage": "preprocess",
        "dataset_id": dataset_id,
        "frame_count": frame_count,
        "elapsed_seconds": round(elapsed, 2),
        "throughput_fps": fps,
        "metadata": str(paths.metadata),
        "frames": str(paths.frames),
        "calibration": str(paths.calibration_normalized)
        if metadata["calibration_values"] is not None
        else None,
    }
    _record_benchmark_stats(paths, dataset_id, "preprocess", stage_result)
    return stage_result


def _write_ply(path: Path, points: np.ndarray, colors: np.ndarray) -> None:
    if points.shape != (len(colors), 3):
        raise ValueError("point and color arrays have incompatible shapes")
    with path.open("w", encoding="utf-8") as handle:
        handle.write("ply\nformat ascii 1.0\n")
        handle.write(f"element vertex {len(points)}\n")
        handle.write("property float x\nproperty float y\nproperty float z\n")
        handle.write("property uchar red\nproperty uchar green\nproperty uchar blue\n")
        handle.write("end_header\n")
        for point, color in zip(points, colors, strict=True):
            handle.write(
                f"{point[0]:.6f} {point[1]:.6f} {point[2]:.6f} "
                f"{int(color[0])} {int(color[1])} {int(color[2])}\n"
            )


def run_vggt(dataset_id: str, raw_config: Mapping[str, Any]) -> dict[str, Any]:
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
    rec_result = run_vggt_reconstruction(image_paths, config.vggt, hf_token=hf_token)

    # Save pointmaps and confidence maps
    paths.pointmaps_npz.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        paths.pointmaps_npz,
        pointmaps=rec_result["pointmaps"],
        confmaps=rec_result["confmaps"],
        keyframe_ids=np.array([int(rec["frame_id"]) for rec in keyframe_records]),
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
                "source": "VGGT-Omega",
            }
        )

    _write_json(
        paths.poses,
        {
            "schema_version": 1,
            "dataset_id": dataset_id,
            "source": "VGGT-Omega",
            "convention": "T_world_camera",
            "frame_count": len(pose_records),
            "poses": pose_records,
        },
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
    }
    _record_benchmark_stats(paths, dataset_id, "vggt", stage_result)
    return stage_result


# Backwards compatibility alias
run_dust3r = run_vggt


def run_detect_and_lift(
    dataset_id: str, raw_config: Mapping[str, Any]
) -> dict[str, Any]:
    """Run open-vocabulary object perception and lift 2D detections to 3D bounding boxes."""

    t0 = time.perf_counter()
    config = _config(raw_config)
    paths = dataset_paths(config, dataset_id)
    metadata = _require_metadata(paths)
    if not paths.pointmaps_npz.exists():
        raise FileNotFoundError(
            f"pointmaps artifact is missing; run dust3r/vggt reconstruction first: {paths.pointmaps_npz}"
        )

    frames = metadata.get("frames", [])
    data = np.load(paths.pointmaps_npz)
    pointmaps = data["pointmaps"]
    confmaps = data["confmaps"]
    keyframe_ids = data["keyframe_ids"].tolist()

    keyframe_id_set = set(keyframe_ids)
    keyframe_records = [f for f in frames if int(f["frame_id"]) in keyframe_id_set]
    keyframe_index_map = {int(kid): idx for idx, kid in enumerate(keyframe_ids)}

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
    detections_2d = detect_and_track_objects(
        keyframe_records,
        paths.frames,
        config.perception,
        sam2_config=config.sam2,
        weights_dir=weights_dir,
    )

    frame_res = tuple(
        metadata.get("resolution", (pointmaps[0].shape[1], pointmaps[0].shape[0]))
    )
    raw_lifted_boxes: list[BoundingBox3D] = []
    masks_generated = sum(1 for det in detections_2d if det.mask is not None)

    for det in detections_2d:
        kf_idx = keyframe_index_map.get(det.frame_id)
        if kf_idx is None:
            continue
        pm = pointmaps[kf_idx]
        cm = confmaps[kf_idx]
        box_3d = lift_detection_to_3d(
            det,
            pm,
            mask=det.mask,
            confmap=cm,
            min_conf_thr=0.01,
            min_points=config.perception.min_points_in_box,
            frame_size=(int(frame_res[0]), int(frame_res[1])),
        )
        if box_3d is not None:
            raw_lifted_boxes.append(box_3d)

    # Layer 2: Evaluate 3D spatial containment and dynamic motion states
    lifted_boxes = evaluate_spatial_containment_and_states(
        raw_lifted_boxes,
        smoothing_alpha=config.perception.track_smoothing,
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

    scene_graph = build_relative_4d_scene_graph(
        lifted_boxes, all_kf_ids, all_ts, camera_poses=pose_records
    )

    paths.objects_json.parent.mkdir(parents=True, exist_ok=True)
    _write_json(
        paths.objects_json,
        {
            "schema_version": 1,
            "dataset_id": dataset_id,
            "total_detections_2d": len(detections_2d),
            "total_boxes_3d": len(lifted_boxes),
            "boxes_3d": serialize_boxes_3d(lifted_boxes),
            "motion_trails": {str(k): v for k, v in motion_trails.items()},
        },
    )

    r4d_path = paths.objects_json.parent / "r4d_scene_graph.json"
    _write_json(r4d_path, scene_graph.as_dict())

    _write_json(
        paths.events_json,
        {
            "schema_version": 1,
            "dataset_id": dataset_id,
            "events": scene_graph.events,
        },
    )

    # Save Structured Spatial Memory Graph
    memory_graph_path = paths.objects_json.parent / "spatial_memory_graph.json"
    _write_json(
        memory_graph_path,
        {
            "schema_version": 1,
            "dataset_id": dataset_id,
            "layer_1": {
                "description": "Static Voxelized 3D Room Canvas",
                "pointcloud_file": str(paths.pointcloud_ply),
            },
            "layer_2": {
                "description": "R4DSG Persistent Object Tracker & Relational States",
                "total_instances": len(motion_trails),
                "total_boxes_3d": len(lifted_boxes),
                "objects": serialize_boxes_3d(lifted_boxes),
                "motion_trails": {str(k): v for k, v in motion_trails.items()},
                "r4d_scene_graph": scene_graph.as_dict(),
            },
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
        "events_file": str(paths.events_json),
        "spatial_memory_graph": str(memory_graph_path),
    }
    _record_benchmark_stats(paths, dataset_id, "detect_and_lift", stage_result)
    return stage_result


TRACK_PALETTE = [
    [34, 197, 94],  # Emerald Green
    [59, 130, 246],  # Vibrant Blue
    [239, 68, 68],  # Red
    [234, 179, 8],  # Amber
    [168, 85, 247],  # Purple
    [236, 72, 153],  # Pink
    [20, 184, 166],  # Teal
    [249, 115, 22],  # Orange
]


def _track_color(track_id: int) -> list[int]:
    return TRACK_PALETTE[(track_id - 1) % len(TRACK_PALETTE)]


def run_rerun(dataset_id: str, raw_config: Mapping[str, Any]) -> dict[str, Any]:
    """Create an offline Rerun recording containing video, geometry, 3D boxes, and motion trails."""

    t0 = time.perf_counter()
    config = _config(raw_config)
    paths = dataset_paths(config, dataset_id)
    metadata = _require_metadata(paths)
    if not paths.poses.exists():
        raise FileNotFoundError(f"pose artifact is missing: {paths.poses}")
    if not paths.pointcloud_npz.exists():
        raise FileNotFoundError(
            f"point-cloud artifact is missing: {paths.pointcloud_npz}"
        )

    import rerun as rr
    import rerun.blueprint as rrb

    pose_data = _read_json(paths.poses)
    pose_records = pose_data.get("poses", [])
    pose_by_frame = {int(record["frame_id"]): record for record in pose_records}
    pointcloud = np.load(paths.pointcloud_npz)
    points = pointcloud["points"]
    colors = pointcloud["colors"]
    trajectory = np.asarray(
        [
            np.asarray(record["matrix"], dtype=np.float32)[:3, 3]
            for record in pose_records
        ]
    )

    SCALE = 5.0

    def to_zup(pt: Sequence[float]) -> list[float]:
        return [float(pt[0]) * SCALE, float(pt[2]) * SCALE, -float(pt[1]) * SCALE]

    def to_zup_size(sz: Sequence[float]) -> list[float]:
        return [float(sz[0]) * SCALE, float(sz[2]) * SCALE, float(sz[1]) * SCALE]

    def to_zup_direction(direction: Sequence[float]) -> np.ndarray:
        return np.asarray(
            [float(direction[0]), float(direction[2]), -float(direction[1])],
            dtype=np.float64,
        )

    def quaternion_to_matrix(quaternion: Sequence[float]) -> np.ndarray:
        qx, qy, qz, qw = (float(value) for value in quaternion)
        norm = float(np.linalg.norm([qx, qy, qz, qw]))
        if norm <= 1e-8:
            return np.eye(3, dtype=np.float64)
        qx, qy, qz, qw = (value / norm for value in (qx, qy, qz, qw))
        return np.asarray(
            [
                [
                    1.0 - 2.0 * (qy * qy + qz * qz),
                    2.0 * (qx * qy - qz * qw),
                    2.0 * (qx * qz + qy * qw),
                ],
                [
                    2.0 * (qx * qy + qz * qw),
                    1.0 - 2.0 * (qx * qx + qz * qz),
                    2.0 * (qy * qz - qx * qw),
                ],
                [
                    2.0 * (qx * qz - qy * qw),
                    2.0 * (qy * qz + qx * qw),
                    1.0 - 2.0 * (qx * qx + qy * qy),
                ],
            ],
            dtype=np.float64,
        )

    def matrix_to_quaternion(matrix: np.ndarray) -> list[float]:
        trace = float(np.trace(matrix))
        if trace > 0.0:
            scale = np.sqrt(trace + 1.0) * 2.0
            qw = 0.25 * scale
            qx = (matrix[2, 1] - matrix[1, 2]) / scale
            qy = (matrix[0, 2] - matrix[2, 0]) / scale
            qz = (matrix[1, 0] - matrix[0, 1]) / scale
        elif matrix[0, 0] > matrix[1, 1] and matrix[0, 0] > matrix[2, 2]:
            scale = np.sqrt(1.0 + matrix[0, 0] - matrix[1, 1] - matrix[2, 2]) * 2.0
            qw = (matrix[2, 1] - matrix[1, 2]) / scale
            qx = 0.25 * scale
            qy = (matrix[0, 1] + matrix[1, 0]) / scale
            qz = (matrix[0, 2] + matrix[2, 0]) / scale
        elif matrix[1, 1] > matrix[2, 2]:
            scale = np.sqrt(1.0 + matrix[1, 1] - matrix[0, 0] - matrix[2, 2]) * 2.0
            qw = (matrix[0, 2] - matrix[2, 0]) / scale
            qx = (matrix[0, 1] + matrix[1, 0]) / scale
            qy = 0.25 * scale
            qz = (matrix[1, 2] + matrix[2, 1]) / scale
        else:
            scale = np.sqrt(1.0 + matrix[2, 2] - matrix[0, 0] - matrix[1, 1]) * 2.0
            qw = (matrix[1, 0] - matrix[0, 1]) / scale
            qx = (matrix[0, 2] + matrix[2, 0]) / scale
            qy = (matrix[1, 2] + matrix[2, 1]) / scale
            qz = 0.25 * scale
        return [float(qx), float(qy), float(qz), float(qw)]

    def zup_box_quaternion(rotation: Sequence[float] | None) -> list[float]:
        if rotation is None or len(rotation) != 4:
            return [0.0, 0.0, 0.0, 1.0]
        # The displayed scene uses A=[x,z,-y]. Conjugating by A keeps box
        # orientation consistent with the coordinate permutation.
        axis_change = np.asarray(
            [[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]],
            dtype=np.float64,
        )
        raw_rotation = quaternion_to_matrix(rotation)
        return matrix_to_quaternion(axis_change @ raw_rotation @ axis_change.T)

    def camera_frustum(record: Mapping[str, Any], depth: float) -> np.ndarray:
        matrix = np.asarray(record["matrix"], dtype=np.float64)
        rotation = matrix[:3, :3]
        origin = matrix[:3, 3]
        half_width = depth * 0.62
        half_height = depth * 0.40
        corners_camera = np.asarray(
            [
                [-half_width, -half_height, depth],
                [half_width, -half_height, depth],
                [half_width, half_height, depth],
                [-half_width, half_height, depth],
            ],
            dtype=np.float64,
        )
        corners_world = corners_camera @ rotation.T + origin
        points = [to_zup(origin)]
        points.extend(to_zup(point) for point in corners_world)
        # A closed pyramid wireframe with rays to two additional corners.
        return np.asarray(
            [
                points[0],
                points[1],
                points[2],
                points[3],
                points[4],
                points[1],
                points[0],
                points[3],
                points[0],
                points[2],
                points[0],
                points[4],
            ],
            dtype=np.float32,
        )

    # Precompute smooth camera trajectory positions across all frames
    all_frame_records = metadata.get("frames", [])
    all_fids = [int(f["frame_id"]) for f in all_frame_records]
    interp_positions: dict[int, list[float]] = {}
    if len(pose_records) > 0 and len(all_fids) > 0:
        kf_ids = np.array([int(r["frame_id"]) for r in pose_records], dtype=np.float32)
        kf_pos = np.array(
            [np.asarray(r["matrix"], dtype=np.float32)[:3, 3] for r in pose_records]
        )
        all_fid_arr = np.array(all_fids, dtype=np.float32)
        ix = np.interp(all_fid_arr, kf_ids, kf_pos[:, 0])
        iy = np.interp(all_fid_arr, kf_ids, kf_pos[:, 1])
        iz = np.interp(all_fid_arr, kf_ids, kf_pos[:, 2])
        for fid, x, y, z in zip(all_fids, ix, iy, iz, strict=True):
            interp_positions[fid] = to_zup([float(x), float(y), float(z)])

    # Load 3D object detections, motion trails, events, and R4DSG.
    motion_trails_by_track: dict[int, list[list[float]]] = {}
    boxes_by_frame: dict[int, list[dict[str, Any]]] = {}
    r4d_anchors: list[dict[str, Any]] = []
    r4d_timeline: dict[str, list[dict[str, Any]]] = {}
    r4d_events: list[dict[str, Any]] = []

    r4d_path = paths.objects_json.parent / "r4d_scene_graph.json"
    if r4d_path.exists():
        r4d_data = _read_json(r4d_path)
        r4d_anchors = r4d_data.get("anchors", [])
        r4d_timeline = r4d_data.get("timeline", {})
        r4d_events = r4d_data.get("events", [])

    if paths.objects_json.exists():
        obj_data = _read_json(paths.objects_json)
        for tid_str, trail in obj_data.get("motion_trails", {}).items():
            motion_trails_by_track[int(tid_str)] = trail
        for box in obj_data.get("boxes_3d", []):
            boxes_by_frame.setdefault(int(box["frame_id"]), []).append(box)

    paths.rerun_recording.parent.mkdir(parents=True, exist_ok=True)
    rr.init(f"aegis-{dataset_id}", spawn=False)
    rr.save(str(paths.rerun_recording))

    # Send a video/3D blueprint with a compact event panel.
    blueprint = rrb.Blueprint(
        rrb.Horizontal(
            rrb.Spatial2DView(
                name="Egocentric Video",
                origin="video",
            ),
            rrb.Vertical(
                rrb.Spatial3DView(
                    name="R4DSG 3D Spatial Memory",
                    origin="spatial_memory",
                    line_grid=True,
                ),
                rrb.TextDocumentView(
                    name="R4DSG Memory Events",
                    origin="memory/events",
                ),
                row_shares=[3.0, 1.0],
            ),
            column_shares=[1.0, 1.35],
        ),
        collapse_panels=True,
    )
    rr.send_blueprint(blueprint)

    # Set View Coordinates to Standard Intuitive Z-Up
    rr.log("spatial_memory", rr.ViewCoordinates.RIGHT_HAND_Z_UP, static=True)

    # 1. Log Spatial Anchors (The Room's Permanent Reference Frame)
    if r4d_anchors:
        anc_centers = [to_zup(a["center"]) for a in r4d_anchors]
        anc_sizes = [to_zup_size(a["size"]) for a in r4d_anchors]
        anc_labels = [f"Anchor: {a['label']} #{a['anchor_id']}" for a in r4d_anchors]
        rr.log(
            "spatial_memory/anchors",
            rr.Boxes3D(
                centers=anc_centers,
                sizes=anc_sizes,
                labels=anc_labels,
                colors=[[59, 130, 246] for _ in r4d_anchors],  # Clean Blue
            ),
            static=True,
        )

    # 2. Log Camera Trajectory in Z-Up Coordinates
    if len(trajectory) > 0:
        zup_trajectory = np.asarray([to_zup(pt) for pt in trajectory], dtype=np.float32)
        rr.log(
            "spatial_memory/camera_trajectory",
            rr.LineStrips3D(
                [zup_trajectory], radii=0.015, colors=[[251, 191, 36]]
            ),  # Amber
            static=True,
        )

    # 2C. Add a minimal visual reference frame and clean ground grid.
    if len(points) > 0:
        point_extent = np.ptp(points, axis=0)
        reference_extent = max(float(np.max(point_extent)) * SCALE * 0.6, 1.0)
    else:
        reference_extent = 2.5
    axis_length = max(reference_extent * 0.18, 0.25)
    rr.log(
        "spatial_memory/reference_axes",
        rr.Arrows3D(
            vectors=[
                [axis_length, 0.0, 0.0],
                [0.0, axis_length, 0.0],
                [0.0, 0.0, axis_length],
            ],
            origins=[[0.0, 0.0, 0.0]] * 3,
            colors=[[239, 68, 68], [34, 197, 94], [59, 130, 246]],
            labels=["X right", "Y forward", "Z up"],
        ),
        static=True,
    )

    grid_values = np.linspace(-reference_extent, reference_extent, 9)
    grid_strips = []
    for value in grid_values:
        grid_strips.append(
            np.asarray(
                [
                    [-reference_extent, float(value), 0.0],
                    [reference_extent, float(value), 0.0],
                ],
                dtype=np.float32,
            )
        )
        grid_strips.append(
            np.asarray(
                [
                    [float(value), -reference_extent, 0.0],
                    [float(value), reference_extent, 0.0],
                ],
                dtype=np.float32,
            )
        )
    rr.log(
        "spatial_memory/reference_grid",
        rr.LineStrips3D(
            grid_strips,
            radii=0.003,
            colors=[[120, 130, 145]],
        ),
        static=True,
    )

    if not r4d_events and paths.events_json.exists():
        r4d_events = _read_json(paths.events_json).get("events", [])
    event_lines = ["# R4DSG memory events", ""]
    if r4d_events:
        for event in r4d_events:
            ev_type = str(event.get("event_type", "transition")).upper()
            event_lines.append(
                f"- **[{ev_type}] {event['object']}**: "
                f"{event.get('source_relation', 'unknown')} → {event.get('destination_relation', 'unknown')} "
                f"({event['start_time']:.2f}s–{event['end_time']:.2f}s), "
                f"evidence frames {event.get('evidence_frames', [])}"
            )
    else:
        event_lines.append("No stable relation transitions were detected.")
    rr.log(
        "memory/events",
        rr.TextDocument("\n".join(event_lines), media_type=rr.MediaType.MARKDOWN),
        static=True,
    )

    # 3. Log All Video Frames, Camera Motion, and 4D Object Memory
    keyframe_id_set = set(pose_by_frame.keys())
    for frame in all_frame_records:
        frame_id = int(frame["frame_id"])

        rr.set_time("frame", sequence=frame_id)
        if "timestamp" in frame:
            rr.set_time("time", duration=float(frame["timestamp"]))

        # 3A. Log Pristine Egocentric Video Frame (compressed to JPEG for compact RRD size)
        if config.visualization.log_video and (
            frame_id % config.visualization.video_stride == 0
        ):
            image_path = paths.frames / str(frame["filename"])
            if image_path.exists():
                import cv2

                img = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
                if img is not None:
                    ok, buf = cv2.imencode(
                        ".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 80]
                    )
                    if ok:
                        rr.log(
                            "video/egocentric_stream",
                            rr.EncodedImage(
                                contents=buf.tobytes(), media_type="image/jpeg"
                            ),
                        )
                    else:
                        rr.log(
                            "video/egocentric_stream",
                            rr.EncodedImage(path=image_path),
                        )
                else:
                    rr.log("video/egocentric_stream", rr.EncodedImage(path=image_path))

        # 3B. Show clean lifted detections on the egocentric video at keyframes.
        frame_boxes = boxes_by_frame.get(frame_id, [])
        if frame_boxes:
            sorted_boxes = sorted(
                frame_boxes,
                key=lambda b: float(b.get("confidence", 0.0)),
                reverse=True,
            )
            clean_boxes: list[dict[str, Any]] = []
            for b in sorted_boxes:
                b_xyxy = b["bbox_2d"]
                is_overlap = False
                for c in clean_boxes:
                    c_xyxy = c["bbox_2d"]
                    iw = max(0.0, min(b_xyxy[2], c_xyxy[2]) - max(b_xyxy[0], c_xyxy[0]))
                    ih = max(0.0, min(b_xyxy[3], c_xyxy[3]) - max(b_xyxy[1], c_xyxy[1]))
                    inter = iw * ih
                    union = (
                        (b_xyxy[2] - b_xyxy[0]) * (b_xyxy[3] - b_xyxy[1])
                        + (c_xyxy[2] - c_xyxy[0]) * (c_xyxy[3] - c_xyxy[1])
                        - inter
                    )
                    if union > 0 and (inter / union) > 0.35:
                        is_overlap = True
                        break
                if not is_overlap:
                    clean_boxes.append(b)
                if len(clean_boxes) >= 3:
                    break

            clean_labels: list[str] = []
            clean_colors: list[list[int]] = []
            for box in clean_boxes:
                lbl = f"{box['label']} #{box['track_id']}"
                if box.get("is_in_hand", False):
                    lbl += " [In Hand]"
                    clean_colors.append([245, 158, 11])  # Amber #F59E0B
                elif box.get("is_hand", False):
                    clean_colors.append([244, 63, 94])  # Rose
                else:
                    clean_colors.append(_track_color(int(box["track_id"])))
                clean_labels.append(lbl)

            rr.log(
                "video/detections",
                rr.Boxes2D(
                    array=np.asarray(
                        [box["bbox_2d"] for box in clean_boxes], dtype=np.float32
                    ),
                    array_format=rr.Box2DFormat.XYXY,
                    colors=clean_colors,
                    labels=clean_labels,
                ),
            )

        # 3C. Smooth Camera Pose in Z-Up
        if frame_id in interp_positions:
            cam_position = interp_positions[frame_id]
            rr.log(
                "spatial_memory/camera",
                rr.Points3D(
                    [cam_position],
                    colors=[[255, 64, 64]],
                    radii=0.035,
                ),
            )

        # 4D. Log R4DSG Persistent Object Memory and Relational Edges
        if frame_id in keyframe_id_set:
            mem_entries = r4d_timeline.get(str(frame_id), [])
            if mem_entries:
                centers = [to_zup(e["center"]) for e in mem_entries]
                sizes = [to_zup_size(e["size"]) for e in mem_entries]
                labels = []
                colors = []
                in_hand_links = []
                cam_pos = interp_positions.get(frame_id)

                for e in mem_entries:
                    is_in_hand = e.get("is_in_hand", False)
                    relation = e.get("relation", "")
                    anchor_lbl = e.get("anchor_label", "Anchor")
                    base_lbl = e["label"]
                    obj_center_zup = to_zup(e["center"])

                    if is_in_hand:
                        labels.append(f"{base_lbl} · [Carried by User]")
                        colors.append([245, 158, 11])  # Amber #F59E0B
                        if cam_pos is not None:
                            in_hand_links.append(
                                np.asarray([cam_pos, obj_center_zup], dtype=np.float32)
                            )
                    elif relation == "inside":
                        labels.append(f"{base_lbl} · [Inside {anchor_lbl}]")
                        colors.append([16, 185, 129])  # Emerald #10B981
                    elif e["is_active_view"]:
                        labels.append(f"{base_lbl} · ACTIVE")
                        colors.append(_track_color(int(e["instance_id"])))
                    else:
                        labels.append(f"{base_lbl} · ✦ PERSISTENT MEMORY")
                        colors.append([20, 184, 166])  # Teal #14B8A6

                quats = [zup_box_quaternion(e.get("rotation")) for e in mem_entries]

                rr.log(
                    "spatial_memory/persistent_objects",
                    rr.Boxes3D(
                        centers=centers,
                        sizes=sizes,
                        labels=labels,
                        colors=colors,
                        quaternions=quats,
                    ),
                )

                if in_hand_links:
                    rr.log(
                        "spatial_memory/in_hand_link",
                        rr.LineStrips3D(
                            in_hand_links,
                            radii=0.015,
                            colors=[[245, 158, 11]],  # Amber
                            labels=["Carried Link"],
                        ),
                    )
                else:
                    rr.log("spatial_memory/in_hand_link", rr.Clear.flat())

            else:
                rr.log("spatial_memory/persistent_objects", rr.Clear.flat())
                rr.log("spatial_memory/in_hand_link", rr.Clear.flat())

    _write_json(
        paths.viewer_manifest,
        {
            "schema_version": 1,
            "dataset_id": dataset_id,
            "recording": str(paths.rerun_recording),
            "frame_count": len(all_frame_records),
            "keyframe_count": len(pose_records),
            "point_count": len(points),
            "total_anchors": len(r4d_anchors),
            "total_tracks": len(motion_trails_by_track),
            "total_events": len(r4d_events),
            "open_command": f"rerun outputs/{dataset_id}/viewer/demo.rrd",
        },
    )
    elapsed = time.perf_counter() - t0
    file_size_mb = (
        round(paths.rerun_recording.stat().st_size / (1024**2), 2)
        if paths.rerun_recording.exists()
        else 0.0
    )

    stage_result = {
        "stage": "rerun",
        "dataset_id": dataset_id,
        "frame_count": len(all_frame_records),
        "keyframe_count": len(pose_records),
        "point_count": len(points),
        "total_anchors": len(r4d_anchors),
        "total_tracks": len(motion_trails_by_track),
        "total_events": len(r4d_events),
        "recording": str(paths.rerun_recording),
        "recording_size_mb": file_size_mb,
        "elapsed_seconds": round(elapsed, 2),
    }
    _record_benchmark_stats(paths, dataset_id, "rerun", stage_result)
    return stage_result
