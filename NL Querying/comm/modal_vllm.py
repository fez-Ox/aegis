"""Modal-side Qwen LLM skeleton for the hybrid NLQ escape hatch.

Serves an OpenAI-compatible vLLM endpoint on a Modal L4, cached on the same
model volume the geometry pipeline uses (``aegis-model-cache``).

Deploy (from the repo root, with the project environment)::

    uv run modal deploy "NL Querying/comm/modal_vllm.py"

The command prints the endpoint URL. Point the client at it::

    export AEGIS_LLM_BASE_URL=https://<workspace>--aegis-llm-serve.modal.run/v1
    export AEGIS_LLM_MODEL=Qwen/Qwen3-8B-AWQ     # the id passed to vLLM
    export AEGIS_LLM_API_KEY=not-needed-local   # vLLM accepts any bearer here

Notes
-----
* vLLM is preferred over Ollama inside Modal: better throughput, guided
  decoding, and a production-grade OpenAI server.
* Qwen3-8B-AWQ (~6 GB weights) fits an L4 (24 GB) with KV headroom for our
  short prompts. Swap ``AEGIS_QWEN_MODEL`` for another Qwen tag without code
  changes - pin the current tag from the HF/Ollama catalog at deploy time.
* Scale-to-zero: free when idle; the first request after idle pays the model
  load time (weights are cached on the volume).
* This app is standalone on purpose - it never redeploys the GPU geometry
  pipeline functions from ``aegis.remote.modal_app``.
"""

from __future__ import annotations

import os
import subprocess

import modal

APP_NAME = "aegis-llm"
MODEL_MOUNT = "/models"
MODEL_CACHE_VOLUME_NAME = os.getenv("AEGIS_MODEL_CACHE_VOLUME", "aegis-model-cache")
MODEL_ID = os.getenv("AEGIS_QWEN_MODEL", "Qwen/Qwen3-8B-AWQ")
PORT = 8000

model_cache = modal.Volume.from_name(MODEL_CACHE_VOLUME_NAME, create_if_missing=True)

VLLM_IMAGE = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("vllm>=0.8,<1")
    .env(
        {
            "HF_HOME": f"{MODEL_MOUNT}/huggingface",
            "TOKENIZERS_PARALLELISM": "false",
        }
    )
)

app = modal.App(APP_NAME)


@app.function(
    image=VLLM_IMAGE,
    gpu="L4",
    volumes={MODEL_MOUNT: model_cache},
    timeout=3600,
    scaledown_window=300,
    min_containers=0,
)
@modal.web_server(port=PORT, startup_timeout=900)
def serve() -> None:
    """Start the vLLM OpenAI server; Modal proxies HTTPS to this port."""
    command = [
        "vllm",
        "serve",
        MODEL_ID,
        "--host",
        "0.0.0.0",
        "--port",
        str(PORT),
        "--max-model-len",
        "8192",
        "--gpu-memory-utilization",
        "0.90",
        "--served-model-name",
        MODEL_ID,
    ]
    subprocess.Popen(command)
