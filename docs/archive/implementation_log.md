> **ARCHIVED — historical snapshot.** Current facts: `CONTEXT.md`; current work: `TODO.md`.

# Implementation Log — Milestone 1, Milestone 2 and §6 improvements

**Date:** 2026-11-15
**Branch:** `feat/memory-plan` (local, not pushed), branched from `develop` @ `8183015`
**Plan followed:** `context/plan.md`, work packages WP01–WP15
**Result:** 326 tests pass (baseline was 129), Ruff lint and format clean, coverage 80% (CI floor set to 75%).

Nothing has been run on Modal or with a real phone yet, so the GPU code paths are untested end to end (see "Not done or not verified").

All commits on this branch are authored by shah-paradox, and none carries a Claude co-author line.

---

## Commits

| Commit | Work package | Summary |
|---|---|---|
| `d0f7bb4` | — | Add the implementation plan (`context/plan.md`) |
| `b4c62d6` | WP01 | `config/vocabulary.yaml` as the single label ontology |
| `340df9a` | WP02 | Per-session gravity frame; no silent synthetic VGGT |
| `16cea65` | WP03 | Oriented boxes fitted in the gravity frame |
| `98f7fc3` | WP04 | Relation classifier: on / under / inside / above / next to / on the floor |
| `32ae026` | WP05 | Scene graph rebuilt on general rules with state runs (graph schema v2) |
| `e2326f0` | WP06 | API: no invented answers, room-rename fix, input validation |
| `0d72d09` | WP07 | Persistent per-home SQLite store with session ingest |
| `62b7f14` | WP08 | Caregiver room names persist per home; `home_map.json` mirror |
| `9aed634`, `d01ddc6` | WP09 | Room-stay activities with plain summaries |
| `1a27bc7` | WP10 | One object-only evidence crop per state run |
| `0b1d14a` | WP11 | Three-day detail, then verified text summaries; weekly/monthly roll-up |
| `c5dd0ef` | WP12 | Live captures as JPEG segments; warm GPU workers |
| `a71c7e6` | WP13 | Class-aware suppression, batched inference, SAM 2 fallback, optional DINOv2 re-ID |
| `17f73ee` | WP14 | App never fabricates answers offline; capture pause from the app |
| `6c6fa01` | WP14 | Dead DROID/depth code removed; Rerun recorder split out; coverage in CI |
| `2888245` | WP15 | Scripts and scoring for the acceptance measurements |
| `ca3cdaf` | — | `context/todo.md` ticked with the test behind each item |

---

## What changed

### Labels (WP01)
- `config/vocabulary.yaml` decides what the detector is prompted for, and whether each label is an object, furniture (anchor), a room landmark or a hand.
- Synonyms, plural grammar, importance and furniture affordances (container, support surface, open underneath) also come from this file.
- The config embeds the vocabulary so Modal workers receive it.
- `demo01` keeps its task-scoped prompts in `config/demo01.yaml`.

### Shoes above or below the bed (WP02–WP04)
- The VGGT stage fits the floor plane (RANSAC, table tops rejected) and writes `outputs/geometry/gravity.json`: up vector, floor height, camera height, confidence. Coordinates are never rotated.
- 3D boxes use the session's up direction for height. Furniture boxes also record the height of their top surface.
- The classifier decides the relation from footprint overlap and vertical order, with tolerances relative to object size. It does not claim under, above or on the floor when the gravity estimate is unreliable.
- Tests cover shoes on, under and beside a bed with the camera pitched 40°.

### Memory engine (WP05)
- Removed all demo-specific rules: shoe IDs from X thresholds, frame-range gates 280–480, the fabricated `Storage Cabinet #1`, invented grasp offsets and placeholder event anchors.
- The same identity rules now apply to every object class.
- States are debounced. A change needs two consecutive observations, or one confident and certain final one.
- Each object needs two observations before it gets a memory.
- `r4d_scene_graph.json` (schema 2) holds runs and last-known states, so its size no longer grows with video length. The per-keyframe view moves to `r4d_timeline.json`, which only the Rerun recorder reads.
- Wall-clock time comes from the live `capture_timestamp`, or from `--recorded-at` for batch videos.

