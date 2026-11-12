# Aegis — Answers: retention budget, elevation, vocabulary

Written 2026-11-12 against `develop` @ `940a09e`. File references are to the current tree.
Numbers in §1 are **estimates from stated assumptions**, except where marked *measured*. They must be replaced by measurements before they go into the report.

---

## 1. Three days of detail, then text — without overshooting memory

### 1.1 Why the current design cannot do it

Three things grow without bound today, and none of them is the information a query needs.

| What grows | Where | Size |
|---|---|---|
| Timeline: one entry per instance per keyframe, including objects that are out of view | `scene_graph.py:780-889` | *Measured* on the `demo04` fixture: 268 entries, 294 KB for 46 s → ≈ 1.1 KB per entry, ≈ 6.3 KB per second of video |
| Pointmaps: every keyframe of a session in one array, all loaded in RAM | `workers.py:240-245`, `:347-349` | 518 × 518 × 16 bytes ≈ 4.3 MB per keyframe |
| Frames: live JPEGs re-encoded as PNG on promotion | `live_handoff.py:152-154` | ≈ 0.9 MB per frame instead of ≈ 80 KB |

The graph is also written three times per run (`r4d_scene_graph.json` plus two copies inside `spatial_memory_graph.json`), and the API loads the whole file into a Python dict, which costs several times the file size in RAM.

Projected to one day of 12 hours of wear, 0.5 keyframes per second after keyframe selection, VGGT stride 6 (3,600 reconstructed keyframes per day):

| Item, current design | Per day | Three days |
|---|---|---|
| Timeline JSON, 30 tracked objects | ≈ 119 MB | ≈ 356 MB (before the 3× duplication) |
| Pointmaps, if kept | ≈ 15.5 GB | ≈ 46 GB |
| Promoted PNG frames | ≈ 19 GB | — (must be purged at 24 h) |

The timeline is O(time × objects). That is linear in recording time, so FR4.4 (sub-linear growth) cannot be met by compressing it afterwards. The laptops have 8 GB RAM and about 100 GB of disk, so this fails within the first day.

There are two further blockers that are not about size:

- Memory is rebuilt per session and instance IDs restart at 1, so there is no multi-day store to retain or compact.
- Timestamps in the graph are seconds from session start, so "older than three days" cannot be evaluated.

### 1.2 The idea: store changes, not frames

An object that sits on a shelf for six hours is one fact, not 10,000 entries. Almost all of the saving comes from this, and it loses nothing a query can ask for.

**Hot tier (0–3 days), structured, in one SQLite file per home**

| Table | One row is | Key columns |
|---|---|---|
| `instance` | A persistent object | id, canonical label, display name, embedding, importance, **last-known state** |
| `state_run` | One stable placement of one object | instance, anchor, relation, room, start/end wall-clock time, observation count, mean position, height above floor, confidence, evidence crop id |
| `event` | A transition between runs, or a room change | type, instance, from/to anchor and room, time, evidence |
| `room_visit` | The wearer's stay in one room | room, start/end time |
| `anchor`, `room` | Stable structure | label, room, extent |
| `evidence` | One small crop per run | path, time, source frame |

A re-sighting of an object in the same place updates `end_time` and `observation_count` on the existing run; it does not add a row. Rows are created only when something changes.

**Warm tier (older than 3 days), text**

A background job (nightly, or when the device is idle — never on the query path) takes runs and events older than the window and writes:

- one line per object per day: *"Keys: last on the hallway table in the Entryway at 18:42; moved 4 times; also seen in Kitchen."*
- one line per activity block (room visit with its interactions): *"09:10–09:40 Kitchen: took Mug #2 from Cupboard #1, placed it on Kitchen Counter #1."*
- a small structured sidecar per line: instance id, anchor id, room id, event types, last-seen time. This is what satisfies FR4.2 and lets tests check room-label survival mechanically.

