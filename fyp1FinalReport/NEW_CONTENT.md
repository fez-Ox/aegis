# FYP-1 Final Report: New and Updated Content

This file holds the **content** to put into the final report, chapter by chapter, following the mid-report structure with one new chapter (Chapter 7, Iteration 2). Structure decision: keep both iterations for now (Ch 6 = Iteration 1 frozen, Ch 7 = Iteration 2).

**Related files:**
- `REPORT_STRUCTURE.md`: outline, rules and checklist.
- `DIAGRAM_SPECS.md`: every figure (IDs F1.2 … F10.1 used below).
- `MID_REPORT_ERRATA.md`: mistakes to fix (IDs A1 … G9 used below).

**Conventions in this file:**
- **[KEEP]**, **[UPDATE]**, **[NEW]** tag each section.
- Text in `> quote blocks` is **draft prose** ready to adapt into LaTeX. Keep the report's British spelling ("summarised", "organised").
- `[[TEAM INPUT: …]]` marks facts that are not in the repository and must come from the team.
- Every number has a source. Numbers were measured on `develop` at `ce49dcc` (24 Nov 2026). **Re-run the counts on the submission commit** and replace them: tests, commits, vocabulary size.
- Status words: **Implemented**, **Partial**, **Planned**, **Measured** / **Unmeasured** (`REPORT_STRUCTURE.md` §2.1).

---

## Front matter

### Students' Submission [UPDATE]

> We certify that this report is submitted as the FYP-1 final report for the project titled **Aegis: A Spatio-Temporal Memory System for Assistive Care**.

### Anti-Plagiarism Statement [KEEP]

### Authors' Declaration [UPDATE]

> We declare that the work documented in this report represents the work completed by the project team up to the end of FYP-1. Contributions, tools, external components and relevant sources are disclosed where applicable. Generative-AI tools were used as coding and drafting aids; they are disclosed per member in Section 9.7, and all technical claims, designs and results remain the responsibility of the team.

### Abstract [UPDATE: paragraph 2 replaced]

Keep paragraph 1 unchanged. Replace paragraph 2 with:

> The project follows an iterative, vertical-slice approach. Iteration 1 (to the mid-evaluation) delivered the batch reconstruction, perception and scene-graph slice. Iteration 2 turned it into a single end-to-end pipeline:
> - live phone capture with criterion-based keyframes, gap and pause records and crash-safe resume;
> - a gravity-aligned spatial model with nine object–anchor relations;
> - debounced object state runs;
> - a persistent per-home SQLite memory with cross-session matching of rooms, anchors and objects;
> - verified three-day-then-summary compaction;
> - a rule-based, closed-vocabulary query engine served from Modal over HTTPS;
> - patient and caregiver Flutter applications with on-device speech input.
>
> The automated suite has 451 passing tests (79% line coverage). Component measurements show:
> - open-vocabulary detection F1 of 0.721 on a ten-frame, five-environment hand-labelled benchmark;
> - 5.7–7.2× smaller memory with 100% semantic retention on two short clips.
>
> A seven-day public egocentric study (EgoLife) found that individual objects remained in memory for one to four days, but class-level queries did not yet benefit from the longer history. Temporal questions, calibrated confidence, caregiver authentication, latency and usability remain unmeasured or planned for FYP-2.

**Keywords (add):** scene graph, natural-language querying.

### Acknowledgments [KEEP]

Optional addition:

> We also thank the authors of VGGT-Ω, SAM 2, SAM 3, DINOv3 and the EgoLife dataset for making their models and data publicly available.

### Executive Summary [UPDATE]

| Paragraph | Draft |
|---|---|
| Motivation | KEEP |
| Project | KEEP. Replace "a consent-based caregiver portal" with "a separate caregiver application (consent-based access is planned)". |
| Research findings | KEEP the first part, then add: "Since the mid-evaluation the team ran its own component experiments: a detector comparison that replaced YOLOE with SAM 3, a memory-compaction audit, and a seven-day EgoLife study that exposed cross-session room-identity instability (Section 2.9, Chapter 8)." |
| Requirements and plan | "Chapter 4 specifies eight top-level functional requirements with **[[count after Ch 4 changes]]** sub-requirements, **[[count]]** non-functional requirements, **[[count]]** acceptance checks with their FYP-1 results, a traceability matrix and a requirements change log. Chapter 3 records two completed iterations against plan and two remaining iterations for FYP-2." |
| Implementation and validation status | "Iteration 2 delivered live capture, a gravity frame, nine spatial relations, state runs, a persistent home store with cross-session matching, verified compaction, the NLQ engine and `/ask` endpoint on Modal, and patient and caregiver apps (Chapter 7). The suite has 451 passing tests at 79% coverage. Measured results are detection F1 0.721, compaction 5.7–7.2× with 100% semantic retention, one end-to-end run, and the EgoLife study. Accuracy on a held-out clip, latency p95, room metrics and usability remain unmeasured." |
| Risks and remaining work | "The three main risks are now: (1) cross-session room identity, because room linking uses an absolute radius in scale-free reconstruction units; (2) temporal and activity questions, which the engine currently declines; and (3) the absence of authentication and encryption. FYP-2 addresses these in Iterations 3 and 4 (Chapter 10)." |

### List of Abbreviations [UPDATE]

Add these rows and keep the table alphabetical:

| Abbreviation | Meaning |
|---|---|
| API | Application Programming Interface |
| ASR | Automatic Speech Recognition |
| CCP | Complex Computing Problem |
| CI/CD | Continuous Integration / Continuous Deployment |
| CORS | Cross-Origin Resource Sharing |
| DFD | Data Flow Diagram |
| ERD | Entity–Relationship Diagram |
| FP | False Positive |
| GPU | Graphics Processing Unit |
| IoU | Intersection over Union |
| LLM | Large Language Model |
| MJPEG | Motion JPEG |
| NLQ | Natural-Language Query |
| NMS | Non-Maximum Suppression |
| OBB | Oriented Bounding Box |
| R4DSG | Relative 4D Scene Graph |
| RANSAC | Random Sample Consensus |
| Re-ID | Re-identification |
| SAM | Segment Anything Model |
| STT | Speech-to-Text |
| UTC | Coordinated Universal Time |
| VGGT | Visual Geometry Grounded Transformer |

---

## Chapter 1: Introduction and Project Vision

**§1.1–1.4 [KEEP].** Fix errata A9 (space before the full stop in §1.3).

### §1.5 Project Objectives [UPDATE]

Table 1.1 gets a new column, **Status at FYP-1 end**. Fix B1 by splitting O4.

| ID | Objective (unchanged) | Measure (O4 fixed) | Status at FYP-1 end |
|---|---|---|---|
| O1 | Continuously capture and ingest | ≥ 1 h without crash or stall | **Partial**: live capture with reconnect, gaps, pause and resume implemented and tested (`ingestion/live_pipeline.py`, 64 ingestion tests); 1-hour soak not run (P2.1) |
| O2 | Spatio-temporal memory of rooms, objects, layout, activities | Room segmentation ≥ 0.90; correct-room ≥ 0.90 | **Partial**: implemented (rooms, anchors, relations, state runs, activities); room metrics **Unmeasured** (P2.3) |
| O3 | Compress older history, keep recent detail | Sub-linear growth; ≤ 15-point drop | **Partial**: compaction implemented and verified; 5.7–7.2× on short clips; accuracy drop after compaction **Unmeasured** |
| O4 | Answer NL spatial and temporal queries with grounded responses | Spatial ≥ 70%, temporal ≥ 60%; every answer cites evidence | **Partial**: spatial queries implemented with evidence; temporal **Planned** (engine declines); accuracy **Unmeasured** (`demo05` not annotated) |
| O5 | Speech and text through an accessible interface | First-time user, one query, ≤ 60 s | **Partial**: on-device speech and text in both apps; usability study not run |
| O6 | Authorised, consent-based caregiver access | 100% rejection of unauthorised attempts | **Planned**: Caregiver App exists; no authentication (P1.7) |
| O7 | Evaluate against structured ground truth | Dataset selected and documented | **Partial**: evaluation harness built; EgoLife used for multi-day study; Ego4D NO-GO (0/100); held-out `demo05` NOT_READY |

### §1.6 Project Scope [UPDATE]

Keep the in-scope and out-of-scope text. Add one sentence:

> Evaluation now uses a public seven-day egocentric dataset (EgoLife, participant A1_JAKE) for multi-day persistence, alongside a frozen held-out care-style clip (`demo05`); Ego4D was assessed and is not pursued in FYP-2 unless access, data and an official scorer become available (Section 8.8).

Table 1.2 (fixes B9):

| Scope item | FYP-1 | FYP-2 |
|---|---|---|
| Capture and ingestion (M1) | Iterations 1–2: batch, live capture, keyframes, gaps, segments | Hardening: 1-hour soak, disconnect recovery measured |
| Spatio-temporal memory and three-day retention (M2) | Iterations 1–2: rooms, relations, state runs, home store, compaction | Room-identity fix, metrics, long-term persistence study |
| Query engine (M3) | Iteration 2: closed-vocabulary location queries, ranking, abstention, on-device speech | Iteration 3: temporal and activity answers, calibrated confidence, evidence references |
| Caregiver access, security, performance (M4) | Iteration 2: Caregiver App (unauthenticated) | Iteration 4: authentication, grants, audit, encryption, latency and usability validation |

Redraw **F1.2** and replace the old context paragraph with:

> Figure 1.2 fixes the system boundary of the FYP-1 prototype. The primary user and caregiver are outside the boundary and reach Aegis through two Android applications. The wearer's phone acts only as a camera, streaming MJPEG over Wi-Fi. Heavy computation runs on Modal, and model weights come from the Hugging Face Hub. Speech is transcribed on the user's phone by the Android speech service, so no audio reaches Aegis. Authentication and consent services are drawn dashed because they are planned for FYP-2.

