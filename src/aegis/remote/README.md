# `aegis.remote` — Modal compute and the FastAPI gateway

| Module | Role |
|---|---|
| `modal_app.py` | Modal `App`, volumes (`aegis-poc-data` → `/data`, `aegis-model-cache` → `/models`), secret `aegis-secrets`, CPU/CUDA/VGGT/perception images, warm GPU classes (`Reconstructor`, `Perception`, `scaledown_window=300`), CPU fallback via `AEGIS_GPU=cpu`. |
| `serve.py` | Deploys **only** `aegis-memory-api`: a small FastAPI image with the graph mounted from `/data`. It must not import `modal_app`, or `modal deploy` would rebuild the CUDA/VGGT images and redeploy the pipeline. |
| `workers.py` | Remote stages: `run_preprocess` → `run_vggt` (poses, pointmaps, gravity) → `run_detect_and_lift` (3D boxes, R4DSG v2 graph, evidence crops) → `run_rerun`. Writes all artifacts to the Modal volume. |
| `api.py` | FastAPI gateway. `resolve_repository()` selects the durable home store (`home_id`) or one session's JSON graph (`dataset_id`). Routes: health, dataset select, scene graph, anchors, rooms/rename, query, **ask**, timeline, activities, crops, video, capture control, simulator (flag-gated). |

`api.py` is also the app served by the Modal ASGI deployment: the same code
runs locally (`run_server.py`) and over HTTPS, reading the graph from the
volume so the normal path needs no local artifact download. It resolves the
graph at `<mount>/<dataset>/outputs/objects/r4d_scene_graph.json`
(`AEGIS_DATA_MOUNT`, default `/data`), which is exactly where the pipeline
writes; a flat `<dataset>/objects` path is only a fallback for old volumes.

The single NLQ entry point is `GET/POST /api/v1/ask`, implemented by
`aegis.nlq`. `GET /api/v1/query` remains as a lower-level, bare-item endpoint.

Known gap: no authentication; CORS is still wildcard (see `TODO.md` P1.7).
