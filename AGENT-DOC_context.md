# AGENT-DOC_context.md — Aegis Project Context (Model Sync Document)

> **Rule (read first):** Any model/LLM/agent working on this project MUST read this file before making
> changes and MUST update it after making changes. This file is the context-transfer mechanism between
> different models. Add all context, specifics, caveats, limits, bugs, and decisions here so any other
> agent can seamlessly contribute.
>
> This file replaces the former `context/specification.md` reference (that path does not exist in this
> repo). `AGENT-DOC_ToDos.md` cites this file as its spec source.

---

## 1. Project Identity

- **Name:** Aegis — A Spatio-Temporal Memory System for Assistive Care.
- **Academic frame:** NUCES/FAST National University FYP-1 → FYP-2. Mid-term defense dossier in
  `docs/fyp1_mid_defense_dossier.md` (note: contains stale claims — see §9).
- **What it does:** Ingests egocentric (first-person, wearable/head-mounted) video, reconstructs 3D
  space, detects/lifts objects into 3D, and persists a structured **R4DSG (Relative 4D Scene Graph)**
  memory: **Rooms → Spatial Anchors → Object Instances**, with multi-instance identity, object
  permanence through occlusion, and spatial/room-grounded events. A patient (dementia) asks
  "Where are my shoes?" and the system answers from memory with a grounded, evidence-referenced
  explanation; caregivers get a timeline + hazard alerts.
- **Team workflow:** Each agent/developer owns a module; module assignments are tracked in
  `AGENT-DOC_ToDos.md` milestones (M1 Ingestion · M2 Graph & History · M3 Voice Agent · M4 Portal).
  **This agent's assignment: Natural Language Querying** = the M3 question-answering path
  (details in §7).

## 2. Stack & Tooling

- Python 3.12. Dependency management via `uv` (`uv add`, `uv sync`, `uv run`). No ad-hoc pip.
- Lint/format: `uvx ruff check src tests run_pipeline.py run_server.py` and
  `uvx ruff format --check src tests run_pipeline.py run_server.py` — must stay clean after changes.
- Tests: `uv run pytest`. All tests must pass; never mark a ToDo done without a test, measured
  result, or recorded artifact (rule in `AGENT-DOC_ToDos.md`).
- Heavy compute (VGGT-Ω, YOLOE/SAM 2, keyframe VLM if added later) runs on **Modal** serverless
  Linux/L4 GPUs (`src/aegis/remote/modal_app.py`); light query-time memory layout → **in-memory JSON
  graph, in-process** in the FastAPI server; query reasoning currently runs **locally on CPU < 25ms**.
- Flutter mobile app lives in `apps/mobile/` (Android; LAN cleartext allowed in release builds).

## 3. System Architecture (5 Layers)

```text
L1  Sensor & Ingestion      Egocentric video (batch file or live MJPEG from IP Webcam app)
                            → normalization/sampling @15FPS or live 2 FPS → frames + metadata
L2  3D Geometry & Perception  VGGT-Ω feed-forward reconstruction (poses + pointmaps, RAW WORLD
                            COORDS) + YOLOE/YOLO-World + SAM 2 (2D masks) → 2D→3D mask lifting
                            → 3D oriented bounding boxes (OBB) per instance
L3  R4DSG Memory Engine     Rooms (trajectory clustering + landmark typing) → Anchors (recurring
                            containers/furniture, spatial clustering 0.40m) → Object instances
                            (3D centroid clustering < 0.28m + bounded appearance ReID), permanence
                            state machine (is_active_view / is_persistent_memory), events
                            (state_change/pickup/placement/room_change)
L4  Service & Reasoning     FastAPI gateway (run_server.py, /api/v1/*) + QueryReasoningEngine
                            (rule-based NL: synonym tables → item/room slots → template answers)
L5  Presentation            Flutter mobile (patient recall, caregiver audit timeline + hazard
                            alerts) + Rerun viewer (juxtaposed 15 FPS video | 3D scene graph)
```

Raw artifact files in `docs/`:
- `docs/live_capture.md` — phone capture → `aegis-ingest` → session dir → handoff into pipeline (M1 work landed on `origin/develop`).
- `docs/evaluation_plan.md` — reproducible metric protocol (room regions, IDF1/HOTA, query accuracy, latency).

