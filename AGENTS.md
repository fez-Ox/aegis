# AGENTS.md

Guidance for coding agents working in this repository.

## Project

**aegis** — A Spatio-Temporal Memory System for Assistive Care.

Stores and retrieves memories that are grounded in both *when* (temporal) and *where* (spatial) events occurred, to support assistive-care applications (e.g., context-aware reminders, activity recall for users and caregivers).

**Current Status:** Successfully implemented the **R4DSG (Relative 4D Scene Graph) Spatio-Temporal Memory Architecture** with **Multi-Instance Object Permanence**, **3D-Grounded Instance Association**, **Upright Natural Coordinate Scaling ($Z$-Up)**, and **Juxtaposed 15 FPS First-Person Video & 3D Memory Visualization** in Rerun.

## Stack & Tooling

- **Language:** Python 3.12.
- Use `uv` for dependency management and running scripts (`uv add`, `uv run`); avoid ad-hoc pip installs.
- Build/test commands:
  - Lint: `uvx ruff check src poc examples`
  - Tests: `uv run pytest` (All 16 tests passing)

## Repository Layout

- `poc/` is the runnable proposal-defense workspace:
  - `poc/config/demo.yaml`: PoC runtime configuration (15 FPS ingestion, target classes, DUSt3R, YOLO-World, visualization).
  - `poc/run_pipeline.py`: Modal pipeline entrypoint (`preprocess`, `reconstruct`, `detect`, `rerun`, `all`).
  - `poc/docs/`: Design documents and implementation plans.
  - `poc/data/demo01/`: Local input video metadata (`#05_iPhone_Put_Shoes_Into_The_Cabinet`) and extracted frames.
  - `poc/outputs/`: Downloaded artifacts (`poc/outputs/demo.rrd`, `poc/outputs/demo01/objects/r4d_scene_graph.json`, etc.).
  - `poc/tests/`: Unit tests (`test_config.py`, `test_geometry.py`, `test_lifting.py`, `test_scene_graph.py`).
- `src/aegis/poc/`:
  - `core/`: Config (`config.py`), data models (`models.py`: `BoundingBox3D`, `Detection2D`), canonical volume paths (`paths.py`).
  - `geometry/`: `dust3r_runner.py` (multi-view 3D reconstruction & global alignment), `lifting.py` (2D-to-3D lifting, 3D voxel downsampling, containment states), `backproject.py`, `transforms.py`.
  - `perception/`: `detector.py` (open-vocab 2D object detection & tracking via YOLO-World).
  - `memory/`: `scene_graph.py` (R4DSG Relative 4D Scene Graph memory engine, spatial anchors, multi-instance object permanence, 3D-grounded instance association).
  - `remote/`: `modal_app.py` (Modal GPU/CPU images on L4 GPUs), `workers.py` (orchestration of DUSt3R, object lifting, R4DSG memory construction, and juxtaposed 2D/3D Rerun logging).

---

## What Has Been Completed

1. **R4DSG Relative 4D Scene Graph Memory Engine (`src/aegis/poc/memory/scene_graph.py`)**:
   - Replaced noisy raw point-cloud representations with structured 3D spatial anchors (`Storage Cabinet #1`, `Floor Entrance`) and persistent 3D object instance boxes.
   - Implemented 3D-grounded persistent instance association (`Shoes #1 [Active Pair]`, `Shoes #2 [Left Shelf]`, `Shoes #3 [Middle Shelf]`, `Shoes #4 [Right Shelf]`).
   - Implemented dynamic anchor-relative vectors ($O \rightarrow A$) with metric distance readouts.

2. **Upright Natural Coordinate Scaling ($Z$-Up)**:
   - Transformed raw miniature/tilted OpenCV camera coordinates to standard Upright World Coordinates ($+Z$ Up, $+Y$ Forward, $+X$ Right, Scale $S=5.0\times$).
   - Cabinet stands upright, and vertical lift from floor to shelf is physically accurate ($\approx 1.08\,\text{m}$).

3. **Juxtaposed 15 FPS Video & Clean 2D Overlays**:
   - Ingestion increased to 15 FPS (648 frames) for fluid video playback.
   - Synchronized 2D bounding boxes (`rr.Boxes2D`) rendered on top of the first-person video stream, color-matched to the 3D bounding boxes.
   - De-cluttered view with at most 1–3 non-overlapping bounding boxes per frame.

4. **Testing & Code Quality**:
   - 16 unit tests passing cleanly in `poc/tests/`; `ruff` lint checks 100% compliant.

## Architectural Principles & Invariants

1. **R4DSG (Relative 4D Scene Graph) Memory**:
   - Environment is represented by stable 3D Spatial Anchors (`Storage Cabinet`, `Floor Entrance`) and persistent 3D Object Instances (`Shoes #1`, `Shoes #2`, etc.).
   - Dynamic anchor-relative vectors ($O \rightarrow A$) provide real-time metric distance and relational states (`inside`, `moving_towards`, `on_floor`).
   - Do not rely on dense noisy point clouds for object-centric spatio-temporal memory.

2. **3D-Grounded Instance Association & Object Permanence**:
   - Distinguish multiple objects of the same semantic class by 3D spatial clustering and assign unique, permanent instance IDs (`Shoes #1 [Active Pair]`, `Shoes #2 [Left Shelf]`, `Shoes #3 [Middle Shelf]`, `Shoes #4 [Right Shelf]`).
   - Objects maintain continuous 3D spatial permanence (`✦ PERSISTENT MEMORY`) after leaving camera field-of-view or being occluded.

3. **Standard Upright Coordinate System ($Z$-Up)**:
   - Always transform raw camera coordinates to $+Z$ Up (Height), $+Y$ Forward (Depth), $+X$ Right with natural room scaling ($S = 5.0\times$).

4. **Juxtaposed Visualization Standards in Rerun**:
   - High ingestion framerate (15 FPS, 648 frames) for fluid video playback.
   - Pristine egocentric video on the left, synchronized 3D spatial memory on the right, without 2D overlay clutter.

---

## How to Run & Visualize

```bash
rerun poc/outputs/demo.rrd
```

