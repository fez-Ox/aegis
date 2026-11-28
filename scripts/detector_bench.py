"""A/B benchmark for open-vocabulary detection on hand-labeled frames.

Runs several detector backends / prompt sets over the same images and scores
class-aware IoU matches against `evaluation/annotations/detection_bench.json`.

Usage:
    uv run python scripts/detector_bench.py --variants compact_yoloe,world_compact
    uv run python scripts/detector_bench.py --variants all --dump-detections
"""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
from typing import Any

import modal

from aegis.remote.modal_app import (
    MODEL_MOUNT,
    PERCEPTION_IMAGE,
    SECRETS,
    model_cache_volume,
)

# SAM3 ships in newer transformers than the pinned perception image.
SAM3_IMAGE = PERCEPTION_IMAGE.pip_install(
    "transformers>=5.0,<6", "accelerate>=1.0,<2", "pillow>=10,<12"
)

app = modal.App("aegis-detector-bench")

# 93 prompts auto-generated from config/vocabulary.yaml: today's generic config.
GENERIC = [
    "storage cabinet",
    "cabinet",
    "cupboard",
    "shelf",
    "refrigerator",
    "fridge",
    "kitchen counter",
    "counter",
    "desk",
    "table",
    "dining table",
    "coffee table",
    "drawer",
    "sink",
    "podium",
    "lectern",
    "rostrum",
    "stand",
    "bed",
    "sofa",
    "couch",
    "chair",
    "wardrobe",
    "nightstand",
    "stove",
    "oven",
    "kitchen island",
    "door",
    "front door",
    "stairs",
    "staircase",
    "television",
    "tv",
    "toilet",
    "bathtub",
    "shower",
    "bathroom sink",
    "window",
    "hand",
    "human hand",
    "hands",
    "shoes",
    "shoe",
    "bottle",
    "water bottle",
    "plastic bottle",
    "mug",
    "cup",
    "keys",
    "keychain",
    "glasses",
    "reading glasses",
    "sunglasses",
    "cell phone",
    "phone",
    "wallet",
    "purse",
    "handbag",
    "backpack",
    "medicine",
    "pill bottle",
    "remote control",
    "hearing aid",
    "walking stick",
    "watch",
    "charger",
    "laptop",
    "book",
    "cooking pot",
    "pot",
    "pan",
    "bowl",
    "plate",
    "dish",
    "fork",
    "spoon",
    "knife",
    "food",
    "food container",
    "container",
    "clothes",
    "shirt",
    "pants",
    "towel",
    "trash bin",
    "trash can",
    "wastebasket",
    "garbage bag",
    "rubbish",
    "paper",
    "basket",
    "box",
    "cardboard box",
]

# Compact, high-value set for the benchmark's five environments.
COMPACT = [
    "storage cabinet",
    "shelf",
    "hand",
    "shoes",
    "cooking pot",
    "bowl",
    "plate",
    "basket",
    "garbage bag",
    "trash bin",
    "clothes",
    "mug",
    "bottle",
    "stove",
    "sink",
    "kitchen counter",
    "toilet",
    "food container",
]

# Extended set: adds common egocentric objects observed in the long-session
# GT that the compact set cannot detect at all (laptop, headphones, phone).
EXTENDED = COMPACT + [
    "laptop",
    "desktop computer",
    "computer monitor",
    "headphones",
    "cellular phone",
    "chair",
    "table",
    "book",
    "keys",
    "glasses",
]

SHOE_WORDS = [word for word in COMPACT if word != "shoes"] + [
    "shoe",
    "sneaker",
    "sandal",
]

