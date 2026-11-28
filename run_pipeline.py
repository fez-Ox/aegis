"""Modal CLI entrypoint for the Aegis spatio-temporal memory pipeline.

Accepts any input video (local file, URL, or egocentric dataset benchmark preset),
inhabits open-vocabulary 3D scene perception and R4DSG memory generation, and
keeps structured artifacts on the Modal volume by default (use --download only
for local Rerun/home-store demos).

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

import json
import os
from pathlib import Path
from typing import Any, Literal

from aegis.core.config import RuntimeConfig, config_to_dict, load_config
from aegis.ingestion.download import (
    EGOCENTRIC_PRESETS,
    ingest_video,
    upload_dataset_to_modal_volume,
    upload_to_modal_volume,
)
from aegis.ingestion.live_handoff import (
    find_latest_live_session,
    promote_live_session,
)
from aegis.remote.modal_app import (
    CPU_ONLY,
    DATA_MOUNT,
    DATA_VOLUME_NAME,
    GPU_TYPE,
    MODEL_CACHE_VOLUME_NAME,
    MODEL_MOUNT,
    Perception,
    Reconstructor,
    app,
    preprocess_video_remote,
    rerun_remote,
)

Stage = Literal[
    "live",
    "preprocess",
    "vggt",
    "reconstruct",
    "detect",
    "objects",
    "rerun",
    "memory",
    "detect_and_rerun",
    "full",
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
    video: str | None = None,
    live_session: str | None = None,
    classes: str | None = None,
    sample_fps: int | None = None,
    keyframe_stride: int | None = None,
    vggt_model: str | None = None,
    stage: Stage = "all",
    upload: bool = True,
    recorded_at: str | None = None,
    home_id: str | None = None,
    no_ingest: bool = False,
    segment_frames: int | None = None,
    follow: bool = False,
    keep_frames: bool = False,
    rerun: bool = False,
    download: bool = False,
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
    live_session : str | None
        Local ``captures/<session_id>`` directory, or ``latest``.
    classes : str | None
        Comma-separated open-vocabulary target object classes.
    sample_fps : int | None
        Optional sample FPS override.
    keyframe_stride : int | None
        Optional keyframe stride override for 3D reconstruction.
    vggt_model : str | None
        Optional Hugging Face repo id override for the VGGT-Ω checkpoint
        (for example a public mirror when the official repo is gated).
    stage : Stage
        Pipeline stage to run ('all', 'live', 'preprocess', 'vggt', 'detect', 'rerun').
    upload : bool
        Whether to ensure input video / promoted dataset is uploaded.
    """
    config = load_config(config_path)
    _validate_modal_mounts(config)
    serialized_config = config_to_dict(config)

    if video and live_session:
        raise ValueError("choose either --video or --live-session, not both")

    # 0. Promote a live capture session into the canonical dataset layout.
    live_path: Path | None = None
    if live_session or stage == "live":
        if live_session and live_session != "latest":
            live_path = Path(live_session)
        else:
            live_path = find_latest_live_session(Path("captures"))
        if live_path is None or not live_path.is_dir():
            raise FileNotFoundError(
                "no live session found; pass --live-session captures/<session_id> "
                "or run aegis-ingest first"
            )
        if dataset_id == "demo01":
            inferred = f"live_{live_path.name}".lower()
            dataset_id = "".join(
                c if (c.isalnum() or c in "._-") else "_" for c in inferred
            )
        frames_per_segment = (
            config.live.segment_frames if segment_frames is None else segment_frames
        )
        if frames_per_segment > 0 and stage == "live":
            _run_live_segmented(
                live_path,
                base_dataset_id=dataset_id,
                segment_frames=frames_per_segment,
                config=config,
                serialized_config=_finalise_config(
                    serialized_config, classes, sample_fps, keyframe_stride
                ),
                upload=upload,
                home_id=home_id or config.memory.home_id,
                ingest=not no_ingest,
                follow=follow,
                keep_frames=keep_frames,
                rerun=rerun,
                download=download,
            )
            return
        promotion = promote_live_session(
            live_path,
            dataset_id=dataset_id,
            video=config.video,
            camera=config.camera,
        )
        print(
            f"Promoted live session {promotion.session_id} -> "
            f"{promotion.dataset_dir} ({promotion.frame_count} frames, "
            f"{promotion.duration_sec:.1f}s, {promotion.gap_count} gaps)"
        )
        if upload:
            upload_dataset_to_modal_volume(
                promotion.dataset_dir, dataset_id, DATA_VOLUME_NAME
            )

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
    elif upload and live_path is None:
        # Check if local video exists in data/<dataset_id>/video.mp4 and sync
        local_video = Path("data") / dataset_id / "video.mp4"
        if local_video.exists():
            upload_to_modal_volume(
                local_video, f"{dataset_id}/video.mp4", volume_name=DATA_VOLUME_NAME
            )

    # 1b. Wall-clock start of a batch video (live sessions carry their own).
    if recorded_at:
        from aegis.ingestion.download import set_recorded_at

        metadata_path = set_recorded_at(Path("data") / dataset_id, recorded_at)
        print(f"Recorded-at time stored in {metadata_path}")
        if upload:
            upload_to_modal_volume(
                metadata_path,
                f"{dataset_id}/source_metadata.json",
                volume_name=DATA_VOLUME_NAME,
            )

    # 2. Configure target classes for perception
    if classes:
        parsed_classes = [c.strip().lower() for c in classes.split(",") if c.strip()]
        if parsed_classes:
            serialized_config["perception"]["target_classes"] = parsed_classes
            print(
                f"Custom perception target classes configured: {', '.join(parsed_classes)}"
            )

    # 3. Apply optional runtime overrides
    if sample_fps is not None and sample_fps > 0:
        serialized_config["video"]["sample_fps"] = sample_fps
        print(f"Sample FPS overridden to: {sample_fps}")
    if keyframe_stride is not None and keyframe_stride > 0:
        serialized_config["vggt"]["keyframe_stride"] = keyframe_stride
        print(f"Keyframe stride overridden to: {keyframe_stride}")
    if vggt_model:
        serialized_config["vggt"]["model_id"] = vggt_model
        print(f"VGGT model overridden to: {vggt_model}")

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
        "live",
        "preprocess",
        "vggt",
        "reconstruct",
        "detect",
        "objects",
        "rerun",
        "memory",
        "detect_and_rerun",
        "full",
        "all",
    }
    if stage not in valid_stages:
        raise ValueError(f"unknown stage: {stage}")

    if CPU_ONLY:
        compute_line = (
            "CPU 16 cores / 40 GiB (AEGIS_GPU=cpu). VGGT often takes several "
            "minutes; the Modal URL is a run dashboard, not a coding workspace."
        )
    else:
        compute_line = (
            f"GPU {GPU_TYPE}. If Modal rejects this, add a payment method or "
            "rerun with AEGIS_GPU=cpu."
        )
    print("\n" + "=" * 80)
    print("  🛡️  AEGIS SPATIO-TEMPORAL MEMORY PIPELINE — LAUNCHING")
    print("=" * 80)
    print(f"  • Dataset ID:    {dataset_id}")
    print(f"  • Target Stage:  {stage}")
    print(f"  • Data Volume:   {DATA_VOLUME_NAME}")
    print(f"  • Compute:       {compute_line}")
    print(
        f"  • Target Classes: {len(serialized_config['perception']['target_classes'])} classes"
    )
    print("=" * 80 + "\n")

    results: list[dict[str, Any]] = []

    # A whole (unsegmented) live capture runs the full chain.
    results = _run_stages(
        dataset_id,
        serialized_config,
        preprocess=stage in {"live", "preprocess", "full", "all"},
        reconstruct=stage in {"live", "vggt", "reconstruct", "full", "all"},
        detect=stage
        in {"live", "detect", "objects", "memory", "detect_and_rerun", "full", "all"},
        visualise=stage in {"live", "rerun", "memory", "detect_and_rerun", "all"},
    )

    _print_benchmark_summary(results)
    # Results stay on the Modal volume by default. The app and aegis-ask read
    # them over HTTPS; pass --download only for local Rerun/home-store demos.
    if download:
        _download_outputs(dataset_id)
        if not no_ingest:
            _ingest_into_home(dataset_id, config, home_id or config.memory.home_id)


