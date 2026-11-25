# FYP-1 Mid Report: Errata

**Report checked:** `fyp_report/F26_062_i230626_i233021_i230683.pdf` (submitted, 128 pages). Its text is identical to `fyp_report/main.pdf`, built from `fyp_report/chapters/*.tex`.

**Code it was checked against:** the repository as of the mid report, commit `2298112` (17 Oct 2026, the last commit before submission on 22 Oct). The current state is `develop` at `ce49dcc`.

**How each entry was verified:**
- Text errors: quoted from the PDF (via `pdftotext`) or the `.tex` source.
- Figure errors: each PNG in `fyp_report/ThesisFigs/` was opened and inspected.
- Code facts: checked with `git show 2298112:<file>`, `git log`, and `pytest --collect-only` in a worktree at `2298112`.

**Severity:**

| Tag | Meaning |
|---|---|
| **R** | Rubric-affecting: likely to cost marks under Form 2/Form 3, or contradicts the code a panel can inspect |
| **F** | Factual error |
| **C** | Internal inconsistency between two parts of the report |
| **T** | Typo, formatting or cosmetic |

**For the final report:** every entry below must be fixed. The "Fix" column says how. Entries marked **(R)** should also be mentioned in the final report's Design Evolution / Defects sections where relevant, because the panel may have seen the mid version.

**Count:** 69 entries in 7 groups:

| Group | Entries |
|---|---|
| A Numbering and cross-references | 10 |
| B Internal contradictions | 18 |
| C Factual errors in evidence tables | 5 |
| D Figure errors | 18 |
| E Tables | 4 |
| F Template, format and housekeeping | 5 |
| G Rubric-level gaps | 9 |

**Checked and found correct (not errors):**
- The 84 tests and every per-file count in Appendix C match the mid code exactly.
- Section 8.7 for tools, Section 1.10/1.11 references and Chapter 7 references are correct.
- The placeholder Dean, Director, HoD and Coordinator names in `main.tex` are not printed by the class file, so they do not appear in the PDF.
- Constraint C2 is complete in the PDF.

---

## A. Numbering and cross-references

| ID | Sev | Location | Wrong text | Why it is wrong | Fix |
|---|---|---|---|---|---|
| A1 | C | Appendix A, last line (`appendix_action_register.tex`) | "Remaining implementation and validation work is summarized in Chapter 10." | Chapter 10 is *Conclusion*. Remaining work is Chapter 9 *Remaining FYP Plan*. | Use `\ref{}` labels instead of hard-coded numbers. In the final report it becomes Chapter 10 (Remaining FYP Plan) because of the new Chapter 7 |
| A2 | C | Appendix D intro (`appendix_repository.tex` l.3) | "…presented in the report's Chapter 9, Project Management and Development Evidence." | That chapter printed as Chapter 8. | Use `\ref{chap:pm}` |
| A3 | C | Appendix D.3 (`appendix_repository.tex`) | "Chapter 9 discusses cross-module work." | Should be Chapter 8. | Use `\ref{}` |
| A4 | T | `chapters/` file names | `chapter8_testing.tex` printed as Ch 7, `chapter9_development_evidence.tex` as Ch 8, `chapter10_fyp2_plan.tex` as Ch 9 | The mismatch is what caused A1–A3. | Rename the files so file number = chapter number (see `REPORT_STRUCTURE.md` §1.3) |
| A5 | C | Ch 4 §4.3, first sentence | "The five most critical use cases are detailed below." | Six are detailed: UC-01, UC-03, UC-13, UC-05, UC-07, UC-09. | "The six most critical use cases…" |
| A6 | C | Executive Summary, *Requirements and plan* | "…thirty objective acceptance checks…" | Table 4.16 has **31** (AC-01 … AC-31). | Give the real count, generated from the table |
| A7 | C | Executive Summary, *Requirements and plan* | "Chapter 3 sets out four iterations with exit criteria and named owners." | Only Iterations 1 and 2 have exit criteria (Tables 3.4, 3.5). Iterations 3 and 4 are "TBD". | "…four iterations; Iterations 1–2 have exit criteria…" |
| A8 | T | Ch 1 §1.10, Assumption A4 *and* the Feasibility paragraph (`chapter1_introduction.tex` l.306 and l.321) | "The live prototype uses local storage and a 2 FPS sampling target." | The same sentence appears twice, eight lines apart. | Keep it once (in A4) |
| A9 | T | Ch 1 §1.3, first bullet (l.69) | "…to 22% \cite{statista2022} ." | Space before the full stop. | Remove the space |
| A10 | T | Figures 5.7, 5.8, 5.9, 5.10, 5.11 | Titles baked into the images: "Figure 5.x(a): Data flow diagram, Level 0", "(a) Batch frame processing", "(b) Query — Frame 1…", "(b) Query — Frame 2…", "(c) Caregiver query" | These are separate LaTeX figures with their own numbers. The embedded labels duplicate and contradict the captions, and "5.x" is a leftover placeholder. | Remove all titles from the images. Captions come from LaTeX only |

