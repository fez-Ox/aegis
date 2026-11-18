# `aegis.memory` — the spatio-temporal memory engine

**Per-session graph (schema v2):** `scene_graph.py` orchestrates the builder;
`anchors.py` clusters furniture, `rooms.py` clusters the wearer's trajectory
and types rooms by landmarks, `association.py` assigns persistent instance
IDs (track → 3D/appearance → relocation → new), `relations.py` +
`geometry/planar.py` decide `inside/on_surface/under/above/next_to/on_floor/
near/in_room`, `runs.py` debounces states into runs and emits events. Output:
`r4d_scene_graph.json` (schema 2: `state_runs`, `latest_states`, `events`,
`room_visits`, no per-keyframe timeline) plus `r4d_timeline.json` for Rerun.

**Durable home memory:** `store.py` (one SQLite file per home, tables for
room/anchor/instance/state_run/event/room_visit/activity/evidence/summary/
compaction_log), `ingest.py` (session merge; no-op on unchanged graph,
replaces only its own session, chronological order enforced), `matching.py`
(pure symbolic cross-session matching: rooms by signature, anchors by unique →
2D alignment → residents → ordinal → new, instances by place → carried →
class → appearance), `homes.py` + `home_registry.py` (caregiver room names
persisted to SQLite and mirrored to `home_map.json`).

**History and answers:** `activities.py` (room stays + events with template
summaries), `evidence.py` (one object-only JPEG crop per state run),
`summaries.py` + `compaction.py` (3-day hot detail, verified text summaries,
week/month roll-up; never on the query path), `reasoning.py` (where-question
templates and event summaries), `repository.py` (v1/v2 JSON reader and store
reader behind one interface), `cli.py` (`aegis-memory ingest|show|size|compact`).

`synthetic.py` is a test-only deterministic graph generator.

Invariants: last-known state is never compacted; history is append-only across
sessions; no fabricated anchors or locations; landmarks are context only.

Tests: `test_scene_graph.py`, `test_anchors.py`, `test_association.py`,
`test_relations.py`, `test_runs.py`, `test_rooms.py`, `test_store.py`,
`test_ingest.py`, `test_matching.py`, `test_room_identity.py`,
`test_compaction.py`, `test_activities.py`, `test_evidence.py`,
`test_repository.py`, `test_reasoning.py`, `test_restart_equivalence.py`.
