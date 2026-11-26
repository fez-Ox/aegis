# FYP-1 Final Report: Diagram Specifications

This file tells Claude (or a team member) exactly what to draw for every figure in the FYP-1 final report. Every element named here was taken from the code on `develop` at `ce49dcc` (24 Nov 2026) or from the mid report.

Where a value is **unknown**, the spec says so and gives the command or person to get it from. Nothing in a diagram may be invented.

**Related files:**
- `REPORT_STRUCTURE.md`: where each figure sits in the report.
- `MID_REPORT_ERRATA.md`: what was wrong with the mid-report figures.
- `NEW_CONTENT.md`: the prose that explains each figure.

---

## 0. Global drawing rules (apply to every figure)

### 0.1 Tool and export

| Item | Rule |
|---|---|
| Tool | The **Tool** column of the figure index (§1) is binding. **draw.io** for structural diagrams (context, modules, pipeline, architecture, component, deployment, DFD, use case, screen flows, test pyramid): most polished and editable, matches the mid style. **PlantUML** for behaviour and code diagrams (sequence, state, activity/flowchart, class): exact UML notation, regenerated from text. **Mermaid** for Gantt charts, the git branch graph and the ERD. **matplotlib** for every result chart, reading the real numbers from a data file. No Canva or AI-generated images in the report body. Keep the source next to the PNG in `fyp1FinalReport/ThesisFigs/src/<file>.drawio` / `.puml` / `.mmd` / `.py` |
| Format | **PNG only.** `\aegisfig` loads `ThesisFigs/<name>.png` and shows a "Missing figure" box for anything else |
| Rendering | draw.io: File → Export → PNG, zoom 300%, border 20, transparent off (or `drawio -x -f png -s 3`). PlantUML: `java -jar plantuml.jar -tpng -Sdpi=300 <file>.puml`. Mermaid: `npx -y @mermaid-js/mermaid-cli -i <file>.mmd -o <file>.png -s 3 -b white`. matplotlib: `savefig(dpi=300, facecolor="white")` |
| Resolution | ≥ 2400 px on the long side (the report scales to text width; the mid figures were 2400–5200 px) |
| Background | **Opaque white.** Several mid figures had transparent backgrounds that turn black in dark PDF viewers (errata D17) |
| Embedded titles | **None.** No "Figure 5.x", "(a)", "(b) Frame 1" inside the image (errata A10). Captions come from LaTeX only |
| Fonts | One sans-serif family (Inter, Helvetica or Arial). Element names 14–18 pt at final size; labels ≥ 10 pt at final size. Code identifiers in a monospace face (JetBrains Mono / Consolas) |
| Aspect | Landscape ≤ 16:10 for most figures. The page allows width 15.9 cm × height 0.55 × text height (`\aegisfig` caps height at `0.55\textheight`); very tall figures shrink and become unreadable |
| Legend | Every figure with more than one line style or colour has a legend box at the bottom, as in the mid figures |
| Line crossings | No connector may pass **through** another element (errata D2, D3). Route around |
| Labels | Every arrow carries a label: data name, message or protocol. No floating labels without an arrow (errata D9) |
| Spelling of identifiers | Copy class, method, route, table and column names **exactly** from the code (backticked names in this file are exact) |

### 0.2 Implemented vs planned

| Style | Meaning |
|---|---|
| Solid outline, solid line | Implemented on `develop` and covered by a test |
| Solid outline + small grey tag **"partial"** | Implemented slice; the text says what is missing |
| **Dashed** outline, dashed line, grey text | Planned / not implemented |
| Red bar or red outline | Known risk / security gap (for example an unauthenticated mutating route) |

State this convention once in the first paragraph of Chapter 5. Repeat the legend on each figure.

### 0.3 Colour palette (keep the mid report's module colours, now named in every legend)

| Module | Fill | Border |
|---|---|---|
| M-A Capture & Ingestion | `#DCE9F7` | `#2F6DB5` |
| M-B Spatio-Temporal Memory | `#DFF0E3` | `#2E8B57` |
| M-C Query / Cognitive Agent | `#FCE8D0` | `#D9822B` |
| M-D Interfaces & Caregiver Access | `#E9DFF2` | `#7B4BA8` |
| Infrastructure / external / neutral | `#F1F3F5` | `#6B7785` |
| Risk / gap | `#F8D7DA` | `#C0392B` |

### 0.4 File naming

`ch<N>-<short-name>.png`: lowercase, hyphens only, no spaces, brackets or double dots. The IDs below (`F5.3` etc.) are guide IDs; LaTeX numbers the figures.

---

## 1. Figure index

| ID | File | Chapter § | Type | Status vs mid | Tool |
|---|---|---|---|---|---|
| F1.1 | `fig-1.1.png` | 1.3 | Conceptual loop | KEEP | — (reuse existing PNG) |
| F1.2 | `ch1-system-context.png` | 1.6 | System context | REDRAW | draw.io |
| F1.3 | `ch1-modules.png` | 1.7 | Module block diagram | REDRAW | draw.io |
| F2.1 | `ch2-pipeline.png` | 2.5 | Pipeline (write/read path) | REDRAW | draw.io |
| F2.2 | `fig-2.2.png` | 2.5 | Gap positioning chart | KEEP | — (reuse existing PNG) |
| F2.3 | `ch2-detector-ab.png` | 2.9 (new) | Grouped bar chart | NEW | matplotlib |
| F3.1 | `ch3-gantt-plan-vs-actual.png` | 3.9 | Gantt (plan vs actual) | REDRAW (was not a Gantt) | Mermaid (gantt) |
| F3.2 | `iterationcycle.png` | 3.5 | Cycle | KEEP | — (reuse existing PNG) |
| F4.1 | `ch4-use-case.png` | 4.2 | UML use case | REDRAW | draw.io |
| F5.1 | `ch5-layered-architecture.png` | 5.1 | Layered architecture | REDRAW | draw.io |
| F5.2 | `ch5-components.png` | 5.2 | UML component | REDRAW | draw.io |
| F5.3 | `ch5-deployment.png` | 5.2 | UML deployment | REDRAW | draw.io |
| F5.4 | `ch5-design-evolution.png` | 5.5 | Before/after architecture | NEW | draw.io |
| F5.5 | `ch5-domain-model.png` | 5.6 | UML conceptual class (domain model) | REDRAW | PlantUML (class) |
| F5.6 | `ch5-scene-graph-v2.png` | 5.7 | JSON document model | REDRAW | PlantUML (json) |
| F5.7 | `ch5-erd-home-store.png` | 5.7 | Crow's-foot ERD | NEW | Mermaid (erDiagram) |
| F5.8 | `ch5-live-session-artifacts.png` | 5.7 | Artifact/file layout | NEW | draw.io |
| F5.9 | `ch5-patient-app-flow.png` | 5.8 | Screen-flow / wireframe map | REDRAW | draw.io + screenshots |
| F5.10 | `ch5-caregiver-app-flow.png` | 5.8 | Screen-flow / wireframe map | NEW | draw.io + screenshots |
| F5.11 | `ch5-dfd-level0.png` | 5.9 | DFD level 0 | NEW | draw.io |
| F5.12 | `ch5-dfd-level1.png` | 5.9 | DFD level 1 | REDRAW | draw.io |
| F5.13 | `ch5-seq-pipeline.png` | 5.9 | UML sequence | REDRAW | PlantUML (sequence) |
| F5.14 | `ch5-seq-query.png` | 5.9 | UML sequence | REDRAW (merges two mid figures) | PlantUML (sequence) |
| F5.15 | `ch5-seq-caregiver.png` | 5.9 | UML sequence | REDRAW | PlantUML (sequence) |
| F5.16 | `ch5-seq-home-ingest.png` | 5.9 | UML sequence | NEW | PlantUML (sequence) |
| F5.17 | `ch5-state-live-session.png` | 5.9 | UML state machine | NEW | PlantUML (state) |
| F5.18 | `ch5-state-object.png` | 5.9 | UML state machine | NEW | PlantUML (state) |
| F5.19 | `ch5-activity-compaction.png` | 5.9 | UML activity | NEW | PlantUML (activity) |
| F5.20 | `ch5-activity-nlq.png` | 5.9 | UML activity | NEW | PlantUML (activity) |
| F6.1 | `ch6-class-core-models.png` | 6.3 | UML class (Iteration 1) | FIX (rename + notation) | PlantUML (class; redraw from tag `v0.2.0-mid2`) |
| F6.2 | `ch6-class-live-api.png` | 6.3 | UML class (Iteration 1) | FIX | PlantUML (class; redraw from tag `v0.2.0-mid2`) |
| F6.3 | `batchvideosamplingflowchart.png` | 6.3 | Flowchart | KEEP | — (reuse existing PNG) |
| F6.4 | `chapter6-screenshot-evidence.jpeg` | 6.8 | Screenshot | KEEP | — (reuse existing PNG) |
| F7.1 | `ch7-class-memory.png` | 7.3 | UML class (real code) | NEW | PlantUML (class) |
| F7.2 | `ch7-class-query-api-apps.png` | 7.3 | UML class (real code) | NEW | PlantUML (class) |
| F7.3 | `ch7-flow-relations.png` | 7.3 | Flowchart / activity | NEW | PlantUML (activity) |
| F7.4 | `ch7-flow-matching.png` | 7.3 | Flowchart / activity | NEW | PlantUML (activity) |
| F7.5 | `ch7-flow-keyframe.png` | 7.3 | Flowchart | NEW | PlantUML (activity) |
| F7.6 | `ch7-shot-patient-app.png` | 7.8 | Screenshots | NEW | Screenshot |
| F7.7 | `ch7-shot-caregiver-app.png` | 7.8 | Screenshots | NEW | Screenshot |
| F7.8 | `ch7-shot-rerun.png` | 7.8 | Screenshot | NEW | Screenshot |
| F7.9 | `ch7-shot-terminal.png` | 7.8 | Screenshot | NEW | Screenshot |
| F8.1 | `ch8-test-levels.png` | 8.2 | Test pyramid | REDRAW | draw.io |
| F8.2 | `ch8-detection-chart.png` | 8.5 | Grouped bar chart | NEW (or reuse F2.3) | matplotlib |
| F8.3 | `ch8-compaction-ratio.png` | 8.6 | Bar chart | NEW | matplotlib |
| F8.4 | `ch8-storage-projection.png` | 8.6 | Line chart | NEW | matplotlib |
| F8.5 | `ch8-e2e-timing.png` | 8.7 | Horizontal bar | NEW | matplotlib |
| F8.6 | `ch8-egolife.png` | 8.8 | Bar/line chart | NEW (data from Faizan) | matplotlib |
| F9.1 | `ch9-commit-timeline.png` | 9.6 | Stacked weekly bar chart | REDRAW | matplotlib |
| F9.2 | `ch9-branch-graph.png` | 9.5 | Git branch graph | NEW | Mermaid (gitGraph) |
| F10.1 | `ch10-fyp2-gantt.png` | 10.7 | Gantt | NEW | Mermaid (gantt) |

---

## 2. Chapter 1 figures

### F1.1 Recall loop (KEEP `fig-1.1.png`)

No change. It is conceptual and still correct.

### F1.2 System context diagram (`ch1-system-context.png`)

**Purpose:** fix the system boundary of Aegis *as built* at the end of FYP-1.
**Notation:** context DFD style, matching the mid figure: one rounded system box, external entities as grey rectangles, labelled data-flow arrows.
**Layout:** Aegis in the centre; users left and right; devices top; cloud and model services bottom.

**System box (centre, thick border):** **"Aegis — egocentric spatio-temporal memory system"**. Sub-label: "pipeline + memory + query API".

**External entities:**

| Entity | Position | Style | Note inside box |
|---|---|---|---|
| Primary user | left | solid | "person with cognitive impairment; uses Patient App" |
| Caregiver | right | solid | "uses Caregiver App" (do **not** say "authenticated"; errata B18) |
| Phone camera (IP Webcam app) | top-left | solid | "first-person RGB, MJPEG over Wi-Fi" |
| Indoor environment | top-right | dashed | "includes bystanders" (keep dotted "light from scene" arrow to the camera, as in mid) |
| Modal cloud (GPU/CPU + volume) | bottom-left | solid | "L4 GPU, CPU workers, `aegis-poc-data` volume" |
| Hugging Face Hub | bottom-centre | solid | "model weights: VGGT-Ω, SAM 2, SAM3, DINOv3" |
| Android speech recogniser | bottom-right | solid | "on-device speech-to-text (via `speech_to_text`)" |