It then deletes the geometry (positions, boxes, crops) for those days. That is the report's "spatial observations converted into text".

Summaries should be produced by templates from the structured rows, not by a language model. Templates are deterministic, cannot invent a location, and can be unit-tested. A language model can be offered later for phrasing only.

### 1.3 Ideas that keep it bounded

1. **Last-known state is never compacted.** It lives on the `instance` row, which is constant size. This directly answers the report's own failure example (compaction dropping the shelf an object last rested on): only *history* is condensed, never the current answer to "where is X".
2. **Run-length storage at ingest** (above). This is the largest factor.
3. **Importance-aware retention.** The vocabulary marks items such as medication, keys, glasses, wallet, phone as high importance; their runs stay in the hot tier longer (for example 7 days) and their summaries keep every move rather than a count.
4. **Hierarchical roll-up.** A fixed-size daily summary is still linear in time, with a small constant. To be genuinely sub-linear, roll daily summaries into weekly ones after 30 days and weekly into monthly after a year, and write "unchanged" instead of repeating a location.
5. **One evidence crop per run**, about 320 px, replaced only by a sharper one. Not one per sighting.
6. **Transient artifacts are deleted by the stage that consumed them.** Pointmaps after lifting; the dense point cloud after rooms and gravity are estimated (keep a low-resolution copy only if Rerun needs it).
7. **Windowed reconstruction.** Run VGGT on overlapping windows of keyframes instead of the whole session, so GPU and RAM use are constant per window. The window size that fits an L4 must be measured.
8. **Keep cross-session memory symbolic.** Each session has its own world origin (`vggt_runner.py:177-194`). Matching a new session onto stored rooms and anchors by type and neighbourhood, and storing room/anchor/relation rather than coordinates, avoids needing a global metric map. Coordinates stay session-local and are dropped at compaction anyway.
9. **JPEG frames end to end**, with the 24-hour purge the report already requires (NFR-S4).
10. **Encrypted SQLite** gives AES-256 at rest for the same file, which closes NFR-S1 and decisions #5 and #6 together.

### 1.4 Predicted storage

Assumptions: 12 hours of wear per day; 2 FPS sampling; keyframe selection keeps 0.5–2 frames per second; 80 KB per 960×540 JPEG; about 1,000 state changes per day (roughly 300–500 object interactions); 50–200 distinct objects in the home. Halve or third the per-day figures for 6 or 4 hours of wear.

| Component | Per day | Steady state | Grows with time? |
|---|---|---|---|
| State runs (≈ 200 B each) | ≈ 0.2 MB | ≈ 0.6 MB (3 days) | No — windowed |
| Events (≈ 250 B each) | ≈ 0.25 MB | ≈ 0.75 MB | No — windowed |
| Room visits, optional trajectory | ≈ 0.02–0.35 MB | ≈ 1 MB | No — windowed |
| Evidence crops (≈ 15 KB each) | ≈ 15 MB | ≈ 45 MB | No — windowed |
| Instances with embeddings, anchors, rooms, home map, vocabulary | — | ≈ 0.5 MB | Only with new objects |
| **Hot tier total** | ≈ 16 MB | **≈ 50 MB** | **No** |
| Text summaries with sidecar | ≈ 20 KB | ≈ 7 MB per year; ≈ 1 MB in year one with weekly/monthly roll-up, then ≈ 0.1 MB per year | Yes, slowly |
| Raw frames, 24-hour rolling window (JPEG) | 1.7–6.9 GB | 1.7–6.9 GB | No — purged |
| Reconstruction window in flight (64 keyframes) | — | ≈ 0.3 GB, then deleted | No |

**Prediction:** persistent memory stays near **50 MB** however long the system runs, plus well under 10 MB per year of summaries. Peak disk use is **2–7 GB**, almost all of it the 24-hour raw-frame window. API process memory should be tens of megabytes, because queries read `instance.last_known_state` and indexed runs instead of parsing a timeline.

