# Aegis Pipeline Evaluation Plan

This plan turns the FYP-1 rubric's **Testing & Early Validation** requirement into
reproducible measurements. It is intentionally small: one annotated subset,
one fixed baseline, one ablation, and one live API check.

## 1. Evaluation questions

1. Does perception find and segment the relevant objects in each video?
2. Does 3D lifting preserve object location and anchor relationships?
3. Does R4DSG keep identities and memories correct through occlusion?
4. Does the API answer only from the selected dataset, including for unknown items?
5. Is the complete pipeline and mobile demonstration fast and reproducible?

## 2. Fixed evaluation set

Use complete videos as the split unit; never put frames from one video in both
sets.

| Split | Videos | Purpose |
|---|---|---|
| Development | `demo01`, `demo03` | Tune prompts, thresholds, and tracking. |
| Held-out test | `demo04` | Report final results without further tuning. |
| Optional generalisation | `demo_pots`, `Demo06-Self` | Show transfer to another room/task. |

For Demo04, annotate all 117 pipeline keyframes (or every fifth source frame)
with: object class, bounding box, binary mask, visibility, instance ID, anchor,
and transition/event interval. Mark an object as *occluded* rather than absent
when the last confirmed state is still valid. Two annotators should label at
least 20% of the frames; adjudicate disagreements and report their mean mask
IoU as annotation agreement.

## 3. Metrics and proposed targets

Targets below are acceptance targets, not results. They should be frozen after
a short development pilot and then measured on Demo04.

### Perception and tracking

- **Detection precision, recall, F1** per target class; report macro average.
- **Mask quality:** mean IoU and mask AP50 on annotated objects.
- **Tracking:** IDF1, HOTA, ID switches, and track fragmentation.
- Suggested initial targets: precision >= 0.85, recall >= 0.75, mask IoU >=
  0.70, and IDF1 >= 0.75. Include a per-class table; do not hide classes
  with zero detections.

### 3D and scene graph

- Object 3D center error in metres against measured/annotated reference points.
- Anchor center error and relation accuracy (`inside`, `on_surface`,
  `on_floor`, `carried_by_user`).
- Event precision/recall/F1 using a +/-1 second boundary tolerance.
- Multi-instance identity accuracy through the sequence.
- Occlusion persistence recall: fraction of deliberately occluded objects that
  remain queryable with the correct last anchor and relation.
- Proposed targets: relation accuracy >= 0.80, event F1 >= 0.75, and occlusion
  persistence recall >= 0.90. Report mean absolute centre error rather than
  claiming metric accuracy without physical measurements.

### Query/API/mobile

- **Dataset isolation:** cross-dataset leakage rate must be exactly 0. Run
  every known object query against every other dataset and count any `found: true`
  answer. Run unknown-item queries too.
- **Grounded query accuracy:** correct instance + anchor + relation / all
  labelled queries. Report false-found and false-not-found separately.
- **Latency:** p50, p95, and maximum for 100 requests after one warm-up request;
  retain the existing requirement of <500 ms.
- **Mobile task checks:** time to select a dataset, time to obtain an answer,
  task completion rate, and wrong-answer rate. A small non-clinical pilot (for
  example 5--10 adult testers) may use SUS or a short 1--5 comprehension
  questionnaire. Do not recruit patients or claim clinical usability without
  ethics approval.

### Resource/reproducibility

Record from `benchmark_stats.json`: stage duration, total duration, keyframes,
point count, GPU model, peak VRAM, detections, masks, tracks, events, and RRD
size. Also record git commit, config path, target classes, model IDs, input
video hash, and Modal image/dependency versions.

For the current Demo04 run, the artifact records 701 source frames, 117
keyframes, 75,243 points, YOLOE-11l-seg + SAM2, 93 detections/masks, 10 tracks,
5 events, 1 anchor, and 383.73 seconds of recorded pipeline time. These are
performance counts, **not accuracy measurements**.

## 4. Minimal experiment matrix

Run the same held-out frames and prompts for each row:

| Run | Detector/segmentation | Prompt policy | Purpose |
|---|---|---|---|
| A | YOLO-World + SAM2 | Broad indoor classes | Existing baseline. |
| B | YOLOE-11l-seg + SAM2 | Demo04 task classes | Current proposed pipeline. |
| C | YOLOE-11l-seg without SAM2 refinement | Demo04 task classes | Measures SAM2 contribution. |
| D | Current API with dataset isolation tests | N/A | Confirms zero cross-scene leakage. |

Compare precision/recall, mask IoU, IDF1, events, relation accuracy, and total
runtime. Keep resolution, keyframe stride, confidence threshold, and hardware
fixed within a comparison. Include 3--5 qualitative success/failure examples
for each important error type: missed object, wrong class, merged instances,
wrong anchor, and stale/foreign memory.

## 5. Execution checklist

1. Freeze the config and commit hash; generate the Demo04 scene graph.
2. Produce the annotation JSON and record annotator agreement.
3. Run A--C and save one JSON result per run under `outputs/evaluation/`.
4. Run the API isolation matrix and 100-request latency benchmark.
5. Start the server with `--dataset-id demo04`, select Demo04 in the APK, and
   record the live task timings.
6. Generate tables, confusion matrix, precision/recall curves, latency plot,
   and qualitative Rerun/mobile screenshots.
7. Add a limitations section: approximate 3D scale, small sample size, prompt
   dependence, false positives, and no clinical validation.

## 6. Report/rubric mapping

- **Form 2 Criterion 3:** live Demo04 APK + Rerun demo and failure cases.
- **Form 2 Criterion 7:** automated API isolation tests, perception results,
  latency and persistence checks.
