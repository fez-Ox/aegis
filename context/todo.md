# Aegis — Master TODO (done + remaining, by milestone)

**Sources:** `fyp_report/main.pdf` (FYP-1 mid-report: scope, FR/NFR, AC-01…AC-31, SC1–SC9) and `context/specification.md`.
**Baseline verified:** 2026-11-12 on `develop` @ `940a09e` — `uv run pytest` → **129 passed**; `ruff check` and `ruff format --check` clean.
**Milestones (proposal):** M1 Ingestion · M2 Graph & History · M3 Voice Agent · M4 Portal & Testing.
**Companion document:** `context/answer.md` (retention/memory budget, elevation fix, vocabulary).

This is the only todo list. `fyp_report/todo.md` was merged into §5 and deleted.

> Rules: do not tick an item without a test, a measured result, or a recorded artifact.
> Keep all existing tests passing and Ruff clean. Never present an unmeasured result as measured.

Legend: `[x]` done and evidenced · `[~]` partly done / simulated only · `[ ]` not started · **(H/M/L)** = report priority.

---

## 0. Status snapshot

| Req | What the report demands | Status today | Evidence / gap |
|---|---|---|---|
| FR1 | Live capture ≥ 1 fps, timestamps, pause/resume | Done on laptop side | `ingestion/live_*.py`; no pause control in the app |
| FR2 | Keyframes by criterion, routing, gaps, buffering | Done (simulated verification) | `keyframe.py`, `buffer.py`, `live_handoff.py`; physical soak unmeasured |
| FR3.1–3.2 | Persistent identities, anchor-relative location + confidence | Partial | Works on demos, but identity logic is demo-hardcoded (§6 C1); no confidence stored per observation |
| FR3.3 | Activity events | Partial | Object state transitions + `room_change` only; no activity grouping |
| FR3.4 | Room estimation | Done, unmeasured | `memory/rooms.py`, 9 tests; AC-22 metrics not measured |
| FR3.5 | Memory survives restart | Partial | JSON on disk; no restart-equivalence test (AC-06) |
| FR3.6–3.7 | Per-home room identity, rename persisted in registry | **Not wired** | `home_registry.py` is used only by its own tests; rename edits the graph only. The report (Table 3.8, UC-13) says the registry is written — it is not |
| FR4 | 3-day detail + summaries, sub-linear growth | **Missing** | No code, no tests |
| FR5.1, 5.6, 5.7 | "Where" queries, room filter, room clause | Done | `reasoning.py`, `api.py`, 27 tests |
| FR5.2–5.3 | "When / what happened", relative time | **Missing** | Timestamps are session-relative seconds |
| FR5.4–5.5 | Evidence on every answer, abstention | **Missing** | `confidence=0.96` constant; crop is a generated SVG |
| FR6 | Speech + text | Text only | No mic, no ASR dependency |
| FR7 | Query UI, evidence, text size, timeline | Partial | Flutter patient/caregiver views; no evidence image, no text-size control |
| FR8 | Auth, grants, audit, summaries, room UI | **Missing** | No auth anywhere; wildcard CORS |
| NFR-R | 1 h soak, crash recovery, 6 h freshness | R1/R2 simulated; R3 missing | `test_live_ingestion.py` |
| NFR-P | p95 ≤ 5 s, backlog ≤ 30 s, storage growth | Unmeasured | Only a fixture `< 0.5 s` assertion |
| NFR-S | TLS/AES-256, scope, audit, 24 h purge, deletion | **Missing** | — |
| NFR-U | ≤ 2 sentences, 3 text sizes, WCAG AA, 60 s task | Unmeasured | Answers are often 2–3 sentences |

---

## Milestone 1 — Ingestion (M-A · FR1, FR2 · lead Shahmeer)

**Goal:** a real phone → pipeline → memory path that survives a one-hour session.
**Exit evidence:** AC-01, AC-02, AC-03, AC-21, AC-27, AC-29; NFR-R1, NFR-R2, NFR-P2.

### 1.1 Batch ingestion — done
- [x] Video → sampled PNG frames + `metadata.json` + intrinsics on a Modal CPU worker (`ingestion/video.py`, `remote/workers.py::run_preprocess`).
- [x] Dataset download/ingest presets and dataset-ID safety (`ingestion/download.py`, `core/paths.py`; `test_video_ingestion.py`, `test_config.py`).