**Data flows (each a labelled arrow):**
1. Phone camera → Aegis: "MJPEG video frames".
2. Primary user → Aegis: "spoken or typed question; object-tile tap".
3. Aegis → Primary user: "short answer + place + time + evidence photo, or 'not sure'".
4. Caregiver → Aegis: "questions; room names; enrolled personal items; capture pause/resume".
5. Aegis → Caregiver: "answers with candidates, timeline, rooms, capture status".
6. Aegis ↔ Modal cloud: "frames + config ⟶ / ⟵ poses, 3D boxes, scene graph" (two arrows, not one bidirectional).
7. Hugging Face Hub → Aegis (Modal workers): "pretrained weights (download once, cached at `/models`)".
8. Primary user ↔ Android speech recogniser: "speech ⟶ / ⟵ transcribed text" (inside the phone; draw a small dashed group "Patient's phone" around the Patient App side if space allows).

**Planned (dashed):** a dashed entity "Identity / consent service (planned, FYP-2)" next to the Caregiver, with a dashed arrow "credentials, grants (planned)".

**Legend:** external entity; system; data flow; dotted = physical influence; dashed = planned.

**Verify against:** `CONTEXT.md` §2, `src/aegis/remote/modal_app.py` (volumes, GPU), `src/aegis/geometry/vggt_runner.py` (`CHECKPOINT_FILENAME`, `FALLBACK_REPO`), `apps/*/pubspec.yaml` (`speech_to_text`).

### F1.3 Module overview (`ch1-modules.png`)

**Notation:** block diagram; four module blocks left→right plus a shared store underneath.

| Block | Colour | Title | Lines inside |
|---|---|---|---|
| M-A | blue | Capture & Ingestion | FR1, FR2 · `aegis-ingest`, keyframes, gaps, pause, segments · Lead: Shahmeer |
| M-B | green | Spatio-Temporal Memory | FR3, FR4 · gravity, relations, state runs, rooms, home store, compaction · Lead: Faizan |
| M-C | orange | Query Engine | FR5, FR6 · NLQ closed vocabulary, ranking, abstention · Lead: Ali Sher |
| M-D | purple | Interfaces & Caregiver Access | FR7, FR8 · Patient App, Caregiver App, API routes · Lead: Shahmeer |

**Shared store (cylinder under M-B/M-C):** "Memory: `r4d_scene_graph.json` (per session) + `memory.db` (per home)".

**Arrows:**
- M-A → M-B: "keyframes + timestamps".
- M-B → store: "writes".
- store → M-C: "reads".
- M-C → M-D: "answers".
- M-D → M-C: "questions".

**Note box (bottom right):** "Leads are responsibility assignments; Iteration 2 work by member is in Ch 9." The actual Iteration 2 work crossed modules: Ali Sher built the apps (M-D), and Shahmeer the memory store (M-B). Use the leads from the final Chapter 3 table, which the team must confirm.

**Verify against:** the final Table 3.x responsibilities (`NEW_CONTENT.md` Ch 3).

---

## 3. Chapter 2 figures

### F2.1 Aegis pipeline (`ch2-pipeline.png`)

**Notation:** two horizontal swim bands, **WRITE PATH (continuous)** on top and **READ PATH (on demand)** below, with the shared memory store between them (same layout as the mid figure).

**Write path, left → right (solid):**
1. "Egocentric capture" (blue): FR1/FR2 · phone MJPEG → `aegis-ingest` → keyframes.
2. "3D reconstruction" (green): VGGT-Ω · poses, pointmaps · gravity frame (RANSAC floor).
3. "Perception" (green): SAM3 (default) / YOLOE · SAM 2 masks · DINOv3 re-ID · 3D oriented boxes.
4. "Memory build" (green): FR3 · relations · state runs · events · rooms.
5. "Home store + compaction" (green): FR4 · SQLite per home · 3-day detail → verified summaries.

Arrow labels: "keyframes", "poses + pointmaps + gravity", "3D boxes", "scene graph v2", "store rows".

**Store (cylinder, centre):** "Spatio-temporal memory: scene graph (session) + home store (persistent)".

**Read path, left → right:**
1. "Query input" (purple): FR6/FR7 · text, voice (on-device STT), object tile.
2. "Query engine" (orange): FR5 · `/query` ranked candidates · `/ask` NLQ · abstention.
3. "Patient access" and "Caregiver access" (purple), fanned out.

Arrow labels: "question text" → "retrieve latest states" ↔ store → "answer + evidence".

**Dashed elements:** a dashed box under "Query engine": "LLM/VLM planner (optional, off by default — planned)". A dashed arrow "temporal/activity questions (planned; currently abstain)".

**Latency badge:** "read path target p95 ≤ 5 s (SC4; not yet measured)".

**Verify against:** `CONTEXT.md` §2, `config/demo.yaml` (`detector_backend: sam3`), `config/live.yaml` (`detector_backend: yoloe`), `nlq/engine.py` (TEMPORAL/ACTIVITY abstain).

### F2.2 Gap positioning (KEEP `fig-2.2.png`)

No change.

### F2.3 Detector A/B chart (`ch2-detector-ab.png`)

**Type:** grouped bar chart (matplotlib).
**x-axis:** five detector variants. **y-axis:** score 0–1. **Bars per variant:** Precision, Recall, F1 (three colours). Annotate FP/img above each group.

**Data (exact, from `docs/detection_benchmark.md`):**

| Variant (x label) | Prompts | P | R | F1 | FP/img |
|---|---|---|---|---|---|
| YOLOE-11l generic | 93 | 0.357 | 0.056 | 0.097 | 0.9 |
| YOLOE-11l compact | 18 | 0.556 | 0.056 | 0.102 | 0.4 |
| YOLO-World m compact | 18 | 0.460 | 0.191 | 0.270 | 2.0 |
| SAM3 compact, thr 0.5 | 18 | 0.326 | 0.798 | 0.463 | 14.7 |
| SAM3 compact, class thr, NMS 0.7 (shipped) | 18 | 0.718 | 0.724 | 0.721 | 3.3 |

Highlight the shipped bar group (bold outline). Caption must say: "10 hand-labelled frames, 960×540, five environments, 116 objects; class-aware IoU ≥ 0.30; Modal L4."

---

## 4. Chapter 3 figures

### F3.1 Plan-vs-actual Gantt (`ch3-gantt-plan-vs-actual.png`)

**Type:** Gantt chart, weekly columns from **ISO week 35 (24 Aug 2026)** to the final submission week. Mark "today" with a vertical line.

**Bands:**
- Iteration 1: start → week 41 (mid-evaluation; the report says "week 9").
- Iteration 2: week 42 → submission (the report says "through week 14").

Shade each iteration band lightly. Mark milestones as diamonds:
- `v0.1.0-mid1` (4 Oct)
- `v0.2.0-mid2` (13 Oct)
- Mid report submitted (22 Oct)
- `develop` = NLQ merge (24 Nov)
- Final submission ([[date]])

**Rows** (one per work item). Planned bar = hollow outline; actual bar = filled, coloured by owner (Shahmeer blue, Faizan green, Ali orange). Planned dates are **not in the repo**: the team must fill them. Actual dates come from git:

| Row | Actual (git evidence) | Owner |
|---|---|---|
| Batch pipeline + R4DSG baseline | 1 Sep (`d82dc30`) – 4 Oct (`64d9c56`) | Faizan |
| CI/CD, API, Flutter scaffold | 4 Oct (merges `411dbb1`…`4419832`) | Faizan |
| In-hand memory + Rerun | 9–11 Oct | Faizan |
| Live MJPEG sampler | 11 Oct | Shahmeer |
| Flutter UI redesign, search history | 12 Oct | Ali Sher |
| Room hierarchy, registry, rooms API | 17 Oct (8 commits `4b20596`…`2298112`) | Faizan |
| Live capture contracts, keyframes, gaps, promotion | 6–7 Nov (`c045d9e`…`940a09e`) | Shahmeer |
| NLQ engine (first version, `NL Querying/`) | 8–9 Nov | Ali Sher |
| Evaluation suite (Options A/C/D, memory audit) | 9–10 Nov (`fb0b5a1`…`cd58d61`) | Faizan |
| M1/M2 implementation pass (gravity, relations, runs, store, rooms, activities, evidence, compaction, segments, perception) | 15 Nov (`0bfc257`…`c69cc9c`) | Shahmeer |
| Part II plan WP16–WP35 | 16 Nov (`889138f`) | Shahmeer |
| Demo harness + calibrate | 17 Nov (`92bc1d2`, `c90287e`) | Faizan |
| NLQ consolidation, `/ask`, Modal serve, `aegis-ask` | 18 Nov | Ali Sher |
| E2E runner `scripts/run_e2e.py` | 20 Nov | Ali Sher |
| EgoLife 7-day study | 21–22 Nov (`5dbc4b6`…`61dda40`) | Faizan |
| Tiered query protocol + ranking | 22 Nov (`b0a834d`) | Faizan |
| SAM3 detector + benchmark | 22 Nov (`2a3c603`) | Faizan |
| Patient App + Caregiver App, enrollment, DINOv3 | 23–24 Nov | Ali Sher |
| Planned, not started (dashed, Iteration 3+) | — | — |

Planned-not-started rows: temporal answers, calibrated confidence, auth/consent, encryption, usability study.

**Legend:** planned (outline), actual (filled), owner colours, milestone diamond, slip = red bracket between planned end and actual end.

### F3.2 Iteration cycle (KEEP `iterationcycle.png`)

No change.

---

## 5. Chapter 4 figure

### F4.1 Use case diagram (`ch4-use-case.png`)

**Notation:** UML 2.5 use case diagram.
- System boundary rectangle titled **"Aegis"**.
- Actors as stick figures outside the boundary: **Primary user** (left), **Caregiver** (right), **System clock** (bottom, «actor» timer, for compaction).
- Planned use cases drawn with a **dashed** ellipse and the stereotype «planned».
- Partial use cases are solid with a "partial" tag.
- **No association line may cross another ellipse.** Group the user's UCs on the left and the caregiver's UCs on the right, shared ones in the middle.

**Use cases (names must match Table 4.1 exactly):**

| ID | Name | Actor(s) | Status at FYP-1 end |
|---|---|---|---|
| UC-01 | Capture and ingest egocentric video | Primary user | Partial (no one-hour soak measured) |
| UC-02 | Submit a query by speech or text | Primary user, Caregiver | Implemented (on-device STT, text) |
| UC-03 | Find the last known location of an object | Primary user | Implemented |
| UC-04 | Review the history of an object | Caregiver (Primary user via tile) | Partial (timeline in Caregiver App) |
| UC-05 | Recall earlier activity | Primary user | Planned (activity intent abstains) |
| UC-06 | View evidence for an answer | Primary user, Caregiver | Implemented (crop URL / candidate photos) |
| UC-07 | Grant, scope and revoke caregiver access | Primary user | Planned |
| UC-08 | Caregiver queries episodic history | Caregiver | Partial (no auth/scope) |
| UC-09 | Caregiver verifies an object state | Caregiver | Partial (no auth) |
| UC-10 | Caregiver reviews an activity summary | Caregiver | Partial (`/activities` and store summaries exist; no app screen, no auth) |
| UC-11 | Pause capture or delete history | Primary user, Caregiver | Partial (pause/resume routes; deletion not verified) |
| UC-12 | Maintain memory by compaction | System clock | Implemented (`compact`, `rollup`) |
| UC-13 | Caregiver calibrates and names rooms | Caregiver | Implemented (no auth) |
| UC-14 | Caregiver enrolls a personal item | Caregiver | Implemented (no auth). **Add only if the team adopts UC-14** |
| UC-15 | Primary user contacts caregiver | Primary user | Implemented. **Add only if adopted** |

**Relationships:**
- UC-03 «include» UC-02.
- UC-03 «include» UC-06.
- UC-08 «include» UC-06.
- UC-09 «include» UC-06.
- Extension point "no evidence": an «extend» from a small use case **"Abstain ('not sure')"** to UC-03, condition `{item unknown or never observed}`. Keep it inside the boundary, solid.
- UC-08, UC-09, UC-10, UC-13 and UC-14 «include» UC-07 **dashed** (planned authorisation dependency). Add a note: "authorisation planned (FR8.1); routes currently unauthenticated".

**Legend:** actor; use case implemented; partial (tag); planned (dashed); «include»; «extend».

---

## 6. Chapter 5 figures

### F5.1 Layered architecture (`ch5-layered-architecture.png`)

**Notation:** five horizontal layers, top to bottom, each a coloured band with its name rotated on the left (as in the mid figure). Arrows only between adjacent layers; each arrow labelled with protocol or artifact.

**Layer 1: Capture & Ingestion (blue)**

| Box | Inside (exact names) |
|---|---|
| Phone camera | "IP Webcam app · HTTP MJPEG `/video`" |
| `OpenCVMjpegSource` | "`FrameSource.frames()` → `DecodedFrame`" |
| `ingest_live` loop | "sample at `sample_fps` 2.0 · `KeyframeSelector` · `FrameBuffer`(30) · gap/pause records · reconnect 3 s / timeout 30 s" |
| `LiveSessionWriter` | "`frame_*.jpg`, `index.jsonl`, `session.json`, `session_state.json`" |
| `promote_live_segments` | "120-frame segments → `data/<id>/` (schema v2)" |
| Batch video | "`ingest_video` / `preprocess_video` → PNG frames + `metadata.json`" |

