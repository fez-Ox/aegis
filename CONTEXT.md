# CONTEXT.md — Aegis single source of truth

> **Rule:** This is the only context file. `TODO.md` is the only task list.
> All older status/context documents are in `docs/archive/` and are history,
> not instructions. Verified against the working tree on 2026-11-18
> (branch `feat/NLQ`, head `46ed2c1`). Last updated: 2026-11-18.

---

## 1. What Aegis is

Aegis is an assistive-care memory system. It turns first-person video into a
3D-grounded spatio-temporal memory (Rooms → Spatial Anchors → Object
Instances) so a person with memory loss can ask *"Where are my keys?"* and get
a short, evidence-grounded answer. Caregivers get a timeline. The system must
never invent a location: no evidence means an explicit abstention.

## 2. The one canonical pipeline

```text
IP Webcam (phone, MJPEG over Wi-Fi)
  │
  ├─ aegis-ingest (laptop CLI only; capture, keyframes, gaps, pause, resume)
  │      └─ promotes to data/<id> (schema-v2 metadata, JPEG frames)
  │
  └─ run_pipeline.py --live-session ... --stage live / --video ... --stage all
         └─ uploads dataset to Modal volume aegis-poc-data (/data)
              │
              ├─ preprocess      → normalized frames + metadata
              ├─ VGGT-Ω          → poses, pointmaps, gravity.json (RANSAC floor)
              ├─ detect + lift   → YOLOE/YOLO-World + SAM 2 masks → 3D OBBs
              ├─ memory          → schema-v2 r4d_scene_graph.json (state runs,
              │                    latest states, events, rooms) on the volume
              └─ ask (Modal CPU) → rule-based NLQ over that graph
                     │
                     ├─ HTTPS → Flutter app: send question, receive answer
                     └─ HTTPS → aegis-ask terminal CLI
```

**Normal operation requires no artifact download to the laptop.** `run_pipeline.py`
leaves artifacts on the Modal volume unless `--download` is passed (needed only
for local Rerun/home-store demos). The Modal API serves the graph directly from
`/data/<dataset>/outputs/...`. Local `outputs/` and `sample_outputs/` are a
development/offline fallback only.

The phone app is a **thin query client**. It does not run reconstruction,
detection, tracking, promotion, or any simulator/mutation flow.

## 3. Active repository map

| Path | Purpose |
|---|---|
| `run_pipeline.py` | Modal pipeline driver (`all`, `live`, `preprocess`, `vggt`, `detect`, `rerun`) |
| `run_server.py` | Optional local FastAPI/Uvicorn launcher for development |
| `config/vocabulary.yaml` | Single label ontology (prompts, roles, synonyms, importance, affordances) |
| `config/demo.yaml`, `config/live.yaml` | Runtime config; task-scoped variants `demo01/03/04/06.yaml` |
| `src/aegis/core/` | Config, data models, vocabulary, canonical paths, time helpers |
| `src/aegis/ingestion/` | Batch + live capture, keyframes, buffer, contracts, promotion, segments |
| `src/aegis/geometry/` | VGGT-Ω runner, gravity, planar geometry, 2D→3D lifting, transforms |
| `src/aegis/perception/` | Open-vocab detection, SAM 2 masks, tracking, appearance re-ID |
| `src/aegis/memory/` | R4DSG builder, anchors/association/relations/runs/rooms, per-home SQLite store, matching, ingest, compaction, activities, evidence, reasoning, repository, CLI |
| `src/aegis/nlq/` | The one NLQ engine: dictionary, ask engine, CLI (terminal script) |
| `src/aegis/remote/` | Modal images/workers (`modal_app.py`, `workers.py`) and FastAPI gateway (`api.py`) |
| `src/aegis/evaluation/` | Held-out / controlled-room / Ego4D / memory-control harness (no scoring without ground truth) |
| `src/aegis/visualization/` | Rerun recording (video left, 3D memory right) |
| `apps/mobile/` | Thin Flutter ask/answer client |
| `scripts/` | Measurement and maintenance scripts |
| `docs/running_aegis.md` | Operational runbook |
| `docs/artifact_contracts.md` | Frozen artifact schemas and validators |
| `docs/evaluation_suite.md` | Evaluation protocol and honest status |

Archived history: `docs/archive/` (see `docs/archive/README.md`).

## 4. Data contracts (summary; details in `docs/artifact_contracts.md`)

- Scene graph `r4d_scene_graph.json` **schema v2**: `schema_version`, `session`,
  `gravity`, `anchors`, `rooms`, `state_runs`, `latest_states`, `events`,
  `room_visits`. Size does not grow with video length. Readers still accept
  legacy v1 graphs with `timeline`.