def _run_stages(
    dataset_id: str,
    serialized_config: dict[str, Any],
    *,
    preprocess: bool,
    reconstruct: bool,
    detect: bool,
    visualise: bool,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if preprocess:
        results.append(preprocess_video_remote.remote(dataset_id, serialized_config))
    if reconstruct:
        results.append(Reconstructor().run.remote(dataset_id, serialized_config))
    if detect:
        results.append(Perception().run.remote(dataset_id, serialized_config))
    if visualise:
        results.append(rerun_remote.remote(dataset_id, serialized_config))
    return results


def _finalise_config(
    serialized_config: dict[str, Any],
    classes: str | None,
    sample_fps: int | None,
    keyframe_stride: int | None,
) -> dict[str, Any]:
    """Apply CLI overrides and the HF token (same rules as the batch path)."""

    if classes:
        parsed = [c.strip().lower() for c in classes.split(",") if c.strip()]
        if parsed:
            serialized_config["perception"]["target_classes"] = parsed
    if sample_fps:
        serialized_config["video"]["sample_fps"] = sample_fps
    if keyframe_stride:
        serialized_config["vggt"]["keyframe_stride"] = keyframe_stride
    token = (
        os.getenv("HF_TOKEN")
        or os.getenv("HUGGING_FACE_HUB_TOKEN")
        or os.getenv("hf_token")
    )
    if token:
        serialized_config["hf_token"] = token
    return serialized_config


def _run_live_segmented(
    live_path: Path,
    *,
    base_dataset_id: str,
    segment_frames: int,
    config: RuntimeConfig,
    serialized_config: dict[str, Any],
    upload: bool,
    home_id: str,
    ingest: bool,
    follow: bool,
    keep_frames: bool,
    rerun: bool,
    download: bool,
) -> None:
    """Promote and process one segment at a time; optionally download it."""

    from aegis.ingestion.segment_runner import run_live_segments

    def process(promotion: Any) -> None:
        segment_id = promotion.dataset_id
        print(
            f"Segment {segment_id}: {promotion.frame_count} frames, "
            f"{promotion.duration_sec:.1f}s"
        )
        if upload:
            upload_dataset_to_modal_volume(
                promotion.dataset_dir, segment_id, DATA_VOLUME_NAME
            )
        results = _run_stages(
            segment_id,
            serialized_config,
            preprocess=True,
            reconstruct=True,
            detect=True,
            visualise=rerun,
        )
        _print_benchmark_summary(results)
        if download:
            _download_outputs(segment_id)
            if ingest:
                _ingest_into_home(segment_id, config, home_id)

    done = run_live_segments(
        live_path,
        base_dataset_id=base_dataset_id,
        segment_frames=segment_frames,
        process=process,
        video=config.video,
        camera=config.camera,
        follow=follow,
        keep_frames=keep_frames,
    )
    print(f"Processed {len(done)} segment(s) of {live_path.name}: {', '.join(done)}")


def _ingest_into_home(dataset_id: str, config: RuntimeConfig, home_id: str) -> None:
    """Merge the downloaded session graph into the home's durable memory."""

    from aegis.memory.ingest import ingest_session
    from aegis.memory.store import open_store

    graph_path = Path("outputs") / dataset_id / "objects" / "r4d_scene_graph.json"
    if not graph_path.exists():
        print(f"  ⚠ No scene graph at {graph_path}; nothing ingested.")
        return
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    if int(graph.get("schema_version", 1)) != 2:
        print("  ⚠ Scene graph is schema v1; re-run the detect stage to ingest it.")
        return
    store = open_store(home_id, config.memory.store_root)
    try:
        report = ingest_session(
            store,
            graph,
            vocabulary=config.vocab(),
            evidence_root=graph_path.parent,
            retention=config.memory.retention,
            matching=config.memory.matching,
        )
    finally:
        store.close()
    print(f"  ✓ Ingested {dataset_id} into home {home_id}: {report.as_dict()}")


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
    evidence_local = local_root / dataset_id / "objects"
    evidence_local.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "modal",
            "volume",
            "get",
            "aegis-poc-data",
            f"{dataset_id}/outputs/objects/evidence",
            str(evidence_local),
            "--force",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
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
    print("  🚀 LOCAL ARTIFACTS READY (optional demo fallback)")
    print("=" * 80)
    print(
        f"  • View 3D Scene Graph in Rerun:  rerun outputs/{dataset_id}/viewer/demo.rrd"
    )
    print(
        "  • Normal path needs none of this: ask the Modal API with aegis-ask "
        "or the mobile app."
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
        "--live-session",
        type=str,
        default=None,
        help="Captured session directory (captures/<id>) or 'latest'",
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
        "--vggt-model",
        type=str,
        default=None,
        help="Override the VGGT checkpoint (e.g. wincentIsMe/VGGT-Omega)",
    )
    parser.add_argument(
        "--stage",
        type=str,
        default="all",
        help="Pipeline stage (all, full, live, preprocess, vggt, detect, rerun)",
    )
    parser.add_argument(
        "--config-path",
        type=str,
        default="config/demo.yaml",
        help="Path to config YAML",
    )
    parser.add_argument(
        "--recorded-at",
        type=str,
        default=None,
        help="ISO-8601 start time of a batch video, e.g. 2026-11-15T09:30:00+05:00",
    )
    parser.add_argument(
        "--home-id", type=str, default=None, help="Home store to ingest into"
    )
    parser.add_argument(
        "--segment-frames",
        type=int,
        default=None,
        help="Frames per live segment (default: live.segment_frames; 0 = whole capture)",
    )
    parser.add_argument(
        "--follow", action="store_true", help="Keep processing while the capture runs"
    )
    parser.add_argument(
        "--keep-frames",
        action="store_true",
        help="Keep local segment frames after ingest",
    )
    parser.add_argument(
        "--rerun", action="store_true", help="Also build a Rerun recording per segment"
    )
    parser.add_argument(
        "--no-ingest",
        action="store_true",
        help="Do not ingest the result into the home store",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download artifacts locally for Rerun/home-store demos (default: keep on Modal)",
    )
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="Video is already in the Modal volume; skip the local upload",
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
    if args.live_session:
        cli_cmd.extend(["--live-session", args.live_session])
    if args.classes:
        cli_cmd.extend(["--classes", args.classes])
    if args.vggt_model:
        cli_cmd.extend(["--vggt-model", args.vggt_model])
    if args.sample_fps:
        cli_cmd.extend(["--sample-fps", str(args.sample_fps)])
    if args.keyframe_stride:
        cli_cmd.extend(["--keyframe-stride", str(args.keyframe_stride)])
    if args.recorded_at:
        cli_cmd.extend(["--recorded-at", args.recorded_at])
    if args.home_id:
        cli_cmd.extend(["--home-id", args.home_id])
    if args.no_ingest:
        cli_cmd.append("--no-ingest")
    if args.download:
        cli_cmd.append("--download")
    if args.no_upload:
        cli_cmd.append("--no-upload")
    if args.segment_frames is not None:
        cli_cmd.extend(["--segment-frames", str(args.segment_frames)])
    if args.follow:
        cli_cmd.append("--follow")
    if args.keep_frames:
        cli_cmd.append("--keep-frames")
    if args.rerun:
        cli_cmd.append("--rerun")

    sys.exit(subprocess.run(cli_cmd, check=False).returncode)
