# Aegis Evaluation Suite

This directory contains a standalone evaluation harness. It reads pipeline
artifacts and compares them with **independent ground truth** (human
annotations or physical measurements). It does not import the pipeline that
creates the predictions, and it never invents a score when an input is missing.

The suite covers:

| Option | Question it answers | Entry point |
|---|---|---|
| **A** | Does the pipeline find the right objects, keep identities, detect events, localise rooms, remember occluded objects, answer questions, stay isolated per dataset, and respond quickly? | `aegis.evaluation.run` |
| **D** | In a measured room, are 3D centres, relations, anchors, and rooms correct? | `aegis.evaluation.controlled_room` |
| **C** | Is an Ego4D benchmark comparison ready to run, and what remains? | `aegis.evaluation.option_c` |
| **Memory control** | Does the timeline stay bounded under compression without losing persisted state? | `aegis.evaluation.memory_audit` |

## 1. Freeze the protocol

1. Pick the held-out video. This repository treats **`demo05`** ("Sort Dirty
   Clothes") as the held-out clip; it has raw video but no processed outputs.
2. Freeze the pipeline config and this repository's commit. Record both.
3. Copy the templates into the annotation directory:
   ```bash
   mkdir -p evaluation/annotations/demo05
   cp evaluation/templates/* evaluation/annotations/demo05/
   ```
4. Annotate the frozen keyframes. Do not change prompts or thresholds after
   looking at held-out scores.
5. Run the pipeline for `demo05` and download its artifacts into
   `outputs/demo05/`.

## 2. Option A — held-out video

```bash
uv run python -m aegis.evaluation.run \
  --config evaluation/configs/demo05.yaml
```

Outputs:

- `evaluation/reports/demo05/summary.md` — panel-readable scorecard, per-class
  tables, failure gallery, ablations, provenance.
- `evaluation/reports/demo05/summary.json` — every metric, confidence interval,
  and failure record.
- `readiness.md` — written instead of scores when annotations or predictions
  are missing. A readiness report is a **status**, not a result.

Sections are skipped individually if their inputs are missing. The report marks
them `NOT RUN`; it does not score them as zero.

### Annotation files

| File | Contents |
|---|---|
| `detections.jsonl` | 2D boxes, optional masks, and stable `instance_id` per object |
| `events.jsonl` | pickup/placement/state-change/room-change intervals |
| `rooms.json` | room footprints, per-keyframe room IDs, room transitions |
| `queries.jsonl` | held-out question bank with expected location fields |
| `persistence.jsonl` | occlusion/relocation cases with check frames |
| `controlled_room_measurements.csv` | Option D physical measurements |

See `evaluation/templates/annotation_guide.md` for labelling rules.

### What is scored

- **Detection:** class-aware micro/macro precision, recall, F1, per-class AP@0.5,
  mask IoU when masks exist.
- **Tracking:** IDF1, MOTA, ID switches, fragmentation, mostly-tracked ratio.
  HOTA is **not** approximated; the harness can export MOT rows, and TrackEval
  should be used if the full HOTA family is required.
- **Events:** one-to-one matching with a ±1 s boundary tolerance.
- **Rooms:** per-keyframe accuracy after maximum-agreement ID mapping, Hydra-style
  footprint containment precision/recall, and room-change F1.
- **Persistence:** state recall, query recall, identity consistency, false-merge
  rate on labelled occlusion/relocation cases.
- **Queries:** grounded answer accuracy (instance + anchor + room + relation),
  false-found and false-not-found rates, p50/p95/max latency.
- **Isolation:** cross-dataset probes. The target leakage rate is exactly 0.
- **Ablations:** `full`, `no_persistence`, `no_memory`, `no_rooms` compared on
  the same question bank and persistence cases.

## 3. Option D — controlled room

Record the room once with a floor grid and a known-size reference. Measure each
object's centre in the same coordinate frame.

```bash
uv run python -m aegis.evaluation.controlled_room \
  --measurements evaluation/annotations/controlled_room/measurements.csv \
  --scene-graph outputs/controlled_room/objects/r4d_scene_graph.json \
  --output-dir evaluation/reports/controlled_room
```

The checker aligns predicted centres to measurements with a similarity
transform (Umeyama: scale, rotation, translation) and reports:

- scale-aligned 3D centre error (mean, median, RMSE, p95, max);
- fitted scale factor and its deviation from 1;
- relation, anchor, and room accuracy;
- per-object errors and unmatched measurements.

**Scale caveat.** Monocular reconstruction is scale-ambiguous. The error is
scale-aligned unless `--assume-metric-scale` is passed and the fitted scale is
close to 1. Do not quote absolute metres without that support.

## 4. Memory control

```bash
uv run python -m aegis.evaluation.memory_audit \
  --snapshot-intervals 0,10,30 \
  --output-dir evaluation/reports/memory_control
```

The audit measures graph size, entries per frame, state runs, and projected
growth, then compacts the timeline into per-instance state runs plus sparse
centre snapshots plus an exact latest state. It reports:

- full/semantic/label/active-view/last-seen retention;
- centre and relative-distance reconstruction error;
- exact latest-state agreement and query agreement;
- canonical and gzip size ratios.

The compaction prototype lives in the evaluation package on purpose: it is
evidence, not a silent change to production memory. See
`docs/memory_control.md` for the full explanation.

## 5. Option C — Ego4D readiness

```bash
uv run python -m aegis.evaluation.option_c \
  --facts evaluation/configs/option_c_facts.yaml
```

This writes a go / conditional-go / no-go decision, a weighted checklist, the
remaining effort, and the adapter contract. It also contains Ego4D-style NLQ
and VQ2D temporal scoring for sanity checks. Those scorers are readiness
estimates, **not** official leaderboard metrics. See
`docs/option_c_feasibility.md`.

## 6. Tests and lint

```bash
uv run pytest
uvx ruff check src tests run_pipeline.py run_server.py
uvx ruff format --check src tests run_pipeline.py run_server.py
```

The evaluation tests use synthetic annotations and graphs, so they do not
depend on downloaded artifacts or GPU access.

## 7. Reading a report honestly

- `PASS` means the measured value reached the frozen target. It is not proof of
  clinical usefulness.
- `FAIL` is information. The failure gallery shows what went wrong.
- `NOT RUN` means the harness refused to score without ground truth.
- Confidence intervals describe sampling uncertainty in the labelled cases, not
  annotation error.
- A held-out score is only credible if the protocol was frozen first. Keep the
  commit, config, annotation hash, and input hash in the report provenance.