## 4. Repository Map (what lives where)

```text
config/demo.yaml                     Runtime config (FPS, target classes, VGGT, YOLOE+SAM2, rooms, live capture)
run_pipeline.py                      Modal pipeline entry (preprocess | reconstruct | detect | rerun | live | all)
run_server.py                        LAN FastAPI server launcher (--dataset-id selects memory to serve)
src/aegis/core/
  config.py                          RuntimeConfig incl. memory.rooms + live capture settings
  models.py                          CameraIntrinsics, Frame, Pose, Detection2D (+masks), BoundingBox3D (yaw/OBB)
  paths.py                           DatasetPaths, validate_dataset_id, Modal volume path mapping
src/aegis/utils/
  geometry/backproject.py            Depth backprojection
  geometry/vggt_runner.py            VGGT-Ω feed-forward reconstruction (Modal CPU/GPU image)
  geometry/lifting.py                Mask-bearing 2D→3D lifting, OBB fit, containment/relation evaluation
  perception/detector.py             Open-vocab detection YOLOE-11l-seg / YOLO-World + SAM 2
  ingestion/video.py, live_*.py      Batch frame extraction; live MJPEG sessions (pause/gaps/crash-resume)
  memory/
    scene_graph.py                   R4DSG engine: extract_spatial_anchors, classify_unique_instance,
                                     relate_objects_to_anchors, build_relative_4d_scene_graph, events
    rooms.py                         RoomRegion estimation (trajectory clustering + landmarks), footprints
    home_registry.py                 HomeRoomRegistry (per-home room calibration → home_map.json)
                                     ⚠️ implemented but NOT wired into workers.py or the API yet (FR3.6/3.7 gap)
    reasoning.py                     QueryReasoningEngine: extract_target_item / extract_room_filter /
                                     reason_spatio_temporal_state — the ONLY NL path today (rule-based)
  remote/
    modal_app.py                     Modal image/secret definitions, volumes
    workers.py                       Orchestration: preprocess→VGGT→perception→scene graph→Rerun logging
    api.py                           FastAPI gateway (~1130 lines): health, query, timeline, scene_graph,
                                     anchors, rooms(+rename), datasets(select), crops, simulate, reset
apps/mobile/lib/                     Flutter: services/api_service.dart, views/patient + caregiver, models/
tests/                               pytest suite incl. fixtures/ (demo01, demo03, demo04, Demo06-Self)
outputs/                             (per AGENTS.md) downloaded pipeline artifacts e.g. r4d_scene_graph.json,
                                     demo.rrd — CURRENTLY ABSENT from this local tree; fixtures carry test graphs
```

## 5. Data Artifacts (what the memory physically is)

- **Persisted memory file:** `<dataset>/.../r4d_scene_graph.json`. Observed top-level keys:
  `schema_version`, `dataset_id`, `anchors`, `events`, `rooms`, `timeline`. In-memory fills:
  `anchor_id`, `label` ("Storage Cabinet #1"), `center`/`size` (metric, RAW VGGT-Ω world coords),
  `room_id`, `room_label`. Objects/states live in `timeline` (per-frame entries; `instance_id`,
  `label` "Shoes #1", anchor/relation info). `api.py::find_latest_objects_state()` folds the
  per-frame timeline into a latest-state map keyed by `instance_id`.
- **Relation vocabulary (fixed):** `inside`, `on_surface`, `on_floor`, `carried_by_user`,
  `moving_towards`, `near`.
- **Event vocabulary (fixed):** `state_change`, pickup-style transitions, `room_change`; each event has
  source/destination anchor+relation+room, start/end times, event_id (`event_0001`…).
- **`home_map.json`:** per-home stable room identities (caregiver-calibrated names). Module
  `memory/home_registry.py` supports calibrate/match; not yet integrated end-to-end.
- **Room labels:** neutral `Room #N` until caregiver renames via `POST /api/v1/rooms/rename`
  (currently rewrites the scene graph JSON only — not `home_map.json`; ToDo M2.2).
- **Datasets:** `GET /api/v1/datasets` discovers local fixture/outputs dirs; dataset isolation is a hard
  guarantee (queries must never leak across datasets — tested). Missing/corrupt graph ⇒ safe empty
  graph, never a fallback to another dataset.

