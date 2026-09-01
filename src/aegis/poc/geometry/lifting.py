"""Lifting 2D object detections into 3D bounding boxes using dense pointmaps."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from aegis.poc.core.models import BoundingBox3D, Detection2D


def lift_detection_to_3d(
    detection: Detection2D,
    pointmap: np.ndarray,
    *,
    confmap: np.ndarray | None = None,
    min_conf_thr: float = 1.0,
    min_points: int = 10,
    lower_quantile: float = 0.05,
    upper_quantile: float = 0.95,
    frame_size: tuple[int, int] | None = None,
) -> BoundingBox3D | None:
    """Lift a 2D bounding box detection to a 3D bounding box from a 3D pointmap.

    Parameters
    ----------
    detection : Detection2D
        The 2D detection containing pixel bounding box (x1, y1, x2, y2).
    pointmap : np.ndarray
        Dense 3D pointmap of shape (H, W, 3) representing 3D coordinates in world space.
    confmap : np.ndarray | None, optional
        Confidence map of shape (H, W), by default None.
    min_conf_thr : float, optional
        Minimum confidence threshold for valid points, by default 1.0.
    min_points : int, optional
        Minimum number of valid 3D points required inside the bounding box, by default 10.
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

    # Convert coordinates to integer indices clamped to image bounds
    ix1 = max(0, min(w - 1, round(x1_scaled)))
    iy1 = max(0, min(h - 1, round(y1_scaled)))
    ix2 = max(0, min(w, round(x2_scaled)))
    iy2 = max(0, min(h, round(y2_scaled)))

    if ix2 <= ix1 or iy2 <= iy1:
        return None

    crop_pts = pointmap[iy1:iy2, ix1:ix2].reshape(-1, 3)

    # Filter out NaNs and infinities
    valid_mask = np.isfinite(crop_pts).all(axis=1)

    if confmap is not None:
        if confmap.shape != (h, w):
            raise ValueError("confmap shape must match pointmap (H, W)")
        crop_conf = confmap[iy1:iy2, ix1:ix2].reshape(-1)
        valid_mask &= (crop_conf >= min_conf_thr) & np.isfinite(crop_conf)

    pts = crop_pts[valid_mask]
    if len(pts) < min_points:
        return None

    # Compute robust bounding bounds using quantiles to avoid flying outlier points
    q_min = np.quantile(pts, lower_quantile, axis=0)
    q_max = np.quantile(pts, upper_quantile, axis=0)

    # Inlier points within quantile bounds
    inlier_mask = (pts >= q_min).all(axis=1) & (pts <= q_max).all(axis=1)
    inlier_pts = pts[inlier_mask]
    if len(inlier_pts) < 3:
        inlier_pts = pts

    center = np.median(inlier_pts, axis=0)
    # Size: max - min with a small minimum extent floor
    extent = np.maximum(q_max - q_min, 0.05)

    return BoundingBox3D(
        frame_id=detection.frame_id,
        timestamp=detection.timestamp,
        track_id=detection.track_id,
        label=detection.label,
        confidence=detection.confidence,
        center=(float(center[0]), float(center[1]), float(center[2])),
        size=(float(extent[0]), float(extent[1]), float(extent[2])),
        bbox_2d=(float(x1), float(y1), float(x2), float(y2)),
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


CONTAINER_LABELS = {"cabinet", "shelf", "cupboard", "box", "drawer", "table", "desk"}


def evaluate_spatial_containment_and_states(
    boxes_3d: Sequence[BoundingBox3D],
    velocity_threshold: float = 0.05,
) -> list[BoundingBox3D]:
    """Evaluate 3D spatial containment and dynamic motion states for all detected 3D boxes.

    Parameters
    ----------
    boxes_3d : Sequence[BoundingBox3D]
        List of all lifted 3D bounding boxes.
    velocity_threshold : float, optional
        Minimum displacement velocity (units/sec) to classify as 'in_motion', by default 0.05.

    Returns
    -------
    list[BoundingBox3D]
        Updated list of BoundingBox3D objects with classified spatial_state and container_relation.
    """
    by_frame: dict[int, list[BoundingBox3D]] = {}
    for b in boxes_3d:
        by_frame.setdefault(b.frame_id, []).append(b)

    sorted_by_track: dict[int, list[BoundingBox3D]] = {}
    for b in boxes_3d:
        sorted_by_track.setdefault(b.track_id, []).append(b)

    velocities: dict[tuple[int, int], float] = {}
    for tid, track_boxes in sorted_by_track.items():
        st = sorted(track_boxes, key=lambda x: x.frame_id)
        for i, curr in enumerate(st):
            if i == 0 and len(st) > 1:
                nxt = st[1]
                dt = max(0.01, nxt.timestamp - curr.timestamp)
                dist = float(np.linalg.norm(np.array(nxt.center) - np.array(curr.center)))
                velocities[(tid, curr.frame_id)] = dist / dt
            elif i > 0:
                prev = st[i - 1]
                dt = max(0.01, curr.timestamp - prev.timestamp)
                dist = float(np.linalg.norm(np.array(curr.center) - np.array(prev.center)))
                velocities[(tid, curr.frame_id)] = dist / dt
            else:
                velocities[(tid, curr.frame_id)] = 0.0

    updated_boxes: list[BoundingBox3D] = []
    for frame_id in sorted(by_frame.keys()):
        frame_boxes = by_frame[frame_id]
        containers = [
            b for b in frame_boxes
            if any(cl in b.label.lower() for cl in CONTAINER_LABELS)
        ]

        for box in frame_boxes:
            box_label = box.label.lower()
            is_container = any(cl in box_label for cl in CONTAINER_LABELS)

            contained_in: str | None = None
            if not is_container and containers:
                s_c = np.array(box.center)
                for c in containers:
                    c_c = np.array(c.center)
                    c_s = np.array(c.size)
                    bounds_min = c_c - c_s * 0.65
                    bounds_max = c_c + c_s * 0.65
                    if (s_c >= bounds_min).all() and (s_c <= bounds_max).all():
                        contained_in = f"{c.label} #{c.track_id}"
                        break

            vel = velocities.get((box.track_id, box.frame_id), 0.0)
            if contained_in is not None:
                spatial_state = f"inside_{contained_in.split()[0]}"
            elif vel > velocity_threshold and not is_container:
                spatial_state = "in_motion"
            else:
                spatial_state = "on_surface" if not is_container else "static_structure"

            updated = BoundingBox3D(
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
            )
            updated_boxes.append(updated)

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

    unique_voxels, inverse_indices = np.unique(voxel_coords, axis=0, return_inverse=True)
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
