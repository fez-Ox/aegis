# Aegis — Remaining Work by Milestone

**Source:** `context/specification.md` (FYP-1 mid-report restated as a build spec).
**Baseline verified on:** 2026-11-06, against the current working tree.
**Milestones:** M1 Ingestion · M2 Graph & History · M3 Voice Agent · M4 Portal & Testing.

> Rule for every item: do not mark complete without a test, a measured result, or a recorded artifact.
> Keep the 84 pre-existing tests passing (129 total after M1) and `ruff check` / `ruff format --check` clean.

---

## 0. Verified baseline

### 0.1 What already exists

| Area | Implemented today | Evidence |
|---|---|---|
| Batch ingestion | Video → sampled PNG frames + `metadata.json` + intrinsics, Modal CPU worker | `src/aegis/ingestion/video.py`, `remote/workers.py` |
| Local live ingestion | MJPEG sampler at 2 FPS, reconnect timeout, unique sessions, JPEG + JSONL + manifest, credential redaction | `ingestion/live_*.py`, `test_live_ingestion.py` |
| 3D + perception | VGGT-Ω pointmaps/poses, YOLOE/YOLO-World + SAM 2, 2D→3D lifting, OBBs | `geometry/`, `perception/` |
| Object memory | Rooms → Anchors → Objects, persistent instance IDs, occlusion permanence, carried-object room inheritance | `memory/scene_graph.py`, `test_scene_graph.py` |
| Rooms | Trajectory clustering + revisit merging, landmark typing, neutral `Room #N`, `room_change` events, floor-plane footprints | `memory/rooms.py`, `test_rooms.py` |
| Room identity (module only) | `HomeRoomRegistry`, landmark/proximity matching, slow centroid blending, corrupt-file fallback | `memory/home_registry.py`, `test_home_registry.py` |
| Query (item only) | Synonym matching, room filters, room clause, not-found + available-labels hint | `memory/reasoning.py`, `remote/api.py` |
| API | health, query, timeline, anchors, scene_graph, rooms, rooms/rename, datasets, crops, simulate, reset | `remote/api.py`, `test_api.py` (19 tests) |
| Flutter | Patient recall, caregiver timeline + hazard card, dataset selector, simulator, Apple HIG styling | `apps/mobile/lib/` |
| Docs | Room evaluation protocol, live capture notes | `docs/evaluation_plan.md`, `docs/live_capture.md` |

### 0.2 Verified gaps and spec/code discrepancies

These are not opinions; each was checked in source.

1. **Room calibration is not actually persisted per home.** `home_registry.py` is referenced only by its own module and tests. `workers.py` never calls `calibrate_from_rooms`, and `POST /api/v1/rooms/rename` updates only `r4d_scene_graph.json` — it does **not** write `home_map.json`, although spec §7.7 says it does. FR3.6/FR3.7 are therefore partial.
2. **The “Tap to Ask by Voice” button is text-only.** No microphone capture, no ASR dependency in `pyproject.toml`, and the button re-submits the current text query.
3. **Confidence and recency are hardcoded.** `confidence=0.96` in `remote/api.py`; `last_seen_time_ago="Recorded today"` regardless of the actual timestamp.
4. **No compaction code or tests.** FR4 is entirely absent from `src/` and `tests/`.
5. **No authentication or authorization.** `rooms/rename`, `simulate_transition`, `reset`, and `dataset/select` are unauthenticated; CORS is wildcard.
6. **No room screen and no real evidence display in Flutter.** `ApiService` has no rooms/rename methods; patient result shows no crop/evidence image.
7. **No temporal query path.** `/api/v1/query` resolves items only; there is no “when / what did I do” handler and no relative-time parsing.
8. **Evidence crop is a generated SVG placeholder**, not a stored frame crop: `/api/v1/crops/{id}` returns SVG text.
9. **Docs drift.** `docs/fyp1_mid_defense_dossier.md` still claims 55 tests, `S=5.0×`, and Z-up transforms, contradicting the current raw VGGT-Ω invariant.

---

## Milestone 1 — Ingestion (M-A, FR1–FR2)

