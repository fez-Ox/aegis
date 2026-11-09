# Aegis NLQ + Modal Handoff

**Last updated:** 2026-11-09  
**Branch:** `feat/NLQ`  
**Workspace:** `/home/ali-sher/Downloads/aegis-antigravity/aegis`  
**Modal profile:** `i230683`

This document is a handoff for another agent or developer who needs to continue
the NL Querying (NLQ), Modal pipeline, and memory-serving work. It records what
was built, how the Modal pieces fit together, how the deployed memory was
queried, what currently works, and what is still blocked.

---

## 1. TL;DR

- The sample video was run **end-to-end through the real pipeline on Modal CPU**.
- The resulting memory is **live over HTTPS** through a deployed Modal FastAPI
  app.
- NLQ is **dictionary-first** with a very large closed home vocabulary; the
  local LLM is only an escape hatch for unknown words.
- The default LLM is **local Ollama `qwen2.5:1.5b`**, not OpenAI.
- The OpenAI key **authenticates** but the account has **no credits**, so chat
  inference returns HTTP 429.
- The branch has **10 local commits** on top of `origin/feat/NLQ`; git push is
  blocked because this shell has **no GitHub credentials**.
- L4 GPU execution is still blocked by Modal billing. The CPU run bypassed it.
- The official `facebook/VGGT-Omega` repo is gated. The run used the unmodified
  public mirror `wincentIsMe/VGGT-Omega` under the FAIR Noncommercial Research
  License.

Current deployed API base URL:

```text
https://i230683--aegis-memory-api-serve-memory-api.us-east.modal.run
```

Example live query:

```bash
curl "$BASE/api/v1/query?item=laptop&dataset_id=nlq_sample"
# found=true, instance_label=Laptop #3, anchor=Desk #1, room=Bedroom
```

---

## 2. What Already Exists

### 2.1 Repo layout that matters

| Path | Purpose |
|---|---|
| `run_pipeline.py` | Modal local entrypoint for `preprocess -> VGGT -> detect/lift -> Rerun`; uploads video, serializes config, invokes remote functions, downloads artifacts |
| `src/aegis/remote/modal_app.py` | Modal app `aegis-poc`, images, volumes, secrets, GPU/CPU compute policy, remote functions |
| `src/aegis/remote/workers.py` | Actual stage implementations called inside Modal containers |
| `src/aegis/remote/api.py` | FastAPI memory gateway (`/api/v1/*`), scene-graph loading, search paths, queries, rooms, timeline, crops, simulations |
| `src/aegis/geometry/vggt_runner.py` | VGGT-Ω checkpoint download/load and reconstruction |
| `src/aegis/memory/scene_graph.py` | R4DSG memory engine (Rooms -> Anchors -> Objects, permanence, events) |
| `config/demo.yaml` | Runtime config: 15 FPS, VGGT model/stride, YOLOE + SAM 2, target classes, rooms, visualization |
| `NL Querying/build_memory.py` | Runs the Modal pipeline, then copies `outputs/<dataset>` into `NL Querying/outputs/<dataset>` |
| `NL Querying/comm/transports.py` | `LocalGraphSource` and `ModalGraphSource`; common memory-view contract |
| `NL Querying/comm/client.py` | `AegisCommClient` facade; caches one dataset view |
| `NL Querying/comm/modal_serve.py` | Deployable Modal app `aegis-memory-api` wrapping `aegis.remote.api:app` |
| `NL Querying/comm/llm.py` | Provider-agnostic OpenAI-compatible LLM client |
| `NL Querying/nlq/engine.py` | Hybrid NLQ engine (dictionary first, LLM escape hatch) |
| `NL Querying/nlq/dictionary.py` | Closed-vocabulary index and merge/lookup logic |
| `NL Querying/nlq/home_vocabulary.json` | Curated authoritative home vocabulary |
| `NL Querying/nlq/dictionary.json` | Generated runtime dictionary (committed) |
| `NL Querying/scripts/build_dictionary.py` | Rebuilds `dictionary.json` from all vocabulary sources |
| `NL Querying/smoke_test.py` | CLI to inspect a transport and optionally ask one question |
| `sample_outputs/nlq_sample/` | Committed real artifacts from the successful sample run |
| `AGENT-DOC_context.md` | Existing project context and session log; this handoff is more operational |

### 2.2 Git state

`origin/feat/NLQ` is currently at `7e1dd79`. Local `feat/NLQ` is **10 commits
ahead**:

