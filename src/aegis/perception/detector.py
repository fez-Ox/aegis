"""Open-vocabulary 2D object detection and keyframe tracking adapter.

This module is imported only inside the Modal GPU perception worker.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import hypot
from pathlib import Path
from typing import Any

from aegis.core.config import PerceptionConfig, Sam2Config
from aegis.core.models import Detection2D


def _compute_iou(
    box_a: tuple[float, float, float, float], box_b: tuple[float, float, float, float]
) -> float:
    """Compute Intersection-over-Union between two bounding boxes (x1, y1, x2, y2)."""
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union_area = area_a + area_b - inter_area

    if union_area <= 0:
        return 0.0
    return inter_area / union_area


@dataclass
class _TrackState:
    """Track state with a bounded appearance memory for re-identification."""

    label: str
    bbox: tuple[float, float, float, float]
    velocity: tuple[float, float] = (0.0, 0.0)
    last_index: int = 0
    appearance: tuple[float, ...] | None = None


def _appearance_descriptor(
    image_bgr: Any,
    bbox: tuple[float, float, float, float],
    mask: Any = None,
) -> tuple[float, ...] | None:
    """Return a small colour/texture descriptor for cheap long-term ReID.

    This is intentionally not a new neural model: it is a stable cue for
    deciding whether a dormant track is worth handing back to the same ID.
    Motion/geometry remains the primary cue for active tracks.
    """
    try:
        import cv2
        import numpy as np

        height, width = image_bgr.shape[:2]
        x1, y1, x2, y2 = (round(value) for value in bbox)
        x1, x2 = max(0, x1), min(width, x2)
        y1, y2 = max(0, y1), min(height, y2)
        if x2 <= x1 or y2 <= y1:
            return None
        crop = image_bgr[y1:y2, x1:x2]
        if crop.size == 0:
            return None
        crop = cv2.resize(crop, (32, 32), interpolation=cv2.INTER_AREA)
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        if mask is not None:
            mask_arr = np.asarray(mask).astype(np.uint8)
            if mask_arr.shape != (height, width):
                mask_arr = cv2.resize(
                    mask_arr, (width, height), interpolation=cv2.INTER_NEAREST
                )
            mask_crop = mask_arr[y1:y2, x1:x2]
            mask_crop = cv2.resize(mask_crop, (32, 32), interpolation=cv2.INTER_NEAREST)
            if int(mask_crop.sum()) >= 8:
                pixels = hsv[mask_crop > 0]
            else:
                pixels = hsv.reshape(-1, 3)
        else:
            pixels = hsv.reshape(-1, 3)
        hist = np.concatenate(
            [
                np.histogram(pixels[:, 0], bins=8, range=(0, 180))[0],
                np.histogram(pixels[:, 1], bins=4, range=(0, 256))[0],
                np.histogram(pixels[:, 2], bins=4, range=(0, 256))[0],
            ]
        ).astype(np.float32)
        hist /= max(float(hist.sum()), 1.0)
        return tuple(float(value) for value in hist)
    except (ImportError, AttributeError, ValueError, TypeError):
        return None


def _appearance_distance(
    first: tuple[float, ...] | None,
    second: tuple[float, ...] | None,
) -> float | None:
    if first is None or second is None or len(first) != len(second):
        return None
    return float(0.5 * sum(abs(a - b) for a, b in zip(first, second, strict=True)))


def _bbox_center(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    return ((bbox[0] + bbox[2]) * 0.5, (bbox[1] + bbox[3]) * 0.5)


def _bbox_diagonal(bbox: tuple[float, float, float, float]) -> float:
    return max(hypot(bbox[2] - bbox[0], bbox[3] - bbox[1]), 1.0)


def _predict_bbox(state: _TrackState, gap: int) -> tuple[float, float, float, float]:
    dx = state.velocity[0] * gap
    dy = state.velocity[1] * gap
    return (
        state.bbox[0] + dx,
        state.bbox[1] + dy,
        state.bbox[2] + dx,
        state.bbox[3] + dy,
    )


def _track_match_cost(
    state: _TrackState,
    label: str,
    bbox: tuple[float, float, float, float],
    gap: int,
    appearance: tuple[float, ...] | None = None,
) -> float | None:
    """Return a geometry-aware association cost, or None when clearly incompatible."""

    if state.label != label:
        return None

    predicted = _predict_bbox(state, gap)
    iou = _compute_iou(predicted, bbox)
    predicted_center = _bbox_center(predicted)
    current_center = _bbox_center(bbox)
    center_distance = hypot(
        predicted_center[0] - current_center[0],
        predicted_center[1] - current_center[1],
    )
    normalized_distance = center_distance / max(
        _bbox_diagonal(predicted), _bbox_diagonal(bbox)
    )

    # A short detector miss may move the box substantially, but an unrelated
    # object should not be joined solely because it has the same class.
    if iou < 0.05 and normalized_distance > 1.35:
        return None

    predicted_width = max(predicted[2] - predicted[0], 1.0)
    predicted_height = max(predicted[3] - predicted[1], 1.0)
    current_width = max(bbox[2] - bbox[0], 1.0)
    current_height = max(bbox[3] - bbox[1], 1.0)
    size_change = abs(predicted_width / current_width - 1.0) + abs(
        predicted_height / current_height - 1.0
    )

    # IoU is strongest when available; center and scale keep tracks alive when
    # egocentric camera motion makes the overlap small. Appearance is only a
    # tie-breaker here; it becomes the main cue for dormant-track recovery.
    appearance_distance = _appearance_distance(state.appearance, appearance)
    appearance_cost = appearance_distance if appearance_distance is not None else 0.5
    return (
        (1.0 - iou) * 0.45
        + min(normalized_distance, 2.0) * 0.30
        + min(size_change, 2.0) * 0.10
        + appearance_cost * 0.15
    )


def _dormant_match_cost(
    state: _TrackState,
    label: str,
    bbox: tuple[float, float, float, float],
    appearance: tuple[float, ...] | None,
    appearance_threshold: float,
) -> float | None:
    """Match a disappeared object without trusting stale screen coordinates."""
    if state.label != label or appearance is None:
        return None
    appearance_distance = _appearance_distance(state.appearance, appearance)
    if appearance_distance is None or appearance_distance > appearance_threshold:
        return None
    old_width = max(state.bbox[2] - state.bbox[0], 1.0)
    old_height = max(state.bbox[3] - state.bbox[1], 1.0)
    width = max(bbox[2] - bbox[0], 1.0)
    height = max(bbox[3] - bbox[1], 1.0)
    size_change = abs(old_width / width - 1.0) + abs(old_height / height - 1.0)
    if size_change > 2.0:
        return None
    return appearance_distance + min(size_change, 2.0) * 0.10


def _update_track(
    state: _TrackState,
    bbox: tuple[float, float, float, float],
    frame_index: int,
    smoothing: float,
    appearance: tuple[float, ...] | None = None,
) -> None:
    """Update a track with an exponential position/velocity estimate."""

    previous_center = _bbox_center(state.bbox)
    current_center = _bbox_center(bbox)
    gap = max(frame_index - state.last_index, 1)
    instantaneous_velocity = (
        (current_center[0] - previous_center[0]) / gap,
        (current_center[1] - previous_center[1]) / gap,
    )
    momentum = 0.5
    state.velocity = (
        momentum * state.velocity[0] + (1.0 - momentum) * instantaneous_velocity[0],
        momentum * state.velocity[1] + (1.0 - momentum) * instantaneous_velocity[1],
    )
    state.bbox = tuple(
        smoothing * old + (1.0 - smoothing) * new
        for old, new in zip(state.bbox, bbox, strict=True)
    )
    if appearance is not None:
        if state.appearance is None:
            state.appearance = appearance
        else:
            state.appearance = tuple(
                0.7 * old + 0.3 * new
                for old, new in zip(state.appearance, appearance, strict=True)
            )
    state.last_index = frame_index


def _canonical_label(label: str) -> str:
    normalized = " ".join(label.lower().strip().split())
    if normalized in {"shoe", "shoes"}:
        return "shoes"
    if normalized in {"hand", "human hand", "hands"}:
        return "hand"
    return normalized


def detect_and_track_objects(
    frame_records: Sequence[dict[str, Any]],
    frames_dir: Path,
    config: PerceptionConfig,
    *,
    sam2_config: Sam2Config | None = None,
    weights_dir: Path | None = None,
) -> list[Detection2D]:
    """Run open-vocabulary object detection and assign consistent track IDs.

    Parameters
    ----------
    frame_records : Sequence[dict[str, Any]]
        Metadata records for the keyframes containing frame_id, timestamp, and filename.
    frames_dir : Path
        Directory containing the normalized frame PNG images.
    config : PerceptionConfig
        Perception settings including target classes and thresholds.
    sam2_config : Sam2Config | None, optional
        SAM 2 configuration for extracting instance segmentation masks.
    weights_dir : Path | None
        Directory to store downloaded YOLO weights.

    Returns
    -------
    list[Detection2D]
        List of all detected 2D bounding boxes across keyframes with optional segmentation masks.
    """
    import os
    import shutil

    import cv2
    from ultralytics import YOLO, YOLOWorld

    # YOLOE-seg is promptable and emits masks directly.  This avoids relying on
    # a weak detector box before SAM2 is asked to segment the object.  The
    # legacy YOLO-World path remains available for compatibility.
    model_class = YOLO if config.detector_backend == "yoloe" else YOLOWorld
    if weights_dir is not None:
        weights_dir.mkdir(parents=True, exist_ok=True)
        os.environ["YOLO_CONFIG_DIR"] = str(weights_dir)
        model_path = weights_dir / config.detector_model
        if model_path.exists():
            model = model_class(str(model_path))
        else:
            model = model_class(config.detector_model)
            local_download = Path(config.detector_model)
            if local_download.exists() and not model_path.exists():
                shutil.copy2(local_download, model_path)
    else:
        model = model_class(config.detector_model)

    model.set_classes(list(config.target_classes))

    # Initialize SAM 2 predictor if requested
    sam2_predictor = None
    if sam2_config is not None:
        try:
            import torch
            from sam2.sam2_image_predictor import (  # type: ignore[import-not-found]
                SAM2ImagePredictor,
            )

            device = "cuda" if torch.cuda.is_available() else "cpu"
            sam2_predictor = SAM2ImagePredictor.from_pretrained(
                sam2_config.model_id, device=device
            )
        except (ImportError, RuntimeError, ValueError, OSError, AttributeError) as err:
            print(f"[detector] Warning: Could not initialize SAM2ImagePredictor: {err}")
            sam2_predictor = None

    all_detections: list[Detection2D] = []
    active_tracks: dict[int, _TrackState] = {}
    next_track_id = 1

    for frame_index, record in enumerate(frame_records):
        frame_id = int(record["frame_id"])
        timestamp = float(record["timestamp"])
        image_path = frames_dir / str(record["filename"])
        if not image_path.exists():
            continue

        frame_bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        results = model.predict(
            str(image_path),
            conf=config.confidence_threshold,
            iou=config.iou_threshold,
            verbose=False,
        )

        current_frame_boxes: list[
            tuple[str, float, tuple[float, float, float, float]]
        ] = []
        direct_masks_by_bbox: dict[tuple[float, float, float, float], Any] = {}
        if len(results) > 0 and results[0].boxes is not None:
            result = results[0]
            boxes = result.boxes
            names = result.names
            for idx in range(len(boxes)):
                cls_id = int(boxes.cls[idx].item())
                # set_classes() makes the prompt order the class order.  Use
                # it as the source of truth because some ultralytics versions
                # expose the model's original names on Result.names instead.
                if cls_id < len(config.target_classes):
                    raw_label = config.target_classes[cls_id]
                elif isinstance(names, dict):
                    raw_label = str(names.get(cls_id, f"object_{cls_id}"))
                else:
                    raw_label = (
                        str(names[cls_id])
                        if cls_id < len(names)
                        else f"object_{cls_id}"
                    )
                label = _canonical_label(raw_label)
                conf = float(boxes.conf[idx].item())
                xyxy = tuple(float(v) for v in boxes.xyxy[idx].tolist())
                current_frame_boxes.append(
                    (label, conf, (xyxy[0], xyxy[1], xyxy[2], xyxy[3]))
                )
                if getattr(result, "masks", None) is not None:
                    try:
                        direct_masks_by_bbox[
                            tuple(float(v) for v in boxes.xyxy[idx].tolist())
                        ] = result.masks.data[idx].detach().cpu().numpy().astype(bool)
                    except (AttributeError, IndexError, RuntimeError):
                        pass

        # Class-aware NMS to eliminate duplicate detections per category
        # without suppressing hands that overlap objects during interaction/grasping.
        if len(current_frame_boxes) > 1:
            current_frame_boxes.sort(key=lambda item: item[1], reverse=True)
            suppressed_boxes: list[
                tuple[str, float, tuple[float, float, float, float]]
            ] = []
            for item in current_frame_boxes:
                lbl_i = item[0]
                bbox_i = item[2]
                is_hand_i = lbl_i == "hand"
                suppress = False
                for kept in suppressed_boxes:
                    is_hand_kept = kept[0] == "hand"
                    if (
                        is_hand_i == is_hand_kept
                        and _compute_iou(bbox_i, kept[2]) > 0.35
                    ):
                        suppress = True
                        break
                if not suppress:
                    suppressed_boxes.append(item)
                if len(suppressed_boxes) >= 6:
                    break
            current_frame_boxes = suppressed_boxes

        # Generate SAM 2 masks for current frame detections if predictor is active
        masks_by_idx: dict[int, Any] = {
            b_idx: direct_masks_by_bbox.get(bbox)
            for b_idx, (_label, _conf, bbox) in enumerate(current_frame_boxes)
            if bbox in direct_masks_by_bbox
        }
        if sam2_predictor is not None and current_frame_boxes and frame_bgr is not None:
            import numpy as np

            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            sam2_predictor.set_image(frame_rgb)
            for b_idx, (_, _, bbox_coord) in enumerate(current_frame_boxes):
                try:
                    box_arr = np.array(bbox_coord, dtype=np.float32)
                    p_masks, p_scores, _ = sam2_predictor.predict(
                        box=box_arr[None, :],
                        multimask_output=sam2_config.multimask_output,
                    )
                    best_i = int(np.argmax(p_scores)) if len(p_scores) > 1 else 0
                    candidate = p_masks[best_i].astype(bool)
                    if candidate.any():
                        masks_by_idx[b_idx] = candidate
                except (RuntimeError, ValueError, IndexError, TypeError):
                    # Keep a direct YOLOE mask, if one was produced.
                    masks_by_idx.setdefault(b_idx, None)

        appearance_by_idx: dict[int, tuple[float, ...] | None] = {
            b_idx: (
                _appearance_descriptor(frame_bgr, bbox, masks_by_idx.get(b_idx))
                if frame_bgr is not None
                else None
            )
            for b_idx, (_label, _conf, bbox) in enumerate(current_frame_boxes)
        }

        # Keep an archive of tracks for the whole video. Active tracks use
        # motion/IoU; dormant tracks use appearance and scale only, because
        # stale screen coordinates are unreliable after camera motion.
        candidate_matches: list[tuple[float, int, int]] = []
        for b_idx, (label, _conf, bbox) in enumerate(current_frame_boxes):
            appearance = appearance_by_idx[b_idx]
            for track_id, state in active_tracks.items():
                gap = max(frame_index - state.last_index, 1)
                if gap <= config.track_max_gap:
                    cost = _track_match_cost(state, label, bbox, gap, appearance)
                elif gap <= config.reid_max_gap:
                    cost = _dormant_match_cost(
                        state,
                        label,
                        bbox,
                        appearance,
                        config.reid_appearance_threshold,
                    )
                else:
                    cost = None
                if cost is not None:
                    candidate_matches.append((cost, b_idx, track_id))

        candidate_matches.sort(key=lambda item: item[0])
        matched_detection_to_track: dict[int, int] = {}
        used_track_ids: set[int] = set()
        for _cost, b_idx, track_id in candidate_matches:
            if b_idx in matched_detection_to_track or track_id in used_track_ids:
                continue
            matched_detection_to_track[b_idx] = track_id
            used_track_ids.add(track_id)

        # Compute hand-object contact association
        contact_pairs: dict[int, int] = {}  # hand_box_index -> object_track_id
        hand_indices = [
            idx for idx, (lbl, _, _) in enumerate(current_frame_boxes) if lbl == "hand"
        ]
        object_indices = [
            idx for idx, (lbl, _, _) in enumerate(current_frame_boxes) if lbl != "hand"
        ]

        for h_idx in hand_indices:
            h_box = current_frame_boxes[h_idx][2]
            for o_idx in object_indices:
                o_box = current_frame_boxes[o_idx][2]
                o_track_id = matched_detection_to_track.get(o_idx)
                iou = _compute_iou(h_box, o_box)
                if iou >= config.hand_contact_iou_threshold and o_track_id is not None:
                    contact_pairs[h_idx] = o_track_id
                    break

        for b_idx, (label, conf, bbox) in enumerate(current_frame_boxes):
            assigned_id = matched_detection_to_track.get(b_idx)
            if assigned_id is None:
                assigned_id = next_track_id
                next_track_id += 1
                active_tracks[assigned_id] = _TrackState(
                    label=label,
                    bbox=bbox,
                    last_index=frame_index,
                    appearance=appearance_by_idx[b_idx],
                )
            else:
                _update_track(
                    active_tracks[assigned_id],
                    bbox,
                    frame_index,
                    config.track_smoothing,
                    appearance_by_idx[b_idx],
                )

            mask_val = masks_by_idx.get(b_idx)
            is_hand = label == "hand"
            target_obj_track_id = contact_pairs.get(b_idx) if is_hand else None
            all_detections.append(
                Detection2D(
                    frame_id=frame_id,
                    timestamp=timestamp,
                    track_id=assigned_id,
                    label=label,
                    confidence=conf,
                    bbox=bbox,
                    mask=mask_val,
                    is_hand=is_hand,
                    contact_target_track_id=target_obj_track_id,
                    appearance=appearance_by_idx[b_idx],
                )
            )

    return all_detections