**Goal:** a real phone → pipeline → memory path that survives a one-hour session.
**Exit evidence:** AC-01, AC-03, AC-21, AC-27, AC-29; NFR-R1, NFR-R2, NFR-P2.

### 1.1 Connect live capture to the memory pipeline (H) — **done**

- [x] Define the handoff contract from a live session directory (`captures/<session_id>/index.jsonl` + JPEGs) into the batch preprocessing stage, so live frames become `frame_*.png` + `metadata.json` and reach VGGT → perception → R4DSG. (`src/aegis/ingestion/live_handoff.py`, frozen in `docs/artifact_contracts.md`.)
- [x] Add a session → dataset mapping (`--dataset-id`, or derived as `live_<session_id>`) with the same `validate_dataset_id` safety used elsewhere.
- [x] Wire a `live` stage into `run_pipeline.py`; it promotes, uploads to the data Volume, and chains into preprocess/VGGT/perception/Rerun. `aegis-ingest --promote-dataset-id` can promote without Modal.
- [x] Publish a complete phone → memory integration note in `docs/live_capture.md` (phone app, URL, session start/stop, pause/resume, promotion, artifact layout, verification).
- **Verified:** `tests/test_live_handoff.py` (promotion, sidecars, `run_preprocess` live detection), `tests/test_live_cli.py` (CLI capture + promote, upload path mapping).
- **Resolved gap:** “no complete phone-to-memory path” — the path is implemented and tested end-to-end with deterministic sources up to the Modal boundary.

### 1.2 Capture control, pauses and gaps (H/M) — **done except mobile UI**

- [x] Implement pause/resume for live capture (FR1.3): while paused no frames are written; pause start/end and duration are recorded in `session.json.pauses[]`, and a `pause` gap is appended to `index.jsonl`. Controlled by `SIGUSR1`/`SIGUSR2` or a pause file (`--pause-file`).
- [x] Record explicit **gap markers** for recovered disconnects, pauses and storage stalls (FR2.3): `gap_start`, `gap_end`, `reason`, `dropped_estimate`, `sequence_before`, `sequence_after`, `recovered`. Terminal disconnects live in `session.json.gaps` only, so index frame-line count stays exact.
- [x] Replace the reconnect counter-only behaviour with gap records that downstream memory can consume (promotion copies `gaps`/`pauses` into `metadata.json`).
- [ ] Add the pause control to the mobile UI (with the M4 capture/delete screen) and a server-side pause endpoint or session control. **Deferred to M4** — out of scope for M1 and not verifiable in this environment.
- **Verified:** `test_pause_skips_frames_and_records_gap`, `test_terminal_disconnect_gap_is_manifest_only`, `test_recovered_disconnect_records_index_gap`.

### 1.3 Keyframe selection and ingestion reliability (H/M) — **done (simulated verification)**

- [x] Implement keyframe selection by criterion, not only fixed sampling/stride: Laplacian-variance sharpness, brightness bounds, visual-change novelty, duplicate suppression, and a forced `max_interval_seconds` keyframe (FR2.1, TC3). See `src/aegis/ingestion/keyframe.py`.
- [x] Make the criterion configurable (`config/demo.yaml: live.keyframe`), and record each decision's sharpness/brightness/visual-change/reason on the frame record plus aggregate counts in the session manifest (AC-02).
- [x] Discard blurred/dark frames and count them (`rejected_frame_count`, `keyframe_selection.rejected_by_reason`) (UC-01 alternate A2).
- [x] Add bounded frame buffering during short pipeline stalls with automatic resume and a backlog metric (`FrameBuffer`, `buffer_capacity`, `dropped_frame_count`, `buffer.max_backlog`) (FR2.4, NFR-P2, AC-29).
- [x] Verify a 1-hour continuous session without crash/stall (NFR-R1, AC-01) — **simulated:** `test_simulated_one_hour_session` runs 3,600 frames over 3,600 s with a deterministic clock, asserting status, frame count, and zero gaps. **A physical phone soak is still unmeasured.**
- [x] Verify graceful resume within 15 s after a 10 s source disconnect, without process restart (AC-03) — **simulated:** `test_disconnect_reconnects_within_fifteen_seconds` asserts one recovered gap and an outage ≤ 15 s; `test_recovered_disconnect_records_index_gap` covers the same loop.
- [x] Implement crash recovery: `session_state.json` checkpoints, `--resume` truncates a half-written trailing index line, continues sequence numbers, and appends to `index.jsonl`. Worst-case loss is bounded by `checkpoint_every` frames, well under 1 minute (NFR-R2, AC-27). **Verified:** `test_resume_after_crash_continues_sequence`.

