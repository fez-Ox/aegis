"""Lifting 2D object detections into 3D bounding boxes using dense pointmaps."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from typing import Any

import numpy as np

from aegis.core.models import BoundingBox3D, Detection2D
from aegis.core.vocabulary import Vocabulary, default_vocabulary
from aegis.geometry.gravity import GravityFrame
from aegis.geometry.transforms import quaternion_from_matrix


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
    gravity: GravityFrame | None = None,
    vocabulary: Vocabulary | None = None,
    unit: float = 1.0,
) -> BoundingBox3D | None:
    """Lift a 2D object detection to a 3D bounding box using dense pointmaps and optional instance masks.

    Supports mask-guided lifting to eliminate background/floor contamination, followed by
    a gravity-aligned oriented box fit (height along the session's up vector, yaw from
    the principal direction of the points in the floor plane).

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
    gravity : GravityFrame | None, optional
        Session gravity frame; None uses the legacy assumption (up = -Y).
    vocabulary : Vocabulary | None, optional
        Label vocabulary (plausible sizes, support surfaces). Remote workers must pass it.
    unit : float, optional
        Scale unit from :meth:`GravityFrame.unit`; multiplies absolute thresholds.

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
    inlier_mask = dists <= max(float(dist_thr * 1.5), 0.08 * unit)
    inlier_pts = pts[inlier_mask]
    if len(inlier_pts) < 3:
        inlier_pts = pts

    return _fit_gravity_obb(
        detection,
        inlier_pts,
        gravity=gravity or GravityFrame.assumed(),
        vocabulary=vocabulary or default_vocabulary(),
        lower_quantile=lower_quantile,
        upper_quantile=upper_quantile,
        unit=unit,
    )


