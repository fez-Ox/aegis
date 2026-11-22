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
from aegis.core.vocabulary import Vocabulary, default_vocabulary


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
    embedding: tuple[float, ...] | None = None


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


Box = tuple[str, float, tuple[float, float, float, float]]


def suppress_duplicates(
    boxes: Sequence[Box], *, duplicate_iou: float, max_detections: int
) -> list[Box]:
    """Drop a box only when a more confident box of the same label overlaps it.

    Different classes never suppress each other (a shoe inside a cabinet, a
    hand holding keys). At most ``max_detections`` boxes are kept.
    """

    kept: list[Box] = []
    for item in sorted(boxes, key=lambda b: b[1], reverse=True):
        if any(
            other[0] == item[0] and _compute_iou(item[2], other[2]) > duplicate_iou
            for other in kept
        ):
            continue
        kept.append(item)
        if len(kept) >= max_detections:
            break
    return kept


def mask_area_ratio(
    mask: Any, bbox: tuple[float, float, float, float], image_size: tuple[int, int]
) -> float:
    """Mask area as a fraction of its box area (mask may be at any resolution)."""

    import numpy as np

    width, height = image_size
    box_area = max(bbox[2] - bbox[0], 0.0) * max(bbox[3] - bbox[1], 0.0)
    if box_area <= 0 or width <= 0 or height <= 0:
        return 0.0
    values = np.asarray(mask, dtype=bool)
    if values.size == 0:
        return 0.0
    mask_fraction = float(values.sum()) / float(values.size)
    box_fraction = box_area / float(width * height)
    return mask_fraction / box_fraction


def choose_mask(
    direct_mask: Any,
    bbox: tuple[float, float, float, float],
    image_size: tuple[int, int],
    *,
    min_area_ratio: float,
) -> tuple[Any, bool]:
    """Return (mask to use, whether SAM 2 is still needed) for ``mode=fallback``."""

    if direct_mask is None:
        return None, True
    if mask_area_ratio(direct_mask, bbox, image_size) < min_area_ratio:
        return direct_mask, True
    return direct_mask, False


def embedding_distance(
    first: Sequence[float] | None, second: Sequence[float] | None
) -> float | None:
    """1 - cosine similarity of two L2-normalised embeddings."""

    if first is None or second is None or len(first) != len(second):
        return None
    dot = sum(a * b for a, b in zip(first, second, strict=True))
    return float(1.0 - dot)


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
    embedding: tuple[float, ...] | None = None,
    embedding_threshold: float | None = None,
) -> float | None:
    """Match a disappeared object without trusting stale screen coordinates.

    With a learned embedding on both sides it is the re-ID cue (``1 - cos``
    against ``embedding_threshold``); otherwise the colour histogram is.
    """
    if state.label != label:
        return None
    if (
        embedding is not None
        and state.embedding is not None
        and embedding_threshold is not None
    ):
        appearance_distance = embedding_distance(state.embedding, embedding)
        appearance_threshold = embedding_threshold
    elif appearance is None:
        return None
    else:
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
    embedding: tuple[float, ...] | None = None,
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
    if embedding is not None:
        if state.embedding is None:
            state.embedding = embedding
        else:
            mixed = [
                0.7 * old + 0.3 * new
                for old, new in zip(state.embedding, embedding, strict=True)
            ]
            norm = sum(v * v for v in mixed) ** 0.5 or 1.0
            state.embedding = tuple(v / norm for v in mixed)
    state.last_index = frame_index


@dataclass
class DetectorModels:
    """Loaded detector (YOLOE / YOLO-World), SAM 2 and optional re-ID model."""

    detector: Any
    sam2: Any = None
    embedder: Any = None


