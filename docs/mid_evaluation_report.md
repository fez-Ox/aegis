# Mid-Evaluation stress report — long unique session

## The input

`mid_eval_long.mp4`: 668.6 s (11.1 min), 704×704 circular-fisheye egocentric
video at 5 FPS, built by concatenating three previously unused A1_JAKE DAY2
clips (d2_s00, d2_s01, d2_s02). 3,343 extracted frames. Hand-labelled GT was
authored from viewed contact sheets and full-resolution frames
(`evaluation/annotations/mid_eval_long_gt.json`,
`evaluation/annotations/mid_eval_detections.json`).

Run: `config/demo.yaml`, keyframe stride 30 (112 keyframes), full `all` stage
on Modal GPU.

## Per-segment numbers

| Segment | Measurement |
|---|---|
| Preprocess | 174 s; 3,343 frames; 19.2 FPS ingest |
| VGGT | 201 s; 112 poses; trajectory span **1.78 m**; median step 0.072 m, max 0.815 m |
| Gravity | source `floor_plane`, confidence **0.371**, floor inlier ratio **0.111**, camera height **0.148 m** — weak/unreliable |
| Detect + lift | 625 s; **1,123** 2D detections, 1,122 3D boxes, **172** tracks, 39 state runs, 5 events |
| Detection confidence | mean 0.772; p10 0.539, p50 0.828, p90 0.914 |
| Points per 3D box | mean 2,089; p10 103, p50 638; mean box volume 0.000194 m³ |
| Spatial states | in_hand 569, hand 495, static_structure 39, on_surface only **19** |
| Memory | 1 room ("Kitchen"), 5 anchors, 34 instances (only **2** with an anchor), 1 room visit, 4 pickups + 1 placement |
| Rerun | **1,926 s** (168.6 MB RRD) — the dominant cost of the run |
| Total pipeline | **2,928 s** (48.8 min compute; ~82 min wall-clock with image build + upload + download) |

Label mix: hand 495, clothes 268, shoes 82, bowl 58, plate 52, cooking pot 47,
trash bin 41, bottle 39, kitchen counter 16, sink 12, storage cabinet 10.

## Ground-truth evaluation

Room and query GT were authored by hand from the frames; the three true zones
are Living Room (0–195 s), Kitchen (195–334 s), Living Room (334–555 s),
Bedroom (555–668 s).

| Metric | Result |
|---|---|
| Room segmentation accuracy | 0.625 |
| Region recall | **1/3** (0.333) — only one predicted room |
| Room-change F1 | **0** (0 predicted vs 3 true transitions) |
| Query correctness | **0.4** (2/5): bowl-in-kitchen ✓, toilet-absent ✓ |
| Query failures | bottle-on-table ✗; laptop not found ✗ (laptop is NOT in the 18-class prompt set); shoes false positive ✗ |
| Evidence coverage on answered queries | **3/3 = 100%** (P1.4 holds on new data) |

Detection GT on two frames (after mapping 704×704 → 960×540 letterboxed):
**F1 0.057**, precision 0.042, recall 0.091, 11.5 FP/image. 6 of the 11 GT
objects (laptop ×5, headphones ×1) are classes the detector was never asked
to find. Excluding them, the pipeline found 1 of 5 in-vocabulary objects (the
cooking pot).

## What this tells us about the pipeline today

1. **It survives long input**: 11 minutes, 3,343 frames, no crash, complete
   artifacts and 100% evidence coverage on answered queries.
2. **Geometry quality collapses on this data**: 1.78 m trajectory span across
   11 minutes, gravity confidence 0.37 with 11% floor inliers. The three
   concatenated clips have discontinuous camera origins, which the single
   feed-forward reconstruction cannot reconcile.
3. **Consequently the spatial backbone has almost nothing to ground on**:
   only 19 `on_surface` states out of 1,122 boxes; only 2 of 34 instances have
   an anchor; no room transitions detected. This explains the room and query
   numbers — it is a geometry/coverage failure, not a ranking failure.
4. **Detection does not generalise to this camera**: circular fisheye + 5 FPS +
   letterboxed preprocessing yields F1 0.057 on hand-labelled frames, far
   below the 0.72 measured on the five demo videos. Prompt coverage also
   matters: laptop/headphones objects are invisible to the detector.

## Honest conclusion for Mid-Evaluation

The improved query/answer layer (confidence, abstention, temporal, activity,
evidence) is robust and transfers to new data. The **front half** of the
pipeline — VGGT geometry and open-vocabulary detection on a new camera — is
the weak point. Fixing it needs either segment-wise reconstruction for long
captures, camera-specific normalisation, or a broader prompt set; none of
these should be tuned to this one video.
