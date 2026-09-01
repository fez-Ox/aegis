"""Implementation of the remote Aegis Phase 1 workers.

Every function in this module is called by a Modal Function. Heavy imports are
kept inside the relevant worker so importing the local orchestration module
never initializes CUDA, OpenCV, or a model.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from aegis.poc.core.config import RuntimeConfig
from aegis.poc.core.models import BoundingBox3D
from aegis.poc.core.paths import (
    DatasetPaths,
    dataset_paths,
    dust3r_model_path,
)
from aegis.poc.ingestion.video import preprocess_video as preprocess_video_file


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


def run_preprocess(dataset_id: str, raw_config: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a video and write frame metadata to the data Volume."""

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
        paths.rerun_recording,
        paths.viewer_manifest,
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
    return {
        "stage": "preprocess",
        "dataset_id": dataset_id,
        "frame_count": metadata["frame_count"],
        "metadata": str(paths.metadata),
        "frames": str(paths.frames),
        "calibration": str(paths.calibration_normalized)
        if metadata["calibration_values"] is not None
        else None,
    }


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


def _ensure_dust3r_weights(config: RuntimeConfig) -> Path:
    weights_path = dust3r_model_path(config)
    weights_path.parent.mkdir(parents=True, exist_ok=True)
    if weights_path.exists() and weights_path.stat().st_size > 10_000_000:
        return weights_path

    import urllib.request

    temporary = weights_path.with_suffix(weights_path.suffix + ".download")
    if temporary.exists():
        temporary.unlink()
    with (
        urllib.request.urlopen(config.dust3r.weights_url, timeout=600) as response,
        temporary.open("wb") as handle,
    ):
        shutil.copyfileobj(response, handle)
    if not temporary.exists() or temporary.stat().st_size <= 10_000_000:
        raise RuntimeError(f"DUSt3R weight download failed: {temporary}")
    temporary.replace(weights_path)
    return weights_path


def run_dust3r(dataset_id: str, raw_config: Mapping[str, Any]) -> dict[str, Any]:
    """Execute DUSt3R multi-view 3D reconstruction on keyframes."""

    config = _config(raw_config)
    paths = dataset_paths(config, dataset_id)
    metadata = _require_metadata(paths)
    frames = metadata.get("frames", [])
    if not frames:
        raise ValueError("metadata contains no frames")

    weights_path = _ensure_dust3r_weights(config)

    # Sample keyframes with stride
    keyframe_records = frames[:: config.dust3r.keyframe_stride]
    if len(keyframe_records) < 2:
        keyframe_records = frames[: min(len(frames), 2)]
    image_paths = [paths.frames / str(rec["filename"]) for rec in keyframe_records]

    from aegis.poc.geometry.dust3r_runner import run_dust3r_reconstruction

    rec_result = run_dust3r_reconstruction(image_paths, weights_path, config.dust3r)

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
    _write_ply(paths.pointcloud_ply, rec_result["global_points"], rec_result["global_colors"])

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
                "source": "DUSt3R",
            }
        )

    _write_json(
        paths.poses,
        {
            "schema_version": 1,
            "dataset_id": dataset_id,
            "source": "DUSt3R",
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
            "source": "DUSt3R",
            "keyframe_count": len(keyframe_records),
            "point_count": len(rec_result["global_points"]),
            "confidence_threshold": config.dust3r.min_conf_thr,
        },
    )

    return {
        "stage": "dust3r",
        "dataset_id": dataset_id,
        "keyframe_count": len(keyframe_records),
        "point_count": len(rec_result["global_points"]),
        "pointcloud": str(paths.pointcloud_ply),
        "poses": str(paths.poses),
    }