```text
c7cc5c5 docs(samples): clarify where the nlq_sample Rerun file lives
e62b291 fix(api): let the deployed demo default to nlq_sample
11f3899 chore(samples): add real nlq_sample Modal CPU artifacts
515cd13 fix(api): discover the Modal pipeline outputs/objects layout
0290588 feat(pipeline): allow VGGT checkpoint override and safe weights loading
ed89180 feat(nlq): cover common slang in the closed vocabulary
af06dad docs(nlq): document vocabulary layers and local LLM default
8756fcb feat(nlq): default to local Ollama Qwen provider
d1c1d91 feat(nlq): add curated closed home vocabulary of 511 items
1d853aa fix(nlq): make vocabulary aliases authoritative and match labels by word boundary
```

Working tree is clean. Push still needs GitHub authentication for
`fez-Ox/aegis` (account `Ali-Sher12`):

```bash
git push origin feat/NLQ
```

The current shell has no credential helper, no `gh`, and no SSH key:

```text
fatal: could not read Username for 'https://github.com': terminal prompts disabled
```

Do **not** embed a PAT in the remote URL or commit one. Authenticate with a
credential helper, `gh auth login`, or an SSH key, then push.

---

## 3. How the Modal Pipeline Works

### 3.1 App, images, volumes, secrets

`src/aegis/remote/modal_app.py` defines the pipeline app:

```python
app = modal.App("aegis-poc")
```

Volumes:

| Volume | Mount | Use |
|---|---|---|
| `aegis-poc-data` | `/data` | Input videos, frames, geometry, scene graphs, Rerun files, benchmark stats |
| `aegis-model-cache` | `/models` | Hugging Face cache, torch cache, YOLO cache, VGGT and SAM 2 weights |

Secret:

```python
SECRETS = [modal.Secret.from_name("aegis-secrets")]
```

The secret currently exists but only contains a harmless placeholder
(`AEGIS_PLACEHOLDER`). It does **not** contain `HF_TOKEN`.

Images:

| Image | Based on | Key packages / env |
|---|---|---|
| `CPU_IMAGE` | Debian slim, Python 3.12 | FastAPI, uvicorn, Pydantic, Rerun SDK, OpenCV, pyyaml |
| `CUDA_IMAGE` | `nvidia/cuda:12.8.1-cudnn-devel-ubuntu24.04` | Common base for GPU stages |
| `VGGT_IMAGE` | `CUDA_IMAGE` | torch 2.7.1, torchvision, HF Hub, transformers, `vggt-omega` from GitHub; `HF_HOME=/models/huggingface`, `TORCH_HOME=/models/torch`, `AEGIS_VGGT_STRICT=1` |
| `PERCEPTION_IMAGE` | `CUDA_IMAGE` | torch, ultralytics YOLOE, SAM 2 from GitHub; model caches on `/models` |

Images use `.add_local_python_source("aegis", copy=True)`, so the local
`src/aegis` package is copied into each image at build time. A code change
needs a new Modal image build on the next run/deploy.

### 3.2 Compute policy

`AEGIS_GPU` controls the accelerator policy:

```python
GPU_TYPE = os.getenv("AEGIS_GPU", "L4").strip()
CPU_ONLY = GPU_TYPE.lower() in {"cpu", "none", "off", ""}
```

- Default: `gpu="L4"` with the stage's memory.
- `AEGIS_GPU=cpu`: 16 CPU cores and 40 GB RAM for VGGT/perception, no GPU.
- CPU mode is slower but works on a workspace without a GPU payment method.
- `AEGIS_GPU=cpu` was also used when deploying the CPU-only memory API because
  `modal_serve.py` imports `aegis.remote.modal_app`, which defines the GPU
  functions at import time.

Modal functions:

| Function | Image | Compute | Stage |
|---|---|---|---|
| `preprocess_video_remote` | `CPU_IMAGE` | 2 CPU / 4 GB | normalize video, extract frames |
| `vggt_reconstruct_remote` | `VGGT_IMAGE` | L4 24 GB or CPU 16 / 40 GB | VGGT-Ω reconstruction |
| `detect_and_lift_remote` | `PERCEPTION_IMAGE` | L4 16 GB or CPU 16 / 40 GB | YOLOE + SAM 2 + 3D lifting + R4DSG memory |
| `rerun_remote` | `CPU_IMAGE` | 2 CPU / 8 GB | build `demo.rrd` |

Every remote function calls `data_volume.commit()` after writing. Without that,
writes in one container are not guaranteed visible to later containers.
VGGT/perception also call `model_cache_volume.commit()`.