class DinoEmbedder:
    """DINOv2 ViT-S/14 CLS embedding of a masked box crop (L2-normalised)."""

    MODEL_ID = "facebook/dinov2-small"

    def __init__(self) -> None:
        import torch
        from transformers import AutoModel

        self.torch = torch
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = AutoModel.from_pretrained(self.MODEL_ID).to(self.device).eval()
        self.mean = torch.tensor([0.485, 0.456, 0.406], device=self.device).view(
            3, 1, 1
        )
        self.std = torch.tensor([0.229, 0.224, 0.225], device=self.device).view(3, 1, 1)

    def __call__(
        self, image_bgr: Any, bbox: tuple[float, float, float, float], mask: Any = None
    ) -> tuple[float, ...] | None:
        import cv2
        import numpy as np

        height, width = image_bgr.shape[:2]
        x1, y1, x2, y2 = (round(v) for v in bbox)
        x1, x2 = max(0, x1), min(width, x2)
        y1, y2 = max(0, y1), min(height, y2)
        if x2 <= x1 or y2 <= y1:
            return None
        crop = cv2.cvtColor(image_bgr[y1:y2, x1:x2], cv2.COLOR_BGR2RGB).astype(
            np.float32
        )
        if mask is not None:
            full = np.asarray(mask).astype(np.uint8)
            if full.shape != (height, width):
                full = cv2.resize(
                    full, (width, height), interpolation=cv2.INTER_NEAREST
                )
            region = full[y1:y2, x1:x2] > 0
            if region.sum() >= 8:
                crop[~region] = crop.reshape(-1, 3).mean(axis=0)
        crop = cv2.resize(crop, (224, 224), interpolation=cv2.INTER_AREA) / 255.0
        tensor = self.torch.from_numpy(crop).permute(2, 0, 1).to(self.device)
        tensor = ((tensor - self.mean) / self.std).unsqueeze(0)
        with self.torch.inference_mode():
            cls = self.model(pixel_values=tensor).last_hidden_state[0, 0]
        cls = cls / cls.norm().clamp_min(1e-6)
        return tuple(float(v) for v in cls.float().cpu().tolist())


class _Sam3Boxes:
    """Minimal tensor container matching Ultralytics' ``result.boxes``."""

    def __init__(self, classes: list[int], confs: list[float], xyxy: list[list[float]]):
        import torch

        self.cls = torch.tensor(classes, dtype=torch.long)
        self.conf = torch.tensor(confs, dtype=torch.float32)
        self.xyxy = torch.tensor(xyxy, dtype=torch.float32).reshape(-1, 4)

    def __len__(self) -> int:
        return int(self.cls.numel())


class _Sam3Masks:
    def __init__(self, masks: list[Any]):
        import numpy as np
        import torch

        if masks:
            self.data = torch.from_numpy(np.stack(masks))
        else:
            self.data = torch.zeros((0, 1, 1), dtype=torch.bool)


class _Sam3Result:
    def __init__(
        self,
        classes: list[int],
        confs: list[float],
        xyxy: list[list[float]],
        masks: list[Any],
    ):
        self.boxes = _Sam3Boxes(classes, confs, xyxy)
        self.masks = _Sam3Masks(masks)
        self.names: dict[int, str] = {}


