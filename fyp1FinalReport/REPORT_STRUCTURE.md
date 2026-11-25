# FYP-1 Final Report: Structure and Content Guide

**Project:** Aegis: A Spatio-Temporal Memory System for Assistive Care (F26-062)
**Team:** Shahmeer Amir (23I-0626), Faizan ur Rehman Khan (23I-3021, Git `pez-Ox`), Ali Sher (23I-0683)
**Supervisor:** Ms. Marium Hida
**Base document:** the FYP-1 mid report in `fyp_report/` (LaTeX, 128 pages, compiled 22 Oct 2026)
**Code baseline for this guide:** branch `develop` at `ce49dcc` (24 Nov 2026), which contains `main` and `feat/NLQ`

**Companion files in this folder:**

| File | Contents |
|---|---|
| `DIAGRAM_SPECS.md` | Exact contents of every figure. **Its figure IDs and specs are authoritative and supersede §6 below** |
| `MID_REPORT_ERRATA.md` | 69 mistakes found in the mid report, each with a fix |
| `NEW_CONTENT.md` | Draft prose and filled tables for every chapter |

---

## 0. Read this first

### 0.1 What this document is

This is the build sheet for the FYP-1 final report. The final report is the mid report modified, not rewritten from scratch. It uses the same template, the same front matter, the same chapter skeleton and the same macros. This guide says, chapter by chapter and section by section:

- what to **keep** unchanged
- what to **update**, and with which facts
- what is **new**
- every **figure** the report needs, with its diagram type, contents, source of truth in the code, and whether it is reused, redrawn or new
- every **table** that needs a new column or new rows

### 0.2 Sources used

| Source | What it gave |
|---|---|
| `fyp_report/main.tex`, `fyp_report/chapters/*.tex`, `main.toc/.lof/.lot` | The exact mid-report structure, figures, tables and macros |
| `docs/FYP-1-Mid-Assessment-Guidelines-and-Rubrics.pdf` | Form 2 (demo) and Form 3 (report) criteria and gates |
| `CONTEXT.md`, `TODO.md` (develop) | Current architecture, what works, known gaps |
| `docs/detection_benchmark.md`, `docs/egolife.md`, `evaluation/reports/*` | Measured results since the mid report |
| `git log` / `git shortlog` on develop | Commit evidence, contribution counts, dates |
| `uv run pytest -q` on develop, 25 Nov 2026 | **451 passed** |

### 0.3 Assumptions to confirm with the supervisor

1. **No separate FYP-1 *final* report guideline was found** in the repo or the project folder. This guide assumes the final panel reads the report against the same Form 3 criteria as the mid report (Section 3 below). If the FYP office issued a final-report template or rubric, check it against Section 4 and adjust.
2. **The mid-evaluation feedback is not recorded anywhere in the repo.** Chapter 3 needs it; the team must supply it (Section 10, item 1).
3. The final report covers work up to the end of **Iteration 2**. Iterations 3 and 4 stay in FYP-2.

### 0.4 How to use this guide

1. Copy the template into this folder (Section 1.1).
2. Work through Section 5 one chapter at a time. Each chapter lists its sections in order with **KEEP / UPDATE / NEW** tags.
3. Draw the figures listed in Section 6. Each figure has an ID (`F5.3` etc.), a file name and a spec. Figure IDs here are guide IDs. LaTeX numbers them automatically.
4. Take every number from Section 8 (the facts sheet). If a number is not there, it has not been verified: measure it or leave it out.
5. Before submission, run the checklist in Section 11.

---

## 1. Build setup (same template as the mid report)

### 1.1 Folder layout

Copy the LaTeX sources, not the build products:

```
fyp1FinalReport/
├── REPORT_STRUCTURE.md        ← this file
├── main.tex                   ← copied from fyp_report/, then edited (1.2)
├── fast-nuces-bs.cls          ← unchanged
├── IEEEtran.bst, tikz-uml.sty, soul.sty   ← unchanged
├── chapters/                  ← copied, then edited/renamed (1.3)
├── references/references.bib  ← copied, then extended (Chapter 2)
└── ThesisFigs/                ← copied, then figures replaced/added (Section 6)
```

Do **not** copy `main.aux`, `.log`, `.toc`, `.lof`, `.lot`, `.out`, `.bbl`, `.blg`, `main.pdf`, `best`, or the `poster/` folder. `best` is an older copy of `main.tex` with different `\needspace` values. Delete it to avoid confusion.

### 1.2 Changes to `main.tex`

| Line / item | Mid value | Final value |
|---|---|---|
| `\degreemonth{October}` | October | The final submission month (December 2026 if that is the deadline; confirm) |
| `\deanname`, `\directorname`, `\hodname` | Placeholders ("Dr. Dean Computing" etc.) | Real names. These were never filled in for the mid report, which is a Form 3 criterion 1 (format) risk |
| `\fypcoordinatorname{Name of FYP Coordinator}` | Placeholder | Real name |
| `\input` list | 10 chapters + 6 appendices | 11 chapters + 7 appendices (Section 4) |
| Macros `\aegisfig`, `\uctable`, `\captionof`, `ltab`, `\signatureblock` | as is | Keep unchanged. All new figures and use cases must use them |

### 1.3 File renames (fix the mid-report numbering mismatch)

In the mid report the file names did not match the printed chapter numbers. `chapter8_testing.tex` printed as Chapter 7, `chapter9_development_evidence.tex` as Chapter 8, and `chapter10_fyp2_plan.tex` as Chapter 9. Rename so that file number equals chapter number:

| Final chapter | File |
|---|---|
| 1 | `chapter1_introduction.tex` |
| 2 | `chapter2_research.tex` |
| 3 | `chapter3_iteration_plan.tex` |
| 4 | `chapter4_requirements.tex` |
| 5 | `chapter5_design.tex` |
| 6 | `chapter6_iteration1.tex` |
| 7 | `chapter7_iteration2.tex` (**new**) |
| 8 | `chapter8_testing.tex` |
| 9 | `chapter9_development_evidence.tex` |
| 10 | `chapter10_fyp2_plan.tex` |
| 11 | `chapter11_conclusion.tex` (was `conclusion.tex`) |

### 1.4 Figure conventions (keep exactly as the mid report)

- `\aegisfig[width]{file}{caption}{label}` only looks for **`ThesisFigs/<file>.png`**. A `.svg` or `.jpeg` will show "Missing figure". Export every diagram as PNG, at 300 dpi or at least 2000 px wide.
  - The mid report embedded `chapter6-screenshot-evidence.jpeg` with a raw `\includegraphics` call.
  - Screenshots may stay JPEG only if they use the same raw `\includegraphics`. Converting them to PNG is simpler.
- **Line-style convention, stated at the top of Chapter 5:** solid elements are implemented and dashed elements are planned. Every redrawn diagram must follow it.
- **Notation:**
  - UML 2.5 for use case, class, component, deployment, sequence, state and activity diagrams.
  - Gane–Sarson or Yourdon for DFDs (pick one and use it for both levels).
  - Crow's-foot notation for the ERD.
  - Draw.io, PlantUML or `tikz-uml` are all fine. Keep the editable source next to the PNG (`ThesisFigs/src/<file>.drawio` or `.puml`) so diagrams can be defended and updated.
- **File naming:** `ch<N>-<short-name>.png`, lowercase, hyphens, no spaces, brackets or double dots. Fix these mid-report names:
  - `classdiagram(a).png` → `ch6-class-core-models.png`
  - `classdiagram(b).png` → `ch6-class-live-api.png`
  - `chapter8-gantt..png` → `ch9-commit-timeline.png`
  - `queryframe2planned-dequence.png` → `ch5-seq-spoken-query.png`
