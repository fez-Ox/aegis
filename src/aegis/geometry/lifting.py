"""Lifting 2D object detections into 3D bounding boxes using dense pointmaps."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from aegis.core.models import BoundingBox3D, Detection2D


def _resize_mask(mask: np.ndarray, target_h: int, target_w: int) -> np.ndarray:
    """Resize binary mask using cv2 if available, or pure numpy nearest-neighbor."""
    if mask.shape == (target_h, target_w):
        return mask
    try:
        import cv2

        return cv2.resize(
            mask.astype(np.uint8), (target_w, target_h), interpolation=cv2.INTER_NEAREST
        )
    except ImportError:
        y_idx = np.linspace(0, mask.shape[0] - 1, target_h).astype(np.int64)
        x_idx = np.linspace(0, mask.shape[1] - 1, target_w).astype(np.int64)
        return mask[y_idx[:, None], x_idx]


def lift_detection_to_3d(
    detection: Detection2D,
    pointmap: np.ndarray,
    *,
    mask: np.ndarray | None = None,
    confmap: np.ndarray | None = None,
    min_conf_thr: float = 1.0,
    min_points: int = 10,
    lower_quantile: float = 0.05,
    upper_quantile: float = 0.95,
    frame_size: tuple[int, int] | None = None,
) -> BoundingBox3D | None:
    """Lift a 2D object detection to a 3D bounding box using dense pointmaps and optional instance masks.

    Supports mask-guided lifting to eliminate background/floor contamination, followed by
    Z-aligned Oriented Bounding Box (OBB) fitting via 2D principal component analysis.

    Parameters
    ----------
    detection : Detection2D
        The 2D detection containing pixel bounding box (x1, y1, x2, y2) and optional mask.
    pointmap : np.ndarray
        Dense 3D pointmap of shape (H, W, 3) representing 3D coordinates in world space.
    mask : np.ndarray | None, optional
        Optional binary foreground segmentation mask of shape (H, W). If None, detection.mask is checked.
    confmap : np.ndarray | None, optional
        Confidence map of shape (H, W), by default None.
    min_conf_thr : float, optional
        Minimum confidence threshold for valid points, by default 1.0.
    min_points : int, optional
        Minimum number of valid 3D points required inside the object, by default 10.
    lower_quantile : float, optional
        Lower quantile for robust bounding box estimation, by default 0.05.
    upper_quantile : float, optional
        Upper quantile for robust bounding box estimation, by default 0.95.
    frame_size : tuple[int, int] | None, optional
        The (width, height) of the original frame that the 2D bounding box was detected on.
        If provided and different from pointmap (W, H), the box is scaled accordingly.

    Returns
    -------
    BoundingBox3D | None
        The lifted 3D bounding box, or None if insufficient valid 3D points exist.
    """
    if pointmap.ndim != 3 or pointmap.shape[2] != 3:
        raise ValueError("pointmap must have shape (H, W, 3)")

    h, w, _ = pointmap.shape
    x1, y1, x2, y2 = detection.bbox

    # Check for foreground segmentation mask (either parameter or on detection)
    seg_mask = mask if mask is not None else getattr(detection, "mask", None)

    if seg_mask is not None and isinstance(seg_mask, np.ndarray) and seg_mask.size > 0:
        mask_bool = _resize_mask(seg_mask, h, w) > 0

        mask_pts = pointmap[mask_bool].reshape(-1, 3)
        valid_mask = np.isfinite(mask_pts).all(axis=1)

        if confmap is not None:
            if confmap.shape != (h, w):
                raise ValueError("confmap shape must match pointmap (H, W)")
            conf_vals = confmap[mask_bool].reshape(-1)
            valid_mask &= (conf_vals >= min_conf_thr) & np.isfinite(conf_vals)

        pts = mask_pts[valid_mask]
    else:
        # Scale 2D bbox if original frame dimensions differ from pointmap grid dimensions
        if frame_size is not None and frame_size[0] > 0 and frame_size[1] > 0:
            orig_w, orig_h = frame_size
            scale_x = w / float(orig_w)
            scale_y = h / float(orig_h)
            x1_scaled = x1 * scale_x
            y1_scaled = y1 * scale_y
            x2_scaled = x2 * scale_x
            y2_scaled = y2 * scale_y
        else:
            x1_scaled, y1_scaled, x2_scaled, y2_scaled = x1, y1, x2, y2

        ix1 = max(0, min(w - 1, round(x1_scaled)))
        iy1 = max(0, min(h - 1, round(y1_scaled)))
        ix2 = max(0, min(w, round(x2_scaled)))
        iy2 = max(0, min(h, round(y2_scaled)))

        if ix2 <= ix1 or iy2 <= iy1:
            return None

        crop_pts = pointmap[iy1:iy2, ix1:ix2].reshape(-1, 3)
        valid_mask = np.isfinite(crop_pts).all(axis=1)

        if confmap is not None:
            if confmap.shape != (h, w):
                raise ValueError("confmap shape must match pointmap (H, W)")
            crop_conf = confmap[iy1:iy2, ix1:ix2].reshape(-1)
            valid_mask &= (crop_conf >= min_conf_thr) & np.isfinite(crop_conf)

        pts = crop_pts[valid_mask]

    if len(pts) < min_points:
        return None

    # Outlier rejection using distance from spatial median
    med = np.median(pts, axis=0)
    dists = np.linalg.norm(pts - med, axis=1)
    dist_thr = np.quantile(dists, 0.90)
    inlier_mask = dists <= max(float(dist_thr * 1.5), 0.08)
    inlier_pts = pts[inlier_mask]
    if len(inlier_pts) < 3:
        inlier_pts = pts

    # Fit Z-aligned Oriented Bounding Box (OBB) using 2D covariance in horizontal plane
    yaw = 0.0
    rot_quat: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)
    try:
        xy = inlier_pts[:, :2]
        if len(xy) >= 5:
            cov = np.cov(xy, rowvar=False)
            if np.isfinite(cov).all():
                _evals, evecs = np.linalg.eigh(cov)
                v = evecs[:, -1]
                yaw = float(np.arctan2(v[1], v[0]))
                rot_quat = (
                    0.0,
                    0.0,
                    float(np.sin(yaw / 2.0)),
                    float(np.cos(yaw / 2.0)),
                )

        cos_y, sin_y = np.cos(-yaw), np.sin(-yaw)
        x_rot = inlier_pts[:, 0] * cos_y - inlier_pts[:, 1] * sin_y
        y_rot = inlier_pts[:, 0] * sin_y + inlier_pts[:, 1] * cos_y
        z_pts = inlier_pts[:, 2]

        q_min_x, q_max_x = (
            np.quantile(x_rot, lower_quantile),
            np.quantile(x_rot, upper_quantile),
        )
        q_min_y, q_max_y = (
            np.quantile(y_rot, lower_quantile),
            np.quantile(y_rot, upper_quantile),
        )
        q_min_z, q_max_z = (
            np.quantile(z_pts, lower_quantile),
            np.quantile(z_pts, upper_quantile),
        )

        cx_rot = float(np.median(x_rot))
        cy_rot = float(np.median(y_rot))
        cz = float(np.median(z_pts))

        cos_pos, sin_pos = np.cos(yaw), np.sin(yaw)
        cx = cx_rot * cos_pos - cy_rot * sin_pos
        cy = cx_rot * sin_pos + cy_rot * cos_pos

        extent = (
            max(float(q_max_x - q_min_x), 0.05),
            max(float(q_max_y - q_min_y), 0.05),
            max(float(q_max_z - q_min_z), 0.05),
        )
        center = (cx, cy, cz)
    except (RuntimeError, ValueError, IndexError, TypeError):
        q_min = np.quantile(inlier_pts, lower_quantile, axis=0)
        q_max = np.quantile(inlier_pts, upper_quantile, axis=0)
        c = np.median(inlier_pts, axis=0)
        center = (float(c[0]), float(c[1]), float(c[2]))
        extent_arr = np.maximum(q_max - q_min, 0.05)
        extent = (float(extent_arr[0]), float(extent_arr[1]), float(extent_arr[2]))

    # Filter out unphysical 3D boxes (e.g. spurious floor or background patches)
    lbl = detection.label.lower()
    max_dim = max(extent)
    volume = extent[0] * extent[1] * extent[2]
    compact_classes = (
        "shoe",
        "pot",
        "bowl",
        "basket",
        "container",
        "cup",
        "bottle",
        "plate",
    )
    if any(k in lbl for k in compact_classes) and (max_dim > 0.85 or volume > 0.25):
        return None
    anchor_classes = (
        "counter",
        "refrigerator",
        "fridge",
        "sink",
        "cabinet",
        "shelf",
        "table",
    )
    if any(k in lbl for k in anchor_classes) and (max_dim > 4.5 or volume > 15.0):
        return None

    return BoundingBox3D(
        frame_id=detection.frame_id,
        timestamp=detection.timestamp,
        track_id=detection.track_id,
        label=detection.label,
        confidence=detection.confidence,
        center=center,
        size=extent,
        bbox_2d=(float(x1), float(y1), float(x2), float(y2)),
        rotation=rot_quat,
        yaw=yaw,
    )


def compute_motion_trails(
    boxes_3d: Sequence[BoundingBox3D],
) -> dict[int, list[tuple[float, float, float]]]:
    """Group 3D bounding box centers by track_id to form temporal motion trails."""
    trails: dict[int, list[tuple[float, float, float]]] = {}
    # Sort boxes chronologically
    sorted_boxes = sorted(boxes_3d, key=lambda b: (b.track_id, b.frame_id))
    for box in sorted_boxes:
        if box.track_id not in trails:
            trails[box.track_id] = []
        trails[box.track_id].append(box.center)
    return trails


CONTAINER_LABELS = {
    "cabinet",
    "storage cabinet",
    "shelf",
    "cupboard",
    "box",
    "drawer",
    "table",
    "desk",
    "counter",
    "kitchen counter",
    "refrigerator",
    "fridge",
    "podium",
    "lectern",
    "rostrum",
}


def _is_container_label(label: str) -> bool:
    normalized = " ".join(label.lower().split())
    return any(
        token == normalized or token in normalized.split() for token in CONTAINER_LABELS
    )


def _smooth_track_boxes(
    boxes_3d: Sequence[BoundingBox3D],
    smoothing_alpha: float,
) -> list[BoundingBox3D]:
    """Apply a light per-track EMA without inventing observations during gaps."""

    by_track: dict[int, list[tuple[int, BoundingBox3D]]] = {}
    for index, box in enumerate(boxes_3d):
        by_track.setdefault(box.track_id, []).append((index, box))

    smoothed: list[BoundingBox3D | None] = [None] * len(boxes_3d)
    for track_boxes in by_track.values():
        previous_center: np.ndarray | None = None
        previous_size: np.ndarray | None = None
        for index, box in sorted(track_boxes, key=lambda item: item[1].frame_id):
            center = np.asarray(box.center, dtype=np.float64)
            size = np.asarray(box.size, dtype=np.float64)
            if previous_center is not None and previous_size is not None:
                center = (
                    smoothing_alpha * previous_center + (1.0 - smoothing_alpha) * center
                )
                size = smoothing_alpha * previous_size + (1.0 - smoothing_alpha) * size
            previous_center = center
            previous_size = size
            smoothed[index] = BoundingBox3D(
                frame_id=box.frame_id,
                timestamp=box.timestamp,
                track_id=box.track_id,
                label=box.label,
                confidence=box.confidence,
                center=tuple(float(value) for value in center),
                size=tuple(float(value) for value in size),
                bbox_2d=box.bbox_2d,
                spatial_state=box.spatial_state,
                container_relation=box.container_relation,
                rotation=box.rotation,
                yaw=box.yaw,
            )

    return [box for box in smoothed if box is not None]


def evaluate_spatial_containment_and_states(
    boxes_3d: Sequence[BoundingBox3D],
    velocity_threshold: float = 0.05,
    smoothing_alpha: float = 0.65,
) -> list[BoundingBox3D]:
    """Classify containment and motion using smoothed 3D extents.

    The previous implementation encoded the demo narrative using object IDs and
    frame ranges. This version derives states only from geometry and observed
    motion, so it remains usable when the video, object count, or ordering changes.
    """
    if not 0.0 <= smoothing_alpha < 1.0:
        raise ValueError("smoothing_alpha must be in [0, 1)")

    smoothed_boxes = _smooth_track_boxes(boxes_3d, smoothing_alpha)
    by_frame: dict[int, list[BoundingBox3D]] = {}
    for box in smoothed_boxes:
        by_frame.setdefault(box.frame_id, []).append(box)

    sorted_by_track: dict[int, list[BoundingBox3D]] = {}
    for box in smoothed_boxes:
        sorted_by_track.setdefault(box.track_id, []).append(box)

    velocities: dict[tuple[int, int], float] = {}
    for track_id, track_boxes in sorted_by_track.items():
        ordered = sorted(track_boxes, key=lambda item: item.frame_id)
        for index, current in enumerate(ordered):
            if index == 0:
                reference = ordered[1] if len(ordered) > 1 else None
            else:
                reference = ordered[index - 1]
            if reference is None:
                velocities[(track_id, current.frame_id)] = 0.0
                continue
            dt = max(0.01, abs(current.timestamp - reference.timestamp))
            distance = float(
                np.linalg.norm(
                    np.asarray(current.center) - np.asarray(reference.center)
                )
            )
            velocities[(track_id, current.frame_id)] = distance / dt

    updated_boxes: list[BoundingBox3D] = []
    for frame_id in sorted(by_frame):
        frame_boxes = by_frame[frame_id]
        containers = [box for box in frame_boxes if _is_container_label(box.label)]

        for box in frame_boxes:
            is_container = _is_container_label(box.label)
            contained_in: str | None = None
            if not is_container:
                object_center = np.asarray(box.center)
                object_half_size = np.asarray(box.size) * 0.5
                object_min = object_center - object_half_size
                object_max = object_center + object_half_size
                for container in containers:
                    container_center = np.asarray(container.center)
                    container_half_size = np.asarray(container.size) * 0.5
                    tolerance = np.maximum(container_half_size * 0.08, 0.02)
                    container_min = container_center - container_half_size - tolerance
                    container_max = container_center + container_half_size + tolerance
                    if (object_min >= container_min).all() and (
                        object_max <= container_max
                    ).all():
                        contained_in = f"{container.label} #{container.track_id}"
                        break

            velocity = velocities.get((box.track_id, box.frame_id), 0.0)
            if contained_in is not None:
                spatial_state = f"inside_{contained_in.split()[0]}"
            elif velocity > velocity_threshold and not is_container:
                spatial_state = "in_motion"
            elif is_container:
                spatial_state = "static_structure"
            else:
                spatial_state = "on_surface"

            updated_boxes.append(
                BoundingBox3D(
                    frame_id=box.frame_id,
                    timestamp=box.timestamp,
                    track_id=box.track_id,
                    label=box.label,
                    confidence=box.confidence,
                    center=box.center,
                    size=box.size,
                    bbox_2d=box.bbox_2d,
                    spatial_state=spatial_state,
                    container_relation=contained_in,
                    rotation=box.rotation,
                    yaw=box.yaw,
                )
            )

    return updated_boxes


def voxel_downsample(
    points: np.ndarray,
    colors: np.ndarray,
    voxel_size: float = 0.004,
) -> tuple[np.ndarray, np.ndarray]:
    """Downsample point cloud using a fast 3D voxel grid filter.

    Parameters
    ----------
    points : np.ndarray
        Point coordinates of shape (N, 3).
    colors : np.ndarray
        RGB color values of shape (N, 3).
    voxel_size : float, optional
        Voxel cell dimension in coordinate units (default 0.004).

    Returns
    -------
    tuple[np.ndarray, np.ndarray]
        Downsampled (points, colors) arrays.
    """
    if len(points) == 0:
        return points, colors

    min_bound = np.min(points, axis=0)
    voxel_coords = np.floor((points - min_bound) / voxel_size).astype(np.int32)

    unique_voxels, inverse_indices = np.unique(
        voxel_coords, axis=0, return_inverse=True
    )
    n_voxels = len(unique_voxels)

    down_points = np.zeros((n_voxels, 3), dtype=np.float32)
    counts = np.zeros(n_voxels, dtype=np.int32)
    sum_cols = np.zeros((n_voxels, 3), dtype=np.float32)

    np.add.at(down_points, inverse_indices, points)
    np.add.at(sum_cols, inverse_indices, colors.astype(np.float32))
    np.add.at(counts, inverse_indices, 1)

    down_points /= counts[:, None]
    down_colors = np.clip(sum_cols / counts[:, None], 0, 255).astype(np.uint8)
    return down_points, down_colors


def serialize_boxes_3d(boxes_3d: Sequence[BoundingBox3D]) -> list[dict[str, Any]]:
    """Convert sequence of BoundingBox3D objects to JSON-serializable dictionaries."""
    return [box.as_dict() for box in boxes_3d]
