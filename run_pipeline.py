"""Modal CLI entrypoint for the Aegis spatio-temporal memory pipeline.

Accepts any input video (local file, URL, or egocentric dataset benchmark preset),
inhabits open-vocabulary 3D scene perception and R4DSG memory generation, and
downloads structured artifacts locally for the mobile app and Rerun visualizer.

Usage examples:
    # 1. Run on any local video file:
    uv run python run_pipeline.py --video /path/to/my_video.mp4 --dataset-id kitchen_eval

    # 2. Run on a remote egocentric URL:
    uv run python run_pipeline.py --video "https://.../video.mp4" --dataset-id living_room

    # 3. Run on an egocentric benchmark preset (e.g. sort_clothes, make_coffee, arrange_pots):
    uv run python run_pipeline.py --video sort_clothes

    # 4. Standard Modal CLI invocation:
    uv run modal run run_pipeline.py --dataset-id demo01 --stage all
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from aegis.core.config import RuntimeConfig, config_to_dict, load_config
from aegis.ingestion.download import (
    EGOCENTRIC_PRESETS,
    ingest_video,
    upload_to_modal_volume,
)
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

COMPREHENSIVE_INDOOR_CLASSES = [
    # Spatial anchors (furniture & surfaces)
    "cabinet",
    "storage cabinet",
    "shelf",
    "cupboard",
    "refrigerator",
    "fridge",
    "sink",
    "counter",
    "kitchen counter",
    "table",
    "dining table",
    "desk",
    "drawer",
    "chair",
    "couch",
    "sofa",
    "bed",
    # Kitchen & dining objects
    "cooking pot",
    "pot",
    "pan",
    "bowl",
    "plate",
    "dish",
    "cup",
    "mug",
    "water bottle",
    "bottle",
    "fork",
    "spoon",
    "knife",
    "food",
    # Personal & daily assistive objects
    "shoes",
    "shoe",
    "slippers",
    "keys",
    "keychain",
    "glasses",
    "reading glasses",
    "sunglasses",
    "cell phone",
    "phone",
    "wallet",
    "purse",
    "backpack",
    "bag",
    "book",
    "laptop",
    "remote control",
    "medicine",
    "pill bottle",
    # Household & clothing
    "clothes",
    "shirt",
    "pants",
    "towel",
    "trash bin",
    "wastebasket",
    # Interaction
    "hand",
    "human hand",
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
    video: str | None = None,
    classes: str | None = None,
    sample_fps: int | None = None,
    keyframe_stride: int | None = None,
    stage: Stage = "all",
    upload: bool = True,
) -> None:
    """Submit one pipeline stage or the complete sequential pipeline to Modal.

    Parameters
    ----------
    config_path : str
        Path to pipeline YAML configuration.
    dataset_id : str
        Dataset identifier (e.g. demo01, demo03, my_kitchen).
    video : str | None
        Input video file path, URL, or egocentric preset (e.g. 'sort_clothes', 'make_coffee').
    classes : str | None
        Comma-separated open-vocabulary target object classes.
    sample_fps : int | None
        Optional sample FPS override.
    keyframe_stride : int | None
        Optional keyframe stride override for 3D reconstruction.
    stage : Stage
        Pipeline stage to run ('all', 'preprocess', 'vggt', 'detect', 'rerun').
    upload : bool
        Whether to ensure input video is uploaded to the Modal volume.
    """
    config = load_config(config_path)
    _validate_modal_mounts(config)
    serialized_config = config_to_dict(config)

    # 1. Ingest input video if provided
    if video:
        # Auto-infer dataset_id if left as default demo01
        inferred_id = dataset_id if dataset_id != "demo01" else None
        if not inferred_id and video in EGOCENTRIC_PRESETS:
            inferred_id = f"demo_{video}"
        ingest_res = ingest_video(
            video,
            dataset_id=inferred_id or dataset_id,
            upload_to_modal=upload,
            modal_volume=DATA_VOLUME_NAME,
        )
        dataset_id = ingest_res["dataset_id"]
    elif upload:
        # Check if local video exists in data/<dataset_id>/video.mp4 and sync
        local_video = Path("data") / dataset_id / "video.mp4"
        if local_video.exists():
            upload_to_modal_volume(
                local_video, f"{dataset_id}/video.mp4", volume_name=DATA_VOLUME_NAME
            )

    # 2. Configure target classes for perception
    if classes:
        parsed_classes = [c.strip().lower() for c in classes.split(",") if c.strip()]
        if parsed_classes:
            serialized_config["perception"]["target_classes"] = parsed_classes
            print(
                f"Custom perception target classes configured: {', '.join(parsed_classes)}"
            )
    elif dataset_id != "demo01":
        # For non-demo01 videos, default to comprehensive indoor daily living classes
        existing_targets = list(
            serialized_config["perception"].get("target_classes", [])
        )
        merged = list(dict.fromkeys(existing_targets + COMPREHENSIVE_INDOOR_CLASSES))
        serialized_config["perception"]["target_classes"] = merged

    # 3. Apply optional runtime overrides
    if sample_fps is not None and sample_fps > 0:
        serialized_config["video"]["sample_fps"] = sample_fps
        print(f"Sample FPS overridden to: {sample_fps}")
    if keyframe_stride is not None and keyframe_stride > 0:
        serialized_config["vggt"]["keyframe_stride"] = keyframe_stride
        print(f"Keyframe stride overridden to: {keyframe_stride}")

    # 4. Inject Hugging Face token for gated models
    token = (
        os.getenv("HF_TOKEN")
        or os.getenv("HUGGING_FACE_HUB_TOKEN")
        or os.getenv("hf_token")
    )
    if not token:
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

    print("\n" + "=" * 80)
    print("  🛡️  AEGIS SPATIO-TEMPORAL MEMORY PIPELINE — LAUNCHING")
    print("=" * 80)
    print(f"  • Dataset ID:    {dataset_id}")
    print(f"  • Target Stage:  {stage}")
    print(f"  • Data Volume:   {DATA_VOLUME_NAME}")
    print(
        f"  • Target Classes: {len(serialized_config['perception']['target_classes'])} classes"
    )
    print("=" * 80 + "\n")

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
    header = (
        f"{'Stage':<18} | {'Duration (s)':<12} | {'Peak VRAM (GB)':<14} | {'Details'}"
    )
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

    local_root = Path("outputs")
    local_root.mkdir(parents=True, exist_ok=True)

    paths_to_fetch = [
        (f"{dataset_id}/outputs/viewer/demo.rrd", local_root / "demo.rrd"),
        (
            f"{dataset_id}/outputs/viewer/demo.rrd",
            local_root / dataset_id / "viewer" / "demo.rrd",
        ),
        (
            f"{dataset_id}/outputs/benchmark_stats.json",
            local_root / "benchmark_stats.json",
        ),
        (
            f"{dataset_id}/outputs/benchmark_stats.json",
            local_root / dataset_id / "benchmark_stats.json",
        ),
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

    print("\n" + "=" * 80)
    print("  🚀 READY FOR LIVE DEMO & VISUALIZATION")
    print("=" * 80)
    print(
        f"  • View 3D Scene Graph in Rerun:  rerun outputs/{dataset_id}/viewer/demo.rrd"
    )
    print(
        f"  • Start Mobile Backend Server:   uv run python run_server.py --dataset-id {dataset_id}"
    )
    print(
        f"  • Mobile API Health Endpoint:   http://localhost:8000/api/v1/health?dataset_id={dataset_id}"
    )
    print("=" * 80 + "\n")


if __name__ == "__main__":
    import argparse
    import subprocess
    import sys

    parser = argparse.ArgumentParser(
        description="Aegis Spatio-Temporal Pipeline Runner"
    )
    parser.add_argument(
        "--video",
        type=str,
        default=None,
        help="Input video file path, URL, or preset key",
    )
    parser.add_argument(
        "--dataset-id",
        type=str,
        default="demo01",
        help="Dataset identifier (e.g. demo01, demo03, my_room)",
    )
    parser.add_argument(
        "--classes",
        type=str,
        default=None,
        help="Comma-separated target classes for perception",
    )
    parser.add_argument(
        "--sample-fps", type=int, default=None, help="Frame sampling rate (FPS)"
    )
    parser.add_argument(
        "--keyframe-stride",
        type=int,
        default=None,
        help="Keyframe stride for 3D reconstruction",
    )
    parser.add_argument(
        "--stage",
        type=str,
        default="all",
        help="Pipeline stage (all, preprocess, vggt, detect, rerun)",
    )
    parser.add_argument(
        "--config-path",
        type=str,
        default="config/demo.yaml",
        help="Path to config YAML",
    )
    args = parser.parse_args()

    # Dispatch to modal run
    cli_cmd = [
        sys.executable,
        "-m",
        "modal",
        "run",
        "run_pipeline.py",
        "--dataset-id",
        args.dataset_id,
        "--stage",
        args.stage,
        "--config-path",
        args.config_path,
    ]
    if args.video:
        cli_cmd.extend(["--video", args.video])
    if args.classes:
        cli_cmd.extend(["--classes", args.classes])
    if args.sample_fps:
        cli_cmd.extend(["--sample-fps", str(args.sample_fps)])
    if args.keyframe_stride:
        cli_cmd.extend(["--keyframe-stride", str(args.keyframe_stride)])

    sys.exit(subprocess.run(cli_cmd, check=False).returncode)