### §1.7 Project Modules [UPDATE]

Table 1.3:

| ID | Name | Responsibility (updated) | FRs | Lead |
|---|---|---|---|---|
| M-A | Capture and Ingestion | Live phone capture, keyframe selection, gap/pause records, crash resume, promotion into bounded segments, batch video normalisation | FR1, FR2 | Shahmeer |
| M-B | Spatio-Temporal Memory | Gravity frame, 3D lifting, relations, state runs, events, rooms, per-home store, cross-session matching, activities, evidence, compaction | FR3, FR4 | Faizan |
| M-C | Query Engine | Closed-vocabulary NLQ, ranked candidate retrieval, abstention, answer wording | FR5, FR6 | Ali Sher |
| M-D | Interfaces and Caregiver Access | Patient and Caregiver apps, API routes, deployment; authentication planned | FR7, FR8 | Shahmeer |

Replace the "Module responsibilities" paragraph (fixes B14):

> M-A turns the phone's MJPEG stream into a disciplined feed of timestamped keyframes and owns ingestion reliability. M-B owns the memory: it converts reconstructed geometry and detections into rooms, anchors and objects, records each object's stable states and the events between them, merges sessions into a persistent per-home store and compacts history older than three days into verified summaries. M-C owns understanding: it maps a question to a known object using a closed vocabulary, retrieves and ranks candidates from memory, and composes a short answer from a template, or declines when evidence is missing. No language model writes answer text. M-D owns access: the patient and caregiver applications and the HTTP API. Leads are responsibility assignments; Iteration 2 work crossed module boundaries, and Chapter 9 records who built what.

Redraw **F1.3**.

### §1.8 Stakeholders [KEEP]

### §1.9 Success Criteria [UPDATE]

Table 1.5 gets a new column, **FYP-1 evidence**:

| ID | Criterion | Threshold | FYP-1 evidence |
|---|---|---|---|
| SC1 | Spatial retrieval accuracy | ≥ 70% | **Unmeasured**: held-out `demo05` annotations missing (readiness: NOT_READY) |
| SC2 | Temporal retrieval accuracy | ≥ 60% | **Unmeasured**: temporal intent not implemented |
| SC3 | Accuracy retained after compaction | drop ≤ 15 points | **Partial**: 100% query agreement on auto-generated probes (demo03/04); human-query comparison unmeasured |
| SC4 | End-to-end latency p95 | ≤ 5 s | **Unmeasured** (P2.8) |
| SC5 | Evidence grounding | 100% of non-abstaining answers | **Partial**: `/ask` and `/query` return evidence; coverage not audited (P1.4) |
| SC6 | Safe failure | verified on unanswerable queries | **Partial**: abstention unit tests (`test_nlq.py`); EgoLife `keys`/`wallet` abstention probes; calibrated threshold planned (P1.2) |
| SC7 | Caregiver access control | no unauthorised access | **Not met**: no authentication yet (P1.7) |
| SC8 | Usability | 5 participants unaided | **Unmeasured**: needs ethics approval |
| SC9 | Room-level memory | seg ≥ 0.90, F1 ≥ 0.70, correct-room ≥ 0.90 | **Unmeasured** (P2.3); identity instability observed on EgoLife |

### §1.10 Constraints and Assumptions [UPDATE]

- **C2 (fixes B10):**
  > Model inference uses Modal L4 GPUs; no model is trained or fine-tuned. One five-minute segment costs about 0.086 GPU-hours (≈ US$0.069: VGGT 200 s, detection 108 s); the 74-segment EgoLife study cost US$8.71 metered. A CPU fallback (`AEGIS_GPU=cpu`) runs the same stages without a GPU at much higher latency (VGGT 831 s for 79 frames).
- **C4:**
  > EgoLife (A1_JAKE, seven days, 12:00–13:00) is used for the multi-day study; a held-out care-style clip (`demo05`) is frozen for accuracy scoring; Ego4D was assessed as NO-GO (0/100 readiness, about 10.8 weeks of prerequisites).
- **New A9:**
  > VGGT-Ω weights are taken from `facebook/VGGT-Omega` when access is granted, otherwise from the public mirror `wincentIsMe/VGGT-Omega` (same weights and licence).
- **Remove the duplicate sentence (A8).**

### §1.11 Ethics, Legal, DEI [UPDATE]

Add:

> **Data used in FYP-1.** Team recordings include only consenting team members. EgoLife is a public dataset of consenting volunteers and is used for evaluation only; its frames are processed on Modal and not redistributed. Object-only evidence crops (at most 320 px) are kept so answers can show a photo; this exceeds the 24-hour raw-frame rule in NFR-S4 and is recorded as supervisor decision #9 (it can be disabled with `memory.evidence.enabled`).
>
> **Current security status.** The API has no authentication, allows any origin (CORS `*`) and both apps permit cleartext HTTP on a LAN for development. This is acceptable only for a single-user prototype with test data and is the main FYP-2 security work (Section 9.10).

---

## Chapter 2: Research and Existing Solutions

**§2.1 [UPDATE]**, add:

> In Iteration 2 the team added a fourth strand: its own component experiments. Where a choice between methods could not be settled from the literature, it was measured on the project's own data (Section 2.9).

**§2.2 [KEEP].**

**§2.3 [UPDATE]**: Table 2.1, Aegis column (rename it "Aegis (FYP-1)"):

| Criterion | Aegis (FYP-1) |
|---|---|
| Sensing input | Phone RGB camera (worn), MJPEG |
| Memory form | Rooms → anchors → objects; state runs and events; per-home SQLite store |
| Temporal abstraction | Implemented: three-day detail, verified day summaries, week/month roll-up |
| Interface | Patient and caregiver apps; text, on-device speech, object tiles |
| Caregiver support | Caregiver app with history, rooms, enrollment; consent-scoped access planned |
| Scaling approach | State runs (size independent of video length) + compaction |

**§2.4–2.6 [UPDATE lightly]**:
- §2.4 gap item 2, last sentence: "…retention of room identity through compaction is now verified by construction (rooms are never compacted), but its effect on query accuracy is unmeasured."
- §2.5: redraw **F2.1**; replace "and a VLM generates a grounded answer" with "and a template composes the answer from the retrieved state; a language model is optional and off by default".

**§2.6 CCP**: add a column **Evidence (FYP-1)** to Table 2.2. Rows 1 and 8:

| # | Evidence (FYP-1) |
|---|---|
| 1 | Measured trade-off: snapshot interval 1 keeps exact geometry at 1.5–1.9× compression; interval 0 gives 5.7–7.2× with centre p95 error 0.22–0.36 scene units (Section 8.6) |
| 8 | Changing the detector (YOLOE → SAM 3) changed which objects exist in memory at all (0/36 → 34/42 shoes); room-linking radius changed cross-session identity (Section 8.8) |

### §2.7 Technical Challenges [UPDATE]

Table 2.3 gets a column **What we found in FYP-1**:

| ID | What we found in FYP-1 |
|---|---|
| TC1 | Appearance re-ID moved from HSV histograms to DINOv3 embeddings; multi-instance identity and occlusion permanence are tested (`test_association`, `test_scene_graph`); not yet measured on ground truth |
| TC2 | Compaction verifies each summary against its source rows before deleting detail; a failed day keeps all rows |
| TC3 | Criterion keyframes reject dark (< 20), bright (> 245), blurred (Laplacian < 15) and duplicate (< 0.8% change within 2 s) frames |
| TC4 | VLM removed from the answer path; GPU used only for reconstruction and detection; Modal warm-down 2 s |
| TC5 | Closed vocabulary + templates; the engine declines unknown items, unobserved items, temporal and activity questions |
| TC9 | EgoLife chosen for multi-day; Ego4D NO-GO |
| TC10 | Gravity frame from a RANSAC floor fit gives "above / under / on floor" without metric scale |
| **TC12 (new)** | **Cross-session room identity under scale-free reconstruction.** `zone_link_radius` (1.5) is an absolute distance in VGGT units, but VGGT scale differs per reconstruction. On two EgoLife segments one produced four rooms and the next one room, matched to the wrong home room. Mitigation: scale-relative linking using the gravity frame's camera-height unit (Iteration 3) |

### §2.8 Findings → Decisions [UPDATE]

Add these rows to Table 2.4:

| Finding (source) | Decision |
|---|---|
| YOLOE found 0/36 shoes and 0/19 hands; SAM 3 found 34/42 and 19/19 (team benchmark, §2.9) | SAM 3 is the default detector for recorded video; YOLOE stays available for live use |
| Per-frame timelines grow with frames × objects (team memory audit) | Store debounced **state runs** instead; graph size independent of video length |
| A free-form language model can produce a plausible but unsupported location (TC5) | Closed vocabulary + template answers; LLM only as an optional parser (P1.9) |
| VGGT-Ω places the origin at the first camera; "up" is unknown | Estimate gravity from a RANSAC floor fit; store it beside raw coordinates |
| JSON graphs cannot merge sessions or survive restarts efficiently | Per-home SQLite store with stable room, anchor and object identities |
| Class-level queries cannot distinguish two mugs (EgoLife tiers) | Ranked top-3 candidates with photos and an explicit ambiguity flag; personal-item enrollment |

**References to add** (check each one yourself): SAM 3; DINOv3; YOLOE; EgoLife (dataset/paper, already cited as `egolife2025`, check); RANSAC (Fischler & Bolles, 1981); Flutter `speech_to_text` (software).

### §2.9 Model and Method Selection Experiments [NEW]

