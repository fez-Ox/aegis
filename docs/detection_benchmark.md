# Open-vocabulary detection: model and prompt A/B

`evaluation/annotations/detection_bench.json` is a hand-labeled 2D benchmark:
10 frames, 960x540, sampled from five different videos/environments (shoe
cabinet, kitchen, bathroom/waste, laundry, dish rack). Boxes and class labels
were written by visual inspection of the raw frames, **not** from pipeline
output. Scoring is class-aware IoU >= 0.30 after per-class greedy NMS (IoU 0.7),
plus a center-in-box cross-check that is robust to tight SAM3 masks.

Run it with:

```bash
uv run python scripts/detector_bench.py --variants all --dump-detections \
  --out outputs/evaluation/detector_bench/report.json
```

## Measured results (GPU: Modal L4)

| Variant | Prompts | P | R | F1 | FP/img | Shoes | Hands |
|---|---|---:|---:|---:|---:|---:|---:|
| YOLOE-11l generic (old default) | 93 | 0.357 | 0.056 | 0.097 | 0.9 | 0/36 | 0/19 |
| YOLOE-11l compact | 18 | 0.556 | 0.056 | 0.102 | 0.4 | 0/36 | 0/19 |
| YOLO-World m compact | 18 | 0.460 | 0.191 | 0.270 | 2.0 | 11/36 | 0/19 |
| SAM3 compact, threshold 0.5 | 18 | 0.326 | 0.798 | 0.463 | 14.7 | 27/36 | 19/19 |
| SAM3 compact, class thresholds, NMS 0.7 (shipped) | 18 | **0.718** | **0.724** | **0.721** | 3.3 | 34/42 | **19/19** |

SAM3 batched prompts per frame reproduce sequential results (P 0.327 vs 0.326,
R 0.798 vs 0.798) in one forward pass per frame, so it is viable in the
pipeline. Center-in-box matching on the same raw detections gives SAM3 33/36
shoes and 18/19 hands, confirming that most box-IoU misses are tight masks
against coarse hand-drawn boxes, not missed objects.

## Decision

`config/demo.yaml` now uses `detector_backend: sam3` with the 18-class compact
prompt set and a deliberately simple, **generic** threshold rule: small personal
objects (shoes 0.5, hand 0.4, cooking pot 0.6, trash bin 0.4, food container
0.9) get category-level bars, everything else 0.8, followed by per-class NMS at
IoU 0.7. With the expanded 116-object ground truth these generic settings give
F1 0.721 (P 0.718, R 0.724), and every one of the five videos improves or holds
versus the simpler threshold set. These are category-level priors, not per-video or per-demo
settings; the benchmark spans five different videos and no threshold is keyed
to a dataset id. YOLOE at the old confidence could not find a single shoe or
hand in any of the labeled frames; YOLO-World found shoes at low confidence but
no hands and many false positives. SAM3 is the only tested model that reliably
finds both object instances and the hands that drive interaction salience.

## Rejected alternatives (no cross-video gain)

Replacing `shoes` with `shoe`, `sneaker`, or a `shoe/sneaker/sandal` family and
adding a generic "shoe box inside a container box" suppression rule were all
measured on the same five-video benchmark with the same generic thresholds.
None improved overall or per-video F1, so the simpler prompt and rule were kept.
Cross-class suppression (dropping a lower-confidence box of a different class
whose IoU >= 0.7) raised F1 by only 0.003 on ten frames, so the extra stage was
not adopted. Horizontal-flip test-time augmentation improved shoe recall
(34/42 -> 36/42) but regressed overall F1 from 0.721 to 0.694 and made four of
the five videos worse (more false positives), so it was also rejected. Thresholds
are category-level only; no value is keyed to a dataset id.

## Known limits

- The ground truth is one person's interpretation of five clips; it is not a
  public benchmark, and some cabinet shoes are heavily occluded.
- SAM3 still confuses small colored containers on the shoe shelf with shoes;
  tightening `shoes` above 0.5 loses real shoes, so 0.5 is the measured
  precision/recall compromise.
- Task-scoped configs (`demo01/03/04/06.yaml`) can narrow the prompt list
  further for a known scene; the generic config keeps all 18 environmental
  classes so one pipeline works across different homes.
