# NL Querying

**Natural Language Querying** for Aegis (AGENT-DOC_ToDos.md **Milestone 3**,
design context in `AGENT-DOC_context.md`).

Users ask questions in **text** (typed, or speech-to-text at the client); the
engine answers **text** grounded strictly in the spatio-temporal memory
(R4DSG scene graph), with explicit abstention instead of invention.

**Architecture: hybrid (Path C) with a very large closed-vocabulary
dictionary.** The dictionary is the primary understanding mechanism; an LLM
(OpenAI, Qwen, or another OpenAI-compatible model) is only an **escape hatch**
that maps unknown words/intents onto validated
vocabulary. The LLM never writes the answer: the deterministic evidence path
always produces the final sentence, so a hallucinated location cannot reach
the user.

### Vocabulary layers

The vocabulary is intentionally **closed** and **large**, but it is split into
three layers so language coverage never becomes a licence to invent memory:

| Layer | Source | Current size | Role |
|---|---|---|---|
| Understanding | `nlq/home_vocabulary.json` | 511 canonical home items, 1,148 aliases, 20 rooms | Every noun the engine may resolve. Curated by room (kitchen, bedroom, bathroom, office, pets, etc.), with regional/slang/plural aliases. |
| Runtime dictionary | `nlq/dictionary.json` (generated) | 525 canonical, 1,631 aliases, 20 rooms | The curated layer merged with the legacy `aegis.memory.reasoning` tables, pipeline classes, config classes, and labels seen in real scene graphs. |
| Perception subset | `run_pipeline.COMPREHENSIVE_INDOOR_CLASSES` + `config/demo.yaml` | 58 + config classes | Objects the open-vocabulary detector is actually prompted to find. It is deliberately smaller than the understanding vocabulary to keep detection fast and precise. |

**Only `r4d_scene_graph.json` supplies locations.** A query for a valid but
unobserved item (e.g. “kettle” in a video that never saw one) gets an honest
`not_observed_in_memory` abstention, not a guess. The LLM is constrained to
the canonical vocabulary and cannot add a new noun.

## Layout

```text
NL Querying/
├── comm/
│   ├── transports.py     LocalGraphSource (NL Querying/outputs, sample_outputs,
│   │                     outputs, tests/fixtures) + ModalGraphSource (HTTPS)
│   ├── client.py         AegisCommClient facade (dataset isolation + cache)
│   ├── llm.py            OpenAI-compatible LLMClient (OpenAI / Ollama / Modal vLLM)
│   ├── modal_vllm.py     Modal vLLM app serving Qwen3 (OpenAI-compatible)
│   └── modal_serve.py    Modal ASGI wrapper around aegis.remote.api
├── nlq/
│   ├── dictionary.py     DictionaryIndex: closed vocabulary + growth hooks
│   ├── home_vocabulary.json  CURATED closed home vocabulary (authoritative)
│   ├── dictionary.json   GENERATED runtime vocabulary (scripts/build_dictionary.py)
│   └── engine.py         HybridNLQEngine: intent → dictionary → evidence →
│                         grounded answer / abstention; LLM escape hatch
├── scripts/
│   └── build_dictionary.py  merges curated + legacy + scene-graph vocabulary
├── build_memory.py       runs the Modal pipeline and stages artifacts here
├── tests/                offline tests (no Modal account needed)
├── smoke_test.py         CLI that exercises communication + answering
├── outputs/              per-dataset artifacts built for NLQ queries
└── README.md
```

## Quickstart (offline, from repo root)

```bash
# Regenerate the dictionary after vocabulary/config changes
uv run python "NL Querying/scripts/build_dictionary.py"

# Offline sanity + a question against sample_outputs
uv run python "NL Querying/smoke_test.py" \
    --dataset demo04 --ask "where is my water bottle"

# Dictionary-only mode (skip the LLM escape hatch)
uv run python "NL Querying/smoke_test.py" --dataset demo04 \
    --ask "where is my sneakers" --no-llm

# Offline tests
uv run pytest "NL Querying/tests" -q
```

`smoke_test.py` prints the active transport, discovered datasets, a compact
scene summary, and the LLM status (never the key).

The default LLM provider is **local Ollama** (`qwen2.5:1.5b`), which needs no
cloud key. Use `AEGIS_LLM_PROVIDER=openai` when OpenAI billing is available;
the key is read from `.keys/openai.txt`. The entire `.keys/` directory is
gitignored and must never be committed. Use `--no-llm` for dictionary-only
mode.

## Building memory from the input video