VARIANTS: dict[str, dict[str, Any]] = {
    "generic_yoloe_l": {
        "backend": "yoloe",
        "model": "yoloe-11l-seg.pt",
        "prompts": GENERIC,
        "conf": 0.45,
        "iou": 0.45,
    },
    "generic_yoloe_l_lowconf": {
        "backend": "yoloe",
        "model": "yoloe-11l-seg.pt",
        "prompts": GENERIC,
        "conf": 0.25,
        "iou": 0.45,
    },
    "compact_yoloe_l": {
        "backend": "yoloe",
        "model": "yoloe-11l-seg.pt",
        "prompts": COMPACT,
        "conf": 0.45,
        "iou": 0.45,
    },
    "compact_yoloe_m": {
        "backend": "yoloe",
        "model": "yoloe-11m-seg.pt",
        "prompts": COMPACT,
        "conf": 0.45,
        "iou": 0.45,
    },
    "compact_yoloe_lowconf": {
        "backend": "yoloe",
        "model": "yoloe-11l-seg.pt",
        "prompts": COMPACT,
        "conf": 0.30,
        "iou": 0.45,
    },
    "compact_world_m": {
        "backend": "world",
        "model": "yolov8m-worldv2.pt",
        "prompts": COMPACT,
        "conf": 0.45,
        "iou": 0.45,
    },
    "generic_world_m": {
        "backend": "world",
        "model": "yolov8m-worldv2.pt",
        "prompts": GENERIC,
        "conf": 0.45,
        "iou": 0.45,
    },
    "compact_world_l": {
        "backend": "world",
        "model": "yolov8l-worldv2.pt",
        "prompts": COMPACT,
        "conf": 0.45,
        "iou": 0.45,
    },
    "yoloe_very_lowconf": {
        "backend": "yoloe",
        "model": "yoloe-11l-seg.pt",
        "prompts": COMPACT,
        "conf": 0.12,
        "iou": 0.45,
    },
    "yoloe_lowconf_nms70": {
        "backend": "yoloe",
        "model": "yoloe-11l-seg.pt",
        "prompts": COMPACT,
        "conf": 0.20,
        "iou": 0.70,
    },
    "world_m_lowconf": {
        "backend": "world",
        "model": "yolov8m-worldv2.pt",
        "prompts": COMPACT,
        "conf": 0.20,
        "iou": 0.45,
    },
    "world_m_nms70": {
        "backend": "world",
        "model": "yolov8m-worldv2.pt",
        "prompts": COMPACT,
        "conf": 0.35,
        "iou": 0.70,
    },
    "world_shoe_words": {
        "backend": "world",
        "model": "yolov8m-worldv2.pt",
        "prompts": SHOE_WORDS,
        "conf": 0.30,
        "iou": 0.60,
    },
    "yoloe_shoe_words": {
        "backend": "yoloe",
        "model": "yoloe-11l-seg.pt",
        "prompts": SHOE_WORDS,
        "conf": 0.20,
        "iou": 0.60,
    },
    "world_l_lowconf": {
        "backend": "world",
        "model": "yolov8l-worldv2.pt",
        "prompts": COMPACT,
        "conf": 0.25,
        "iou": 0.60,
    },
    "sam3_compact": {
        "backend": "sam3",
        "model": "facebook/sam3",
        "prompts": COMPACT,
        "threshold": 0.5,
    },
    "sam3_core": {
        "backend": "sam3",
        "model": "facebook/sam3",
        "prompts": [
            "shoes",
            "storage cabinet",
            "hand",
            "cooking pot",
            "bowl",
            "basket",
            "garbage bag",
            "clothes",
        ],
        "threshold": 0.4,
    },
    "sam3_batched_compact": {
        "backend": "sam3",
        "model": "facebook/sam3",
        "prompts": COMPACT,
        "threshold": 0.5,
        "batched": True,
        "nms": 0.5,
    },
    "sam3_shoe_word": {
        "backend": "sam3",
        "model": "facebook/sam3",
        "prompts": ["shoe" if p == "shoes" else p for p in COMPACT],
        "label_map": {"shoe": "shoes"},
        "threshold": 0.2,
        "batched": True,
        "nms": 0.5,
    },
    "sam3_sneaker_word": {
        "backend": "sam3",
        "model": "facebook/sam3",
        "prompts": ["sneaker" if p == "shoes" else p for p in COMPACT],
        "label_map": {"sneaker": "shoes"},
        "threshold": 0.2,
        "batched": True,
        "nms": 0.5,
    },
    "sam3_shoe_family": {
        "backend": "sam3",
        "model": "facebook/sam3",
        "prompts": ["shoe" if p == "shoes" else p for p in COMPACT]
        + ["sneaker", "sandal"],
        "label_map": {"shoe": "shoes", "sneaker": "shoes", "sandal": "shoes"},
        "threshold": 0.2,
        "batched": True,
        "nms": 0.5,
    },
    "sam3_raw_low": {
        "backend": "sam3",
        "model": "facebook/sam3",
        "prompts": COMPACT,
        "threshold": 0.2,
        "batched": True,
        "nms": 0.5,
    },
    "sam3_extended": {
        "backend": "sam3",
        "model": "facebook/sam3",
        "prompts": EXTENDED,
        "threshold": 0.2,
        "batched": True,
        "nms": 0.5,
    },
    "sam3_flip_tta": {
        "backend": "sam3",
        "model": "facebook/sam3",
        "prompts": COMPACT,
        "threshold": 0.2,
        "batched": True,
        "nms": 0.5,
        "flip_tta": True,
    },
    "sam3_t06": {
        "backend": "sam3",
        "model": "facebook/sam3",
        "prompts": [
            "shoes",
            "storage cabinet",
            "hand",
            "cooking pot",
            "bowl",
            "basket",
            "garbage bag",
            "clothes",
        ],
        "threshold": 0.6,
        "nms": 0.5,
    },
    "sam3_t07": {
        "backend": "sam3",
        "model": "facebook/sam3",
        "prompts": [
            "shoes",
            "storage cabinet",
            "hand",
            "cooking pot",
            "bowl",
            "basket",
            "garbage bag",
            "clothes",
        ],
        "threshold": 0.7,
        "nms": 0.5,
    },
    "sam3_t05_nms06": {
        "backend": "sam3",
        "model": "facebook/sam3",
        "prompts": [
            "shoes",
            "storage cabinet",
            "hand",
            "cooking pot",
            "bowl",
            "basket",
            "garbage bag",
            "clothes",
        ],
        "threshold": 0.5,
        "nms": 0.6,
    },
}