### API and answers (WP06)
- Room rename matches by room id; it used to relabel every neutral room.
- `dataset_id` is validated (400 on path tricks); labels in the SVG card are escaped.
- `confidence` is the stored value or null, never the constant 0.96. `last_seen_time_ago` is null instead of "Recorded today".
- Queries resolve through the vocabulary: no substring matches, and "cup" no longer finds a bottle.
- Answers are at most two sentences, say "last seen" when the object is out of view, and flag uncertain relations.
- The graph repository reloads a file that changed on disk and does not cache a corrupt one.
- Simulator routes respond only with `AEGIS_ENABLE_SIMULATOR=1` (`run_server.py --enable-simulator`).

### Long-term memory (WP07–WP11)
- **Home store:** one SQLite file per home at `<store_root>/<home_id>/memory.db`.
  - Each processed dataset is ingested as a session.
  - Rooms, furniture and objects keep the same IDs across sessions.
  - An object seen in the same place again extends its existing row; a move between sessions becomes a `moved_while_unobserved` event.
  - Re-ingesting the same graph is a no-op. A changed graph replaces only its own session. Out-of-order sessions are rejected.
- **Cross-session matching:** symbolic, because every session has its own origin.
  - Rooms: by landmark/furniture signature, plus continuity between back-to-back segments.
  - Furniture: by type within a room, then a 2D alignment from unambiguous matches, then by what rests on it.
  - Objects: by last-known place, then class, then appearance.
- **Room names:** stored in the room table and mirrored to `home_map.json` after every change. A caregiver rename is never overwritten. Unknown room → 404, duplicate name → 409.
- **Activities:** one room stay plus the events in it, each with a deterministic summary line. `GET /api/v1/activities` lists them.
- **Evidence crops:** a 320 px, object-only crop per run. A later, larger crop replaces it. `GET /api/v1/crops/{id}?home_id=` serves it; `crop_url` is null when there is none.
- **Retention:**
  - Full detail for 3 days (7 for high-importance items).
  - After that, template summaries per object and per activity, checked against the source rows before anything is deleted. A day that fails the check keeps its rows and `/health` reports `compaction_ok: false`.
  - Each object's last-known state is never compacted.
  - Day lines roll into week lines after 30 days, and week lines into month lines after a year.
- **CLI:** `aegis-memory ingest|show|size|compact`. `run_pipeline.py` ingests the downloaded graph unless `--no-ingest`.

### Live path (WP12)
- Promoted frames stay JPEG, copied byte for byte when no resize is needed.
- Long captures are processed as segments (`live.segment_frames`, default 120). Each segment runs the full chain: preprocess, VGGT, perception, download, ingest.
- Progress is saved in `captures/<session>/pipeline_state.json`. `--follow` keeps processing while the capture runs.
- `config/live.yaml` reconstructs and detects every live keyframe.
- `vggt.max_keyframes` is enforced. Pointmaps are written one file per keyframe, read one at a time and deleted after detection.
- VGGT honours `image_size` (512) and `dtype`.
- The GPU stages are Modal classes that keep models loaded between segments and reload the data volume before each call.

### Perception (WP13)
- A box is suppressed only by a more confident box of the same label; the per-frame cap is 30 (was 6).
- Frames are decoded once and predicted in batches. Masks are requested at the original frame size.
- `sam2.mode: fallback` runs SAM 2 only where the detector's own mask is missing or too small.
- Optional DINOv2 embeddings for re-identifying objects after occlusion (`perception.reid_backend: dino`). The default stays `hsv` until measured.

### App and cleanup (WP14)
- **App:** no canned answers, datasets or search history. An unreachable server shows "Can't reach Aegis memory…" and is not added to the search history.
  - One 5 s timeout for every request.
  - The simulator button appears only when the server enables it.
  - A Recording/Paused switch is backed by `/api/v1/capture/status|pause|resume`.
  - Widget tests use a mock HTTP client.
