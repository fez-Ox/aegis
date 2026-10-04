"""Modal CLI entrypoint for the Aegis geometry pipeline.

Run from the repository root with, for example::

    uv run modal run run_pipeline.py --dataset-id demo01 --stage all

The local entrypoint only submits sequential remote jobs. Video decoding,
model inference, point-cloud construction, and Rerun logging all execute in
Modal containers.
"""

from __future__ import annotations

from typing import Any, Literal

from aegis.core.config import RuntimeConfig, config_to_dict, load_config
from aegis.remote.modal_app import (
    DATA_MOUNT,
    DATA_VOLUME_NAME,
    MODEL_CACHE_VOLUME_NAME,
    MODEL_MOUNT,
    app,
    detect_and_lift_remote,
    preprocess_video_remote,
    rerun_remote,
    vggt_reconstruct_remote,
)

Stage = Literal[
    "preprocess",
    "vggt",
    "dust3r",
    "reconstruct",
    "detect",
    "objects",
    "rerun",
    "memory",
    "detect_and_rerun",
    "all",
]


def _validate_modal_mounts(config: RuntimeConfig) -> None:
    if config.storage.data_volume != DATA_VOLUME_NAME:
        raise ValueError(
            "config storage.data_volume does not match AEGIS_DATA_VOLUME / "
            f"Modal app volume ({DATA_VOLUME_NAME!r})"
        )
    if config.storage.model_cache_volume != MODEL_CACHE_VOLUME_NAME:
        raise ValueError(
            "config storage.model_cache_volume does not match "
            "AEGIS_MODEL_CACHE_VOLUME / Modal app volume "
            f"({MODEL_CACHE_VOLUME_NAME!r})"
        )
    if config.storage.data_mount != DATA_MOUNT:
        raise ValueError(f"storage.data_mount must remain {DATA_MOUNT!r}")
    if config.storage.model_mount != MODEL_MOUNT:
        raise ValueError(f"storage.model_mount must remain {MODEL_MOUNT!r}")


@app.local_entrypoint()
def main(
    config_path: str = "config/demo.yaml",
    dataset_id: str = "demo01",
    stage: Stage = "all",
) -> None:
    """Submit one pipeline stage or the complete sequential pipeline to Modal."""

    config = load_config(config_path)
    _validate_modal_mounts(config)
    serialized_config = config_to_dict(config)

    # Inject Hugging Face token for gated models (e.g. facebook/VGGT-Omega)
    import os
    token = (
        os.getenv("HF_TOKEN")
        or os.getenv("HUGGING_FACE_HUB_TOKEN")
        or os.getenv("hf_token")
    )
    if not token:
        from pathlib import Path

        env_path = Path(".env")
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if "=" in line and ("token" in line.lower() or "hf" in line.lower()):
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if "hf" in k.lower() and v.startswith("hf_"):
                        token = v
                        break
    if token:
        serialized_config["hf_token"] = token

    valid_stages = {
        "preprocess",
        "vggt",
        "dust3r",
        "reconstruct",
        "detect",
        "objects",
        "rerun",
        "memory",
        "detect_and_rerun",
        "all",
    }
    if stage not in valid_stages:
        raise ValueError(f"unknown stage: {stage}")

    results: list[dict[str, Any]] = []

    # Step 1: Preprocess video frames
    if stage in {"preprocess", "all"}:
        results.append(preprocess_video_remote.remote(dataset_id, serialized_config))

    # Step 2: 3D Scene Reconstruction (VGGT-Ω)
    if stage in {"vggt", "dust3r", "reconstruct", "all"}:
        results.append(vggt_reconstruct_remote.remote(dataset_id, serialized_config))

    # Step 3: 2D Object Perception and 3D Bounding Box Lifting
    if stage in {"detect", "objects", "memory", "detect_and_rerun", "all"}:
        results.append(detect_and_lift_remote.remote(dataset_id, serialized_config))

    # Final Step: Build Rerun 4D visualization recording
    if stage in {"rerun", "memory", "detect_and_rerun", "all"}:
        results.append(rerun_remote.remote(dataset_id, serialized_config))

    _print_benchmark_summary(results)
    _download_outputs(dataset_id)