- **Form 3 Criterion 3:** scope and frozen success criteria.
- **Form 3 Criterion 7:** exact commands, configs, models, hardware, and saved
  artifacts make the run reproducible.
- **Form 3 Criterion 8:** metrics, baseline/ablation results, risks,
  limitations, and YOLOE/SAM2/Modal tool disclosure.

## 7. Object persistence diagnosis and fix

### Diagnosis

The original pipeline had two separate identity lifetimes:

1. The detector kept `_TrackState` only for `track_max_gap` keyframes. When a
   detection disappeared for longer, a new track ID was allocated.
2. R4DSG then clustered the new 3D track using a fixed 0.28 m proximity rule.
   A moving camera, noisy monocular 3D scale, or a relocated object could
   exceed that radius. SAM2 was also invoked through `SAM2ImagePredictor` on
   each keyframe, so its video memory was not being used to carry an identity
   through the gap.

Therefore a reappearance was treated as a new observation rather than evidence
for an existing object. This is an identity-association problem, not simply a
segmentation problem.

### Literature findings

- **BoT-SORT** combines motion and appearance cues, camera-motion
  compensation, and a stronger motion model for association. This directly
  supports adding appearance to the existing lightweight motion/IoU matcher:
  [Aharon et al., BoT-SORT (arXiv)](https://arxiv.org/abs/2206.14651).
- **MeMOTR (ICCV 2023)** uses long-term memory to maintain identities through
  occlusions and appearance changes:
  [ICCV open-access paper](https://openaccess.thecvf.com/content/ICCV2023/html/Gao_MeMOTR_Long-Term_Memory-Augmented_Transformer_for_Multi-Object_Tracking_ICCV2023_paper.html).
- **Visual Multi-Object Tracking with Re-Identification and Occlusion
  Handling using Labeled Random Finite Sets (2024)** uses object features and
  a long-lived track representation to reconnect targets after disappearance:
  [arXiv:2407.08872](https://arxiv.org/abs/2407.08872).
- **SAM 2 (2024)** provides streaming video memory and a video predictor that
  propagates masklets through a video. The current Aegis path uses the image
  predictor independently per keyframe, so it does not receive that benefit:
  [SAM 2 paper](https://arxiv.org/abs/2408.00714),
  [official repository](https://github.com/facebookresearch/sam2).
- For evaluation, **HOTA** and **IDF1** measure association quality from
  different perspectives; identity switches should also be reported. The
  reference implementation is [TrackEval](https://github.com/JonathonLuiten/TrackEval).

### Implemented minimal fix

A full Transformer tracker is unnecessary for this project. The pipeline now
uses a bounded hybrid memory:

- Active tracks still use motion, IoU, centre displacement, and scale.
- Every track retains a compact masked HSV appearance descriptor.
- A dormant track can be recovered for up to `reid_max_gap` keyframes using
  appearance similarity and object scale, without trusting stale screen
  coordinates after camera movement.
- R4DSG first trusts a recovered detector track ID, then combines appearance
  and 3D centre evidence before creating a new semantic instance ID.
- Descriptors are propagated from `Detection2D` through 3D lifting and scene
  graph association.
- The Rerun supervisor overlay now displays active R4DSG labels and instance
  colours, not transient detector track IDs. Duplicate detections that have no
  active R4DSG instance are omitted from that clean overlay; hand boxes are
  shown without exposing a temporary hand track ID.
- Defaults are conservative: `track_max_gap=3`, `reid_max_gap=30`, and
  `reid_appearance_threshold=0.35`. These values are configurable per video.

This is deliberately a small ReID memory, not a claim of person-level or
lifetime identity. If similar-looking objects still switch IDs, the next
upgrade should be BoT-SORT with its ReID option; do not increase the gap or
proximity threshold indefinitely because that will merge different objects.
For long continuous video, SAM 2's video predictor can be added later to
propagate masks between detector keyframes.

### Demo04 result after the fix

The task-scoped Demo04 rerun used the same 117 keyframes, YOLOE model, SAM2
model, and 93 detections/masks:

| Measure | Before persistence memory | After persistence memory |
|---|---:|---:|
| Detector tracks | 20 | 10 |
| 3D tracks in benchmark | 20 | 10 |
| Scene-graph events | 4 | 5 |
| Detection/mask count | 93 | 93 |

The track reduction is evidence of less fragmentation, not proof of accuracy.
The final evaluation must use manually annotated instance IDs and report IDF1,
HOTA, identity switches, fragmentation, and re-identification recall.

### Persistence-specific evaluation

Annotate each target object's first appearance, every visible reappearance,
visibility/occlusion intervals, and one persistent ground-truth ID. Evaluate:

- **Re-identification recall:** reappearing ground-truth objects that recover
  their original ID within one annotated frame.
- **False merge rate:** different physical objects assigned one ID.
- **ID switches:** changes of predicted ID while the ground-truth ID is stable.
- **Fragmentation:** number of predicted track segments per ground-truth object.
- **IDF1 and HOTA:** report both overall and per class.
- **Occlusion survival:** correct ID after 1, 3, 10, and 30 keyframe gaps.

Run the same annotation through these ablations:

1. Original short-term motion/IoU tracker.
2. Current bounded appearance-memory tracker.
3. Optional BoT-SORT + ReID comparison if time permits.

The persistence acceptance target is: re-identification recall >= 0.90,
false merge rate <= 0.05, IDF1 >= 0.75, and zero cross-dataset memory leakage.
Freeze these targets before inspecting the held-out Demo04 results and report
all failures qualitatively.