def run_detect_and_lift(
    dataset_id: str, raw_config: Mapping[str, Any]
) -> dict[str, Any]:
    """Run open-vocabulary object perception and lift 2D detections to 3D bounding boxes."""

    config = _config(raw_config)
    paths = dataset_paths(config, dataset_id)
    metadata = _require_metadata(paths)
    if not paths.pointmaps_npz.exists():
        raise FileNotFoundError(
            f"pointmaps artifact is missing; run dust3r reconstruction first: {paths.pointmaps_npz}"
        )

    frames = metadata.get("frames", [])
    data = np.load(paths.pointmaps_npz)
    pointmaps = data["pointmaps"]
    confmaps = data["confmaps"]
    keyframe_ids = data["keyframe_ids"].tolist()

    keyframe_id_set = set(keyframe_ids)
    keyframe_records = [f for f in frames if int(f["frame_id"]) in keyframe_id_set]
    keyframe_index_map = {int(kid): idx for idx, kid in enumerate(keyframe_ids)}

    from aegis.poc.geometry.lifting import (
        compute_motion_trails,
        evaluate_spatial_containment_and_states,
        lift_detection_to_3d,
        serialize_boxes_3d,
    )
    from aegis.poc.perception.detector import detect_and_track_objects

    weights_dir = Path(config.storage.model_mount) / "yolo"
    detections_2d = detect_and_track_objects(
        keyframe_records, paths.frames, config.perception, weights_dir=weights_dir
    )

    frame_res = tuple(metadata.get("resolution", (pointmaps[0].shape[1], pointmaps[0].shape[0])))
    raw_lifted_boxes: list[BoundingBox3D] = []
    for det in detections_2d:
        kf_idx = keyframe_index_map.get(det.frame_id)
        if kf_idx is None:
            continue
        pm = pointmaps[kf_idx]
        cm = confmaps[kf_idx]
        box_3d = lift_detection_to_3d(
            det,
            pm,
            confmap=cm,
            min_conf_thr=config.dust3r.min_conf_thr,
            min_points=config.perception.min_points_in_box,
            frame_size=(int(frame_res[0]), int(frame_res[1])),
        )
        if box_3d is not None:
            raw_lifted_boxes.append(box_3d)

    # Layer 2: Evaluate 3D spatial containment and dynamic motion states
    lifted_boxes = evaluate_spatial_containment_and_states(raw_lifted_boxes)
    motion_trails = compute_motion_trails(lifted_boxes)

    # Build R4DSG Relative 4D Scene Graph Memory
    from aegis.poc.memory.scene_graph import build_relative_4d_scene_graph

    all_kf_ids = [int(f["frame_id"]) for f in keyframe_records]
    all_ts = [float(f["timestamp"]) for f in keyframe_records]
    scene_graph = build_relative_4d_scene_graph(lifted_boxes, all_kf_ids, all_ts)

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

    return {
        "stage": "detect_and_lift",
        "dataset_id": dataset_id,
        "detections_2d": len(detections_2d),
        "boxes_3d": len(lifted_boxes),
        "tracks": len(motion_trails),
        "objects_file": str(paths.objects_json),
        "r4d_scene_graph": str(r4d_path),
        "spatial_memory_graph": str(memory_graph_path),
    }


TRACK_PALETTE = [
    [34, 197, 94],   # Emerald Green
    [59, 130, 246],  # Vibrant Blue
    [239, 68, 68],   # Red
    [234, 179, 8],   # Amber
    [168, 85, 247],  # Purple
    [236, 72, 153],  # Pink
    [20, 184, 166],  # Teal
    [249, 115, 22],  # Orange
]


def _track_color(track_id: int) -> list[int]:
    return TRACK_PALETTE[(track_id - 1) % len(TRACK_PALETTE)]