### 3.3 Data layout on the Modal volume

The canonical real-run layout is:

```text
/data/<dataset_id>/
  video.mp4
  metadata.json
  frames/
  outputs/
    benchmark_stats.json
    geometry/
      pointcloud.ply
      poses.json
    objects/
      detected_objects_3d.json
      r4d_scene_graph.json
      events.json
      spatial_memory_graph.json
    viewer/
      demo.rrd
```

Important: the graph is at

```text
/data/<dataset_id>/outputs/objects/r4d_scene_graph.json
```

not at `/data/<dataset_id>/objects/...`. The API was initially deployed assuming
the latter, so it reported `scene_graph_ready: false`. Commit `515cd13` added
the `outputs/objects` path to both `get_search_paths()` and
`list_available_datasets()`.

### 3.4 Running a stage or the whole pipeline

There are two equivalent entry styles:

```bash
# Local wrapper: parses args, then shells out to `python -m modal run ...`
uv run python run_pipeline.py --video ... --dataset-id ... --stage all

# Direct Modal CLI
uv run modal run run_pipeline.py --video ... --dataset-id ... --stage all
```

The `@app.local_entrypoint()` `main()`:

1. Loads `config/demo.yaml`.
2. Validates storage mounts against the Modal app constants.
3. Ingests the video and uploads it to `aegis-poc-data/<dataset>/video.mp4`.
4. Optionally merges `COMPREHENSIVE_INDOOR_CLASSES` when:
   - `dataset_id != "demo01"`, and
   - the config filename is exactly `demo.yaml`.
5. Applies `--sample-fps`, `--keyframe-stride`, `--vggt-model` overrides.
6. Finds `HF_TOKEN` from the environment or `.env` and injects it into the
   serialized config.
7. Calls the remote functions for the selected stage(s).
8. Prints a benchmark table.
9. Downloads artifacts into local `outputs/` using `modal volume get --force`.

Stage aliases:

- `preprocess`
- `vggt` / `dust3r` / `reconstruct`
- `detect` / `objects` / `memory` / `detect_and_rerun`
- `rerun`
- `all`

`memory` is an alias for detection + Rerun; there is no separate memory
function. R4DSG construction happens inside `run_detect_and_lift`.

The `build_memory.py` wrapper exposes a smaller stage set:
`all`, `preprocess`, `vggt`, `detect`, `rerun`.

### 3.5 The actual successful sample run

Command used:

```bash
AEGIS_GPU=cpu MODAL_PROFILE=i230683 \
uv run python "NL Querying/build_memory.py" \
  --video "NL Querying/sample_input_video.mp4" \
  --dataset-id nlq_sample \
  --gpu cpu \
  --profile i230683 \
  --vggt-model wincentIsMe/VGGT-Omega \
  --keyframe-stride 10
```

Why these flags:

- `AEGIS_GPU=cpu` / `--gpu cpu`: L4 was rejected by billing.
- `--vggt-model wincentIsMe/VGGT-Omega`: official repo is gated and no
  `HF_TOKEN` was available.
- `--keyframe-stride 10`: reduced VGGT keyframes from the default 6 to 21 for
  CPU runtime.

Run result:

| Stage | Time | Result |
|---|---:|---|
| preprocess | 10.23 s | 202 frames at 15 FPS |
| VGGT-Ω | 196.89 s | 21 keyframes, 17,362 points |
| detect/lift | 138.25 s | 29 detections, 29 masks, 29 3D boxes, 11 tracks, 2 events |
| Rerun | 91.38 s | 12.3 MB `demo.rrd` |
| **total** | **436.75 s** | memory + visualization |

The CPU throughput was about 0.11 FPS for VGGT and 0.15 FPS for detection.

Committed artifacts are under `sample_outputs/nlq_sample/`:

```text
benchmark_stats.json
geometry/poses.json
objects/detected_objects_3d.json
objects/events.json
objects/r4d_scene_graph.json
README.md
```

The Rerun file is **not committed** because `*.rrd` is ignored. It is on the
Modal volume at `/data/nlq_sample/outputs/viewer/demo.rrd` and locally at
`NL Querying/outputs/nlq_sample/viewer/demo.rrd`.

### 3.6 VGGT-Ω checkpoint loading

`src/aegis/geometry/vggt_runner.py`:

```python
ckpt_path = hf_hub_download(
    repo_id=config.model_id,
    filename="vggt_omega_1b_512.pt",
    token=token,
    cache_dir=os.environ.get("HF_HOME"),
)
...
ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=True)
if "model" in ckpt:
    ckpt = ckpt["model"]
model.load_state_dict(ckpt)
```

