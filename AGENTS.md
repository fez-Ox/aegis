# AGENTS.md

Guidance for coding agents working in this repository.

## Project

**aegis** — A Spatio-Temporal Memory System for Assistive Care.

Stores and retrieves memories that are grounded in both *when* (temporal) and *where* (spatial) events occurred, to support assistive-care applications (e.g., context-aware reminders, activity recall for users and caregivers).

**Current Status:** Successfully implemented the **R4DSG (Relative 4D Scene Graph) Spatio-Temporal Memory Architecture** with **Room-Level Spatial Memory (Rooms → Anchors → Objects)**, **Multi-Instance Object Permanence**, **3D-Grounded Instance Association**, raw **VGGT-Ω World Coordinates** (no manual scale/axis transforms), and **Juxtaposed 15 FPS First-Person Video & 3D Memory Visualization** in Rerun.

## Stack & Tooling

- **Language:** Python 3.12.
- Use `uv` for dependency management and running scripts (`uv add`, `uv run`); avoid ad-hoc pip installs.
- Build/test commands:
  - Lint: `uvx ruff check src tests run_pipeline.py run_server.py && uvx ruff format --check src tests run_pipeline.py run_server.py`
  - Tests: `uv run pytest`

## Repository Layout

- `config/demo.yaml`: Runtime configuration (15 FPS ingestion, target classes, VGGT-Ω, YOLO-World + SAM 2, visualization).
- `run_pipeline.py`: Modal pipeline entrypoint (`preprocess`, `reconstruct`, `detect`, `rerun`, `all`).
- `docs/`: Design documents and implementation plans.
- `data/demo01/`: Local input video metadata (`#05_iPhone_Put_Shoes_Into_The_Cabinet`) and extracted frames.
- `outputs/`: Downloaded artifacts (`outputs/demo.rrd`, `outputs/demo01/objects/r4d_scene_graph.json`, etc.).
- `tests/`: Automated unit tests (`test_config.py`, `test_geometry.py`, `test_lifting.py`, `test_scene_graph.py`).
- `src/aegis/`:
  - `core/`: Config (`config.py`, incl. `memory.rooms`), data models (`models.py`: `BoundingBox3D` with rotation/yaw, `Detection2D` with masks), canonical volume paths (`paths.py`).
  - `geometry/`: `vggt_runner.py` (VGGT-Ω feed-forward 3D reconstruction), `lifting.py` (SAM 2 mask-grounded 2D-to-3D lifting, Z-aligned OBB fitting, containment states), `backproject.py`, `transforms.py`.
  - `perception/`: `detector.py` (open-vocab 2D object detection via YOLO-World + SAM 2 instance segmentation).
  - `memory/`: `scene_graph.py` (R4DSG Relative 4D Scene Graph memory engine, spatial anchors, multi-instance object permanence, 3D-grounded instance association), `rooms.py` (room-level region estimation: trajectory clustering + landmark typing), `reasoning.py` (query reasoning incl. room clauses and room filters), `home_registry.py` (per-home room calibration registry, `home_map.json`).
  - `remote/`: `modal_app.py` (Modal GPU/CPU images on L4 GPUs with secret injection), `workers.py` (orchestration of VGGT-Ω, SAM 2 mask lifting, R4DSG memory construction, room-aware Rerun logging in raw VGGT-Ω coordinates), `api.py` (FastAPI gateway incl. `GET /api/v1/rooms`, `POST /api/v1/rooms/rename`).
  - `ingestion/`: Video normalization and frame extraction.
  - `visualization/`: Visualization utilities.

---

## What Has Been Completed

1. **Room-Level Spatial Memory (`src/aegis/memory/rooms.py`, integrated in `scene_graph.py`)**:
   - 3-level hierarchy: **Rooms → Spatial Anchors → Object Instances** (`RoomRegion`, persisted in `r4d_scene_graph.json`).
   - Rooms estimated Hydra-style by clustering the camera wearer's trajectory on the floor plane (online spatial clustering + revisit merging), typed HOV-SG-style by room-defining landmarks (`door`, `sofa`, `bed`, `television`, `toilet`, `kitchen counter`, `dining table`, `stairs`) detected by the open-vocab detector; landmarks are room evidence only and never become object memories.
   - Objects are room-grounded: placed objects inherit their anchor's room, carried objects inherit the wearer's per-frame room; `_insert_room_clause` produces answers like "…inside Storage Cabinet #1 in Room #1."
   - `room_change` events for the camera wearer; queries support room constraints ("keys in the kitchen").
   - Caregiver room naming persists via `POST /api/v1/rooms/rename`; `home_registry.py` (`home_map.json` per `home_id`) matches sessions onto stable room identities.
   - Room-level evaluation protocol documented in `docs/evaluation_plan.md` (Hydra region precision/recall).

