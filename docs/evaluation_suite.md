# Evaluation Suite (Option A and Option D)

This document explains the evaluation harness that turns the FYP-1 rubric's
*Testing & Early Validation* requirement into reproducible measurements. It
implements **Option A** (held-out video evaluation) and **Option D**
(controlled-room spatial experiment), with supporting feasibility tools for
**Option C** (Ego4D) and **memory control** (long-term growth).

The short version for the panel:

> We do not self-grade. The harness compares pipeline artifacts with human
> annotations or physical measurements, reports confidence intervals and
> failure cases, and writes "not ready" instead of inventing a score when the
> ground truth is missing.

## 1. Why a separate harness

The pipeline that produces predictions must not also define the scoring. This
package therefore:

- lives under `src/aegis/evaluation/` and is not imported by the pipeline;
- reads only saved artifacts (`r4d_scene_graph.json`, `detected_objects_3d.json`,
  `poses.json`) plus annotation files;
- reuses the API's query-matching helpers so the scored path is the production
  path, not an evaluation-only imitation;
- records input hashes, git commit, config path, Python version, and platform in
  every report;
- refuses to score a section whose inputs are absent (`NOT RUN`, not zero).

## 2. Option A — held-out video protocol

### 2.1 Split discipline

| Role | Clip | Use |
|---|---|---|
| Development | `demo01`, `demo03`, `demo04` | Tune prompts, thresholds, tracking. |
| Held-out | `demo05` ("Sort Dirty Clothes") | Report final results; no tuning after freeze. |
| Optional generalisation | other rooms/tasks | Show transfer, not the headline number. |

The split unit is the **complete video**, never a frame. Frames from one video
must not appear in both development and held-out sets. `demo05` is deliberately
unprocessed at the time of writing: the raw video exists, but no scene graph,
detections, or poses. That is what makes it a genuine held-out clip.

### 2.2 Metrics and targets

Targets are acceptance criteria frozen before scoring. They are not results.

| Layer | Metric | Target | Why it matters |
|---|---|---:|---|
| Detection | precision | ≥ 0.85 | False boxes waste caregiver trust. |
| Detection | recall | ≥ 0.75 | Missed objects break the memory. |
| Detection | F1 | ≥ 0.80 | Balanced headline. |
| Tracking | IDF1 | ≥ 0.75 | Same name on the same object. |
| Events | F1 (±1 s) | ≥ 0.75 | Pickup/placement is the memory update. |
| Rooms | per-keyframe accuracy | ≥ 0.90 | Room-grounded answers need it. |
| Rooms | room-change F1 | ≥ 0.70 | Transitions are safety-relevant. |
| Persistence | state recall | ≥ 0.90 | Occluded objects stay queryable. |
| Persistence | query recall | ≥ 0.90 | The API must answer from memory. |
| Queries | grounded accuracy | ≥ 0.80 | Instance + anchor + room + relation. |
| Isolation | leakage rate | = 0.00 | No foreign memories. |
| Latency | p95 | < 500 ms | Dementia-appropriate response. |

Detection uses class-aware matching at IoU 0.5. Mask IoU is reported only for
matched pairs that have both ground-truth and predicted masks. AP is
all-point interpolated per class. Tracking reports IDF1, MOTA, ID switches,
fragmentation, and mostly-tracked ratio. **HOTA is not approximated**: a
home-made HOTA would be less credible than saying "use TrackEval". The harness
keeps enough MOT information for that export.

Room scoring has three parts:

1. **per-keyframe accuracy** after mapping predicted room IDs onto ground-truth
   IDs by maximum frame agreement;
2. **Hydra-style region containment** precision/recall on footprints;
3. **room-change event F1** with the same ±1 s tolerance as object events.

Mapping IDs is necessary because a neutral `Room #2` in the prediction is not
required to have the same number as `Room #2` in the annotation. What matters
is that the same physical room is consistently identified.

### 2.3 Persistence scoring

Each labelled case names a query, an expected instance, an anchor, a room, a
relation, and a check frame. The scorer:

- finds the memory entry at the last keyframe at or before the check frame;
- verifies label, instance ID, anchor, room, relation;
- answers the query against a graph slice containing only memory known at that
  frame;
- checks whether the entry is still an active view when the case expects
  persistent memory;
- counts false merges when the predicted label differs from the expected label.

Occlusion survival is therefore measured on the **query path**, not just by
looking for a row in the timeline.

### 2.4 Ablations

The same question bank and persistence cases are re-run against four memory
variants:

| Variant | What is removed | What a drop means |
|---|---|---|
| `full` | nothing | Baseline. |
| `no_persistence` | remembered entries that are not currently visible | The score depends on object permanence. |
| `no_memory` | everything except the final active view | The score depends on history. |
| `no_rooms` | room IDs and labels | The score depends on room grounding. |

Ablations are diagnostic. They show which component a score depends on; they do
not prove that the component is correct.

### 2.5 Isolation

For every pair of processed datasets, the harness probes the target dataset with
labels unique to the other dataset, plus a configured list of items that must
never appear (`keys`, `wallet`, `glasses`, `medication`, `phone`). A `found:
true` answer is leakage. The target is exactly 0, because a care assistant that
answers from another resident's memory is worse than one that says "I don't
know".

### 2.6 Latency

Latency is measured through the real FastAPI route after one warm-up request,
with 100 requests by default. The report keeps p50, p95, max, mean, and error
count. Graph-mode timings are also recorded, but the headline number should be
the HTTP route because that is what the mobile app calls.

### 2.7 Report contents

`summary.md` contains:

1. scorecard with claim, metric, result, target, verdict, n, and note;
2. inputs and hashes;
3. per-class detection table and mask summary;
4. tracking summary;
5. event failures;
6. room confusion matrix and region metrics;
7. persistence failures;
8. query failures with expected vs actual;
9. latency and dataset-isolation probes;
10. ablation table;
11. failure gallery;
12. method and limitations;
13. provenance;
14. exact reproduce command.

`summary.json` contains the same data plus typed records for downstream tools.

## 3. Option D — controlled-room experiment

### 3.1 Setup

- One room, measured with a floor grid and at least one known-size reference.
- 5–10 objects spanning `inside`, `on_surface`, `on_floor`, and
  `carried_by_user`.
- Each object measured three times from a fixed room origin; use the median.
- Record the room name and anchor name exactly as the caregiver would use them.

### 3.2 Alignment

Monocular reconstruction is scale-ambiguous. Reporting raw 3D error in metres
would be dishonest. The checker therefore fits a similarity transform
(Umeyama: scale, rotation, translation) from predicted centres to measured
centres, then reports:

- **scale-aligned centre error** (mean, median, RMSE, p95, max);
- **fitted scale factor** and deviation from 1;
- fraction of objects within the target error;
- relation, anchor, and room accuracy (independent of alignment);
- per-object errors and unmatched measurements.

The scale factor is itself evidence. A value near 1 supports the claim that the
pipeline's units are approximately metric; a value far from 1 says the
reconstruction is only up to scale. `--assume-metric-scale` adds a pass/fail
check at ±10%, but it must be justified by the protocol.

### 3.3 Targets

| Measure | Target |
|---|---:|
| Mean scale-aligned centre error | ≤ 0.30 m |
| Relation accuracy | ≥ 0.80 |
| Anchor accuracy | ≥ 0.80 |
| Room accuracy | ≥ 0.90 |

These targets are deliberately modest. A single room is a demonstration, not a
generalisation study.

## 4. Reproducibility

Every report records:

- config path and dataset ID;
- git commit, branch, and dirty flag;
- SHA-256 of every input file;
- Python version and platform;
- generated timestamp;
- the exact command to reproduce.

The harness has no hidden dependency on SciPy, matplotlib, pandas, pycocotools,
or TrackEval. It uses NumPy and the standard library. MOT export is available
for anyone who wants the official HOTA implementation.

## 5. What this evaluation does not prove

- It does not prove clinical usefulness or safety.
- It does not replace a usability study with older adults or caregivers.
- It does not prove generalisation beyond the annotated clips.
- It does not make 3D errors metric without a measured room and a scale check.
- It does not turn a readiness report into a result. A readiness report is a
  statement that the evidence does not exist yet.
- It does not approximate HOTA or official Ego4D metrics. Those require the
  official implementations.

## 6. Commands

```bash
# Option A (writes readiness.md until annotations and predictions exist)
uv run python -m aegis.evaluation.run \
  --config evaluation/configs/demo05.yaml

# Option D
uv run python -m aegis.evaluation.controlled_room \
  --measurements evaluation/annotations/controlled_room/measurements.csv \
  --scene-graph outputs/controlled_room/objects/r4d_scene_graph.json \
  --output-dir evaluation/reports/controlled_room

# Memory control
uv run python -m aegis.evaluation.memory_audit \
  --snapshot-intervals 0,1,10,30 \
  --output-dir evaluation/reports/memory_control

# Option C readiness
uv run python -m aegis.evaluation.option_c \
  --facts evaluation/configs/option_c_facts.yaml

# Tests and lint
uv run pytest
uvx ruff check src tests run_pipeline.py run_server.py
uvx ruff format --check src tests run_pipeline.py run_server.py
```
