# `aegis.visualization` — Rerun recording

`rerun_scene.py` builds `viewer/demo.rrd` from the scene graph and the separate
`r4d_timeline.json` (the per-keyframe view is not stored in the v2 graph).

Layout: horizontal blueprint with the egocentric video on the left and the
3D memory panel on the right. It logs anchors, room floor slabs/outlines/
pillars/labels, a room-coloured wearer trajectory, reference axes, up to three
non-overlapping 2D boxes per frame colour-matched to persistent instances, and
3D boxes with `✦ PERSISTENT MEMORY` / relation labels.

`rr.ViewCoordinates.RIGHT_HAND_Y_DOWN` is a **display hint only**; coordinates
are passed through raw. The point cloud is written as binary PLY.

Tests: `tests/test_rerun_visualization.py`.