> **Object detection.** Open-vocabulary detection decides which objects can ever enter memory. The team hand-labelled a small benchmark (10 frames, 960×540) from five different videos — a shoe cabinet, a kitchen, a bathroom/waste area, laundry and a dish rack — with 116 objects, drawn by inspecting raw frames rather than pipeline output. Detections were scored class-aware at IoU ≥ 0.30 after per-class non-maximum suppression (IoU 0.7). Table 2.5 and Figure 2.3 compare five variants on a Modal L4 GPU.
>
> YOLOE, the previous default, found none of the 36 shoes or 19 hands. YOLO-World found 11 shoes but no hands. SAM 3 with an 18-class prompt set and category-level thresholds (shoes 0.5, hand 0.4, cooking pot 0.6, trash bin 0.4, food container 0.9, others 0.8) reached F1 0.721, and was adopted. The thresholds are category priors, not tuned per video. Every alternative tried (prompt-word variants, NMS sweeps, cross-class suppression, flip test-time augmentation) was rejected when it regressed any video or gained less than 0.005. The benchmark is small, so the result guides the choice of detector; it is not a general accuracy claim.

Table 2.5: copy the five-row table from `DIAGRAM_SPECS.md` F2.3. Figure: **F2.3**.

---

## Chapter 3: Proposal and Mid-Evaluation Feedback, and Iteration Plan

### §3.1 Proposal Feedback Summary [KEEP]

### §3.2 Proposal Action Register [UPDATE]

Table 3.1 gets an **Evidence** column (fixes G6):

| No. | Required modification | Response (FYP-1 final) | Evidence | Status |
|---|---|---|---|---|
| 1 | Narrow scope, define persistence | Three-day detail window and verified summaries implemented; week/month roll-up | `memory/compaction.py`, `core/config.py` `RetentionConfig(hot_days=3)`, `tests/test_compaction.py` (14 tests) | Addressed (implemented); accuracy after compaction unmeasured |
| 2 | Define the CCP | Fidelity–storage trade-off now measured | Table 2.2, Section 8.6, `evaluation/reports/memory_control/summary.md` | Addressed |
| 3 | Define GPU, storage, devices | Constraint C2 with measured cost per segment; deployment diagram | Section 1.10, Fig 5.3, `docs/egolife.md` (cost) | Addressed |
| 4 | Fix the app design | Two new apps (patient, caregiver), espresso/ochre theme, large tiles, voice | `apps/Patient App/`, `apps/Caregiver App/`, Figs 5.9, 5.10, 7.6, 7.7 | Partially addressed: usability study pending |

### §3.3 Mid-Evaluation Feedback Summary [NEW]