- `--vggt-model` overrides `config.vggt.model_id`.
- `weights_only=True` was added for safe checkpoint loading; the successful run
  proves the checkpoint is loadable this way.
- `AEGIS_VGGT_STRICT=1` is set in `VGGT_IMAGE`, so a failed VGGT run raises
  instead of silently falling back to synthetic test geometry.

---

## 4. Current Memory Contents

The sample video is **not** the shoes video. It produced a desk/cabinet scene.

From `sample_outputs/nlq_sample/objects/r4d_scene_graph.json`:

- Dataset: `nlq_sample`
- Anchors:
  - `Desk #1` (Bedroom)
  - `Storage Cabinet #2` (Bedroom)
  - `Storage Cabinet #3` (Bedroom)
- Rooms:
  - `Bedroom` (`room_id=1`, `room_type=Bedroom`)
- Tracked objects (`latest_objects`):
  - `Chair #1` -> `Storage Cabinet #2`
  - `Book #2` -> `Storage Cabinet #3`
  - `Laptop #3` -> `Desk #1`
  - `Cell Phone #4` -> `Storage Cabinet #2`
  - `Bottle #5` -> `Storage Cabinet #2`
- Events: 2 (`state_change`, `anchor_change`)
- Timeline frames: 21

The sample video has **no shoes and no keys**, so `kicks`, `shoes`, and `keys`
correctly abstain with `not_observed_in_memory`.

---

## 5. How Communication Works

### 5.1 One interface, two transports

`NL Querying/comm/transports.py` defines the common memory view:

```python
{
    "dataset_id": str,
    "anchors": [...],
    "rooms": [...],
    "events": [...],
    "latest_objects": [...],
    "timeline_frames": int,
    "transport": "local" | "modal",
}
```

The two sources are interchangeable:

| Transport | Class | Behavior |
|---|---|---|
| `local` | `LocalGraphSource` | Reads scene-graph JSON from `NL Querying/outputs`, `sample_outputs`, `outputs`, `tests/fixtures` |
| `modal` | `ModalGraphSource` | HTTPS calls to the deployed Modal memory API |

`AegisCommClient` wraps a source and caches one loaded dataset view per
dataset id. Dataset isolation is intentional: one memory view per question,
never merged.

Selection:

```python
create_source(transport="modal", base_url="https://...")
# or environment:
AEGIS_COMM_TRANSPORT=modal
AEGIS_MODAL_BASE_URL=https://...
```

`auto` chooses Modal only when a base URL is known; otherwise local.

### 5.2 Local transport

Priority roots:

```text
NL Querying/outputs
sample_outputs
outputs
tests/fixtures
```

The local transport folds the per-frame `timeline` into `latest_objects` using
`fold_latest_states`, mirroring the remote API.

The committed real artifacts under `sample_outputs/nlq_sample` make local
queries possible even without Modal:

```bash
uv run python "NL Querying/smoke_test.py" \
  --dataset nlq_sample --ask "where is my laptop" --no-llm
```

### 5.3 Modal memory API

`NL Querying/comm/modal_serve.py` deploys a separate app:

```python
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
    import aegis.remote.api
    return aegis.remote.api.app
```

Deploy:

```bash
AEGIS_DATASET_ID=nlq_sample AEGIS_GPU=cpu MODAL_PROFILE=i230683 \
uv run modal deploy "NL Querying/comm/modal_serve.py"
```

- `AEGIS_DATASET_ID=nlq_sample` makes `/api/v1/health` and the default active
  dataset report the sample memory.
- `AEGIS_GPU=cpu` avoids defining GPU functions while importing
  `aegis.remote.modal_app`.
- The app is deployed and idle (`0` tasks) after the run.
- The URL is **unauthenticated**; see the security note below.

Why the API works:

- `CPU_IMAGE` includes `fastapi`, `uvicorn`, and the local `aegis` package.
- The app mounts `aegis-poc-data` at `/data`.
- `api.get_search_paths()` probes both:
  - `/data/<dataset>/objects/r4d_scene_graph.json` (canonical)
  - `/data/<dataset>/outputs/objects/r4d_scene_graph.json` (pipeline layout)
- `list_available_datasets()` recognizes the same layouts.

### 5.4 API endpoints

