# Live Egocentric Capture

Aegis has a real phone → frames → VGGT/perception → R4DSG path:

```text
Android / IP Webcam MJPEG
        -> OpenCVMjpegSource
        -> ingest_live sampling, pause control, keyframes, gap recovery
        -> LiveSessionWriter (JPEG + index.jsonl + session.json + checkpoints)
        -> promote_live_session (data/<dataset_id>: PNG + metadata.json)
        -> run_preprocess / run_vggt / run_detect_and_lift / run_rerun
        -> mobile API + Rerun
```

The source boundary is `aegis.ingestion.FrameSource`. Wearable or RTSP adapters
can implement the same `frames()` iterator without changing persistence,
promotion, or the memory pipeline. Artifact shapes are frozen in
[`artifact_contracts.md`](artifact_contracts.md).

## 1. Run a capture session

```bash
uv sync
uv run aegis-ingest \
  --url 'http://PHONE_IP:8080/video' \
  --source-id android-ip-webcam-01 \
  --output-root ./captures \
  --config-path config/demo.yaml \
  --sample-fps 2 \
  --max-duration 3600 \
  --session-id walkthrough-01 \
  --keyframe-selection
```

The URL may also be supplied as `AEGIS_STREAM_URL`. Other supported environment
variables are `AEGIS_SOURCE_ID`, `AEGIS_OUTPUT_ROOT`, `AEGIS_SAMPLE_FPS`,
`AEGIS_MAX_DURATION_SECONDS`, `AEGIS_RECONNECT_INTERVAL_SECONDS`,
`AEGIS_RECONNECT_TIMEOUT_SECONDS`, `AEGIS_BUFFER_CAPACITY`,
`AEGIS_CHECKPOINT_EVERY`, `AEGIS_SESSION_ID`, `AEGIS_CONFIG_PATH`, and
`AEGIS_PAUSE_FILE`.

Capture settings resolve as **CLI flag > environment variable > `live:` block in
`--config-path` > built-in default**. With `config/demo.yaml` the defaults are
2 FPS, a 3,600 s duration limit, a 30-frame stall buffer, checkpoints every 5
frames, and keyframe selection enabled.

Credentials are accepted in the URL when the camera app requires them, but the
CLI and manifests redact URL userinfo (`safe_url`). Do not commit credentials.

## 2. Pause and resume capture

A session can be paused in three equivalent ways:

```bash
# 1. While the process is running: SIGUSR1 pauses, SIGUSR2 resumes.
kill -USR1 <pid>
kill -USR2 <pid>

# 2. File-based control: capture is paused while this file exists.
touch captures/.pause
rm captures/.pause

# 3. Start with a pause file path.
uv run aegis-ingest --url ... --pause-file captures/.pause
```

While paused, no frames are written. One `pauses[]` entry is added to
`session.json` and one recovered `pause` gap is appended to `index.jsonl`,
including the estimated number of missed samples.

## 3. Keyframe selection

`config/demo.yaml` enables criterion-based selection. It keeps a frame only when
it is:

- exposed (`min_brightness` / `max_brightness`),
- sharp enough (`Laplacian` variance ≥ `min_sharpness`),
- visually different from the last accepted frame (`min_visual_change`),
- or overdue (`max_interval_seconds`, so a static scene is still represented).

Rejected frames are counted in the session manifest under
`keyframe_selection.rejected_by_reason`. Each accepted frame record carries its
sharpness, brightness, visual-change score, and decision reason.

Use `--no-keyframe-selection` to keep fixed-rate sampling.

## 4. Disconnects, gaps, and stall buffering

- A source failure opens a **disconnect gap**. If the stream recovers before
  `reconnect_timeout_seconds`, the gap is written to `index.jsonl` with
  `recovered: true`. If the timeout expires, the session ends
  `disconnected` and the gap is stored only in `session.json.gaps`; this keeps
  the number of index frame lines equal to the number of frames.