`build_memory.py` runs the existing Modal pipeline and copies the downloaded
artifacts into `NL Querying/outputs/<dataset_id>`, which the local transport
searches first:

```bash
# GPU workspace (default; needs a Modal payment method)
uv run python "NL Querying/build_memory.py" \
    --video "NL Querying/sample_input_video.mp4" \
    --dataset-id nlq_sample --profile i230683

# CPU-only Modal workspace (no GPU payment method; much slower)
AEGIS_GPU=cpu uv run python "NL Querying/build_memory.py" \
    --video "NL Querying/sample_input_video.mp4" \
    --dataset-id nlq_sample --profile i230683 \
    --vggt-model wincentIsMe/VGGT-Omega --keyframe-stride 10

# Only re-stage artifacts already downloaded by run_pipeline.py
uv run python "NL Querying/build_memory.py" --skip-run
```

Then answer from it:

```bash
uv run python "NL Querying/smoke_test.py" --dataset nlq_sample \
    --ask "where are my shoes"
```

Real runs require two credentials owned by the workspace:

1. **Modal:** auth via `MODAL_PROFILE` / `~/.modal.toml`; GPU functions also
   require a payment method on the workspace (`AEGIS_GPU=cpu` avoids GPUs).
2. **Hugging Face:** `facebook/VGGT-Omega` is gated (HTTP 401 without a
   token). Put `HF_TOKEN=...` in the environment or `.env`; `run_pipeline.py`
   forwards it into the Modal job. The Modal secret `aegis-secrets` must
   exist (an empty/placeholder secret is fine for CPU, but a real `HF_TOKEN`
   can also be stored there).

## LLM escape hatch

The same client code talks to any OpenAI-compatible endpoint:

| Provider | Config | Notes |
|---|---|---|
| Local Ollama + Qwen (default) | `AEGIS_LLM_PROVIDER=local`; defaults to `http://localhost:11434/v1`, `qwen2.5:1.5b`, key `ollama`, timeout 240s | Works offline. Start Ollama first (`ollama serve` / the desktop app). Non-thinking Qwen works without cloud keys. Avoid `qwen3:*` on old Ollama versions: their reasoning fills the token budget and the OpenAI endpoint returns empty content. |
| OpenAI | `AEGIS_LLM_PROVIDER=openai`; key in `.keys/openai.txt`; defaults to `https://api.openai.com/v1`, `gpt-4o-mini` | Auth is valid (`/v1/models` returns 200 with 96 models), but the current account has **no credits**: chat completions return HTTP 429 `insufficient_quota` ("no credits remaining"). Add billing credits before using it. |
| Ollama Cloud | `AEGIS_LLM_PROVIDER=ollama`; key in `.keys/ollama.txt`; defaults to `https://ollama.com/v1`, `gpt-oss:20b` | The cloud catalog for the current key has **no qwen** model; `gpt-oss:20b` is used for live verification. |
| Modal vLLM + Qwen (designed) | deploy `comm/modal_vllm.py`, then `AEGIS_LLM_PROVIDER=custom`, `AEGIS_LLM_BASE_URL=https://<workspace>--aegis-llm-serve.modal.run/v1`, `AEGIS_LLM_MODEL=Qwen/Qwen3-8B-AWQ`, any non-empty key | Needs a GPU-capable Modal workspace. |

Variable reference: `AEGIS_LLM_PROVIDER` (default `local`),
`AEGIS_LLM_BASE_URL`, `AEGIS_LLM_MODEL`, `AEGIS_LLM_API_KEY`,
`AEGIS_LLM_KEY_FILE`, `AEGIS_LLM_TIMEOUT`, `AEGIS_LLM_EXTRA_BODY` (JSON merged
into the request; Qwen3 on vLLM can use
`{"chat_template_kwargs": {"enable_thinking": false}}`). Explicit
`AEGIS_LLM_BASE_URL` / `AEGIS_LLM_MODEL` / `AEGIS_LLM_TIMEOUT` values always
override the provider defaults.

For fallback questions the LLM receives the question plus the dataset's
canonical items, tracked labels and rooms, and must return strict JSON
(`intent`, `item`, `room`). The engine then:

1. rejects any item/room that is not in the dictionary or the actual memory;
2. runs the same LOCATE/TEMPORAL/ACTIVITY handler as a dictionary hit;
3. abstains if no valid mapping exists, or if the LLM is unreachable.

Results expose `llm_used` so callers can audit when the escape hatch fired.

## Engine behaviour

