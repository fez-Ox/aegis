"""Deploy Aegis memory + NLQ asking as one Modal CPU web app.

The graph stays on the Modal volume; the app and terminal CLI ask over HTTPS.
No artifact download is part of the normal path.

    AEGIS_DATASET_ID=nlq_sample uv run modal deploy src/aegis/remote/serve.py
"""

from __future__ import annotations

import os
from typing import Any

import modal

from .modal_app import CPU_IMAGE, DATA_MOUNT, data_volume

# Separate app so serving never redeploys the GPU pipeline functions.
app = modal.App("aegis-memory-api")


@app.function(
    image=CPU_IMAGE,
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