### 1.2 Live capture — done
- [x] MJPEG sampler at 2 FPS, per-frame timestamps, unique sessions, JPEG + `index.jsonl` + manifest, credential redaction (FR1.1, FR1.2).
- [x] Pause/resume via `SIGUSR1`/`SIGUSR2` or `--pause-file`; pauses recorded as gaps (FR1.3, AC-21 at CLI level).
- [x] Gap markers for disconnects, pauses and storage stalls (FR2.3).
- [x] Criterion-based keyframes: sharpness, brightness, visual change, duplicate suppression, forced interval (FR2.1) — `ingestion/keyframe.py`, `config/demo.yaml: live.keyframe`.
- [x] Bounded frame buffer with backlog metric (FR2.4) — `ingestion/buffer.py`.
- [x] Crash recovery: `session_state.json` checkpoints + `--resume` (NFR-R2, AC-27).

### 1.3 Live → memory handoff — done
- [x] Promotion of a live session into a dataset (`ingestion/live_handoff.py`, `aegis-ingest --promote-dataset-id`).
- [x] `live` stage in `run_pipeline.py` chaining preprocess → VGGT → perception → Rerun (FR2.2).
- [x] Frozen artifact contracts and schema versions (`docs/artifact_contracts.md`, `ingestion/contracts.py`, `test_live_contracts.py`).
- [x] One authoritative timestamp (`capture_timestamp`, `timebase: "capture"`).
- [x] Runbook in `docs/live_capture.md`.

### 1.4 Remaining for M1
- [~] **NFR-R1 / AC-01:** one-hour session is proven only with a simulated clock (`test_simulated_one_hour_session`). Run a physical phone soak and record frame count, gaps, disk use and device model.
- [~] **AC-03:** 10 s disconnect → resume ≤ 15 s is simulated only. Repeat on the real phone stream.
- [~] **AC-02:** keyframe tests are unit-level. Record a scripted clip with 5 known scene changes and report how many are selected (target ≥ 80%).
- [ ] **AC-29 / NFR-P2 (H/M):** measure backlog over a real 10-minute run with the memory engine paused for 10 s.
- [ ] **FR1.3 in the app (M):** pause/resume control in Flutter plus a server-side session-control endpoint (belongs with the M4 capture/delete screen).
- [ ] Stop re-encoding promoted frames to PNG (§6 C12) — it is the largest avoidable disk cost in the live path.
- [ ] Micro-batch the live path (promote and process every N minutes) instead of one whole-session run (§6 A5, A10); required before a one-hour session can pass through VGGT at all.
- [ ] Carry wall-clock capture time into the scene graph (§6 A8); M3 temporal queries depend on it.

---

## Milestone 2 — Graph & History (M-B · FR3, FR4 · lead Faizan)

**Goal:** three days of detailed memory, compacted older history, stable per-home rooms, real activity history.
**Exit evidence:** AC-04, AC-05, AC-06, AC-07, AC-08, AC-22, AC-23, AC-31; SC3, SC9; NFR-P3.

### 2.1 Geometry, perception, object memory — done
- [x] VGGT-Ω pointmaps, confidence maps, poses, fused point cloud (`geometry/vggt_runner.py`).
- [x] Open-vocabulary detection (YOLOE-seg / YOLO-World) + SAM 2 masks + keyframe tracker with appearance re-ID (`perception/detector.py`).
- [x] Mask-grounded 2D→3D lifting, oriented boxes, containment and motion states (`geometry/lifting.py`, 9 tests).
- [x] R4DSG: spatial anchors, persistent instances, anchor-relative vectors, occlusion permanence, in-hand propagation (`memory/scene_graph.py`, 10 tests).
- [x] Object transition events: pickup, placement, anchor change, state change.
- [x] Raw VGGT-Ω coordinates; the ×5 / Z-up transform is removed.
- [x] Rerun recording: video + 3D memory, rooms, trajectory (`workers.py::run_rerun`).

### 2.2 Rooms — done as a module, unmeasured
- [x] Trajectory clustering + revisit merging, landmark typing, neutral `Room #N`, footprints (`memory/rooms.py`, FR3.4).
- [x] Room binding for anchors/objects; carried objects follow the wearer; `room_change` events.
- [x] `HomeRoomRegistry` module with landmark/proximity matching, blending, corrupt-file fallback (`memory/home_registry.py`, 5 tests).
- [x] Room evaluation protocol written (`docs/evaluation_plan.md`).

