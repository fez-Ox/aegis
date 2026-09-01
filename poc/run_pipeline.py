"""Modal CLI entrypoint for the Aegis geometry pipeline.

Run from the repository root with, for example::

    uv run modal run poc/run_pipeline.py --dataset-id demo01 --stage all

The local entrypoint only submits sequential remote jobs. Video decoding,
model inference, point-cloud construction, and Rerun logging all execute in
Modal containers.
"""

from __future__ import annotations

from typing import Literal

from aegis.poc.core.config import RuntimeConfig, config_to_dict, load_config
from aegis.poc.remote.modal_app import (
    DATA_MOUNT,
    DATA_VOLUME_NAME,
    MODEL_CACHE_VOLUME_NAME,
    MODEL_MOUNT,
    app,
    detect_and_lift_remote,
    dust3r_reconstruct_remote,
    preprocess_video_remote,
    rerun_remote,
)

Stage = Literal[
    "preprocess",
    "dust3r",
    "reconstruct",
    "detect",
    "objects",
    "rerun",
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
    config_path: str = "poc/config/demo.yaml",
    dataset_id: str = "demo01",
    stage: Stage = "all",
) -> None:
    """Submit one pipeline stage or the complete sequential pipeline to Modal."""

    config = load_config(config_path)
    _validate_modal_mounts(config)
    serialized_config = config_to_dict(config)

    valid_stages = {
        "preprocess",
        "dust3r",
        "reconstruct",
        "detect",
        "objects",
        "rerun",
        "all",
    }
    if stage not in valid_stages:
        raise ValueError(f"unknown stage: {stage}")

    results: list[dict[str, object]] = []

    # Step 1: Preprocess video frames
    if stage in {"preprocess", "all"}:
        results.append(preprocess_video_remote.remote(dataset_id, serialized_config))

    # Step 2: 3D Scene Reconstruction
    if stage in {"dust3r", "reconstruct", "all"}:
        results.append(dust3r_reconstruct_remote.remote(dataset_id, serialized_config))

    # Step 3: 2D Object Perception and 3D Bounding Box Lifting
    if stage in {"detect", "objects", "all"}:
        results.append(detect_and_lift_remote.remote(dataset_id, serialized_config))

    # Final Step: Build Rerun 4D visualization recording
    if stage in {"rerun", "all"}:
        results.append(rerun_remote.remote(dataset_id, serialized_config))

    for result in results:
        print(result)