## B. Internal contradictions

| ID | Sev | Location | Contradiction | Fix |
|---|---|---|---|---|
| B1 | C | Table 1.1 (O4) vs Table 1.5 (SC1), AC-09, Table 3.4 exit criterion | O4: "Spatial and temporal question accuracy of at least **60%**". SC1, AC-09 and the Iteration 1 exit criterion all use **70%** for spatial. | Split O4 into spatial ≥ 70% and temporal ≥ 60%, matching SC1/SC2 |
| B2 | C | Table 4.1 vs `\uctable`s vs Appendix B vs "Use-case coverage" paragraph (end of §4.7) | The same use case maps to different FRs in different places (list below) | Pick one mapping per UC (the most specific) and generate all four places from it |
| B3 | C | Use-case names differ between Table 4.1, Fig 4.1 and Appendix B | Name mismatches (list below) | One canonical name per UC, used in the table, diagram and appendix |
| B4 | R | §4.6, first paragraph | "Every requirement of priority H or M is covered by at least one check." | **FR5.7 (priority M)** appears in no acceptance criterion. This was verified by parsing all 31 AC rows against the 38 sub-FRs. | Add an AC for FR5.7 (room clause in explanations, already testable via `tests/test_reasoning.py`), or extend AC-22 |
| B5 | R | AC-03 (Table 4.16) | AC-03 maps to **NFR-R1** (one continuous hour without crash) but its check is a **10-second disconnect**. | No AC actually tests NFR-R1's one-hour requirement: AC-01 uses a 5-minute video. Map AC-03 to FR2.3/FR2.4. Add a one-hour soak AC for NFR-R1 (the final report's TODO P2.1) |
| B6 | C | NFR-U1 vs NFR-U4 vs FR6.1 vs AC-15 | NFR-U1 and AC-15 require a **spoken** query within 60 s; NFR-U4 says speech is "best-effort… not blocking"; FR6.1 says "should". | Make NFR-U1/AC-15 modality-neutral ("speech or text"), or make speech a firm requirement. Speech now exists on-device in both apps, so the final report can raise it |
| B7 | C | FR6.1 | "The system **should** accept spoken queries…" | §4.4 states every requirement uses "shall". | "shall … when speech support is available" |
| B8 | C | Tables 4.12–4.15 (NFRs) | §4.4 defines H/M/L priorities and the traceability relies on them, but the NFR tables have no priority column. | Add a priority column to every NFR table |
| B9 | C | Table 1.2 "Scope split across FYP-1 and FYP-2" | Row M4 has "Iteration 4 (FYP-2)" in the **FYP-1** column and "TBD" in the FYP-2 column. | FYP-1: "—"; FYP-2: "Iteration 4" |
| B10 | F | Ch 1 §1.10, Constraint C2 | "Model training and GPU inference use Modal L4 instances only" | No model is trained anywhere in the project. VGGT-Ω, YOLOE/YOLO-World, SAM 2 (and now SAM3, DINOv3) are used pretrained. | "Model inference uses Modal L4 GPUs; no model is trained or fine-tuned" |
| B11 | F, R | Executive Summary, Abstract, Fig 5.1, §6.7 | "YOLO-World/SAM 2 perception"; Fig 5.1 box "YOLO-World + SAM 2" | At `2298112`, `config/demo.yaml` and `PerceptionConfig` defaulted to `detector_backend: yoloe`, `detector_model: yoloe-11l-seg.pt`. YOLO-World was only an alternative backend (validator accepted `{"yoloe","yolo_world"}`). | "YOLOE (open-vocabulary, YOLO-World as alternative backend) + SAM 2". The final report must say **SAM3** for the shipped `demo.yaml` and **YOLOE** for `live.yaml` |
| B12 | F | Table 8.3 External dependencies, §6.7 | The dependency list omits Depth-Anything-V2 | At `2298112`, `config/demo.yaml` still configured `depth-anything/Depth-Anything-V2-Metric-Indoor-Small-hf` (removed later as dead code in `c4236df`). | Final report: mention its removal in Design Evolution; it is no longer a dependency |
| B13 | C, R | Ch 6 (titled *Iteration 1*), §6.4, §6.5, §6.6, Figs 6.1/6.2 captions | Ch 6 describes the 17 Oct room hierarchy, registry, rooms API and Rerun room depictions in detail. Ch 3 §3.8 and Ch 6 §6.9 say these are **Iteration 2** work. | Final report: Ch 6 keeps only Iteration 1 content; all 17 Oct room work moves to the new Ch 7 (Iteration 2) |
| B14 | R | Ch 1 §1.7 ("M-C … generating short, grounded answers **via a VLM**"); Ch 2 §2.5 ("a VLM generates a grounded answer with evidence"); Fig 1.2; Fig 2.1 | These are worded as the design without saying they are planned. The mid code and the current code have **no VLM on the answer path**: answers are template-composed (`nlq/engine.py`, `memory/reasoning.py`). | Final report: the shipped design is a rule-based closed-vocabulary engine; a VLM/LLM is an optional, off-by-default parser (TODO P1.9). Rewrite these sentences and redraw the figures |
| B15 | F, R | Fig 5.9 (query sequence), `alt [exception or non-200]` | "client-side mock QueryResult is substituted" | This shows the client **fabricating an answer** when the server fails. It contradicts the safe-failure principle (Ch 1 §1.11, FR5.5, SC6). It was a real defect, fixed in `180b897` ("fix(app): never fabricate answers offline"), but §7.7 *Defects* did not list it. | Final report: list it as a defect found and fixed (Ch 8 Defects table). The redrawn sequence shows "Can't reach Aegis memory" (`ApiService.unreachableMessage`) instead |
| B16 | F | Fig 5.4 caption vs image | Caption: "Conceptual class model for existing … and **proposed user, caregiver, access-grant, summary, evidence and audit concepts**" | The image contains only five implemented classes (`Relative4DSceneGraph`, `SpatialAnchor`, `ObjectMemoryEntry`, `BoundingBox3D`, "Event record"); no proposed concept is drawn. It also duplicates Fig 6.1. | Final F5.5 is a true conceptual domain model with the planned concepts drawn dashed (see `DIAGRAM_SPECS.md`) |
| B17 | C | Fig 7.1 (test levels) vs §7.4 | Fig 7.1 badge: "Solid, **includes the 4 failures**". §7.4: "84 passed (84/84)". | Stale label from an earlier run. Final F8.1 shows real per-tier counts |
| B18 | F | Fig 1.2 (system context) | The VLM & speech-to-text box is labelled **"on-device"**, but §1.6 says it is drawn dashed "because it is not yet decided whether they run in the cloud or on the device". The caregiver box says **"authenticated access"**, but no authentication exists. | Final F1.2 shows the actual externals (Modal, Hugging Face, Android STT on-device) with authentication marked planned |