For comparison, the current design projects to roughly 120 MB per day of timeline JSON alone at the same assumptions.

### 1.5 What must be measured before this is claimed

- Actual keyframes per hour and JPEG size on the phone used for capture.
- State changes per hour in a real session (the 1,000 per day figure is the weakest assumption).
- Store size after 1, 2, 3, 5 and 7 simulated days, to plot the growth curve required by AC-07. A replayed or synthetic event stream is enough for the curve; it does not need seven days of video.
- Query accuracy on the same question set before and after compaction (AC-08, target drop ≤ 15 points).
- Largest VGGT window that fits the L4, and pipeline throughput relative to real time.

---

## 2. Elevation: shoes above or below the bed

### 2.1 Root causes

The system has no way to represent "under", and the geometry it would need is not there. Five separate causes, all confirmed in source:

1. **No gravity direction.** The world frame is the first camera's frame. `rooms.py:27` and `workers.py:904` assume "up is −Y". A phone held in the hand or tilted down at shoes — which is how the demo starts — makes world Y point somewhere between down and forward. Height computed along Y then mixes vertical and horizontal distance.
2. **The oriented box uses a different axis convention from the rest of the code.** `lifting.py:139-177` fits yaw in the X–Y plane and treats Z as height. That was correct in the removed Z-up frame. So the box "height" is depth along the camera's forward axis.
3. **There are no vertical relations.** The relation set is `inside`, `on_surface`, `on_floor`, `carried_by_user`, `moving_towards`. For anything that is not a shoe, being within 0.35 of an anchor's centre yields `on_surface` or `inside` (`scene_graph.py:706-711`), regardless of whether the object is above or below. `on_floor` is only reachable through a shoe-specific rule tied to frame numbers.
4. **Anchor choice ignores direction.** `_anchor_for_box` picks the nearest anchor centre by straight-line distance, and the relation is derived from that distance alone.
5. **A bed cannot be an anchor.** `bed`, `sofa` and `dining table` are room landmarks (`rooms.py:32-36`), so they are filtered out before anchors are extracted. "Shoes … bed" can never be produced; the shoes attach to whatever anchor is nearest, or to the fabricated `Storage Cabinet #1` at the origin when none exists.

### 2.2 Solution

**Step 1 — Estimate the up vector and floor height per session.** Store them next to the poses (`up_vector`, `floor_offset`, `source`, `confidence`). Coordinates are not rotated, so the raw-VGGT invariant holds; height is a derived quantity:

```
height(p) = dot(p, up) − floor_offset
```

Sources for `up`, in order of preference:

| Source | How | Notes |
|---|---|---|
| Phone accelerometer | Gravity in the camera frame, rotated by each pose, robustly averaged | Most reliable. Needs the capture app to expose sensor readings alongside the stream — check what the app in `docs/live_capture.md` offers |
| Floor plane fit | RANSAC plane on the fused point cloud, restricted to points below the camera path, with the normal pointing toward the cameras. Adding `floor` to the detector prompts and fitting only floor-mask points makes this robust | Works for batch videos and needs no new hardware. Recommended first implementation |
| Camera path | A walking wearer's camera positions lie close to a horizontal plane; its normal is a cross-check | Weak when the wearer stands still |
| Single-image gravity estimator | A learned per-frame gravity prediction averaged over keyframes | Fallback when little floor is visible |

Use the floor fit, validate it against the camera-path normal, and abstain from vertical relations when they disagree by more than a set angle.

**Step 2 — Fix the frame convention everywhere.** Fit oriented boxes in the plane perpendicular to `up` (replacing the X–Y assumption in `lifting.py`), and project room footprints onto that plane instead of assuming (X, Z).

**Step 3 — Give each object and anchor a vertical extent and a footprint.** From the masked points: `bottom` and `top` as the 5th and 95th percentile of height, and a footprint polygon in the horizontal plane. For furniture, also fit the **support surface**: the dominant horizontal plane among its points (mattress top, table top).

