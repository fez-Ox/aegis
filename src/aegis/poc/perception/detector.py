"""Open-vocabulary 2D object detection and keyframe tracking adapter.

This module is imported only inside the Modal GPU perception worker.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from aegis.poc.core.config import PerceptionConfig
from aegis.poc.core.models import Detection2D


def _compute_iou(box_a: tuple[float, float, float, float], box_b: tuple[float, float, float, float]) -> float:
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


def detect_and_track_objects(
    frame_records: Sequence[dict[str, Any]],
    frames_dir: Path,
    config: PerceptionConfig,
    *,
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
    weights_dir : Path | None
        Directory to store downloaded YOLO weights.

    Returns
    -------
    list[Detection2D]
        List of all detected 2D bounding boxes across keyframes.
    """
    import os
    import shutil

    from ultralytics import YOLOWorld

    if weights_dir is not None:
        weights_dir.mkdir(parents=True, exist_ok=True)
        os.environ["YOLO_CONFIG_DIR"] = str(weights_dir)
        model_path = weights_dir / config.detector_model
        if model_path.exists():
            model = YOLOWorld(str(model_path))
        else:
            model = YOLOWorld(config.detector_model)
            local_download = Path(config.detector_model)
            if local_download.exists() and not model_path.exists():
                shutil.copy2(local_download, model_path)
    else:
        model = YOLOWorld(config.detector_model)

    model.set_classes(list(config.target_classes))

    all_detections: list[Detection2D] = []
    active_tracks: dict[int, tuple[str, tuple[float, float, float, float]]] = {}
    next_track_id = 1

    for record in frame_records:
        frame_id = int(record["frame_id"])
        timestamp = float(record["timestamp"])
        image_path = frames_dir / str(record["filename"])
        if not image_path.exists():
            continue

        results = model.predict(
            str(image_path),
            conf=config.confidence_threshold,
            iou=config.iou_threshold,
            verbose=False,
        )

        current_frame_boxes: list[tuple[str, float, tuple[float, float, float, float]]] = []
        if len(results) > 0 and results[0].boxes is not None:
            boxes = results[0].boxes
            for idx in range(len(boxes)):
                cls_id = int(boxes.cls[idx].item())
                raw_label = (
                    config.target_classes[cls_id]
                    if cls_id < len(config.target_classes)
                    else f"object_{cls_id}"
                )
                label = "shoes" if raw_label.lower().strip() == "shoe" else raw_label
                conf = float(boxes.conf[idx].item())
                xyxy = tuple(float(v) for v in boxes.xyxy[idx].tolist())
                current_frame_boxes.append((label, conf, (xyxy[0], xyxy[1], xyxy[2], xyxy[3])))

        # Associate current frame detections with active tracks
        updated_active: dict[int, tuple[str, tuple[float, float, float, float]]] = {}
        unmatched_detections: list[tuple[str, float, tuple[float, float, float, float]]] = []

        for label, conf, bbox in current_frame_boxes:
            best_track_id: int | None = None
            best_iou = 0.2  # minimum IoU to maintain track continuity across keyframes

            for track_id, (prev_label, prev_bbox) in active_tracks.items():
                if track_id in updated_active:
                    continue
                if prev_label == label:
                    iou = _compute_iou(prev_bbox, bbox)
                    if iou > best_iou:
                        best_iou = iou
                        best_track_id = track_id

            if best_track_id is not None:
                updated_active[best_track_id] = (label, bbox)
                all_detections.append(
                    Detection2D(
                        frame_id=frame_id,
                        timestamp=timestamp,
                        track_id=best_track_id,
                        label=label,
                        confidence=conf,
                        bbox=bbox,
                    )
                )
            else:
                unmatched_detections.append((label, conf, bbox))

        # Assign new track IDs to unmatched detections
        for label, conf, bbox in unmatched_detections:
            assigned_id = next_track_id
            next_track_id += 1
            updated_active[assigned_id] = (label, bbox)
            all_detections.append(
                Detection2D(
                    frame_id=frame_id,
                    timestamp=timestamp,
                    track_id=assigned_id,
                    label=label,
                    confidence=conf,
                    bbox=bbox,
                )
            )

        active_tracks = updated_active

    return all_detections
