# Pipeline change report — detection, evaluation, and client impact

This report describes what changed in the pipeline, what is already shipped, and
what the UI/UX and surrounding surfaces must change to consume it. It is split
into: (1) detection stage, (2) memory/query stage including the four-tier
evaluation plan, and (3) required client and operational changes.

## 1. What changed in the pipeline

### 1.1 Detection: YOLOE → SAM3

`config/demo.yaml` now selects `detector_backend: sam3` with `facebook/sam3`.
The other backends (`yoloe`, `yolo_world`) remain available via config.

- `src/aegis/perception/detector.py` adds `Sam3Adapter` plus small
  `_Sam3Boxes` / `_Sam3Masks` / `_Sam3Result` shims. SAM3 text prompts are
  batched once per frame; results are adapted to the existing Ultralytics-style
  `predict` interface so mask rescue, re-ID, tracking, and hand-contact logic
  are unchanged.
- `src/aegis/core/config.py` adds `sam3_model`, `sam3_default_threshold`,
  `sam3_class_thresholds`, validates them, and accepts `sam3` as a backend.
- `src/aegis/remote/modal_app.py` upgrades the perception image to
  `transformers>=5,<6`, `huggingface_hub>=1.3,<2`, `pillow`, and `accelerate`.

**Why:** on a hand-labeled benchmark across five videos, YOLOE found 0/36 shoes
and 0/19 hands; YOLO-World found 11/36 shoes and 0/19 hands; SAM3 found both
object instances and the hands that drive interaction salience.

**Generic settings only** (no per-video or per-class-by-dataset tuning):
18-class compact prompt set, category-level thresholds
(`shoes 0.5`, `hand 0.4`, `cooking pot 0.6`, `trash bin 0.4`,
`food container 0.9`, everything else `0.8`), per-class NMS at IoU `0.7`.

### 1.2 Reliability fix: volume upload failures are now loud

`src/aegis/ingestion/download.py`: `upload_to_modal_volume` previously printed a
warning and returned `False` on failure; callers ignored the return value. A
large video upload that timed out silently produced a confusing downstream
`FileNotFoundError` inside remote preprocess. It now raises `RuntimeError` with
the underlying stderr, and `tests/test_live_cli.py` covers the failure path.
Recovery for the oversized demo05 input was a local re-encode (212 MB → 67 MB,
same 1080p content), uploaded once, then the pipeline rerun with `--no-upload`.

### 1.3 Visualization fix: schema-v2 graphs render object overlays

`src/aegis/visualization/rerun_scene.py` adds `_v2_timeline`, which converts
v2 `state_runs` + `latest_states` into the per-frame timeline the viewer
consumes. Without it, v2 recordings showed rooms/anchors but no object boxes or
2D overlays. Covered by `tests/test_rerun_visualization.py`.

### 1.4 Benchmark and evidence

New artifacts: `evaluation/annotations/detection_bench.json` (10 hand-labeled
frames, 116 objects, five videos), `scripts/detector_bench.py` (A/B harness),
`docs/detection_benchmark.md` (measured results and rejected alternatives).
Measured shipped-config result: F1 0.721, P 0.718, R 0.724, shoes 34/42,
hands 19/19, 3.3 FP/image. Every generic alternative tested — prompt-word
variants, NMS sweep, cross-class suppression, horizontal-flip TTA — was
measured per-video and rejected when it regressed any video or gained <0.005.

## 2. Evaluation suite: four-tier query protocol (Gemini-assisted plan)

The memory query protocol is already four-tiered
(`docs/evaluation_suite.md` §15, commit `b0a834d`):

| Tier | Question form | Ground truth | Status |
|---|---|---|---|
| T1 | "Where are my glasses?" (enrolled personal item) | enrolled instance id | NOT RUN — no enrollment GT |
| T2 | "Where is the mug?" (class-level, ambiguous) | frozen `expect_place` | primary result |
| T3 | "Where is the mug I used two days ago?" | place + coarse-time window | mechanically derived cue only |
| T4 | "Where was the mug at 2026-01-07T12:02:07Z?" | place + exact timestamp | oracle upper bound |

Shipped mechanics relevant to clients:

- `HomeStore.states_as_of(asked_at)` snapshot semantics; T4 uses `state_at`.
- `MemoryQueryResponse` exposes `resolution_mode`, `is_ambiguous`,
  `ambiguity_reason`, and up to three place-deduplicated `candidates` with
  `crop_url` and a score breakdown. Ambiguity is shown as real photos, not a
  single guessed answer.
