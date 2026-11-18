# `aegis.ingestion` — capture, normalization, handoff

Two separate paths, connected only by promotion.

**Batch:** `download.py` (presets/URL/file), `video.py` (sample + resize to
960×540, write frames + schema-v2 `metadata.json` + intrinsics).

**Live:** `live_source.py` (`FrameSource` protocol, `OpenCVMjpegSource`,
credential-safe URLs), `live_pipeline.py` (2 Hz sampling, keyframe gate, gap
and pause records, reconnect loop), `live_storage.py` (JPEG frames,
`index.jsonl`, `session.json`, `session_state.json`, resume), `keyframe.py`
(sharpness/brightness/novelty/duplicate rules + forced interval), `buffer.py`
(bounded stall buffer with drop/backlog counters), `live_cli.py`
(`aegis-ingest`, `--resume`, `--promote-dataset-id`, stall injection).

**Handoff:** `live_handoff.py` promotes a session (or resumable segments) into
`data/<id>` with byte-copied JPEGs and `timebase: "capture"`;
`segment_runner.py` drives each segment through upload → stages → download →
home ingest with `pipeline_state.json` checkpoints and `--follow`.

**Contracts:** `contracts.py` validates every frame/gap/pause/manifest record.
Schemas are frozen in `docs/artifact_contracts.md`; changes require a version
bump and a test in `tests/test_live_contracts.py`.

Tests: `test_live_ingestion.py`, `test_live_keyframe.py`, `test_live_buffer.py`,
`test_live_contracts.py`, `test_live_handoff.py`, `test_live_segments.py`,
`test_live_cli.py`, `test_video_ingestion.py`.
