# Perception/geometry backbone — research and evaluation audit

## Research findings (web, Nov 2026)

Sources consulted:
- Ego4D (arXiv:2110.07058, CVPR 2022): 3,670 h egocentric video; benchmarks
  define task-specific metrics rather than a single detection F1.
- Mamba-VGGT (arXiv:2605.17478): VGGT suffers "catastrophic geometric
  forgetting and accumulation drift" on long sequences because global
  attention is truncated to windows; fix = persistent sliding-window memory.
- IncVGGT (OpenReview) / RetrieveVGGT (NeurIPS 2026 submission): training-free
  incremental or retrieval-bounded context for long sequences.
- COCO detection protocol: exhaustive annotation; detections over unlabeled
  regions are ignored; TIDE (ECCV 2020) decomposes errors into
  classification / localization / background / missed.
- Fisheye detection literature (FishEye8K, JVCIR 2026): distortion hurts
  standard detectors; segmentation-based annotation and distortion-aware
  handling are the recommended fixes.

Implication for Aegis: our failures are consistent with the literature — a
single feed-forward VGGT call over a long capture drifts, and a detector
trained on normal cameras degrades on circular fisheye. The fix should be
generic (windowing + alignment, prompt coverage), not tuned to one video.

## Evaluation audit — what was wrong before

| Problem | Effect | Fix |
|---|---|---|
| GT boxes drawn at 704×704, detections at 960×540, and I first assumed letterbox padding | x-coordinates shifted by 210 px → false F1 0.057 | Ingestion uses `cv2.resize(frame,(960,540))` — a **stretch**. Correct transform: sx=960/704, sy=540/704. Corrected recall 0.6 (in-prompt) |
| 6 of 11 GT objects were laptop/headphones — classes absent from the 18-class prompt set | Impossible recall, fake "query not found" | `detection_v2.evaluate_detection` reports prompt coverage (0.455) and excludes out-of-prompt GT |
| GT frames hand-labeled selectively, not exhaustively | 21 unmatched detections counted as FP → meaningless precision | v2 reports precision only when a frame declares `exhaustive`; otherwise recall + error breakdown |
| t=620 GT scored against t=624 detections | 4 s scene mismatch | exact-frame matching only |

## Corrected evaluator

`src/aegis/evaluation/detection_v2.py` reports: prompt coverage, in-prompt
recall, precision only on exhaustive frames, TIDE-style error breakdown, and
per-class TP/FN. Result on the long unique session:

```
prompt_coverage 0.455   gt_in_prompt 5/11   recall 0.6
precision null (GT not exhaustive)  unmatched 21
error_breakdown localization 1, classification 1
```

## Cross-dataset room-radius experiment

`scripts/room_radius_sweep.py` swept radius 0.3–2.5 across **seven** datasets
with hand-labeled room GT (five demos, stress EgoLife clip, 11-min session):

| radius | mean segmentation | mean region recall | mean change F1 |
|---:|---:|---:|---:|
| 0.3 | 0.747 | 1.000 | 0.301 |
| 0.5 | 0.813 | 1.000 | 0.310 |
| 0.7 | 0.840 | 0.952 | 0.429 |
| 1.5 | 0.898 | 0.833 | 0.571 |
| **2.5 (shipped)** | **0.920** | 0.833 | **0.714** |

Decision: **keep 2.5**. The long session is an outlier, not a reason to change
a threshold globally. This is the "adopt only on a wide range" rule in action.

## Implemented geometry change (under test)

`vggt.window_size` + `window_overlap` add overlapping-window reconstruction
with 3D Umeyama alignment of shared camera poses (`src/aegis/remote/workers.py`,
`_similarity_3d`, `run_vggt_segmented`). Default 0 = unchanged behaviour.
Unit-tested for similarity recovery and config validation. GPU A/B is queued.

## Detector experiment (rejected as default)

`sam3_extended` adds laptop, monitor, headphones, phone, chair, table, book,
keys, glasses to the prompt set. It raises hand-labeled GT prompt coverage on
the fisheye session from 0.455 to 1.000, but on the established five-video
benchmark it **regresses** overall F1 0.721 → 0.698 and three of five videos
(demo01 0.702→0.673, demo04 0.941→0.889, demo05 0.857→0.762). Per the
"wide range" rule it is **not adopted** as the default; the compact prompt set
stays. This also shows that prompt coverage alone is not detection accuracy.