Useful endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/health` | active dataset and graph counts |
| `GET /api/v1/datasets` | available datasets and summaries |
| `GET /api/v1/scene_graph?dataset_id=...` | full graph + `latest_objects` |
| `GET /api/v1/query?item=laptop&dataset_id=...` | older deterministic item query |
| `GET /api/v1/anchors?dataset_id=...` | anchors with contained objects |
| `GET /api/v1/rooms?dataset_id=...` | room regions |
| `GET /api/v1/timeline?dataset_id=...` | event stream |
| `GET /api/v1/crops/{instance_id}` | crop image |
| `POST /api/v1/rooms/rename` | caregiver room naming (mutating) |
| `POST /api/v1/dataset/select` | switch active dataset |
| `POST /api/v1/reset` | reset simulated state |

The NLQ transport only uses `health`, `datasets`, and `scene_graph`. The NLQ
engine performs its own dictionary matching against `latest_objects`; it does
not call `/api/v1/query`. The two matchers are related but not identical.
Parity checking is a TODO.

### 5.5 Querying the deployed API

HTTP:

```bash
BASE="https://i230683--aegis-memory-api-serve-memory-api.us-east.modal.run"

curl -sS "$BASE/api/v1/health" | python3 -m json.tool
# status=ok, dataset_loaded=nlq_sample, num_anchors=3, num_rooms=1,
# num_events=2, total_timeline_frames=21

curl -sS "$BASE/api/v1/scene_graph?dataset_id=nlq_sample" | python3 -m json.tool
curl -sS "$BASE/api/v1/query?item=laptop&dataset_id=nlq_sample" | python3 -m json.tool
```

NLQ CLI over HTTPS:

```bash
export AEGIS_MODAL_BASE_URL="https://i230683--aegis-memory-api-serve-memory-api.us-east.modal.run"

uv run python "NL Querying/smoke_test.py" \
  --transport modal \
  --dataset nlq_sample \
  --ask "where is my laptop" \
  --no-llm