### 1.4 Artifact and contract stabilization (H) — W1 dependency for M2–M4 — **done**

- [x] Freeze and document schema versions for normalized frames + `metadata.json`, live session index/manifest, `poses.json`, pointmaps, detections, `r4d_scene_graph.json`, `home_map.json` in `docs/artifact_contracts.md`.
- [x] Define canonical local vs Modal-volume paths for live sessions and ensure discovery covers them (`DatasetPaths.source_metadata`, `live_timestamps`, `live_session`; `upload_dataset_to_modal_volume` maps `data/<id>/*` → `/<id>/*`).
- [x] Decide and document frame timestamp semantics (source capture vs laptop receive vs ingestion) and propagate one authoritative timestamp (`capture_timestamp`; `timebase: "capture"` after promotion).
- [x] Add contract tests for schema/version mismatches and missing fields (`tests/test_live_contracts.py`).

### 1.5 Milestone 1 tests — **done**

- [x] Live → preprocess handoff test (`test_run_preprocess_accepts_promoted_live_dataset`).
- [x] Pause/resume test: no frames during pause, gap recorded, resume works (`test_pause_skips_frames_and_records_gap`, `test_resume_after_crash_continues_sequence`).
- [x] Gap detection test on simulated disconnect and dropped frames (`test_terminal_disconnect_gap_is_manifest_only`, `test_recovered_disconnect_records_index_gap`, `test_stall_buffer_recovers_and_records_gap`).
- [x] Stall buffering/backlog recovery test (`test_stall_buffer_recovers_and_records_gap`, `tests/test_live_buffer.py`).
- [x] Keyframe criterion test on a scripted scene-change fixture (`tests/test_live_keyframe.py`, `test_keyframe_selection_filters_duplicates`).
- [x] One-hour soak test, repeatable harness (`test_simulated_one_hour_session`); a physical run remains manual (steps in `docs/live_capture.md` §9).

**M1 status:** 129 tests pass; `ruff check` and `ruff format --check` are clean. Not measured: physical 1-hour phone soak and the mobile pause UI (deferred to M4).

---

## Milestone 2 — Graph & History (M-B, FR3–FR4)

**Goal:** a three-day detailed memory, compacted older history, stable per-home rooms, and real activity history.
**Exit evidence:** AC-04, AC-05, AC-06, AC-07, AC-08, AC-22, AC-23, AC-31; SC3, SC9; NFR-P3.

### 2.1 Compaction and tiered retention — FR4, entirely missing (H)

