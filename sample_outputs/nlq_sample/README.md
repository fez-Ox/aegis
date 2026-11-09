# `nlq_sample` — real sample-video run

Artifacts from a full pipeline run of `NL Querying/sample_input_video.mp4` on
Modal CPU (2026-11-09), using `AEGIS_GPU=cpu`, keyframe stride 10, and the
unmodified public mirror `wincentIsMe/VGGT-Omega` of the VGGT-Ω checkpoint
(FAIR Noncommercial Research License).

## Run summary

- 202 sampled frames at 15 FPS; 21 VGGT keyframes
- VGGT-Ω: 17,362 world points
- 29 2D detections / 29 SAM 2 masks / 29 3D boxes; 11 tracks
- Memory: 3 anchors (`Desk #1`, `Storage Cabinet #2`, `Storage Cabinet #3`),
  1 room (`Bedroom`), 5 tracked objects, 2 events, 21 timeline frames
- Total pipeline time: 436.75 s (preprocess 10.23 s, VGGT 196.89 s,
  detect/lift 138.25 s, Rerun 91.38 s)

## Query locally

```bash
uv run python "NL Querying/smoke_test.py" --dataset nlq_sample \
    --ask "where is my laptop"
# >>> Your laptop is sitting on Desk #1 in the Bedroom.
```

## View

The Rerun recording is **not** committed because the repository ignores
`*.rrd` artifacts. After a pipeline run it is available locally at
`NL Querying/outputs/nlq_sample/viewer/demo.rrd`; the canonical copy is on the
Modal volume at `/data/nlq_sample/outputs/viewer/demo.rrd`. Download and open
it with:

```bash
MODAL_PROFILE=i230683 uv run modal volume get aegis-poc-data \
    nlq_sample/outputs/viewer/demo.rrd .
rerun demo.rrd
```