@app.function(
    image=PERCEPTION_IMAGE,
    volumes={MODEL_MOUNT: model_cache_volume},
    secrets=SECRETS,
    gpu="L4",
    timeout=1800,
)
def detect(
    images_b64: list[tuple[str, str]], variant: dict[str, Any]
) -> dict[str, list[dict[str, Any]]]:
    """Load one detector once, predict over all benchmark images."""

    import shutil

    import cv2
    import numpy as np
    from ultralytics import YOLO, YOLOWorld

    model_dir = Path(MODEL_MOUNT) / "yolo"
    model_dir.mkdir(parents=True, exist_ok=True)
    os.environ["YOLO_CONFIG_DIR"] = str(model_dir)
    name = variant["model"]
    cached = model_dir / name
    model_class = YOLO if variant["backend"] == "yoloe" else YOLOWorld
    if cached.exists():
        model = model_class(str(cached))
    else:
        model = model_class(name)
        if Path(name).exists():
            shutil.copy2(name, cached)

    model.set_classes(list(variant["prompts"]))
    result: dict[str, list[dict[str, Any]]] = {}
    for image_id, encoded in images_b64:
        image = cv2.imdecode(
            np.frombuffer(base64.b64decode(encoded), dtype=np.uint8), cv2.IMREAD_COLOR
        )
        output = model.predict(
            [image],
            conf=float(variant["conf"]),
            iou=float(variant["iou"]),
            verbose=False,
            retina_masks=True,
        )[0]
        boxes: list[dict[str, Any]] = []
        if output.boxes is not None:
            for index in range(len(output.boxes)):
                class_id = int(output.boxes.cls[index].item())
                label = (
                    variant["prompts"][class_id]
                    if class_id < len(variant["prompts"])
                    else str(getattr(output, "names", {}).get(class_id, class_id))
                )
                boxes.append(
                    {
                        "label": label,
                        "bbox": [float(v) for v in output.boxes.xyxy[index].tolist()],
                        "conf": round(float(output.boxes.conf[index].item()), 4),
                    }
                )
        result[image_id] = boxes
    model_cache_volume.commit()
    return result


