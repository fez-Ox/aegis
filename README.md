# Aegis

[![Aegis CI](https://github.com/fez-Ox/aegis/actions/workflows/ci.yml/badge.svg)](https://github.com/fez-Ox/aegis/actions/workflows/ci.yml)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://docs.astral.sh/ruff/)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)

Aegis turns egocentric video into a 3D-grounded spatio-temporal memory so a
person with memory loss can ask *"Where are my keys?"* and get a short,
evidence-grounded answer — never a guess.

**Start here:** [`CONTEXT.md`](CONTEXT.md) (architecture and current truth) and
[`TODO.md`](TODO.md) (the only task list). Older status documents are archived
in [`docs/archive/`](docs/archive/README.md).

## Pipeline at a glance

```text
IP Webcam → aegis-ingest (laptop CLI) → Modal volume
          → Modal: preprocess · VGGT-Ω · detect/lift · R4DSG memory · NLQ ask
          → HTTPS answer to the Flutter app and the aegis-ask terminal CLI
```

Normal operation needs no local artifact download. The app only asks
questions and displays answers; `docs/running_aegis.md` has the commands.

## Repository layout

Each directory has its own `README.md` describing its modules and contracts.

| Path | Description |
|---|---|
| `src/aegis/core/` | Config, data models, the single label ontology, canonical paths, time helpers. |
| `src/aegis/ingestion/` | Batch + live capture, criterion keyframes, gap/pause records, crash resume, promotion and segments, frozen artifact contracts. |
| `src/aegis/geometry/` | VGGT-Ω reconstruction, gravity estimation, planar geometry, mask-grounded oriented 3D boxes. |
| `src/aegis/perception/` | Open-vocabulary detection, SAM 2 masks, tracking and appearance re-ID. |
| `src/aegis/memory/` | R4DSG builder (Rooms → Anchors → Instances), per-home SQLite store, cross-session matching, activities, evidence, compaction, reasoning, repository, CLI. |
| `src/aegis/nlq/` | The one rule-based NLQ engine (dictionary, ask engine) used by the API and terminal CLI. |
| `src/aegis/remote/` | Modal images/workers and the FastAPI gateway (`/api/v1/ask`, query, timeline, rooms, …). |
| `src/aegis/visualization/` | Rerun recording: video left, 3D memory right. |
| `src/aegis/evaluation/` | Harness that refuses to invent scores (`NOT_READY`/`NO_GO`). |
| `config/` | `vocabulary.yaml` (single ontology), generic/live/task-scoped runtime configs. |
| `apps/Patient App/` | Flutter patient app (ask, voice search, object tiles, first-run caregiver setup + call). Built from `patient.html`. |
| `apps/Caregiver App/` | Caregiver app folder (HTML mockup `caregiver.html`; Flutter app to follow). |
| `scripts/` | Measurement and maintenance scripts. |
| `tests/` | 356 passing core tests plus fixtures. |
| `docs/` | Active: `running_aegis.md`, `artifact_contracts.md`, `evaluation_suite.md`; history: `archive/`. |

## Quickstart

```bash
uv sync --dev
uv run pytest -q                 # 388 passed
uvx ruff check src tests run_pipeline.py run_server.py
uvx ruff format --check src tests run_pipeline.py run_server.py

uv run python run_pipeline.py --video put_shoes --dataset-id shoes01 \
  --config-path config/demo01.yaml --stage all
uv run modal deploy src/aegis/remote/serve.py     # graph + /ask on Modal
uv run aegis-ask "where are my shoes" --dataset-id shoes01  # or the app
```

On this machine `uv` is at `~/.venvs/tools/bin/uv` (system Python is 3.14;
the project requires 3.12).
