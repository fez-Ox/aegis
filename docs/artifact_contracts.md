# Aegis Artifact Contracts (Milestone 1)

This document freezes the handoff formats that downstream stages depend on. A
contract change requires a schema-version bump and a matching contract test in
`tests/test_live_contracts.py`. Validators live in
`src/aegis/ingestion/contracts.py`.

> Invariant: VGGT-Ω output is the single source of truth for 3D scale and axes.
> No artifact contract may introduce a manual scale factor or axis permutation.

## 1. Canonical paths

| Scope | Root | Layout |
|---|---|---|
| Local dataset | `data/<dataset_id>/` | `frames/`, `metadata.json`, `source_metadata.json`, `live_session.json`, `live_timestamps.json`, `outputs/` |
| Modal data Volume | `/data/<dataset_id>/` | same layout, resolved by `aegis.core.paths.dataset_paths` |
| Local live capture | `captures/<session_id>/` | `frame_*.jpg`, `index.jsonl`, `session.json`, `session_state.json` |

`dataset_id` and `session_id` must match `[A-Za-z0-9][A-Za-z0-9_.-]*`
(`validate_dataset_id`). Path separators are rejected.

## 2. Live session artifacts (schema v2)

### 2.1 Frame record — one line in `index.jsonl`

| Field | Type | Meaning |
|---|---|---|
| `record_type` | `"frame"` | Discriminator. Missing means `frame` for older sessions. |
| `record_schema_version` | `2` | Frame-record schema. |
| `session_id` | string | Session identifier. |
| `sequence` | int ≥ 0 | Monotonic frame index; survives resume. |
| `frame_path` | string | Relative JPEG filename. |
| `source_id` | string | Camera/source identity. |
| `capture_timestamp` | ISO-8601 with timezone | Authoritative capture time. |
| `timestamp_source` | enum | `source_capture`, `laptop_receive_decode`, `ingestion`, or `unknown`. |
| `received_at` | ISO-8601 | Laptop receive/decode time (always recorded). |
| `ingestion_timestamp` | ISO-8601 | When the writer persisted the frame. Never authoritative. |
| `width`, `height` | int > 0 | Decoded pixel dimensions. |
| `encoding` | string | `jpeg` for live frames. |
| `sample_rate_target_hz` | number > 0 | Target sampling rate. |
| `source_protocol` | string | `http-mjpeg`, `fixture`, etc. |
| `keyframe` | object, optional | `KeyframeDecision.as_dict()` when selection is enabled. |

### 2.2 Gap record — `record_type: "gap"`

Recovered gaps are appended to `index.jsonl`. Terminal gaps (a session that
ends disconnected) are stored only in `session.json.gaps`, so the frame count
remains the number of frame lines.

| Field | Type | Meaning |
|---|---|---|
| `record_type` | `"gap"` | Discriminator. |
| `record_schema_version` | `2` | Gap-record schema. |
| `session_id` | string | Session identifier. |
| `gap_start`, `gap_end` | ISO-8601 | Gap window; `gap_end >= gap_start`. |
| `duration_seconds` | number ≥ 0 | Window length. |
| `reason` | enum | `disconnect`, `pause`, `storage_stall`, `source_stall`, `dropped_frames`. |
| `dropped_estimate` | int ≥ 0 | Estimated missed samples. |
| `sequence_before`, `sequence_after` | int or null | Adjacent frame sequences. |
| `recovered` | bool | Whether capture resumed inside the same session. |

### 2.3 Pause record — `session.json.pauses[]`

| Field | Type |
|---|---|
| `pause_id` | int ≥ 1 |
| `started_at`, `ended_at` | ISO-8601 |
| `duration_seconds` | number ≥ 0 |

### 2.4 Session manifest — `session.json`

Schema v2 requires: `schema_version`, `session_id`, `source_id`,
`source_protocol`, `sample_rate_target_hz`, `started_at`, `status`,
`emitted_frame_count`, `frame_count`, `gaps`, `pauses`. `status` is one of
`running`, `completed`, `time_limit`, `stopped`, `disconnected`,
`storage_error`.

Additional v2 fields include `ended_at`, `total_frame_count`, `last_sequence`,
`reconnect_count`, `dropped_frame_count`, `rejected_frame_count`, `buffer`,
`keyframe_selection`, `resumed`, `resumed_at`, and `resumed_from_sequence`.
Schema v1 manifests remain readable.

### 2.5 Crash checkpoint — `session_state.json`