@app.function(
    image=SAM3_IMAGE,
    volumes={MODEL_MOUNT: model_cache_volume},
    secrets=SECRETS,
    gpu="L4",
    timeout=3600,
)
def detect_sam3(
    images_b64: list[tuple[str, str]], variant: dict[str, Any]
) -> dict[str, list[dict[str, Any]]]:
    """Promptable Concept Segmentation: one text prompt at a time, per image."""

    import io

    import torch
    from PIL import Image
    from transformers import Sam3Model, Sam3Processor

    device = "cuda" if torch.cuda.is_available() else "cpu"
    os.environ["HF_HOME"] = f"{MODEL_MOUNT}/huggingface"
    model = Sam3Model.from_pretrained("facebook/sam3", device_map=device).to(
        device, dtype=torch.bfloat16
    )
    processor = Sam3Processor.from_pretrained("facebook/sam3")
    threshold = float(variant.get("threshold", 0.5))
    result: dict[str, list[dict[str, Any]]] = {}
    prompts = list(variant["prompts"])

    def batched_boxes(image: Image.Image) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        inputs = processor(
            images=[image] * len(prompts), text=prompts, return_tensors="pt"
        ).to(device)
        with torch.no_grad():
            outputs = model(**inputs)
        processed_all = processor.post_process_instance_segmentation(
            outputs,
            threshold=threshold,
            mask_threshold=0.5,
            target_sizes=inputs["original_sizes"].tolist(),
        )
        for prompt, processed in zip(prompts, processed_all, strict=True):
            for box, score in zip(processed["boxes"], processed["scores"], strict=True):
                found.append(
                    {
                        "label": variant.get("label_map", {}).get(prompt, prompt),
                        "bbox": [float(value) for value in box.tolist()],
                        "conf": round(float(score), 4),
                    }
                )
        return found

    for image_id, encoded in images_b64:
        image = Image.open(io.BytesIO(base64.b64decode(encoded))).convert("RGB")
        boxes: list[dict[str, Any]] = []
        if variant.get("batched"):
            boxes += batched_boxes(image)
            if variant.get("flip_tta"):
                width = image.width
                flipped = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                for box in batched_boxes(flipped):
                    x1, y1, x2, y2 = box["bbox"]
                    box["bbox"] = [width - x2, y1, width - x1, y2]
                    boxes.append(box)
        else:
            for prompt in prompts:
                inputs = processor(images=image, text=prompt, return_tensors="pt").to(
                    device
                )
                with torch.no_grad():
                    outputs = model(**inputs)
                processed = processor.post_process_instance_segmentation(
                    outputs,
                    threshold=threshold,
                    mask_threshold=0.5,
                    target_sizes=inputs["original_sizes"].tolist(),
                )[0]
                for box, score in zip(
                    processed["boxes"], processed["scores"], strict=True
                ):
                    boxes.append(
                        {
                            "label": variant.get("label_map", {}).get(prompt, prompt),
                            "bbox": [float(value) for value in box.tolist()],
                            "conf": round(float(score), 4),
                        }
                    )
        result[image_id] = boxes
    model_cache_volume.commit()
    return result


