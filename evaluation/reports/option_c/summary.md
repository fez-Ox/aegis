# Option C — Ego4D benchmark readiness

**Decision:** `NO_GO`  
**Readiness score:** 0.0% (0/100 points)  
**Estimated remaining effort:** 10.8 weeks

> Too many prerequisites are missing to justify a benchmark claim. Report Option C as future work instead.

## Why Option C is a research extension, not a quick add-on

- Ego4D access is gated; approval is usually fast (~48 h), but credentials expire in ~14 days.
- The benchmark subset is large (order of ~1 TB), so transfer and GPU time are real costs.
- Ego4D is an egocentric *general* dataset, not an assistive-care dataset. A score there supports generalisation of perception/grounding, not clinical usefulness.
- The official leaderboard requires the official splits, official metrics, and no test-set tuning.

## Readiness checklist

| Category | Prerequisite | Weight | Done | Blocker |
| --- | --- | ---: | --- | --- |
| access | Ego4D license approved and credentials issued | 20 | NO | yes |
| access | Benchmark credentials valid for the evaluation window | 5 | NO |  |
| data | Held-out benchmark videos downloaded locally | 10 | NO | yes |
| data | Official annotations and splits downloaded | 10 | NO | yes |
| engineering | Aegis -> Ego4D annotation adapter implemented | 15 | NO | yes |
| engineering | Aegis query and memory outputs mapped to benchmark answers | 5 | NO |  |
| science | Scoring validated against official task definitions | 10 | NO |  |
| engineering | GPU and storage budget confirmed for the subset | 10 | NO |  |
| governance | Ethics/privacy review covers benchmark and demo data | 5 | NO |  |
| science | Benchmark protocol and success criteria frozen before scoring | 5 | NO |  |
| science | Domain mismatch risk stated and bounded | 5 | NO |  |

## Category scores

| Category | Score | Points |
| --- | ---: | ---: |
| access | 0% | 0/25 |
| data | 0% | 0/20 |
| engineering | 0% | 0/30 |
| governance | 0% | 0/5 |
| science | 0% | 0/20 |

## Remaining work

| Prerequisite | Blocker | Effort (weeks) | What to do |
| --- | --- | ---: | --- |
| Ego4D license approved and credentials issued | YES | 0.3 | Apply through the Ego4D portal (Lab22); approval is typically ~48 h after signing. |
| Benchmark credentials valid for the evaluation window |  | 0.2 | Credentials last ~14 days; confirm the window covers download, annotation, and scoring. |
| Held-out benchmark videos downloaded locally | YES | 1.5 | Plan storage and transfer time; the benchmark subset is order ~1 TB. |
| Official annotations and splits downloaded | YES | 0.3 | Use official splits; do not re-split videos that share scenes. |
| Aegis -> Ego4D annotation adapter implemented | YES | 4.0 | Map queries, temporal windows, tracks, and video/clip identifiers; budget 3–6 weeks. |
| Aegis query and memory outputs mapped to benchmark answers |  | 1.0 | Decide whether NLQ answers use anchors, rooms, or raw windows. |
| Scoring validated against official task definitions |  | 1.0 | Compare on a small official sample before running the full subset. |
| GPU and storage budget confirmed for the subset |  | 0.5 | Estimate Modal cost from measured per-video runtime, not optimism. |
| Ethics/privacy review covers benchmark and demo data |  | 1.0 | Keep the public benchmark and the care demo data separate. |
| Benchmark protocol and success criteria frozen before scoring |  | 0.5 | Same freeze discipline as the held-out Aegis video. |
| Domain mismatch risk stated and bounded |  | 0.5 | Ego4D is not an assistive-care dataset; do not over-claim transfer. |

## Recorded constraints

- **license_portal:** Ego4D (Lab22) gated access
- **approval_lead_time:** ≈48 h after signing the agreement, but do not promise a date
- **credential_lifetime_days:** 14
- **benchmark_subset_size:** order of 1 TB
- **adapter_effort_weeks:** ≈3–6 depending on task coverage
- **domain:** general egocentric video, not assistive care
- **existing_aegis_data:** demo01–demo05 are Hub egocentric iPhone clips, not Ego4D

## Adapter contract

```json
version: 1
purpose: Convert official Ego4D clips and annotations into Aegis pipeline inputs and evaluation records
  without changing benchmark semantics.
inputs:
  video: <ego4d_root>/videos/<video_uid>.mp4
  clips: <ego4d_root>/annotations/nlq_train.json | nlq_val.json
  vq2d: <ego4d_root>/annotations/vq_train.json | vq_val.json
  official_splits: official train/val/test split files; never re-split
clip_record:
  required:
  - clip_uid
  - video_uid
  - video_start_sec
  - video_end_sec
  notes: Aegis processes the clip window; timestamps in queries are relative to the clip start unless
    the adapter records otherwise.
query_record:
  required:
  - query_id
  - clip_uid
  - query
  - start_time
  - end_time
  maps_to: aegis.evaluation.schema.QuerySpec for NLQ-style checks
  notes: Keep the original query text. Do not paraphrase benchmark queries after the protocol is frozen.
vq2d_record:
  required:
  - query_id
  - clip_uid
  - response_track
  response_track_item:
  - timestamp
  - x
  - y
  - w
  - h
  maps_to: aegis.evaluation.option_c.BoxObservation (xyxy pixels)
aegis_outputs:
  scene_graph: outputs/<clip_uid>/objects/r4d_scene_graph.json
  detections: outputs/<clip_uid>/objects/detected_objects_3d.json
  poses: outputs/<clip_uid>/geometry/poses.json
scoring:
  nlq: score_nlq(...) with temporal IoU thresholds 0.3 and 0.5
  vq2d: score_vq2d(...) with timestamp tolerance and box IoU 0.5
  official_parity_required: Before publishing, re-score with the official Ego4D evaluation code on the
    official val/test splits.
must_not_do:
- Mix clips from one video across splits.
- Tune prompts, classes, or thresholds on the benchmark test split.
- Report Aegis-specific metrics as official Ego4D leaderboard numbers.
- Treat Ego4D results as clinical or assistive-care validation.
```

## Bottom line for the panel

Option C is **future work with a concrete plan**, not a result. The defensible move is to report the score above, show the adapter contract, and state that no Ego4D number exists yet. Inventing a number from a different dataset would not survive review.