- Ranker modes: `recency_only` (legacy), `salience` (interaction + displacement),
  `full` (personal registry + fuzzy-cue boost). Enrollment via
  `aegis-memory enroll --alias ... --usual-anchor ... --visual-crop ...`.
- T1 has a scoring path and unit tests but no enrolled GT in the frozen bank;
  it is reported NOT RUN, never a zero. Visual-trait and activity cues likewise
  remain NOT IMPLEMENTED / NOT RUN.

**Gemini-assisted plan (proposed, not implemented).** There is no Gemini code in
the repository today; the deterministic scorer remains the source of truth.
A Gemini layer should be additive and offline, used only to:

1. Generate and paraphrase T2/T3 query variants from the frozen bank for
   robustness testing — never edit the frozen bank; write to a sidecar keyed
   by query id, as `egolife_tiers.json` already does.
2. Produce independent `ambiguity_expected` labels from caption transcripts,
   then keep the existing human-verified sidecar as the adjudication source.
3. Judge free-text answer quality for reporting only, with the deterministic
   Top-1 / Recall@3 / MRR / Ambiguity-F1 / False-Confidence Rate still primary.

Any Gemini output must be versioned with a prompt hash and kept out of the
scoring path, so a model change cannot silently move published metrics.

## 3. What must change accordingly

### 3.1 API

`/api/v1/query` already returns the ambiguity fields, but no endpoint exposes
tier metadata or ranker mode to clients. Add:

- `tier`, `resolution_mode`, `is_ambiguous`, `ambiguity_reason`, and
  `candidates` to the client contract (the server already computes them).
- Optional `ranker_mode` and `as_of` query parameters so the client can
  exercise T3/T4 and compare ranker modes.
- An enrollment endpoint (alias, class, usual anchor/room, reference crop) so
  caregivers can create the T1 ground truth the suite currently lacks.
- A `GET /api/v1/evaluation/tiers` summary that reports NOT RUN tiers honestly
  instead of zeros — this is what the report/UI should read.

### 3.2 Mobile UI/UX (Flutter)

> **Implemented (patient app):** the patient client now lives in
> `apps/Patient App/` (built from `patient.html`). It models ambiguity and
> candidates in `lib/models/memory_answer.dart`, consumes `/api/v1/query`
> first and `/api/v1/ask` as a fallback, and shows candidates as Apple-HIG
> inset cards with a labelled `resolution_mode` badge. The caregiver app is
> planned in `apps/Caregiver App/`. The older file paths below describe the
> original pre-rewrite client and are kept for context.

`apps/mobile/lib/models/query_result.dart` currently models a single answer:
`found`, `instanceLabel`, `anchorLabel`, `roomLabel`, one `cropUrl`, one
`confidence`. It has no notion of ambiguity, candidates, tier, or temporal cue.
Required changes:

- **Patient view** (`views/patient/patient_view.dart`): when `is_ambiguous` is
  true, replace the single-location card with an Apple-HIG inset grouped card
  of up to three candidates, each with its crop, place label, and score; keep
  the "I'm not sure — which one?" framing rather than a false direct answer.
- **Query input**: add tier-aware phrasing hints ("Where is my mug?" vs "Where
  was it at 3 PM?") and a time-cue picker that maps to `as_of` / T3 / T4.
- **Confidence display**: show `resolution_mode` (direct / ranked / ambiguous)
  as a labelled badge, not a naked probability; keep 44×44 pt touch targets
  and the existing Cupertino sheet/alert patterns.
- **Caregiver view** (`views/caregiver/caregiver_view.dart`): add enrollment
  UI (alias, class, usual anchor/room, reference crop) and a room-rename flow
  that reuses the existing `POST /api/v1/rooms/rename`.
- **Models/services**: extend `QueryResult` and
  `services/api_service.dart` with the new fields; add a `Candidate` model and
  an `Enrollment` request model. Keep old fields optional so older servers work.
- **Search history**: `models/patient_search_record.dart` should retain tier
  and ambiguity outcome so "show me the ambiguous ones" is possible.

### 3.3 Operations and docs

- `docs/evaluation_suite.md` stays the authority for tier definitions and
  scoring rules; link the detection benchmark report from it.
- Acquisition: T1 needs a controlled recording with an enrolled object, and
  visual-trait/activity cues need ground truth before they are ever scored.
- The four end-to-end SAM3 runs plus demo05 establish that one generic config
  works across shoe cabinets, kitchens, waste areas, laundry, and dish racks;
  keep task-scoped configs as optional narrowings, never as the default.