2. **R4DSG Relative 4D Scene Graph Memory Engine (`src/aegis/poc/memory/scene_graph.py`)**:
   - Structured 3D spatial anchors (`Storage Cabinet #1`, `Floor Entrance`) and persistent 3D object instance boxes.
   - 3D-grounded persistent instance association (`Shoes #1 [Active Pair]`, `Shoes #2 [Left Shelf]`, `Shoes #3 [Middle Shelf]`, `Shoes #4 [Right Shelf]`).
   - Dynamic anchor-relative vectors ($O \rightarrow A$) with metric distance readouts.

3. **Raw VGGT-Ω World Coordinates (no manual transforms)**:
   - The ×5.0 Z-up scale/axis permutation was removed; VGGT-Ω output is the single source of truth for scale and orientation (fixes the altitude-drift artifact). Rerun uses `ViewCoordinates.RIGHT_HAND_Y_DOWN` (OpenCV-style: +X right, +Y down, +Z forward) as a display hint only.

4. **Juxtaposed 15 FPS Video & Clean 2D Overlays**:
   - Ingestion at 15 FPS (648 frames); synchronized 2D bounding boxes (`rr.Boxes2D`) on the first-person stream, color-matched to 3D boxes; ≤ 3 non-overlapping boxes per frame.
   - 3D view: anchors, room footprints with per-room palette and room-colored trajectory.

5. **Apple HIG Design Architecture & Patient Search Audit (`apps/mobile/`)**:
   - Inset grouped cards, SF typography hierarchy, 44×44 pt touch targets, iOS segmented control with haptics, patient recent search history, Cupertino modal sheets/alerts.

6. **Testing & Code Quality**:
   - All unit tests passing (`tests/test_config.py`, `test_geometry.py`, `test_lifting.py`, `test_scene_graph.py`, `test_rooms.py`, `test_home_registry.py`, `test_reasoning.py`, `test_api.py`, `test_rerun_visualization.py`); `ruff` lint and format 100% compliant.

---

## Architectural Principles & Invariants

1. **R4DSG (Relative 4D Scene Graph) Memory**:
   - 3-level hierarchy: stable **Rooms** (trajectory zones) → stable 3D **Spatial Anchors** (`Storage Cabinet`, `Desk`) → persistent **Object Instances** (`Shoes #1`, `Keys #1`).
   - Dynamic anchor-relative vectors ($O \rightarrow A$) provide real-time metric distance and relational states (`inside`, `moving_towards`, `on_floor`).
   - Do not rely on dense noisy point clouds for object-centric spatio-temporal memory.

2. **Room Grounding**:
   - Rooms come from trajectory clustering + sparse landmark evidence, never from dense clouds.
   - Room-defining landmarks are architectural context only — never stored as personal-object memories.
   - Room naming is caregiver-calibrated (`home_map.json`); neutral labels are `Room #N`.

3. **3D-Grounded Instance Association & Object Permanence**:
   - Distinguish multiple objects of the same semantic class by 3D spatial clustering and assign unique, permanent instance IDs.
   - Objects maintain continuous 3D spatial permanence (`✦ PERSISTENT MEMORY`) after leaving camera field-of-view or being occluded, including while carried across rooms.

4. **Raw VGGT-Ω Coordinates**:
   - Never reintroduce manual scale or axis permutations; VGGT-Ω is the single source of truth for coordinates and scale.

5. **Juxtaposed Visualization Standards in Rerun**:
   - High ingestion framerate (15 FPS, 648 frames) for fluid video playback.
   - Pristine egocentric video on the left, synchronized 3D spatial memory on the right, without 2D overlay clutter.

---

## How to Run & Visualize

```bash
rerun outputs/demo.rrd
```

