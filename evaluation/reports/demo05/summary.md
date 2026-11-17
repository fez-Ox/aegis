# Aegis held-out evaluation — demo05 (Sort Dirty Clothes)

**Dataset:** `demo05`  
**Generated:** 2026-11-10T13:32:03+00:00  
**Status:** NOT_READY

## Readiness

This run did **not** produce accuracy scores. The harness refuses to invent ground truth: scores appear only after the annotation files exist.

| Section | Missing input | What to do |
| --- | --- | --- |
| prediction | `/home/faizan/code/aegis/outputs/demo05/objects/r4d_scene_graph.json` | Run the pipeline for this dataset, then download the scene graph artifact. |
| prediction | `/home/faizan/code/aegis/outputs/demo05/objects/detected_objects_3d.json` | Run the pipeline detection stage and download detected_objects_3d.json. |
| prediction | `/home/faizan/code/aegis/outputs/demo05/geometry/poses.json` | Run the VGGT pose stage and download geometry/poses.json. |
| annotation | `/home/faizan/code/aegis/evaluation/annotations/demo05/detections.jsonl` | Annotate 2D boxes and track IDs; see evaluation/templates/detections.jsonl. |
| annotation | `/home/faizan/code/aegis/evaluation/annotations/demo05/events.jsonl` | Label event intervals; see evaluation/templates/events.jsonl. |
| annotation | `/home/faizan/code/aegis/evaluation/annotations/demo05/rooms.json` | Label rooms and per-keyframe room IDs; see evaluation/templates/rooms.json. |
| annotation | `/home/faizan/code/aegis/evaluation/annotations/demo05/queries.jsonl` | Write the held-out question bank; see evaluation/templates/queries.jsonl. |
| annotation | `/home/faizan/code/aegis/evaluation/annotations/demo05/persistence.jsonl` | Label occlusion/relocation cases; see evaluation/templates/persistence.jsonl. |

### Next steps

1. Copy the templates in `evaluation/templates/` into the annotation directory for this dataset.
2. Annotate the frozen test video. Do not tune the pipeline on it after this point.
3. Re-run the command in the readiness JSON. The report will replace this page with scored sections.