**Use-case mappings that disagree (B2):**

| UC | Table 4.1 | `\uctable` / Appendix B | Coverage paragraph |
|---|---|---|---|
| UC-02 | FR6, FR7 | FR5, FR6, FR7 | — |
| UC-04 | FR3, FR4, FR5, FR7 | — | FR3, FR4, FR5 |
| UC-09 | FR3, FR8 | FR3.2, FR5.1, FR8.2, FR8.3 | FR5, FR8 |
| UC-10 | FR4, FR8 | FR3, FR4, FR8 | FR5, FR8 |
| UC-13 | FR3.7, FR8.6 | FR3.6, FR3.7, FR8.6 | — |

**Use-case names that disagree (B3):**
- UC-05: "Ask what I did earlier (activity recall)" / "Recall Earlier Activity" / "Recall an earlier activity".
- UC-08: "Caregiver requests an in-scope history answer" / "Caregiver Queries Episodic History".
- UC-12: "Maintain memory (compaction)" / "Maintain memory / compact history" / "Maintain Memory by Compaction".

## C. Factual errors in evidence tables

| ID | Sev | Location | Wrong text | Evidence | Fix |
|---|---|---|---|---|---|
| C1 | F, R | Table 3.8 Progress, rows "M1: frame stream capture", "M1: keyframe optimisation", "M2: anchor database" | "Commit d82dc30; repository history dates this evidence to **2026-10-04**" | `git log -1 d82dc30` gives author and commit date **2026-09-01** ("feat: implement R4DSG spatio-temporal memory…"). | Correct the date. A wrong date in the evidence table is exactly what the "dishonest milestone logging" red flag looks for |
| C2 | F | Table 8.1, row Faizan | "Observed commit evidence: 2026-10-04–2026-10-17" | First `pez-Ox` commit is `d82dc30` on 2026-09-01; the repo starts 2026-08-24 (`c56ce37`, "Faizan Ur Rehman Khan"). | "2026-08-24 – 2026-10-17" |
| C3 | F | Table 8.1, row Ali Sher | "`Ali Sher`/`Ali-Sher12`; 14 commits" | `git log 2298112` shows one identity, `Ali Sher` (14 commits). `Ali-Sher12` is not a Git author identity in the history (it may be a GitHub handle; if so, say so). | "`Ali Sher` (GitHub `Ali-Sher12`)" or drop it |
| C4 | C | Fig 5.5 note | "event_type is pickup, placement, anchor_change or state_change." | At `2298112` the scene graph already emitted `room_change` events (`a15c108`; three occurrences in `memory/scene_graph.py`). | Final F5.6 lists the full set: `pickup`, `placement`, `anchor_change`, `state_change`, `room_change`, plus `moved_while_unobserved` in the store |
| C5 | F | §5.3 Interfaces | Lists GET routes and `POST /api/v1/rooms/rename` | At `2298112` the API also had `POST /api/v1/simulate_transition`, `POST /api/v1/reset` and the `GET /api/v1/simulate/*` presets (the mid caption of Fig 5.2 even mentions "simulation/reset"). They are mutating routes and were not in the interface list. | Final API contract table lists every route (`DIAGRAM_SPECS.md`, F5.2 and Table T5.2 in `NEW_CONTENT.md`) |

