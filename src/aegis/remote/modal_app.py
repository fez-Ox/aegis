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
        # DINOv2 re-ID embeddings (perception.reid_backend: dino).
        "transformers>=4.48,<5",
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

    data_volume.reload()

    result = run_preprocess(dataset_id, config)
    data_volume.commit()
    return result


@app.function(
    image=CPU_IMAGE,
    volumes={DATA_MOUNT: data_volume},
    cpu=2.0,
    memory=4096,
    timeout=7200,
)
def fetch_egolife_day(
    segments: list[dict[str, Any]],
    width: int = 704,
    height: int = 704,
    fps: int = 5,
) -> dict[str, Any]:
    """Download one day of EgoLife clips and write pipeline-ready videos.

    Everything happens in the Modal volume, so the local machine never has to
    download the ~10 GB source dataset. Clips are deduplicated and fetched in
    parallel; each 5-minute segment becomes ``<dataset>/video.mp4`` plus a
    ``source_metadata.json`` carrying its real wall-clock start.
    """

    import json
    import os
    import shutil
    import subprocess
    import urllib.request
    from concurrent.futures import ThreadPoolExecutor
    from pathlib import Path

    data_volume.reload()
    base = "https://huggingface.co/datasets/lmms-lab/EgoLife/resolve/main/"
    cache = Path(DATA_MOUNT) / "_egolife_clips"
    cache.mkdir(parents=True, exist_ok=True)

    paths = sorted({path for segment in segments for path in segment["clips"]})

    def download(path: str) -> Path:
        destination = cache / path
        if destination.exists() and destination.stat().st_size > 0:
            return destination
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(".part")
        request = urllib.request.Request(base + path)
        with (
            urllib.request.urlopen(request, timeout=300) as response,
            temporary.open("wb") as handle,
        ):
            shutil.copyfileobj(response, handle, 1 << 20)
        os.replace(temporary, destination)
        return destination

    with ThreadPoolExecutor(max_workers=12) as pool:
        files = dict(zip(paths, pool.map(download, paths), strict=True))

    for segment in segments:
        dataset_id = str(segment["dataset_id"])
        output_dir = Path(DATA_MOUNT) / dataset_id
        output_dir.mkdir(parents=True, exist_ok=True)
        sources = [files[path] for path in segment["clips"]]
        listing = output_dir / "clips.txt"
        listing.write_text(
            "".join(f"file '{source}'\n" for source in sources), encoding="utf-8"
        )
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(listing),
                "-vf",
                f"scale={width}:{height}:flags=lanczos",
                "-r",
                str(fps),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                "-an",
                str(output_dir / "video.mp4"),
            ],
            check=True,
        )
        (output_dir / "source_metadata.json").write_text(
            json.dumps(
                {
                    "dataset_id": dataset_id,
                    "source": "EgoLife A1_JAKE 12:00 (remote fetch)",
                    "recorded_at": segment["recorded_at"],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    data_volume.commit()
    return {"clips": len(paths), "segments": len(segments)}


# GPU stages are classes: a warm container keeps the model loaded between
# calls (one call per live segment) instead of reloading weights every time.
WARM_SECONDS = 300


@app.cls(
    image=VGGT_IMAGE,
    gpu="L4",
    volumes={DATA_MOUNT: data_volume, MODEL_MOUNT: model_cache_volume},
    secrets=SECRETS,
    memory=24576,
    timeout=7200,
    scaledown_window=WARM_SECONDS,
)
class Reconstructor:
    """VGGT-Ω reconstruction on an L4 GPU."""

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
    gpu="L4",
    volumes={DATA_MOUNT: data_volume, MODEL_MOUNT: model_cache_volume},
    secrets=SECRETS,
    memory=16384,
    timeout=7200,
    scaledown_window=WARM_SECONDS,
)
class Perception:
    """Detection, SAM 2 masks, 3D lifting and the memory graph on an L4 GPU."""

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
