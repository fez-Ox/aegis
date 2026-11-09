# Long-Term Persistence and Memory Control

## 1. The worry

A care assistant that runs for days must not let its memory grow without bound.
The current R4DSG timeline stores one entry per known instance per keyframe,
including instances that are currently occluded. That is exactly what gives
object permanence — a hidden object stays queryable — but the raw size grows as

```
entries ≈ frames × known instances
```

For a short demo this is small. For a full day it is not obviously safe. The
question for the panel is:

> Can the memory keep every object's latest state and every event, while storing
> far fewer per-frame entries and without breaking answers?

This document describes the measured feasibility study. The prototype lives in
`src/aegis/evaluation/memory_audit.py`; it is **not** a silent change to the
production memory engine.

## 2. What is measured

### 2.1 Growth audit

For each scene graph:

- frames, duration, entries, instances, anchors, rooms, events;
- entries per frame and per instance;
- semantic **state runs** (a new run only when the state changes);
- canonical JSON bytes, gzip bytes, bytes per frame;
- linear projections to 8 h and 24 h, explicitly labelled as projections.

### 2.2 Compaction prototype

The compact representation keeps:

1. **per-instance state runs** — start/end frame, timestamp, and all semantic
   fields (`label`, `anchor`, `room`, `relation`, `is_in_hand`, `carrier`);
2. **sparse centre snapshots** every N keyframes — `center`, `size`,
   `relative_vector`, `relative_distance`, `rotation`, `yaw`;
3. an **exact latest state** for every instance;
4. **active-view ranges** — enough to reconstruct `is_active_view` and
   `last_seen_timestamp` without storing a boolean per frame;
5. unchanged anchors, rooms, events, and frame timestamps.

Between snapshots, geometry is linearly interpolated. The snapshot interval is
the tunable knob: larger intervals compress more but increase reconstruction
error.

### 2.3 Retention metrics

The reconstructed timeline is compared with the original, entry by entry:

| Metric | Meaning |
|---|---|
| **full retention** | semantic state + active-view flag + last-seen timestamp all match exactly |
| **semantic retention** | label, anchor, room, relation, carrier, hand state match |
| **label retention** | canonical label matches |
| **active-view retention** | `is_active_view` matches |
| **last-seen retention** | `last_seen_timestamp` matches within 1 µs |
| **centre error** | L2 distance between original and reconstructed centres, in scene units |
| **latest-state exactness** | every instance's final semantic state matches exactly |
| **query agreement** | answers from the compacted latest state match answers from the original |

Query agreement uses the same `answer_query` path as the API, so a change in
answer wording or grounding would be visible.

## 3. What the existing clips show

The audit was designed against the graphs already in `outputs/`:

| Dataset | Frames | Entries | Instances | Semantic runs | Entries / run |
|---|---:|---:|---:|---:|---:|
| `demo04` | 117 | 268 | 5 | 10 | 26.8 |
| `demo03` | 243 | 981 | 16 | 56 | 17.5 |
| `demo01` | 145 | 280 | 7 | 7 | 40.0 |
| `demo_pots` | 131 | 385 | 8 | 8 | 48.1 |

The point is not the exact ratio; it is the shape. Semantic state changes are
rare compared with keyframes. A run-length representation should therefore be
much smaller than the per-frame timeline while preserving the states that
queries actually use.

These are **short clips**. The projected 8 h / 24 h numbers are linear
extrapolations from the observed state-change rate, not measured long sessions.
The report labels them accordingly.

## 4. What the study proves — and does not prove

### Proves (if the metrics pass)

- The representation can preserve every instance's semantic state, latest
  state, events, anchors, and rooms while storing far fewer per-frame entries.
- Query answers from the compacted latest state can be compared with the
  original; agreement is measured, not assumed.
- The size/accuracy trade-off is visible, so a deployment can choose a snapshot
  interval with evidence.

### Does not prove

- **Real-world persistence over days.** That needs a long recording with
  labelled occlusion and relocation events; the current clips are minutes long.
- **Production database performance.** The prototype serialises JSON. A real
  deployment should use SQLite or Parquet with indices, and measure query
  latency at scale.
- **Metric 3D accuracy.** Centre errors are in scene units because VGGT-Ω is
  scale-ambiguous. Use the controlled-room experiment for metric calibration.
- **That compression is free.** Interpolation between snapshots is an
  approximation; the report states the error instead of hiding it.

## 5. Recommended integration path

1. Keep the full-resolution timeline as an append-only archive, or delete it
   after compaction.
2. Serve queries from the compacted latest state and state runs.
3. Keep a sparse snapshot every 10–30 keyframes for point-in-time
   reconstruction. Choose the interval from the measured error, not a guess.
4. Store events, anchors, and rooms unchanged; they are already small.
5. Add a retention policy: keep all state runs, downsample snapshots for
   sessions older than N days.
6. Move the prototype into the memory engine only after the evaluation tests
   cover reconstruction and query parity.

The prototype remains in the evaluation package until step 6. That keeps the
production path unchanged and makes the evidence auditable.

## 6. Reproduce

```bash
uv run python -m aegis.evaluation.memory_audit \
  --graphs outputs/demo04/objects/r4d_scene_graph.json \
           outputs/demo03/objects/r4d_scene_graph.json \
  --snapshot-intervals 0,10,30 \
  --output-dir evaluation/reports/memory_control
```

Outputs:

- `evaluation/reports/memory_control/summary.json` — audit, per-interval
  retention, compression, projections, recommendation;
- `evaluation/reports/memory_control/summary.md` — panel-readable tables and
  the feasibility verdict.

The `--write-compacted` flag also writes the compacted graphs for inspection.
It is off by default because the compacted files are evidence artifacts, not
production data.

## 7. How to read the verdict

- **Feasible in principle** — at least one interval preserved full state at a
  centre p95 ≤ 0.05 scene units, and the size ratio is reported. This is a
  representation result, not a long-term field result.
- **Needs attention** — no tested interval met that bar. Increase snapshot
  density, or accept and state an approximation. Do not quietly lower the bar.

The verdict is a statement about the representation and the measured clips. It
is not a claim that Aegis has run for a week in a care home.
