# `aegis.perception` — detection, segmentation, tracking

`detector.py` is the whole layer. It:

- prompts an open-vocabulary detector (`yoloe-11l-seg.pt` by default,
  `YOLOWorld` as compatibility fallback) with classes from
  `config/vocabulary.yaml`;
- runs SAM 2 (`facebook/sam2-hiera-large`) in `fallback` mode — the detector's
  own mask is used when large enough, SAM 2 refines otherwise;
- batches inference, restricts boxes to the same canonical label before
  IoU suppression, and caps detections per frame;
- tracks boxes with motion + appearance (`hsv` by default, optional DINOv2
  embeddings), recovering dormant tracks for re-identification after
  occlusion;
- classifies hands via the vocabulary `hand` role and emits hand cues used
  downstream for `carried_by_user`.

All model construction is behind `load_models(config, ...)` so Modal worker
classes can load weights once and reuse warm containers.

Tests: `tests/test_detector_postprocess.py`.