class Sam3Adapter:
    """Batched SAM3 text prompts behind the ``model.predict`` interface.

    The rest of :func:`detect_and_track_objects` (mask rescue, re-ID, tracking,
    hand contact) therefore runs unchanged for SAM3 as for YOLOE.
    """

    def __init__(self, config: PerceptionConfig):
        self.config = config
        self.prompts: list[str] = []
        self._model: Any = None
        self._processor: Any = None
        self._device: str = "cpu"

    def set_classes(self, prompts: list[str]) -> None:
        self.prompts = list(prompts)

    def _load(self) -> None:
        if self._model is not None:
            return
        import torch
        from transformers import Sam3Model, Sam3Processor

        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model = Sam3Model.from_pretrained(
            self.config.sam3_model, device_map=self._device
        ).to(self._device, dtype=torch.bfloat16)
        self._processor = Sam3Processor.from_pretrained(self.config.sam3_model)

    def predict(
        self,
        images: Sequence[Any],
        *,
        conf: float = 0.0,
        iou: float = 0.45,
        verbose: bool = False,
        retina_masks: bool = True,
    ) -> list[_Sam3Result]:
        self._load()
        import cv2
        import torch
        from PIL import Image

        if not self.prompts:
            return [_Sam3Result([], [], [], []) for _ in images]
        results: list[_Sam3Result] = []
        for image in images:
            pil = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            inputs = self._processor(
                images=[pil] * len(self.prompts),
                text=self.prompts,
                return_tensors="pt",
            ).to(self._device)
            with torch.no_grad():
                outputs = self._model(**inputs)
            processed_all = self._processor.post_process_instance_segmentation(
                outputs,
                threshold=0.2,
                mask_threshold=0.5,
                target_sizes=inputs["original_sizes"].tolist(),
            )
            raw: list[tuple[str, float, tuple[float, float, float, float]]] = []
            masks: list[Any] = []
            for prompt, processed in zip(self.prompts, processed_all, strict=True):
                threshold = self.config.sam3_class_thresholds.get(
                    prompt, self.config.sam3_default_threshold
                )
                instances = processed.get("masks")
                for index, score in enumerate(processed["scores"]):
                    if float(score) < threshold:
                        continue
                    box = [float(value) for value in processed["boxes"][index].tolist()]
                    raw.append((prompt, float(score), (box[0], box[1], box[2], box[3])))
                    mask = (
                        None
                        if instances is None
                        else instances[index].cpu().numpy().astype(bool)
                    )
                    if mask is None or mask.size == 0:
                        import numpy as np

                        mask = np.zeros((1, 1), dtype=bool)
                    masks.append(mask)
            kept = suppress_duplicates(
                raw,
                duplicate_iou=self.config.duplicate_iou,
                max_detections=self.config.max_detections_per_frame,
            )
            mask_by_box = {id(box): mask for box, mask in zip(raw, masks, strict=True)}
            results.append(
                _Sam3Result(
                    [self.prompts.index(item[0]) for item in kept],
                    [item[1] for item in kept],
                    [list(item[2]) for item in kept],
                    [mask_by_box[id(item)] for item in kept],
                )
            )
        return results


def load_models(
    config: PerceptionConfig,
    *,
    sam2_config: Sam2Config | None = None,
    weights_dir: Path | None = None,
) -> DetectorModels:
    """Load the models once; a warm Modal container reuses them."""

    import os
    import shutil

    sam3 = config.detector_backend == "sam3"
    if sam3:
        model = Sam3Adapter(config)
    else:
        from ultralytics import YOLO, YOLOWorld

        # YOLOE-seg is promptable and emits masks directly; YOLO-World remains
        # available for compatibility.
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
    if sam2_config is not None and sam2_config.mode == "off":
        sam2_predictor = None
    embedder = None
    if config.reid_backend == "dino":
        try:
            embedder = DinoEmbedder()
        except (ImportError, OSError, RuntimeError) as err:
            print(f"[detector] Warning: DINOv2 unavailable, using HSV re-ID: {err}")
    return DetectorModels(detector=model, sam2=sam2_predictor, embedder=embedder)


