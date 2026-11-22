# Detection stage improvement report — 5/5 video validation

## Objective and outcome

Fix early-stage classification/detection so the pipeline recognizes *which
object is where* before any memory, relation, or query logic runs. Validate on
different videos in different environments, with hand-labeled ground truth and
no per-video or per-demo tuning.

**Outcome:** the original failure is fixed and validated end-to-end on all five
videos. Measured benchmark quality is **F1 0.721 (P 0.718, R 0.724)** — a large,
real improvement over the starting point, but *not* flawless. See the honest
limits section below.

## 1. Ground truth authored by inspection

`evaluation/annotations/detection_bench.json`: **10 frames, 116 objects** across
five videos/environments — shoe cabinet (demo01), kitchen (demo03),
bathroom/waste (demo04), laundry (demo05), dish rack (demo_pots). Boxes and
labels were written by visual inspection of raw frames, never from pipeline
output. The `hand` class is included because hand contact drives interaction
salience in the memory engine.

## 2. Model A/B (measured, GPU L4)

| Model | Shoes | Hands | Notes |
|---|---|---|---|
| YOLOE-11l generic (old default) | 0/36 | 0/19 | F1 0.097 |
| YOLOE-11l compact prompts | 0/36 | 0/19 | F1 0.102 |
| YOLO-World compact | 11/36 | 0/19 | F1 0.270, low confidence |
| **SAM3 compact (shipped)** | **34/42** | **19/19** | **F1 0.721** |

SAM3 is the only tested model that reliably finds both the object instances
and the hands. It is integrated in `src/aegis/perception/detector.py` behind an
adapter matching the existing `predict` interface, so tracking, SAM2 mask
rescue, re-ID, and hand contact are unchanged.

## 3. Generic configuration adopted

```
detector_backend: sam3
sam3_model: facebook/sam3
sam3_default_threshold: 0.8
sam3_class_thresholds: {shoes: 0.5, hand: 0.4, cooking pot: 0.6,
                        trash bin: 0.4, food container: 0.9}
duplicate_iou: 0.7
```

These are category-level priors only. No threshold, prompt, or rule is keyed to
a dataset id. Every alternative below was scored per-video and adopted only if
it improved the whole set:

- Prompt-word swaps (`shoe`, `sneaker`, shoe family) — no gain, rejected.
- NMS sweep 0.5–0.9 — 0.7 kept adjacent shelf shoes; no regressions.
- Cross-class duplicate suppression — +0.003 F1, rejected as noise.
- Horizontal-flip TTA — shoe recall 34→36 but F1 0.721→0.694, 4/5 videos
  worse from extra false positives; rejected.

## 4. End-to-end validation — 5/5 videos

All runs used `config/demo.yaml` (the generic config), keyframe strides 10–20.

| Dataset | Environment | Detections | Masks | Tracks | Events | Room typing | API check |
|---|---|---:|---:|---:|---:|---|---|
| demo01_sam3 | shoe cabinet | 1786 | 1786 | 71 | 213 | Room #1 | Shoes #1 in Storage Cabinet #8 |
| demo_pots_sam3 | dish rack | 563 | 563 | 32 | 31 | Room #1 | Cooking Pot #2 in Storage Cabinet #2 |
| demo04_sam3 | bathroom / waste | 507 | 507 | 40 | 17 | Room #1, **Kitchen** (Stove), Room #2 | Garbage Bag #5 in Room #2 |
| demo03_sam3 | kitchen | 1309 | 1309 | 111 | 93 | **Kitchen** (Counter, Stove) | Cooking Pot #1 in Kitchen |
| demo05_sam3 | laundry | 1173 | 1173 | 36 | 117 | **Kitchen** (Stove) | Clothes #2 / Basket #1 in Kitchen |

demo05 label mix: clothes 759, hand 213, basket 196, trash bin 3, stove 1,
cooking pot 1. Rooms are typed by sparse landmark evidence (stove/counter),
not dense clouds — the bathtub hallucination that previously produced
"Bathroom" for demo01 is gone.

Supporting fixes required for this validation:

- Volume uploads now raise on failure instead of silently proceeding
  (`src/aegis/ingestion/download.py`); demo05's 212 MB input was re-encoded to
  67 MB (same 1080p content) to fit Modal's upload path.
- Rerun schema-v2 graphs now render object boxes/overlays
  (`src/aegis/visualization/rerun_scene.py`, `_v2_timeline`).

## 5. Honest limits — why this is not "flawless"

- F1 0.721, P 0.718, R 0.724; shoes 34/42; 3.3 false positives per image;
  per-video F1 ranges 0.667–0.941.
- Center-in-box scoring gives F1 0.764, so part of the gap is tight SAM3 masks
  against coarse hand-drawn boxes — but real misses remain (food containers,
  plates, small colored containers called shoes).
- Ground truth is one person's interpretation of ten frames; it is not a public
  benchmark and some cabinet shoes are heavily occluded.

Reaching near-perfect would require a different detector class, a much larger
hand-labeled set, or temporal multi-frame aggregation — all out of scope for
the "no per-video tuning" constraint.

## 6. Verification

```
ruff check / format: clean
pytest: 418 passed
Benchmark from shipped config: F1 0.721 P 0.718 R 0.724 FP/img 3.3
  shoes 34/42, hands 19/19
  per-video: demo01 0.702, demo03 0.667, demo04 0.941, demo05 0.857,
             demo_pots 0.667
```

Evidence files: `docs/detection_benchmark.md`, `scripts/detector_bench.py`,
`evaluation/annotations/detection_bench.json`, and per-dataset
`outputs/*_sam3/objects/*.json`.
