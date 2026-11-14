"""P5: largest VGGT-Omega window that fits the L4 (sets vggt.max_keyframes).

Runs on Modal. Reconstructs the first N keyframes of one dataset for each
N, recording seconds, peak VRAM and out-of-memory failures, plus pipeline
seconds per second of video. Choose vggt.max_keyframes and
live.segment_frames as the largest N with peak VRAM <= 85% of the GPU.

Usage:
    uv run modal run scripts/measure_vggt_window.py --dataset-id <long dataset> \
        --sizes 32,64,96,120,160
"""

from __future__ import annotations

import json
from typing import Any

from aegis.core.config import config_to_dict, load_config
from aegis.remote.modal_app import (
    DATA_MOUNT,
    MODEL_MOUNT,
    SECRETS,
    VGGT_IMAGE,
    app,
    data_volume,
    model_cache_volume,
)


@app.function(
    image=VGGT_IMAGE,
    gpu="L4",
    volumes={DATA_MOUNT: data_volume, MODEL_MOUNT: model_cache_volume},
    secrets=SECRETS,
    memory=24576,
    timeout=7200,
)
def measure(
    dataset_id: str, raw_config: dict[str, Any], sizes: list[int]
) -> dict[str, Any]:
    import time

    import torch

    from aegis.core.config import RuntimeConfig
    from aegis.core.paths import dataset_paths
    from aegis.geometry.vggt_runner import load_model, run_vggt_reconstruction

    config = RuntimeConfig.from_mapping(raw_config)
    paths = dataset_paths(config, dataset_id)
    metadata = json.loads(paths.metadata.read_text())
    frames = metadata["frames"][:: config.vggt.keyframe_stride]
    model = load_model(config.vggt, hf_token=raw_config.get("hf_token"))
    total_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
    rows = []
    for size in sizes:
        chunk = frames[:size]
        if len(chunk) < size:
            rows.append({"keyframes": size, "skipped": "dataset too short"})
            continue
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        start = time.perf_counter()
        try:
            run_vggt_reconstruction(
                [paths.frames / f["filename"] for f in chunk], config.vggt, model=model
            )
            ok = True
        except torch.cuda.OutOfMemoryError:
            ok = False
        seconds = time.perf_counter() - start
        peak = torch.cuda.max_memory_allocated() / 1024**3
        video_seconds = float(chunk[-1]["timestamp"]) - float(chunk[0]["timestamp"])
        rows.append(
            {
                "keyframes": size,
                "ok": ok,
                "seconds": round(seconds, 2),
                "peak_vram_gb": round(peak, 2),
                "vram_fraction": round(peak / total_gb, 3),
                "pipeline_seconds_per_video_second": (
                    round(seconds / video_seconds, 3)
                    if ok and video_seconds > 0
                    else None
                ),
            }
        )
    fitting = [
        r["keyframes"] for r in rows if r.get("ok") and r["vram_fraction"] <= 0.85
    ]
    return {
        "gpu_total_gb": round(total_gb, 2),
        "rows": rows,
        "recommended_max_keyframes": max(fitting) if fitting else None,
    }


@app.local_entrypoint()
def main(
    dataset_id: str,
    sizes: str = "32,64,96,120,160",
    config_path: str = "config/live.yaml",
) -> None:
    result = measure.remote(
        dataset_id,
        config_to_dict(load_config(config_path)),
        [int(s) for s in sizes.split(",")],
    )
    print(json.dumps(result, indent=2))
