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
│   ├── dictionary.json   GENERATED vocabulary (scripts/build_dictionary.py)
│   └── engine.py         HybridNLQEngine: intent → dictionary → evidence →
│                         grounded answer / abstention; LLM escape hatch
├── scripts/
│   └── build_dictionary.py  regenerates dictionary.json from every source
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

The default provider is OpenAI, reading the key from `.keys/openai.txt`. The
entire `.keys/` directory is gitignored and must never be committed. If the
OpenAI account has no credits, use `--no-llm` for dictionary-only mode or the
local Ollama override below.

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
AEGIS_GPU=cpu uv run python "NL Querying/build_memory.py"

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
| OpenAI (default) | key in `.keys/openai.txt`; `AEGIS_LLM_BASE_URL=https://api.openai.com/v1`, `AEGIS_LLM_MODEL=gpt-4o-mini` | Auth is valid (`/v1/models` returns 200 with 96 models), but the current account has **no credits**: chat completions return HTTP 429 `insufficient_quota` ("no credits remaining"). Add billing credits or use another provider. |
| Ollama Cloud (working fallback) | `AEGIS_LLM_BASE_URL=https://ollama.com/v1`, `AEGIS_LLM_MODEL=gpt-oss:20b`, key in `AEGIS_LLM_API_KEY` or `.keys/ollama.txt` | The cloud catalog for the current key has **no qwen** model; `gpt-oss:20b` is used for live verification. |
| Local Ollama + Qwen | `AEGIS_LLM_BASE_URL=http://localhost:11434/v1`, `AEGIS_LLM_MODEL=qwen2.5:1.5b` (or `qwen2.5:3b`), `AEGIS_LLM_API_KEY=ollama` | Non-thinking Qwen works without cloud keys. Avoid `qwen3:*` on old Ollama versions: their reasoning fills the token budget and the OpenAI endpoint returns empty content. |
| Modal vLLM + Qwen (designed) | deploy `comm/modal_vllm.py`, then `AEGIS_LLM_BASE_URL=https://<workspace>--aegis-llm-serve.modal.run/v1`, `AEGIS_LLM_MODEL=Qwen/Qwen3-8B-AWQ`, any non-empty key | Needs a GPU-capable Modal workspace. |

Variable reference: `AEGIS_LLM_BASE_URL` (default `https://api.openai.com/v1`),
`AEGIS_LLM_MODEL` (default `gpt-4o-mini`), `AEGIS_LLM_API_KEY`,
`AEGIS_LLM_KEY_FILE` (default `.keys/openai.txt`), `AEGIS_LLM_TIMEOUT`,
`AEGIS_LLM_EXTRA_BODY` (JSON merged into the request; Qwen3 on vLLM can use
`{"chat_template_kwargs": {"enable_thinking": false}}`).

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
tables, so growth is data-only and never removes existing synonyms.

`scripts/build_dictionary.py` harvests:

- `QueryReasoningEngine.ITEM_SYNONYMS` / `ROOM_KEYWORDS`;
- `run_pipeline.COMPREHENSIVE_INDOOR_CLASSES` (read via `ast`, no Modal import);
- `config/demo.yaml` `perception.target_classes`;
- object/anchor labels from real scene graphs in all local artifact roots.

## Communication transports

| Transport | Status | How it connects |
|---|---|---|
| `local` | ✅ working | Reads `r4d_scene_graph.json` from `NL Querying/outputs`, `sample_outputs`, `outputs`, `tests/fixtures`; folds latest states exactly like the production API |
| `modal` | 🔜 one deploy away | `AEGIS_MODAL_BASE_URL` → `comm/modal_serve.py` (`@modal.asgi_app`) serving the existing `aegis.remote.api` FastAPI over the `aegis-poc-data` volume |

## Invariants

1. No evidence → abstain; never fabricate a location.
2. Dataset isolation: one memory view per question, never merged.
3. ≤ 2 sentences, plain words (dementia-friendly phrasing).
4. RAW VGGT-Ω world coordinates; rooms from trajectory clusters, not clouds.
5. The LLM classifies vocabulary only; evidence composes every answer.