```

Observed answers:

| Question | Answer |
|---|---|
| where is my laptop | Your laptop is sitting on **Desk #1 in the Bedroom**. |
| where is my book | Your book is near **Storage Cabinet #3 in the Bedroom**. |
| where is my phone | Your phone is inside **Storage Cabinet #2 in the Bedroom**. Aegis remembers it there, even out of direct view. |
| where is my bottle | Your bottle is inside **Storage Cabinet #2 in the Bedroom**. |
| where is my chair | Your chair is inside **Storage Cabinet #2 in the Bedroom**. |
| where are my kicks | I couldn't find your shoes in this memory. I do remember book, bottle, cell phone. |
| where are my shoes | Same honest abstention; the sample video has no shoes. |
| where is my keys | Honest abstention; no keys in this memory. |

### 5.6 Local FastAPI server

For local/mobile development without Modal:

```bash
uv run python run_server.py --dataset-id nlq_sample
```

This sets the active dataset and serves on `0.0.0.0:8000`. It reads local
`outputs/`, `data/`, and `/data`; it does **not** search `sample_outputs` by
default. If you only have the committed sample artifacts, either use the local
NLQ transport (which does search `sample_outputs`) or copy them under
`outputs/nlq_sample`.

---

## 6. NLQ Engine and Vocabulary

### 6.1 Engine behavior

`NL Querying/nlq/engine.py` is a hybrid, evidence-gated engine:

1. **Dictionary first**: resolve the item and optional room.
2. **Evidence path**: match `latest_objects` by canonical item/synonyms.
3. **Answer template**: compose a short grounded location sentence.
4. **Abstain** if the item is valid but not observed, or unknown.
5. **LLM escape hatch** only for unknown vocabulary/intent; the LLM may map the
   phrase to a validated dictionary item, but it never writes the location.

Intents:

| Intent | Status |
|---|---|
| `LOCATE` | Working |
| `TEMPORAL` | Honest stub (`temporal_handler_not_implemented`) |
| `ACTIVITY` | Honest stub (`activity_handler_not_implemented`) |
| `UNKNOWN` | LLM mapping or abstention |

Important limitation: `_locate_item` matches **object instances**, not anchors.
Asking "where is my storage cabinet" or "where is my desk" abstains even though
those anchors exist. If anchor queries are required, add an anchor fallback
that answers from `memory["anchors"]` / room labels.

Another limitation: the intent classifier only looks for `where`, `when`, and
`last see/time`. "Which room is my laptop in?" is currently `UNKNOWN`; add a
rule if that phrasing matters.

### 6.2 Vocabulary layers

| Layer | Source | Size |
|---|---|---|
| Curated understanding | `NL Querying/nlq/home_vocabulary.json` | **511 canonical, 1,148 aliases, 20 rooms** |
| Generated runtime | `NL Querying/nlq/dictionary.json` | **525 canonical, 1,631 aliases, 20 rooms** |
| Perception/detection | `config/demo.yaml` + `run_pipeline.COMPREHENSIVE_INDOOR_CLASSES` | config 14 + pipeline 56 classes (deduped at run time) |

The curated file is organized by room categories: kitchen, food, living room,
bedroom, bathroom, dining, office, laundry/utility, entryway/outdoor,
storage/garage, health/personal, pets, kids, decor.

The generated dictionary also merges:

- `QueryReasoningEngine.ITEM_SYNONYMS` / `ROOM_KEYWORDS`
- `COMPREHENSIVE_INDOOR_CLASSES` (read via `ast`, no Modal import)
- `config/demo.yaml` `perception.target_classes`
- object/anchor labels from real scene graphs

The curated layer is applied **last** with reassignment, so it owns aliases
that legacy tables used to claim:

- `cup` -> `cup` (not `bottle`)
- `pan` -> `frying pan` (not `cooking pot`)
- `notebook` -> `notebook` (not `laptop`)
- `bag` -> `bag` (not `backpack`)

Matching uses word boundaries, so:

- `pan` does not match `pants`
- `cup` does not match `cupboard`
- `bed` does not match `bedroom`

Common slang is covered, e.g.:

```text
kicks, trainers, running shoes, wellies -> shoes
brolly -> umbrella
lappy -> laptop
telly -> television
shades -> glasses
hoover -> vacuum
fridge -> refrigerator
tap -> faucet
nappy -> diaper
```

### 6.3 Adding vocabulary

1. Add canonical items/aliases to `NL Querying/nlq/home_vocabulary.json`.
2. Rebuild the runtime dictionary:

```bash
uv run python "NL Querying/scripts/build_dictionary.py"
# --dry-run to inspect without writing
```

3. Run tests:

```bash
uv run pytest "NL Querying/tests" -q
```

4. Commit both the curated file and regenerated `dictionary.json`.

`DictionaryIndex.add_item(..., reassign=True)` is the runtime growth hook. The
curated file is the preferred source for permanent additions.

### 6.4 LLM providers

`NL Querying/comm/llm.py` is OpenAI-compatible and provider-agnostic.

| Provider | Default | Notes |
|---|---|---|
| `local` (default) | `http://localhost:11434/v1`, `qwen2.5:1.5b`, key `ollama` | No cloud key; start Ollama first |
| `openai` | `https://api.openai.com/v1`, `gpt-4o-mini`, `.keys/openai.txt` | Key authenticates, but account has no credits |
| `ollama` | `https://ollama.com/v1`, `gpt-oss:20b`, `.keys/ollama.txt` | Cloud key works; catalog has no qwen |
| `custom` | explicit base URL/model/key | Use for Modal vLLM or any compatible endpoint |

Environment overrides:

```text
AEGIS_LLM_PROVIDER
AEGIS_LLM_BASE_URL
AEGIS_LLM_MODEL
AEGIS_LLM_API_KEY
AEGIS_LLM_KEY_FILE
AEGIS_LLM_TIMEOUT
AEGIS_LLM_EXTRA_BODY
```

Current OpenAI status (re-verified):

- `/v1/models` -> HTTP 200, 96 models.
- Chat completion -> HTTP 429:
  `You have no credits remaining. Add credits to continue using the API.`

The local Qwen model is available. Known vocabulary queries answer in about
0.05 s; genuinely unknown words may take ~80 s with `qwen2.5:1.5b`.

Qwen3 caveat: old local Ollama versions cannot disable Qwen3 thinking through
the OpenAI endpoint; the reasoning text consumes the token budget and
`content` comes back empty. Use `qwen2.5:1.5b`/`qwen2.5:3b` locally, or serve
Qwen3 on Modal vLLM with `enable_thinking: false`.

---

## 7. Tests and Lint

From the repo root:

```bash
uvx ruff check src tests "NL Querying" run_pipeline.py run_server.py
uvx ruff format --check src tests "NL Querying" run_pipeline.py run_server.py

uv run pytest
uv run pytest "NL Querying/tests" -q
```

Last verified state:

- **86 repo tests pass**
- **44 NLQ tests pass**
- ruff check and format clean

Useful targeted tests:

```bash
uv run pytest tests/test_api.py -q
uv run pytest "NL Querying/tests/test_engine.py" -q
uv run pytest "NL Querying/tests/test_vocabulary.py" -q
uv run pytest "NL Querying/tests/test_llm.py" -q
```