## 6. Query Path As Implemented TODAY (read this before touching querying)

1. Client (Flutter or browser) calls `GET /api/v1/query?item=<text>&dataset_id=<optional>`.
2. `api.py` loads scene graph JSON (cached per dataset), folds timeline → latest object states.
3. `QueryReasoningEngine.extract_target_item()` — synonym table + room-word stripping + stopword
   removal + naive singularization → canonical item.
4. `extract_room_filter()` — "keys in the kitchen" → room constraint; candidates are filtered by
   `room_label` substring.
5. Ranking: exact lexical match > "active" in label > recency (`last_seen_timestamp`). Primary match +
   `other_instances` list.
6. `reason_spatio_temporal_state()` builds a dementia-friendly template sentence by relation
   (`inside`/`on_surface`/`on_floor`/`carried_by_user`), handles occlusion ("Even though they are
   currently out of direct view… Aegis remembers…") with `is_persistent_memory: true`, inserts a
   grammar-aware room clause ("…inside Storage Cabinet #1 in the Entryway.").
7. Response `MemoryQueryResponse`: found, instance_label, anchor_label, room_label, relation,
   relative_distance_m, location_summary/explanation, last_seen_timestamp_s, crop_url, confidence,
   other_instances. Non-existent item → `found:false` + honest hint listing available labels.

**Hard limits of today's path (these are the assignment's gaps):**
- `item` is treated as a noun phrase; no intents at all. No temporal questions ("when did I last see
  X", "what happened yesterday"), no activity questions ("what did I do this morning") — only
  *where is item* retrieval over latest states + limited event use.
- Hardcoded `confidence=0.96` (line ~729) and `last_seen_time_ago="Recorded today"` regardless of
  actual timestamps (line ~726).
- No speech input: Flutter "Tap to Ask by Voice" button is text-only (re-submits text). No mic, no ASR
  dependency. No TTS anywhere.
- No multimodal queries (no image/VLM input path), no query logging, no abstention semantics
  (hardcoded confidence is effectively always "certain").
- Explanation length often exceeds the 2-sentence target in the spec (NFR-U2).

## 7. ASSIGNMENT — Natural Language Querying (M3, FR5/FR6)

> Question: user asks a question in **text** (typed, or speech-to-text at the client) and a natural
> model answers, grounded strictly in the spatio-temporal memory. Answer returns as **text** (TTS can
> be added for speech out). How it communicates / which components it touches is being designed now.

### 7.1 Exit criteria for the module (from AGENT-DOC_ToDos.md, M3)
- Speech input end-to-end or approved typed-only scope; typed queries remain equivalent (FR6.2, AC-13).
- Temporal intent path: "when did I last see X?" / "what did I do this morning?" / "what happened
  yesterday?" with relative-time resolution against session clock (FR5.2/5.3, AC-10).
- Freshness: 6-hour freshness window; real "time ago" from `last_seen_timestamp`; stale answers must
  say when last seen, never present stale as current (NFR-R3, AC-28).
- Calibrated confidence + configurable abstention threshold; abstain when evidence missing; distinguish
  never-observed vs stale vs low-confidence (FR5.5, AC-12). Never fabricate locations.
- Evidence grounding: every non-abstaining answer carries retrievable evidence (observation ID,
  timestamp, anchor, room, real frame crop — replace the current SVG placeholder with a stored frame
  crop) (FR5.4, AC-11).
- Answer quality: ≤ 2 short sentences + 1 evidence (AC-14); multi-instance → clarifying question or
  options list (UC-03 A3); log every query + resolved evidence (UC-03 postcondition).
- Optional VLM/tool-calling agent over memory after provider choice (open decision #3) — retrieval-first,
  evidence-required, keyframes only.

### 7.2 Candidate architecture paths (under discussion with project owner)

```text
CLIENT (Flutter or HTTP)  ── input: typed text ─┐
                (mic → ASR: on-device plugin OR hosted Whisper)  ── speech→text ─┤
                                                                                  ▼
                                                        FASTAPI GATEWAY (/api/v1 — new endpoint(s))
                                                                                  │
              ┌───────────────────────────┬─────────────────────────────────┴────────┐
              A) Deterministic NLU + retrieval          B) LLM/VLM tool-calling agent          C) Hybrid
              extend QueryReasoningEngine:              LLM receives question + tool specs;    A/B fused:
              intent classifier → slots (item,          calls memory tools: query_item,        classifier routes
              room, time phrase) → resolve against      list_items, get_timeline, get_rooms,   hard intents to A;
              scene graph + events → grounded           search_events; composes answer FROM    free-form/conflicted
              template answer + evidence                tool evidence; must abstain w/o        queries go to B
                                                        evidence
                                                                                  │
                                                                                  ▼
                                       Shared evidence + abstention layer: evidence refs (obs id,
                                       timestamp, anchor, room, crop) + computed confidence; ≤2-sentence
                                       composer; query log store
                                                                                  │
                                                                                  ▼
                                              Answer text → Flutter card (+ optional TTS at client,
                                              e.g. flutter_tts; cloud TTS possible)
```

- **A)** zero hallucination, <500ms guaranteed, no provider dependency, but brittle to paraphrase.
- **B)** robust NL understanding; hallucination risk mitigated ONLY by evidence-required + abstention
  rules; needs provider decision (which LLM, on Modal or hosted elsewhere) + latency budget.
