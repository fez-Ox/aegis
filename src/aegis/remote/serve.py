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

# ``add_local_python_source`` ships Python modules only. The NLQ lexicon and the
# label ontology are data, so they are added explicitly -- otherwise the app
# silently falls back to ~30 built-in words and cannot answer about anything
# else ("I don't know that word. Try: book").
VOCABULARY_REMOTE = "/root/config/vocabulary.yaml"
NLQ_DATA_REMOTE = "/root/aegis/nlq/data"

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
    .add_local_file("config/vocabulary.yaml", VOCABULARY_REMOTE, copy=True)
    .add_local_dir("src/aegis/nlq/data", NLQ_DATA_REMOTE, copy=True)
)

SERVE_ENV = {
    "AEGIS_DATASET_ID": os.getenv("AEGIS_DATASET_ID", "demo01"),
    "AEGIS_VOCABULARY_FILE": VOCABULARY_REMOTE,
}


@app.function(
    image=SERVE_IMAGE,
    volumes={DATA_MOUNT: data_volume},
    cpu=1.0,
    memory=2048,
    timeout=600,
    env=SERVE_ENV,
)
@modal.asgi_app()
def serve_memory_api() -> Any:
    """Serve the FastAPI gateway, including /api/v1/ask, from the volume.

    A pipeline run commits new artifacts to the volume from another container.
    Without an explicit reload this container keeps its stale mount, so the app
    would keep answering from the old graph until it was restarted. Reload
    (throttled) before each request so a rerun is visible immediately.
    """
    import asyncio
    import time

    import aegis.remote.api

    last_reload = [0.0]

    async def app_with_fresh_volume(scope, receive, send):
        now = time.monotonic()
        if now - last_reload[0] >= 1.0:
            await asyncio.to_thread(data_volume.reload)
            last_reload[0] = now
        await aegis.remote.api.app(scope, receive, send)

    return app_with_fresh_volume