def _fit_gravity_obb(
    detection: Detection2D,
    points: np.ndarray,
    *,
    gravity: GravityFrame,
    vocabulary: Vocabulary,
    lower_quantile: float,
    upper_quantile: float,
    unit: float,
) -> BoundingBox3D | None:
    """Fit a box whose height axis is the gravity up vector.

    Yaw is the principal direction of the points projected onto the floor
    plane. Extents are robust quantiles along ``(a, b, up)``; the centre is
    the middle of those extents. Returns None when the box is larger than
    the vocabulary's plausible size for this label.
    """

    e1, e2, up = gravity.basis()
    h1 = points @ e1
    h2 = points @ e2
    vertical = points @ up

    yaw = 0.0
    if len(points) >= 5:
        cov = np.cov(np.vstack([h1, h2]))
        if np.isfinite(cov).all():
            _evals, evecs = np.linalg.eigh(cov)
            vx, vy = float(evecs[0, -1]), float(evecs[1, -1])
            if vx < 0 or (vx == 0 and vy < 0):
                vx, vy = -vx, -vy
            yaw = float(np.arctan2(vy, vx))

    cos_y, sin_y = float(np.cos(yaw)), float(np.sin(yaw))
    along_a = h1 * cos_y + h2 * sin_y
    along_b = -h1 * sin_y + h2 * cos_y
    min_extent = 0.05 * unit

    def _span(values: np.ndarray) -> tuple[float, float, float]:
        low = float(np.quantile(values, lower_quantile))
        high = float(np.quantile(values, upper_quantile))
        return low, high, max(high - low, min_extent)

    low_a, high_a, length = _span(along_a)
    low_b, high_b, width = _span(along_b)
    low_v, high_v, height = _span(vertical)

    a_axis = cos_y * e1 + sin_y * e2
    b_axis = -sin_y * e1 + cos_y * e2
    center_vec = (
        0.5 * (low_a + high_a) * a_axis
        + 0.5 * (low_b + high_b) * b_axis
        + 0.5 * (low_v + high_v) * up
    )
    rotation = quaternion_from_matrix(np.column_stack([a_axis, b_axis, up]))

    entry = vocabulary.entry(detection.label)
    support_up: float | None = None
    if entry.support_surface and len(points) >= 50 and high_v > low_v:
        upper = vertical[(vertical >= 0.5 * (low_v + high_v)) & (vertical <= high_v)]
        if len(upper) > 0:
            bin_width = max(0.05 * (high_v - low_v), 1e-6)
            edges = np.arange(
                float(upper.min()), float(upper.max()) + bin_width, bin_width
            )
            if len(edges) < 2:
                support_up = float(np.median(upper))
            else:
                counts, edges = np.histogram(upper, bins=edges)
                best = int(np.argmax(counts))
                in_bin = upper[(upper >= edges[best]) & (upper <= edges[best + 1])]
                support_up = float(np.median(in_bin)) if len(in_bin) else None

    size = (float(length), float(width), float(height))
    if entry.max_extent is not None and max(size) > entry.max_extent * unit:
        return None

    x1, y1, x2, y2 = detection.bbox
    return BoundingBox3D(
        frame_id=detection.frame_id,
        timestamp=detection.timestamp,
        track_id=detection.track_id,
        label=detection.label,
        confidence=detection.confidence,
        center=(float(center_vec[0]), float(center_vec[1]), float(center_vec[2])),
        size=size,
        bbox_2d=(float(x1), float(y1), float(x2), float(y2)),
        rotation=rotation,
        yaw=yaw,
        is_hand=detection.is_hand,
        appearance=detection.appearance,
        held_by_hand_track_id=detection.contact_target_track_id,
        up_min=low_v,
        up_max=high_v,
        support_up=support_up,
        point_count=len(points),
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


def _smoothed_centers(
    boxes_3d: Sequence[BoundingBox3D],
    smoothing_alpha: float,
) -> dict[int, np.ndarray]:
    """Per-track EMA of box centres, keyed by input index.

    Used only to estimate velocities; the returned boxes keep their raw
    geometry (sizes are never smoothed because the a/b axes can swap).
    """

    by_track: dict[int, list[tuple[int, BoundingBox3D]]] = {}
    for index, box in enumerate(boxes_3d):
        by_track.setdefault(box.track_id, []).append((index, box))

    smoothed: dict[int, np.ndarray] = {}
    for track_boxes in by_track.values():
        previous: np.ndarray | None = None
        for index, box in sorted(track_boxes, key=lambda item: item[1].frame_id):
            center = np.asarray(box.center, dtype=np.float64)
            if previous is not None:
                center = smoothing_alpha * previous + (1.0 - smoothing_alpha) * center
            previous = center
            smoothed[index] = center
    return smoothed


def evaluate_spatial_containment_and_states(
    boxes_3d: Sequence[BoundingBox3D],
    velocity_threshold: float = 0.05,
    smoothing_alpha: float = 0.65,
    *,
    vocabulary: Vocabulary | None = None,
    unit: float = 1.0,
    hand_distance: float = 0.35,
) -> list[BoundingBox3D]:
    """Classify per-box motion and hand-contact states.

    Spatial relations to furniture (inside, on, under, ...) are decided later
    by :mod:`aegis.memory.relations` in the gravity frame; this stage only
    labels each box as ``static_structure`` (anchor or landmark), ``hand``,
    ``in_hand``, ``in_motion`` or ``on_surface`` (a static object; legacy
    name). ``container_relation`` is always None. Geometry is returned
    unchanged.
    """

    if not 0.0 <= smoothing_alpha < 1.0:
        raise ValueError("smoothing_alpha must be in [0, 1)")
    vocab = vocabulary or default_vocabulary()

    smoothed = _smoothed_centers(boxes_3d, smoothing_alpha)
    by_track: dict[int, list[int]] = {}
    for index, box in enumerate(boxes_3d):
        by_track.setdefault(box.track_id, []).append(index)

    velocities: dict[int, float] = {}
    for indices in by_track.values():
        ordered = sorted(indices, key=lambda i: boxes_3d[i].frame_id)
        for position, index in enumerate(ordered):
            if position == 0:
                reference = ordered[1] if len(ordered) > 1 else None
            else:
                reference = ordered[position - 1]
            if reference is None:
                velocities[index] = 0.0
                continue
            dt = max(
                0.01, abs(boxes_3d[index].timestamp - boxes_3d[reference].timestamp)
            )
            distance = float(np.linalg.norm(smoothed[index] - smoothed[reference]))
            velocities[index] = distance / dt

    by_frame: dict[int, list[int]] = {}
    for index, box in enumerate(boxes_3d):
        by_frame.setdefault(box.frame_id, []).append(index)

    updated: list[BoundingBox3D | None] = [None] * len(boxes_3d)
    for indices in by_frame.values():
        hands = [boxes_3d[i] for i in indices if boxes_3d[i].is_hand]
        for index in indices:
            box = boxes_3d[index]
            role = vocab.role(box.label)
            is_structure = role in {"anchor", "landmark"}
            is_hand_box = box.is_hand or role == "hand"

            is_in_hand = box.is_in_hand
            carrier = box.carrier
            held_by = box.held_by_hand_track_id
            if not is_structure and not is_hand_box:
                for hand in hands:
                    distance = float(
                        np.linalg.norm(np.asarray(box.center) - np.asarray(hand.center))
                    )
                    if (
                        hand.held_by_hand_track_id == box.track_id
                        or distance <= hand_distance * unit
                    ):
                        is_in_hand = True
                        carrier = "camera_wearer"
                        held_by = hand.track_id
                        break

            if is_structure:
                state = "static_structure"
            elif is_hand_box:
                state = "hand"
            elif is_in_hand:
                state = "in_hand"
            elif velocities.get(index, 0.0) > velocity_threshold * unit:
                state = "in_motion"
            else:
                state = "on_surface"

            updated[index] = replace(
                box,
                spatial_state=state,
                container_relation=None,
                is_in_hand=is_in_hand
                if not is_structure and not is_hand_box
                else False,
                carrier=carrier if not is_structure and not is_hand_box else None,
                held_by_hand_track_id=held_by,
            )

    return [box for box in updated if box is not None]


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