### 2.3 Per-home room identity — FR3.6 / FR3.7 (H) — not wired
- [ ] Add `home_id` to config / dataset metadata, distinct from `dataset_id`.
- [ ] Load the registry before building the graph and apply matched labels (`match_room_into_registry` / `calibrate_from_rooms` from `run_detect_and_lift`).
- [ ] Make `POST /api/v1/rooms/rename` write `home_map.json` (today it edits only `r4d_scene_graph.json`).
- [ ] Fix the rename bug that relabels the events of *every* neutral room (§6 C3).
- [ ] Decide how cross-session matching works when each session has its own coordinate origin (§6 A3): landmark-type matching is valid today, proximity matching is not.
- [ ] Tests: rename → restart → rebuild → label survives (AC-31); unknown room ID rejected; corrupt registry falls back at the API level.

### 2.4 Compaction and tiered retention — FR4 (H) — missing entirely
Design and size budget are in `context/answer.md` §1.
- [ ] Decide persistence technology (decision #6) and summary format/trigger (decision #7).
- [ ] Replace the per-keyframe timeline with change-only state runs (§6 A2) — prerequisite for any sub-linear growth claim.
- [ ] Hot tier: full detail for a configurable window, default 3 days (FR4.1).
- [ ] Background compaction job on a time/size trigger, never on the query path.
- [ ] Summaries retain object identity, last known location, room identity, event type (FR4.2); keep each object's last-known state forever.
- [ ] Room IDs/labels survive compaction; add a survival check.
- [ ] Mark summary-derived answers as `summarised` (FR4.3, AC-23).
- [ ] Flag a compaction failure and keep source detail when context cannot be preserved (UC-12 A1).
- [ ] Record the storage growth curve after retention (FR4.4, NFR-P3, AC-07).
- [ ] Before/after query accuracy on the same query set (AC-08, SC3).
- [ ] Tests: retention boundary, summary content, room-label survival, summarised flag, growth bound, failure flag.

### 2.5 Activity history — FR3.3 (H) — partial
- [x] Per-object transition events and wearer `room_change` events.
- [ ] Define an "activity event" (room visit + the object interactions inside it).
- [ ] Group transitions into timestamped activities; expose via `/api/v1/timeline` with session/date filters.
- [ ] Activity-level summaries that feed "what did I do?" (M3) and the daily summary (M4).
- [ ] Ground-truth order/time test on a scripted sequence (AC-05, ≥ 70%).

### 2.6 Identity and spatial correctness (H)
- [ ] Remove demo-specific identity/state rules from `scene_graph.py` (§6 C1) and re-verify the demos with general rules.
- [ ] Store detection confidence on every observation (FR3.2 requires it; `ObjectMemoryEntry` has none).
- [ ] Gravity-aligned height and vertical relations (`on`, `under`, `above`, `on_floor`) — `context/answer.md` §2.
- [ ] Fix the oriented-box vertical axis (§6 C2).
- [ ] AC-04: 5 known objects at known anchors, ≥ 70% correct, ≤ 20% duplicate identities — recorded run.

### 2.7 Restart persistence and graph lifecycle — FR3.5 / AC-06 (H)
- [ ] Restart-equivalence test: memory identical before and after an application restart.
- [ ] Explicit cache invalidation when a new graph is written while the API is alive.
- [ ] API-level test for a corrupt `r4d_scene_graph.json`.
- [ ] Decide and document append-only versus rebuilt history (§6 A1 recommends append-only).

### 2.8 Room evaluation — AC-22 / SC9 (H) — unmeasured
- [ ] Annotate at least one multi-room video per `docs/evaluation_plan.md`.
- [ ] Measure region precision/recall, keyframe segmentation accuracy (≥ 0.90), `room_change` F1 (≥ 0.70), correct-room query rate (≥ 0.90).
- [ ] Record config, commit, model versions and artifacts with the run.

---

## Milestone 3 — Voice Agent (M-C · FR5, FR6 · lead Ali Sher)

**Goal:** speech and text queries answered with calibrated confidence, evidence, temporal reasoning and explicit abstention.
**Exit evidence:** AC-09…AC-13, AC-28; SC1, SC2, SC5, SC6.

### 3.1 Done
- [x] Typed queries (FR6.2): synonym matching, plural handling, not-found with available-labels hint.
- [x] Room-constrained queries and room clause in explanations (FR5.6, FR5.7; 8 reasoning tests).
- [x] Query endpoint returns instance, anchor, room, relation and other instances (`api.py::query_memory`).

### 3.2 Speech input — FR6.1 / FR6.3 (M/L)
- [ ] Choose ASR provider and placement (decision #2).
- [ ] Microphone capture in the patient view; the current "Tap to Ask by Voice" button re-submits text.
- [ ] Transcript + confidence returned to the client; confirm/correct step when confidence is low (FR6.3).
- [ ] Speech/text equivalence on 10 queries; report transcription accuracy (AC-13, target ≥ 80%).

### 3.3 Temporal queries — FR5.2 / FR5.3 (H/M)
- [ ] Intent routing: where / when / what-happened / did-I.
- [ ] Relative-time parser (`this morning`, `yesterday`, `last night`, `before lunch`) against wall-clock time.
- [ ] Retrieve from hot and summarised tiers; label summarised evidence.
- [ ] "No matching activity — capture may have been off" response (UC-05 A1).
- [ ] 10 temporal queries with known answers (AC-10, target ≥ 60%).

### 3.4 Freshness — NFR-R3 (H)
- [ ] Real relative time from `last_seen_timestamp` instead of the constant `"Recorded today"`.
- [ ] 6-hour freshness window; stale answers state when the object was last seen (AC-28).
- [ ] Stale-object test with a synthetic old timestamp.

### 3.5 Confidence and abstention — FR5.5 / SC6 (H)
- [ ] Computed confidence from detection score, mask/lifting quality, association certainty and recency (replaces `0.96`).
- [ ] Configurable abstention threshold (decision #8).
- [ ] Distinguish never observed / observed but stale / low confidence.
- [ ] 5 unanswerable queries, ≥ 4 abstain, zero fabricated locations (AC-12).
- [ ] Remove the Flutter offline mock answers (§6 A9) — they fabricate locations.

### 3.6 Evidence grounding — FR5.4 / SC5 (H)
- [ ] Every non-abstaining answer carries an evidence reference: observation ID, time, anchor, room, crop path (AC-11).
- [ ] Store a real evidence crop when a placement is recorded; replace the generated SVG.
- [ ] Fallback text evidence when the frame has been purged.
- [ ] Evidence-coverage test over all non-abstaining answers (100%).

### 3.7 Answer quality and multi-instance handling (M)
- [ ] Enforce ≤ 2 short sentences (NFR-U2, AC-14); current templates emit up to 3.
- [ ] Clarification flow when several instances match (UC-03 A3); `other_instances` is returned but unused.
- [ ] Query log with resolved evidence (UC-03 postcondition).
- [ ] Optional tool-calling agent / VLM over memory (decision #3); retrieval-first, evidence required, keyframe captions cached (TC4).
- [ ] Vocabulary / ontology file as the single source for labels and synonyms — `context/answer.md` §3.

---

## Milestone 4 — Portal & Testing (M-D · FR7, FR8, NFRs · lead Shahmeer)

**Goal:** authorised, consent-scoped caregiver access; accessible portal; measured performance and benchmark results.
**Exit evidence:** AC-14…AC-20, AC-24…AC-26, AC-30; SC4, SC7, SC8; NFR-S1–S5, NFR-P1.

### 4.1 Done
- [x] FastAPI gateway: health, query, timeline, anchors, scene_graph, rooms, rooms/rename, datasets, crops, simulate, reset (19 API tests).
- [x] Flutter patient recall view with recent-search history; caregiver timeline and hazard card; dataset switcher; simulator panel.
- [x] Apple HIG restyle (panel feedback item 4): design tokens, 44 pt targets, segmented control.
- [x] CI: Ruff, pytest, Flutter analyze/test (`.github/workflows/ci.yml`).

### 4.2 Authentication and authorisation — FR8.1 / FR8.4 (H)
- [ ] Choose auth mechanism and credential storage (decision #4).
- [ ] Caregiver username/password login (NFR-S3).
- [ ] Primary-user grant / restrict / revoke with timestamps; enforced on every request (AC-17).
- [ ] Patient identity boundary and consent record.
- [ ] Protect mutating endpoints (`rooms/rename`, `simulate_transition`, `reset`, `dataset/select`); validate every `dataset_id` (§6 C8).
- [ ] Replace wildcard CORS with explicit origins.
- [ ] Tests: 5 invalid credentials all denied and logged (AC-16); revocation (AC-17).

### 4.3 Security and privacy — NFR-S1–S5 (H/M)
- [ ] TLS in transit; AES-256 at rest for the memory store and `home_map.json` (AC-20; decision #5).
- [ ] Caregiver scope excludes raw video and out-of-scope history (AC-26).
- [ ] Access audit log: username, timestamp, result; 30-day retention; visible to the primary user (AC-18).
- [ ] Raw-frame purge after 24 h with a verification check (AC-30).
- [ ] Full, immediate, irreversible deletion of history (NFR-S5, UC-11).
- [ ] Written privacy-limitation statement (bystanders, evidence crops).

### 4.4 Portal and client — FR7 / FR8.2 / 8.3 / 8.6 (H/M)
- [ ] Evidence display (image or description, time, location) in patient and caregiver views (FR7.2, AC-14).
- [ ] Caregiver object-state verification with stale indicator (UC-09).
- [ ] Daily activity summary view (FR8.3, UC-10).
- [ ] Access-log view (FR8.5).
- [ ] Room list / rename screen; `ApiService` has no room methods (UC-13, AC-31; decision #12).
- [ ] Timeline with session/date filter matching the real session log (FR7.4, AC-25).
- [ ] Capture pause and delete-history controls (UC-11).

### 4.5 Accessibility and usability — NFR-U (M)
- [ ] Three text sizes (AC-24).
- [ ] Measured WCAG AA contrast ≥ 4.5:1.
- [ ] First-time-user task: one query in ≤ 60 s, 5 participants (AC-15, SC8); record protocol and results, no clinical claim.

### 4.6 Performance — NFR-P (H/M)
- [ ] End-to-end latency p50/p95/max over ≥ 100 warm requests; target p95 ≤ 5 s (AC-19, SC4).
- [ ] Ingestion backlog over 10 minutes (NFR-P2).
- [ ] Storage growth after retention (NFR-P3).
- [ ] Record hardware, config, model versions and commit with every measurement.

---

## 5. Cross-cutting: benchmark, report and records

### 5.1 Benchmark — O7, SC1–SC3 (H)
- [ ] Select dataset/subset and annotation strategy (decision #1; Ego4D subset is only a candidate).
- [ ] Build `Aegis-TestSet-v1`: ground truth for object locations, events, rooms, temporal queries; assign an owner.
- [ ] Spatial accuracy (≥ 70%, AC-09) and temporal accuracy (≥ 60%, AC-10).
- [ ] Accuracy drop after compaction (≤ 15 points, AC-08), including the multi-day compaction experiment.
- [ ] Evidence coverage and abstention correctness (SC5, SC6).
- [ ] Iteration 1 exit criterion is still unevidenced: 10 placements, ≥ 70% last-location correct.
- [ ] Document dataset limitations before reporting any number.

### 5.2 Report and documentation
- [ ] Correct the report where it says rename persists to the home registry (Table 3.8, UC-13 main flow, §5.3) — or land §2.3 first.
- [ ] Update figures that lag the text: use-case diagram (UC-13), component, class, data-flow and sequence diagrams (rooms, registry, compaction, auth, speech).
- [ ] Update report test count (84 → current) and M1 status (live path is now connected to memory).
- [ ] Rewrite `docs/fyp1_mid_defense_dossier.md`: it still claims 55 tests, `S = 5.0×` and a Z-up frame.
- [ ] Fix `AGENTS.md` stale path `src/aegis/poc/memory/scene_graph.py`.
- [ ] Consolidated compute/storage/device account (panel item 3) using measured numbers from `benchmark_stats.json`.
- [ ] Iteration 3 and 4 dates, owners and scope (decision #11).
- [ ] End-to-end GPU + Flutter + live-camera evidence run.
- [ ] Optional hardware metadata if the supervisor asks: exact laptop CPUs, phone model and Android version, test browser/device.

---

## 6. Improvements found in the current codebase

Each item was checked in source. Priority: **P0** blocks requirements or produces wrong answers · **P1** blocks scale or accuracy · **P2** cleanup.

### 6.1 Architecture

- [ ] **A1 (P0) Memory is rebuilt per session, not maintained.** `build_relative_4d_scene_graph` consumes one session's boxes, `_clear_downstream_artifacts` wipes prior output, and instance IDs restart at 1. Nothing accumulates across sessions, so "three days of memory" has no place to live. *Fix:* a persistent memory store with an `ingest(session)` operation that matches new observations against existing instances and anchors.
- [ ] **A2 (P0) Timeline stores one entry per instance per keyframe.** Occluded instances are re-emitted every keyframe (`scene_graph.py:780-889`), so size is O(keyframes × instances). Measured on the `demo04` fixture: 268 entries, 294 KB for 46 s (≈ 1.1 KB per entry, ≈ 6 KB per second of video). The graph is then written three times (`r4d_scene_graph.json`, and twice more inside `spatial_memory_graph.json`, `workers.py:448-487`). *Fix:* store state runs (one row per stable placement), in SQLite.
- [ ] **A3 (P0) Every session has its own world frame and an unverified scale.** `vggt_runner.py:177-194` puts the origin at the first keyframe. Positions from two sessions are not comparable, so registry proximity matching and cross-session re-identification by 3D distance cannot work. Thresholds (`0.45`, `0.35`, `zone_link_radius: 1.5`) are written as metres while the report states scale is not calibrated. *Fix:* keep cross-session memory symbolic (room / anchor / relation), align sessions with a similarity transform estimated from shared anchors when geometry is needed, and express thresholds relative to a per-session scale estimate.
- [ ] **A4 (P0) No gravity direction.** "Up" is assumed to be −Y of the first camera (`rooms.py:27`, `workers.py:904`), which is only true if the phone starts level. This is the root of the elevation problem — see `context/answer.md` §2.
- [ ] **A5 (P1) VGGT runs once over the whole session.** `model(images)` receives every keyframe (`vggt_runner.py:106-113`); all pointmaps go into one `.npz` and are loaded whole in the detect stage (`workers.py:347-349`). At ≈ 4.3 MB per keyframe a one-hour live session cannot fit GPU or RAM. *Fix:* overlapping windows, per-window artifacts deleted after lifting.
- [ ] **A6 (P1) API is a JSON file behind a process-global cache.** `ACTIVE_DATASET_ID` is global mutable state; `find_latest_objects_state` re-scans the entire timeline on almost every request (`api.py:266-284`); `/datasets` loads every graph; the cache is never invalidated by a new file. Simulation endpoints mutate memory through `GET` and contain demo literals (`"Demo06-Self"`, frame `642`). *Fix:* a repository layer over the store with a `latest_state` table; move the simulator behind a debug flag.
- [ ] **A7 (P1) Vocabulary is spread over at least six places** (`config/demo.yaml`, `ANCHOR_CLASS_NAMES`, `ROOM_LANDMARK_ROOM_TYPES`, `CONTAINER_LABELS`, size filters in `lifting.py`, `ITEM_SYNONYMS`) plus three separate label normalisers. See `context/answer.md` §3.
- [ ] **A8 (P1) Wall-clock time is dropped.** Promotion keeps `capture_timestamp` in a sidecar, but graph entries and events carry seconds-from-start. "This morning" and the 6-hour freshness rule cannot be evaluated. *Fix:* store absolute capture time on every observation and event.
- [ ] **A9 (P0) The Flutter client fabricates answers when offline.** `api_service.dart:244-470` returns canned locations with `confidence: 0.96` if the backend does not respond in 3 s. This breaks the safe-failure invariant and SC6. *Fix:* show "can't reach memory" instead; keep mocks in tests only.
- [ ] **A10 (P1) Live is not continuous end to end.** Capture → promote → upload → three cold Modal functions → download. Models are loaded on every call. *Fix:* micro-batches, Modal classes that load weights once, and run detection in parallel with VGGT since it only needs pointmaps at lifting time.
- [ ] **A11 (P1) No evidence artifact exists.** Events list `evidence_frames` IDs but no crop is saved, and frames must be purged after 24 h. *Fix:* write a small crop when a placement run is created.

### 6.2 Model choices

- [ ] **M1 (P1) Two segmenters per detection.** YOLOE-seg already returns masks, then SAM 2 hiera-large is run on every box (`detector.py:407-430`). *Fix:* use the YOLOE mask and call SAM 2 only when it is missing or small; or drop to a smaller SAM 2. Measure mask IoU and time before choosing.
- [ ] **M2 (P1) Hand-written tracker with a 16-bin HSV histogram for re-ID** (`detector.py:54-104`). Similar-coloured objects swap identities; lighting changes break matches. *Fix:* Ultralytics' built-in trackers or SAM 2 video propagation for short-term tracks, and an image-embedding (DINOv2 / SigLIP class) of the masked crop for long-term re-ID. The same embedding enables open-vocabulary query matching.
- [ ] **M3 (P1) Detection is tied to VGGT keyframes** (stride 6). On the live path at 2 FPS that is one detection every ≥ 3 s, so short pick-up/put-down actions are missed. *Fix:* detect and track on every keyframe, reconstruct on a subset, lift using the nearest reconstructed frame.
- [ ] **M4 (P1) Detections are capped at 6 per frame and suppressed across classes** at IoU 0.35 (`detector.py:382-404`). Cluttered scenes lose objects. *Fix:* class-aware suppression and a configurable cap.
- [ ] **M5 (P2) VGGT settings are ignored.** `vggt.dtype`, `vggt.batch_size` and `vggt.image_size` are never read; inference runs in float32 at a hard-coded 512; images are loaded and resized twice. *Fix:* honour the config, enable autocast, and measure frames-per-window on the L4.
- [ ] **M6 (P2) Hands come from an open-vocabulary "hand" prompt and box overlap.** A dedicated hand/hand-object model would make pickup detection more reliable — evaluate on the demos.
- [ ] **M7 (P2) Unbatched inference from file paths** (`model.predict(str(image_path))` after the frame was already decoded). Batch frames and pass arrays.
- [ ] **M8 (decision) VLM use.** Call a VLM only when an event is created (caption the evidence crop, cache it) and for low-margin spatial relations; never per frame (TC4).

### 6.3 Code

- [ ] **C1 (P0) Demo-specific rules inside the memory engine.** Shoes get IDs from fixed X thresholds (`scene_graph.py:289-297`); in-hand and placement are forced by frame ranges 280–480 (`:621-641`, `:669-681`, `:795-812`); with no anchors a fake `Storage Cabinet #1` is created at the origin (`:193-202`) and used as an event destination (`:442`). Any other video containing shoes gets wrong identities and states. `lifting.py:336` says such rules were removed. *Fix:* delete them, rely on the general association path, return no anchor when none is observed.
- [ ] **C2 (P0) Oriented boxes use the wrong vertical axis.** `lifting.py:139-177` fits yaw in the X–Y plane and treats Z as height — a leftover from the Z-up frame. In the current Y-down frame this rotates boxes about the viewing axis. *Fix:* fit in the plane perpendicular to the estimated up vector.
- [ ] **C3 (P0) Room rename corrupts events.** `api.py:572-580` rewrites the source/destination of every event whose room label starts with `"room #"`, not only the renamed room. *Fix:* store `room_id` on events and match on it.
- [ ] **C4 (P1) Objects can never be "on the floor" or "under" anything** outside the shoe special case; any object within 0.35 of an anchor centre becomes `on_surface` or `inside` (`scene_graph.py:706-711`). `bed`, `sofa`, `dining table` are room landmarks only, so they can never be an object's anchor.
- [ ] **C5 (P1) `dataset_id` is not validated in the API.** It is interpolated into paths in `get_search_paths` and `/video/{dataset_id}`; `validate_dataset_id` exists but is not called. Labels are also written unescaped into the SVG response.
- [ ] **C6 (P1) Silent synthetic reconstruction.** On CPU, any VGGT failure falls back to fabricated poses and flat depth (`vggt_runner.py:196-239`). *Fix:* raise unless a test flag is set.
- [ ] **C7 (P2) Dead and broken legacy code.** `paths.py:105` reads `config.dust3r`, which does not exist; `depth`, `pose` and `geometry` config sections and the DROID settings are unused; `dust3r` aliases remain in three files.
- [ ] **C8 (P2) Query matching is substring-based and over-broad.** `"cup"` and `"mug"` resolve to `bottle`; `canonical in clean` matches inside other words; `_matches_query` has five fallbacks. Replace with the ontology lookup.
- [ ] **C9 (P2) Answer wording asserts more than the evidence** ("safely put away", "securely stored") and exceeds two sentences.
- [ ] **C10 (P2) `workers.py` is 1,300 lines** mixing orchestration and Rerun drawing; `_write_ply` writes ASCII in a Python loop. Split the visualiser out; write binary PLY.
- [ ] **C11 (P2) Tests lock in demo behaviour** and there is none for vertical relations, multi-session identity, or the rename bug. Add coverage reporting to CI.
- [ ] **C12 (P1) Live frames are re-encoded from JPEG to PNG** on promotion (`live_handoff.py:152-154`), roughly a tenfold size increase with no quality gain. Accept JPEG in the frame contract.
- [ ] **C13 (P2) Flutter:** half of `api_service.dart` is mock data; UI branches on dataset names (`home_screen.dart:542-544`); timeouts are hard-coded; one widget test.

---

## 7. Open decisions (the report leaves these open)

| # | Decision | Blocks | Recommendation | Owner |
|---|---|---|---|---|
| 1 | Evaluation dataset and annotation strategy | M2 rooms, §5.1 | Own scripted multi-room recordings as the primary set (matches phone capture); Ego4D subset as secondary | Team |
| 2 | ASR provider, on-device or cloud | M3 speech | On-device platform speech recognition first; server Whisper as fallback | M-C |
| 3 | VLM/LLM provider and tool interface | M3 agent | Rule-based retrieval stays primary; VLM only for event captions and tie-breaks | M-C |
| 4 | Identity, credential storage, grants, audit format | M4 auth | Local accounts with salted password hashes and short-lived tokens in the same store | M-D |
| 5 | Encryption at rest | M4 security | Encrypted SQLite for the store; TLS at the gateway | M-D |
| 6 | Persistence for tiers and summaries | M2 compaction | One SQLite file per home | M-B |
| 7 | Compaction trigger and summary format | M2 compaction | Nightly/idle job; template text plus a structured sidecar | M-B |
| 8 | Abstention threshold | M3 confidence | Pick from a precision/abstention curve on the benchmark | M-C |
| 9 | Evidence crops versus the 24-hour raw-frame rule | M3 evidence, M4 privacy | Keep object-only crops as derived evidence; confirm with supervisor | Team |
| 10 | Gravity source | M2 elevation | Floor-plane fit now; phone IMU when the capture app exposes it | M-A/M-B |
| 11 | Iteration 3/4 dates, owners, final thresholds | Planning | — | Team |
| 12 | Room calibration UI in the caregiver view | M4 portal | Yes, behind caregiver auth | M-D |

---

## 8. Recommended order

1. **C1, C2, C3, A9** — correctness fixes that affect every later measurement.
2. **A4 + C4** — gravity and vertical relations (elevation problem).
3. **A2 + A1 + A8** — persistent store with state runs and wall-clock time (decision #6).
4. **M2 §2.3** — wire the room registry and rename.
5. **A7** — ontology file; then per-home vocabulary.
6. **M2 §2.4** — compaction and summaries on top of the store.
7. **M3 §3.4–3.6** — freshness, confidence/abstention, evidence.
8. **M3 §3.2–3.3** — speech and temporal queries.
9. **A5, A10, M1–M4** — windowed, faster perception; physical one-hour soak.
10. **M4 §4.2–4.5** — auth, security, portal, accessibility.
11. **§4.6, §5.1** — measure, then report. **§5.2** — close the documentation.

---

## Definition of done (report §9.8 / spec §20)

- [ ] All H and M requirements implemented, or documented as deferred with a reason.
- [ ] AC-01…AC-31 executed with results recorded; misses reported.
- [ ] SC1–SC9 measured on the selected benchmark and reported as proposed targets.
- [ ] All tests pass; Ruff clean.
- [ ] No unmeasured result or unimplemented feature presented as complete.

## Invariants while doing this work

- Raw VGGT-Ω coordinates remain the spatial source of truth; derived quantities (up vector, floor height, scale estimate) are stored beside them, never baked in.
- Rooms come from trajectory clustering + sparse landmarks, never dense clouds.
- Room landmarks never become personal-object memories (they may serve as anchors).
- Object permanence and multi-instance identity must not regress.
- Safe failure over fabrication: no evidence → explicit uncertainty.
- Batch and live contracts stay separate, connected only through promotion.