## D. Figure errors (by figure)

| ID | Sev | Figure (file) | Problems | Fix (see `DIAGRAM_SPECS.md`) |
|---|---|---|---|---|
| D1 | R | Fig 3.1 `chapter3-gantt.png` **and** Fig 8.1 `chapter8-gantt..png` | Problems listed below | F3.1 = real plan-vs-actual Gantt; F9.1 = per-member weekly commit timeline |
| D2 | R | Fig 4.1 `fig-4.1.png` (use case) | Problems listed below | F4.1 |
| D3 | R | Fig 5.1 `chapter5-layered-architecture.png` | Problems listed below | F5.1 |
| D4 | R | Fig 5.2 `chapter5-component-interfaces.png` | Problems listed below | F5.2 |
| D5 | R | Fig 5.3 `chapter5-deployment.png` | Problems listed below | F5.3 |
| D6 | R | Fig 5.4 `chapter5-domain-model.png` | See B16. Also: attributes partly typed ("center, size" untyped); no operations; "Event record" as a «dictionary» class | F5.5 |
| D7 | R | Fig 5.5 `chapter5-json-schema.png` | No `rooms[]` (caption admits it); event-type note incomplete (C4); shows only the v1 `timeline{}` form | F5.6 (schema v2) |
| D8 | R | Fig 5.6 `chapter5-ui-wireframes.png` | Problems listed below | F5.9, F5.10 (screen flows) plus real screenshots F7.5/F7.6 |
| D9 | R | Fig 5.7 `dfd.png` | Problems listed below | F5.11 (level 0) and F5.12 (level 1) |
| D10 | R | Fig 5.8 `chapter5-batch-sequence.png` | Problems listed below | F5.13 |
| D11 | R | Fig 5.9 `query-sequence.png` | Problems listed below | F5.14 |
| D12 | C | Fig 5.10 `queryframe2planned-dequence.png` | Problems listed below | F5.14 now covers voice (implemented); planned items go in F5.19 |
| D13 | T | Fig 5.11 `caregiverquerysequence.png` | Problems listed below | F5.15 |
| D14 | R | Fig 6.1 `classdiagram(a).png` | Problems listed below | Keep as the Iteration 1 record (rename, fix notation); F7.1 is the new memory class diagram |
| D15 | R | Fig 6.2 `classdiagram(b).png` | Problems listed below | Same as D14; F7.2 is new |
| D16 | C | Fig 7.1 `testlevel.png` | "includes the 4 failures" (B17); not a pyramid; no counts; the API-tier description says "simulation" without saying those routes are simulator-gated | F8.1 |
| D17 | T | Several PNGs (`fig-4.1`, `chapter5-layered-architecture`, `chapter5-component-interfaces`, `chapter5-deployment`, `chapter5-domain-model`, `chapter5-json-schema`, `classdiagram(a)`, `classdiagram(b)`) | Transparent backgrounds: fine in print, black in dark-mode PDF viewers and in screen sharing during the defence | Export all new figures with an opaque white background |
| D18 | T | `ThesisFigs/room-commit-timeline.svg` | Unused file. `\aegisfig` only loads `.png`, so it could never be included | Delete it |