Arrow down to Layer 2: "upload to Modal volume `aegis-poc-data` (`upload_dataset_to_modal_volume`)".

**Layer 2: 3D Processing & Perception on Modal (blue/grey band)**

| Box | Inside |
|---|---|
| `preprocess_video_remote` (CPU) | "normalise frames, metadata" |
| `Reconstructor` (L4 GPU) | "`run_vggt`: VGGT-Ω, `keyframe_stride`, `max_keyframes` 120 → `poses.json`, pointmaps, `pointcloud.ply`" |
| Gravity | "`estimate_gravity`: RANSAC floor → `gravity.json` (stored beside raw coordinates)" |
| `Perception` (L4 GPU) | "`detect_and_track_objects`: SAM3 / YOLOE + SAM 2 masks + DINOv3 re-ID → `lift_detection_to_3d` (gravity-aligned OBB)" |
| CPU fallback note | "`AEGIS_GPU=cpu` runs the same stages on CPU" |

Arrow down: "3D boxes + gravity + poses".

**Layer 3: Memory (green)**

| Box | Inside |
|---|---|
| Session graph builder | "`build_relative_4d_scene_graph`: anchors, `associate_instances`, `classify_relation`, `build_state_runs`, `build_events`, `extract_room_regions` → `r4d_scene_graph.json` (schema v2)" |
| Home store | "`ingest_session` → `HomeStore` (SQLite `memory.db`): `match_rooms` / `match_anchors` / `match_instances`, activities, evidence crops" |
| Retention | "`compact` (3 days → verified day summaries) · `rollup` (week/month)" |
| Registry | "`home_map.json` (caregiver room names)" |
| Personal items | "`enroll` / `resolve_alias` (`meta.personal_items`)" |

Cylinders: `r4d_scene_graph.json` (on volume), `memory.db` (laptop, `outputs/_homes/<home_id>/`).

Arrow down: "graph / store rows via `MemoryRepository`".

**Layer 4: Query Service (orange)**

| Box | Inside |
|---|---|
| FastAPI `api.py` | "`/api/v1/*` 20 routes; `resolve_repository` → `JsonGraphRepository` or `StoreRepository`" |
| Ranked lookup | "`/query`: `rank_candidates` (recency, interaction, displacement, personal, cue) + `QueryReasoningEngine` wording; top-3 candidates, ambiguity" |
| NLQ | "`/ask`: `AnswerEngine` + `DictionaryIndex` (525 items); abstains when unknown / not observed / temporal / activity" |
| Deploy | "`serve.py`: Modal CPU ASGI app `aegis-memory-api`" |
| Red bar on the right edge | "CORS `*`; no auth on mutating routes" |

Arrow down: "HTTPS JSON".

**Layer 5: Presentation (purple)**

| Box | Inside |
|---|---|
| Patient App (Flutter) | "tiles, voice (on-device STT), answer drawer, call caregiver" |
| Caregiver App (Flutter) | "search, Home/Track/Interior/Status tabs, history, enroll, rename" |
| `aegis-ask` CLI | "terminal, http or local transport" |
| Rerun | "offline 3D memory recording (`run_rerun`)" |

**Dashed (planned) boxes:**
- Layer 4: "Optional LLM planner (P1.9)" and "Auth / grants / audit (P1.7)".
- Layer 3: "Encryption at rest (P1.8)".

**Legend:** layer colours, solid/dashed, cylinder = artifact store, red bar = security gap.

### F5.2 Component diagram (`ch5-components.png`)

**Notation:** UML 2.5 component diagram. Components are rectangles with the component icon. Provided interfaces use **lollipops**; required interfaces use **sockets**. Join them with assembly connectors. Artifacts are «artifact» rectangles.

**Packages / groups (dashed containers):**
- "Laptop" (left)
- "Modal app `aegis-poc`" (centre)
- "Modal app `aegis-memory-api`" (centre-right)
- "Android devices" (right)

**Components:**

| Component | Package path | Provides (lollipop) | Requires (socket) |
|---|---|---|---|
| `core` | `src/aegis/core/` | `RuntimeConfig`, `Vocabulary`, `DatasetPaths`, models | — |
| `ingestion` | `src/aegis/ingestion/` | `FrameSource`, `promote_live_segments` | `core` |
| `geometry` | `src/aegis/geometry/` | `run_vggt_reconstruction`, `GravityFrame`, `lift_detection_to_3d` | `core` |
| `perception` | `src/aegis/perception/` | `detect_and_track_objects` | `core` |
| `memory` | `src/aegis/memory/` | `MemoryRepository`, `HomeStore`, `ingest_session`, `compact` | `core`, `geometry` |
| `nlq` | `src/aegis/nlq/` | `AnswerEngine.ask`, `DictionaryIndex` | `MemoryRepository` (memory view) |
| `remote.workers` | `src/aegis/remote/workers.py`, `modal_app.py` | `run_preprocess`, `run_vggt`, `run_detect_and_lift`, `run_rerun` | `ingestion`, `geometry`, `perception`, `memory`, `visualization` |
| `remote.api` | `src/aegis/remote/api.py`, `serve.py` | **HTTP API `/api/v1`** | `MemoryRepository`, `AnswerEngine` |
| `visualization` | `src/aegis/visualization/rerun_scene.py` | `run_rerun` | graph + geometry artifacts |
| `evaluation` | `src/aegis/evaluation/` | readiness/score reports | `memory`, artifacts |
| Patient App | `apps/Patient App/` | — | **HTTP API** (`/query`, `/ask`, `/health`, `/datasets`, `/scene_graph`) |
| Caregiver App | `apps/Caregiver App/` | — | **HTTP API** (adds `/rooms`, `/rooms/rename`, `/enroll`, `/timeline`, `/capture/status`) |
| `aegis-ask` CLI | `src/aegis/nlq/cli.py` | — | **HTTP API** or local graph |

**Artifacts:** `metadata.json`, `poses.json`, `gravity.json`, `pointmaps/*.npz`, `detected_objects_3d.json`, `r4d_scene_graph.json`, `r4d_timeline.json`, `memory.db`, `home_map.json`, evidence crops `*.jpg`.

Connect each artifact to its producer (dependency arrow «create») and its consumer («use»).

**Verify against:** `CONTEXT.md` §3, the code map (module → public functions), `apps/*/lib/services/api_service.dart` (endpoints listed above).

### F5.3 Deployment diagram (`ch5-deployment.png`)

**Notation:** UML 2.5 deployment: 3D node boxes with «device» / «executionEnvironment» stereotypes, artifacts inside nodes, communication paths labelled with protocols.

**Nodes:**
1. «device» **Wearer's Android phone #1**. Contains: «executionEnvironment» IP Webcam app → artifact "MJPEG stream `http://<phone-ip>:8080/video`".
2. «device» **Developer laptop** (Arch Linux / Debian, Python 3.12, uv). Contains: `aegis-ingest` (`ingestion/live_cli.py`), `run_pipeline.py`, `scripts/run_e2e.py`, optional `run_server.py` (Uvicorn :8000), `outputs/_homes/<home_id>/memory.db`, `home_map.json`, `captures/<session>/`.
3. «device» **Modal cloud**. Contains these execution environments:
   - «executionEnvironment» CPU container (`CPU_IMAGE`, Debian slim, Python 3.12): `preprocess_video_remote`, `rerun_remote`, `fetch_egolife_day`.
   - «executionEnvironment» GPU container `Reconstructor` (`VGGT_IMAGE`, CUDA 12.8.1, torch 2.7.1, **L4**, 24 GB GPU mem request, `scaledown_window=2`).
   - «executionEnvironment» GPU container `Perception` (`PERCEPTION_IMAGE`, **L4**, 16 GB GPU mem request).
   - «executionEnvironment» ASGI web endpoint `aegis-memory-api` (`SERVE_IMAGE`, CPU): `serve_memory_api` → FastAPI + NLQ.
   - «artifact» Volume `aegis-poc-data` mounted `/data`.
   - «artifact» Volume `aegis-model-cache` mounted `/models`.
   - Secret `aegis-secrets` (name only).
4. «device» **Patient's Android phone**: «executionEnvironment» Patient App APK (`aegis_patient` 0.3.0+3) + Android speech service.
5. «device» **Caregiver's Android phone**: Caregiver App APK (`aegis_caregiver` 0.3.0+3).
6. «device» **GitHub**: Actions CI (`ci.yml`: ruff, pytest `--cov-fail-under=75`, Flutter analyze/test), CD (`cd.yml`: release patient APK).
7. «device» **Hugging Face Hub**: `facebook/VGGT-Omega` (gated), fallback `wincentIsMe/VGGT-Omega`, `facebook/sam2-hiera-large`, `facebook/sam3`, `facebook/dinov3-vits16-pretrain-lvd1689m`.

**Communication paths:**

| From | To | Label |
|---|---|---|
| Phone #1 | Laptop | "HTTP MJPEG over Wi-Fi LAN" |
| Laptop | Modal | "Modal client (gRPC/HTTPS): volume upload, function calls" |
| Modal GPU | HF Hub | "HTTPS weights download (`HF_TOKEN` from `aegis-secrets`)" |
| Patient phone, Caregiver phone | `aegis-memory-api` | "HTTPS JSON (`https://…modal.run`)" |
| Patient phone, Caregiver phone | Laptop `run_server.py` | **dashed** "HTTP over LAN (cleartext allowed, development)" |
| Laptop | `memory.db` | local file. Note: "home store lives on the laptop; ingest runs after download (`_ingest_into_home`)" |
| GitHub CD | Patient phone | "release APK" |

**Red notes:**
- On the API node: "CORS `*`; no authentication on mutating routes".
- On both app nodes: "cleartext LAN permitted (`network_security_config`)".

**Dashed (planned):** "Auth service / encrypted store (FYP-2)" next to the API node.

**Verify against:** `src/aegis/remote/modal_app.py` (`_compute`, images, `WARM_SECONDS`), `src/aegis/remote/serve.py`, `run_pipeline.py` (`_ingest_into_home`), `.github/workflows/ci.yml` and `cd.yml`, `apps/Patient App/android/app/src/main/res/xml/network_security_config.xml` (and the Caregiver App equivalent).

### F5.4 Design evolution (`ch5-design-evolution.png`)

**Type:** two simplified architecture strips side by side: **"Mid report (17 Oct, `2298112`)"** left and **"FYP-1 final (`develop`)"** right. Same five layers. Changed boxes are highlighted (orange border) and numbered ①–⑨. The numbers match Table 5.x (design evolution) in `NEW_CONTENT.md`.

| # | Mid (left) | Final (right) |
|---|---|---|
| ① | YOLOE / YOLO-World + SAM 2 | SAM3 (demo) / YOLOE (live) + SAM 2 + DINOv3 re-ID |
| ② | raw VGGT coords, no up-vector | + gravity frame (`gravity.json`) |
| ③ | per-frame `timeline` (schema v1) | state runs + latest states (schema v2) |
| ④ | relations: on_surface/inside/in-hand | 9 relations in gravity frame |
| ⑤ | JSON graph only | + SQLite home store + cross-session matching |
| ⑥ | compaction planned | compaction + roll-up implemented |
| ⑦ | `QueryReasoningEngine` only | + `rank_candidates`, `/ask` NLQ engine |
| ⑧ | local FastAPI | Modal-deployed `aegis-memory-api` |
| ⑨ | single `apps/mobile` | Patient App + Caregiver App; local live sampler connected to the pipeline by promotion + segments |

### F5.5 Domain model (`ch5-domain-model.png`)

**Notation:** UML conceptual class diagram: attributes only (names + simple types), **no methods**, multiplicities on every association. Planned classes dashed with «planned».

