# `tests` — automated test suite

Run: `uv run pytest -q` (currently **385 passed**). CI adds
`--cov=aegis --cov-fail-under=75`. `pyproject.toml` sets
`testpaths = ["tests"]`.

Coverage by area:

| Area | Tests |
|---|---|
| Config/ontology | `test_config.py`, `test_vocabulary.py` |
| Geometry/perception | `test_geometry.py`, `test_gravity.py`, `test_planar.py`, `test_lifting.py`, `test_detector_postprocess.py`, `test_modal_compute.py` |
| Memory engine | `test_scene_graph.py`, `test_anchors.py`, `test_association.py`, `test_relations.py`, `test_runs.py`, `test_rooms.py` |
| Store/history | `test_store.py`, `test_ingest.py`, `test_matching.py`, `test_home_registry.py`, `test_room_identity.py`, `test_compaction.py`, `test_activities.py`, `test_evidence.py`, `test_repository.py`, `test_restart_equivalence.py` |
| API/reasoning | `test_api.py`, `test_reasoning.py`, `test_capture_control.py`, `test_mid1_prototype.py` |
| Ingestion/live | `test_video_ingestion.py`, `test_live_*.py`, `test_contracts.py` (in `test_live_contracts.py`), `test_wallclock.py` |
| Evaluation | `test_evaluation*.py` |
| Visualization | `test_rerun_visualization.py` |

`fixtures/<dataset>/objects/r4d_scene_graph.json` are legacy **schema v1**
graphs used for backward-compatibility tests; do not regenerate them.
`_graphs.py` holds shared graph builders.

`test_nlq.py` covers the consolidated engine, `/api/v1/ask` and the CLI in the
same run (see `TODO.md` P0.7).