- **Captions must not apologise.** Many mid-report captions said things like "room types are described in the text but are not yet depicted". The rubric penalises design artefacts that do not match the code (Form 2 #5, Form 3 #5 and #6). Every Chapter 5 and Chapter 7 diagram must be **redrawn to match `develop`**, so the captions can simply say what the figure shows.

### 1.5 Compile

Same as the mid report: `pdflatex main` → `bibtex main` → `pdflatex main` → `pdflatex main`. Fix every `Missing figure` box and every `??` reference before submission.

---

## 2. Global editing rules

### 2.1 Status vocabulary

Use these four words for every requirement, use case, feature and acceptance check. Use them consistently in text, tables and captions.

| Word | Meaning | Evidence required |
|---|---|---|
| **Implemented** | Exists on `develop` and is covered by passing tests | File path and test file |
| **Partial** | A slice exists; say exactly what is missing | File path, plus the missing part |
| **Planned** | Specified but not built | Target iteration (3 or 4) |
| **Measured** / **Unmeasured** | Whether a numeric result exists | Report file or output artifact |

### 2.2 Honesty rules carried over from the mid report

These are supervisor follow-ups from 13 and 20 Oct, and the team's own working rules. The final report must keep them.

1. Every claim ties to a commit, a file, a test or a report. No claim without evidence.
2. No calibrated metric accuracy. VGGT-Ω coordinates are scale-ambiguous ("scene units", not metres).
3. No clinical, usability or Ego4D benchmark claim. `option_c` is **NO_GO, 0/100**, and no usability study has been run.
4. Linear projections (for example the 8 h and 24 h storage figures) must be labelled **projection**, never "measured".
5. Room metrics (SC9 / AC-22) stay **Unmeasured** until an annotated multi-room clip is scored.

### 2.3 Numbers that changed since the mid report (search and replace all of them)

| Mid report said | Final must say | Source |
|---|---|---|
| "84 tests, 84/84 passing" (appears in the Abstract, Executive Summary, Ch 7, Ch 10 and App. C) | **451 passed** on `develop` at `ce49dcc` (re-run on the submission commit and update) | `uv run pytest -q` |
| "Compaction is not implemented" | Three-day-then-summary compaction is implemented with verification (`memory/compaction.py`, `memory/summaries.py`), with week/month roll-up | `CONTEXT.md` §5 |
| "No relational database" | Per-home SQLite store, 12 tables (`memory/store.py`) | code |
| "Speech not implemented" | Patient App has on-device speech-to-text (`speech_to_text` package, `voice_service.dart`). Server-side ASR is not used | code |
| "YOLO-World/SAM 2" | Shipped detector is **SAM3** with an 18-class compact prompt set. YOLOE / YOLO-World remain configurable backends. Re-ID embeddings switched to **DINOv3** | `docs/detection_benchmark.md`, commit `950ede7` |
| `apps/mobile/` | `apps/Patient App/` and `apps/Caregiver App/` (legacy `apps/mobile` removed) | repo tree |
| FastAPI routes: health, query, timeline, anchors, scene_graph, rooms, rooms/rename | Add `/ask` (GET/POST), `/enroll`, `/activities`, `/crops/{instance_id}`, `/video/{dataset_id}`, `/datasets`, `/dataset/select`, `/capture/status\|pause\|resume`, and the simulator routes (gated by `require_simulator`) | `src/aegis/remote/api.py` |
| `docs/evaluation_plan.md` | Archived. The live protocol is `docs/evaluation_suite.md` | `docs/archive/` |

### 2.4 Consistency checks

- A use case, FR or AC marked Implemented in Chapter 4 must have a matching row in Chapter 8 or Appendix C with a test file.
- Iteration 2 deliverables in Chapter 3 must match what Chapter 7 says was delivered. Deviations go in Section 3.8.
- Contribution text in Chapter 9 must match the Git evidence table (Section 8.3 of this guide).

---

## 3. What the panel marks, and where it is answered

The Form 3 (report) criteria and the Form 2 (demo) criteria that the report must support:

| Rubric criterion | Marks | Answered in | What the panel looks for |
|---|---|---|---|
| F3-1 Report format and artefacts | 5 | Front matter, all chapters, appendices | Template followed; signatures; all sections; no missing figures |
| F3-2 Problem formulation, R&D, gap | 15 | Ch 1, Ch 2 | Project-specific literature synthesis, a clear gap, the CCP. Generic or GenAI-style text triggers a **mandatory rewrite** gate |
| F3-3 Vision, scope, success criteria | 10 | Ch 1 | Scope table, modules, testable success criteria consistent with the proposal |
| F3-4 Requirements and acceptance | 15 | Ch 4, App. B | Numbered testable FRs/NFRs, ACs with pass conditions, traceability |
| F3-5 Architecture, component and interface design | 15 | Ch 5 | Layered architecture, components, interface contracts. Diagrams must not be purely decorative or auto-generated |
| F3-6 Data, process and behaviour design | 10 | Ch 5, Ch 7 | ERD/schema, DFD, sequence, activity and state diagrams, explained in text |
| F3-7 Implementation documentation | 15 | Ch 6, Ch 7, App. D | Setup, main files/classes/functions, algorithms, trade-offs, reproducible commands |
| F3-8 Testing, tool and risk disclosure | 15 | Ch 8, Ch 9 | Test plan and results, full GenAI tool disclosure (item scores **0** until disclosed), risks, privacy |
| F2-1 Proposal actions addressed | 10 | Ch 3, App. A | Action register with status and evidence link per action |
| F2-2 Iteration plan progress | 10 | Ch 3 | Planned vs actual, justified delays, recovery plan with owners |
| F2-5 Design evolution | 15 | Ch 5 (Design Evolution) | Design changes since the mid report, with reasons |
| F2-6 Repository and member evidence | 10 | Ch 9, App. D | Tags, commit timeline, every member's ownership visible |
| F2-7 Testing | 10 | Ch 8, App. C | Executed tests and failure cases discussed |

---

## 4. Final outline at a glance

| # | Chapter / appendix | Mid equivalent | Action | Target pages |
|---|---|---|---|---|
| — | Students' Submission | same | UPDATE wording | 1 |
| — | Anti-Plagiarism Statement | same | KEEP | 1 |
| — | Authors' Declaration | same | UPDATE wording | 1 |
| — | Abstract | same | REWRITE status paragraph | 1 |
| — | Acknowledgments | same | KEEP (optionally add EgoLife dataset authors) | 1 |
| — | Executive Summary | same | REWRITE status and risks | 2 |
| — | List of Abbreviations | same | EXTEND | 1–2 |
| — | Table of Contents, List of Figures, List of Tables | auto | — | — |
| 1 | Introduction and Project Vision | Ch 1 | LIGHT UPDATE | 13–14 |
| 2 | Research and Existing Solutions | Ch 2 | UPDATE + new findings | 10–12 |
| 3 | Proposal and Mid-Evaluation Feedback, Iteration Plan | Ch 3 | MAJOR UPDATE | 12–14 |
| 4 | Software Requirements | Ch 4 | UPDATE status, add UCs/FRs | 20–22 |
| 5 | System Design | Ch 5 | **REDRAW ALL DIAGRAMS** + new ones | 18–22 |
| 6 | Iteration 1: Design and Implementation | Ch 6 | FREEZE + exit-criteria outcome | 6–7 |
| 7 | **Iteration 2: Design and Implementation** | — | **NEW** | 14–18 |
| 8 | Testing and Validation | Ch 7 | MAJOR UPDATE (measured results) | 12–15 |
| 9 | Project Management and Development Evidence | Ch 8 | UPDATE | 9–10 |
| 10 | Remaining FYP Plan (FYP-2) | Ch 9 | REWRITE | 5–6 |
| 11 | Conclusion | Ch 10 | REWRITE | 1–2 |
| A | Proposal and Mid-Evaluation Action Register | App. A | EXTEND | 2 |
| B | Supplementary Use-Case Specifications | App. B | UPDATE status | 5 |
| C | Detailed Test Cases and Results | App. C | REWRITE for 451 tests | 5–6 |
| D | Repository and Contribution Evidence | App. D | UPDATE | 4 |
| E | Additional Design Diagrams | App. E (was empty) | FILL or DELETE | 3–6 |
| F | Meeting and Progress Evidence | App. F | EXTEND with Oct–Nov meetings | 2–3 |
| G | **Evaluation Protocols and Raw Results** | — | **NEW** | 4–6 |
| — | References | same | EXTEND | 3 |

Expected length is about 150–170 pages. The mid report was 128.

---

## 5. Chapter-by-chapter specification

### Front matter

**Students' Submission** (`01_students_submission.tex`): change "submitted as the FYP-1 mid-report" to "submitted as the FYP-1 final report". Keep `\signatureblock`.

**Anti-Plagiarism Statement:** KEEP.

**Authors' Declaration:** change "up to the FYP-1 mid-report stage" to "up to the end of FYP-1". Keep the GenAI sentence but point it to the new section number (Chapter 9, Tools and Tool-Assisted Development).

**Abstract** (about 250–300 words, two paragraphs plus keywords):
- **Paragraph 1:** KEEP as is (problem, gap, what Aegis is).
- **Paragraph 2:** REWRITE the status part. It must state:
  - What Iteration 1 and Iteration 2 delivered, in one sentence each.
  - The test count.
  - One or two measured results, for example detection F1 0.721 on the 10-frame, five-environment benchmark, and the 5.7–7.2× compaction ratio with 100% semantic retention on demo03/demo04.
  - What is still not proven: room metrics, the latency p95, the usability study and calibrated confidence.
  - What FYP-2 will do.
- **Keywords:** add "scene graph" and "natural-language querying".

**Acknowledgments:** KEEP. Optionally thank the EgoLife and VGGT authors for public data and weights.

**Executive Summary** (2 pages, same bold-label paragraphs as the mid report):

| Paragraph | Action | Content |
|---|---|---|
| Motivation | KEEP | — |
| Project | KEEP; one fix | Mention the two apps (patient and caregiver) instead of "a caregiver portal" |
| Research findings | UPDATE | Add one sentence on what was learned since the mid report: the detector A/B (SAM3 over YOLOE/YOLO-World) and the cross-session room-identity instability found by the EgoLife run |
| Requirements and plan | UPDATE | Number of FRs and ACs after the Chapter 4 changes; four iterations, two now complete |
| Implementation and validation status | REWRITE | Iteration 2 deliverables (Section 7.5); 451 tests; the measured results listed in the Abstract; what is unmeasured |
| Risks and remaining work | REWRITE | Top three risks now: (1) room identity across sessions (absolute `zone_link_radius` in scale-free VGGT units); (2) temporal/activity answering not implemented (the NLQ abstains by design); (3) no auth or encryption. Then the FYP-2 summary |

**List of Abbreviations:** extend the table with:
- API, ASR, CCP, CI/CD, CORS, DFD, ERD, F1, FPS, GPU, HTTPS, IoU, LLM, MJPEG, NLQ, OBB
- R4DSG, RANSAC, Re-ID, SAM, SG, SQLite, STT, VGGT, YOLOE, UTC

Keep alphabetical order.

---

### Chapter 1: Introduction and Project Vision (LIGHT UPDATE)

The vision and scope were approved, so leave the substance alone. Change only what has gone out of date.

| § | Section | Action | Details |
|---|---|---|---|
| 1.1 | Project Overview | KEEP | — |
| 1.2 | Problem Statement | KEEP | Formal (a)/(b)/(c) statement unchanged |
| 1.3 | Problem Context and Motivation | KEEP | Figure F1.1 unchanged |
| 1.4 | Project Vision | KEEP | — |
| 1.5 | Project Objectives | UPDATE table 1.1 | Add a column **"Status at FYP-1 end"** (Implemented/Partial/Planned + one-line evidence) for O1–O7. For example, O3 is Partial: compaction is implemented and verified, and the before/after query accuracy (SC3) is unmeasured |
| 1.6 | Project Scope | UPDATE table 1.2 "Scope split across FYP-1 and FYP-2" | Move items that were done in FYP-1 (compaction, SQLite store, NLQ `/ask`, two apps, on-device STT) into the FYP-1 column; keep auth/encryption, temporal answering, usability study and the benchmark in FYP-2. **Redraw F1.2** |
| 1.7 | Project Modules | UPDATE table 1.3 | Module M-C now names the **rule-based NLQ engine** (`src/aegis/nlq/`) and `/api/v1/ask`; M-D names both Flutter apps. **Redraw F1.3** |
| 1.8 | Stakeholders and User Classes | KEEP | Table 1.4 unchanged |
| 1.9 | Success Criteria | UPDATE table 1.5 | Add a column **"FYP-1 evidence"** for SC1–SC9: write "Unmeasured" or the measured value with its source. Do not change thresholds without supervisor sign-off |
| 1.10 | Constraints and Assumptions | UPDATE | Add the measured Modal cost (one 5-min segment on L4 = 0.086 GPU-h ≈ $0.069; EgoLife 74 segments $8.71 metered). Add that VGGT-Ω weights come from the gated `facebook/VGGT-Omega` repo, with fallback to the public mirror. State C4 (dataset) as: EgoLife A1_JAKE used for the multi-day study; Ego4D NO_GO |
| 1.11 | Ethical, Legal and DEI | UPDATE | Add: EgoLife is a public dataset of consenting volunteers, used for evaluation only; evidence crops are retained past the 24-hour raw-frame rule (supervisor decision #9 pending); no auth or encryption yet |

**Figures:** F1.1 (keep), F1.2 (redraw), F1.3 (redraw). See Section 6.

---

### Chapter 2: Research and Existing Solutions (UPDATE)

This chapter carries 15 marks, and the rubric has a **red-flag gate for generic GenAI text**. Each member must be able to explain any paragraph in their own words. Add depth that only this project could have, meaning the team's own experiments.

| § | Section | Action | Details |
|---|---|---|---|
| 2.1 | Research Method / Approach | UPDATE | Add a sentence: the team ran its own component experiments (detector A/B, compaction audit, EgoLife multi-day run) to choose between candidate methods |
| 2.2 | Existing Solutions / Products | KEEP | MemPal, R4DSG, DAAAM, CrossSense |
| 2.3 | Comparison of Existing Solutions | UPDATE table 2.1 | Re-check the Aegis column against `develop`. For example, "progressive temporal abstraction" is now implemented; "caregiver querying" is Partial (no auth) |
| 2.4 | Limitations and Gaps | KEEP | — |
| 2.5 | Proposed Solution | UPDATE | **Redraw F2.1** (pipeline). F2.2 (gap positioning) unchanged |
| 2.6 | Complex Computing Problem | UPDATE table 2.2 | Add the evidence column: the fidelity–storage trade-off now has a measured data point (memory-control audit: 5.7–7.2× smaller at snapshot interval 0, 100% semantic retention). Long-term persistence over days has partial evidence: the EgoLife oracle diagnostic found 12/12 instances still in store 1–4 days later, while the class-level queries did **not** beat the 24 h ablation. Report both honestly |
| 2.7 | Technical Challenges | UPDATE table 2.3 | Add a "What we found" column for TC1–TC11. New challenge TC12: **cross-session room identity under scale-free reconstruction** (from `docs/egolife.md` limitation 2) |
| 2.8 | Research Findings and Design Decisions | UPDATE table 2.4 | Add rows for the decisions made since the mid report, each with its evidence (see the list after this table) |
| 2.9 | **NEW: Model and Method Selection Experiments** | NEW (1–2 pages) | Short write-up of the detector A/B as research evidence: 10 hand-labelled frames, 960×540, five environments, IoU ≥ 0.30. **Figure F2.3** (grouped bar chart) |

Decisions to add as rows in table 2.4:
- SAM3 open-vocabulary detector over YOLOE/YOLO-World
- DINOv3 re-ID embeddings
- Gravity frame from a RANSAC floor fit, stored beside raw coordinates
- Rule-based closed-vocabulary NLQ (525 items) instead of free LLM answering, chosen so the system never fabricates
- SQLite per-home store instead of a growing JSON file
- State runs (run-length encoding) instead of per-frame timelines

**References to add to `references.bib`** (verify each citation yourself; do not let a tool invent BibTeX):
- SAM 3
- DINOv3
- YOLOE
- EgoLife (dataset and paper)
- Hydra (room segmentation)
- HOV-SG (if not already cited)
- RANSAC (Fischler & Bolles 1981)
- Flutter `speech_to_text` (as software)

---

### Chapter 3: Proposal and Mid-Evaluation Feedback, Iteration Plan (MAJOR UPDATE)

Rename the chapter to **"Proposal and Mid-Evaluation Feedback, and Iteration Plan"**. This chapter answers Form 2 criteria 1 and 2 (20 marks).

| § | Section | Action | Details |
|---|---|---|---|
| 3.1 | Proposal Feedback Summary | KEEP | Panel comments and four required modifications, verbatim |
| 3.2 | Proposal Action Register | UPDATE table 3.1 | Same 4 rows. Update **Status** and add an **Evidence** column with a concrete link (commit hash, file, figure number) |
| 3.3 | **NEW: Mid-Evaluation Feedback Summary** | NEW | Supervisor feedback and marks from the mid evaluation (Form 2/Form 3 comments), verbatim where possible. **Team must supply this** |
| 3.4 | **NEW: Mid-Evaluation Action Register** | NEW table | Columns: No., Feedback item, Action taken, Evidence (commit/file/section), Status. One row per feedback item. This is the "Panel Action Register" the rubric looks for |
| 3.5 | Iteration Strategy | UPDATE | Keep the vertical-slice text and F3.2 (iteration cycle). Update table 3.2 "Iterations mapped to milestones": set Iteration 1 = **Complete**, Iteration 2 = **Complete** (with end date), Iterations 3–4 = FYP-2 with tentative dates |
| 3.6 | Iteration 1 Plan | KEEP + 1 row | Keep table 3.4 and add a row **"Outcome"** pointing to Section 6.9 |
| 3.7 | Iteration 2 Plan | KEEP + 1 row | Keep table 3.5 as it was planned at mid (do not rewrite history) and add a row **"Outcome"** pointing to Section 7.9 |
| 3.8 | Work Breakdown and Responsibilities | UPDATE tables 3.3, 3.6, 3.7 | Reflect who actually led what in Iteration 2 (see below) |
| 3.9 | Progress Against Plan | REWRITE table 3.8 | Columns: Planned item, Planned iteration/week, Actual status, Evidence (commit + date). Add every Iteration 2 item (see Section 7.5). Fill in the "Planned date" column, which was empty in the mid report |
| 3.10 | Delays, Deviations and Recovery Plan | REWRITE | List each deviation with reason, impact, recovery action, owner and new date (see below) |

**Who actually led what in Iteration 2** (Section 3.8):
- **Ali Sher:** NLQ engine, `/ask`, Modal serving, the e2e runner and both Flutter apps.
- **Shahmeer:** live ingestion hardening and the M1/M2 implementation pass: gravity, OBBs, relations, scene-graph rebuild, SQLite store, rooms, activities, evidence, compaction, live segments and perception changes.
- **Faizan:** evaluation suite, EgoLife study, SAM3 detector, and the demo harness/calibration.

If responsibilities moved away from the original M-A to M-D leads, say so explicitly rather than hiding it.

**Deviations to record in Section 3.10** (one row each in a table: reason, impact, recovery action, owner, new date):
1. The voice "tool-calling agent" (planned for Iteration 2) was replaced by a rule-based closed-vocabulary NLQ plus on-device STT. Reason: grounding and no-fabrication. The LLM planner is optional and deferred (TODO P1.9).
2. Temporal/activity questions abstain by design (TODO P1.1). Moved to Iteration 3.
3. The Iteration 1 exit criterion (10 placements, ≥70% correct) is still not run with ground truth (TODO P2.2).
4. Room metrics are still unmeasured (P2.3).
5. Auth and encryption are not started (P1.7, P1.8).

**Figures:**
- **F3.1 — Planned vs actual Gantt chart**, redrawn through the final submission date. This replaces the mid "commit-evidence timeline", which moves to Chapter 9.
- F3.2 iteration cycle (keep).

---

### Chapter 4: Software Requirements (UPDATE STATUS, ADD WHAT WAS BUILT)

The requirement IDs from the mid report stay stable. **Do not renumber.** Add new IDs at the end of each block.

| § | Section | Action | Details |
|---|---|---|---|
| 4.1 | User Interactions / Use Cases | UPDATE table 4.1 (use case inventory) | Add a **Status** column. Add new use cases if the team keeps these features in scope (see below) |
| 4.2 | Use Case Diagram | **REDRAW F4.1** | The mid diagram omitted UC-13 (its caption admitted it). The new diagram must show all UCs, both actors, the System actor for compaction, and «planned» stereotype or dashed outline for planned UCs |
| 4.3 | Detailed Use Cases | UPDATE | Keep UC-01, 03, 13, 05, 07, 09 in the `\uctable` format. Rewrite each main flow and alternate flow to match the current apps and API (UC-03 now goes through `/api/v1/ask`; UC-13 now exists in the API and the Caregiver App if implemented there, so check). Add the new UCs here or in App. B |
| 4.4 | Functional Requirements | UPDATE tables 4.8–4.11 | Add a **Status** column (I/P/Pl) to each longtable. Add new sub-requirements (see below) |
| 4.5 | Non-Functional Requirements | UPDATE tables 4.12–4.15 | Add a Status column. NFR-Performance: note that only fixture timing exists, and p50/p95 over 100 warm requests is planned (P2.8). NFR-Security: still Planned; note wildcard CORS and unauthenticated mutating routes (`/rooms/rename`, `/enroll`, `/capture/*`) |
| 4.6 | Acceptance Criteria | UPDATE table 4.16 (AC-01…AC-31) | Add two columns: **Result at FYP-1 end** (Pass / Fail / Partial / Not run) and **Evidence**. Keep the pass conditions unchanged. Where a check was run, cite the report file; where not run, say "Not run" and give the TODO ID |
| 4.7 | Requirements Traceability | UPDATE table 4.17 | Columns: FR, Priority, UC(s), AC(s), Module/file, Test file(s), **Status**. Every H/M requirement must map to at least one test file or say "no test yet" |
| 4.8 | **NEW: Requirements Change Log** | NEW table | Columns: ID, Change (added/modified/deferred), Reason, Date, Approved by. Covers every requirement touched since the mid report. This directly evidences "design evolution" |

**New use cases to consider** (add only if the team agrees they are in scope):

| ID | Name | Evidence on develop |
|---|---|---|
| UC-14 | Caregiver enrolls a personal item | `POST /api/v1/enroll`, Caregiver App `enroll_dialog.dart` |
| UC-15 | Primary user contacts caregiver | Patient App `call_view.dart` (tel/SMS) |
| UC-16 | Caregiver reviews object tracking and interaction history | Caregiver App tracking, interactions, interior, status and history tabs |

UC-11 (pause capture) moves from Planned to **Partial**: `/api/v1/capture/pause` and `/resume` exist, but history deletion is not verified.

**New sub-requirements to add** (mark each with H/M/L priority):

| ID (suggested) | Requirement | Status |
|---|---|---|
| FR3.x | The system shall persist memory per home in a store with stable room, anchor and instance IDs across sessions | Implemented |
| FR3.x | The system shall classify object relations (inside, on_surface, under, above, next_to, on_floor) in a gravity-aligned frame | Implemented |
| FR4.x | The system shall verify each summary against its source detail before deleting that detail, and log the compaction | Implemented |
| FR5.x | The query engine shall answer only from a closed vocabulary and shall abstain when the item is unknown or never observed | Implemented |
| FR7.x | The patient app shall accept spoken queries using on-device speech-to-text | Implemented / Partial (confirm-and-correct step not done) |
| FR8.x | The caregiver shall be able to enroll a personal item | Implemented, no auth |

---

### Chapter 5: System Design (REDRAW EVERY DIAGRAM TO MATCH `develop`)

This chapter carries 25 report marks (F3-5 plus F3-6) and 15 demo marks (F2-5). It was the mid report's weakest point: diagrams were images with almost no explanatory text, and captions admitted the figures did not match the code. Rules for the final:

- **Every figure gets at least one explanatory paragraph**: what it shows, how to read it, and which code it maps to. The mid Chapter 5 was 36 lines of LaTeX for 11 figures.
- **Every diagram matches `develop`**, using the solid = implemented, dashed = planned convention.

| § | Section | Action | Figures | Text to write |
|---|---|---|---|---|
| 5.1 | System Architecture | REDRAW | **F5.1** layered architecture | One paragraph per layer: responsibilities, main modules, what crosses the layer boundary |
| 5.2 | Architectural Components | REDRAW + NEW | **F5.2** component diagram with interfaces; **F5.3** deployment diagram | Component responsibilities table (component, package path, provides, requires) |
| 5.3 | Interfaces and Dependencies | REWRITE + NEW table | — | **Table: API contract.** One row per route: method, path, request params/body, response model, auth (currently "none"), mutating? (Y/N). Use the 20 routes in `api.py` (Section 8.4). **Table: artifact contracts:** `r4d_scene_graph.json` schema v2 top-level keys; `r4d_timeline.json`; live session files `frame_*.jpg`, `index.jsonl`, `session.json`, `session_state.json`; `gravity.json`; `memory.db`; `home_map.json`. Source: `docs/artifact_contracts.md` |
| 5.4 | Architecture Decisions and Rationale | REWRITE as ADR table | — | Columns: Decision, Alternatives considered, Rationale, Evidence, Consequence (see below) |
| 5.5 | Design Evolution | REWRITE (1 page) | **F5.4** before/after architecture (optional, side by side) | Mid design vs FYP-1 final design (see below). Each change gets one reason. The rubric scores this directly |
| 5.6 | Domain Model | REDRAW | **F5.5** conceptual class diagram | Explain each concept and multiplicity |
| 5.7 | Data Design | REDRAW + NEW | **F5.6** scene-graph v2 document model; **F5.7** SQLite ERD (12 tables); **F5.8** live-session artifact layout (optional) | For the ERD: one sentence per table, primary and foreign keys, and which tables compaction writes (`summary`, `compaction_log`) and which it never deletes (latest state) |
| 5.8 | User Interface Design | MOVE + REDRAW | **F5.9** Patient App screen flow; **F5.10** Caregiver App screen flow | Was inside 5.7 in the mid report. Explain how the panel's "fix the app design" action is addressed (accessible tiles, large controls, espresso/ochre theme, voice rings) |
| 5.9 | Process / Behaviour Design | REDRAW + NEW | F5.11–F5.19 (see below) | One paragraph per figure |

**ADR rows for Section 5.4** (at least these):
- Raw VGGT-Ω coordinates plus a separate gravity frame
- Rooms from trajectory clustering plus sparse landmarks, never dense clouds
- State runs instead of per-keyframe timeline
- Per-home SQLite store
- Three-day detail window then verified text summaries
- SAM3 detector
- DINOv3 re-ID
- Rule-based closed-vocabulary NLQ, with the LLM as an optional parser only
- Artifacts stay on the Modal volume; no local download on the normal path
- Thin client apps that never mutate memory
- Modal CPU serving for `/ask`

**Changes to cover in Section 5.5 (design evolution):**
- Graph schema v1 (timeline) became v2 (state runs, latest states, events, room visits).
- JSON memory became the SQLite home store.
- YOLO-World became SAM3.
- The old Ali/NL-Querying folder became `src/aegis/nlq`.
- `apps/mobile` became the two apps.
- Local FastAPI became Modal-deployed `serve.py`.
- Compaction went from planned to implemented.

**Process and behaviour figures for Section 5.9:**

| Figure | Type | Replaces |
|---|---|---|
| F5.11 | DFD level 0 (context) | — |
| F5.12 | DFD level 1 | mid `dfd.png` |
| F5.13 | Sequence: batch/live pipeline on Modal | mid `chapter5-batch-sequence` |
| F5.14 | Sequence: `/ask` query, text or voice, with grounded answer or abstention | mid `query-sequence` and `queryframe2planned-dequence` |
| F5.15 | Sequence: caregiver room rename and personal-item enrollment | mid `caregiverquerysequence` |
| F5.16 | State machine: live capture session | new |
| F5.17 | State machine: object instance (state runs and events) | new |
| F5.18 | Activity diagram: daily compaction with verification | new |
| F5.19 | Activity diagram / flowchart: NLQ answer engine decision flow | new |

---

### Chapter 6: Iteration 1: Design and Implementation (FREEZE + CLOSE)

Iteration 1 is history. Do not rewrite it to look better. Freeze it at the mid-report state, label it with the tag, and add its final outcome.

| § | Section | Action | Details |
|---|---|---|---|
| 6.1 | Iteration Objectives | KEEP | Add one line: "Baseline tag `v0.2.0-mid2` (13 Oct 2026); mid report evidence through 17 Oct 2026." |
| 6.2 | Selected Use Cases / Features | KEEP | — |
| 6.3 | Design | KEEP figures, fix captions | F6.1, F6.2 class diagrams and F6.3 sampling flowchart. Rename the files (Section 1.4). Captions say "as implemented in Iteration 1 (tag `v0.2.0-mid2`)". Remove the "not depicted" disclaimers |
| 6.4 | Implementation | KEEP | Make sure file names are those of Iteration 1 |
| 6.5 | Completed Features / Module | TRIM | Move the 17 Oct room work description to Chapter 7, which is where the mid report itself said it belonged (Iteration 2 refinement) |
| 6.6 | Technical Implementation Details | KEEP | — |
| 6.7 | Tools, Frameworks and Technologies | KEEP | — |
| 6.8 | Demonstration Evidence | KEEP | F6.4 screenshot |
| 6.9 | Iteration Outcome | UPDATE | State the final exit-criteria result honestly. The criterion was "10 object placements ingested, ≥70% last-location correct". If run before submission, give the number and the clip; if not, say "not evidenced; scheduled as P2.2 in Iteration 3" |

---

### Chapter 7: Iteration 2: Design and Implementation (NEW)

This chapter mirrors Chapter 6's section list exactly, so the panel sees the same structure twice. It is the main answer to F3-7 implementation documentation (15 marks). Each member should write the sections on the work they led and be ready to defend them.

| § | Section | Content |
|---|---|---|
| 7.1 | Iteration Objectives | Restate the Iteration 2 objective from table 3.5 ("temporal depth and natural-language access"), plus the M1/M2 completion pass. Period: 18 Oct → end date. |
| 7.2 | Selected Use Cases / Features | UC-02, UC-04, UC-05 (as planned), plus UC-06, UC-11 (partial), UC-12, UC-13 and the new UC-14/15/16 if added. Table: UC → FRs → delivered? |
| 7.3 | Design | Figures F7.1–F7.4 (see below). One paragraph each |
| 7.4 | Implementation | Walk through the code **by package**, with file → responsibility → key classes/functions. Packages and modules are listed below this table |
| 7.5 | Completed Features / Module | Table: Feature, FR/UC, Owner, Commit(s), Test file(s), Status. One row per Iteration 2 deliverable (list below) |
| 7.6 | Technical Implementation Details | Algorithms and parameters (list below) |
| 7.7 | Tools, Frameworks and Technologies | Add the Iteration 2 tools (list below). Python 3.12 + uv unchanged |
| 7.8 | Demonstration Evidence | Figures F7.5–F7.8: real screenshots only (Patient App, Caregiver App, Rerun 3D memory view, `aegis-ask` terminal session over HTTPS). Plus a short table of the measured e2e run (Section 8.2 facts) |
| 7.9 | Iteration Outcome | Exit criteria from table 3.5 vs result. "Spatial and temporal queries answered correctly at the Iteration 2 target" → spatial: give a number if measured; temporal: **not met** (abstains by design). "Abstention on ≥5 unanswerable queries" → cite `tests/test_nlq.py` abstention tests and/or the EgoLife keys/wallet abstention probes. List what carries into Iteration 3 |

**Code walk-through for Section 7.4, by package:**
- `core/`:
  - `vocabulary.py` with `config/vocabulary.yaml` as the single ontology
  - `timeutil.py` (UTC ISO)
- `ingestion/`:
  - `keyframe.py` (criterion keyframes)
  - `buffer.py` (bounded buffer, stall accounting)
  - `contracts.py` (schema-v2 validation)
  - `live_pipeline.py`, `segment_runner.py` (JPEG segments, resume)
  - `live_handoff.py` (promotion to dataset)
- `geometry/`:
  - `gravity.py` (RANSAC floor and gravity frame)
  - `planar.py`
  - `lifting.py` (mask-grounded oriented boxes)
- `perception/detector.py`: SAM3 / YOLOE / YOLO-World backends, class-aware suppression, batching, DINOv3 re-ID
- `memory/`:
  - `relations.py`
  - `runs.py` (state runs)
  - `scene_graph.py` (v2 builder)
  - `rooms.py`
  - `store.py` (SQLite)
  - `ingest.py` (session → home store)
  - `matching.py` (cross-session matching)
  - `activities.py` (room-stay activities)
  - `evidence.py` (object-only crops)
  - `compaction.py` and `summaries.py` (3-day window, verified summaries, roll-up)
  - `personal.py` (enrolled personal items)
  - `repository.py`
- `nlq/`:
  - `dictionary.py` (525-item closed vocabulary, synonyms, word-boundary matching)
  - `engine.py` (intent → retrieval → grounded answer or abstention)
  - `cli.py` (`aegis-ask`)
- `remote/`:
  - `api.py` (`/ask`, `/enroll`, `/activities`, `/crops`, `/capture/*`)
  - `serve.py` (Modal CPU ASGI deploy)
  - `modal_app.py` (CPU fallback, volume reload)
- `evaluation/`: `egolife.py`, `memory_audit.py`, `controlled_room.py`, `option_c.py` (harness that refuses to invent scores)
- `scripts/run_e2e.py`: one-command runner with human-in-the-loop checkpoints
- `apps/Patient App/` and `apps/Caregiver App/`: models, services (API client, voice, dialer, persistence), views

**Iteration 2 deliverables for the Section 7.5 table.** Take dates and hashes from `git log`.
- Live: pause/gap/crash-resume, promotion (Shahmeer, 6 Nov)
- Gravity frame, OBBs, relations, scene-graph rebuild, SQLite store, rooms, activities, evidence crops, compaction, JPEG segments, class-aware suppression (Shahmeer, 15 Nov)
- Evaluation suite, EgoLife study, SAM3 (Faizan, 9–22 Nov)
- Demo harness and calibration (Faizan, 17 Nov)
- NLQ engine, `/ask`, Modal serving, `aegis-ask`, e2e runner (Ali, 8–20 Nov)
- Patient App, Caregiver App, enrollment, DINOv3 (Ali, 23–24 Nov)

**Algorithms and parameters for Section 7.6:**
- Gravity: the RANSAC floor fit, and how gravity is stored beside the coordinates, never baked in.
- The relation classifier rules in the gravity frame.
- State-run encoding: why storage grows as state changes × instances instead of frames × instances.
- Cross-session matching order: room, then anchor, then instance.
- The compaction verification step: what is checked before detail is dropped, and what is never compacted (the last-known state).
- NLQ: the closed-vocabulary layers, synonym handling and abstention categories.
- SAM3 thresholds: category-level priors (shoes 0.5, hand 0.4, pot 0.6, bin 0.4, food container 0.9, others 0.8, NMS IoU 0.7).
- VGGT keyframe cap: `vggt.max_keyframes = 120`.

**Iteration 2 tools for Section 7.7:**
- SAM3, YOLOE, DINOv3, SQLite
- Modal ASGI deploy
- Flutter `speech_to_text`, `shared_preferences`, URL-launcher/dialer
- GitHub Actions CI (ruff, pytest with `--cov-fail-under=75`, Flutter analyze/test) and CD (patient APK release)

**Design figures for Section 7.3:**

| Figure | Type | Shows |
|---|---|---|
| F7.1 | Real-code class diagram | `memory` package |
| F7.2 | Real-code class diagram | `nlq` + `remote/api` + app services |
| F7.3 | Algorithm flowchart | Relation classification in the gravity frame |
| F7.4 | Algorithm flowchart | Cross-session matching into the home store |

---

### Chapter 8: Testing and Validation (MAJOR UPDATE: from "early" to "measured")

Rename from "Testing and Early Validation" to **"Testing and Validation"**. The mid chapter had no measured results. The final has several, and they must be reported with method, data, number and limitation.

| § | Section | Action | Content |
|---|---|---|---|
| 8.1 | Testing Strategy | UPDATE | Four tiers: unit, API integration, pipeline/integration (live, Modal compute with fakes), and evaluation/measurement (benchmarks on real video). Add the CI gate: ruff, pytest with a 75% coverage floor, and Flutter analyze/test on `main`/`develop` |
| 8.2 | Test Levels and Techniques | REDRAW **F8.1** | Test pyramid with per-tier test counts taken from the actual suite |
| 8.3 | Test Cases | REWRITE | Summary by area. Full table in App. C |
| 8.4 | Automated Test Results | UPDATE | 451 passed (command, commit, date, duration); coverage % from the CI command (run `uv run pytest --cov=aegis` and report the real figure); ruff clean |
| 8.5 | **NEW: Component Benchmark: Object Detection** | NEW | Method (10 frames, five environments, hand-labelled, class-aware IoU ≥ 0.30, NMS 0.7), the five-variant table from `docs/detection_benchmark.md`, **F8.2** chart, decision and limitation (small benchmark) |
| 8.6 | **NEW: Memory Compaction Audit** | NEW | Method (`memory_audit`), the demo03/demo04 table (ratio, semantic retention, latest-state exactness, query agreement, centre p95 in scene units), **F8.3** chart, **F8.4** projected growth (labelled projection). Limitation: query agreement uses auto-generated label probes, not a human query bank |
| 8.7 | **NEW: End-to-End Pipeline Run** | NEW | The 20 Nov measured run (Section 8.2 facts): CPU, capture `walk01-2`, 79 frames, VGGT 831 s, detect+lift 27 s, deploy 8 s, `aegis-ask` answered over HTTPS with no local artifacts. **F8.5** stage-timing bar (optional). State it is a single run on CPU |
| 8.8 | **NEW: Multi-Day Memory Study (EgoLife)** | NEW | Protocol (A1_JAKE, 12:00–13:00 for 7 days, 74 five-minute segments, chronological ingest, DenseCaption ground truth), cost, results (see below), **F8.6** chart. Get the numbers from `outputs/evaluation/egolife_scored/FINAL_SUMMARY.md` on Faizan's machine; it is not in the repo. List all 7 known limitations from `docs/egolife.md` |
| 8.9 | Acceptance Testing / Validation | REWRITE | Summary of the AC results column from table 4.16: how many Pass, Partial, Not run. Name the ACs that were actually executed |
| 8.10 | Edge and Failure Cases | UPDATE | Keep the mid list, and add the new failure cases listed below |
| 8.11 | Defects and Corrective Actions | REWRITE as table | Columns: Defect, How found, Fix, Commit, Test added (rows listed below) |
| 8.12 | Current Validation Status | REWRITE | Two lists, "Measured" and "Not yet measured" (see below) |

**EgoLife results to report in Section 8.8:**
- Class-level queries did **not** show a long-term memory advantage: full history never beat the 24 h ablation.
- The oracle-assisted diagnostic found 12/12 matched instances still in store 1–4 days later.

**New failure cases for Section 8.10:**
- Unknown and never-observed items: NLQ abstention.
- Temporal and activity intents: abstain by design.
- Empty API volume: self-diagnoses.
- Gated VGGT checkpoint: falls back to the public mirror.
- Corrupt or missing graph: safe failure.
- Dataset isolation: no cross-dataset leakage.
- Slow network: client timeouts.

**Defect rows for Section 8.11** (at least these):

| Defect | Commit |
|---|---|
| YOLOE found 0/36 shoes and 0/19 hands; switched to SAM3 | `2a3c603` |
| API read the graph from the wrong path | `7a905d2` |
| Lexicon was not shipped in the serving image | `8c9746d` |
| Modal scaledown window was invalid | `48d8e4f` |
| Room signatures were not normalised | `61dda40` |
| API answered invented locations; fixed so it never fabricates | `2b3e6db`, `180b897` |
| Room identity unstable across sessions | open, with cause |

**Validation status for Section 8.12:**
- **Measured:** detection P/R/F1, compaction ratio and retention, the e2e stage timings, EgoLife persistence diagnostic.
- **Not yet measured:**
  - SC1/SC2 spatial and temporal accuracy on a frozen held-out set (`demo05` is NOT_READY because annotations are missing)
  - SC3 before/after-compaction accuracy on human queries
  - SC4 latency p95
  - SC8 usability
  - SC9 room metrics
  - AC-01 one-hour soak
  - AC-03 disconnect recovery
  - Ego4D: NO_GO

---

### Chapter 9: Project Management and Development Evidence (UPDATE)

| § | Section | Action | Details |
|---|---|---|---|
| 9.1 | Work Completed | REWRITE | Short summary across both iterations; refer to tables 6.x and 7.x |
| 9.2 | Work Remaining | REWRITE | From `TODO.md` P1/P2 items; refer to Chapter 10 |
| 9.3 | Individual Responsibilities | UPDATE | Assigned leads, and where actual work differed |
| 9.4 | Contribution of Each Team Member | REWRITE table 8.1 | Git evidence up to the submission commit (see the caution below). Columns: Member, Git identity, commits all-time, commits since mid (no merges), date range, areas evidenced |
| 9.5 | Repository and Version Control Evidence | UPDATE + NEW **F9.2** | Branching model (feature branches → `develop` → `main`), tags, PR template, CI/CD. **F9.2: branch and merge graph** |
| 9.6 | Milestones and Commit Evidence | REDRAW **F9.1** | Commit timeline per member, 4 Oct → submission, with iteration bands and tags. Recommend tagging the submission commit (for example `v0.3.0-fyp1-final`) and citing it |
| 9.7 | Tools and Tool-Assisted Development | **UPDATE: graded gate** | Form 3 #8 gives **0 marks for the tool item until disclosure is complete**. List every tool used since the mid report as well: Claude Code (used for repo work and drafting), Codex, Gemini, Antigravity, Pi harness, and anything else each member used. For each tool, say which member used it, what for, and how its output was reviewed. Each member must confirm their own list |
| 9.8 | External Components and Dependencies | UPDATE table 8.3 | Add SAM3, YOLOE, DINOv3, SQLite, Flutter packages, the EgoLife dataset and the Hugging Face VGGT-Ω checkpoint (gated plus mirror), with licence notes. Remove "relational database: not implemented" |
| 9.9 | Risks and Mitigation | UPDATE table 8.4 | Add a **Likelihood × Impact** score, which the rubric expects (mid was "unscored"). Update each TC with current status. Add TC12 (room identity across sessions) and R-team (integration risk from large late merges) |
| 9.10 | Security and Privacy Considerations | UPDATE | Still true: wildcard CORS, no auth. Unauthenticated mutating routes are now `/rooms/rename`, `/enroll`, `/capture/pause`, `/capture/resume` and `/dataset/select`. No encryption at rest for `memory.db`, `home_map.json` or evidence crops. Cleartext LAN is allowed in both Android apps (`network_security_config`). The deployed Modal endpoint is public HTTPS. Planned: P1.7, P1.8 |
| 9.11 | Current Limitations | REWRITE | — |

**Caution for Section 9.4.** Commit counts are badly skewed by commit granularity. For example, 122 commits by Ali Sher on 23 Nov are one-file-per-commit app scaffolding. State plainly that counts are not effort, and add a column listing **features owned** instead.

---

### Chapter 10: Remaining FYP Plan (FYP-2) (REWRITE)

| § | Section | Content |
|---|---|---|
| 10.1 | Remaining Scope | From `TODO.md` P1 and P2 |
| 10.2 | Remaining Modules and Features | Table: Feature, FR, Owner, Iteration (3 or 4), Dependency |
| 10.3 | Remaining Iterations | Iteration 3: temporal answers (P1.1), calibrated confidence (P1.2), freshness (P1.3), evidence refs (P1.4), multi-instance clarification (P1.5), speech confirm step (P1.6), room identity fix. Iteration 4: auth/grants/consent/audit/CORS (P1.7), encryption/deletion (P1.8), optional LLM planner (P1.9), performance and usability validation |
| 10.4 | Implementation Plan | Dependency order with reasons |
| 10.5 | Testing and Validation Plan | Exact protocol for each unmeasured SC and AC (list below), with an owner each |
| 10.6 | Deployment Plan | Modal-deployed API, APK release via CD, home-store location, secrets handling |
| 10.7 | Tentative Timeline | **F10.1: FYP-2 Gantt**, with real week numbers and owners |
| 10.8 | Expected Final Deliverables | Keep the mid list and add the two apps and the evaluation report |

**Protocols to specify in Section 10.5:**
- Freeze and annotate `demo05` (P2.5), then score SC1/SC2.
- Latency: at least 100 warm requests, p50/p95/max (P2.8).
- Compaction before/after accuracy on human queries.
- Annotated multi-room clip for SC9.
- One-hour soak and 10 s disconnect (AC-01, AC-03).
- Usability with 5 participants (SC8), after ethics approval.
- Controlled-room metric experiment (P2.4).

---

### Chapter 11: Conclusion (REWRITE, 1–2 pages)

Three paragraphs:
1. What FYP-1 delivered: both iterations, in one paragraph.
2. What was learned: the key measured findings and the honest negative result (EgoLife class-level queries).
3. What FYP-2 must prove.

Remove the mid sentence "The diagrams in this report are synchronized with the implementation evidence" unless it is now true.

---

### Appendices

| App. | Title | Action | Content |
|---|---|---|---|
| A | Proposal and Mid-Evaluation Action Register | EXTEND | Keep the 4 proposal items, updated. Add every mid-evaluation item with evidence links |
| B | Supplementary Use-Case Specifications | UPDATE | Same `\uctable` format. Update the preconditions/notes for UC-02 (STT now on-device), UC-06 (crops endpoint), UC-10 (activities endpoint exists, summaries exist, auth missing), UC-11 (pause/resume implemented), UC-12 (compaction implemented). Add UC-14/15/16 if not placed in Ch 4. Update B.3 coverage |
| C | Detailed Test Cases and Results | REWRITE | Same table style (Module, N, Coverage, Result) for all test files on the submission commit. Generate N per file with `uv run pytest --collect-only -q`. Split into C.1 Core/geometry/perception, C.2 Ingestion/live, C.3 Memory/store/compaction, C.4 NLQ/API/serving, C.5 Evaluation harness, C.6 Flutter widget tests (Patient and Caregiver), C.7 Acceptance-test boundary |
| D | Repository and Contribution Evidence | UPDATE | D.1 layout (current `src/aegis/*`, `apps/*`, `evaluation/`, `scripts/`, `demo/`); D.2 reproduction commands (copy from `CONTEXT.md` §7, including `scripts/run_e2e.py`, `aegis-ingest`, `run_pipeline.py`, `modal deploy`, `aegis-ask`); D.3 attribution table; D.4 tags and branches |
| E | Additional Design Diagrams | FILL or DELETE | The mid version was a one-line empty appendix. Either put full-page versions of dense diagrams here (ERD, class diagrams, DFD level 1) or delete it. An empty appendix costs format marks |
| F | Meeting and Progress Evidence | EXTEND | Add every supervisor meeting after 20 Oct (Tuesdays 11:30), same format: date, attendees, discussion, follow-up. **Team must supply the notes** |
| G | **Evaluation Protocols and Raw Results** (NEW) | NEW | G.1 detection benchmark protocol and per-variant table; G.2 memory audit full table and projection table; G.3 EgoLife protocol, query bank summary, cost and per-day results; G.4 Option C (Ego4D) readiness checklist, 0/100 NO_GO; G.5 `demo05` held-out readiness (NOT_READY) and annotation templates |

---

## 6. Master diagram register

> **Superseded by `DIAGRAM_SPECS.md`.** This register was the first pass. The full code read changed some figure IDs and corrected two facts:
> - The patient query sequence calls **`/api/v1/query` first** and `/api/v1/ask` only as a fallback (`apps/Patient App/lib/services/api_service.dart`).
> - Home-store ingest runs **only after `--download`** (`run_pipeline.py`).
>
> Use the IDs in `DIAGRAM_SPECS.md` §1.

Legend:
- **Status vs mid:** KEEP = reuse the mid PNG; FIX = reuse but rename or fix the caption; REDRAW = same diagram type, new content to match `develop`; NEW = did not exist.
- **Owner:** a suggestion only; assign real owners in Section 10.

### 6.1 Chapter 1–3

| ID | File | Type | Must show | Source of truth | Status | Owner |
|---|---|---|---|---|---|---|
| F1.1 | `fig-1.1.png` | Conceptual loop | "No record" recall loop and where Aegis breaks it | — | KEEP | — |
| F1.2 | `ch1-system-context.png` | System context diagram (DFD level 0 style or UML) | Aegis as one box; external entities: primary user (phone camera via IP Webcam MJPEG, Patient App), caregiver (Caregiver App), Modal cloud (GPU/CPU, volume), Hugging Face (VGGT-Ω weights), Android OS services (STT, dialer). Labelled data flows: video frames, questions, answers with evidence, room names, enrolled items | `CONTEXT.md` §2 | REDRAW | Shahmeer |
| F1.3 | `ch1-modules.png` | Block diagram | M-A Capture/Ingestion, M-B Memory, M-C Query (NLQ), M-D Interfaces; their FRs; leads; shared store (`memory.db` plus scene graph) | §1.7 table | REDRAW | Shahmeer |
| F2.1 | `ch2-pipeline.png` | Pipeline diagram | Write path: capture → keyframes → VGGT-Ω + gravity → SAM3 + SAM2 masks → OBB lifting → scene graph v2 → home store → compaction. Read path: app/CLI → `/ask` → NLQ → answer/abstain | `CONTEXT.md` §2 | REDRAW | Faizan |
| F2.2 | `fig-2.2.png` | Positioning chart | Gap positioning (spatial grounding vs temporal memory) | Ch 2 table | KEEP | — |
| F2.3 | `ch2-detector-ab.png` | Grouped bar chart | P, R, F1 for 5 detector variants; annotate FP/img | `docs/detection_benchmark.md` | NEW | Faizan |
| F3.1 | `ch3-gantt-plan-vs-actual.png` | Gantt | Rows = work items; planned bar (outline) vs actual bar (filled); iteration bands I1 (to week 9) and I2 (to end); milestone diamonds for mid evaluation, tags and final | Ch 3 progress table and `git log` | REDRAW | Shahmeer |
| F3.2 | `iterationcycle.png` | Cycle diagram | Select → design → implement → test → review → re-plan | — | KEEP | — |

### 6.2 Chapter 4: Requirements

| ID | File | Type | Must show | Status |
|---|---|---|---|---|
| F4.1 | `ch4-use-case.png` | UML use case diagram | Actors: Primary User, Caregiver, System (timer, for compaction). UC-01…UC-13 plus any new UC-14/15/16. `«include»` for UC-03/UC-05 → UC-02 (submit query) and → UC-06 (view evidence). `«extend»` for abstention. Caregiver UCs inside a "requires grant (UC-07)" note. Planned UCs dashed. **UC-13 must be present** | REDRAW |

### 6.3 Chapter 5: Design (all must match `develop`)

| ID | File | Type | Must show | Source of truth | Status |
|---|---|---|---|---|---|
| F5.1 | `ch5-layered-architecture.png` | Layered architecture | (1) Capture: IP Webcam, `aegis-ingest`, batch video. (2) Processing on Modal: preprocess, VGGT-Ω + gravity, detection + SAM2 + lifting. (3) Memory: scene graph v2 builder, home store (SQLite), matching, activities, evidence, compaction. (4) Service: FastAPI `api.py` deployed by `serve.py`, NLQ engine. (5) Presentation: Patient App, Caregiver App, `aegis-ask` CLI, Rerun. Arrows only between adjacent layers; label the protocols (HTTPS/JSON, Modal volume, files) | `src/aegis/*`, `CONTEXT.md` | REDRAW |
| F5.2 | `ch5-components.png` | UML component diagram | One component per package (`core`, `ingestion`, `geometry`, `perception`, `memory`, `nlq`, `remote`, `evaluation`, `visualization`) plus the two apps. Provided/required interfaces as lollipop/socket: `AskAPI`, `MemoryRepository`, `HomeStore`, `ArtifactContract`, `Vocabulary`. Artifacts as `«artifact»` (`r4d_scene_graph.json`, `memory.db`, `home_map.json`, `gravity.json`) | code | REDRAW |
| F5.3 | `ch5-deployment.png` | UML deployment diagram | Nodes: Android phone #1 (IP Webcam app); laptop (Python 3.12/uv: `aegis-ingest`, `run_pipeline.py`, `run_e2e.py`); Modal cloud with execution environments: L4 GPU worker (VGGT, detect), CPU worker (preprocess, Rerun, CPU fallback), ASGI web endpoint (`serve.py`: FastAPI + NLQ), Volume `aegis-poc-data` mounted at `/data`, model cache `/models`; Android phones with Patient App APK and Caregiver App APK (HTTPS to the ASGI endpoint); GitHub (Actions CI, CD APK release). Dashed: future auth server and encrypted store | `modal_app.py`, `serve.py`, `.github/workflows` | REDRAW |
| F5.4 | `ch5-design-evolution.png` | Side-by-side architecture (optional) | Mid architecture on the left, final on the right; changed boxes highlighted | Ch 5.5 | NEW (optional) |
| F5.5 | `ch5-domain-model.png` | UML class diagram (conceptual, no methods) | Home 1–* Room, Room 1–* Anchor, Anchor 1–* ObjectInstance (via StateRun), ObjectInstance 1–* StateRun, StateRun → relation type enum (inside, on_surface, under, above, next_to, on_floor, near, in_room, carried_by_user), Event (pickup, placement, anchor_change, state_change, room_change, moved_while_unobserved), Session, RoomVisit, Activity, Evidence (crop), Summary, CompactionLog, PersonalItem. Dashed (planned): User, Caregiver, AccessGrant, AuditEntry | `memory/store.py`, `runs.py`, `relations.py` | REDRAW |
| F5.6 | `ch5-scene-graph-v2.png` | JSON document model (tree) | Top-level keys: `schema_version`, `session`, `gravity`, `anchors`, `rooms`, `state_runs`, `latest_states`, `events`, `room_visits`; expand one example of each; note "size does not grow with video length" | `docs/artifact_contracts.md` | REDRAW |
| F5.7 | `ch5-erd-home-store.png` | Crow's-foot ERD | All 12 tables: `meta`, `room`, `session`, `anchor`, `instance`, `state_run`, `activity`, `event`, `room_visit`, `evidence`, `summary`, `compaction_log`, with PKs, FKs, key columns and cardinalities. Mark which tables compaction writes and which rows are never compacted | `src/aegis/memory/store.py` (CREATE TABLE statements, lines 33–175) | NEW |
| F5.8 | `ch5-live-session-layout.png` | File/artifact diagram (optional) | `captures/<id>/frame_*.jpg`, `index.jsonl` (frame + gap records), `session.json`, `session_state.json` → promotion → `data/<id>/` | `ingestion/contracts.py` | NEW (optional) |
| F5.9 | `ch5-patient-app-flow.png` | Screen-flow / wireframe map | Onboarding dialog → Patient Home (object tiles, live badge, server badge, voice button) → Answer Drawer (resolution badge, time cue, candidate photo card) → Call View (call/SMS caregiver) | `apps/Patient App/lib/views/*` | REDRAW (replaces `chapter5-ui-wireframes`) |
| F5.10 | `ch5-caregiver-app-flow.png` | Screen-flow / wireframe map | Onboarding → Caregiver Home (search, voice rings) → tabs (tracking, interactions, interior, status, history) → Answer Drawer (ranker chip) → Enroll Dialog | `apps/Caregiver App/lib/views/*` | NEW |
| F5.11 | `ch5-dfd-level0.png` | DFD level 0 | Single process "Aegis"; entities: Primary User, Caregiver, Camera, Model Hub; flows labelled | — | NEW |
| F5.12 | `ch5-dfd-level1.png` | DFD level 1 | Processes: 1 Capture & Ingest, 2 Reconstruct & Perceive, 3 Build Memory, 4 Compact, 5 Answer Query, 6 Manage Rooms/Items. Data stores: D1 Modal volume (frames/artifacts), D2 Home store `memory.db`, D3 `home_map.json`, D4 Evidence crops | — | REDRAW (replaces `dfd.png`) |
| F5.13 | `ch5-seq-pipeline.png` | UML sequence | Laptop `run_pipeline.py` → Modal volume upload → preprocess (CPU) → VGGT-Ω (L4) → gravity → detect + SAM2 + lift (L4) → scene graph builder → (optional) home-store ingest → artifacts stay on the volume. Use `alt` for the CPU fallback (`AEGIS_GPU=cpu`) and the gated-checkpoint fallback | `run_pipeline.py`, `remote/workers.py` | REDRAW |
| F5.14 | `ch5-seq-ask.png` | UML sequence | Patient App (`alt` voice: STT on-device → text) → HTTPS `POST /api/v1/ask` → `api.py` → repository loads graph from `/data` → NLQ `engine`: dictionary match → intent → retrieval → `alt`: grounded answer with place/time/evidence, or abstain (unknown item / never observed / temporal intent) → JSON → Answer Drawer | `nlq/engine.py`, `api.py`, `api_service.dart` | REDRAW (replaces two mid figures) |
| F5.15 | `ch5-seq-caregiver.png` | UML sequence | Caregiver App: rename room (`POST /rooms/rename` → graph + `home_map.json`) and enroll item (`POST /enroll`). Show a dashed "auth check (planned)" lifeline step | `api.py` | REDRAW |
| F5.16 | `ch5-state-live-session.png` | UML state machine | States: Idle → Capturing ⇄ Paused; Capturing → Gap (stall/disconnect) → Capturing (resume); Capturing → Stopped → Promoted; Crashed → Resumed (crash-resume). Guards and actions (gap record written, keyframe criterion) | `ingestion/live_pipeline.py`, `contracts.py` | NEW |
| F5.17 | `ch5-state-object.png` | UML state machine | Object instance: Unseen → Observed(on anchor/room) → Carried (`carried_by_user`) → Placed → Occluded/Unobserved (object permanence) → `moved_while_unobserved`. Label each transition with the Event type it emits | `memory/runs.py`, `scene_graph.py` | NEW |
| F5.18 | `ch5-activity-compaction.png` | UML activity diagram | For each local day older than 3 days: skip if already logged → build object/activity day summaries → verify against source (VerificationError branch keeps detail) → write summary → delete detail except protected/latest runs → log → weekly/monthly roll-up | `memory/compaction.py`, `summaries.py` | NEW |
| F5.19 | `ch5-flow-nlq.png` | Activity diagram / flowchart | Normalise text → closed-vocabulary match (aliases authoritative, word boundary) → no match → abstain "I don't know that item" → intent (LOCATE / TEMPORAL / ACTIVITY) → TEMPORAL/ACTIVITY → abstain (by design) → LOCATE → retrieve latest state → none → abstain "not seen" → answer (place, room, time, evidence) | `nlq/engine.py`, `dictionary.py` | NEW |

### 6.4 Chapter 6–7: Iterations

| ID | File | Type | Must show | Status |
|---|---|---|---|---|
| F6.1 | `ch6-class-core-models.png` | UML class (real code) | Iteration 1 core models; caption "as at `v0.2.0-mid2`" | FIX (rename from `classdiagram(a)`) |
| F6.2 | `ch6-class-live-api.png` | UML class (real code) | Iteration 1 live capture and API | FIX (rename from `classdiagram(b)`) |
| F6.3 | `batchvideosamplingflowchart.png` | Flowchart | Batch sampling and keyframe selection | KEEP |
| F6.4 | `chapter6-screenshot-evidence.jpeg` | Screenshot | Iteration 1 prototype | KEEP |
| F7.1 | `ch7-class-memory.png` | UML class (real code, key attributes and methods only) | `HomeStore`, `StateRun`, relation classifier, `SceneGraphBuilder`, matching functions, `CompactionReport`, `SummaryDraft`, activities, evidence | NEW |
| F7.2 | `ch7-class-nlq-api.png` | UML class (real code) | NLQ `Dictionary`, engine, answer model, `AskResponse`; FastAPI request/response models; Flutter `ApiService`, `VoiceService`, answer/candidate models | NEW |
| F7.3 | `ch7-flow-relations.png` | Flowchart | Relation classification from the OBB and support surface in the gravity frame (inside → on_surface → under → above → next_to → on_floor → near) with thresholds | NEW |
| F7.4 | `ch7-flow-matching.png` | Flowchart | Session → home store matching: room (landmarks, then proximity) → anchor → instance (label + appearance re-ID) → new or matched IDs | NEW |
| F7.5 | `ch7-shot-patient-app.png` | Real screenshots (2–3 panels) | Home with tiles, answer drawer with evidence crop, abstention answer | NEW |
| F7.6 | `ch7-shot-caregiver-app.png` | Real screenshots | Search plus one tab, enroll dialog | NEW |
| F7.7 | `ch7-shot-rerun.png` | Real screenshot | Rerun: video left, 3D memory right (rooms, anchors, OBBs) | NEW |
| F7.8 | `ch7-shot-aegis-ask.png` | Terminal screenshot | `aegis-ask "where are my keys"` over HTTPS: one grounded answer and one abstention | NEW |

### 6.5 Chapter 8–10: Testing, evidence, plan

| ID | File | Type | Must show | Data source | Status |
|---|---|---|---|---|---|
| F8.1 | `ch8-test-levels.png` | Test pyramid | Tiers with real counts: unit, API integration, pipeline/live integration, evaluation/measurement, Flutter widget tests | `pytest --collect-only`, `flutter test` | REDRAW |
| F8.2 | `ch8-detection-chart.png` | Grouped bar | Same as F2.3; use one figure and cross-reference if shown in Ch 2 | `docs/detection_benchmark.md` | NEW |
| F8.3 | `ch8-compaction-ratio.png` | Bar chart | Compaction ratio by snapshot interval (0, 1, 10, 30) for demo03 and demo04; secondary marker for centre p95 | `evaluation/reports/memory_control/summary.md` | NEW |
| F8.4 | `ch8-storage-projection.png` | Line chart | Original vs compacted MiB at 1 h, 8 h, 24 h for both demos. Title or caption must say **"linear projection, not measured"** | same | NEW |
| F8.5 | `ch8-e2e-timing.png` | Horizontal bar (optional) | VGGT 831 s, detect+lift 27 s, deploy 8 s (CPU, single run) | `TODO.md` P0.8 | NEW (optional) |
| F8.6 | `ch8-egolife.png` | Line or bar chart | Accuracy by day: full history vs 24 h ablation; plus the 12/12 instance-survival diagnostic | `outputs/evaluation/egolife_scored/FINAL_SUMMARY.md` (get from Faizan) | NEW |
| F9.1 | `ch9-commit-timeline.png` | Timeline / swimlane | Commits per member per week, 4 Oct → submission; iteration bands; tags `v0.1.0-mid1`, `v0.2.0-mid2`, final tag | `git log` | REDRAW |
| F9.2 | `ch9-branch-graph.png` | Git graph | `main`, `develop`, feature branches (`feat/evaluation-suite`, `feat/memory-plan`, `feat/NLQ`, `feat/demo`, `design/patient-app-styles`), merges, tags | `git log --graph` | NEW |
| F10.1 | `ch10-fyp2-gantt.png` | Gantt | Iterations 3 and 4; work items from Ch 10.3 with owners; evaluation and usability study; thesis writing; FYP-2 mid and final | Ch 10 | NEW |

**Charts** (F2.3, F8.2–F8.6): make them with matplotlib (or similar) from the source numbers, export PNG at 300 dpi, label both axes with units, and put the data source in the caption. Keep the chart script under `ThesisFigs/src/` so the numbers can be reproduced.

**Count:** about 45 figures (mid: 27). About 20 are new, about 14 redrawn, and the rest kept or fixed.

---

## 7. Master table register (new and changed tables only)

| Ch | Table | Change |
|---|---|---|
| 1 | 1.1 Objectives | + "Status at FYP-1 end" column |
| 1 | 1.2 Scope split | Move completed items into FYP-1 |
| 1 | 1.3 Modules | M-C = NLQ; M-D = two apps |
| 1 | 1.5 Success criteria | + "FYP-1 evidence" column |
| 2 | 2.1 Comparison | Re-check the Aegis column |
| 2 | 2.2 CCP | + evidence column |
| 2 | 2.3 Technical challenges | + "What we found"; + TC12 |
| 2 | 2.4 Findings → decisions | + 6 new decision rows |
| 2 | NEW Detector A/B | 5 variants × P/R/F1/FP |
| 3 | 3.1 Proposal actions | + Evidence column |
| 3 | NEW Mid-evaluation action register | All mid feedback items |
| 3 | 3.2 Iteration map | Status column |
| 3 | 3.4, 3.5 Iteration plans | + Outcome row |
| 3 | 3.3, 3.6, 3.7 Responsibilities | Actual Iteration 2 leads |
| 3 | 3.8 Progress | Rewrite with planned dates |
| 3 | NEW Deviations | Reason, impact, recovery, owner, date |
| 4 | 4.1 UC inventory | + Status; + new UCs |
| 4 | 4.8–4.15 FR/NFR | + Status; + new sub-FRs |
| 4 | 4.16 Acceptance criteria | + Result, + Evidence |
| 4 | 4.17 Traceability | + Test file, + Status |
| 4 | NEW Requirements change log | — |
| 5 | NEW Component responsibilities | Package, provides, requires |
| 5 | NEW API contract | All routes |
| 5 | NEW Artifact contracts | All files |
| 5 | NEW ADR table | Decisions with alternatives |
| 5 | NEW Design evolution | Mid → final |
| 7 | NEW Iteration 2 plan vs delivered | — |
| 7 | NEW Completed features | Feature, owner, commit, test |
| 7 | NEW Key parameters | Thresholds and settings |
| 8 | NEW Detection, compaction, e2e, EgoLife result tables | — |
| 8 | NEW Defects and corrective actions | — |
| 9 | 8.1 → 9.x Contribution evidence | Rewrite |
| 9 | 8.3 → 9.x Dependencies | + new models/datasets/licences |
| 9 | 8.4 → 9.x Risk register | + Likelihood × Impact scores |
| 10 | NEW Remaining features | Owner and iteration |
| App. C | Test tables | All test files, real N |

---

## 8. Facts sheet (verified numbers; take numbers only from here or re-measure)

### 8.1 Code and tests

| Fact | Value | How verified |
|---|---|---|
| Test suite on `develop` `ce49dcc` | **451 passed**, 7.7 s | `uv run pytest -q`, 25 Nov 2026 |
| CI gate | ruff check + format; pytest with `--cov=aegis --cov-fail-under=75`; Flutter analyze/test | `.github/workflows/ci.yml` |
| CD | Patient app release APK published | `.github/workflows/cd.yml`, commit `ef0db05` |
| Tags | `v0.1.0-mid1` (4 Oct 2026, `4419832`); `v0.2.0-mid2` (13 Oct 2026, `678acbd`) | `git tag` |
| SQLite tables | 12: meta, room, session, anchor, instance, state_run, activity, event, room_visit, evidence, summary, compaction_log | `memory/store.py` |
| NLQ vocabulary | 525-item closed vocabulary (CONTEXT.md); an earlier curated list had 511 items. Re-count on the submission commit | `CONTEXT.md` §5 |
| Mid-report ACs | AC-01 … AC-31 | `chapter4_requirements.tex` |

### 8.2 Measured results

| Result | Value | Source | Caveat |
|---|---|---|---|
| Detector (shipped SAM3, class thresholds, NMS 0.7) | P 0.718, R 0.724, F1 0.721, 3.3 FP/img; hands 19/19 | `docs/detection_benchmark.md` | 10 frames, hand-labelled, five environments |
| Old default YOLOE-11l | F1 0.097; 0/36 shoes, 0/19 hands | same | — |
| Compaction (snapshot interval 0) | demo04 7.2× (178.3 → 24.8 KiB); demo03 5.7× (528.5 → 92.0 KiB); 100% semantic retention, 100% latest-state exact, 100% query agreement | `evaluation/reports/memory_control/summary.md` | Auto-generated probes; scene units |
| Projected growth (demo04) | 13.51 → 2.11 MiB/h; 24 h: 324.2 → 50.7 MiB | same | **Linear projection** |
| End-to-end run, 20 Nov 2026 | CPU; `walk01-2`, 79 frames; VGGT 831 s; detect+lift 27 s; deploy 8 s; HTTPS answer with no local artifacts | `TODO.md` P0.8 | Single run |
| EgoLife multi-day study, 22 Nov 2026 | 74 segments; $8.71 metered; class-level queries: full history never beat the 24 h ablation; oracle diagnostic: 12/12 instances still in store 1–4 days later | `docs/egolife.md` (+ FINAL_SUMMARY on Faizan's machine) | Six-volunteer shared house, not a care home |
| L4 cost per 5-min segment | VGGT 200 s + detect 108 s = 0.086 GPU-h ≈ $0.069 | `docs/egolife.md` | — |
| Ego4D readiness | NO_GO, 0/100, about 10.8 weeks remaining | `evaluation/reports/option_c/summary.md` | — |
| `demo05` held-out | NOT_READY (no annotations) | `evaluation/reports/demo05/summary.md` | — |

### 8.3 Git evidence on `develop` `ce49dcc`

| Identity | Member | All-time commits | Since 22 Oct (no merges) |
|---|---|---|---|
| `Ali Sher` | Ali Sher | 223 | 203 (122 on 23 Nov, one file per commit) |
| `pez-Ox` (+2 as "Faizan Ur Rehman Khan") | Faizan | 69 (+2) | 14 |
| `shah-paradox` | Shahmeer | 44 | 32 |

Re-run `git shortlog -sn --no-merges` on the submission commit and replace these figures.

### 8.4 API routes on `develop` (`src/aegis/remote/api.py`)

| Group | Routes |
|---|---|
| Read | `GET /health`, `/scene_graph`, `/datasets`, `/anchors`, `/rooms`, `/query`, `/timeline`, `/activities`, `/crops/{instance_id}`, `/video/{dataset_id}`, `/capture/status`, `GET /ask` |
| Write | `POST /dataset/select`, `/rooms/rename`, `/enroll`, `/ask`, `/capture/pause`, `/capture/resume` |
| Simulator (gated by `require_simulator`) | `POST /simulate_transition`, `POST /reset`, `GET /simulate/floor\|cabinet\|in_hand\|bottle_table1\|bottle_occluded\|bottle_table2` |

All routes are under `/api/v1`. CORS is `allow_origins=["*"]`, and there is no auth dependency on any route except the simulator gate.

---

## 9. Section-writing template (use for every new section)

Each new or rewritten technical section should follow this shape so it reads as project-specific, not generic:

1. **What:** one sentence on what the component or result is.
2. **Why:** the requirement (FR/NFR/SC ID) or panel action it serves.
3. **How:** the design or algorithm, pointing to the figure and the file path.
4. **Evidence:** test file, commit hash or report file.
5. **Limits:** what it does not show, and which TODO or iteration covers that.

---

## 10. Inputs the team must provide (blocking)

| # | Item | Needed for | Who |
|---|---|---|---|
| 1 | Mid-evaluation feedback (supervisor comments, Form 2/3 remarks, required actions) | Ch 3.3, 3.4, App. A | All |
| 2 | Meeting notes for every supervisor meeting after 20 Oct | App. F | Shahmeer |
| 3 | Dean, Director, HoD and FYP-coordinator names; submission month | `main.tex` | Any |
| 4 | EgoLife `FINAL_SUMMARY.md` and per-day numbers | Ch 8.8, F8.6, App. G | Faizan |
| 5 | Decision on new UCs/FRs (UC-14/15/16, new FR sub-items) | Ch 4 | All, with supervisor |
| 6 | Iteration 1 exit-criterion run (10 placements), if it can be done before submission | Ch 6.9 | Shahmeer / Faizan |
| 7 | Real app screenshots on a device (both apps) and a Rerun screenshot | F7.5–F7.7 | Ali (apps), Faizan (Rerun) |
| 8 | Full GenAI and tool disclosure, per member | Ch 9.7 | Each member |
| 9 | Diagram owners, assigned from Section 6 | All figures | All |
| 10 | FYP-2 dates and week numbers | Ch 10, F10.1 | All |

---

## 11. Pre-submission checklist

- [ ] Compiles with no `Missing figure` boxes, no `??` references, and no overfull tables running off the page.
- [ ] Every number appears in Section 8 or was re-measured on the submission commit (test count, commit counts, vocabulary size).
- [ ] No "84 tests", "apps/mobile", "evaluation_plan.md", "compaction not implemented" or "no relational database" left anywhere (`grep -ri` the chapters).
- [ ] Every Chapter 5 diagram matches `develop`; no caption says "not depicted" or "earlier".
- [ ] Every figure is referenced and explained in the text.
- [ ] Solid/dashed convention stated and followed.
- [ ] Every FR and AC has a Status; every Implemented item has a test file.
- [ ] Proposal and mid-evaluation action registers have an evidence link per row.
- [ ] Deviations table has an owner and new date per row.
- [ ] Measured vs unmeasured clearly separated in Ch 8.12; projections labelled.
- [ ] No clinical, usability, Ego4D or metric-accuracy claim.
- [ ] Tool disclosure complete for all three members (otherwise the tool item scores 0).
- [ ] Risk register scored (likelihood × impact).
- [ ] Contribution section states that commit counts are not effort, and lists features owned.
- [ ] Appendix E either filled or removed.
- [ ] Signatures on Students' Submission, Anti-Plagiarism and Authors' Declaration.
- [ ] Submission commit tagged, and the tag cited in Ch 9 and App. D.
- [ ] Each member can explain, without reading, any paragraph of Chapter 2 and the chapters on the modules they own (red-flag gates for GenAI text and uneven contribution).