---

## 8. Modal Operations Cheat Sheet

```bash
# Auth/profile
export MODAL_PROFILE=i230683

# List apps; the pipeline app is ephemeral, the memory API stays deployed
uv run modal app list

# Logs for the deployed memory API
uv run modal app logs aegis-memory-api

# Stop the public API
uv run modal app stop aegis-memory-api

# Volume inspection
uv run modal volume ls aegis-poc-data nlq_sample
uv run modal volume ls aegis-poc-data nlq_sample/outputs
uv run modal volume get aegis-poc-data \
  nlq_sample/outputs/viewer/demo.rrd . --force

# Billing summary
uv run modal billing summary
```

Current billing reality:

- Metered cost around **$0.02**.
- Credits slightly negative (`-0.02`).
- Billed cost `$0.00`.
- L4 and T4 submissions are rejected:
  `Please add a payment method to use L4 GPU functions.`
- CPU functions run on 16 cores.

The pipeline app `aegis-poc` from the successful run is stopped. The memory API
app `aegis-memory-api` is deployed and idle.

### Cold starts

The memory API scales to zero. The first request after idle may take several
seconds. That is expected. If demo latency matters, set `min_containers=1` on
the function, but that keeps a container warm and costs money.

### Security note

The deployed API is **unauthenticated** and includes mutating endpoints
(`/api/v1/rooms/rename`, `/api/v1/reset`, simulations). Do not leave it running
indefinitely. Stop it with `modal app stop aegis-memory-api` when the demo is
over, or add Modal proxy auth / application auth before exposing it widely.

---

## 9. Blockers and How to Unblock

### 9.1 GitHub push

Need authentication for `https://github.com/fez-Ox/aegis.git` as
`Ali-Sher12`. Then:

```bash
git push origin feat/NLQ
```

### 9.2 Modal L4 GPU

Add a payment method to workspace `i230683`, then rerun without CPU mode:

```bash
MODAL_PROFILE=i230683 \
uv run python "NL Querying/build_memory.py" \
  --video "NL Querying/sample_input_video.mp4" \
  --dataset-id nlq_sample \
  --profile i230683
```

If the official weights are still unavailable, add the mirror flag:

```bash
  --vggt-model wincentIsMe/VGGT-Omega
```

The default config uses keyframe stride 6 on GPU; CPU used 10.

### 9.3 Official VGGT-Ω weights

`facebook/VGGT-Omega` is gated (`gated: manual`; unauthenticated resolve returns
HTTP 401). There is no `HF_TOKEN` in the shell, `.env`, HF cache, or
`aegis-secrets`.

To use the official repo:

```bash
echo 'HF_TOKEN=hf_...' >> .env
# .env is gitignored; do not commit it
```

`run_pipeline.py` reads `HF_TOKEN` from the environment or `.env` and injects it
into the serialized config.

Current research workaround:

- Repo: `wincentIsMe/VGGT-Omega`
- File: `vggt_omega_1b_512.pt` (4,576,706,322 bytes)
- Described by the mirror as an unmodified copy of the official checkpoint.
- License: **FAIR Noncommercial Research License**; the mirror includes a copy.
- Use only for noncommercial research; prefer the official repo with a token
  for anything beyond that.

### 9.4 API auth

Before a public/production demo, add authentication or Modal proxy auth. The
current deployment is intentionally a research demo.

---

## 10. Recommended Next Steps

1. **Push the branch** after authenticating as `Ali-Sher12`.
2. **Decide whether to keep the memory API running.** If not, stop it.
3. **Add the Modal payment method + HF token** and rerun on L4 with the
   official checkpoint; compare the GPU scene graph against the CPU one.
4. **Implement anchor queries** if users should be able to ask about desks,
   cabinets, and other room landmarks. Today only object instances answer.
5. **Implement temporal/activity intents** (`M3.2`): "when did I last see my
   book?", "what did I do this morning?", "what did I put in the cabinet?".
6. **Add intent patterns** for "which room is X in?" and similar phrasings.
7. **Add auth** to the memory API before exposing it beyond a demo.
8. **Optionally deploy Modal vLLM** (`NL Querying/comm/modal_vllm.py`) once GPU
   billing works; wire it with `AEGIS_LLM_PROVIDER=custom`,
   `AEGIS_LLM_BASE_URL=https://<workspace>--aegis-llm-serve.modal.run/v1`,
   `AEGIS_LLM_MODEL=Qwen/Qwen3-8B-AWQ`.