**D1 problems (the Gantt / timeline figure):**
- The two figures are the **same image** (identical md5 `4ffa7887…`) used for two different captions.
- It is **not a Gantt chart** and not a "commit-evidence timeline through 2026-10-17". It lists 8 commits by one member (`pez-Ox`) on **one day** (17 Oct).
- It shows no plan, no other members and no iteration bars.
- The file name `chapter8-gantt..png` has a double dot.

**D2 problems (use case diagram):**
- UC-13 is missing (the caption admits it).
- No «include»/«extend» relationships.
- Actor lines run **through** other use cases: Primary user → UC-01 crosses UC-02, and → UC-11 crosses UC-07.
- The four ellipse colours are not in the legend.
- UC-10 (summaries, not implemented at mid) is drawn solid with a "partial" tag.
- UC-12 «system» has no actor connection.

**D3 problems (layered architecture):**
- "YOLO-World + SAM 2" (B11).
- No room estimation, room binding or `home_map.json` registry, although they were implemented.
- The batch arrow from `preprocess_video` is routed **through** the live-path boxes, visually suggesting the live path feeds VGGT. That contradicts the red "No automatic downstream processing connection" bar.

**D4 problems (component diagram):**
- Typo `/data//video.mp4` (missing `<dataset_id>`).
- Overlapping labels: "Local live path (independent)" is covered by a box, and "metadata, poses, poi…" is cut off under a note.
- Room endpoints and registry are missing (the caption admits it).
- Lollipop/socket notation is used on only two connectors, although the legend defines it.

