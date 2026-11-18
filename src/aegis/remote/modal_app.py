"""Modal application definitions for the Aegis remote pipeline."""

from __future__ import annotations

import os
from typing import Any

import modal

DATA_VOLUME_NAME = os.getenv("AEGIS_DATA_VOLUME", "aegis-poc-data")
MODEL_CACHE_VOLUME_NAME = os.getenv("AEGIS_MODEL_CACHE_VOLUME", "aegis-model-cache")
DATA_MOUNT = "/data"
MODEL_MOUNT = "/models"

# Accelerator policy: L4 by default (the designed deployment). Set
# AEGIS_GPU=cpu to run the same functions on CPU Modal containers, which works
# on workspaces that cannot allocate GPUs yet (slower, but honest compute).
GPU_TYPE = os.getenv("AEGIS_GPU", "L4").strip()
CPU_ONLY = GPU_TYPE.lower() in {"cpu", "none", "off", ""}


def _compute(gpu_memory_mb: int, cpu_memory_mb: int) -> dict[str, Any]:
    if CPU_ONLY:
        return {"cpu": 16.0, "memory": cpu_memory_mb}
    return {"gpu": GPU_TYPE, "memory": gpu_memory_mb}


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
            # A real run must never silently swap in the synthetic test
            # geometry if VGGT fails (e.g. on a CPU-only container).
            "AEGIS_VGGT_STRICT": "1",
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
        # DINOv2 re-ID embeddings (perception.reid_backend: dino).
        "transformers>=4.48,<5",
    )
    .run_commands(
        "pip install git+https://github.com/facebookresearch/sam2.git || true",
        # YOLOE pulls CLIP at runtime otherwise, which stalls the first detect.
        "pip install 'git+https://github.com/ultralytics/CLIP.git' ftfy",
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

    data_volume.reload()

    result = run_preprocess(dataset_id, config)
    data_volume.commit()
    return result


# GPU stages are classes: a warm container keeps the model loaded between
# calls (one call per live segment) instead of reloading weights every time.
WARM_SECONDS = 300


@app.cls(
    image=VGGT_IMAGE,
    volumes={DATA_MOUNT: data_volume, MODEL_MOUNT: model_cache_volume},
    secrets=SECRETS,
    timeout=7200,
    scaledown_window=WARM_SECONDS,
    **_compute(gpu_memory_mb=24576, cpu_memory_mb=40960),
)
class Reconstructor:
    """VGGT-Ω reconstruction on an L4 GPU, or 16-core CPU when AEGIS_GPU=cpu."""

    @modal.enter()
    def setup(self) -> None:
        self.model = None
        self.model_key = ""

    @modal.method()
    def run(self, dataset_id: str, config: dict[str, Any]) -> dict[str, Any]:
        from aegis.core.config import RuntimeConfig
        from aegis.geometry.vggt_runner import load_model
        from aegis.remote.workers import run_vggt

        # Frames were committed by another container; see them first.
        data_volume.reload()
        vggt = RuntimeConfig.from_mapping(config).vggt
        key = f"{vggt.model_id}"
        if self.model is None or self.model_key != key:
            self.model = load_model(vggt, hf_token=config.get("hf_token"))
            self.model_key = key
        result = run_vggt(dataset_id, config, model=self.model)
        data_volume.commit()
        model_cache_volume.commit()
        return result


@app.cls(
    image=PERCEPTION_IMAGE,
    volumes={DATA_MOUNT: data_volume, MODEL_MOUNT: model_cache_volume},
    secrets=SECRETS,
    timeout=7200,
    scaledown_window=WARM_SECONDS,
    **_compute(gpu_memory_mb=16384, cpu_memory_mb=40960),
)
class Perception:
    """Detection, SAM 2, lifting and memory on L4, or 16-core CPU when AEGIS_GPU=cpu."""

    @modal.enter()
    def setup(self) -> None:
        self.models = None
        self.models_key = ""

    @modal.method()
    def run(self, dataset_id: str, config: dict[str, Any]) -> dict[str, Any]:
        from pathlib import Path

        from aegis.core.config import RuntimeConfig
        from aegis.perception.detector import load_models
        from aegis.remote.workers import run_detect_and_lift

        data_volume.reload()
        runtime = RuntimeConfig.from_mapping(config)
        key = "|".join(
            (
                runtime.perception.detector_backend,
                runtime.perception.detector_model,
                runtime.sam2.model_id if runtime.sam2 else "",
                runtime.sam2.mode if runtime.sam2 else "",
                runtime.perception.reid_backend,
            )
        )
        if self.models is None or self.models_key != key:
            self.models = load_models(
                runtime.perception,
                sam2_config=runtime.sam2,
                weights_dir=Path(runtime.storage.model_mount) / "yolo",
            )
            self.models_key = key
        result = run_detect_and_lift(dataset_id, config, models=self.models)
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

    data_volume.reload()

    result = run_rerun(dataset_id, config)
    data_volume.commit()
    return result