- Per-keyframe view is `r4d_timeline.json`, used only by Rerun.
- Home store: one SQLite file per home, `<store_root>/<home_id>/memory.db`
  (default `outputs/_homes`). Stable room/anchor/instance IDs across sessions;
  last-known state is never compacted. `SCHEMA_VERSION = 1` (store) is
  independent of graph schema 2.
- Live session: `frame_*.jpg`, `index.jsonl` (frame + gap records),
  `session.json`, `session_state.json`, all schema v2, validated by
  `ingestion/contracts.py`.
- All wall-clock values are fixed-format UTC ISO strings (`core/timeutil.py`).

## 5. What works today

- Batch and live ingestion with criterion keyframes, bounded buffering,
  pause/gap records, crash resume, and resumable live segments.
- VGGT-Ω reconstruction in **raw world coordinates**; per-session gravity from
  a RANSAC floor fit, stored beside the coordinates, never baked into them.
  The checkpoint comes from `facebook/VGGT-Omega` when the HF account is on the
  gated repo's authorized list; otherwise the worker logs a warning and uses
  the public mirror `wincentIsMe/VGGT-Omega` (same weights, same license).
- Open-vocab detection + SAM 2 masks + mask-grounded oriented 3D boxes;
  multi-instance identity with appearance re-ID and object permanence through
  occlusion.
- Relations `inside`, `on_surface`, `under`, `above`, `next_to`, `on_floor`,
  `near`, `in_room`, `carried_by_user`; events `pickup`, `placement`,
  `anchor_change`, `state_change`, `room_change`, `moved_while_unobserved`.
- Per-home SQLite memory with symbolic cross-session matching, caregiver room
  naming persisted to `home_map.json`, activities, object-only evidence crops,
  and verified 3-day-then-summary compaction with week/month roll-up.
- FastAPI with dual read paths (session JSON or home store); dataset isolation
  and safe failure for missing/corrupt graphs.
- Rerun visualization of video and 3D memory.
- Rule-based NLQ with a 525-item closed vocabulary; grounded answers and
  honest abstentions. `TEMPORAL`/`ACTIVITY` intents currently abstain by design.
- Evaluation harness that refuses to invent scores (`NOT_READY` / `NO_GO`).

## 6. Invariants (never regress)

1. Raw VGGT-Ω coordinates are the spatial source of truth; no manual scale or
   axis transforms. Derived quantities live beside the coordinates.
2. Rooms come from trajectory clustering + sparse landmarks, never dense
   clouds. Landmarks never become personal-object memories.
3. Object permanence and multi-instance identity must not regress.
4. No evidence → explicit uncertainty/abstention. Never fabricate a location,
   anchor, room, or confidence.
5. Dataset isolation: one memory view per question; zero cross-dataset leakage.
6. Batch and live contracts stay separate, connected only by promotion.
7. The app never mutates memory and never reconstructs or tracks anything.

## 7. Commands

```bash
# everything, one command (stops and waits when a human step is required)
uv run python scripts/run_e2e.py

# ingest from a phone (laptop CLI)
uv run aegis-ingest --url 'http://PHONE:8080/video' --output-root ./captures \
  --session-id walk01 --config-path config/live.yaml

# full pipeline on Modal (CPU fallback: AEGIS_GPU=cpu)
uv run python run_pipeline.py --live-session captures/walk01 \
  --dataset-id walk01 --config-path config/live.yaml --stage live

# deploy the Modal memory + ask API (serves /data, no local download)
AEGIS_DATASET_ID=walk01 uv run modal deploy src/aegis/remote/serve.py

# ask from the terminal (http transport talks to the Modal HTTPS URL)
uv run aegis-ask "where are my keys" --dataset-id walk01
uv run aegis-ask "where are my keys" --dataset-id walk01 --transport local

# local development API (optional)
uv run python run_server.py --dataset-id walk01

# verify
uv run pytest -q
uvx ruff check src tests run_pipeline.py run_server.py
uvx ruff format --check src tests run_pipeline.py run_server.py
```

`uv` lives at `~/.venvs/tools/bin/uv` on this machine (not on PATH).

## 8. Document policy

Active: this file, `TODO.md`, `README.md`, `AGENTS.md`, and the three docs
listed in §3. Everything else is archived in `docs/archive/` with an index.
When a decision is made, update `CONTEXT.md` (facts) and `TODO.md` (work) in
the same commit; do not create a new parallel document.

## 9. Known gaps

See `TODO.md`. The short version: temporal/activity answering, calibrated
confidence and freshness, evidence refs in NLQ, auth/encryption/privacy, and
all physical measurements are still open. Documentation numbers in archived
files (84, 129, 326, 55 tests, `S=5.0×`, Z-up) are wrong — current counts are
**388 tests in one suite**.
