"""Modal-side skeleton: serve the existing FastAPI memory gateway over HTTPS.

Goals
-----
Give the NLQ module (and any client) a stable public URL that reads the scene
graphs on the ``aegis-poc-data`` Modal volume, without introducing any
large-language dependency yet.

Why this works with zero changes to ``aegis.remote.api``
--------------------------------------------------------
``get_search_paths()`` probes the canonical
``/data/<dataset_id>/objects/r4d_scene_graph.json`` layout first and then the
pipeline's ``/data/<dataset_id>/outputs/objects/r4d_scene_graph.json`` layout.
Both live under the ``DATA_MOUNT`` (``/data``) used by every Modal function in
this project.

Deployment (needs workspace access first, from the repo root with the
project's ``uv`` environment)::

    AEGIS_GPU=cpu uv run modal deploy "NL Querying/comm/modal_serve.py"

The command prints the public base URL::

    https://<workspace>--aegis-memory-api-serve-memory-api.modal.run

Set ``AEGIS_DATASET_ID`` at deploy time to choose the default dataset served
by the API (for example ``AEGIS_DATASET_ID=nlq_sample``); without it the
deployment falls back to ``demo01``.

Wire it into the client::

    export AEGIS_COMM_TRANSPORT=modal
    export AEGIS_MODAL_BASE_URL=https://<workspace>--aegis-memory-api-serve-memory-api.modal.run
    uv run python "NL Querying/smoke_test.py" --transport modal

Fallback
--------
If module discovery of the local ``aegis`` package misbehaves from this
folder, copy this same function into ``src/aegis/remote/modal_app.py``
(deploying that file instead) - the function body is transport-agnostic.

Caveats (see AGENT-DOC_context.md section 12)
--------------------------------------------
* Serverless cold starts add seconds before the first byte; keep alive via
  ``min_containers=1`` only if the demo latency matters at Modal boundary.
* ``@modal.asgi_app()`` URLs are public unless Modal proxy-auth is enabled;
  pairing with the unauthenticated mutating endpoints is ToDo M4.1.
"""

from __future__ import annotations

import os
from typing import Any

import modal

from aegis.remote.modal_app import CPU_IMAGE, DATA_MOUNT, data_volume

# Separate app so NLQ serving never (re)deploys the heavy GPU pipeline
# functions defined in ``aegis.remote.modal_app``.
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
    """Serve the existing memory API; each cold start mounts /data fresh."""
    import aegis.remote.api

    return aegis.remote.api.app