- **Removed dead code:** depth/pose/geometry/DroidCalib config, the broken `dust3r_model_path`, and the `dust3r` aliases.
- **Rerun recorder:** moved to `aegis/visualization/rerun_scene.py`; it now uses the gravity frame. The point cloud is written as binary PLY.
- **CI:** `pytest-cov` with a 75% floor. `AGENTS.md` paths updated.

### Measurement tooling (WP15)
- Every protocol has a script that writes `outputs/evaluation/<name>.json` with the commit, a dirty flag, the config hash, model IDs and hardware:

  | Script | Measures |
  |---|---|
  | `summarise_live_session.py` | One-hour soak, disconnect recovery, backlog |
  | `evaluate_keyframes.py` | Keyframe selection |
  | `evaluate_placements.py` | Object placement accuracy |
  | `evaluate_rooms.py` | Room segmentation and transitions |
  | `evaluate_activity_order.py` | Activity order and timing |
  | `measure_vggt_window.py` | Largest reconstruction window on the L4 |
  | `compare_masks.py` | YOLOE vs SAM 2 masks |
  | `evaluate_hand_contact.py` | Pick-up and put-down events |
  | `measure_store_growth.py` | Store size over simulated days |

- The metric arithmetic is in `aegis.evaluation` and unit-tested.
- `aegis-ingest --inject-stall-at/--inject-stall-for` supports the backlog protocol; `session.json` now records `max_backlog_seconds`.

---

## Bugs found along the way

- `--stage live` only ran preprocessing, so live captures never produced a memory.
- Detector masks came back at the padded inference size and were stretched onto the frame, so they were slightly misaligned.
- Back-to-back sessions could merge two different rooms. The continuity rule overrode room signatures; it now applies only to type-compatible rooms the signature didn't place.
- A newer evidence crop could delete itself when replacing an older one.

## Behaviour changes to know about

- Beds, sofas and fridges are now furniture that objects can be on or under. Doors, windows and stairs remain room evidence only.
- `r4d_scene_graph.json` is schema 2. The API still reads schema 1 (the test fixtures).
- The demo simulator is off unless the server is started with `run_server.py --enable-simulator`.
- `--stage live` runs the full chain per segment. `--stage all` with `--live-session` still processes the whole capture as one dataset.
- `demo.yaml` derives its prompts from the vocabulary; use `config/demo01.yaml` for the original shoe-scene prompts.

---

## Not done or not verified

- **Modal/GPU code:** the VGGT changes, batched detection and the warm model containers have only been checked for syntax and with fakes. Re-run demo01, demo04 and Demo06-Self on Modal to check the new rules against the videos.
- **Flutter:** there is no Flutter SDK on the development machine. The app changes are checked only by CI's `flutter analyze` and `flutter test`.
- **Physical measurements:** the soak (AC-01), disconnects (AC-03), keyframes (AC-02), backlog (AC-29), placements (AC-04), rooms (AC-22), activity order (AC-05) and reconstruction window size all need the phone, recordings and ground-truth files.
- **Storage growth:** the figure comes from a **synthetic** stream (100 objects, 1,000 changes/day, 144 sessions/day, 14 days). Detail rows stay flat at about 12.5k from day 3; `memory.db` reaches 6.7 MB at day 14 and grows about 0.2 MB/day from summaries and session rows before roll-up. Repeat with real recordings.
- **Deferred:** running detection in parallel with VGGT (A10) until stage times are measured. Cross-session use of DINOv2 embeddings (M2) until measured.

## Open decisions

- **Evidence crops vs the 24-hour raw-frame rule (decision #9):** crops are kept by default (`memory.evidence.enabled`). This needs supervisor confirmation.
- **Commit `8183015`:** already pushed to `origin/develop` and still carries a Claude co-author line. Removing it means rewriting published history; waiting for your decision.