**D5 problems (deployment diagram):**
- "Uvicorn on 0.0.0.0:, default 8000" (port missing after the colon).
- "captures// —" (missing session segment).
- "Local capture process (OpenCV)" is drawn inside the **phone** node, but it runs on the laptop (`aegis-ingest`).
- Nodes are not UML «device»/«executionEnvironment» stereotypes.

**D8 problems (UI wireframes):**
- Grey placeholder bars only: too low fidelity to evidence the panel's "fix the app design" action.
- Truncated label "Time / persistent-memory statu."
- Displays a red "No speech recognition" banner inside the product wireframe.
- The caption claims it "reflects the Flutter client".

**D9 problems (DFD):**
- The title embedded in the image says "Level 0", but the diagram has **five processes** (P1–P5), which makes it a Level-1 DFD; there is no Level-0 context DFD.
- The flows "config / stage submission" and "artifacts" have floating labels with no attached arrows.
- One bidirectional arrow carries two different flows.
- Room estimation and registry flows are missing (the caption admits it).

**D10 problems (batch sequence):**
- `/data//video.mp4` typo.
- "Memory builder" is drawn as a separate participant, but in code it runs inside the detect worker (`run_detect_and_lift` → `build_relative_4d_scene_graph`).
- The loop guard label is overprinted by the lifeline.
- No room estimation, binding or registry steps (the caption admits it).
- Gravity estimation was not yet present then; the final version must add it.

**D11 problems (query sequence):**
- The message PatientView → ApiService is labelled `_executeQuery(item)`, the same as the PatientView self-call, so the ApiService method is mis-named.
- Two separate `alt` frames are used instead of one `alt` with `[no match]` / `[match]` operands.
- "3 s timeout" is shown.
- Mock-answer substitution (B15).
- Room parameters are not shown (the caption admits it).

**D12 problems (planned spoken-query sequence):**
- No user/UI lifeline.
- The final reply returns to the **ASR service** lifeline instead of the user.
- File name typo "dequence".

**D13 problems (caregiver sequence):**
- Self-messages ("pull-to-refresh", "search-history card") are drawn after the activation bar has ended.
- Repetition should be a `loop` fragment.
- The caption itself says the figure is "earlier" and does not show the rooms API.

**D14 problems (class diagram a):**
- Attributes are listed as untyped comma lists, with no visibility and no operations compartment.
- **Two** relationships (an association 0..1–0..* and a «derives» dependency) connect the same pair, `BoundingBox3D`–`ObjectMemoryEntry`.
- `RoomRegion`, `HomeRoomRegistry`/`HomeRoomRecord` are missing, although implemented on 17 Oct (the caption admits it).

**D15 problems (class diagram b):**
- **A leftover authoring instruction is printed inside the figure:** "Generated from or checked against src/aegis/; confirm names against the repository before export."
- The Pydantic models are drawn name-only with the note "fields not listed in the specification".
- `QueryReasoningEngine` shows 2 of its 5 methods (missing `extract_room_filter`, `strip_room_words`, `item_phrase`).
- `RoomModel` is missing, although the rooms API existed.

## E. Tables