Written after every accepted frame (or every `checkpoint_every` frames). It
contains `schema_version`, `session_id`, `source_id`, `source_protocol`,
`sample_rate_target_hz`, `started_at`, `status`, `last_sequence`, `frame_count`,
`last_frame_path`, `gap_count`, `pause_count`, and `updated_at`.

On resume the writer truncates a half-written trailing index line, continues
from `max(last index sequence, last_sequence) + 1`, and appends to
`index.jsonl`.

## 3. Normalized dataset metadata — `metadata.json`

### 3.1 Batch video (`preprocess_source: "source_video"`)

Schema v2. Required by the validator: `schema_version`, `dataset_id`,
`frame_count`, `resolution` (two positive ints), and a non-empty `frames` list
whose `timestamp` values are non-decreasing. Each frame has `frame_id`,
`filename`, and `timestamp`.

`timebase` is `source_video`. Existing schema-v1 metadata is still readable.

### 3.2 Promoted live session (`preprocess_source: "live_session"`)

Requires schema v2 and `timebase: "capture"`, plus `live_session_id`. Promotion
normalises the first capture timestamp to `0.0` and preserves ordering; the
original timestamps remain in `live_timestamps.json`.

Additional fields: `source_video` (`null`), `live_session_dir`, `source_fps`,
`source_frame_count`, `source_resolution`, `sample_fps`, `duration_sec`,
`timestamp_source`, `authoritative_timestamp_field`, `gaps`, `gap_count`,
`pauses`, `pause_count`, and `keyframe_selection`.

`metadata.json` is what `run_vggt` consumes: it reads `frames[].filename`,
`frames[].frame_id`, `frames[].timestamp`, and `resolution`. A promoted live
dataset therefore needs no `video.mp4`; `run_preprocess` validates it and
records `preprocess_source: "live_session"` in `benchmark_stats.json`.

### 3.3 Companion files

| File | Purpose |
|---|---|
| `source_metadata.json` | Human-readable source/task/duration summary. |
| `live_session.json` | Copy of the capture manifest, including gaps/pauses. |
| `live_timestamps.json` | Per-frame normalised and original capture timestamps. |

## 4. Downstream artifacts (schema v1, unchanged)

| File | Schema | Notes |
|---|---|---|
| `outputs/geometry/poses.json` | 1 | `T_world_camera`, source `VGGT-Omega`. |
| `outputs/geometry/pointmaps.npz` | array keys | `pointmaps`, `confmaps`, `keyframe_ids`. |
| `outputs/geometry/pointcloud.ply` | PLY | Raw VGGT-Ω world coordinates. |
| `outputs/objects/detected_objects_3d.json` | 1 | 2D detections, 3D boxes, motion trails. |
| `outputs/objects/r4d_scene_graph.json` | 1 | Rooms → anchors → object instances; carries `dataset_id`. |
| `outputs/objects/events.json` | 1 | Timeline events. |
| `outputs/objects/spatial_memory_graph.json` | 1 | Layer-1 point cloud + layer-2 R4DSG objects. |
| `<home_id>/home_map.json` | 1 | Caregiver-calibrated room identity registry. |

## 5. Timestamp semantics

1. **Authoritative capture time** is `capture_timestamp`. It is
   `source_capture` when an adapter can expose the phone clock, otherwise
   `laptop_receive_decode` (the current MJPEG path).
2. **`received_at`** is always the laptop receive/decode time and is retained
   for diagnostics even when a phone clock is available.
3. **`ingestion_timestamp`** records when bytes hit local storage. It is never
   used to order memory events.
4. **Promotion** normalises capture timestamps to start at zero and sets
   `timebase: "capture"`. Relative order and deltas are preserved.
5. **Batch normalization** uses the video timebase unless
   `preprocess_video(..., source_timestamps=...)` is supplied, in which case it
   normalises those timestamps and sets `timebase: "capture"`.

## 6. How contracts are enforced

- `validate_frame_record`, `validate_gap_record`, `validate_pause_record`,
  `validate_session_manifest`, `validate_session_state`, and
  `validate_normalized_metadata` raise `ContractError` (a `ValueError`).
- `read_live_index` validates every line and reports the file and line number.
- `run_preprocess` validates promoted metadata and verifies every referenced
  frame exists before the GPU stages run.
- `LiveSessionWriter.close` validates its own manifest before writing it.

Run the contract suite with:

```bash
uv run pytest tests/test_live_contracts.py tests/test_live_handoff.py -q
```
