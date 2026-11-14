"""Compare YOLOE masks with SAM 2 masks on a processed dataset (M1 gate).

Runs on Modal (GPU). For every keyframe it detects objects once, then
reports per class: mean IoU between the YOLOE mask and the SAM 2 mask of
the same box, the share of boxes where the YOLOE mask is missing or too
small (the boxes 'fallback' mode still sends to SAM 2), and the time spent
in SAM 2. Keep sam2.mode=fallback only if mean IoU >= 0.80 on demo01 and
demo04; record the numbers in context/todo.md (M1).

Usage:
    uv run modal run scripts/compare_masks.py --dataset-id demo04 \
        --config-path config/demo04.yaml
"""

from __future__ import annotations

import json
from typing import Any

from aegis.core.config import config_to_dict, load_config
from aegis.remote.modal_app import (
    DATA_MOUNT,
    MODEL_MOUNT,
    PERCEPTION_IMAGE,
    SECRETS,
    app,
    data_volume,
    model_cache_volume,
)


@app.function(
    image=PERCEPTION_IMAGE,
    gpu="L4",
    volumes={DATA_MOUNT: data_volume, MODEL_MOUNT: model_cache_volume},
    secrets=SECRETS,
    timeout=3600,
)
def compare(dataset_id: str, raw_config: dict[str, Any]) -> dict[str, Any]:
    import time
    from pathlib import Path

    import cv2
    import numpy as np

    from aegis.core.config import RuntimeConfig
    from aegis.core.paths import dataset_paths
    from aegis.perception.detector import choose_mask, load_models

    config = RuntimeConfig.from_mapping(raw_config)
    paths = dataset_paths(config, dataset_id)
    metadata = json.loads(paths.metadata.read_text())
    frames = metadata["frames"][:: config.vggt.keyframe_stride]
    models = load_models(
        config.perception,
        sam2_config=config.sam2,
        weights_dir=Path(config.storage.model_mount) / "yolo",
    )
    models.detector.set_classes(list(config.perception.target_classes))
    stats: dict[str, dict[str, Any]] = {}
    sam_seconds = 0.0
    for record in frames:
        image = cv2.imread(str(paths.frames / record["filename"]))
        result = models.detector.predict(
            [image],
            conf=config.perception.confidence_threshold,
            verbose=False,
            retina_masks=True,
        )[0]
        if result.boxes is None or result.masks is None:
            continue
        models.sam2.set_image(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        for index in range(len(result.boxes)):
            label = config.perception.target_classes[
                int(result.boxes.cls[index].item())
            ]
            bbox = tuple(float(v) for v in result.boxes.xyxy[index].tolist())
            direct = result.masks.data[index].cpu().numpy().astype(bool)
            start = time.perf_counter()
            masks, _scores, _ = models.sam2.predict(
                box=np.asarray(bbox, dtype=np.float32)[None, :], multimask_output=False
            )
            sam_seconds += time.perf_counter() - start
            sam = masks[0].astype(bool)
            if sam.shape != direct.shape:
                direct = cv2.resize(direct.astype(np.uint8), sam.shape[::-1]) > 0
            union = np.logical_or(direct, sam).sum()
            iou = float(np.logical_and(direct, sam).sum() / union) if union else 0.0
            _mask, needs_sam = choose_mask(
                direct,
                bbox,
                (image.shape[1], image.shape[0]),
                min_area_ratio=config.sam2.min_mask_area_ratio,
            )
            entry = stats.setdefault(label, {"boxes": 0, "iou_sum": 0.0, "fallback": 0})
            entry["boxes"] += 1
            entry["iou_sum"] += iou
            entry["fallback"] += int(needs_sam)
    report = {
        label: {
            "boxes": entry["boxes"],
            "mean_iou": round(entry["iou_sum"] / entry["boxes"], 4),
            "fallback_share": round(entry["fallback"] / entry["boxes"], 4),
        }
        for label, entry in stats.items()
    }
    boxes = sum(e["boxes"] for e in stats.values())
    report["_overall"] = {
        "boxes": boxes,
        "mean_iou": round(sum(e["iou_sum"] for e in stats.values()) / max(boxes, 1), 4),
        "sam2_seconds": round(sam_seconds, 2),
    }
    return report


@app.local_entrypoint()
def main(dataset_id: str, config_path: str = "config/demo.yaml") -> None:
    result = compare.remote(dataset_id, config_to_dict(load_config(config_path)))
    print(json.dumps(result, indent=2))