| Path | Today | TODO (M3 ref) |
|---|---|---|
| LOCATE | grounded answer or honest abstain; dictionary → evidence, LLM alias mapping when needed | calibrated confidence (M3.4), evidence crops (M3.5), freshness (M3.3) |
| TEMPORAL | abstains honestly ("can't answer time questions yet") | event retrieval + relative time (M3.2) |
| ACTIVITY | abstains honestly | activity grouping (pre-step: M2.3) |
| UNKNOWN | LLM maps to a valid intent/item, then evidence path; otherwise abstains | calibrated abstention threshold (M3.4) |

Dictionary growth: `DictionaryIndex.add_item()` / `save()` / `load()`. The
generated file is merged **on top of** the live `aegis.memory.reasoning`
tables with authoritative reassignment: curated aliases win over legacy
collisions (`cup` moves from `bottle` to `cup`, `pan` from `cooking pot` to
`frying pan`). Lookup and scene-label matching use word boundaries, so `pan`
never matches `pants`, `cup` never matches `cupboard`, and `bed` never matches
`bedroom`.

`scripts/build_dictionary.py` harvests:

- `nlq/home_vocabulary.json` — the curated closed home vocabulary
  (applied last and authoritative);
- `QueryReasoningEngine.ITEM_SYNONYMS` / `ROOM_KEYWORDS`;
- `run_pipeline.COMPREHENSIVE_INDOOR_CLASSES` (read via `ast`, no Modal import);
- `config/demo.yaml` `perception.target_classes`;
- object/anchor labels from real scene graphs in all local artifact roots.

## Gated VGGT weights and checkpoint overrides

The official `facebook/VGGT-Omega` repository is gated (`gated: manual`). Provide
a Hugging Face read token with access to that repository in `.env` as
`HF_TOKEN=hf_...`; `run_pipeline.py` forwards it to the Modal job.

For noncommercial research where the official grant is not available, the
pipeline accepts a checkpoint-repo override:

```bash
uv run python run_pipeline.py --video my.mp4 --dataset-id my_room   --vggt-model wincentIsMe/VGGT-Omega
# or through the NLQ wrapper
uv run python "NL Querying/build_memory.py" --video my.mp4 --dataset-id my_room   --vggt-model wincentIsMe/VGGT-Omega
```

`wincentIsMe/VGGT-Omega` is an unmodified public mirror of
`vggt_omega_1b_512.pt` and remains subject to the FAIR Noncommercial Research
License (a copy is in that repository). Prefer the official repository and a
real `HF_TOKEN` for anything beyond local research.

## Communication transports

| Transport | Status | How it connects |
|---|---|---|
| `local` | ✅ working | Reads `r4d_scene_graph.json` from `NL Querying/outputs`, `sample_outputs`, `outputs`, `tests/fixtures`; folds latest states exactly like the production API |
| `modal` | ✅ working | `AEGIS_MODAL_BASE_URL` → `comm/modal_serve.py` (`@modal.asgi_app`) serving the existing `aegis.remote.api` FastAPI over the `aegis-poc-data` volume. The API finds both the canonical `/data/<dataset>/objects/...` layout and the pipeline's `/data/<dataset>/outputs/objects/...` layout. |

### Deployed demo

The `nlq_sample` memory built from `NL Querying/sample_input_video.mp4` is
served at:

```text
https://i230683--aegis-memory-api-serve-memory-api.us-east.modal.run
```

Deploy it with the demo dataset as the default (so `/api/v1/health` reports
the sample memory):

```bash
AEGIS_DATASET_ID=nlq_sample AEGIS_GPU=cpu uv run modal deploy \
    "NL Querying/comm/modal_serve.py"
```

Query it with the `modal` transport:

```bash
export AEGIS_MODAL_BASE_URL=https://i230683--aegis-memory-api-serve-memory-api.us-east.modal.run
uv run python "NL Querying/smoke_test.py" --transport modal \
    --dataset nlq_sample --ask "where is my laptop" --no-llm
# >>> Your laptop is sitting on Desk #1 in the Bedroom.
```

The API is currently unauthenticated (the room-rename endpoints are mutating).
Stop it when the demo is over:

```bash
MODAL_PROFILE=i230683 uv run modal app stop aegis-memory-api
```

## Invariants

1. No evidence → abstain; never fabricate a location.
2. Dataset isolation: one memory view per question, never merged.
3. ≤ 2 sentences, plain words (dementia-friendly phrasing).
4. RAW VGGT-Ω world coordinates; rooms from trajectory clusters, not clouds.
5. The LLM classifies vocabulary only; evidence composes every answer.