**Step 4 — Classify from footprint overlap and vertical order.** With `overlap` = share of the object's footprint that lies over the anchor's footprint, and a tolerance `tol` proportional to the anchor's height (not a fixed metre value, because scale is not calibrated):

| Condition | Relation | Spoken as |
|---|---|---|
| overlap high, object bottom ≈ anchor support surface | `on` | "on the bed" |
| overlap high, object top below the support surface by more than `tol`, anchor has open space beneath (bed, table, desk, chair, sofa) | `under` | "under the bed" |
| overlap high, object within the anchor's vertical span, anchor is a container | `inside` | "inside the cabinet" |
| overlap high, object bottom above anchor top by more than `tol` | `above` | "on the shelf above the desk" |
| overlap low, small horizontal gap, object bottom ≈ floor | `on_floor` + `next_to` | "on the floor beside the bed" |
| overlap low, small horizontal gap | `next_to` | "next to the bed" |

"Under" and "on the floor beside" differ only in footprint overlap, which is why the horizontal plane must be correct first.

**Step 5 — Let furniture be an anchor.** Keep `bed`, `sofa`, `dining table` as room-typing landmarks *and* register them as anchors. The invariant is that landmarks never become personal-object memories; an anchor is not an object memory.

**Step 6 — Handle the uncertain middle.** When the vertical margin is smaller than `tol`, or the gravity confidence is low, do not guess. Either answer with the weaker relation ("near the bed") or, once a VLM is available, ask it one closed question about the evidence crop ("on top of, or underneath?") and cache the answer on the state run. Either way the confidence score drops.

**Step 7 — Carry it through.** Add `height_above_floor` and the new relations to the state run, the API response and the answer templates in `reasoning.py`; add them to the event types so "moved from under the bed to the shelf" is a transition.

### 2.3 Tests that prove it

- A synthetic scene whose first camera is pitched 40° downward, with one pair of shoes on a bed and one under it. Today both come out as the same relation; after the change they must come out as `on` and `under`.
- The same scene with the shoes on the floor beside the bed → `on_floor` / `next_to`.
- Up-vector estimation recovers a known tilt within a few degrees on a synthetic point cloud, and reports low confidence when no floor is present.
- A recorded clip with five objects at known heights, reported as part of AC-04.

### 2.4 Scale

Tolerances relative to anchor size avoid needing metres. If metric height is wanted for answers ("on the top shelf, about chest height"), estimate one scale factor per session — from the camera's height above the fitted floor during walking, or by comparing against a metric depth model on a few keyframes — and store it as metadata. Do not multiply it into the coordinates.

---

## 3. Vocabulary list

### 3.1 Why it is required

The detector is open-vocabulary, but it only finds what it is prompted for. `perception.target_classes` in `config/demo.yaml` is that prompt, and today it is written by hand for one demo (shoes, cabinet, shelf, hand, plus room landmarks). Consequences:

- **Anything not on the list is never detected, so it is never remembered.** A user asking for their glasses in a home recorded with the shoe config gets "not found" forever. The vocabulary is the upper bound on what memory can contain.
- **The list decides roles.** Whether a label is a personal object, an anchor, a container, a surface, a room landmark or a hand is currently decided by six separate hard-coded lists: the config, `ANCHOR_CLASS_NAMES`, `ROOM_LANDMARK_ROOM_TYPES`, `CONTAINER_LABELS`, the size filters in `lifting.py`, and `ITEM_SYNONYMS`. They already disagree (for example `table` groups under `desk`; `cup` and `mug` resolve to `bottle`).
- **Labels are normalised in three places** (`scene_graph._normalise_label`, `detector._canonical_label`, `workers._memory_label_key`), so the same object can carry different names in different stages.
- **Queries need the reverse mapping.** "Spectacles", "specs", "reading glasses" must reach the same stored label. That is a vocabulary problem too.
- **Evaluation needs it.** Spatial accuracy on a benchmark is capped by vocabulary coverage of the benchmark's objects, so coverage has to be reported alongside accuracy.
- **Later features hang off it.** Importance for retention (§1.3), "has space underneath" for vertical relations (§2.2), plural grammar for answers, and Urdu aliases if that extension happens.