def iou(first: list[float], second: list[float]) -> float:
    ix1 = max(first[0], second[0])
    iy1 = max(first[1], second[1])
    ix2 = min(first[2], second[2])
    iy2 = min(first[3], second[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(0.0, first[2] - first[0]) * max(0.0, first[3] - first[1])
    area_b = max(0.0, second[2] - second[0]) * max(0.0, second[3] - second[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def class_nms(
    predictions: list[dict[str, Any]], threshold: float = 0.5
) -> list[dict[str, Any]]:
    """Greedy per-class NMS; SAM3 emits many overlapping part/duplicate boxes."""

    from aegis.core.vocabulary import default_vocabulary

    vocab = default_vocabulary()
    labels = {vocab.canonical(pred["label"]) for pred in predictions}
    kept: list[dict[str, Any]] = []
    for label in sorted(labels):
        group = sorted(
            (pred for pred in predictions if vocab.canonical(pred["label"]) == label),
            key=lambda pred: float(pred["conf"]),
            reverse=True,
        )
        survivors: list[dict[str, Any]] = []
        for pred in group:
            if all(iou(pred["bbox"], other["bbox"]) < threshold for other in survivors):
                survivors.append(pred)
        kept.extend(survivors)
    return kept


def score(
    bench: dict[str, Any], predictions: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    from aegis.core.vocabulary import default_vocabulary

    vocab = default_vocabulary()
    threshold = float(bench["iou_threshold"])
    per_class: dict[str, dict[str, int]] = {}
    total_tp = total_fp = total_gt = 0
    misses: list[dict[str, Any]] = []
    false_positives: list[dict[str, Any]] = []
    for image in bench["images"]:
        image_id = image["id"]
        preds = list(predictions.get(image_id, []))
        used: set[int] = set()
        for item in image["objects"]:
            expected = vocab.canonical(item["label"])
            bucket = per_class.setdefault(expected, {"tp": 0, "fp": 0, "fn": 0})
            total_gt += 1
            candidates = [
                (iou(item["bbox"], pred["bbox"]), index)
                for index, pred in enumerate(preds)
                if index not in used and vocab.canonical(pred["label"]) == expected
            ]
            best = max(candidates, default=(0.0, -1))
            if best[0] >= threshold:
                used.add(best[1])
                bucket["tp"] += 1
                total_tp += 1
            else:
                bucket["fn"] += 1
                misses.append(
                    {"image": image_id, "label": expected, "bbox": item["bbox"]}
                )
        for index, pred in enumerate(preds):
            if index in used:
                continue
            label = vocab.canonical(pred["label"])
            per_class.setdefault(label, {"tp": 0, "fp": 0, "fn": 0})["fp"] += 1
            total_fp += 1
            false_positives.append(
                {"image": image_id, "label": label, "conf": pred["conf"]}
            )
    precision = total_tp / (total_tp + total_fp) if total_tp + total_fp else 0.0
    recall = total_tp / total_gt if total_gt else 0.0
    for bucket in per_class.values():
        tp, fp, fn = bucket["tp"], bucket["fp"], bucket["fn"]
        bucket["precision"] = round(tp / (tp + fp), 3) if tp + fp else 0.0
        bucket["recall"] = round(tp / (tp + fn), 3) if tp + fn else 0.0
    return {
        "tp": total_tp,
        "fp": total_fp,
        "fn": total_gt - total_tp,
        "ground_truth": total_gt,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(2 * precision * recall / (precision + recall), 4)
        if precision + recall
        else 0.0,
        "fp_per_image": round(total_fp / len(bench["images"]), 2),
        "per_class": dict(sorted(per_class.items())),
        "misses": misses,
        "false_positives": false_positives,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bench", default="evaluation/annotations/detection_bench.json"
    )
    parser.add_argument(
        "--variants", default="generic_yoloe_l,compact_yoloe_l,compact_world_m"
    )
    parser.add_argument("--dump-detections", action="store_true")
    parser.add_argument("--out", default="/tmp/opencode/detector_bench/report.json")
    args = parser.parse_args()

    bench = json.loads(Path(args.bench).read_text(encoding="utf-8"))
    images = [
        (item["id"], base64.b64encode(Path(item["path"]).read_bytes()).decode())
        for item in bench["images"]
    ]
    names = ["all"] if args.variants == "all" else args.variants.split(",")
    if names == ["all"]:
        names = list(VARIANTS)
    unknown = set(names) - set(VARIANTS)
    if unknown:
        raise SystemExit(f"unknown variants: {sorted(unknown)}")

    report: dict[str, Any] = {
        "bench": str(args.bench),
        "n_images": len(images),
        "iou_threshold": bench["iou_threshold"],
        "variants": {},
    }
    with app.run():
        for name in names:
            variant = VARIANTS[name]
            print(
                f"[bench] running {name}: {variant['model']} / "
                f"{len(variant['prompts'])} prompts / "
                f"threshold {variant.get('conf', variant.get('threshold'))}"
            )
            raw = (
                detect_sam3.remote(images, variant)
                if variant["backend"] == "sam3"
                else detect.remote(images, variant)
            )
            refined = {
                image_id: class_nms(boxes, float(variant.get("nms", 0.5)))
                for image_id, boxes in raw.items()
            }
            scored = score(bench, refined)
            by_video: dict[str, Any] = {}
            for video in sorted({item.get("video", "") for item in bench["images"]}):
                subset = {
                    **bench,
                    "images": [
                        item for item in bench["images"] if item.get("video") == video
                    ],
                }
                ids = {item["id"] for item in subset["images"]}
                by_video[video] = score(
                    subset, {key: value for key, value in refined.items() if key in ids}
                )
            report["variants"][name] = {
                "config": variant,
                "metrics": scored,
                "by_video": by_video,
            }
            if args.dump_detections:
                report["variants"][name]["detections"] = raw
                report["variants"][name]["detections_nms"] = refined
            print(
                f"  P={scored['precision']:.3f} R={scored['recall']:.3f} "
                f"F1={scored['f1']:.3f} FP/img={scored['fp_per_image']:.1f} "
                f"shoes R={scored['per_class'].get('shoes', {}).get('recall', 0)}"
            )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"[bench] wrote {out}")


if __name__ == "__main__":
    main()
