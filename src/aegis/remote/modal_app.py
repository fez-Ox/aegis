"""Modal application definitions for the Aegis remote pipeline."""

from __future__ import annotations

import os
from typing import Any

import modal

DATA_VOLUME_NAME = os.getenv("AEGIS_DATA_VOLUME", "aegis-poc-data")
MODEL_CACHE_VOLUME_NAME = os.getenv("AEGIS_MODEL_CACHE_VOLUME", "aegis-model-cache")
DATA_MOUNT = "/data"
MODEL_MOUNT = "/models"

app = modal.App("aegis-poc")
data_volume = modal.Volume.from_name(DATA_VOLUME_NAME, create_if_missing=True)
model_cache_volume = modal.Volume.from_name(
    MODEL_CACHE_VOLUME_NAME, create_if_missing=True
)


COMMON_APT_PACKAGES = (
    "ffmpeg",
    "git",
    "libgl1",
    "libglib2.0-0",
    "build-essential",
)

CPU_IMAGE = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install(*COMMON_APT_PACKAGES)
    .pip_install(
        "numpy>=1.26,<3",
        "pyyaml>=6.0,<7",
        "opencv-python-headless>=4.10,<5",
        "rerun-sdk>=0.23,<0.30",
        "fastapi>=0.110.0",
        "uvicorn>=0.28.0",
        "pydantic>=2.0.0",
    )
    .add_local_python_source("aegis", copy=True)
)

CUDA_IMAGE = (
    modal.Image.from_registry(
        "nvidia/cuda:12.8.1-cudnn-devel-ubuntu24.04",
        add_python="3.12",
    )
    .entrypoint([])
    .apt_install(*COMMON_APT_PACKAGES)
)

SECRETS = [modal.Secret.from_name("aegis-secrets")]

VGGT_IMAGE = (
    CUDA_IMAGE.pip_install(
        "torch==2.7.1",
        "torchvision==0.22.1",
        "numpy>=1.26,<2",
        "scipy>=1.13,<2",
        "opencv-python-headless>=4.10,<5",
        "pillow>=10,<12",
        "tqdm>=4.66,<5",
        "pyyaml>=6.0,<7",
        "huggingface_hub>=0.23,<1",
        "transformers>=4.48,<5",
        "accelerate>=1.0,<2",
        "einops>=0.7,<1",
        "safetensors>=0.4,<1",
        "trimesh>=4.4,<5",
        "scikit-image>=0.22,<1",
        "matplotlib>=3.9,<4",
    )
    .run_commands("pip install git+https://github.com/facebookresearch/vggt-omega.git")
    .env(
        {
            "HF_HOME": f"{MODEL_MOUNT}/huggingface",
            "TORCH_HOME": f"{MODEL_MOUNT}/torch",
        }
    )
    .add_local_python_source("aegis", copy=True)
)

PERCEPTION_IMAGE = (
    CUDA_IMAGE.pip_install(
        "torch==2.7.1",
        "torchvision==0.22.1",
        "numpy>=1.26,<2",
        "opencv-python-headless>=4.10,<5",
        "ultralytics>=8.3,<9",
        "pyyaml>=6.0,<7",
        "huggingface_hub>=0.23,<1",
    )
    .run_commands(
        "pip install git+https://github.com/facebookresearch/sam2.git || true"
    )
    .env(
        {
            "YOLO_CONFIG_DIR": f"{MODEL_MOUNT}/yolo",
            "HF_HOME": f"{MODEL_MOUNT}/huggingface",
            "TORCH_HOME": f"{MODEL_MOUNT}/torch",
        }
    )
    .add_local_python_source("aegis", copy=True)
)


@app.function(
    image=CPU_IMAGE,
    volumes={DATA_MOUNT: data_volume},
    cpu=2.0,
    memory=4096,
    timeout=3600,
)
def preprocess_video_remote(dataset_id: str, config: dict[str, Any]) -> dict[str, Any]:
    """Run remote video normalization and calibration preparation."""

    from aegis.remote.workers import run_preprocess

    result = run_preprocess(dataset_id, config)
    data_volume.commit()
    return result


@app.function(
    image=VGGT_IMAGE,
    gpu="L4",
    volumes={DATA_MOUNT: data_volume, MODEL_MOUNT: model_cache_volume},
    secrets=SECRETS,
    memory=24576,
    timeout=7200,
)
def vggt_reconstruct_remote(dataset_id: str, config: dict[str, Any]) -> dict[str, Any]:
    """Run VGGT-Ω feed-forward 3D reconstruction remotely on an L4 GPU."""

    from aegis.remote.workers import run_vggt

    result = run_vggt(dataset_id, config)
    data_volume.commit()
    model_cache_volume.commit()
    return result


# Backwards compatibility alias
dust3r_reconstruct_remote = vggt_reconstruct_remote


@app.function(
    image=PERCEPTION_IMAGE,
    gpu="L4",
    volumes={DATA_MOUNT: data_volume, MODEL_MOUNT: model_cache_volume},
    secrets=SECRETS,
    memory=16384,
    timeout=7200,
)
def detect_and_lift_remote(dataset_id: str, config: dict[str, Any]) -> dict[str, Any]:
    """Run open-vocabulary object perception, SAM 2 masking, and 3D lifting on an L4 GPU."""

    from aegis.remote.workers import run_detect_and_lift

    result = run_detect_and_lift(dataset_id, config)
    data_volume.commit()
    model_cache_volume.commit()
    return result


@app.function(
    image=CPU_IMAGE,
    volumes={DATA_MOUNT: data_volume},
    cpu=2.0,
    memory=8192,
    timeout=3600,
)
def rerun_remote(dataset_id: str, config: dict[str, Any]) -> dict[str, Any]:
    """Generate an offline Rerun recording from cached artifacts."""

    from aegis.remote.workers import run_rerun

    result = run_rerun(dataset_id, config)
    data_volume.commit()
    return result