| ID | Sev | Table | Problem | Fix |
|---|---|---|---|---|
| E1 | R | Table 3.8 *Progress against plan* | The "Planned date" column is **empty in every row**. The rubric (Form 2 #2) scores planned-vs-actual with justified delays. | Fill planned week/date for every row; add a variance column |
| E2 | R | Table 8.4 *Unscored risk register* | No likelihood, impact or score. | Add Likelihood (1–5), Impact (1–5), Score, Owner and Trigger columns |
| E3 | C | Table 4.17 *Traceability* | FR6 (speech) cites `test_reasoning.py` as test evidence, but that file tests text parsing only | State "no speech test" (at mid). The final cites the Flutter widget tests for the voice flow |
| E4 | C | Table 3.3 vs 3.6 vs 3.7 | Three overlapping responsibility tables in one chapter, plus Tables 8.1 and 8.2 in Ch 8. The M-C lead (Ali Sher) is described differently in each | Final report: one responsibility table in Ch 3 and one evidence table in Ch 9 |

## F. Template, format and housekeeping

| ID | Sev | Item | Problem | Fix |
|---|---|---|---|---|
| F1 | T | `main.tex` | `\usepackage{blindtext}` is loaded but unused (dummy-text package from the template) | Remove |
| F2 | T | `fyp_report/README.txt` | Describes `figures/` and `tables/` folders that do not exist (figures are in `ThesisFigs/`) | Update or delete |
| F3 | T | `fyp_report/best` | A stray older copy of `main.tex` with different `\needspace` values | Delete (do not copy into the final) |
| F4 | T | `main.tex` | `\deanname`, `\directorname`, `\hodname`, `\fypcoordinatorname` are placeholders. They are **not printed** in the PDF (the class does not use them), so there is no visible error, but fill them in case the final template prints them | Fill with real names |
| F5 | T | `\degreemonth{October}` | Correct for the mid report; must change for the final | Set the final month |

## G. Rubric-level gaps (not wrong, but marked down under Form 3)

| ID | Rubric item | Gap in the mid report | What the final report must do |
|---|---|---|---|
| G1 | F3-5 / F3-6 Design (25 marks) | Chapter 5 has **11 figures and only 3 short paragraphs** (36 lines of LaTeX). Most figures have no explanatory text at all. The rubric caps design marks when diagrams are "purely decorative" or unexplained. | One explanatory paragraph per figure (what it shows, how to read it, which code it maps to). See `NEW_CONTENT.md` Ch 5 |
| G2 | F3-5 | Most Chapter 5 captions say the figure is out of date ("Earlier…", "not yet depicted", "described in the text but not depicted"). The panel reads this as "diagrams do not match the code". | Redraw every figure to match `develop`; captions describe, never apologise |
| G3 | F3-7 Implementation (15 marks) | §6.4 is one paragraph and §6.6 is one paragraph. There are no algorithm descriptions, no parameter table and no trade-offs. | Ch 7 package-by-package walk-through, algorithms, parameter table, trade-offs |
| G4 | F2-7 / F3-8 Testing | §7.7 *Defects and Corrective Actions* lists scope gaps ("missing benchmark labels, absent ASR…"), not defects. A real defect (B15) was not reported. | A real defect table: defect, how found, fix, commit, test added |
| G5 | F3-8 Tool disclosure | §8.7 lists tools but not **which member used which tool for what**, nor how the output was checked. The gate scores the tool item 0 until disclosure is complete. | Per-member disclosure table |
| G6 | F2-1 Action register | Table 3.1 / Appendix A give status but **no evidence link** per action (commit, file, figure). | Add an Evidence column with concrete links |
| G7 | F3-1 Format | Appendix E *Additional Design Diagrams* contains one sentence and no diagrams. | Fill it or remove it |
| G8 | F2-6 Repository evidence | No branch/merge evidence and no tag evidence in the report, although tags `v0.1.0-mid1` (`4419832`) and `v0.2.0-mid2` (`678acbd`) exist. | Add the branch graph (F9.2) and cite tags |
| G9 | F3-2 R&D | Chapter 2 is literature-only. No experiment by the team informs any design decision. | Add the team's own experiments (detector A/B, compaction audit, EgoLife) as evidence for decisions |
