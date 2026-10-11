# Legacy Aegis Migration Notes

Source reviewed: `../../aegis/` on 2026-10-11. This document identifies useful pieces from the older FR1/FR2-focused repository that can be carried into the current Aegis repo. No migration has been performed yet.

## Legacy repo summary

The legacy repo implements a small, local **egocentric capture and ingestion prototype** for:

- **FR1 — Egocentric Visual Capture** using an Android phone running IP Webcam.
- **FR2 — Sensory Data Ingestion** using a laptop-side Python process that pulls an HTTP/MJPEG stream, samples frames, and writes a session dataset.

It does **not** implement memory construction, 3D reconstruction, object tracking, NL querying, UI, speech, or caregiver access. Those are already more developed in this current repo.

## Most useful migration candidates

### 1. Replaceable live frame source abstraction

Legacy files:

- `../../aegis/ingestion/source.py`
- `../../aegis/capture/README.md`

Useful concepts:

- `FrameSource` protocol with a `frames()` iterator.
- `DecodedFrame` carrying an image and receive timestamp.
- `OpenCVMjpegSource` adapter for HTTP/MJPEG streams via `cv2.VideoCapture`.
- `safe_url()` helper that strips credentials/userinfo from URLs before logging or writing manifests.

Why useful here:

The current repo has strong offline/video-file ingestion in `src/aegis/ingestion/video.py`, but not a live egocentric source boundary. The legacy source abstraction could become a new module such as `src/aegis/ingestion/live_source.py` or be merged into a broader ingestion interface.

Potential adaptation:

- Move the protocol/dataclass into `src/aegis/ingestion/`.
- Update imports/package style from flat `ingestion.*` to `aegis.ingestion.*`.
- Decide whether OpenCV should become a core dependency or stay optional for live capture.
- Preserve URL redaction behavior.

### 2. Session writer and generic frame-index contract

Legacy file:

- `../../aegis/ingestion/storage.py`

Useful concepts:

- Creates unique session directories.
- Writes sampled JPEGs.
- Writes `index.jsonl` with one metadata record per frame.
- Writes `session.json` manifest at close.
- Frame record includes:
  - session ID
  - sequence number
  - frame path
  - source ID
  - capture timestamp
  - ingestion timestamp
  - dimensions
  - encoding
  - sample rate
  - source protocol

Why useful here:

The current repo’s pipeline expects dataset frames and metadata, but it is batch-video oriented. The legacy `index.jsonl`/`session.json` contract could be the live-capture handoff into the existing Modal/offline pipeline or a future near-live memory pipeline.

Potential adaptation:

- Convert output format to match or bridge to current `metadata.json` format used by `preprocess_video()`.
- Possibly support both:
  - legacy JSONL session records for raw capture provenance;
  - current normalized frame metadata for downstream reconstruction/perception.
- Add privacy-preserving manifests and credential redaction.

### 3. Bounded ingestion orchestration

Legacy file:

- `../../aegis/ingestion/pipeline.py`

Useful concepts:

- `IngestionConfig` dataclass with configurable:
  - output root
  - source ID
  - sample FPS
  - max duration
  - reconnect interval
  - reconnect timeout
  - source protocol
  - redacted source URL
- `ingest()` loop with:
  - FPS sampling based on frame timestamps;
  - max-duration termination;
  - bounded reconnect attempts;
  - statuses: `completed`, `time_limit`, `stopped`, `disconnected`;
  - injectable source factory, clock, and sleep function for deterministic tests.

Why useful here:

The current system has Modal batch stages, but no local always-on/near-live capture process. This orchestration is directly relevant to FR1/FR2 and can provide a clean first live-ingestion layer before frames are routed into reconstruction/memory.

Potential adaptation:

- Rename/align `IngestionConfig` with current `src/aegis/core/config.py` config model.
- Add conversion from live session output to current dataset layout under `data/<dataset_id>/frames` or Modal volume layout.
- Make reconnect policy configurable through YAML.
- Consider async/event-driven extensions later; keep the initial deterministic loop for reliability.

### 4. CLI for local capture

Legacy file:

- `../../aegis/ingestion/cli.py`

Useful concepts:

- `aegis-ingest` command.
- Reads config from CLI flags or environment variables:
  - `AEGIS_STREAM_URL`
  - `AEGIS_SOURCE_ID`
  - `AEGIS_OUTPUT_ROOT`
  - `AEGIS_SAMPLE_FPS`
  - `AEGIS_MAX_DURATION_SECONDS`
  - `AEGIS_RECONNECT_INTERVAL_SECONDS`
  - `AEGIS_RECONNECT_TIMEOUT_SECONDS`