def run_rerun(dataset_id: str, raw_config: Mapping[str, Any]) -> dict[str, Any]:
    """Create an offline Rerun recording containing video, geometry, 3D boxes, and motion trails."""

    config = _config(raw_config)
    paths = dataset_paths(config, dataset_id)
    metadata = _require_metadata(paths)
    if not paths.poses.exists():
        raise FileNotFoundError(f"pose artifact is missing: {paths.poses}")
    if not paths.pointcloud_npz.exists():
        raise FileNotFoundError(
            f"point-cloud artifact is missing: {paths.pointcloud_npz}"
        )

    import cv2
    import rerun as rr

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

    # Load 3D object detections, motion trails, and R4DSG if available
    motion_trails_by_track: dict[int, list[list[float]]] = {}
    r4d_anchors: list[dict[str, Any]] = []
    r4d_timeline: dict[str, list[dict[str, Any]]] = {}

    r4d_path = paths.objects_json.parent / "r4d_scene_graph.json"
    if r4d_path.exists():
        r4d_data = _read_json(r4d_path)
        r4d_anchors = r4d_data.get("anchors", [])
        r4d_timeline = r4d_data.get("timeline", {})
    elif paths.objects_json.exists():
        obj_data = _read_json(paths.objects_json)
        for tid_str, pts in obj_data.get("motion_trails", {}).items():
            motion_trails_by_track[int(tid_str)] = pts

    paths.rerun_recording.parent.mkdir(parents=True, exist_ok=True)
    rr.init(f"aegis-{dataset_id}", spawn=False)
    rr.save(str(paths.rerun_recording))

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
                colors=[[59, 130, 246] for _ in r4d_anchors], # Clean Blue
            ),
            static=True,
        )

    # 2. Log Camera Trajectory in Z-Up Coordinates
    if len(trajectory) > 0:
        zup_trajectory = np.asarray([to_zup(pt) for pt in trajectory], dtype=np.float32)
        rr.log(
            "spatial_memory/camera_trajectory",
            rr.LineStrips3D([zup_trajectory], radii=0.015, colors=[[251, 191, 36]]), # Amber
            static=True,
        )

    # 3. Log time-sequenced video, 2D bounding boxes, camera poses, and Persistent 4D Object Memory
    for frame in metadata["frames"]:
        frame_id = int(frame["frame_id"])
        pose_record = pose_by_frame.get(frame_id)
        if pose_record is None:
            continue

        rr.set_time("frame", sequence=frame_id)
        if "timestamp" in frame:
            rr.set_time("time", duration=float(frame["timestamp"]))

        # 3A. Log Video Frame & 2D Detections
        if config.visualization.log_video and (
            frame_id % config.visualization.video_stride == 0
        ):
            image_path = paths.frames / str(frame["filename"])
            image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
            if image is not None:
                rr.log("video/egocentric_stream", rr.Image(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)))

        # 3B. Camera Pose in Z-Up
        raw_position = np.asarray(pose_record["matrix"], dtype=np.float32)[:3, 3]
        cam_position = to_zup(raw_position.tolist())
        rr.log(
            "spatial_memory/camera",
            rr.Points3D(
                [cam_position],
                colors=[[255, 64, 64]],
                radii=0.035,
            ),
        )

        # 3C. Log R4DSG Persistent Object Memory in Z-Up
        mem_entries = r4d_timeline.get(str(frame_id), [])
        if mem_entries:
            centers = [to_zup(e["center"]) for e in mem_entries]
            sizes = [to_zup_size(e["size"]) for e in mem_entries]
            labels = []
            colors = []

            for e in mem_entries:
                act = "ACTIVE" if e["is_active_view"] else f"PERSISTENT (t={e['last_seen_timestamp']:.1f}s)"
                labels.append(
                    f"{e['label']} · [{act}] · Rel: {e['relation']} ({e['relative_distance']:.2f}m)"
                )
                if e["is_active_view"]:
                    colors.append(_track_color(int(e["instance_id"])))
                else:
                    colors.append([20, 184, 166]) # Teal for persistent memory

            rr.log(
                "spatial_memory/persistent_objects",
                rr.Boxes3D(
                    centers=centers,
                    sizes=sizes,
                    labels=labels,
                    colors=colors,
                ),
            )

            # Log 3D Relational Graph Edges in Z-Up
            for e in mem_entries:
                if e.get("anchor_id") is not None:
                    anc = next((a for a in r4d_anchors if a["anchor_id"] == e["anchor_id"]), None)
                    if anc:
                        edge_pts = np.asarray([to_zup(e["center"]), to_zup(anc["center"])], dtype=np.float32)
                        rr.log(
                            f"spatial_memory/relational_edges/inst_{e['instance_id']}",
                            rr.LineStrips3D(
                                [edge_pts],
                                radii=0.006,
                                colors=[[236, 72, 153]],
                                labels=[f"{e['relation']} ({e['relative_distance']:.2f}m)"],
                            ),
                        )

    _write_json(
        paths.viewer_manifest,
        {
            "schema_version": 1,
            "dataset_id": dataset_id,
            "recording": str(paths.rerun_recording),
            "frame_count": len(pose_records),
            "point_count": len(points),
            "total_anchors": len(r4d_anchors),
            "total_tracks": len(motion_trails_by_track),
            "open_command": f"rerun poc/outputs/{dataset_id}/viewer/demo.rrd",
        },
    )
    return {
        "stage": "rerun",
        "dataset_id": dataset_id,
        "frame_count": len(pose_records),
        "point_count": len(points),
        "total_anchors": len(r4d_anchors),
        "total_tracks": len(motion_trails_by_track),
        "recording": str(paths.rerun_recording),
    }