**Classes and key attributes:**
- **Home**: `home_id`.
- **Session**: `session_id`, `started_at`, `ended_at`, `time_source {capture, recorded_at, ingest}`, `keyframe_count`, `gravity_confidence`.
- **Room**: `room_id`, `label`, `room_type`, `label_source {auto, caregiver}`, `signature`.
- **Anchor** (furniture): `anchor_id`, `canonical`, `label`, `ordinal`, `match_quality {unique, aligned, resident, ordinal, new}`.
- **ObjectInstance**: `instance_id`, `canonical`, `label`, `importance {normal, high}`, last-known state (`last_relation`, `last_anchor`, `last_room`, `last_seen_at`, `last_confidence`).
- **StateRun**: `relation`, `relation_certain`, `start_at`, `end_at`, `observation_count`, `confidence`, `height_above_floor`.
- **Relation** «enumeration»: `inside`, `on_surface`, `under`, `above`, `next_to`, `on_floor`, `near`, `in_room`, `carried_by_user`.
- **Event**: `event_type` («enumeration»: `pickup`, `placement`, `anchor_change`, `state_change`, `room_change`, `moved_while_unobserved`), `start_at`, `end_at`, `confidence`.
- **RoomVisit**: `start_at`, `end_at`.
- **Activity**: `start_at`, `end_at`, `event_count`, `summary`.
- **Evidence** (crop): `path`, `captured_at`, `frame_id`, `width`, `height`.
- **Summary**: `level {day, week, month}`, `kind {object, activity}`, `period_start`, `period_end`, `text`.
- **PersonalItem**: `alias`, `canonical_class`, `usual_anchor`, `usual_room`, `visual_crop`.
- **Landmark** (room evidence): door, stairs, television, toilet, bathtub, shower, bathroom sink, window. **Note:** "types rooms; never stored as personal objects".
- **Planned (dashed):**
  - **PrimaryUser**: name.
  - **Caregiver**: name, phone, relationship (today these exist only on-device in `PatientProfile`).
  - **AccessGrant**: scope, granted_at, revoked_at.
  - **AuditEntry**: who, what, when, result.

**Associations (with multiplicities):**

| From | To | Multiplicity | Kind |
|---|---|---|---|
| Home | Room | 1 — 0..* | composition |
| Home | Session | 1 — 0..* | composition |
| Room | Anchor | 0..1 — 0..* | "located in" |
| ObjectInstance | StateRun | 1 — 1..* | "has history" |
| StateRun | Anchor | 0..* — 0..1 | "relative to" |
| StateRun | Room | 0..* — 0..1 | "in" |
| StateRun | Relation | — | — |
| Event | ObjectInstance | 0..* — 0..1 | — |
| Event | Room / Anchor | — | "from/to" (two roles each) |
| Session | StateRun | 1 — 0..* | — |
| Session | RoomVisit | 1 — 0..* | — |
| Session | Activity | 1 — 0..* | — |
| Activity | Event | 0..1 — 0..* | groups |
| StateRun | Evidence | 0..1 — 0..1 | — |
| Summary | ObjectInstance or Activity | 0..* — 1 | "summarises" |
| PersonalItem | ObjectInstance | 0..1 — 1 | "enrolls" |
| Caregiver | AccessGrant | 1 — 0..* | dashed |
| PrimaryUser | AccessGrant | 1 — 0..* | dashed |
| AuditEntry | Caregiver | 0..* — 1 | dashed |

**Note box:** "Never compacted: ObjectInstance last-known state, Room, Anchor, Session."

**Verify against:** `src/aegis/memory/store.py` `_SCHEMA`, `memory/relations.py` `RELATIONS`, `memory/runs.py` `_event_type`, `memory/ingest.py` (`moved_while_unobserved`), `memory/personal.py` `PersonalItem`, `core/vocabulary.py` (landmarks).

### F5.6 Scene graph v2 document model (`ch5-scene-graph-v2.png`)

**Notation:** document model as in the mid figure: root box, filled-diamond composition to arrays, dashed arrows = logical references (not foreign keys).

**Root:** `r4d_scene_graph.json`, `schema_version: 2`, `dataset_id`.

**Children (field lists exact):**
- `session{}` (`scene_graph.py` l.458–467): `dataset_id`, `home_id`, `started_at`, `ended_at`, `time_source {capture, none}`, `keyframe_count`, `duration_seconds`, `first_timestamp`. The store later maps the time source to `capture | recorded_at | ingest`.
- `gravity{}`: `up[3]`, `floor_offset`, `source {floor_plane, camera_prior, assumed}`, `confidence`, `inlier_ratio`, `camera_height`.
- `anchors[]` (`SpatialAnchor.as_dict`): `anchor_id`, `label`, `canonical`, `center[3]`, `size[3]`, `observations_count`, `room_id`, `room_label`, `rotation[4]`, `yaw`, `footprint[]`, `up_min`, `up_max`, `support_up`.
- `rooms[]` (`RoomRegion.as_dict`): `room_id`, `label`, `room_type`, `centroid[3]`, `footprint[]`, `evidence_labels[]`, `keyframe_count`, `start_timestamp`, `end_timestamp`.
- `state_runs[]` (`StateRun.as_dict`): `instance_id`, `relation`, `relation_certain`, `anchor_id`, `room_id`, `start_frame`, `end_frame`, `start_time`, `end_time`, `observation_count`, `confidence`, `center[3]`, `height_above_floor`, `best_frame`, `best_bbox_2d[4]`.
- `latest_states[]`: `instance_id`, `label`, `canonical`, `relation`, `relation_certain`, `anchor_id`, `anchor_label`, `room_id`, `room_label`, `center[3]`, `size[3]`, `confidence`, `height_above_floor`, `is_active_view`, `is_in_hand`, `last_seen_timestamp`, `last_seen_wallclock`, `appearance`.
- `events[]`: `event_id`, `event_type`, `instance_id`, `object`, `source_/destination_relation`, `source_/destination_anchor`(+`_id`), `source_/destination_room`(+`_id`), `start_time`, `end_time`, `start_wallclock`, `end_wallclock`, `source_frame`, `destination_frame`, `stable_observations`, `relative_displacement`, `evidence_frames[]`, `confidence`.
- `room_visits[]` (`_room_visits()`): `room_id`, `room_label`, `start_frame`, `end_frame`, `start_time`, `end_time`, `keyframe_count`, plus wall-clock start/end when available.

**Logical references (dashed arrows):**
- `state_runs[*].anchor_id → anchors[*].anchor_id`
- `state_runs[*].room_id → rooms[*].room_id`
- `anchors[*].room_id → rooms[*].room_id`
- `latest_states[*].instance_id ↔ state_runs[*].instance_id`
- `events[*].instance_id → latest_states[*].instance_id`
- `room_visits[*].room_id → rooms[*].room_id`

**Note boxes:**
- "No per-keyframe data: size does not grow with video length."
- "Readers still accept schema 1 (`timeline{}`); `r4d_timeline.json` (per keyframe) exists only for Rerun."
- Event types note: `pickup`, `placement`, `anchor_change`, `state_change`, `room_change`.

**Companion documents** (wavy-bottom "document" shapes, as in mid): `detected_objects_3d.json` (schema 2: gravity-frame OBBs with `up_min`/`up_max`/`support_up`), `events.json` (schema 1), `spatial_memory_graph.json` (schema 2: manifest of counts and file names), `gravity.json`, `poses.json`.

**Before drawing:** generate one real v2 graph and copy its keys. The bundled `sample_outputs/*` and `tests/fixtures/*` graphs are still **schema 1**. Command: `uv run python run_pipeline.py --dataset-id <id> --stage full --download` or the test helper in `tests/test_scene_graph.py`.

### F5.7 ERD of the home store (`ch5-erd-home-store.png`)

**Notation:** crow's-foot ERD. Every table is a box: name header; columns with type; **PK** bold; **FK** italic with arrow. Include CHECK enums in brackets. Source: `src/aegis/memory/store.py` `_SCHEMA` (lines 31–175). Use the column lists below **verbatim**.

- **meta**: `key` TEXT **PK**, `value` TEXT. Note: "holds `schema_version`, `personal_items` JSON".
- **room**: `room_id` INTEGER **PK**, `label` TEXT, `room_type` TEXT, `label_source` TEXT [auto|caregiver], `signature` TEXT, `session_count` INTEGER, `last_seen_session` TEXT, `created_at` TEXT, `updated_at` TEXT.
- **session**: `session_id` TEXT **PK**, `started_at`, `ended_at`, `time_source` [capture|recorded_at|ingest], `ingested_at`, `graph_sha256`, `keyframe_count` INTEGER, `gravity_confidence` REAL, *`last_wearer_room_id`* → room.
- **anchor**: `anchor_id` **PK**, `canonical`, `label`, `ordinal` INTEGER, *`room_id`* → room, `home_x` REAL, `home_y` REAL, `match_quality` [unique|aligned|resident|ordinal|new], `observations` INTEGER, `last_seen_session`. UNIQUE(`canonical`, `ordinal`).
- **instance**: `instance_id` **PK**, `canonical`, `label`, `importance`, `appearance`, `created_at`, `observation_count`, `last_relation`, `last_relation_certain`, *`last_anchor_id`* → anchor, *`last_room_id`* → room, `last_seen_at`, `last_confidence`, `last_height`, `last_run_id`, `last_session_id`, `last_evidence_id`.
- **state_run**: `run_id` **PK**, *`instance_id`* → instance (NOT NULL), *`session_id`* → session (NOT NULL), `relation`, `relation_certain`, *`anchor_id`* → anchor, *`room_id`* → room, `start_at`, `end_at`, `observation_count`, `confidence`, `height_above_floor`, `center_x`, `center_y`, `center_z`, `evidence_id`. Indexes: (`instance_id`, `end_at`), (`end_at`), (`session_id`).
- **event**: `event_id` **PK**, *`session_id`* → session, `event_type`, *`instance_id`* → instance, `from_relation`, `to_relation`, `from_anchor_id`, `to_anchor_id`, `from_room_id`, `to_room_id`, `start_at`, `end_at`, `confidence`, `activity_id`, `evidence_id`. Indexes: `end_at`, `session_id`.
- **room_visit**: `visit_id` **PK**, *`session_id`* → session, *`room_id`* → room, `start_at`, `end_at`.
- **activity**: `activity_id` **PK**, *`session_id`* → session, *`room_id`* → room, `start_at`, `end_at`, `event_count`, `summary`.
- **evidence**: `evidence_id` **PK**, *`session_id`* → session, *`instance_id`* → instance, `path`, `captured_at`, `frame_id`, `width`, `height`, `bytes`.
- **summary**: `summary_id` **PK**, `level` [day|week|month], `period_start`, `period_end`, `kind` [object|activity], `subject_key`, `text`, `sidecar` (JSON), `created_at`. UNIQUE(`level`, `period_start`, `kind`, `subject_key`).
- **compaction_log**: `id` **PK**, `ran_at`, `day`, `status` [ok|failed|skipped], `runs_deleted`, `events_deleted`, `summaries_written`, `detail`.