### 3.2 Ways to build it

| Approach | What it is | Strength | Weakness |
|---|---|---|---|
| A. Curated ontology file | One versioned YAML: canonical label, detector prompts, synonyms, role, properties | Deterministic, testable, removes the six lists | Only covers what the team thought of |
| B. Per-home discovery | During the caregiver's room-calibration walkthrough, run an image-tagging model or VLM on the keyframes, propose the objects present, caregiver confirms in the app | Fits this home; reuses the UC-13 flow | Needs the calibration screen; one extra model pass |
| C. Prompt-free detection | Use the detector's built-in large vocabulary mode instead of text prompts | No list to maintain | Many irrelevant classes, more false positives, labels still need mapping to roles; verify availability and speed for the YOLOE weights in use |
| D. Query-driven expansion | When a query names something unknown, add it and re-run detection on frames still inside the 24-hour window | Recovers from gaps | Only works within raw-frame retention; costs GPU time |
| E. Embedding matching | Store an image-text embedding per instance; match queries by similarity rather than by label string | Handles unseen words and descriptions ("the blue mug") | Similarity thresholds need tuning; weaker guarantees for abstention |
| F. Personal items by example | Caregiver photographs specific items (pill box, hearing-aid case); detector is prompted with the images | Best for the few items that matter most | Manual step per item |

### 3.3 Recommended approach

Use A as the foundation, B to fit each home, and E only as a fallback for query matching.

1. **Create `config/vocabulary.yaml` as the single source of truth** and delete the scattered lists. One entry:

   ```yaml
   - id: glasses
     prompts: [glasses, eyeglasses, spectacles]     # sent to the detector
     synonyms: [specs, reading glasses, sunglasses]  # accepted in queries
     role: object            # object | anchor | room_landmark | hand
     plural: true
     importance: high        # drives retention
     max_extent: 0.3         # relative size sanity bound
   - id: bed
     prompts: [bed]
     role: anchor
     room_type: Bedroom      # also votes for room typing
     support_surface: true
     open_underneath: true   # enables the "under" relation
     container: false
   ```

2. **Seed it from three sources:** items people with memory problems commonly misplace (keys, glasses, phone, wallet, remote control, medication, hearing aids, walking stick, purse, watch, charger); household furniture and containers for anchors; and the object classes that appear in the chosen benchmark. Aim for roughly 60–120 detector prompts — measure detection quality as the list grows, because open-vocabulary detectors lose precision with long, overlapping prompt lists.

3. **Generate everything else from the file:** the detector class list, the anchor/landmark/container sets, the label normaliser, and the query synonym table. A unit test asserts that every prompt maps to exactly one canonical id and one role.

4. **Add a per-home overlay** (`home_vocabulary.json` next to `home_map.json`) filled during calibration (approach B): objects present in this home, caregiver-given names ("Mum's blue mug"), and any personal items registered by photo (approach F).

5. **Match queries in two steps:** exact canonical/synonym lookup first; if that fails, embedding similarity against the labels and stored instance embeddings, accepted only above a threshold and answered with lower confidence. Below the threshold, say the item is not known and offer the closest known items — do not guess.

6. **Report coverage:** for the benchmark, the share of queried objects that are in the vocabulary, and per-class detection recall. A low accuracy figure can then be attributed to the right stage.

### 3.4 What to decide

- Whether prompt-free detection (C) is good enough on your own footage to replace the curated prompts — a one-afternoon comparison on the existing demos will show it.
- How many prompts the detector tolerates before precision drops on the L4 at your frame size.
- Whether personal-item registration (F) is in scope for FYP-2 or listed as future work.