9. **Rebuild the dictionary** after collecting more real scene graphs, and add
   any new observed labels to the curated vocabulary where appropriate.
10. **Add a remote/local parity test** comparing `ModalGraphSource` and
    `LocalGraphSource` answers for the same dataset.

---

## 11. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Please add a payment method to use L4 GPU functions` | Workspace has credits but no card | Use `AEGIS_GPU=cpu` or add payment method |
| `401`/`gated` downloading VGGT | Official repo gated, no token | Add `HF_TOKEN` or use `--vggt-model wincentIsMe/VGGT-Omega` |
| `torch.load` unpickling error | Non-state-dict checkpoint | Inspect keys; `weights_only=True` expects plain tensors/dicts |
| API says `scene_graph_ready: false` | Graph is under `outputs/objects`, API searched only `objects` | Commit `515cd13` or copy graph to `/data/<ds>/objects/` |
| API health shows `demo01` / 0 anchors | Deploy did not set `AEGIS_DATASET_ID` | Redeploy with `AEGIS_DATASET_ID=nlq_sample`; explicit `dataset_id` still works |
| `smoke_test.py` says no datasets | Wrong transport or missing artifact root | Use `--transport local` or set `AEGIS_MODAL_BASE_URL` |
| `where is my storage cabinet` abstains | Anchors are not object instances | Implement anchor fallback; this is expected today |
| `kicks` abstains | Sample video has no shoes | Use a video that contains shoes; abstention is correct |
| Local LLM is slow | `qwen2.5:1.5b` escape hatch on unknown word | Use dictionary terms or a stronger model |
| Qwen3 returns empty content | Thinking tokens consume the budget on old Ollama | Use Qwen2.5 locally, or disable thinking on vLLM |
| `git push` asks for username | No Git credentials | Authenticate as Ali-Sher12 |
| `*.rrd` not in git | Repo ignores Rerun files | Keep on volume/local; download with `modal volume get` |

---

## 12. Exact Artifact / API Reference

### Sample run

- Dataset: `nlq_sample`
- Source video: `NL Querying/sample_input_video.mp4`
- Committed artifacts: `sample_outputs/nlq_sample/`
- Local staged artifacts: `NL Querying/outputs/nlq_sample/`
- Modal volume artifacts: `/data/nlq_sample/`
- Rerun: `demo.rrd` (12.3 MB), not committed

### Deployed API

- App: `aegis-memory-api`
- Base URL:
  `https://i230683--aegis-memory-api-serve-memory-api.us-east.modal.run`
- Default dataset: `nlq_sample`
- Health: 3 anchors, 1 room, 2 events, 21 timeline frames
- State: deployed, idle, unauthenticated

### Useful commands

```bash
# Local query
uv run python "NL Querying/smoke_test.py" \
  --dataset nlq_sample --ask "where is my laptop" --no-llm

# Remote query
AEGIS_MODAL_BASE_URL="https://i230683--aegis-memory-api-serve-memory-api.us-east.modal.run" \
uv run python "NL Querying/smoke_test.py" \
  --transport modal --dataset nlq_sample --ask "where is my laptop" --no-llm

# Rebuild dictionary
uv run python "NL Querying/scripts/build_dictionary.py"

# Re-stage already downloaded outputs
uv run python "NL Querying/build_memory.py" --skip-run

# Full tests
uv run pytest
uv run pytest "NL Querying/tests" -q

# Stop the public API
MODAL_PROFILE=i230683 uv run modal app stop aegis-memory-api
```

---

## 13. Design Invariants to Preserve

1. **Raw VGGT-Ω coordinates are the spatial source of truth.** Do not
   reintroduce manual scale or axis permutations.
2. **The scene graph is the only source of locations.** The LLM may map words
   to items, but it must never invent a location.
3. **No evidence -> abstain.** A valid but unobserved item returns
   `not_observed_in_memory`; an unknown word returns
   `item_not_in_dictionary` with suggestions.
4. **One dataset per query.** Never merge two memories.
5. **Rooms and anchors are context, not personal-object memories.**
   Room-defining landmarks should not become object memories.
6. **The curated vocabulary is authoritative.** Apply it last with
   reassignment and use word-boundary matching.
7. **Dataset-specific configs must not inherit the broad indoor class merge.**
   The merge only happens for `dataset_id != "demo01"` with a config named
   `demo.yaml`.
8. **Commit Modal volume writes.** Remote functions must call
   `data_volume.commit()` (and model cache commit where relevant).