**Relationships (crow's foot):**
- session ||—o< state_run, event, room_visit, activity, evidence
- instance ||—o< state_run, event, evidence
- room |o—o< anchor, state_run, room_visit, activity
- anchor |o—o< state_run
- room |o—o| session (`last_wearer_room_id`)
- instance → anchor and instance → room (last-known; 0..1)

Draw these as **dotted** lines with the label "soft reference (no FK constraint)":
- `event.from_/to_anchor_id`, `event.from_/to_room_id`
- `event.activity_id`, `event.evidence_id`
- `state_run.evidence_id`
- `instance.last_run_id`, `instance.last_evidence_id`

**Colour overlay (legend):**
- Green: never compacted (`room`, `anchor`, `instance`, `session`, `meta`).
- Orange: compacted after 3 days (`state_run` except protected last-known runs, `event`, `room_visit`, `activity`).
- Blue: written by compaction (`summary`, `compaction_log`).

**Note:** "One file per home: `<store_root>/<home_id>/memory.db`; `SCHEMA_VERSION = 1`."

### F5.8 Live-session artifacts (`ch5-live-session-artifacts.png`)

**Type:** file-tree / artifact diagram, left → right.

Left folder `captures/<session_id>/`:
- `frame_000000.jpg …`
- `index.jsonl`: two record types. Show one sample row each:
  - `frame` (fields: `record_type`, `record_schema_version: 2`, `session_id`, `sequence`, `frame_path`, `source_id`, `capture_timestamp`, `timestamp_source {source_capture | laptop_receive_decode | ingestion | unknown}`, `received_at`, `ingestion_timestamp`, `width`, `height`, `encoding: jpeg`, `sample_rate_target_hz`, `source_protocol`, `keyframe{accepted, reason, sharpness, brightness, visual_change}`)
  - `gap` (fields: `gap_start`, `gap_end`, `duration_seconds`, `reason {disconnect | pause | storage_stall | source_stall | dropped_frames}`, `dropped_estimate`, `sequence_before`, `sequence_after`, `recovered`)
- `session.json`: manifest; `status {running | completed | time_limit | stopped | disconnected | storage_error}`, `pauses[]`, counts.
- `session_state.json`: crash checkpoint.
- `pipeline_state.json`: segment runner progress.

Arrow "`promote_live_segments` (≤ 120 frames per segment, split at gaps)" → right folder `data/<session>_seg0001/`: `frames/*.jpg`, `metadata.json` (schema v2, `preprocess_source: live_session`), `live_session.json`, `live_timestamps.json`, `source_metadata.json`.

Arrow "upload" → "Modal volume `/data/<dataset_id>/`".

**Verify against:** `docs/artifact_contracts.md` §2–3, `ingestion/contracts.py` constants, `ingestion/segment_runner.py` `STATE_FILENAME`.

### F5.9 Patient App screen flow (`ch5-patient-app-flow.png`)

**Type:** screen-flow map. Mid-fidelity phone-frame wireframes (not grey bars only; errata D8) connected by labelled arrows. Use the **real** labels from the code.

**Screens:**
1. **Onboarding dialog** (`OnboardingDialog`, first run): fields "Your name", "Caregiver name", "Relationship", "Caregiver phone number"; button "Save and continue". Stored with `PreferencesService` (`SharedPreferences`).
2. **Patient Home** (`PatientHome`):
   - header with live badge (server reachable: `isServerLive` → `GET /api/v1/health`)
   - `_ServerBadge` (shows the server; tap to change URL)
   - grid of object tiles `_ObjectButton`, built from `trackedObjects()` (`GET /api/v1/datasets` → `tracked_objects`, fallback `GET /api/v1/scene_graph`) with icons from `iconFor(ObjectKind)` in `widgets/object_icon.dart` (`ObjectKind.other` → question-mark icon)
   - big mic button (voice rings)
   - text field
   - "Call" button
3. **Answer Drawer** (`AnswerDrawer`, bottom sheet):
   - title = the question
   - resolution badge (`ResolutionMode`: direct / ranked / ambiguous / notFound)
   - time-cue chips (`TimeCue`: now / morning / yesterday)
   - summary sentence
   - up to 3 `CandidateCard`s (crop photo from `crop_url`, place label, score)
   - not-found state text "Not found. Object not in history"
   - unreachable state "Can't reach Aegis memory…"
4. **Call View** (`CallView`): "Call <name> now" (`tel:`), "Send Message" (`sms:` via `DeviceCallService`), "Change caregiver or number", "Back to home".

**Arrows:**
- Onboarding → Home ("saved").
- Home tile tap → Drawer ("`lookupObject(label)` → `GET /query?item=`").
- Home mic → Drawer: "`DeviceVoiceService.start` (on-device STT) → text → `ask(text)`: `GET /query` first, then `GET /ask` fallback".
- Home text → Drawer (same).
- Drawer time chip → Drawer ("`recall(text, cue)`").
- Home Call → Call View.
- Drawer close (`onClose`) → Home. The drawer has no call button, so do not draw a Drawer → Call View arrow.

**Annotation callouts (numbered):**
- ① 44 pt touch targets.
- ② espresso/ochre theme (`PatientTheme`).
- ③ the app never mutates memory.
- ④ no answer is invented offline.

### F5.10 Caregiver App screen flow (`ch5-caregiver-app-flow.png`)

**Type:** as F5.9.

**Screens:**
1. **Onboarding** (`OnboardingDialog`): patient/server setup, server URL field (hint "https://…"), "Save and continue".
2. **Caregiver Home** (`CaregiverHome`), with a header, a search field + voice rings (`DeviceVoiceService`), a "History" button, and **4 tabs** (`_tabs = ['Home','Track','Interior','Status']`):
   - **Home** (`CaregiverHomeTab`): object tiles `_TileButton`.
   - **Track** (`TrackingTab`): timeline (`GET /api/v1/timeline`), per-item lookup (`queryItem` → `GET /query`), "Interactions" view from the header button.
   - **Interior** (`InteriorTab`): rooms list (`GET /api/v1/rooms`) with rename (`POST /api/v1/rooms/rename`).
   - **Status** (`StatusTab`): server health (`GET /health`), live check, capture status (`GET /api/v1/capture/status`).
3. **Search History** (`SearchHistoryTab`): entries from `HistoryService` (on-device), with filter buttons `_FilterButton`.
4. **Answer Drawer** (`AnswerDrawer`): as patient, plus the ranker chip.
5. **Enroll Dialog** (`EnrollDialog`): alias, class, usual anchor/room → "Save item" (`instanceIdFor(item)` then `enrollItem` → `POST /api/v1/enroll`).

**Red callouts:** "rename and enroll are unauthenticated writes (FR8.1 planned)".

**Verify against:** `apps/Caregiver App/lib/views/*.dart`, `lib/services/api_service.dart`.

### F5.11 DFD level 0 (`ch5-dfd-level0.png`)

**Notation:** Gane–Sarson (rounded process, open-ended data store, square external entity).

- **One process:** "0 — Aegis".
- **External entities:** Primary user, Caregiver, Phone camera, Modal compute platform, Model hub.
- **Flows:**
  - camera → 0: "video frames"
  - user → 0: "question"
  - 0 → user: "answer + evidence / not sure"
  - caregiver → 0: "question, room name, enrolled item, pause/resume"
  - 0 → caregiver: "answers, timeline, rooms, status"
  - 0 → Modal: "frames, config"
  - Modal → 0: "3D boxes, poses, scene graph"
  - hub → Modal: "weights"
- **No data stores at level 0.**

### F5.12 DFD level 1 (`ch5-dfd-level1.png`)

**Notation:** Gane–Sarson. Numbered processes, data stores D1–D6.

**Processes:**
1. **1.0 Capture & sample**: in: camera frames; out: frames + `index.jsonl` → D1.
2. **2.0 Promote & upload**: in: D1; out: segment dataset → D2.
3. **3.0 Reconstruct & perceive** (on Modal): in: D2 frames; out: poses, gravity, 3D boxes → D2.
4. **4.0 Build session memory**: in: D2 boxes/poses/gravity; out: scene graph v2 → D2; evidence crops → D5.
5. **5.0 Ingest into home & compact**: in: D2 graph (downloaded); out: rows → D3; summaries → D3; registry → D4.
6. **6.0 Answer query**: in: question (user / caregiver); reads D2 (session graph) or D3 (home store), D5 (crop); out: answer.
7. **7.0 Manage rooms, items, capture**: in: caregiver commands; writes D2/D3 room labels, D4 `home_map.json`, D3 `meta.personal_items`, capture pause flag file.

**Data stores:**
- D1 Live capture folder `captures/<session>/`
- D2 Modal volume `/data/<dataset_id>/`
- D3 Home store `memory.db`
- D4 `home_map.json`
- D5 Evidence crops
- D6 App local storage (`SharedPreferences`: profile, server URL, caregiver search history)

**External entities:** as F5.11.

Every arrow is labelled. No floating labels.

### F5.13 Sequence: pipeline run (`ch5-seq-pipeline.png`)

**Notation:** UML 2.5 sequence. Lifelines, activation bars, `alt`/`loop`/`opt` fragments with guards.

**Lifelines (left → right):**
1. Operator
2. `run_pipeline.py`
3. Modal volume `/data`
4. `preprocess_video_remote` (CPU)
5. `Reconstructor` (GPU)
6. `Perception` (GPU)
7. `rerun_remote` (CPU)
8. Home store (laptop)

**Messages:**
1. Operator → run_pipeline: `--live-session captures/walk01 --stage live --config-path config/live.yaml`.
2. `opt [live session]` run_pipeline: `promote_live_segments(session, segment_frames)`; `loop [each segment]` wraps steps 3–11.
3. run_pipeline → volume: `upload_dataset_to_modal_volume(dataset_dir, dataset_id)`.
4. run_pipeline → preprocess: `.remote(dataset_id, config)` → writes normalised frames + `metadata.json`; return "frame count".
5. run_pipeline → Reconstructor: `run(dataset_id, config)`.
   - Self-message `download_checkpoint`, with `alt [gated repo refuses token]`: "fallback `wincentIsMe/VGGT-Omega`".
   - Self-message "select every `keyframe_stride`-th frame", with `alt [> max_keyframes]` → error "use --segment-frames".
   - Self-message `run_vggt_reconstruction`.
   - Then `estimate_gravity` → writes `poses.json`, pointmaps, `pointcloud.ply`, `gravity.json`.
6. run_pipeline → Perception: `run(dataset_id, config)`.
   - Self-message `detect_and_track_objects` (SAM3 / YOLOE, SAM 2 fallback masks, DINOv3 embeddings).
   - `loop [each detection]` `lift_detection_to_3d(gravity)`.
   - `evaluate_spatial_containment_and_states`.
   - `build_relative_4d_scene_graph` → writes `detected_objects_3d.json`, `r4d_scene_graph.json`, `r4d_timeline.json`, `events.json`.
   - `write_run_crops`.
7. `opt [visualise]` run_pipeline → rerun_remote: `run_rerun` → `viewer/*.rrd`. Guard text:
   - "`--stage live` unsegmented: always."
   - "segmented live: only with `--rerun` (default off)."
   - "`--stage full`: never."
8. `opt [--download]` (default **off**) run_pipeline ← volume: `_download_outputs(dataset_id)`.
9. Nested inside step 8: `opt [not --no-ingest]` run_pipeline → Home store: `_ingest_into_home` → `ingest_session(store, graph)` → `IngestReport`. Add the note: **"Home-store ingest happens only after `--download`; on the normal path the artifacts stay on the volume and the deployed API reads the session graph directly."**
10. run_pipeline → Operator: `_print_benchmark_summary` (stage timings).
11. Note on the GPU lifelines: "`AEGIS_GPU=cpu` runs Reconstructor/Perception on CPU."

**Verify against:** `run_pipeline.py` (`main` lines 300–326, `_run_stages`, `_run_live_segmented`, `_ingest_into_home`), `remote/workers.py`, `remote/modal_app.py`.

### F5.14 Sequence: patient query (`ch5-seq-query.png`)

**Lifelines:**
1. Patient
2. `PatientHome`
3. `DeviceVoiceService`
4. `ApiService`
5. FastAPI `api.py`
6. `resolve_repository` / Repository
7. `rank_candidates` + `QueryReasoningEngine`
8. `AnswerEngine` (NLQ)
9. `AnswerDrawer`

**Messages:**
1. Patient → PatientHome: tap mic.
   - `alt [voice]`: PatientHome → DeviceVoiceService `start()` → returns transcribed text. Note "on-device STT; no audio leaves the phone".
   - `[typed]`: text field.
   - `[tile]`: `lookupObject(label)` (jump to 3).
2. PatientHome → ApiService: `ask(text, cue)`.
3. ApiService → FastAPI: `GET /api/v1/query?item=<extracted item>` (timeout 8 s).
4. FastAPI → Repository: `resolve_repository(dataset_id, home_id)`, then `latest_states()`.
5. FastAPI → rank: `rank_candidates(states, target, cues=parse_query_cues(item), personal_ids)`, then `reason_spatio_temporal_state(...)`.
6. FastAPI → ApiService: `MemoryQueryResponse{found, location_summary, crop_url, resolution_mode, is_ambiguous, candidates[≤3]}`.
7. `alt [found]`: ApiService → PatientHome: `MemoryAnswer.fromQuery`.
   `[not found]`:
   - ApiService → FastAPI: `GET /api/v1/ask?text=<question>`.
   - FastAPI → AnswerEngine: `ask(text, memory_view_from_repo(repo))`.
   - `alt` inside AnswerEngine:
     - `[LOCATE & item in dictionary & observed]` → answer + evidence
     - `[item not in dictionary]` → abstain `item_not_in_dictionary` + suggestions
     - `[not observed]` → abstain `not_observed_in_memory`
     - `[TEMPORAL / ACTIVITY]` → abstain `*_handler_not_implemented`
   - → `AskResponse` → ApiService: `MemoryAnswer.fromAsk`, `alt [still not found]` → "Not found. Object not in history".
8. `alt [network error / timeout]`: ApiService → PatientHome: `ApiException` → "Can't reach Aegis memory. Check the connection and try again." Add the note "never substitutes a fabricated answer (fixed in `180b897`)".
9. PatientHome → AnswerDrawer: show (badge, summary, candidates with crops via `GET /api/v1/crops/{instance_id}`).

**Verify against:** `apps/Patient App/lib/services/api_service.dart` (`ask`, `lookupObject`, `requestTimeout = 8 s`, `notFoundMessage`, `unreachableMessage`), `remote/api.py` (`query_memory`, `_answer_question`), `nlq/engine.py`.

### F5.15 Sequence: caregiver operations (`ch5-seq-caregiver.png`)

Three `ref`-style sections in one diagram, separated by horizontal dividers.

**Lifelines:** Caregiver, `CaregiverHome`/tabs, `ApiService`, FastAPI, Repository / `HomeStore`, `home_map.json`.

1. **Room rename (UC-13):**
   - `InteriorTab` → ApiService `rooms()` → `GET /api/v1/rooms` → `RoomModel[]`.
   - Caregiver edits the name.
   - `renameRoom(roomId, label)` → `POST /api/v1/rooms/rename`.
   - Repository `rename_room` (JSON graph) **or** `rename_home_room(store, …)` (store: `DuplicateRoomLabelError` if the label is taken, max 40 chars).
   - `export_registry` → `home_map.json`.
   - `alt [unknown room / invalid label]` → 4xx.
2. **Enroll item (UC-14):**
   - `EnrollDialog` → `instanceIdFor(item)` (`GET /query`) → `enrollItem(...)` → `POST /api/v1/enroll {instance_id, alias, canonical_class, usual_anchor, usual_room, visual_crop, home_id}`.
   - `personal.enroll(store, …)` writes `meta.personal_items`.
   - → list of `PersonalItem`.
3. **Status (UC-11 partial):**
   - `StatusTab` → `health()`, `captureStatus()` → `GET /api/v1/capture/status` → `CaptureStatusModel{available, session_id, status, paused, frame_count, last_frame_at}`.
   - `opt` `POST /api/v1/capture/pause` | `/resume` (writes the pause flag file read by `ingest_live`). **Neither app calls these routes** (checked with grep), so draw this message from a separate lifeline "API client (curl / demo script)".

**Dashed fragment** spanning all three: `opt [planned FR8.1]` "authenticate caregiver, check grant scope, write audit entry".

**Red note:** "CORS `*`; these writes are unauthenticated today."

### F5.16 Sequence: home ingest and compaction (`ch5-seq-home-ingest.png`)

**Lifelines:** `run_pipeline`/`aegis-memory` CLI, `ingest_session`, `matching`, `HomeStore` (SQLite), `activities`, `compaction`, `home_registry`.

1. → `ingest_session(store, graph, vocabulary, now, timezone, evidence_root, retention)`.
2. Self-message `graph_sha256(graph)`.
   - `alt [same sha as stored]` → return status `unchanged`.
   - `[different sha]` → `delete_session_rows` (status `replaced`).
3. `store.transaction()` begins (the frame spans steps 4–10).
4. insert `session`.
5. `_ingest_rooms` → `match_rooms(session_rooms, home_rooms, continuity)` → room map.
6. `_ingest_anchors` → `match_anchors(..., room_map)`, returning a map with quality labels unique / aligned / resident / ordinal / new.
7. `_ingest_instances` → `match_instances(...)`.
8. `_ingest_runs`: `loop [each run]`
   - `alt [same place as last run within CONTIGUOUS_SECONDS = 10]` → extend the run.
   - `[moved since last seen]` → insert event `moved_while_unobserved`.
   - Then insert `state_run`; `_attach_evidence`.
9. `_ingest_events`, `_ingest_visits`.
10. `store_session_activities` → activity rows; `recompute_last_known(instance)`.
11. Commit.
12. `export_registry(store)` → `home_map.json`.
13. `opt [retention configured]` → `compact(store, now, config)` then `rollup(store, now, config)` (each day in its own transaction; see F5.19).
14. Return `IngestReport` (counts: rooms/anchors/instances created vs matched, runs inserted/extended, events, activities, `days_compacted`, `compaction_failures`).

**Verify against:** `src/aegis/memory/ingest.py` lines 110–210.

### F5.17 State machine: live capture session (`ch5-state-live-session.png`)

**Notation:** UML state machine: initial pseudostate, states with `entry/`/`do/` actions, guarded transitions `event [guard] / action`, final states.

**States:**
- **Starting**: `entry / create LiveSessionWriter (new or resume)`.
- **Sampling**: `do / read frames; emit at sample_fps; KeyframeSelector.evaluate`. Sub-transitions as an internal self-transition: `frame [not accepted] / rejected += 1`.
- **Paused**: `do / count dropped`.
- **StorageStalled**: `do / buffer frames (capacity 30); drop oldest when full`.
- **Reconnecting**: `do / sleep reconnect_interval (3 s)`.
- Final states (each writes the manifest status): **completed**, **time_limit**, **stopped**, **disconnected**, **storage_error**.

**Transitions:**

| From | Event / guard | Action | To |
|---|---|---|---|
| Starting | — | — | Sampling |
| Sampling | `pause flag set` | — | Paused |
| Paused | `pause flag cleared` | `record_pause + record_gap(reason=pause)` | Sampling |
| Sampling | `write fails (OSError)` | — | StorageStalled |
| StorageStalled | `flush succeeds` | `record_gap(reason=storage_stall, recovered=true)` | Sampling |
| Sampling | `ConnectionError / source ended` | `start disconnect window` | Reconnecting |
| Reconnecting | `frames arrive` | `record_gap(reason=disconnect, recovered=true)` | Sampling |
| Reconnecting | `[now ≥ reconnect deadline (30 s)]` | — | disconnected |
| Sampling | `[now ≥ max_duration (600 s)]` | — | time_limit |
| any | `KeyboardInterrupt` | — | stopped |
| any, on exit | `[buffer cannot be flushed]` | — | storage_error |

Note: "`checkpoint()` writes `session_state.json` every `checkpoint_every` frames → crash resume (`resume=True`)".

**Verify against:** `src/aegis/ingestion/live_pipeline.py` (`ingest_live`), `contracts.py` `SESSION_STATUSES`, `GAP_REASONS`.

### F5.18 State machine: object instance (`ch5-state-object.png`)

**Purpose:** how one object's state runs and events arise.

**States:**
- **Unknown** (never seen)
- **Placed**: composite state with sub-states:
  - `inside`, `on_surface`, `under`, `above`, `next_to`, `on_floor`, `near` (each "relative to anchor A").
  - `in_room` (no anchor).
  - Each sub-state is one **StateRun**.
- **Carried** (`carried_by_user`)
- **Unobserved** (out of view; last-known state kept: object permanence)

**Transitions (label = emitted event):**

| From | To | Label |
|---|---|---|
| Unknown | Placed | first stable observation `[≥ min_observations = 2]` / create instance |
| Placed | Carried | `pickup` |
| Carried | Placed | `placement` |
| Placed(anchor A) | Placed(anchor B) | `anchor_change` |
| Placed(rel X) | Placed(rel Y, same anchor) | `state_change` |
| Placed | Unobserved | leaves view (no event; run ends) |
| Unobserved | Placed | seen again `[same place]` / extend run |
| Unobserved | Placed | seen again `[different place, next session]` / `moved_while_unobserved` (home store) |
| any | any | wearer's room changes / `room_change` (wearer event, drawn as a note) |

**Note:** debouncing: a new state starts only after `min_run_observations = 2` consecutive observations, or a single trailing one with confidence ≥ `trailing_single_confidence = 0.5` (`runs._segments`).

**Verify against:** `memory/runs.py` (`_segments`, `_event_type`), `memory/ingest.py` (`moved_while_unobserved`), `core/config.py` `MemoryBuildConfig`.

### F5.19 Activity diagram: compaction (`ch5-activity-compaction.png`)

**Notation:** UML activity: rounded actions, diamonds, a swimlane per actor ("compact()" and "SQLite transaction"), and an exception handler.

**Flow:**
1. Start → "today = now in `RetentionConfig.timezone` (Asia/Karachi)"; "cutoff = today − `hot_days` (3)"; "important_cutoff = today − `important_hot_days` (7)".
2. "for each local day with detail (`_detail_days`)" (expansion region / loop).
3. Diamond `[day ≥ cutoff or already logged]` → skip (next day).
4. "begin transaction".
5. "`_build_day`: object day summaries (`object_day_summary`) + activity summaries (`activity_day_summary`)".
6. "`_verify`" (see the checks below), diamond `[VerificationError]`:
   - yes → "rollback; log `failed` with reason; keep all rows (UC-12 A1)" → next day.
   - no → continue.
7. "`_write_summary` (level=day)".
8. "protected = `_protected_runs` (each instance's last-known run)".
9. "delete runs (`_delete_runs`) except protected, and except important objects while day ≥ important_cutoff; keep last evidence if `keep_last_evidence`".
10. "delete events / room_visits / activities of that day (same important exception for events)".
11. "`_log` ok (runs_deleted, events_deleted, summaries_written)"; commit.
12. After the loop → "`rollup`: day lines > `weekly_rollup_after_days` (30) → week; week lines > `monthly_rollup_after_days` (365) → month".
13. End → `CompactionReport`.

**Checks performed by `_verify`** (show as a note attached to step 6):
1. Every instance with runs that day has an object summary.
2. The summary's last state equals the final run (relation, anchor, room, time).
3. Every activity has a summary.
4. Every referenced room/anchor exists.
5. The text is non-empty and contains no "None".

**Verify against:** `src/aegis/memory/compaction.py` (module docstring, `_verify`, `compact`, `rollup`), `core/config.py` `RetentionConfig`.

### F5.20 Activity diagram: NLQ answer engine (`ch5-activity-nlq.png`)

**Flow:**
1. Input question → "normalise whitespace".
2. `[empty]` → abstain `empty_query` "Please type a question."
3. "classify_intent" (regex rules):
   - `when|what time|how long ago` → TEMPORAL → abstain `temporal_handler_not_implemented`.
   - `what did|what have|what was|what happened|activities` → ACTIVITY → abstain `activity_handler_not_implemented`.
   - `where|find|locate|show`, **or** a dictionary item is found → LOCATE.
   - else UNKNOWN → abstain `unknown_intent`.
4. LOCATE: "`DictionaryIndex.lookup_item` (aliases authoritative, word boundary)".
   - `[no item]` → abstain `item_not_in_dictionary` + suggestions (`suggestions_for`).
5. "candidates = latest states whose canonical = item".
   - `[none]` → abstain `not_observed_in_memory` "I haven't seen your <item>. I remember: …".
6. `[room slot present]` → filter by room/anchor label.
   - `[none]` → abstain `no_match_in_room`.
7. "sort: in active view, then last_seen_timestamp, then wallclock (desc)" → primary.
8. "compose answer from template (`_compose`, `_place`, `_room_clause`); evidence = state id + description + crop".
9. Output `AskResult{status, answer, evidence[], other_instances[], confidence, last_seen_*}`.

Dashed side branch from step 3: "Optional LLM planner (P1.9, off by default; parser only, never writes answer text)".

**Verify against:** `src/aegis/nlq/engine.py` (`classify_intent`, `ask`, `_answer_locate`), `nlq/dictionary.py`.

---

## 7. Chapter 6 figures (Iteration 1, frozen)

### F6.1 / F6.2 (`ch6-class-core-models.png`, `ch6-class-live-api.png`)

Reuse the mid content, but fix these (errata D14, D15):
- Rename the files.
- Remove the printed authoring note in F6.2 ("Generated from or checked against…").
- Add types to attributes (`frame_id: int`, `center: tuple[float,float,float]`, …) from `git show v0.2.0-mid2:src/aegis/core/models.py` and `…/memory/scene_graph.py`.
- Keep only one relationship between `BoundingBox3D` and `ObjectMemoryEntry` (the «derives» dependency).
- In F6.2, list the Pydantic fields of `HealthResponse`, `AnchorModel`, `MemoryQueryResponse`, `TimelineEventModel` *as at `v0.2.0-mid2`*.
- In F6.2, add `QueryReasoningEngine`'s five methods.
- **Caption:** "Iteration 1 implementation at tag `v0.2.0-mid2` (13 Oct 2026)". Do **not** add room classes: they belong to Iteration 2.

### F6.3, F6.4

KEEP.

---

## 8. Chapter 7 figures (Iteration 2, new)

### F7.1 Class diagram: memory package (`ch7-class-memory.png`)

**Notation:** UML class with attribute types and the key public operations only (no private `_` methods). Package frames: `aegis.memory`, `aegis.geometry` (for `GravityFrame`).

**Classes (exact names, attributes, operations):**

- **`GravityFrame`** (geometry, frozen dataclass)
  - Attributes: `up: tuple[float,float,float]`, `floor_offset: float|None`, `source: str`, `confidence: float`, `inlier_ratio: float`, `camera_height: float|None`
  - Operations: `+assumed()`, `+elevation(point)`, `+height(point)`, `+horizontal(point)`, `+is_reliable(min_confidence)`, `+unit(assumed_camera_height, min_confidence)`, `+as_dict()`, `+from_dict(raw)`
- **`SpatialAnchor`**
  - Attributes: `anchor_id: int`, `label: str`, `canonical: str`, `center`, `size`, `room_id: int|None`, `footprint: list`, `up_min`, `up_max`, `support_up`
  - Operations: `+as_dict()`
- **`AnchorShape`**: `anchor_id`, `footprint: Footprint3D`, `container: bool`, `support_surface: bool`, `open_underneath: bool`
- **`Footprint3D`**: `polygon`, `up_min`, `up_max`, `support_up`
- **`RelationResult`**: `relation: str`, `anchor_id: int|None`, `certain: bool`, `overlap: float`, `gap: float`
- **`Observation`**
  - Attributes: `frame_id`, `timestamp`, `instance_id`, `box: BoundingBox3D`, `relation`, `anchor_id`, `certain`, `hand_cue`
  - Operations: `+state()`, `+state_certain()`
- **`StateRun`**
  - Attributes: `instance_id`, `relation`, `anchor_id`, `room_id`, `start_frame`, `end_frame`, `start_time`, `end_time`, `observation_count`, `confidence`, `certain`, `center`, `height_above_floor`, `best_frame`, `best_bbox_2d`
  - Operations: `+as_dict()`
- **`RoomRegion`**
  - Attributes: `room_id`, `label`, `room_type`, `centroid`, `footprint`, `evidence_labels`, `keyframe_count`, `start_timestamp`, `end_timestamp`
  - Operations: `+as_dict()`
- **`Relative4DSceneGraph`**
  - Attributes: `anchors: list[SpatialAnchor]`, `rooms: list[RoomRegion]`, `state_runs`, `latest_states`, `events`, `room_visits`, `gravity: GravityFrame`, `session: dict`
  - Operations: `+as_dict()`, `+timeline_dict()`
- **`HomeStore`**
  - Attributes: `home_id: str`, `path: Path`
  - Operations: `+transaction()`, `+query(sql, params)`, `+insert(table, values)`, `+update(...)`, `+rooms()`, `+anchors()`, `+instances()`, `+latest_states()`, `+states_as_of(as_of, since)`, `+state_at(canonical, at, tolerance_s)`, `+events(start, end)`, `+activities(start, end)`, `+summaries(start, end)`, `+recompute_last_known(instance_id)`, `+delete_session_rows(session_id)`, `+counts()`, `+db_size_bytes()`
- **`IngestReport`**: `session_id`, `status`, `rooms_created`, `rooms_matched`, `anchors_created`, `anchors_matched`, `instances_created`, `instances_matched`, `runs_inserted`, `runs_extended`, `events_inserted`, `events_skipped`, `activities`, `days_compacted`, `compaction_failures`
- **`RoomInfo`**, **`AnchorInfo`**, **`InstanceInfo`** (matching inputs)
- **`Similarity2D`**: `scale`, `theta`, `translation`, `+apply(point)`
- **`AnchorMatchResult`**: `mapping`, `transform`
- **`CompactionReport`**: `days_compacted`, `days_failed`, `runs_deleted`, `events_deleted`, `summaries_written`, `rollups_written`
- **`SummaryDraft`**: `kind`, `subject_key`, `text`, `sidecar`
- **`VerificationError`** (RuntimeError)
- **`ActivityDraft`**: `room_id`, `start_at`, `end_at`, `event_ids`
- **`PersonalItem`**: `instance_id`, `alias`, `canonical_class`, `usual_anchor`, `usual_room`, `visual_crop`
- **`HomeRoomRegistry`** / **`HomeRoomRecord`**: `room_id`, `label`, `room_type`, `signature`, `label_source`, `session_count`, `last_seen_session`
- **«interface» `MemoryRepository`** (Protocol)
  - Attributes: `ready: bool`
  - Operations: `+anchors()`, `+rooms()`, `+events()`, `+latest_states()`, `+rename_room(room_id, label)`, `+keyframe_count()`
  - Realised by **`JsonGraphRepository`** and **`StoreRepository`** (hollow-triangle dashed realisation)

**Module functions** (draw as «utility» boxes):
- `relations`: `classify_relation`, `box_footprint`
- `runs`: `build_state_runs`, `build_events`
- `matching`: `match_rooms`, `match_anchors`, `match_instances`, `estimate_similarity`
- `ingest`: `ingest_session`
- `compaction`: `compact`, `rollup`, `compaction_ok`
- `personal`: `enroll`, `resolve_alias`, `personal_ids_for_query`

**Relationships:**
- `Relative4DSceneGraph` ◆— `SpatialAnchor`, `RoomRegion`, `GravityFrame`.
- `StateRun` o— `Observation` (1..*).
- `classify_relation` uses `Footprint3D`, `AnchorShape`, `GravityFrame` → `RelationResult`.
- `ingest_session` uses `HomeStore`, `matching`, returns `IngestReport`.
- `StoreRepository` → `HomeStore`.
- `compact` uses `HomeStore`, `SummaryDraft`, raises `VerificationError`, returns `CompactionReport`.

**Size control:** if it does not fit, split it into F7.1a (session graph: geometry, relations, runs, scene graph) and F7.1b (home store: store, ingest, matching, compaction, personal, repository).

### F7.2 Class diagram: query, API and apps (`ch7-class-query-api-apps.png`)

**Package `aegis.nlq`:**
- `Intent` «enumeration» `LOCATE`, `TEMPORAL`, `ACTIVITY`, `UNKNOWN`.
- `AskResult` (fields as in the code map: `question`, `intent`, `status`, `answer`, `abstained`, `abstain_reason`, `instance_label`, `anchor_label`, `room_label`, `relation`, `confidence`, `last_seen_timestamp`, `last_seen_wallclock`, `suggestions`, `evidence`, `other_instances`, `dataset_id`; `+to_dict()`).
- `AnswerEngine` (`+classify_intent(question)`, `+ask(question, memory)`).
- `DictionaryIndex` (`item_synonyms: dict`, `room_keywords: dict`; `+seeded()`, `+load(path)`, `+lookup_item(query): Slots`, `+lookup_room(query)`, `+canonical_of(label)`, `+suggestions_for(unknown, limit)`).
- `Slots` (`item`, `room`, `item_raw`).

**Package `aegis.memory.reasoning`:**
- `QueryReasoningEngine` (`+strip_room_words`, `+item_phrase`, `+extract_target_item`, `+extract_room_filter`, `+reason_spatio_temporal_state`).
- `QueryCues` (`room`, `days_ago`, `window_start`, `window_end`, `activity`, `visual_terms`).
- `rank_candidates(states, target, mode∈{recency_only, salience, full}, cues, config, personal_ids)`.
- `RankingConfig` (`candidate_limit 3`, `ambiguity_margin 0.08`, `recency_half_life_hours 24`, `w_vip 1.0`, `w_act 0.45`, `w_disp 0.25`, `w_rec 0.20`, `w_cue 0.10`, `w_visual 0.10`).

**Package `aegis.remote.api`** (Pydantic, with fields):
- `AskRequest{text ≤300, dataset_id, home_id}`
- `AskResponse` (as `AskResult` + `found`)
- `MemoryQueryResponse` (list all 25 fields from the code map: `query`, `found`, `item`, `instance_label`, `instance_id`, `anchor_id`, `anchor_label`, `room_id`, `room_label`, `relation`, `relation_certain`, `height_above_floor`, `relative_distance_m`, `location_summary`, `explanation`, `last_seen_timestamp_s`, `last_seen_at`, `last_seen_time_ago`, `is_persistent_memory`, `crop_url`, `confidence`, `other_instances`, `resolution_mode`, `is_ambiguous`, `ambiguity_reason`, `candidates`)
- `EnrollRequest`
- `RoomModel`
- `AnchorModel`
- `TimelineEventModel`
- `ActivityModel`
- `CaptureStatusModel`
- `HealthResponse`

**Flutter (Patient App):**
- `ApiService` (`baseUrl`, `requestTimeout=8s`; `+ask(text, cue)`, `+lookupObject(label, cue)`, `+trackedObjects()`, `+recall(text, cue)`, `+isServerLive()`, `+setBaseUrl(url)`)
- `MemoryAnswer` (`+fromQuery`, `+fromAsk`)
- `MemoryCandidate`
- `ResolutionMode` «enum» `direct`, `ranked`, `ambiguous`, `notFound`
- `TimeCue` «enum» `now`, `morning`, `yesterday`
- «interface» `VoiceService` (`+initialize`, `+start`, `+stop`, `+cancel`) ← `DeviceVoiceService`, `NoVoiceService`
- «interface» `CallService` (`+call(phone)`, `+message(phone, body)`) ← `DeviceCallService`, `NoCallService`
- `PatientProfile` (`patientName`, `caregiverName`, `caregiverPhone`, `relationship`)
- `PreferencesService`
- `ObjectTile`, `ObjectKind`

**Flutter (Caregiver App):**
- `ApiService` adds `+queryItem`, `+instanceIdFor`, `+renameRoom`, `+enrollItem`, `+captureStatus`, `+health`, `+datasets`, `+rooms`, `+timeline`
- `HistoryService` (`+load`, `+add`, `+clear`)
- `SearchEntry`

**Dependencies (dashed arrows labelled with the HTTP route):**
- `ApiService` ⇢ `query_memory` "`GET /query`"
- `ApiService` ⇢ `ask_question` "`GET /ask`"
- Caregiver `ApiService` ⇢ `rename_room`, `enroll_item`, `get_timeline`, `capture_status`

### F7.3 Flowchart: relation classification (`ch7-flow-relations.png`)

Follow `classify_relation` exactly:
1. Input: object `Footprint3D`, anchors `AnchorShape[]`, `GravityFrame`.
2. `reliable = gravity.is_reliable(0.5)`; `floor_tol = 0.06 × camera_height` (else 0.5 × object height); `on_floor = reliable ∧ floor known ∧ (up_min − floor_offset) ≤ floor_tol`.
3. Loop over anchors:
   - `overlap = overlap_fraction(obj.polygon, anchor.polygon)`
   - `gap` = centroid-to-polygon distance
   - `tol = 0.15 × max(spans)`
   - `reach = 0.5·√area`
4. Diamond `overlap ≥ 0.5` → **`_over_anchor`**:
   - `up_min > a.up_max + tol` → `above`
   - else if container: `middle > up_max` → `on_surface`; within span → `inside`; else `near` (uncertain)
   - else if `|up_min − surface| ≤ tol` → `on_surface`
   - else if `up_min > surface + tol` → `on_surface` (uncertain)
   - else if open underneath and `up_max ≤ surface − tol` → `under`
   - else `near` (uncertain)
5. Else if `gap ≤ reach` → `on_floor` if on_floor, else `next_to`.
6. Collect candidates; choose by priority:
   - inside / on_surface: 6
   - under: 5
   - on_floor: 4
   - next_to: 3
   - above: 2
   - on_surface (uncertain): 2
   - near: 1
   - Ties are broken by overlap, then smaller gap.
7. No candidates:
   - on_floor → `on_floor` (nearest anchor if gap ≤ 3·reach)
   - else nearest within 3·reach → `near` (uncertain)
   - else `in_room`
8. If gravity is **unreliable**:
   - vertical relations (`under`, `above`, `on_floor`) → `near` (or `in_room` if no anchor), marked uncertain
   - `inside` / `on_surface` / `next_to` are kept but marked uncertain
9. Output `RelationResult`.

### F7.4 Flowchart: cross-session matching (`ch7-flow-matching.png`)

Three stacked lanes.

**Rooms (`match_rooms`):**
1. Continuity: a session that starts within seconds of the previous one starts in the last wearer room.
2. Signature Jaccard ≥ 0.5, compatible type, margin ≥ 0.05 over the runner-up, ≥ 1 shared label; one-to-one.
3. A single remaining bare room ↔ a single remaining bare home room.
4. Otherwise create a new room (`_new_room_label`).

**Anchors (`match_anchors`), group by (canonical, mapped room):**
1. `unique` (one of its type on both sides).
2. `aligned` (2D similarity transform `estimate_similarity` from the unique matches; residual ≤ 25 % of scale).
3. `resident` (what rests on it).
4. `ordinal` (equal counts left; paired in id order, weak).
5. `new`.

**Instances (`match_instances`), per class, one-to-one:**
1. Same place as last known.
2. Carried across a segment boundary.
3. Only one of its class on both sides.
4. Appearance distance ≤ 0.35 with a margin of 0.1.
5. Else new.

**Footer note:** "Measured weakness: `zone_link_radius` (1.5) is in absolute VGGT units, which are scale-arbitrary per reconstruction. EgoLife showed room identity instability across sessions (DAY7 rooms 44→40 after `61dda40`; anchors 859→818)."

### F7.5 Flowchart: live keyframe selection (`ch7-flow-keyframe.png`)

Follow `KeyframeSelector._decide`:
1. brightness < 20 → reject `too_dark`.
2. brightness > 245 → reject `too_bright`.
3. sharpness (Laplacian variance) < 15 → reject `blurred`.
4. First frame → accept `first_frame`.
5. visual_change = mean |gray₆₄ₓ₃₆ − last| / 255.
6. visual_change < 0.008 **and** elapsed < 2.0 s → reject `duplicate`.
7. Otherwise accept:
   - reason `max_interval` if visual_change < 0.008 (accepted only because ≥ 2 s elapsed)
   - else reason `scene_change`

**Verify against:** `KeyframeConfig` defaults in `core/config.py`.

### F7.6–F7.9 Screenshots (shot list)

These are **real screenshots, never mock-ups** (rubric red flag). Capture on a physical Android phone against the deployed API, with a dataset that has at least 3 objects (for example the `walk01-2` segment, or `demo04`).

| ID | Panels (left → right) | Exact state to capture |
|---|---|---|
| F7.6 Patient App | (a) Home | Tiles visible, live badge green |
|  | (b) Voice | Mic listening (voice rings animating) |
|  | (c) Answer drawer | Answer to "where are my shoes" with the resolution badge and candidate photo |
|  | (d) Not-found | Answer to "where are my keys" (abstention text) |
|  | (e) Call view | — |
| F7.7 Caregiver App | (a) Home | Search field + tiles |
|  | (b) Track tab | Timeline |
|  | (c) Interior tab | Room list with the rename field open |
|  | (d) Status tab | — |
|  | (e) Enroll dialog | Filled in |
| F7.8 Rerun | One frame | Video panel on the left, 3D memory on the right showing room colours, anchors and object OBBs, from `run_rerun` output |
| F7.9 Terminal | One window | `uv run aegis-ask "where are my keys" --dataset-id <id>` (abstention) and `"where are my shoes"` (answer) over the http transport, URL visible |

Add a red-rectangle callout only where the text refers to it. Crop the status bar; blur any faces or bystanders (ethics, §1.11).

---

## 9. Chapter 8 figures (testing and results)

### F8.1 Test pyramid (`ch8-test-levels.png`)

**Type:** pyramid of four tiers + a side column "Evaluation & measurement". Each tier shows its test count and example files. Counts come from `uv run pytest --collect-only -q` on `develop` `ce49dcc`: **451 tests in 53 files**. Group them exactly as below; the counts add up to 451.

| Tier | Files (tests) | Total |
|---|---|---|
| Unit: geometry & perception | `test_geometry` 5, `test_gravity` 12, `test_planar` 6, `test_lifting` 15, `test_detector_postprocess` 6, `test_vggt_checkpoint` 3 | 47 |
| Unit: memory | `test_anchors` 4, `test_association` 6, `test_relations` 19, `test_runs` 5, `test_rooms` 9, `test_scene_graph` 18, `test_room_identity` 6, `test_matching` 15, `test_store` 4, `test_ingest` 12, `test_compaction` 14, `test_activities` 7, `test_evidence` 7, `test_home_registry` 4, `test_restart_equivalence` 3, `test_wallclock` 4, `test_mid1_prototype` 4 | 141 |
| Unit: config, vocabulary, query | `test_config` 10, `test_vocabulary` 19, `test_reasoning` 12, `test_ranking` 12, `test_nlq` 9 | 62 |
| Integration: ingestion / live | `test_live_ingestion` 13, `test_live_contracts` 12, `test_live_handoff` 8, `test_live_segments` 7, `test_live_keyframe` 6, `test_live_buffer` 3, `test_live_cli` 8, `test_video_ingestion` 5, `test_capture_control` 2 | 64 |
| Integration: API & serving | `test_api` 28, `test_repository` 4, `test_serve_app` 2, `test_modal_compute` 1, `test_rerun_visualization` 3 | 38 |
| Tooling: E2E runner & demo harness | `test_run_e2e` 17, `test_demo_harness` 7, `test_demo_calibrate` 4 | 28 |
| Evaluation harness | `test_evaluation` 6, `test_evaluation_metrics` 13, `test_evaluation_query` 8, `test_evaluation_run` 1, `test_evaluation_controlled_room` 3, `test_evaluation_memory_audit` 4, `test_evaluation_option_c` 6, `test_egolife` 30 | 71 |
| **Total (Python)** | | **451** |
| Flutter widget tests | Patient `widget_test.dart` 14, Caregiver `widget_test.dart` 11 | 25 (counted by `grep -c testWidgets\|test(`; confirm with `flutter test` in CI) |

**Top of the pyramid (dashed):** "System / acceptance: one measured E2E run (20 Nov, CPU); 1-hour soak, p95 latency and usability not yet run."

**Footer:** "Coverage 79% (`pytest --cov=aegis`, 10,759 statements), CI floor 75%."

### F8.2 Detection chart (`ch8-detection-chart.png`)

Same as F2.3. Use one image and `\ref` it from both chapters, unless Ch 2 shows only the decision table.

### F8.3 Compaction ratio (`ch8-compaction-ratio.png`)

**Type:** grouped bars. x = snapshot interval {0, 1, 10, 30}; two series, demo04 and demo03; y = compaction ratio (×). Secondary y-axis: centre p95 error (scene units) as dots joined by a line.

**Data (`evaluation/reports/memory_control/summary.md`):**

| Interval | demo04 ratio | demo04 p95 | demo03 ratio | demo03 p95 |
|---|---|---|---|---|
| 0 | 7.2 | 0.363 | 5.7 | 0.219 |
| 1 | 1.9 | 0.000 | 1.5 | 0.000 |
| 10 | 5.4 | 0.241 | 4.4 | 0.137 |
| 30 | 6.4 | 0.245 | 5.0 | 0.178 |

Annotate: "semantic retention, latest-state exactness and query agreement = 100% in all 8 runs".

### F8.4 Storage projection (`ch8-storage-projection.png`)

**Type:** line chart. x = hours {1, 8, 24}; y = MiB (log scale optional). Four lines: demo04 original/compacted, demo03 original/compacted.

**Data:**

| Series | 1 h | 8 h | 24 h |
|---|---|---|---|
| demo04 original | 13.51 | 108.1 | 324.2 |
| demo04 compacted | 2.11 | 16.9 | 50.7 |
| demo03 original | 18.76 | 150.1 | 450.3 |
| demo03 compacted | 3.27 | 26.1 | 78.4 |

**Title or caption must contain "linear projection from short clips — not measured".**

Optional extra series, if the team runs it: the synthetic store-growth measurement `outputs/evaluation/store_growth.csv` (`scripts/measure_store_growth.py`, `memory/synthetic.py`). Check the CSV columns before plotting.

### F8.5 E2E stage timing (`ch8-e2e-timing.png`)

**Type:** horizontal bar. Bars: VGGT 831 s, detect + lift 27 s, deploy 8 s. Caption: "Single end-to-end run, 20 Nov 2026, CPU (`AEGIS_GPU=cpu`), capture `walk01-2`, 79 frames, segment `walk01-2_seg0001`; `aegis-ask` answered over HTTPS from the volume." Add a grey reference bar: "L4 GPU, one 5-min EgoLife segment: VGGT 200 s, detection 108 s".

### F8.6 EgoLife (`ch8-egolife.png`)

**Data not in the repository.** It lives in `outputs/evaluation/egolife_scored/FINAL_SUMMARY.md` and `report.json` on Faizan's machine. Get them before drawing.

**Planned form:**
- Panel (a): grouped bars per query day (DAY2…DAY7). Series: Top-1 place accuracy with **full history** vs **last-24 h ablation** (T2 tier, `full` ranker).
- Panel (b): the oracle-assisted diagnostic, 12 matched placements, as horizontal bars of "days persisted" (1–4).
- Panel (c, optional): identity growth (rooms and anchors per day before/after `61dda40`: DAY7 rooms 44→40, anchors 859→818).

**Known facts to put in the caption:**
- 74 segments.
- $8.71 metered, $0 billed.
- "full history never beats the 24 h ablation at class level".
- "12/12 matched instances still in store 1–4 days later".

---

## 10. Chapter 9 and 10 figures

### F9.1 Commit timeline (`ch9-commit-timeline.png`)

**Type:** stacked weekly bar chart (one colour per member), x = ISO week, y = non-merge commits.

**Data** (`git log --no-merges`, identities merged: `pez-Ox` + "Faizan Ur Rehman Khan" = Faizan; `shah-paradox` = Shahmeer; `Ali Sher` = Ali). Excludes the guide commit `9aaf2c5`. **Re-run on the submission commit.**

| ISO week (Mon) | Faizan | Shahmeer | Ali |
|---|---|---|---|
| W35 (24 Aug) | 1 | 0 | 0 |
| W36 (31 Aug) | 1 | 0 | 0 |
| W40 (28 Sep) | 10 | 0 | 0 |
| W41 (5 Oct) | 8 | 10 | 0 |
| W42 (12 Oct) | 24 | 0 | 15 |
| W45 (2 Nov) | 0 | 9 | 30 |
| W46 (9 Nov) | 3 | 22 | 11 |
| W47 (16 Nov) | 11 | 1 | 38 |
| W48 (23 Nov) | 0 | 0 | 124 |

Overlay vertical markers:
- Tags `v0.1.0-mid1` (4 Oct) and `v0.2.0-mid2` (13 Oct).
- Mid report (22 Oct).
- Merge of NLQ into `develop` (24 Nov).

**Mandatory caption note:** "Commit counts reflect commit granularity, not effort; 122 of Ali Sher's W48 commits are one-file-per-commit app scaffolding."

**Command:**
```bash
git log --no-merges --format='%ad|%an' --date=format:'%G-W%V'
```

### F9.2 Branch graph (`ch9-branch-graph.png`)

**Type:** git graph (horizontal lanes). Lanes: `main`, `develop`, and feature branches.

**Events to show (from `git log --merges`):**
- 4 Oct: `feat/ci-cd-pipeline`, `feat/api-r4dsg-query`, `feat/ui-dementia-flutter`, `feat/vlm-query-agent`, `feat/cd-automation` → `develop`; tag `v0.1.0-mid1` (`4419832`).
- 9 Oct: `feat/egocentric-in-hand-memory` → `develop`; `develop` → `main` (`8f9cd63`).
- 11 Oct: PR #1 `migrate-legacy-aegis-analysis` (`30e8388`); `develop` → `main` (`2c7884a`, `50551a4`).
- 12 Oct: `develop` → `main` (`712e96e`).
- 13 Oct: tag `v0.2.0-mid2` (`678acbd`).
- 7 Nov: `main` → `develop` (`b249335`).
- 15 Nov: `develop`, `feat/memory-plan`, `feat/evaluation-suite` → `feat/NLQ` (`638c30f`, `c36f3ff`, `bc89e7e`).
- 17 Nov: `feat/evaluation-suite` → `develop` (`0f227c0`); `feat/memory-plan` → `develop` (`82e54d4`); `develop` → `feat/NLQ` (`46ed2c1`); `main` fast-forwarded to `develop`.
- 21–22 Nov: commits directly on `main` (`feat/demo` work, EgoLife, SAM3). Mark these in orange with the note "committed directly to main; policy: main only via develop".
- 23 Nov: `main` → `feat/NLQ` (`d5d3bd1`).
- 24 Nov: `develop` fast-forwarded to `feat/NLQ` (`ce49dcc`).
- Final: `develop` → `main` + tag `v0.3.0-fyp1-final` (planned; dashed).

**Command to confirm:**
```bash
git log --graph --oneline --all --decorate --since=2026-10-01
```

### F10.1 FYP-2 Gantt (`ch10-fyp2-gantt.png`)

Rows (Iteration 3, then Iteration 4), with an owner colour per row. Dates and owners are **team input**; leave placeholders until agreed.

**Iteration 3:**

| Item | TODO ID |
|---|---|
| Temporal answers | P1.1 |
| Calibrated confidence | P1.2 |
| Freshness | P1.3 |
| Evidence refs | P1.4 |
| Multi-instance clarification + query log | P1.5 |
| Speech confirm step | P1.6 |
| Scale-relative room linking (fix for TC12) | — |
| `demo05` annotation + scoring | P2.5 |
| Room metrics | P2.3 |

**Iteration 4:**

| Item | TODO ID |
|---|---|
| Auth / grants / consent / audit / CORS | P1.7 |
| Encryption + deletion | P1.8 |
| Optional LLM planner | P1.9 |
| 1-hour soak + disconnect tests | P2.1 |
| Placement/activity GT | P2.2 |
| Controlled room | P2.4 |
| Latency p95 + compaction before/after | P2.8 |
| 7/30-day persistence pilot | P2.7 |
| Usability study (after ethics approval) | — |
| Thesis writing | — |

**Milestones:** FYP-2 mid evaluation, FYP-2 final, thesis submission (dates TBD).

---

## 11. Verification checklist for every figure

Before a figure goes into `ThesisFigs/`:

- [ ] Every class, method, field, table, column, route and file name appears verbatim in the code on the submission commit. Check with `grep -rn "<name>" src apps scripts config run_pipeline.py`.
- [ ] Every number appears in `REPORT_STRUCTURE.md` §8 / this file, or was re-measured, and the caption gives its source.
- [ ] Solid/dashed/red convention followed; legend present.
- [ ] No embedded "Figure x" title; no placeholder text; no authoring notes.
- [ ] No connector crosses another element; no floating labels.
- [ ] Opaque white background; PNG; ≥ 2400 px.
- [ ] Editable source saved in `ThesisFigs/src/`.
- [ ] The owning team member can explain every element (rubric red flag: "diagrams purely AI-generated without understanding").