def detect_and_track_objects(
    frame_records: Sequence[dict[str, Any]],
    frames_dir: Path,
    config: PerceptionConfig,
    *,
    sam2_config: Sam2Config | None = None,
    weights_dir: Path | None = None,
    vocabulary: Vocabulary | None = None,
    models: DetectorModels | None = None,
    track_embeddings: dict[int, tuple[float, ...]] | None = None,
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
    vocabulary : Vocabulary | None
        Label vocabulary. Remote workers must pass ``config.vocab()``; ``None``
        reads the repository file and only works locally.

    Returns
    -------
    list[Detection2D]
        List of all detected 2D bounding boxes across keyframes with optional segmentation masks.
    """
    import cv2

    vocab = vocabulary or default_vocabulary()
    if models is None:
        models = load_models(config, sam2_config=sam2_config, weights_dir=weights_dir)
    model = models.detector
    sam2_predictor = models.sam2
    # Prompts can differ per call (task-scoped configs); setting them is cheap.
    model.set_classes(list(config.target_classes))

    all_detections: list[Detection2D] = []
    active_tracks: dict[int, _TrackState] = {}
    next_track_id = 1

    embedder = models.embedder
    sam2_mode = sam2_config.mode if sam2_config is not None else "off"
    min_area_ratio = sam2_config.min_mask_area_ratio if sam2_config is not None else 0.0

    def batches():
        """Decode each frame once and predict in batches (M7)."""

        pending: list[tuple[int, dict[str, Any], Any]] = []
        for frame_index, record in enumerate(frame_records):
            image_path = frames_dir / str(record["filename"])
            if not image_path.exists():
                continue
            image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
            if image is None:
                continue
            pending.append((frame_index, record, image))
            if len(pending) >= config.batch_size:
                yield from _predict(pending)
                pending = []
        if pending:
            yield from _predict(pending)

    def _predict(items):
        outputs = model.predict(
            [image for _i, _r, image in items],
            conf=config.confidence_threshold,
            iou=config.iou_threshold,
            verbose=False,
            # Masks at the original frame size, not the letterboxed one.
            retina_masks=True,
        )
        for (frame_index, record, image), output in zip(items, outputs, strict=True):
            yield frame_index, record, image, [output]

    for frame_index, record, frame_bgr, results in batches():
        frame_id = int(record["frame_id"])
        timestamp = float(record["timestamp"])
        image_size = (int(frame_bgr.shape[1]), int(frame_bgr.shape[0]))

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
                label = vocab.canonical(raw_label)
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

        # Duplicates of the same label only (M4); different classes never
        # suppress each other.
        current_frame_boxes = suppress_duplicates(
            current_frame_boxes,
            duplicate_iou=config.duplicate_iou,
            max_detections=config.max_detections_per_frame,
        )

        # Masks: YOLOE's own mask when adequate, SAM 2 only where needed (M1).
        masks_by_idx: dict[int, Any] = {}
        needs_sam: list[int] = []
        for b_idx, (_label, _conf, bbox) in enumerate(current_frame_boxes):
            direct = direct_masks_by_bbox.get(bbox)
            if sam2_mode == "always":
                masks_by_idx[b_idx] = direct
                needs_sam.append(b_idx)
            elif sam2_mode == "fallback":
                chosen, need = choose_mask(
                    direct, bbox, image_size, min_area_ratio=min_area_ratio
                )
                masks_by_idx[b_idx] = chosen
                if need:
                    needs_sam.append(b_idx)
            else:
                masks_by_idx[b_idx] = direct
        if sam2_predictor is not None and needs_sam:
            import numpy as np

            sam2_predictor.set_image(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
            for b_idx in needs_sam:
                bbox_coord = current_frame_boxes[b_idx][2]
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
                    pass  # keep the direct YOLOE mask, if any

        embedding_by_idx: dict[int, tuple[float, ...] | None] = {
            b_idx: (
                embedder(frame_bgr, bbox, masks_by_idx.get(b_idx))
                if embedder is not None
                else None
            )
            for b_idx, (_label, _conf, bbox) in enumerate(current_frame_boxes)
        }
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
                        embedding_by_idx[b_idx],
                        config.reid_embedding_threshold,
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
            idx
            for idx, (lbl, _, _) in enumerate(current_frame_boxes)
            if vocab.role(lbl) == "hand"
        ]
        object_indices = [
            idx
            for idx, (lbl, _, _) in enumerate(current_frame_boxes)
            if vocab.role(lbl) != "hand"
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
                    embedding=embedding_by_idx[b_idx],
                )
            else:
                _update_track(
                    active_tracks[assigned_id],
                    bbox,
                    frame_index,
                    config.track_smoothing,
                    appearance_by_idx[b_idx],
                    embedding_by_idx[b_idx],
                )

            mask_val = masks_by_idx.get(b_idx)
            is_hand = vocab.role(label) == "hand"
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

    if track_embeddings is not None:
        for track_id, state in active_tracks.items():
            if state.embedding is not None:
                track_embeddings[track_id] = state.embedding
    return all_detections