> [[TEAM INPUT: supervisor's mid-evaluation comments and marks (Form 2 / Form 3), verbatim where possible, with the date]].

### §3.4 Mid-Evaluation Action Register [NEW]

Columns: No. · Feedback item · Action taken · Evidence · Status. Pre-filled from the supervisor follow-ups already recorded in the mid report's Appendix F; add the real mid-evaluation items:

| No. | Feedback item | Action taken | Evidence | Status |
|---|---|---|---|---|
| M1 | Keep claims tied to repository/test evidence (13 Oct) | Single source of truth `CONTEXT.md`/`TODO.md`; every status in this report cites a file, commit or test | `CONTEXT.md`, `TODO.md` | Addressed |
| M2 | Keep room metrics labelled unmeasured (20 Oct) | Still unmeasured; annotation templates and scorer ready | `evaluation/templates/rooms.json`, `scripts/evaluate_rooms.py` | Ongoing |
| M3 | Prioritise caregiver-calibration authorisation and room-label retention tests (20 Oct) | Room-label retention: rooms never compacted (`compaction.py` docstring), tested. Authorisation: not started | `tests/test_compaction.py`; P1.7 | Partial |
| M4… | [[TEAM INPUT: each mid-evaluation item]] | | | |

### §3.5 Iteration Strategy [UPDATE]

Keep the text and F3.2. Table 3.2:

| Iteration | Milestones | Period | Status |
|---|---|---|---|
| 1 | Spatio-temporal memory engine (FR3), light FR1/FR2 | to mid-evaluation (week 9) | Complete; exit criterion not run on ground truth (§6.9) |
| 2 | M1 live ingestion, M2 memory completion, M3 query engine and speech, first apps | to week 14 / [[submission date]] | Complete (§7.9) |
| 3 | Temporal answers, confidence, evidence, room-identity fix, accuracy measurement | FYP-2 [[dates]] | Planned |
| 4 | Caregiver security, encryption, latency and usability validation | FYP-2 [[dates]] | Planned |

### §3.6 / §3.7 Iteration Plans [KEEP + one row each]

- Table 3.4: add the row **Outcome**: "Slice implemented; exit criterion (10 placements, ≥ 70%) not run with ground truth; moved to Iteration 3 as P2.2 (§6.9)."
- Table 3.5: add the row **Outcome**: "Delivered with one deviation: a rule-based engine plus on-device speech instead of a tool-calling voice agent; temporal answers deferred (§3.10, §7.9)."

### §3.8 Work Breakdown and Responsibilities [UPDATE]

Merge Tables 3.3, 3.6 and 3.7 into **one** table (errata E4):

| Member | Assigned lead | Iteration 2 work actually led (git evidence) |
|---|---|---|
| Shahmeer Amir | M-A, M-D | Live capture contracts, keyframes, buffer, gaps, pause, promotion (6–7 Nov); M1/M2 implementation pass: vocabulary ontology, gravity frame, oriented boxes, relations, scene-graph rebuild with state runs, SQLite home store, room identity, activities, evidence crops, compaction, JPEG live segments, perception changes, API fixes (15 Nov); Part II plan (16 Nov) |
| Faizan ur Rehman Khan | M-B | Evaluation suite (Options A/C/D, memory audit) (9–10 Nov); demo harness and calibration (17 Nov); EgoLife study, tiered query protocol and ranking (21–22 Nov); SAM 3 detector and benchmark (22 Nov) |
| Ali Sher | M-C | NLQ engine and dictionary (8–9 Nov); consolidation into `src/aegis/nlq`, `/ask`, Modal serving, `aegis-ask` CLI (18 Nov); end-to-end runner (20 Nov); Patient and Caregiver apps, enrollment endpoint, DINOv3 re-ID (23–24 Nov) |

> Responsibilities moved in Iteration 2. Shahmeer implemented most of the M-B memory store and Ali Sher built the M-D applications. The leads are kept as accountability assignments, and the table records who did the work.

[[TEAM INPUT: confirm this wording with all three members.]]

### §3.9 Progress Against Plan [REWRITE]

Fixes E1 and C1. Every row needs a **planned date** [[TEAM INPUT]].

| Planned item | Planned (week/date) | Actual status | Evidence (commit, date) |
|---|---|---|---|
| M1 frame stream capture | [[ ]] | Implemented | `d82dc30` (**1 Sep**, batch); live sampler `3a8808d`, `353db31` (11 Oct); live contracts `c045d9e`–`713e94a` 6 Nov |
| M1 keyframe optimisation | [[ ]] | Implemented | batch stride `d82dc30` (1 Sep); criterion keyframes `e022c6c` (6 Nov) |
| M1 gaps, pause, resume | [[ ]] | Implemented | `e8da287` (6 Nov) |
| M1 live → memory connection | [[ ]] | Implemented | promotion `713e94a`, pipeline `34207d7` (6 Nov); JPEG segments `8afd235` (15 Nov) |
| M2 anchor database | [[ ]] | Implemented | `d82dc30` (1 Sep) |
| M2 event grouping | [[ ]] | Implemented | `fa93619` (12 Oct); activities `c349916` (15 Nov) |
| M2 room hierarchy + registry | [[ ]] | Implemented | 8 commits 17 Oct (`4b20596`…`2298112`) |
| M2 gravity frame + relations | [[ ]] | Implemented | `1a40db9`, `1ad4eeb`, `ce05662` (15 Nov) |
| M2 persistent home store | [[ ]] | Implemented | `af2ef3b` (15 Nov) |
| M2 three-day compaction | [[ ]] | Implemented | `5eaba35` (15 Nov) |
| M3 natural-language queries | [[ ]] | Implemented (location only) | NLQ 8–9 Nov; `3209e72` `/ask` (18 Nov) |
| M3 voice input | [[ ]] | Implemented (on-device STT) | Patient app `6464d46` (23 Nov), caregiver `c5d94a4` |
| M3 tool-calling agent | [[ ]] | Deviated (see §3.10) | — |
| M4 patient/caregiver UI | [[ ]] | Implemented (no auth) | apps 23 Nov |
| M4 CI and reproducibility | [[ ]] | Implemented | CI with coverage floor; `scripts/run_e2e.py` `70f0240` (20 Nov) |
| Evaluation | [[ ]] | Partial | `fb0b5a1` (9 Nov), EgoLife `5dbc4b6` (21 Nov), SAM3 benchmark `2a3c603` (22 Nov) |

Figure **F3.1** (plan-vs-actual Gantt).

### §3.10 Delays, Deviations and Recovery Plan [REWRITE]

| # | Deviation | Reason | Impact | Recovery action | Owner | New date |
|---|---|---|---|---|---|---|
| D1 | Tool-calling voice agent replaced by a closed-vocabulary engine with on-device speech | A model writing answers can state a location it never observed (TC5); a template engine cannot | Safer answers; fewer question types | Optional LLM parser behind the vocabulary (P1.9) | Ali Sher | Iteration 4 |
| D2 | Temporal and activity questions not answered | Engine and store support exists (`states_as_of`, activities), but no answer templates yet | SC2 cannot be measured | Implement P1.1 | [[ ]] | Iteration 3 |
| D3 | Iteration 1 exit criterion not evidenced | No ground-truth placement recording | Iteration 1 slice unproven on data | Record and score 10 placements (P2.2) | [[ ]] | Iteration 3 |
| D4 | Room metrics unmeasured | No annotated multi-room clip | SC9 open | Annotate `demo05`/multi-room clip (P2.3) | [[ ]] | Iteration 3 |
| D5 | Authentication and encryption not started | Effort went to the end-to-end pipeline | SC7 not met; prototype only | P1.7, P1.8 | [[ ]] | Iteration 4 |
| D6 | Room identity unstable across sessions (found 22 Nov) | Absolute linking radius in scale-free units | Duplicate rooms over days | Scale-relative linking | [[ ]] | Iteration 3 |

---

## Chapter 4: Software Requirements

### §4.1 Use case inventory [UPDATE]

Fixes B2 and B3. Table 4.1 gets **Status**, with one name and one FR mapping per UC:

| ID | Use case | Primary actor | FRs | Status |
|---|---|---|---|---|
| UC-01 | Capture and ingest egocentric video | Primary user (system acts) | FR1, FR2 | Partial |
| UC-02 | Submit a query by speech or text | Primary user, caregiver | FR6, FR7.1 | Implemented |
| UC-03 | Find the last known location of an object | Primary user | FR3.2, FR5.1, FR5.4–FR5.7, FR7.2 | Implemented |
| UC-04 | Review the history of an object | Caregiver, primary user | FR3, FR4.3, FR7.4 | Partial |
| UC-05 | Recall earlier activity | Primary user | FR3.3, FR4, FR5.2, FR5.3 | Planned |
| UC-06 | View evidence for an answer | Primary user, caregiver | FR5.4, FR7.2 | Implemented |
| UC-07 | Grant, scope and revoke caregiver access | Primary user | FR8.1, FR8.4, FR8.5 | Planned |
| UC-08 | Caregiver queries episodic history | Caregiver | FR5, FR8.2 | Partial |
| UC-09 | Caregiver verifies an object state | Caregiver | FR3.2, FR5.1, FR8.2 | Partial |
| UC-10 | Caregiver reviews an activity summary | Caregiver | FR3.3, FR4.2, FR8.3 | Partial |
| UC-11 | Pause capture or delete history | Primary user | FR1.3, NFR-S5 | Partial |
| UC-12 | Maintain memory by compaction | System | FR4.1–FR4.4 | Implemented |
| UC-13 | Caregiver calibrates and names rooms | Caregiver | FR3.6, FR3.7, FR8.6 | Implemented (no auth) |
| UC-14 | Caregiver enrolls a personal item (**new**) | Caregiver | FR8.7 | Implemented (no auth) |
| UC-15 | Primary user contacts caregiver (**new**) | Primary user | FR7.5 | Implemented |

Only add UC-14/UC-15 if the team and supervisor agree. [[TEAM INPUT]]

### §4.2 Use case diagram

**F4.1** (includes UC-13).

### §4.3 Detailed use cases [UPDATE]

Fix A5 ("six"). Updated main flows:

**UC-03:**
1. The user taps an object tile, types a question, or speaks (on-device speech-to-text).
2. The app calls `GET /api/v1/query?item=…`.
3. The server ranks same-class candidates (recency, interaction, displacement, personal item, cues) and composes a short answer with place, room and time.
4. If no candidate is found, the app calls `GET /api/v1/ask`. The NLQ engine either answers or declines.
5. The app shows the answer with a resolution badge and up to three candidate photos.

Alternate flows:
- A1: Object never observed → "I haven't seen your keys. I remember: …".
- A2: Unknown word → "I don't know that word. Try: …".
- A3: Several similar objects → "ambiguous" badge with up to three photos.
- A4: Server unreachable → "Can't reach Aegis memory…" (never a made-up answer).
- A5: Room-constrained with no match → "I couldn't find your keys in the kitchen."

**UC-13:** unchanged steps; add "4a. In the home store, labels are unique per home (max 40 characters); a duplicate label is rejected (`DuplicateRoomLabelError`)." Actor: Caregiver App *Interior* tab.

**New UC-14 (`\uctable`):**

| Field | Content |
|---|---|
| Primary actor | Caregiver |
| Preconditions | The object has been observed at least once |
| Trigger | The caregiver opens *Enroll* |
| Main flow | 1. Enter item and alias ("dad's cup"), class, usual anchor and room. 2. The app resolves the instance (`/query`). 3. `POST /api/v1/enroll`. 4. The store records the personal item; later queries rank it first |
| Alternate flows | A1: Item not found → enrollment refused. A2: Alias too long (> 60) → rejected |
| Postconditions | The alias resolves to the instance |
| Related FRs | FR8.7, FR5.1 |

### §4.4 Functional requirements [UPDATE]

Add a **Status** column and the evidence. Fix B7 (FR6.1 → "shall … when speech support is available").

| ID | Status | Evidence (file · test) |
|---|---|---|
| FR1.1 | Implemented | `ingestion/live_pipeline.py` `ingest_live` (2 fps) · `test_live_ingestion` |
| FR1.2 | Implemented | `ingestion/contracts.py` frame record `capture_timestamp` · `test_live_contracts` |
| FR1.3 | Implemented | pause file / signals, `POST /api/v1/capture/pause\|resume` · `test_capture_control`, `test_live_ingestion` |
| FR2.1 | Implemented | `ingestion/keyframe.py` `KeyframeSelector` · `test_live_keyframe` |
| FR2.2 | Implemented | `live_handoff.promote_live_segments`, `segment_runner` · `test_live_handoff`, `test_live_segments` |
| FR2.3 | Implemented | gap records (disconnect, pause, storage_stall, source_stall, dropped_frames) · `test_live_contracts` |
| FR2.4 | Implemented | `ingestion/buffer.py` `FrameBuffer(30)` · `test_live_buffer` |
| FR3.1 | Implemented | `memory/association.py`, DINOv3/HSV re-ID · `test_association`, `test_scene_graph` |
| FR3.2 | Implemented | `memory/relations.py`, `memory/runs.py` · `test_relations`, `test_runs` |
| FR3.3 | Implemented | `memory/activities.py` · `test_activities` |
| FR3.4 | Implemented (unmeasured) | `memory/rooms.py` · `test_rooms` |
| FR3.5 | Implemented | `memory/store.py` · `test_restart_equivalence`, `test_store` |
| FR3.6 | Partial | `memory/matching.py` `match_rooms` · `test_matching`, `test_room_identity`; unstable across scale (TC12) |
| FR3.7 | Implemented | `memory/homes.py` `rename_home_room`, `home_registry.py` · `test_api`, `test_home_registry` |
| FR4.1 | Implemented | `RetentionConfig.hot_days = 3` · `test_compaction` |
| FR4.2 | Implemented | `compaction.compact`, `_verify` · `test_compaction` |
| FR4.3 | Partial | timeline lines carry `tier="summarised"` (`api.get_timeline`); `/ask` and `/query` do not use summaries |
| FR4.4 | Partial | state runs + compaction; 5.7–7.2× on short clips; long recording not measured |
| FR5.1 | Implemented | `api.query_memory`, `nlq/engine.py` · `test_api`, `test_nlq` |
| FR5.2 | Planned | engine declines temporal/activity (P1.1) |
| FR5.3 | Partial | `reasoning.parse_query_cues` (days ago, time windows) used for ranking only · `test_ranking` |
| FR5.4 | Partial | `/ask` evidence list, `/query` `crop_url`; coverage not audited (P1.4) |
| FR5.5 | Partial | declines when evidence is missing; confidence threshold not implemented (P1.2) |
| FR5.6 | Implemented | `extract_room_filter`, NLQ room slot · `test_reasoning`, `test_nlq` |
| FR5.7 | Implemented | `reasoning._insert_room_clause` · `test_reasoning` |
| FR6.1 | Implemented (on-device) | `voice_service.dart` (`speech_to_text`) · Flutter widget tests; accuracy unmeasured |
| FR6.2 | Implemented | both apps, `aegis-ask` |
| FR6.3 | Planned | P1.6 |
| FR7.1 | Implemented | both apps |
| FR7.2 | Implemented | `AnswerDrawer`, `CandidateCard`, `/api/v1/crops/{instance_id}` |
| FR7.3 | Partial | template answers ≤ 2 sentences; adjustable text size [[TEAM INPUT: check apps]] |
| FR7.4 | Partial | Caregiver App *Track* tab (`/timeline`); none in the Patient App |
| FR8.1 | Planned | P1.7 |
| FR8.2 | Partial | caregiver queries work; no scope enforcement |
| FR8.3 | Partial | `GET /api/v1/activities`, store summaries; no app screen |
| FR8.4 | Planned | P1.7 |
| FR8.5 | Planned | P1.7 |
| FR8.6 | Implemented (no auth) | `GET /rooms`, `POST /rooms/rename`, Caregiver *Interior* tab |
| **FR3.8 (new)** | Implemented | "The system shall classify each object's relation to the nearest anchor (inside, on_surface, under, above, next_to, on_floor, near, in_room, carried) in a gravity-aligned frame and mark uncertain relations." `relations.py` · `test_relations` (19) |
| **FR3.9 (new)** | Implemented | "The system shall match rooms, anchors and objects of a new session to the home's stable identities and record objects moved while unobserved." `matching.py`, `ingest.py` · `test_matching`, `test_ingest` |
| **FR4.5 (new)** | Implemented | "The system shall verify each summary against its source rows before deleting them and shall keep a day's detail if verification fails." `_verify` · `test_compaction` |
| **FR5.8 (new)** | Implemented | "When several same-class objects match, the system shall return up to three ranked candidates with photos and mark the answer as ambiguous." `rank_candidates` · `test_ranking` |
| **FR7.5 (new)** | Implemented | "The patient app shall let the user call or message the caregiver." `call_view.dart` |
| **FR8.7 (new)** | Implemented (no auth) | "The caregiver shall be able to enroll a personal item with an alias." `POST /api/v1/enroll`, `personal.py` |

### §4.5 Non-functional requirements [UPDATE]

Add a **Priority** column (B8) and a **Status** column:

| ID | Priority | Status | Note |
|---|---|---|---|
| NFR-R1 | H | Unmeasured | 1-hour soak not run (P2.1) |
| NFR-R2 | H | Partial | capture checkpoint + crash resume (`session_state.json`); store writes are transactional; loss bound not measured |
| NFR-R3 | M | Planned | freshness (P1.3) |
| NFR-U1 | H | Unmeasured | make it modality-neutral (B6) |
| NFR-U2 | H | Implemented | template answers |
| NFR-U3 | M | [[TEAM INPUT]] | contrast and text sizes not audited |
| NFR-U4 | H | Implemented | — |
| NFR-P1 | H | Unmeasured | P2.8 |
| NFR-P2 | M | Partial | backlog accounting (`max_backlog_seconds` in the manifest); not run for 10 min |
| NFR-P3 | H | Implemented | growth measured on short clips only |
| NFR-P4 | H | Unmeasured | — |
| NFR-S1 | H | Partial | HTTPS only on the Modal endpoint; no encryption at rest; cleartext LAN allowed |
| NFR-S2 | H | Not met | no role enforcement; `GET /api/v1/video/{dataset_id}` serves raw video without authentication |
| NFR-S3 | H | Planned | — |
| NFR-S4 | M | Partial | promoted local segment frames deleted after processing unless `--keep-frames`; pointmaps deleted after detection; volume frames and evidence crops kept (decision #9) |
| NFR-S5 | H | Partial | `HomeStore.delete_session_rows` exists; verified full deletion not implemented (P1.8) |

### §4.6 Acceptance criteria [UPDATE]

Fixes A6, B4 and B5. Add two columns, **Result** and **Evidence**:

| AC | Result at FYP-1 end | Evidence |
|---|---|---|
| AC-01 | Not run (5-min stream test not recorded) | P2.1 |
| AC-02 | Not run | P2.1 (scripted keyframe clip) |
| AC-03 | Partial: disconnect/reconnect logic unit-tested with an injected source; physical 10 s test not run | `test_live_ingestion`; P2.1. **Re-map to FR2.3, FR2.4** |
| AC-04 | Not run | P2.2 |
| AC-05 | Not run | P2.2 (`scripts/evaluate_activity_order.py` ready) |
| AC-06 | **Pass** (automated) | `test_restart_equivalence.py` (3 tests) |
| AC-07 | **Pass** (automated, synthetic history) | `test_compaction.py` (14); real long history not run |
| AC-08 | Partial | auto-probe agreement 100% (memory audit); human queries not run |
| AC-09 | Not run | `demo05` NOT_READY |
| AC-10 | Not run | temporal not implemented |
| AC-11 | Not run as an audit | P1.4 |
| AC-12 | **Pass** (automated): unknown and unobserved items decline; no fabricated location | `test_nlq.py`, `test_api.py`; EgoLife keys/wallet probes |
| AC-13 | Not run | — |
| AC-14 | Partial: answer screens show answer, time, evidence | F7.6 screenshots; not a formal 5-query inspection |
| AC-15 | Not run | usability study |
| AC-16 … AC-18 | Not run (no auth) | P1.7 |
| AC-19 | Not run | P2.8 |
| AC-20 | Fail / not run | no encryption at rest |
| AC-21 | Partial: pause records and no frames while paused tested | `test_live_ingestion`, `test_capture_control` |
| AC-22 | Not run | P2.3 |
| AC-23 | Partial | timeline labels summarised lines; query path does not |
| AC-24 | Partial | text and speech flows exist; text-size and contrast not measured |
| AC-25 | Partial | Caregiver *Track* tab; not compared to a ground-truth log |
| AC-26 | Not run (no scopes) | — |
| AC-27 | Partial: capture crash-resume tested | `test_live_ingestion` (resume) |
| AC-28 | Not run | P1.3 |
| AC-29 | Partial: buffer behaviour tested | `test_live_buffer`; 10 s engine pause not run |
| AC-30 | Partial | see NFR-S4 |
| AC-31 | **Pass** (automated) | `test_api.py`, `test_home_registry.py` |
| **AC-32 (new, FR5.7)** | **Pass** (automated) | `test_reasoning.py` room-clause tests |
| **AC-33 (new, NFR-R1)** | Not run | stream for 60 min; no crash, no stall > 30 s (P2.1) |
| **AC-34 (new, FR3.9)** | **Pass** (automated) | `test_ingest.py`, `test_matching.py`: second session reuses room, anchor and instance IDs |
| **AC-35 (new, FR4.5)** | **Pass** (automated) | `test_compaction.py`: a day failing verification keeps its rows and logs `failed` |

Summary sentence for §8.9: count Pass / Partial / Not run / Fail from this table after the team confirms it.

### §4.7 Traceability [UPDATE]

Same table, with test files from the FR table above. Fix the "Use-case coverage" paragraph by generating it from Table 4.1 (B2).

### §4.8 Requirements change log [NEW]

| ID | Change | Reason | Date | Approved by |
|---|---|---|---|---|
| FR3.8 | Added | Relations became explicit in the gravity frame | 15 Nov 2026 | [[supervisor]] |
| FR3.9 | Added | Persistent home store needs cross-session identity | 15 Nov 2026 | [[ ]] |
| FR4.5 | Added | Compaction must never lose the last-known state silently | 15 Nov 2026 | [[ ]] |
| FR5.8 | Added | Class-level ambiguity (tiered protocol) | 22 Nov 2026 | [[ ]] |
| FR6.1 | Modified ("should" → "shall when available") | Consistency with keyword rule; speech now implemented | [[ ]] | [[ ]] |
| FR7.5, FR8.7, UC-14, UC-15 | Added | Features built in the new apps | 23 Nov 2026 | [[ ]] |
| NFR-U1, AC-15 | Modified (speech or text) | Removes the conflict with NFR-U4 | [[ ]] | [[ ]] |
| AC-03 | Re-mapped to FR2.3/FR2.4 | It did not test NFR-R1 | [[ ]] | [[ ]] |
| AC-32–35 | Added | Coverage gaps (FR5.7, NFR-R1, new FRs) | [[ ]] | [[ ]] |
| FR5.2 | Deferred to Iteration 3 | Deviation D2 | [[ ]] | [[ ]] |

---

## Chapter 5: System Design

Every figure gets at least one explanatory paragraph (errata G1, G2). The opening paragraph:

> In the diagrams, solid elements are implemented on the `develop` branch and covered by tests, elements tagged "partial" are implemented slices, dashed elements are planned, and red marks a known security gap. All diagrams were drawn from the code at commit [[submission commit]].

### §5.1 System Architecture: F5.1

> Aegis is organised in five layers (Figure 5.1).
> - **Capture and ingestion** runs on the laptop. `aegis-ingest` reads the phone's MJPEG stream, samples it at 2 fps, keeps only sharp, well-exposed frames that differ from the last one, and writes JPEG frames with an index of frame and gap records. A finished or growing capture is cut into segments of at most 120 frames and uploaded to a Modal volume.
> - **Processing** runs on Modal. A CPU worker normalises the frames; an L4 GPU worker runs VGGT-Ω to recover camera poses and per-pixel 3D points, then fits the floor with RANSAC to find "up"; a second GPU worker detects objects with SAM 3 (or YOLOE), refines masks with SAM 2, tracks identities with DINOv3 embeddings, and lifts each detection into a gravity-aligned 3D box.
> - **Memory** turns boxes into rooms, anchors and objects, classifies each object's relation to its anchor, debounces observations into state runs and derives events. The result is one session graph. A session can then be merged into a per-home SQLite store that keeps stable identities, groups activities, keeps evidence crops and compacts history older than three days.
> - **Service** is a FastAPI application deployed on Modal. It answers ranked object queries and natural-language questions from the session graph or the home store.
> - **Presentation** is the patient and caregiver apps, a terminal client, and an offline Rerun viewer.
>
> Layers talk only to their neighbours through files on the volume or HTTPS JSON.

### §5.2 Architectural components: F5.2, F5.3

**Table 5.1: Component responsibilities.** Columns: Component, package path, provides, requires. Copy the table in `DIAGRAM_SPECS.md` F5.2.

Deployment paragraph:

> The prototype is deployed across five kinds of device (Figure 5.3). The wearer's phone only streams video. The laptop runs capture, launches the pipeline and, when artifacts are downloaded, holds the persistent home store. Modal runs CPU and GPU containers for processing and a separate CPU web endpoint, `aegis-memory-api`, that serves the API from the data volume, so normal operation needs no download to the laptop. The patient's and caregiver's phones reach that endpoint over HTTPS. GitHub Actions runs linting, the test suite with a 75% coverage floor and Flutter checks on every push to `main` and `develop`, and publishes the patient APK. Model weights are downloaded once from Hugging Face and cached on a model volume.

### §5.3 Interfaces and Dependencies [REWRITE]

Fixes C5.

**Table 5.2: HTTP API contract** (`src/aegis/remote/api.py`, base `/api/v1`, `API_VERSION = 0.2.1`):

| Method | Path | Inputs | Response | Mutates | Auth |
|---|---|---|---|---|---|
| GET | `/health` | `dataset_id?`, `home_id?` | `HealthResponse` (anchors, rooms, events, frames, `compaction_ok`) | no | none |
| GET | `/scene_graph` | `dataset_id?`, `home_id?` | full graph JSON | no | none |
| GET | `/datasets` | — | datasets + tracked objects | no | none |
| POST | `/dataset/select` | `dataset_id` | active dataset | **yes** (server state) | none |
| GET | `/anchors` | `dataset_id?`, `home_id?` | `AnchorModel[]` | no | none |
| GET | `/rooms` | `dataset_id?`, `home_id?` | `RoomModel[]` | no | none |
| POST | `/rooms/rename` | `room_id`, `label`, `dataset_id?`, `home_id?` | renamed room | **yes** (graph/store + `home_map.json`) | none |
| POST | `/enroll` | `EnrollRequest` | personal items | **yes** (store) | none |
| GET / POST | `/ask` | `text` (≤ 300), `dataset_id?`, `home_id?` | `AskResponse` | no | none |
| GET | `/query` | `item`, `dataset_id?`, `home_id?` | `MemoryQueryResponse` (≤ 3 candidates) | no | none |
| GET | `/timeline` | `dataset_id?`, `home_id?`, `start?`, `end?` | `TimelineEventModel[]` (incl. `tier`) | no | none |
| GET | `/activities` | `home_id`, `start?`, `end?` | `ActivityModel[]` | no | none |
| GET | `/crops/{instance_id}` | `dataset_id?`, `home_id?` | JPEG | no | none |
| GET | `/video/{dataset_id}` | — | MP4 | no | **none: raw video exposed** |
| GET | `/capture/status` | — | `CaptureStatusModel` | no | none |
| POST | `/capture/pause`, `/capture/resume` | — | `CaptureStatusModel` | **yes** (pause file) | none |
| POST | `/simulate_transition`, `/reset`; GET `/simulate/*` (6) | — | simulator responses | **yes** | gated by `require_simulator` (`AEGIS_ENABLE_SIMULATOR=1`), off by default |

**Table 5.3: Artifact contracts.** Rows (source: `docs/artifact_contracts.md`):
- live `index.jsonl` frame and gap records (schema 2)
- `session.json`
- `session_state.json`
- `metadata.json` (schema 2)
- `poses.json`
- `gravity.json`
- `pointmaps/*.npz`
- `detected_objects_3d.json` (2)
- `r4d_scene_graph.json` (2)
- `r4d_timeline.json`
- `events.json`
- `spatial_memory_graph.json`
- `memory.db` (store schema 1)
- `home_map.json`

All timestamps are UTC ISO strings (`core/timeutil.py`).

### §5.4 Architecture Decisions and Rationale [REWRITE as ADR table]

| # | Decision | Alternatives | Rationale | Evidence |
|---|---|---|---|---|
| AD1 | Raw VGGT-Ω coordinates; gravity stored beside them | Rotate/scale the scene; manual SCALE/to_zup (mid-era, removed) | No hidden transform; every derived height is reproducible | `geometry/gravity.py`; `test_gravity` (12) |
| AD2 | Rooms from wearer trajectory + sparse landmarks | Dense point-cloud segmentation | Cheap, works on RGB-only video | `memory/rooms.py`; Hydra / HOV-SG |
| AD3 | Debounced state runs instead of per-frame timeline | Store every observation | Graph size independent of video length; 5.7–7.2× smaller | `memory/runs.py`; Section 8.6 |
| AD4 | Per-home SQLite store | Growing JSON; a server database | Single file, transactional, no service to run | `memory/store.py` |
| AD5 | Three-day detail, verified template summaries, roll-up | Keep everything; LLM summaries | Bounded storage; no model can hallucinate a summary; failure keeps detail | `memory/compaction.py` |
| AD6 | SAM 3 default detector | YOLOE, YOLO-World | Only model to find small personal objects and hands | Section 2.9 |
| AD7 | Closed-vocabulary rule engine; LLM optional parser only | VLM/LLM writes answers | Never states an unobserved location | `nlq/engine.py` |
| AD8 | Artifacts stay on the Modal volume; API served there | Download to laptop, serve locally | No large transfers; phone reaches HTTPS | `remote/serve.py` |
| AD9 | Thin apps that never mutate memory (except caregiver rename/enroll) | On-device processing | Simple, battery-friendly; one source of truth | `CONTEXT.md` invariant 7 |
| AD10 | Ranked top-3 candidates with photos | Single answer | Honest about ambiguity | `reasoning.rank_candidates` |

### §5.5 Design Evolution [REWRITE]

Figure **F5.4**. Table 5.4 is the nine numbered changes in `DIAGRAM_SPECS.md` F5.4, with a "Why" column:

| # | Why |
|---|---|
| ① | detector benchmark |
| ② | relations need "up" |
| ③ | storage growth |
| ④ | "inside / under" questions |
| ⑤ | multi-session memory and restarts |
| ⑥ | proposal action 1 |
| ⑦ | ambiguity + natural language |
| ⑧ | phone access without a laptop |
| ⑨ | panel action 4, live-to-memory gap closed |

Add one paragraph naming what was **removed**:
- the SCALE=5.0/to_zup display transform (mid);
- the Depth-Anything depth model and dead DROID code (`c4236df`);
- the client-side mock answer (`180b897`);
- the legacy `apps/mobile` app;
- the separate `NL Querying/` folder (archived).

### §5.6 Domain Model: F5.5

> The domain model (Figure 5.5) separates what persists from what is derived. A **Home** owns **Rooms** and **Sessions**. Furniture-sized **Anchors** sit in rooms. Each personal **ObjectInstance** has a history of **StateRuns**, each a stable relation to an anchor over a time interval, and **Events** record the change between two runs. **Activities** group the wearer's stay in a room with the events that happened there. **Summaries** replace detail older than three days. Rooms, anchors, sessions and each object's last-known state are never compacted, so "where is X now?" survives any amount of history. User, caregiver, access grant and audit entry are planned and drawn dashed.

### §5.7 Data Design: F5.6, F5.7, F5.8

One paragraph each:
- the session graph (schema 2, no per-frame data);
- the home store (12 tables; what compaction writes and never deletes; soft references);
- the live capture contracts.

### §5.8 User Interface Design: F5.9, F5.10

> The panel asked for a product-like design suited to older users. The patient app opens on large object tiles built only from objects that memory actually holds, a single large microphone button, and a call button. Answers appear in a bottom sheet with one plain sentence, a labelled certainty badge (direct, ranked, ambiguous, not found) and up to three real photos, never a bare probability. The caregiver app adds search history, a tracking timeline, room naming, server and capture status, and personal-item enrollment. Both use 44-point touch targets and a warm espresso/ochre theme.

### §5.9 Process / Behaviour Design: F5.11–F5.20

One paragraph per figure. Content for each paragraph is in the matching spec in `DIAGRAM_SPECS.md`.

---

## Chapter 6: Iteration 1 (frozen)

| § | Change |
|---|---|
| 6.1 | Add the line: "Baseline: tag `v0.2.0-mid2` (13 Oct 2026); evidence to 17 Oct 2026." |
| 6.4 / 6.5 | Remove the 17 Oct room material (B13); it moves to Chapter 7 |
| 6.7 | "YOLOE (YOLO-World alternative)/Ultralytics" (B11) |
| 6.9 | New text (below) |

New §6.9 text:

> The Iteration 1 slice (batch ingestion, reconstruction, perception, scene graph, item query and clients) was implemented. Its exit criterion — ten recorded object placements with at least 70% correct last-known locations — was not run against ground truth during FYP-1. It is scheduled as P2.2 in Iteration 3 together with the activity-order check (AC-05).

Figures F6.1–F6.4 as specified (renamed, notation fixed).

---

## Chapter 7: Iteration 2: Design and Implementation [NEW]

### §7.1 Iteration Objectives

> Iteration 2 (18 October to [[submission date]]) had three objectives:
> 1. Close the live-to-memory gap left at the mid-evaluation.
> 2. Complete the memory model planned for Milestones 1 and 2 — gravity, relations, persistence across sessions and three-day compaction.
> 3. Give users natural-language access by text and voice through product-quality apps.

### §7.2 Selected use cases / features

UC-02, UC-03 (refined), UC-04, UC-06, UC-11 (pause), UC-12, UC-13 (moved from the Iteration 1 chapter), and UC-14/UC-15 if adopted. Planned but deferred: UC-05 (activity recall).

### §7.3 Design

Figures F7.1–F7.5, one paragraph each.

### §7.4 Implementation: package walk-through

Table 7.1 (file → responsibility → key functions):

| File | Responsibility | Key classes / functions |
|---|---|---|
| `core/vocabulary.py`, `config/vocabulary.yaml` | One ontology: 56 labels (31 objects, 16 anchors, 8 landmarks, hand); 8 high-importance items (keys, glasses, cell phone, wallet, purse, medicine, hearing aid, walking stick) | `Vocabulary.canonical`, `.role`, `.resolve_query` |
| `ingestion/live_pipeline.py` | Live sampling loop | `ingest_live`, `LiveIngestionConfig` |
| `ingestion/keyframe.py` | Keyframe criterion | `KeyframeSelector.evaluate` |
| `ingestion/buffer.py` | Stall buffer | `FrameBuffer` |
| `ingestion/contracts.py` | Schema-v2 validation | `validate_frame_record`, `validate_gap_record`, `validate_session_manifest` |
| `ingestion/live_handoff.py`, `segment_runner.py` | Promotion and segments | `promote_live_segments`, `plan_segments`, `run_live_segments` |
| `geometry/gravity.py` | Up direction, floor, scale unit | `estimate_gravity`, `GravityFrame` |
| `geometry/lifting.py`, `planar.py` | Gravity-aligned oriented boxes; 2D polygons | `lift_detection_to_3d`, `_fit_gravity_obb`, `overlap_fraction` |
| `perception/detector.py` | SAM 3 / YOLOE detection, SAM 2 masks, tracking, DINOv3 re-ID | `Sam3Adapter`, `DinoEmbedder`, `detect_and_track_objects` |
| `memory/relations.py` | Nine relations | `classify_relation` |
| `memory/runs.py` | State runs and events | `build_state_runs`, `build_events` |
| `memory/scene_graph.py` | Session graph v2 | `build_relative_4d_scene_graph` |
| `memory/store.py` | SQLite home store | `HomeStore` |
| `memory/matching.py`, `ingest.py` | Cross-session identity | `match_rooms`, `match_anchors`, `match_instances`, `ingest_session` |
| `memory/activities.py`, `evidence.py` | Room-stay activities; one crop per run | `build_activities`, `write_run_crops` |
| `memory/compaction.py`, `summaries.py` | Retention | `compact`, `rollup`, `object_day_summary` |
| `memory/reasoning.py` | Ranking and wording | `rank_candidates`, `parse_query_cues`, `QueryReasoningEngine` |
| `memory/personal.py` | Personal items | `enroll`, `resolve_alias` |
| `nlq/dictionary.py`, `engine.py`, `cli.py` | NLQ | `DictionaryIndex`, `AnswerEngine.ask`, `aegis-ask` |
| `remote/api.py`, `serve.py`, `modal_app.py`, `workers.py` | API, deployment, workers | see Table 5.2 |
| `scripts/run_e2e.py` | One-command end-to-end runner with human checkpoints | `phase_*` functions |
| `apps/Patient App/lib/…`, `apps/Caregiver App/lib/…` | Clients | `ApiService`, `DeviceVoiceService`, `AnswerDrawer`, `EnrollDialog` |

Setup and reproduction (copy into the text, from `CONTEXT.md` §7):

```bash
uv sync --dev
uv run pytest -q
uv run aegis-ingest --url 'http://PHONE:8080/video' --output-root ./captures \
  --session-id walk01 --config-path config/live.yaml
uv run python run_pipeline.py --live-session captures/walk01 \
  --dataset-id walk01 --config-path config/live.yaml --stage live
AEGIS_DATASET_ID=walk01 uv run modal deploy src/aegis/remote/serve.py
uv run aegis-ask "where are my keys" --dataset-id walk01
uv run python scripts/run_e2e.py   # all of the above, with checkpoints
```

### §7.5 Completed features

Table 7.2. Columns: Feature · FR/UC · Owner · Commit(s) · Tests · Status. Rows are the Iteration 2 items from §3.9 with their commits and test files.

### §7.6 Technical implementation details

Table 7.3: key parameters, all from `config/demo.yaml`, `config/live.yaml` and `core/config.py`.

| Group | Parameter | Value |
|---|---|---|
| Live capture | sample_fps; buffer; reconnect interval / timeout; max duration; segment | 2.0; 30 frames; 3 s / 30 s; 600 s; 120 frames |
| Keyframes | min sharpness; brightness range; min visual change; max interval | 15; 20–245; 0.008; 2.0 s |
| VGGT-Ω | image size; stride (demo / live); max keyframes; dtype | 512; 6 / 1; 120; bfloat16 |
| Gravity | RANSAC iterations; min confidence; assumed camera height | 500; 0.5; 1.4 |
| Detection (demo) | backend; default threshold; class thresholds; NMS | SAM 3; 0.8; shoes 0.5, hand 0.4, cooking pot 0.6, trash bin 0.4, food container 0.9; 0.7 |
| Detection (live) | backend; model | YOLOE; `yoloe-11l-seg.pt` |
| Tracking / re-ID | max gap; re-ID gap; appearance threshold | 3; 30; 0.35 |
| Memory build | anchor cluster radius; association radius; min observations; min run observations; trailing single confidence; vertical tolerance | 0.4; 0.45; 2; 2; 0.5; 0.15 |
| Rooms | zone link radius; min zone keyframes | 1.5 (absolute VGGT units, see TC12); 3 |
| Ranking | candidates; ambiguity margin; half-life; weights vip/act/disp/rec/cue/visual | 3; 0.08; 24 h; 1.0/0.45/0.25/0.20/0.10/0.10 |
| Retention | hot days; important hot days; weekly / monthly roll-up after; timezone | 3; 7; 30 / 365 days; Asia/Karachi |
| Evidence | max side; JPEG quality | 320 px; 85 |

Algorithm paragraphs (one each, matching F7.3, F7.4, F7.5, F5.18, F5.19, F5.20):
- relation classification
- cross-session matching
- keyframe selection
- debouncing into state runs
- verified compaction
- NLQ decision flow

### §7.7 Tools, frameworks and technologies

Add to the Iteration 1 list:
- SAM 3 (`facebook/sam3`)
- DINOv3 (`facebook/dinov3-vits16-pretrain-lvd1689m`)
- YOLOE (`yoloe-11l-seg.pt`)
- SQLite
- Modal ASGI web endpoints
- Hugging Face `transformers` ≥ 5
- Flutter ≥ 3.22 with `speech_to_text` ^7.0, `shared_preferences` ^2.3, `url_launcher` ^6.3, `http` ^1.2
- GitHub Actions with `pytest-cov`

### §7.8 Demonstration evidence

Figures F7.6–F7.9, plus a short table of the measured end-to-end run (§8.7).

### §7.9 Iteration outcome

> Against the Iteration 2 exit criteria (Table 3.5):
> - Spatial queries are answered with evidence, but their accuracy on the test sequence has not been measured, because the held-out clip is not yet annotated.
> - Temporal queries are declined by design, so the temporal half of the criterion is not met.
> - Abstention is demonstrated: automated tests cover unknown words, unobserved objects, room mismatches and temporal and activity questions, and the EgoLife run included two never-mentioned objects (keys, wallet) as abstention probes.
>
> Carried into Iteration 3: temporal answers, calibrated confidence, evidence-reference audit, room-identity fix and all accuracy measurements.

---

## Chapter 8: Testing and Validation

### §8.1 Strategy

> Testing has four levels:
> - deterministic unit tests for geometry, memory and query logic;
> - integration tests for live ingestion (injected frame sources), the API (FastAPI test client) and the Modal compute wrappers (fakes);
> - Flutter widget tests for both apps;
> - evaluation and measurement on real video.
>
> The evaluation harness refuses to report a score without ground truth (it writes `NOT_READY` / `NO_GO` instead). Continuous integration runs Ruff, the Python suite with a 75% coverage floor and Flutter analyse/test on every push to `main` and `develop`.

### §8.2 Levels

Figure **F8.1** (table of counts in `DIAGRAM_SPECS.md`).

### §8.3 Test cases

Summary by area; full table in Appendix C.

### §8.4 Results

> `uv run pytest -q` on commit [[submission commit]]: **451 passed** in about 8–31 s; line coverage 79% of 10,759 statements (`--cov=aegis`). Ruff check and format pass. Flutter: [[TEAM INPUT: `flutter test` counts from CI]].

### §8.5 Component benchmark: detection

Table 2.5 / Figure F2.3 (reference it), plus the per-class result: shoes 34/42, hands 19/19 (shipped). Limitation: 10 frames.

### §8.6 Memory compaction audit

Table from `evaluation/reports/memory_control/summary.md`; Figures F8.3 and F8.4.

> On two short clips (demo04: 117 frames, 5 objects; demo03: 100 frames, 16 objects), state-run compaction reduced the memory from 178.3 KiB to 24.8 KiB (7.2×) and from 528.5 KiB to 92.0 KiB (5.7×) while preserving 100% of semantic state, every latest state exactly, and 100% agreement on automatically generated label queries. Keeping a snapshot every keyframe preserves exact geometry at 1.5–1.9×. Hourly and daily figures are linear projections from these clips, not measurements.

### §8.7 End-to-end run

> On 20 November 2026 the full chain ran once on CPU from a real phone capture (`walk01-2`, 79 frames, segment `walk01-2_seg0001`): VGGT 831 s, detection and lifting 27 s, API deployment 8 s. `aegis-ask` then answered over HTTPS from the Modal volume with no local artifacts. This shows the pipeline is connected end to end; it is a single CPU run, not a performance measurement.

Figure F8.5.

### §8.8 Multi-day study (EgoLife)

**Protocol:** participant A1_JAKE, 12:00–13:00 on each of 7 days, 74 five-minute segments, keyframe every 3 s, ingested in chronological order into one home. Ground truth comes from EgoLife's own dense captions. 17 frozen queries with SHA-256 recorded. Each query is answered from full history and from the last 24 h only.

**Results (as recorded in `docs/egolife.md` and commit `61dda40`):**
- full history never beat the 24 h ablation at class level;
- an oracle-assisted diagnostic found 12 of 12 matched placements still in memory 1–4 days later;
- room/anchor identity grew across days (DAY7: 44 rooms, 859 anchors, reduced to 40 and 818 by a signature fix);
- cost US$8.71 metered.

[[TEAM INPUT: per-day table from `outputs/evaluation/egolife_scored/FINAL_SUMMARY.md` (Faizan's machine).]]

**Limitations:** copy the seven limitations from `docs/egolife.md`. Figure F8.6.

### §8.9 Acceptance status

Count of AC results from Table 4.16. Name the ACs that passed: AC-06, 07, 12, 31, 32, 34, 35 (all automated).

### §8.10 Edge and failure cases

The mid list, plus:
- unknown word → suggestions
- unobserved object
- room mismatch
- temporal/activity decline
- empty volume self-diagnosis in the e2e runner
- gated checkpoint → public mirror
- missing or corrupt graph → safe failure
- dataset isolation
- 8 s client timeout → "Can't reach Aegis memory"
- compaction verification failure keeps detail
- duplicate room label rejected

### §8.11 Defects and corrective actions

Table, fixing G4 and B15:

| Defect | How found | Fix | Commit | Test added |
|---|---|---|---|---|
| Client substituted a mock answer when the server failed | Code review against the safe-failure rule | Show an explicit "can't reach memory" message (legacy `apps/mobile`; the new apps keep this behaviour, `ApiService.unreachableMessage`) | `180b897` | none at the time; Patient App widget tests cover the unreachable state [[check `widget_test.dart`]] |
| API could word an answer beyond the evidence; room rename bugs; no input validation | Review | Evidence-bound wording, validated inputs | `2b3e6db` | `test_api`, `test_reasoning` |
| YOLOE missed all shoes and hands | Detection benchmark | Switch to SAM 3 | `2a3c603` | `test_config` (SAM 3 settings), `test_vocabulary` |
| Silent Modal upload failure caused a confusing downstream error | Large `demo05` upload | Raise with stderr | `2a3c603` | `test_live_cli` |
| v2 graphs showed no object overlays in Rerun | Visual check | `_v2_timeline` | `2a3c603` | `test_rerun_visualization` |
| API read the graph from the wrong path | Deployment | Read where the pipeline writes | `7a905d2` | `test_api`, `test_run_e2e` |
| Lexicon missing from the serving image | Deployment | Ship it; self-diagnose an empty API | `8c9746d` | `test_serve_app` |
| Gated VGGT checkpoint refused the token | E2E run | Fall back to the public mirror | `d3861d3` | `test_vggt_checkpoint`, `test_run_e2e` |
| Invalid Modal scale-down window | Deployment | Use the minimum valid value | `48d8e4f` | — |
| Room signatures mixed display and canonical labels | EgoLife diagnostic | Normalise signatures | `61dda40` | `test_ingest` |
| Room identity unstable across sessions | EgoLife | **Open** (TC12) | — | — |

### §8.12 Validation status

**Measured:**
- detection P/R/F1 (10 frames);
- compaction ratio and retention (2 clips);
- one end-to-end run;
- EgoLife persistence diagnostic and cost.

**Not yet measured:**
- SC1 spatial accuracy and SC2 temporal accuracy;
- SC3 on human queries;
- SC4 latency p95;
- SC8 usability;
- SC9 room metrics;
- AC-01/03 physical capture tests;
- controlled-room metric error.

Ego4D: not pursued (NO-GO).

---

## Chapter 9: Project Management and Development Evidence

| § | Content |
|---|---|
| 9.1 Work completed | One paragraph over both iterations; refer to Tables 6.x and 7.2 |
| 9.2 Work remaining | `TODO.md` P1.1–P1.9 and P2.1–P2.9, summarised |
| 9.3 Individual responsibilities | Refer to §3.8 |
| 9.4 Contribution evidence | Table below |
| 9.5 Repository evidence | Branching model, tags, PR template, CI/CD, F9.2. Policy note: "main changes only by merging develop" (direct commits on 21–22 Nov are recorded honestly) |
| 9.6 Milestones and commit evidence | F9.1. Tag the submission commit `v0.3.0-fyp1-final` and cite it |

**Table 9.4: Contribution evidence.** Re-run on the submission commit with `git shortlog -sn --no-merges` and `git log --since=2026-10-22`.

| Member | Git identity | Commits all-time (incl. merges) | Non-merge since 22 Oct | Date range | Features owned (Iteration 2) |
|---|---|---|---|---|---|
| Shahmeer Amir | `shah-paradox` | 44 | 32 | 11 Oct – 17 Nov | live capture reliability; memory store; gravity; relations; state runs; compaction; rooms; activities; evidence |
| Faizan ur Rehman Khan | `pez-Ox`, "Faizan Ur Rehman Khan" | 69 + 2 | 14 | 24 Aug – 22 Nov | evaluation suite; EgoLife; SAM 3; ranking protocol; demo harness |
| Ali Sher | `Ali Sher` | 223 | 203 | 12 Oct – 24 Nov | NLQ engine; `/ask`; Modal serving; `aegis-ask`; e2e runner; Patient and Caregiver apps; enrollment; DINOv3 |

> Commit counts measure commit granularity, not effort or quality: 122 of Ali Sher's commits on 23 November add one app file each. The "features owned" column is the meaningful record.

### §9.7 Tools and tool-assisted development [UPDATE]

This is a graded gate: the tool item scores 0 until disclosure is complete.

Columns: Member · Tool · Used for · How the output was checked. The team must fill every row. [[TEAM INPUT]]

Tools known from the repository:
- **Claude Code**: used in this repository for git operations and report-planning documents, including this file (Shahmeer).
- **Codex / GPT, Gemini, Antigravity, Pi harness**: listed in the mid report.
- **Gemini**: the evaluation-plan knowledge files `aegis_*_gemini*.md` in the repository root.
- **`.agents/skills/modal`**: agent skill files for Modal.

Add one closing sentence:

> Every merged change passed the automated suite, and each member can explain the code in the modules they own.

### §9.8 External components and dependencies

Table: add these rows.

| Component | Use | Licence / access note |
|---|---|---|
| SAM 3 | detection | gated HF model |
| DINOv3 | re-ID embeddings | HF |
| YOLOE | live detection | Ultralytics |
| SQLite | home store | stdlib |
| EgoLife | evaluation dataset | public, research use |
| VGGT-Ω | reconstruction | gated, public mirror |
| Flutter packages | apps | `speech_to_text`, `shared_preferences`, `url_launcher`, `http` |
| Modal web endpoint | API hosting | — |

Remove the row "relational database: not implemented".

### §9.9 Risks (scored)

Fixes E2. Columns: ID · Risk · L (1–5) · I (1–5) · Score · Mitigation · Owner · Trigger.

| ID | Risk | L | I | Score | Mitigation |
|---|---|---|---|---|---|
| TC12 | Cross-session room identity | 4 | 4 | 16 | scale-relative linking |
| TC5 | Temporal questions unanswered | 5 | 3 | 15 | P1.1 |
| TC7 | No auth/encryption | 5 | 4 | 20 | P1.7, P1.8 |
| TC8 | Results don't generalise | 4 | 4 | 16 | honest limits; persistence pilot |
| TC1 | Identity under clutter | 3 | 4 | 12 | DINOv3; measure on `demo05` |
| R-INT | Late large merges break `develop` | 3 | 4 | 12 | CI on `develop`, merge `develop` into feature branches first |

Fill L/I with the team: [[TEAM INPUT]].

### §9.10 Security and privacy

> The current prototype has no authentication or authorisation on any route except the simulator gate, and allows any origin. Routes that change state without authentication are `POST /rooms/rename`, `/enroll`, `/capture/pause`, `/capture/resume` and `/dataset/select`. `GET /video/{dataset_id}` returns the raw recording to any caller. The home store, the room registry and the evidence crops are not encrypted at rest. Both apps allow cleartext HTTP on a local network for development, and the deployed Modal endpoint is a public HTTPS URL. Promoted local frames are deleted after processing; evidence crops are kept by decision #9. These are the Iteration 4 security work items (P1.7, P1.8).

### §9.11 Limitations

Rewrite in line with §8.12.

---

## Chapter 10: Remaining FYP Plan (FYP-2)

| § | Content |
|---|---|
| 10.1 Remaining scope | `TODO.md` P1 + P2 |
| 10.2 Features | Table: Feature · FR · Iteration · Owner [[ ]] · Depends on. Rows P1.1–P1.9, P2.1–P2.8, room-identity fix |
| 10.3 Iterations | Iteration 3 (correctness and measurement), Iteration 4 (security and validation); see the F10.1 rows |
| 10.4 Implementation order | room identity → temporal answers → calibrated confidence → evidence audit → `demo05` scoring → auth → encryption → latency → usability |
| 10.5 Validation plan | One protocol per unmeasured SC/AC (list below) |
| 10.6 Deployment | Modal API + APK release via CD; home store location decided [[ ]]; secrets via Modal secret |
| 10.7 Timeline | F10.1 |
| 10.8 Deliverables | Mid list + two apps + evaluation report + reproducible runner |

Protocols for §10.5:
- `demo05` frozen-bank scoring (Option A, `evaluation/configs/demo05.yaml`)
- latency: ≥ 100 warm requests, p50/p95/max
- compaction before/after on human queries
- annotated multi-room clip (`scripts/evaluate_rooms.py`)
- 1-hour soak and 10 s disconnect
- controlled room (Option D)
- 7-day persistence pilot (evaluation suite §7)
- usability with 5 participants after ethics approval

---

## Chapter 11: Conclusion [REWRITE]

> Aegis has moved from a batch prototype to a connected pipeline: a phone stream is captured reliably, reconstructed and interpreted on Modal, merged into a persistent per-home memory that compacts its own history with verification, and queried by patients and caregivers through two apps by text or voice. Every answer is composed from stored evidence, and the system declines rather than guesses.
>
> The team's own measurements guided the main design changes. SAM 3 replaced YOLOE because it was the only detector that found small personal objects and hands. State runs shrank memory five to seven times without losing state. The seven-day EgoLife run showed that individual objects persist for days, but also exposed a real weakness in cross-session room identity.
>
> FYP-2 must show what FYP-1 could not yet measure: accuracy on a frozen held-out clip, temporal questions, latency, usability and secure caregiver access.

---

## Appendices

| App. | Content |
|---|---|
| A | Tables 3.1 + 3.4 in long form with evidence links |
| B | Updated `\uctable`s: UC-02 (on-device STT; FRs FR6, FR7.1), UC-04, UC-06 (crops), UC-08, UC-10 (`/activities`), UC-11 (pause/resume implemented), UC-12 (implemented; A1 = verification failure keeps detail), UC-14, UC-15. Coverage paragraph generated from Table 4.1 |
| C | One row per test file (53 files, 451 tests) using the counts in `DIAGRAM_SPECS.md` F8.1, grouped C.1–C.7, plus Flutter tests and the acceptance boundary |
| D | Updated layout (`src/aegis/{core,ingestion,geometry,perception,memory,nlq,remote,evaluation,visualization}`, `apps/Patient App`, `apps/Caregiver App`, `evaluation/`, `scripts/`, `demo/`, `config/`), the reproduction commands from §7.4, the attribution table, and tags/branches |
| E | Full-page versions of F5.7 (ERD), F7.1, F7.2 and F5.12, or delete the appendix (G7) |
| F | Meetings after 20 Oct, same format [[TEAM INPUT]] |
| G (new) | G.1 detection protocol and per-variant table; G.2 memory-audit tables (measured + projected); G.3 EgoLife protocol, query-bank summary, cost, per-day results [[Faizan]]; G.4 Ego4D readiness checklist (0/100, blockers, 10.8 weeks); G.5 `demo05` readiness (NOT_READY) and the annotation templates list |