- Returns non-zero on disconnected sessions.
- Logs session ID, status, frame count, and output path.

Why useful here:

The current repo has `run_pipeline.py` and `run_server.py`, but no simple local command for live capture. This could become a new script/entry point for FR1/FR2.

Potential adaptation:

- Add a project script like `aegis-ingest = "aegis.ingestion.live_cli:main"`.
- Keep env-var support for quick demos.
- Ensure it does not conflict with the existing `aegis` package script.

### 5. Automated ingestion tests

Legacy file:

- `../../aegis/tests/test_ingestion.py`

Useful concepts:

- Tests JPEG persistence and JSONL contract.
- Tests FPS sampling from deterministic synthetic frames.
- Tests unique session directories.
- Uses injected fake source instead of hardware/WiFi.

Why useful here:

These can be ported into current `tests/` to protect FR1/FR2 behavior without requiring a phone stream.

Potential adaptation:

- Update imports to `aegis.ingestion.*`.
- Adjust OpenCV dependency handling if live ingestion is optional.
- Add tests for URL redaction, reconnect manifest fields, and conversion into current pipeline metadata.

### 6. Requirements, design, test plan, and runbook documentation

Legacy files:

- `../../aegis/REQUIREMENTS.md`
- `../../aegis/DESIGN.md`
- `../../aegis/TEST_PLAN.md`
- `../../aegis/RUNBOOK.md`
- `../../aegis/AI_DEVELOPMENT_LOG.md`

Useful concepts:

- FR1/FR2 acceptance criteria.
- Clear scope boundaries: phone capture and local ingestion only.
- Architecture alternatives and rationale for HTTP/MJPEG.
- Frame/session data contract.
- Manual validation protocol for 10-minute capture sessions.
- Privacy and operational limitations.
- AI development log noting assumptions and verification gaps.

Why useful here:

The current repo’s code is stronger for FR3+ and demo UI/backend, but it lacks this detailed FR1/FR2 capture documentation. These docs can help align the full project with the stated feature requirements.

Potential adaptation:

- Create a current-repo `docs/` directory if desired.
- Merge legacy FR1/FR2 requirements into the current README or architecture docs.
- Preserve the manual runbook for phone-based prototype testing.
- Update commands from the legacy flat package to current `uv`/`src/aegis` layout.

## Fit with current repo

Current repo strengths:

- Modal batch pipeline.
- VGGT-Ω reconstruction.
- YOLO-World + SAM 2 detection/lifting.
- R4DSG memory construction.
- FastAPI query service.
- Flutter patient/caregiver prototype.
- Tests for API, reasoning, geometry, lifting, and scene graph.

Legacy repo strengths:

- Practical FR1/FR2 capture layer.
- Local live MJPEG ingestion.
- Sessionized raw-frame persistence.
- Strong acceptance criteria/runbook for physical capture testing.

Best migration strategy later:

1. Port documentation first or create current-repo FR1/FR2 docs.
2. Port source/session abstractions into `src/aegis/ingestion/`.
3. Add tests from legacy repo adapted to current imports.
4. Add CLI entry point for live capture.
5. Add a bridge from live capture sessions to the current dataset metadata format.
6. Only then connect live/session output to the existing Modal reconstruction and memory pipeline.

## Risks / decisions before migration

- Current repo pins Python `>=3.12,<3.13`; legacy supports Python `>=3.10`. Migration should target current Python 3.12.
- Current dependencies do not include OpenCV in `pyproject.toml`; legacy uses `opencv-python`. Decide whether OpenCV belongs in core dependencies, an optional `ingestion` group, or Modal-only images.
- Legacy code writes JPEG frames directly; current pipeline normalizes video frames and metadata from an input video. A metadata bridge is needed to avoid duplicate incompatible frame contracts.
- Live capture may produce sensitive household data. Credential redaction, local-only defaults, gitignore coverage, and retention guidance should be preserved.
- Legacy tests assume a flat package named `ingestion`; imports must be changed.

## Recommendation

The highest-value pieces to carry forward are the **live source abstraction**, **session writer/index contract**, **bounded ingestion loop**, **CLI**, and **FR1/FR2 documentation/runbook**. These fill a clear gap in the current repo: moving from offline demo-video processing toward actual continuous egocentric visual capture and sensory ingestion.
