# `aegis.geometry` — 3D reconstruction and grounding

Turns sampled frames into camera poses, a gravity frame, and oriented 3D boxes.

| Module | Role |
|---|---|
| `vggt_runner.py` | Loads VGGT-Ω (`facebook/VGGT-Omega`, checkpoint override via `--vggt-model`), runs feed-forward reconstruction, writes per-keyframe compressed pointmaps + index, point cloud, poses. Honours image size/dtype; `AEGIS_VGGT_STRICT=1` prevents silent synthetic fallback in production. |
| `gravity.py` | `GravityFrame` + RANSAC floor-plane estimator (table tops rejected, camera-path cross-check) → `geometry/gravity.json`: up vector, floor offset, camera height, source, confidence, scale unit. |
| `planar.py` | Pure 2D helpers: convex hull, polygon area, point-in-polygon, Sutherland–Hodgman clipping, overlap fraction, distance to polygon, oriented rectangles. |
| `lifting.py` | Mask-grounded 2D→3D lifting; fits oriented boxes in the gravity frame (`size = length × width × height`, yaw, quaternion `rotation`, `support_up`, `up_min/up_max`), vocabulary-driven plausibility filters. |
| `backproject.py`, `transforms.py` | Depth backprojection and rotation/quaternion helpers. |

**Invariant:** VGGT-Ω world coordinates are the single source of truth for
scale and axes. Gravity is derived metadata stored *beside* the coordinates —
never rotate or rescale the points themselves.

Tests: `tests/test_geometry.py`, `test_gravity.py`, `test_planar.py`,
`test_lifting.py`.
