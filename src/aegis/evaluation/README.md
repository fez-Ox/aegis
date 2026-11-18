# `aegis.evaluation` — honest evaluation harness

The harness lives outside the pipeline and reads only saved artifacts plus
independent annotations. It refuses to invent a score: missing inputs produce
`NOT_READY`, not zero. Full protocol and status: `docs/evaluation_suite.md`.

| Module | Role |
|---|---|
| `run.py`, `config.py`, `schema.py`, `io.py` | Option A (held-out video): detection, IDF1/tracking, events, rooms, persistence, query accuracy, latency, leakage, ablations; readiness gate and config freeze. |
| `controlled_room.py` | Option D: Umeyama scale alignment, centre error, relation/anchor/room accuracy, Wilson intervals. |
| `option_c.py` | Ego4D readiness scorecard, effort estimate, adapter contract. |
| `memory_audit.py` | Bounded-growth / compaction audit (state runs, sparse snapshots, retention and query agreement). |
| `metrics.py`, `measurements.py`, `query.py`, `report.py` | Metric arithmetic, room metrics, API-backed query scoring, Markdown/JSON reports with provenance. |

Generated reports live in `evaluation/reports/`:
`demo05` = **NOT_READY** (no predictions, no annotations),
`option_c` = **NO_GO / 0%**, `memory_control` = measured on short clips
("feasible in principle"). No controlled-room report yet.

Tests: `test_evaluation*.py`, `test_evaluation_controlled_room.py`,
`test_evaluation_option_c.py`, `test_evaluation_memory_audit.py`.