- A slow/failed storage write opens a **storage-stall gap**. Accepted frames
  wait in a bounded `FrameBuffer` (`buffer_capacity`). If the buffer fills, the
  oldest frames are dropped and counted (`dropped_frame_count`); the gap records
  the estimated loss. When storage recovers, the queue drains automatically.
- Pauses produce `pause` gaps as described above.

## 5. Crash recovery

The writer checkpoints `session_state.json` after every accepted frame (or every
`checkpoint_every` frames). If the process dies:

```bash
uv run aegis-ingest \
  --url 'http://PHONE_IP:8080/video' \
  --output-root ./captures \
  --session-id walkthrough-01 \
  --resume
```

Resume truncates a half-written trailing JSONL line, continues sequence numbers
from the last durable frame, and appends to the same `index.jsonl`. No frame
older than the last checkpoint is lost.

## 6. Promote a session into the memory pipeline

```bash
# Promote and upload, then run preprocess only.
uv run python run_pipeline.py \
  --live-session captures/walkthrough-01 \
  --dataset-id live_walkthrough_01 \
  --stage live

# Promote and run the complete VGGT -> perception -> R4DSG -> Rerun path.
uv run python run_pipeline.py \
  --live-session captures/walkthrough-01 \
  --dataset-id live_walkthrough_01 \
  --stage all

# Or ask the runner for the newest capture directory.
uv run modal run run_pipeline.py --dataset-id live_walkthrough_01 --stage live --live-session latest
```

Promotion writes `data/<dataset_id>/frames/frame_XXXXXX.png`, a schema-v2
`metadata.json` with `preprocess_source: "live_session"` and
`timebase: "capture"`, plus `source_metadata.json`, `live_session.json`, and
`live_timestamps.json`. The dataset directory is uploaded to
`modal://aegis-poc-data/<dataset_id>/` before the remote preprocess stage runs.
`run_preprocess` detects the promoted metadata and does not require
`video.mp4`.

The CLI can promote without invoking Modal:

```bash
uv run aegis-ingest ... --promote-dataset-id live_walkthrough_01
```

## 7. Session artifact layout

```text
captures/walkthrough-01/
  frame_00000000_20251106T101500.120Z.jpg
  frame_00000001_20251106T101500.620Z.jpg
  index.jsonl          # frame and recovered-gap records (schema v2)
  session.json         # manifest: status, gaps, pauses, counts (schema v2)
  session_state.json   # crash-recovery checkpoint (schema v2)
```

After promotion:

```text
data/live_walkthrough_01/
  frames/frame_000000.png ...
  metadata.json
  source_metadata.json
  live_session.json
  live_timestamps.json
  outputs/geometry/...
  outputs/objects/r4d_scene_graph.json
  outputs/viewer/demo.rrd
```

## 8. Status values

| Status | Meaning |
|---|---|
| `time_limit` | Configured duration elapsed. |
| `stopped` | Operator interrupted the process. |
| `disconnected` | Source failure continued beyond the reconnect timeout. |
| `storage_error` | Storage remained unavailable at session end. |
| `completed` | Source ended after a successful run (finite fixtures). |

The CLI exits non-zero for `disconnected` and `storage_error`.

## 9. Verification

Deterministic tests (no phone or network needed):

```bash
uv run pytest tests/test_live_ingestion.py tests/test_live_keyframe.py \
  tests/test_live_buffer.py tests/test_live_contracts.py \
  tests/test_live_handoff.py tests/test_live_cli.py -q
```

`tests/test_live_ingestion.py::test_simulated_one_hour_session` runs a
deterministic 3,600-frame / 3,600-second session with a fake clock. This proves
loop stability, sequence continuity, checkpointing, and clean time-limit
termination; it does **not** replace a physical phone soak.

For a physical soak, keep the phone on the same WiFi and run:

```bash
uv run aegis-ingest --url 'http://PHONE_IP:8080/video' \
  --max-duration 3600 --session-id soak-$(date +%Y%m%d) \
  --config-path config/demo.yaml
```

Verify afterwards: `session.json.status == "time_limit"`, no unexpected gaps,
`frame_count` close to `sample_fps × duration`, and a readable JPEG for the
first and last sequence numbers.