- [ ] Choose and document the persistence technology for summaries/tiers (open decision #6; no relational DB exists today).
- [ ] Define the tiered store: hot detailed records, warm summaries, and the boundary between them.
- [ ] Implement configurable recent window, default **3 days** (FR4.1).
- [ ] Implement a compaction job that runs in the background on a configured trigger (interval or size based) — do not run it on the query path (spec §5.1).
- [ ] Summaries must retain: object identity, last known location, room identity when available, and event type (FR4.2).
- [ ] Preserve room IDs/labels through compaction, not just anchor labels (W2/§16). Add a room-label survival check.
- [ ] Mark answers derived from summaries as **summarised** (FR4.3, AC-23).
- [ ] Flag a compaction failure and retain source detail when required context cannot be preserved (UC-12 alternate A1).
- [ ] Bound storage growth sub-linearly and record the growth curve after retention is applied (FR4.4, NFR-P3, AC-07).
- [ ] Add before/after query accuracy evaluation on the same query set (AC-08, SC3); keep the result **unmeasured** until the benchmark exists.
- [ ] Add tests: retention boundary, summary content, room-label survival, summarised marking, sub-linear growth, failure flag.

### 2.2 Per-home room identity — FR3.6/FR3.7 partial (H)

- [ ] Add `home_id` configuration/plumbing (pipeline config and/or dataset metadata) distinct from `dataset_id`.
- [ ] Call `calibrate_from_rooms` / `match_room_into_registry` from the memory-building worker so each session matches onto stable room identities (FR3.6).
- [ ] Load the existing registry **before** building the graph and apply matched labels, instead of always starting from neutral `Room #N`.
- [ ] Make `POST /api/v1/rooms/rename` also update `home_map.json` (FR3.7, AC-31); today it only edits the scene graph.
- [ ] Decide and document how renaming reconciles with a future session’s freshly estimated rooms (landmark overlap → proximity → blending is already implemented in the module).
- [ ] Add a restart + rebuild test: rename survives service restart, graph reload, and a new session’s matching (AC-31).
- [ ] Add a corrupt-registry safe-fallback test at the API level (module test exists; AC-31 also requires the endpoint path).

### 2.3 Activity history and event grouping — FR3.3 partial (H)

- [ ] Define what an “activity event” is beyond a spatial state change (e.g. sequence of placements, carried-object trajectory, room change).
- [ ] Group observations/transitions into timestamped activity events (FR3.3) and expose them through `/api/v1/timeline` and a session/date view.
- [ ] Add activity-level summaries that can feed M3 “what did I do?” answers.
- [ ] Add an event-order/timestamp ground-truth test (AC-05).

### 2.4 Restart persistence and graph lifecycle — FR3.5 / AC-06 (H)

- [ ] Prove memory contents are identical before and after an application restart (AC-06); current loading is JSON-based but there is no restart equivalence test.
- [ ] Handle graph regeneration while the API is alive (the cache already avoids caching empty graphs; add an explicit invalidation path for a newly written graph).
- [ ] Define behavior when `r4d_scene_graph.json` is missing/corrupt: safe empty graph is implemented; add a test for corrupt JSON at the API boundary.
- [ ] Decide whether event/timeline history is append-only or rebuilt; document it.

### 2.5 Room-memory evaluation — currently unmeasured (H)

- [ ] Select at least one evaluation video and annotate room boundaries/labels per the protocol in `docs/evaluation_plan.md`.
- [ ] Measure room region precision/recall, keyframe room-segmentation accuracy, `room_change` event F1, and room-grounded correct-room rate (AC-22, SC9).
- [ ] Report results honestly; keep them labelled unmeasured until the annotation and run artifacts exist.
- [ ] Record config, commit, model versions and artifacts with the run (spec §16).

### 2.6 Milestone 2 tests

- [ ] Compaction unit + integration tests (none exist today).
- [ ] Registry ↔ pipeline integration test.
- [ ] Rename → `home_map.json` → restart → match test.
- [ ] Activity grouping test.
- [ ] Restart equivalence and corrupt-graph tests.
- [ ] Room evaluation harness (not necessarily a CI test).

---

## Milestone 3 — Voice Agent (M-C, FR5–FR6)

**Goal:** speech and text queries answered with calibrated confidence, evidence, temporal reasoning and explicit abstention.
**Exit evidence:** AC-09 to AC-13, AC-28; SC1, SC2, SC5, SC6.

### 3.1 Speech input — FR6.1/FR6.3 (H/M)

- [ ] Choose the ASR provider and whether it runs on-device or in the cloud (open decision #2).
- [ ] Add microphone capture to the Flutter patient screen; replace the current fake “Tap to Ask by Voice” action.
- [ ] Add a transcription endpoint or client-side transcription path; return transcript + confidence.
- [ ] When transcription confidence is low, let the user confirm or correct before answering (FR6.3, L).
- [ ] Keep typed queries fully supported and equivalent (FR6.2).
- [ ] Add speech/text equivalence tests with at least 10 queries (AC-13).
- [ ] Measure transcription accuracy on test speakers; report, do not assume 80%.

### 3.2 Temporal query handling — FR5.2/FR5.3 (H/M)

- [ ] Add a temporal intent path to the query API: “when did I last see X?”, “what did I do this morning?”, “what happened yesterday?”.
- [ ] Resolve relative expressions (`this morning`, `yesterday`, `last night`, `before lunch`) against the current time and session clock (FR5.3).
- [ ] Retrieve from both detailed and compacted tiers, and label summarised evidence (FR4.3, UC-05 A2).
- [ ] Return matching events with times, rooms and anchors.
- [ ] Handle “no matching activity” explicitly and state that capture may have been off (UC-05 A1).
- [ ] Add 10 temporal queries with known answers and measure accuracy against SC2 (AC-10).

### 3.3 Freshness and stale reporting — NFR-R3 (H)

- [ ] Implement the 6-hour freshness window.
- [ ] Compute real relative time from `last_seen_timestamp` instead of `"Recorded today"`.
- [ ] When no observation falls in the window, say when it was last seen and do not present it as current (AC-28).
- [ ] Add a stale-object test with a synthetic old timestamp.

### 3.4 Calibrated confidence and abstention — FR5.5 / SC6 (H)

- [ ] Replace fixed `confidence=0.96` with a computed score that incorporates detection confidence, lifting/mask quality, association certainty and recency.
- [ ] Add a configurable abstention threshold (open decision #8) and document the default.
- [ ] Abstain when evidence is missing or confidence is below threshold; do not fabricate a location (FR5.5, SC6).
- [ ] Distinguish “never observed” from “observed but stale” from “low confidence”.
- [ ] Add at least 5 unanswerable-query tests and low-confidence fixtures; target 80%+ correct abstention (AC-12).
- [ ] Keep confidence values out of user-facing claims until calibrated.

### 3.5 Evidence grounding — FR5.4 / SC5 (H)

- [ ] Give every non-abstaining answer a retrievable evidence reference: observation ID, timestamp, anchor, room, and a real frame/crop path (FR5.4, AC-11).
- [ ] Replace the synthetic SVG crop with a real stored frame crop (with fallback when the frame has been purged).
- [ ] Ensure the Flutter result card displays the evidence (image or description + time + location) (FR7.2, AC-14).
- [ ] Make evidence optional only in the explicit no-evidence response; never show a location without evidence (UC-06 A1).
- [ ] Add an evidence-coverage test over all non-abstaining answers (100%).

### 3.6 Answer quality and multi-instance handling (M)

- [ ] Enforce ≤ 2 short sentences + one piece of evidence (NFR-U2, AC-14); current explanations are often 2–3 sentences.
- [ ] When multiple matching instances exist, ask a short clarifying question or list options (UC-03 A3); `other_instances` exists but there is no clarification flow.
- [ ] Log every query and its resolved evidence (UC-03 postcondition); currently no query log.
- [ ] Optionally add a VLM/tool-calling agent over memory (W3) after the provider is chosen (open decision #3); keep retrieval-first and evidence-required. Cache keyframe descriptions and process keyframes only (TC4).
- [ ] Keep room-constrained answers and the “anchor already names the room” rule working (FR5.6/5.7).

### 3.7 Milestone 3 tests

- [ ] ASR/transcript tests and text equivalence.
- [ ] Temporal parser tests for relative phrases and boundaries.
- [ ] Freshness/stale tests.
- [ ] Abstention/low-confidence tests.
- [ ] Evidence coverage test.
- [ ] Answer-length test.
- [ ] Multi-instance clarification test.
- [ ] Query-log test.

---

## Milestone 4 — Portal & Testing (M-D, FR7–FR8, NFRs, evaluation)

**Goal:** authorised, consent-scoped caregiver access; an accessible portal; measured performance and benchmark results.
**Exit evidence:** AC-14 to AC-20, AC-24 to AC-26, AC-30; SC4, SC7, SC8; NFR-S1–S5, NFR-P1.

### 4.1 Authentication and authorization — FR8.1/8.4 (H)

- [ ] Choose the identity/auth mechanism and credential storage (open decision #4).
- [ ] Implement username/password authentication for caregivers (FR8.1, NFR-S3).
- [ ] Add primary-user grant/restrict/revoke of caregiver access with timestamps (FR8.4, UC-07).
- [ ] Enforce grants on every request; revocation blocks the next request, an active session may expire naturally (FR8.4, AC-17).
- [ ] Define a patient identity boundary and consent record (currently absent, spec §14).
- [ ] Protect mutating endpoints: `/rooms/rename`, `/simulate_transition`, `/reset`, `/dataset/select`.
- [ ] Remove wildcard CORS (`allow_origins=["*"]`, credentials enabled) and configure explicit origins.
- [ ] Add invalid-credential tests: 100% denied (AC-16) and revocation tests (AC-17).

### 4.2 Security and privacy — NFR-S1–S5 (H/M)

- [ ] TLS in transit and AES-256 at rest for stored artifacts, including `home_map.json` and the scene graph (NFR-S1, AC-20).
- [ ] Ensure caregiver scope excludes raw video and out-of-scope history (NFR-S2, AC-26).
- [ ] Add an access audit log with username, timestamp and result, retained 30 days, visible to the primary user (FR8.5, NFR-S3, AC-18).
- [ ] Enforce raw-frame retention of 24 hours with a purge job and verification (NFR-S4, AC-30).
- [ ] Implement full, immediate, irreversible deletion of stored history (NFR-S5, AC-20, UC-11).
- [ ] Prefer derived structured memory over raw video where possible; document the privacy limitation statement.

### 4.3 Caregiver portal and Flutter completion — FR7/FR8.2/8.3/8.6 (H/M)

- [ ] Add caregiver object-state verification flow (query + latest state + evidence + stale indicator) (UC-09, FR8.2, AC-26).
- [ ] Add daily activity summary view sourced from events/summaries (FR8.3, UC-10).
- [ ] Add the access-log view (FR8.5).
- [ ] Add room listing/rename/calibration screen wired to `GET /api/v1/rooms` and `POST /api/v1/rooms/rename` (FR3.7/8.6, UC-13, AC-31). `ApiService` currently has no room methods.
- [ ] Add session/date filtering and a browsable timeline that matches the real session log (FR7.4, AC-25).
- [ ] Display answer evidence (image/description, time, location) in both patient and caregiver views (FR7.2, AC-14).
- [ ] Decide whether room calibration belongs in the caregiver view (open decision #13).

### 4.4 Accessibility and usability — FR7.3 / NFR-U1–U4 (M)

- [ ] Add in-app text size control with at least 3 sizes on Android/browser (NFR-U3, AC-24).
- [ ] Verify WCAG AA contrast ≥ 4.5:1 with a measured check (NFR-U3, AC-24).
- [ ] Keep answers plain-language and ≤ 2 sentences (NFR-U2).
- [ ] Run a first-time-user task test: one query in ≤ 60 s without assistance, 5 participants (NFR-U1, AC-15, SC8).
- [ ] Record the usability protocol and results; no clinical claim.

### 4.5 Performance validation — NFR-P1–P3 (H/M)

- [ ] Measure end-to-end query latency distribution (p50/p95/max) over ≥ 100 requests after warm-up; target p95 ≤ 5 s (NFR-P1, SC4, AC-19).
- [ ] Replace the fixture-level `< 0.500 s` assertion with a documented benchmark (keep the unit test, add the real measurement).
- [ ] Measure ingestion backlog over 10 minutes; target ≤ 30 s unprocessed backlog (NFR-P2, AC-29).
- [ ] Measure storage growth after retention/compaction (NFR-P3, AC-07).
- [ ] Record hardware, config, model versions and commit with every measurement.

### 4.6 Benchmark and evaluation — O7 / SC1–SC3, SC9 (H)

- [ ] Select and document the dataset/subset and annotation strategy (open decision #1; Ego4D portion is only a candidate).
- [ ] Build ground truth for object locations, events, rooms and temporal queries.
- [ ] Measure spatial accuracy (target ≥ 70%, SC1) and temporal accuracy (target ≥ 60%, SC2).
- [ ] Measure accuracy drop after compaction (target ≤ 15 points, SC3).
- [ ] Measure evidence coverage and abstention correctness (SC5, SC6).
- [ ] Execute and record AC-04, AC-05, AC-08, AC-09, AC-10, AC-22.
- [ ] Document dataset limitations and adaptation before reporting any number.

### 4.7 Docs, diagrams and final deliverables — W11 (M)

- [ ] Update `docs/fyp1_mid_defense_dossier.md` to current facts: 84 tests, raw VGGT-Ω coordinates (no 5×/Z-up transform), room hierarchy, no ASR/auth yet.
- [ ] Update architecture, class, data-flow and use-case diagrams to include rooms, compaction, auth and speech; add UC-13 to the use-case diagram.
- [ ] Document the graph/retention policy and the privacy/security limitations statement.
- [ ] Record reproduction commands and artifacts for each claim.
- [ ] Add tests for every new capability: compaction, access control, speech, temporal reasoning (definition of done #4).
- [ ] Keep 84 existing tests + new tests passing and Ruff clean.

---

## Cross-cutting decisions to resolve before coding

Each is explicitly left open by the report; do not silently invent an answer.

| # | Decision | Blocks | Suggested owner |
|---|---|---|---|
| 1 | Evaluation dataset/subset + annotation strategy | M2 room metrics, M4 benchmark | Team |
| 2 | ASR provider and on-device vs cloud | M3 speech | M-C |
| 3 | VLM/LLM provider and tool interface | M3 optional agent | M-C |
| 4 | Identity provider, credential storage, grant store, audit format | M4 auth | M-D |
| 5 | Encryption approach (TLS + AES-256 at rest) | M4 security | M-D |
| 6 | Persistence technology for summaries/tiered store | M2 compaction | M-B |
| 7 | Compaction trigger, summary format, importance criteria | M2 compaction | M-B |
| 8 | Abstention confidence threshold | M3 confidence | M-C |
| 9 | Keyframe selection criterion beyond examples | M1 reliability | M-A |
| 10 | Phone-to-memory capture path | M1 integration | M-A |
| 11 | Iteration 3/4 dates, owners, final thresholds | Planning | Team |
| 12 | Whether room calibration UI lives in caregiver view | M4 portal | M-D |

---

## Recommended dependency order

1. **M1.4 artifact contracts** → unblocks everything.
2. **M1.1 live → memory** + **M1.2 gaps/pause** → makes ingestion real.
3. **M2.2 room registry integration** → cheapest high-value fix; closes FR3.6/3.7.
4. **M2.1 compaction** → largest missing block; needs decision #6/#7 first.
5. **M3.4 confidence/abstention** + **M3.5 evidence** → needed for SC5/SC6 and credible answers.
6. **M3.1 speech** + **M3.2 temporal queries** → completes the agent.
7. **M4.1–4.2 auth/security** → required before any caregiver access claim.
8. **M4.3 portal UI** + **M4.4 accessibility**.
9. **M4.5 performance** + **M4.6 benchmark** → measure, then report.
10. **M4.7 docs/diagrams** → close the loop.

---

## Definition of done (from spec §20)

- [ ] All H and M requirements implemented, or explicitly documented as deferred with a reason.
- [ ] All AC-01 to AC-31 executed with results recorded; misses reported honestly.
- [ ] SC1–SC9 measured on the selected benchmark and reported as proposed targets, not guarantees.
- [ ] Existing 84 tests + new capability tests pass; Ruff check/format clean.
- [ ] No unmeasured result or unimplemented feature presented as complete.

---

## Non-negotiable invariants while doing this work

- Raw VGGT-Ω coordinates remain the spatial source of truth; never reintroduce scale/axis permutations.
- Rooms come from trajectory clustering + sparse landmarks, never dense clouds.
- Room-defining landmarks are context only and never become object memories.
- Object permanence and multi-instance identity must not regress.
- Safe failure over fabrication: no evidence → explicit uncertainty.
- Keep the batch path and live path contracts separate but connected through M1.1, not merged implicitly.