- **C)** recommended default in discussion: cheap deterministic path for the common intents, LLM only
  when rule-based parse fails (low item-type confidence / temporal/activity phrasing).
- Provider/ASR/abstention-threshold choices are deliberately OPEN (AGENT-DOC_ToDos.md cross-cutting
  decisions #2, #3, #8) — do not silently pick one; document in this file when chosen.

## 8. Non-Negotiable Invariants (from AGENTS.md + AGENT-DOC_ToDos.md)

1. RAW VGGT-Ω world coordinates are the spatial source of truth — never reintroduce manual scale or
   axis permutations (an old ×5.0 Z-up transform was deliberately removed; fixes altitude drift).
2. Rooms come from trajectory clustering + sparse landmarks, never from dense point clouds.
3. Room-defining landmark labels (door, sofa, bed, toilet…) are architectural context only and NEVER
   become personal-object memories.
4. Object permanence + multi-instance identity must never regress (occlusion retention, <0.28m
   centroid clustering with bounded appearance ReID).
5. Safe failure over fabrication: no evidence → explicit uncertainty/abstention. Never invent a location.
6. Dataset isolation: answers may only come from the selected dataset's graph (zero leakage).
7. Keep batch path and live path contracts separate but connected via the M1.1 handoff, not merged.
8. Keep `ruff` and the full pytest suite clean; do not claim done without test/measurement/artifact.

## 9. Known Caveats, Bugs, Drift (verified 2026-11-07)

- **Working-tree discrepancy:** `AGENT-DOC_ToDos.md` (verified 2026-11-06) says M1 "done", but the M1
  implementation commits (`live_handoff.py`, `keyframe.py`, bump-format pause/gap tests,
  `test_live_*.py`) are on **`origin/develop` branch, NOT on local `main`** where the agent works.
  Verify branch before assuming; ask the project owner before merging.
- `context/specification.md` referenced by `AGENT-DOC_ToDos.md` does not exist; this file is the
  replacement context source.
- `outputs/` does not exist in the local tree (AGENTS.md/README claim artifacts like
  `outputs/demo.rrd`, `outputs/demo01/objects/r4d_scene_graph.json`). Testable graphs exist under
  `tests/fixtures/<dataset>/objects/r4d_scene_graph.json`. Run the Modal pipeline (or promote fixtures)
  to regenerate real outputs.
- `docs/fyp1_mid_defense_dossier.md` carries stale claims: 55 tests; `S=5.0×`/Z-up transforms
  (removed by invariant #1). Test count in chore docs vs `uv run pytest` may drift — always measure.
- API hardcoded `confidence=0.96`, hardcoded `last_seen_time_ago="Recorded today"` (ToDo M3.3/3.4).
- `/api/v1/crops/{id}` returns a generated SVG placeholder, not a real stored frame crop (ToDo M3.5).
- `home_registry.py` never called in production path; `POST /api/v1/rooms/rename` does not write
  `home_map.json` (ToDo M2.2); wildcard CORS; mutating endpoints unauthenticated (ToDo M4.1).
- `QueryReasoningEngine` has no temporal/wh- intent handling; ignore-words list is hand-built; if any
  new intends get added, extend the tests (`tests/test_reasoning.py`) rather than special-casing.

## 10. Glossary (shared vocabulary across agents)

- **R4DSG** — Relative 4D Scene Graph: Rooms → Spatial Anchors → Object Instances with anchor-relative
  vectors (O→A) and relations.
- **Spatial anchor** — recurring stable furniture/container with 3D OBB ("Storage Cabinet #1", "Desk #1").
- **Object permanence** — a placed object persists in memory when invisible/occluded
  (`is_persistent_memory`, `is_active_view:false`), cannot be evicted while last placement stands
  (zero-hallucination guarantee).
- **Instance IDs / "Shoes #1..#4"** — multi-instance same-class objects disambiguated in 3D; IDs are
  permanent.
- **Rooms** — trajectory-zone regions with optional caregiver-calibrated labels; neutral default
  "Room #N".
- **In-hand / carried_by_user** — kinematic state of objects the wearer is currently holding.
- **Dataset isolation** — strict scoping of all query answers to one dataset's graph.

## 12. Infrastructure Reality & Modal Communication Plan (2026-11-07)

- **There is no always-on server.** The friend/teammate runs the whole pipeline on **Modal** (AI platform):
  `uv run modal run run_pipeline.py --dataset-id X --stage all`. Outputs persist on the Modal volume
  **`aegis-poc-data`** (mounted at `/data`; constant names/env in `remote/modal_app.py`:
  `AEGIS_DATA_VOLUME`, `AEGIS_MODEL_CACHE_VOLUME`). Artifacts are synced locally per run into `outputs/`.
- **Sample outputs provided:** `sample_outputs/demo04/` contains a full artifact set to work from without
  any Modal/GPU spend: `objects/r4d_scene_graph.json` (top keys: schema_version, dataset_id, anchors,
  events, rooms, timeline; 117 timeline frames; 6 events; 2 rooms; 1 anchor "Storage Cabinet #1"),
  `objects/events.json`, `objects/detected_objects_3d.json`, `geometry/poses.json`,
  `benchmark_stats.json`, `viewer/demo.rrd`. Use these for unit tests/mocks when a real run is not needed.
- **Event schema keys (real output):** event_id, event_type, object, instance_id, source_anchor/
  destination_anchor, source_relation/destination_relation, source_room/destination_room,
  start_time/end_time, source_frame/destination_frame, relative_displacement, stable_observations,
  evidence_frames.
- **Room schema keys (real output):** centroid, footprint, end_timestamp, evidence_labels, (id/label).
- **Communication plan agreed (2026-11-07):** Phase 0 join teammate's Modal workspace + `uv run modal
  token new`; Phase 1 prove data in/out with existing `run_pipeline.py` / `modal volume get|put`; Phase 2
  NEW CODE — add `@modal.asgi_app()` function `serve_memory_api` in `modal_app.py` (CPU_IMAGE,
  volumes={DATA_MOUNT: data_volume}) returning `aegis.remote.api.app`, so the existing FastAPI gateway
  is served over HTTPS from Modal with zero changes to api.py (it already probes
  `/data/{dataset_id}/objects/r4d_scene_graph.json` first); Phase 3 validate with curl
  (health/datasets/query) and point Flutter `ApiService.baseUrl` at the printed
  `https://<workspace>--aegis-poc-serve-memory-api.modal.run` URL. Phase 4+ (deferred): `/api/v1/ask`
  NLQ endpoint, ASR (Whisper on Modal), LLM/VLM tool-calling function, `requires_proxy_auth`.
- **Deployment caveats recorded:** serverless cold starts (seconds) vs the <500ms SLA (SLA is measured
  locally in-process; Modal adds network+boot latency); `modal.asgi_app()` URLs are public unless
  proxy auth enabled (tied to open decision #4 / M4.1); `_GRAPH_CACHE` is process-local — graph
  regeneration invalidation is ToDo M2.4.

- **Hybrid mode chosen (2026-11-08):** the NLQ system is **hybrid (Path C) with a very large
  closed-vocabulary dictionary**, NOT open-vocabulary. Unknown words are gated with clarification /
  fuzzy suggestions, never guessed. The LLM escape hatch is now implemented (see §12.1); it only
  maps unknown vocabulary/intent to validated items — evidence still composes every answer.
- **Module folder created: `NL Querying/`** (top level of repo; note the space — its entry points
  bootstrap their own package root onto `sys.path`):
  - `comm/transports.py` — `LocalGraphSource` (reads `sample_outputs/`, `outputs/`, `tests/fixtures/`
    and folds latest states exactly like the production API) and `ModalGraphSource` (HTTPS to the
    deployed Modal memory API); both return one common memory-view dict (dataset_id, anchors, rooms,
    events, latest_objects, timeline_frames, transport).
  - `comm/client.py` — `AegisCommClient` facade (health / list_datasets / load_memory cached per
    dataset / scene_summary).
  - `comm/modal_serve.py` — deployable `@modal.asgi_app()` under `modal.App("aegis-memory-api")`
    (separate app so it never redeploys the GPU pipeline functions); deploy with
    `uv run modal deploy "NL Querying/comm/modal_serve.py"` from repo root.
  - `nlq/dictionary.py` — `DictionaryIndex`, seeded from `aegis.memory.reasoning` synonym tables with
    a fallback copy; `lookup_item` strips room words, longest-synonym-first, returns `Slots`
    (item/room/item_raw); unknown vocab gated with `suggestions_for` (difflib, empty = honest
    "I don't know this word"); `add_item`/`save`/`load` growth hooks.
  - `nlq/engine.py` — `HybridNLQEngine`: intent classifier (LOCATE/TEMPORAL/ACTIVITY/UNKNOWN),
    dictionary slot extraction, latest-state matching/ranking (exact label > active > recency),
    grounding templates ≤2 sentences with room clause and occlusion sentence, undefined-vocabulary
    abstention (`item_not_in_dictionary`), observed-abstence abstention (`not_observed_in_memory`),
    honest TEMPORAL/ACTIVITY stubs (M3.2), LLM fallback stub, in-memory query log (UC-03).
  - `smoke_test.py` — CLI: `uv run python "NL Querying/smoke_test.py" --dataset demo04 --ask "where
    is my water bottle"`; `--transport modal` + `AEGIS_MODAL_BASE_URL` for the live path.
  - `tests/test_comm.py`, `tests/test_engine.py` — offline tests; run with
    `uv run pytest "NL Querying/tests" -q` (repo pytest testpaths is `tests/`, so pass the path
    explicitly).
  - Verified offline in a dependency-free sandbox: dictionary resolution, dataset discovery
    (Demo06-Self, demo01, demo03, demo04 fixtures), grounded answer, unknown-gated abstention,
    temporal stub, query log. Still unrun in a real `uv` environment (`uv sync` first).

### 12.1 NLQ implementation completed + real-run blockers (2026-11-08)

- **Toolchain/workspace facts:** system Python is 3.14 only; repo requires `<3.13`. Installed `uv`
  into `~/.venvs/tools` (PEP 668 blocks user pip), `uv sync` downloaded CPython 3.12. `uv.lock`
  modal upgraded `1.5.4 -> 1.6.3` (old client rejected image-builder `2026.10`). Modal profile
  `i230683` authenticates. `aegis-secrets` created with a harmless placeholder key (empty secrets
  are rejected by the CLI). Volumes `aegis-poc-data` / `aegis-model-cache` auto-create on first use.
- **LLM decision (open decision #3): Qwen served by vLLM on Modal.** `comm/modal_vllm.py` is a
  standalone `modal.App("aegis-llm")` (`@modal.web_server`, L4, model volume, default
  `Qwen/Qwen3-8B-AWQ`, deploy with `uv run modal deploy "NL Querying/comm/modal_vllm.py"`).
  `comm/llm.py` is a provider-agnostic OpenAI-compatible client (`AEGIS_LLM_BASE_URL`,
  `AEGIS_LLM_MODEL`, `AEGIS_LLM_API_KEY` or `AEGIS_LLM_KEY_FILE` default `.keys/openai.txt`,
  `AEGIS_LLM_TIMEOUT`). The `.keys/` directory is gitignored and must never be committed. Keys are
  never logged/serialised.
- **OpenAI reality (verified live 2026-11-08):** `.keys/openai.txt` authenticates at
  `https://api.openai.com/v1` and `/v1/models` returns **96 models** (`gpt-4o-mini`,
  `gpt-4.1-mini`, `gpt-5-mini`, ...). Chat completions fail with HTTP **429
  `insufficient_quota`**: "You have no credits remaining." The client now defaults to OpenAI
  (`gpt-4o-mini`) but surfaces this provider message instead of a generic HTTP error; the engine
  still degrades to honest abstention. Add billing credits to use OpenAI, or override to local
  Ollama/Qwen or Ollama Cloud.
- **Ollama Cloud reality (verified live):** the key in `.keys/ollama.txt` works at
  `https://ollama.com/v1`, but its 26-model catalog contains **no qwen**. Live fallback verification
  therefore used `gpt-oss:20b` and passed: "where are my kicks" → mapped to `shoes` → grounded
  answer "Your shoes are inside Storage Cabinet #1 in Room #1." Unknown "grapefruit peeler" still
  abstains. The qwen path remains: Modal vLLM (blocked by GPU payment) or local
  `qwen2.5:1.5b` + `AEGIS_LLM_BASE_URL=http://localhost:11434/v1`.
- **Escape-hatch contract:** LLM receives question + dataset's canonical items, tracked labels and
  rooms; must return strict JSON `{intent,item,room,confidence}`. `engine._validate_llm_decision`
  rejects any item/room not in the dictionary or actual memory; valid mappings run the same
  LOCATE/TEMPORAL/ACTIVITY handlers. `AskResult.llm_used` audits usage. Network/parse failures
  degrade to honest abstention (`engine.last_llm_error`), never to invention.
- **Dictionary bootstrap:** `scripts/build_dictionary.py` generates `nlq/dictionary.json` from
  (1) `QueryReasoningEngine` tables, (2) `run_pipeline.COMPREHENSIVE_INDOOR_CLASSES` via `ast`,
  (3) `config/demo.yaml` target classes, (4) labels in all local scene graphs. Current output:
  **49 canonical items / 156 synonyms / 13 room keywords**. `DictionaryIndex.seeded()` merges the
  file on top of the live tables; `save/load/add_item/add_room/merge` are the growth hooks.
- **Artifact root:** `LocalGraphSource` now searches `NL Querying/outputs/` **first**, then
  `sample_outputs/`, `outputs/`, `tests/fixtures/`. `build_memory.py` runs
  `modal run run_pipeline.py --video ... --dataset-id ... --stage all` and copies
  `outputs/<dataset>/` into `NL Querying/outputs/<dataset>/` (or `--skip-run` to re-stage).
- **CPU fallback added to the pipeline:** `modal_app.py` now honours `AEGIS_GPU=cpu` (16 CPU /
  40 GB for VGGT+perception instead of `gpu="L4"`); default remains L4. `vggt_runner.py` honours
  `AEGIS_VGGT_STRICT=1` (set on the VGGT image) so a real run raises instead of silently using the
  synthetic test geometry. `workers.py`/`detector.py` already fall back to CPU via
  `torch.cuda.is_available()`.
- **Verification done:** `uv run pytest "NL Querying/tests" -q` → **32 passed**; ruff check/format
  clean on `NL Querying/`; live Ollama fallback + grounded answers verified against `sample_outputs`
  (demo01: shoes inside Storage Cabinet #1, Room #1). The Modal memory API deploy
  (`comm/modal_serve.py`, CPU-only) was attempted twice but its image build died on Modal network
  heartbeats (`Deadline exceeded`); re-deploy after real artifacts exist. `NL Querying/outputs/`
  keeps a tracked README while generated artifacts stay git-ignored.
- **Local Ollama qwen caveat:** `qwen3:4b` pulls fine but Ollama 0.34.1's OpenAI-compatible endpoint
  cannot disable Qwen3 thinking (`/no_think` and `chat_template_kwargs.enable_thinking` are ignored),
  so `content` is empty once the default 200-token budget is spent on `reasoning`. Use a non-thinking
  Qwen locally (`qwen2.5:1.5b`/`qwen2.5:3b`) for smoke tests; Qwen3 works through the Modal vLLM app
  with `enable_thinking: false`.
- **Local Qwen inference verified (2026-11-08):** `qwen2.5:1.5b` via Ollama
  (`http://localhost:11434/v1`) maps "where are my kicks" → `shoes` in ~14 s and returns the grounded
  answer with `llm_used=true`. The first attempt failed because the small model echoed the slang word
  `kicks`; the engine correctly rejected it. The prompt now states the hard rules with few-shot
  mappings, and the engine ignores any LLM-invented room that the user did not mention. Tests: **34
  passed** in `NL Querying/tests`. Environment alias for activation: `~/envs/aegis-env` →
  repo `.venv` (Python 3.12; `PyEnv` is 3.14 and is not the project env).
- **BLOCKERS for the user's video (`sample_input_video.mp4`, 13.5 s, 854x480, 30 fps):**
  1. **Modal GPU requires a payment method** on workspace `i230683` — both L4 and T4 submissions are
     rejected ("Please add a payment method to use … GPU functions"), even though credits exist.
     CPU functions do run (probe: 18 cores). `AEGIS_GPU=cpu` is ready but slower.
  2. **`facebook/VGGT-Omega` weights are gated:** unauthenticated HEAD returns HTTP 401. No
     `HF_TOKEN` exists anywhere on this machine (env, `.env`, HF cache). A token with access to that
     repo must be provided; `run_pipeline.py` forwards it into the Modal job.
  Consequently no real-video artifacts exist yet (`NL Querying/outputs/` absent) and the NLQ answers
  have been validated only against the tracked sample scene graphs. Re-run
  `build_memory.py` once either (a) the workspace gets a payment method + HF token (GPU), or
  (b) an HF token is supplied and `AEGIS_GPU=cpu` is used.

## 13. Session Log (append; newest last)

| Date | Agent | Summary of actions |
|---|---|---|
| 2026-11-07 | GLM-5.3-Flash (OpenCode) | Read all docs + query-path code; wrote this context file (replacing the missing context/specification.md); re-pointed `AGENT-DOC_ToDos.md` source ref; confirmed M1 work lives on origin/develop not main; surveyed today's query path limits; drafted the NL-querying candidate paths (§7.2); no production code touched yet. |
| 2026-11-07 | GLM-5.3-Flash (OpenCode) | Inspected `sample_outputs/demo04` artifact schemas (documented in §12); analyzed `remote/modal_app.py` + `run_pipeline.py`; loaded Modal skill/references; produced and recorded the Modal communication implementation plan in §12 (workspace access → volume round-trip → `@modal.asgi_app()` serve function → curl/Flutter validation → deferred NLQ/ASR/auth phases). No production code touched yet — plan pending project-owner confirmation. |
| 2026-11-08 | GLM-5.3-Flash (OpenCode) | Decision: hybrid NLQ with very large closed-vocabulary dictionary. Created `NL Querying/` skeleton: comm layer (local fixture transport + Modal HTTPS transport + deployable Modal ASGI server), dictionary-seeded NLQ engine with grounded/abstain answering, smoke-test CLI, 11 offline tests; verified offline in sandbox; recorded in §12. Modal deploy itself not yet executed (no workspace access/token here). `HOME/uv` toolchain absent in sandbox — first real run requires `uv sync` + `uv run pytest "NL Querying/tests" -q`. |
| 2026-11-08 | Big Pickle (OpenCode) | Implemented (a) LLM decision recorded, (b) provider-agnostic `comm/llm.py` + Modal vLLM Qwen app `comm/modal_vllm.py` + evidence-gated escape hatch in the engine, (c) `scripts/build_dictionary.py` + generated `nlq/dictionary.json` (49 items/156 synonyms). Added `NL Querying/outputs` priority root, `build_memory.py` runner, CPU mode + strict VGGT guard. Verified: 29 tests pass, ruff clean, live Ollama fallback maps "kicks"→shoes with grounded answer. Real-video run blocked: Modal GPU payment method absent; `facebook/VGGT-Omega` gated (401) and no HF token on machine. Details + exact unblock steps in §12.1. |
