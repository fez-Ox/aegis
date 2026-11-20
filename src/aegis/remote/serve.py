"""Deploy Aegis memory + NLQ asking as one Modal CPU web app.

The graph stays on the Modal volume; the app and terminal CLI ask over HTTPS.
No artifact download is part of the normal path.

    AEGIS_DATASET_ID=walk01 uv run modal deploy src/aegis/remote/serve.py

This module deliberately does **not** import ``aegis.remote.modal_app``: that
module registers the GPU pipeline app, and importing it would make this deploy
build the CUDA/VGGT/perception images and redeploy the whole pipeline. Serving
needs only FastAPI, pydantic and PyYAML, so the image below is small and the
deploy finishes in seconds.
"""

from __future__ import annotations

import os
from typing import Any

import modal

DATA_VOLUME_NAME = os.getenv("AEGIS_DATA_VOLUME", "aegis-poc-data")
DATA_MOUNT = "/data"

# Separate app so serving never redeploys the GPU pipeline functions.
app = modal.App("aegis-memory-api")
data_volume = modal.Volume.from_name(DATA_VOLUME_NAME, create_if_missing=True)

SERVE_IMAGE = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "fastapi>=0.110.0",
        "pydantic>=2.0.0",
        "pyyaml>=6.0,<7",
    )
    .add_local_python_source("aegis", copy=True)
)


@app.function(
    image=SERVE_IMAGE,
    volumes={DATA_MOUNT: data_volume},
    cpu=1.0,
    memory=2048,
    timeout=600,
    env={"AEGIS_DATASET_ID": os.getenv("AEGIS_DATASET_ID", "demo01")},
)
@modal.asgi_app()
def serve_memory_api() -> Any:
    """Serve the FastAPI gateway, including /api/v1/ask, from the volume."""
    import aegis.remote.api

    return aegis.remote.api.app