def _print_benchmark_summary(results: list[dict[str, Any]]) -> None:
    """Print an aligned execution report of runtime and VRAM statistics."""
    print("\n" + "=" * 80)
    print("                AEGIS PIPELINE EXECUTION & BENCHMARK REPORT")
    print("=" * 80)
    header = f"{'Stage':<18} | {'Duration (s)':<12} | {'Peak VRAM (GB)':<14} | {'Details'}"
    print(header)
    print("-" * 80)
    total_time = 0.0
    for res in results:
        stage = str(res.get("stage", "unknown"))
        duration = float(res.get("elapsed_seconds", 0.0))
        total_time += duration
        vram = res.get("peak_vram_gb", "-")
        vram_str = f"{vram} GB" if isinstance(vram, (int, float)) and vram > 0 else "-"

        details = []
        if "throughput_fps" in res:
            details.append(f"{res['throughput_fps']} FPS")
        if "gpu_device" in res and res["gpu_device"] != "CPU":
            details.append(f"{res['gpu_device']}")
        if "point_count" in res:
            details.append(f"{res['point_count']:,} pts")
        if "detections_2d" in res:
            details.append(f"{res['detections_2d']} det2d")
        if "sam2_masks_generated" in res:
            details.append(f"{res['sam2_masks_generated']} masks")
        if "boxes_3d" in res:
            details.append(f"{res['boxes_3d']} box3d")
        if "tracks" in res:
            details.append(f"{res['tracks']} tracks")
        if "events" in res:
            details.append(f"{res['events']} events")
        if "recording_size_mb" in res:
            details.append(f"{res['recording_size_mb']} MB rrd")

        detail_str = ", ".join(details)
        print(f"{stage:<18} | {duration:<12.2f} | {vram_str:<14} | {detail_str}")
    print("-" * 80)
    print(f"{'Total Pipeline':<18} | {total_time:<12.2f} | {'':<14} | Complete")
    print("=" * 80 + "\n")


def _download_outputs(dataset_id: str) -> None:
    """Download key artifacts (.rrd, benchmark_stats.json, scene graph) to local outputs/."""
    import subprocess
    import sys
    from pathlib import Path

    local_root = Path("outputs")
    local_root.mkdir(parents=True, exist_ok=True)

    paths_to_fetch = [
        (f"{dataset_id}/outputs/viewer/demo.rrd", local_root / "demo.rrd"),
        (f"{dataset_id}/outputs/viewer/demo.rrd", local_root / dataset_id / "viewer" / "demo.rrd"),
        (f"{dataset_id}/outputs/benchmark_stats.json", local_root / "benchmark_stats.json"),
        (f"{dataset_id}/outputs/benchmark_stats.json", local_root / dataset_id / "benchmark_stats.json"),
        (
            f"{dataset_id}/outputs/objects/detected_objects_3d.json",
            local_root / dataset_id / "objects" / "detected_objects_3d.json",
        ),
        (
            f"{dataset_id}/outputs/objects/r4d_scene_graph.json",
            local_root / dataset_id / "objects" / "r4d_scene_graph.json",
        ),
        (
            f"{dataset_id}/outputs/objects/events.json",
            local_root / dataset_id / "objects" / "events.json",
        ),
        (
            f"{dataset_id}/outputs/geometry/poses.json",
            local_root / dataset_id / "geometry" / "poses.json",
        ),
    ]

    print("\n--- Syncing Artifacts from Modal Volume to Local ---")
    for remote_path, local_dest in paths_to_fetch:
        local_dest.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            sys.executable,
            "-m",
            "modal",
            "volume",
            "get",
            "aegis-poc-data",
            remote_path,
            str(local_dest),
            "--force",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode == 0 and local_dest.exists():
            sz_mb = round(local_dest.stat().st_size / (1024**2), 2)
            print(f"  ✓ Downloaded {remote_path} -> {local_dest} ({sz_mb} MB)")
        else:
            print(
                f"  ⚠ Could not download {remote_path}: {res.stderr.strip() or res.stdout.strip()}"
            )

