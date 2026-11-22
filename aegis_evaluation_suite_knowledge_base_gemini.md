# Aegis Evaluation Suite & Query Disambiguation Knowledge Base

> **Purpose:** Engineering and evaluation knowledge base for coding agents extending Aegis's evaluation suite (`src/aegis/evaluation/`, `evaluation/`, `scripts/`) and query reasoning pipeline (`src/aegis/memory/reasoning.py`, `home_registry.py`, `evidence.py`, `activities.py`).
>
> **Core Problem Addressed:** Bridging the gap between **under-specified, real-world dementia patient queries** (e.g., `"Where is the mug?"`) and **over-specified episodic database queries** (e.g., `"Where is the mug I put on the table on DAY3 at 12:02?"`).

---

## 1. The Design Problem: Why Pure Recency Fails (and Why Exact Timestamps Are Unrealistic)

In a multi-day home deployment (and in multi-day benchmarks like EgoLife), two failure modes collide:

1. **The Under-Specification Trap (Class-Level Queries):**
   - A patient asks: `"Where is the mug?"`
   - Across multiple days or rooms, the 4D scene graph contains multiple distinct mug instances (or multiple historical placements of mugs).
   - Because no instance uniqueness or temporal constraint was supplied, any single-answer resolver defaults to **most recently observed**.
   - **Why this fails in practice:** A wearable camera passively glances at background clutter (e.g., a mug in the sink or on a shelf) far more recently than the mug the user actively drank from and misplaced 30 minutes ago.
   - **Why this breaks evaluation:** If an evaluation test case asks `"Where is the mug?"` and grades Top-1 exact match against *one* arbitrary historical mug, the ground truth is **ill-posed**—the pipeline is penalized for an ambiguity inherent in the prompt.

2. **The Over-Specification Trap (Exact Episodic Queries):**
   - A query like `"Where is the mug I put on the table on DAY3 at 12:02?"` has a clean, unique ground-truth answer, so the 4D retrieval pipeline scores well.
   - **Why this fails clinically:** A user with dementia or mild cognitive impairment cannot be expected to recall exact day indices, clock timestamps, or precise prior anchors—if they remembered those, they would not need a memory prosthesis.

**Architectural Principle:**
> Do **not** force the patient to supply database keys. Shift disambiguation from the patient's recall onto **(a) identity priors**, **(b) interaction/displacement salience**, **(c) fuzzy human-anchored cues**, and **(d) visual candidate confirmation (Recognition over Recall)**. Grade each query type in the evaluation suite with metrics that match its information content.

---

## 2. How Prior Egocentric & Assistive Memory Systems Frame Queries

Agents modifying `src/aegis/evaluation/` should align Aegis's taxonomy with established benchmarks while explicitly correcting for dementia-usability gaps:

| Benchmark / System | Query Formulation | Disambiguation Strategy | Evaluation Metrics | Lesson for Aegis |
| :--- | :--- | :--- | :--- | :--- |
| **Ego4D NLQ** (Natural Language Queries, arXiv:2110.07058) | Free-text questions over 5–20 min clips (e.g., *"Where did I put the scissors?"*) | Relies on short clip horizon + occasional visual modifiers (*"red bowl"*). | Recall@k across temporal IoU thresholds. | Short clips mask multi-day object duplication; **Recall@k** is the standard retrieval metric when multiple moments compete. |
| **Ego4D VQ2D / VQ3D** (Visual Queries, arXiv:2110.07058) | A cropped reference image of the exact object + *"Where is this?"* | Eliminates class ambiguity completely via visual Re-ID; returns the latest 2D/3D location. | Spatio-temporal IoU, 3D localization error (L2 / success rate). | **Visual identity beats class names.** Enrolling a visual crop of a personal object turns an ambiguous class query into a unique instance lookup. |
| **EgoLife / EgoLifeQA** (CVPR 2025, arXiv:2503.03803) | Multi-day life-oriented QA across 5 categories: **EntityLog**, **EventRecall**, **HabitInsight**, **RelationMap**, **TaskMaster**. | Anchors queries to daily routines, habits, and personal entities rather than raw wall-clock seconds. | Category-wise and overall MCQ accuracy. | Aegis already has `egolife.py` and `activities.py`—leverage routine/activity context (*"after lunch"*, *"this morning"*) instead of exact `HH:MM`. |
| **ReMEmbR / NaVQA** (ICRA 2025, arXiv:2409.13682) | Long-horizon spatial, temporal, and descriptive queries over continuous robot memory. | Iterative LLM retrieval over text, position, and time vectors; notes that visually/semantically similar classes still get confused without disambiguation. | Spatial/temporal/descriptive QA accuracy across short/medium/long horizons. | Separate retrieval into **spatial**, **temporal**, and **semantic** dimensions and evaluate performance as memory horizon grows. |
| **PReMind** (arXiv:2611.23808) & Interactive Egocentric Retrieval | Object crops / personal memory queries matched via image embeddings (e.g., SigLIP 2) against candidate memory stores. | Retrieves **Top-K visual candidates** and uses physical interaction cues to rank relevance. | Top-K retrieval accuracy / candidate recall. | Combine **visual crops** (`evidence.py`) with **interaction/placement cues** (`evaluate_hand_contact.py`, `evaluate_placements.py`) to surface Top-K options. |
| **Clinical Dementia Assistive Design** | Minimal utterance (*"My mug?"*, *"Glasses?"*) | **Recognition over Recall:** Patients recognize a photo of their own item far more reliably than they can verbally describe its attributes or time of use. | Task completion with $\le 1$ visual disambiguation tap; low false-confidence rate. | When ambiguity is genuinely unresolved, showing **2–3 cropped photos** is safer and more accurate than silently guessing one wrong room. |

---

## 3. Mandatory Discovery Pass (Read Before Editing)

Before modifying any code, inspect the current branch implementation to bind this knowledge base to exact dataclasses, CLI flags, and file schemas:

1. **Evaluation Contracts & Runner:**
   - `docs/evaluation_suite.md` and `docs/evaluation_plan.md` — existing tier definitions, targets, and terminology.
   - `src/aegis/evaluation/schema.py` — current annotation and result dataclasses.
   - `src/aegis/evaluation/query.py` — how queries are executed against `reasoning.py` and graded today.
   - `src/aegis/evaluation/metrics.py` — current accuracy/recall/latency calculations.
   - `src/aegis/evaluation/egolife.py` & `scripts/egolife_eval.py` — how `evaluation/annotations/egolife_queries.json` is parsed and scored.
   - `src/aegis/evaluation/report.py` & `src/aegis/evaluation/run.py` — how `summary.json` / `summary.md` reports are generated.
   - `evaluation/templates/queries.jsonl` & `evaluation/templates/annotation_guide.md` — current query annotation schema.

2. **Memory & Reasoning Pipeline:**
   - `src/aegis/memory/reasoning.py` — current query parsing, candidate lookup, and single-answer selection logic.
   - `src/aegis/memory/home_registry.py` & `src/aegis/memory/homes.py` — how homes and registered/persistent items are stored.
   - `src/aegis/memory/scene_graph.py`, `matching.py`, `association.py` — how object instances, re-identification, and placement transitions are represented.
   - `src/aegis/memory/evidence.py` — how cropped images / keyframes are linked to object observations.
   - `src/aegis/memory/activities.py` & `src/aegis/memory/rooms.py` — how daily activities and rooms are indexed.
   - `scripts/evaluate_hand_contact.py` & `scripts/evaluate_placements.py` — existing signals for active interaction vs. passive background sighting.
   - `src/aegis/core/timeutil.py` & `src/aegis/core/vocabulary.py` (`config/vocabulary.yaml`) — time parsing and class/synonym mapping.

3. **Existing Tests (Must Stay Green):**
   - `tests/test_evaluation*.py`, `tests/test_egolife.py`, `tests/test_reasoning.py`, `tests/test_home_registry.py`, `tests/test_activities.py`, `tests/test_evidence.py`.

---

## 4. The 4-Layer Architectural Middle-Ground (Pipeline Side)

To resolve general class queries without demanding unrealistic timestamps, implement or expose these four layers cleanly in `src/aegis/memory/`:

### Layer 1: Personal "VIP" Object Registry (`home_registry.py`)
- **Concept:** Caretakers enroll a small set of high-value personal items (e.g., *patient's reading glasses*, *house keys*, *pill organizer*, *favorite blue mug*) with:
  - `personal_id` / `alias` (e.g., `"my mug"`, `"mug"`, `"dad's cup"`)
  - `canonical_class` (aligned with `config/vocabulary.yaml`)
  - Reference visual embedding / crop (`evidence.py`) and optional `usual_anchor` / `usual_room`.
- **Resolution Rule:** When a patient asks `"Where is the mug?"` or `"Where is my mug?"`, `reasoning.py` checks enrolled personal items matching that class/alias **before** falling back to generic class search. If a unique enrolled instance exists and has been tracked via `matching.py`, return its latest grounded state directly.

### Layer 2: Salience-Weighted Ranking Over Pure Recency (`scene_graph.py` + `reasoning.py`)
- **Concept:** Passive glances at stationary background objects must not outrank an object the user actually touched, moved, or placed out of its usual spot.
- **Signals to Combine** (leverage existing placement, hand-contact, and anchor transitions):
  1. **Personal Registry Match ($S_{\text{vip}}$):** Highest prior if the candidate matches an enrolled personal object.
  2. **Interaction / Placement Signal ($S_{\text{act}}$):** Was this instance involved in a hand-contact event or a confirmed placement / anchor-change transition?
  3. **Displacement / Out-of-Place Signal ($S_{\text{disp}}$):** Did the object move to a non-default room or anchor compared to its historical baseline (e.g., mug in living room vs. kitchen dish rack)?
  4. **Recency Decay ($S_{\text{rec}}$):** Smooth exponential or log-time decay used as a **tie-breaker and freshness factor**, not the sole ranker.
- **Suggested Interpretable Scoring Formula (tunable via config, no black-box magic):**
  $$\text{Score}(o) = w_{\text{vip}} S_{\text{vip}}(o) + w_{\text{act}} S_{\text{act}}(o) + w_{\text{disp}} S_{\text{disp}}(o) + w_{\text{rec}} S_{\text{rec}}(o)$$
  with default hierarchy $w_{\text{vip}} > w_{\text{act}} > w_{\text{disp}} > w_{\text{rec}}$. Log individual score components in evaluation outputs for explainability and ablation studies.

### Layer 3: Structured Ambiguity & Top-$K$ Visual Candidates (`reasoning.py` + `evidence.py`)
- **Concept:** When multiple unregistered instances of the same class remain plausible (e.g., two mugs were both moved today and their scores are within a configurable margin $\Delta$), **do not silently commit to one guess**.
- **Response Contract Upgrade (backward-compatible):**
  Keep the top-1 primary answer fields intact for legacy callers, and add structured disambiguation fields:
  - `resolution_mode`: `"direct"` | `"disambiguate"` | `"not_found"`
  - `is_ambiguous`: `bool`
  - `ambiguity_reason`: e.g., `"multiple_active_instances_same_class"` | `None`
  - `candidates`: list of up to $K=3$ distinct object instances, each containing:
    - `object_id` / `track_id`
    - `class_label` and optional `visual_tag` (e.g., `"blue mug"`, `"white cup"`)
    - `room`, `anchor`, `last_seen_ts`, `last_moved_ts`
    - `evidence_crop_path` / `evidence_ref` (from `evidence.py`)
    - `rank_score` and `score_breakdown`
- **How Patient UI Uses This:** If `resolution_mode == "disambiguate"`, the patient UI shows 2–3 large photo cards (*"Which mug are you looking for?"*) so the patient resolves ambiguity in one tap via visual recognition.

### Layer 4: Fuzzy Human-Cue Parsing (`reasoning.py` + `activities.py` + `rooms.py` + `timeutil.py`)
- **Concept:** Support the natural, imprecise cues real people actually remember—without requiring `DAY3 at 12:02`:
  - **Visual traits:** color / size / material descriptors matched against stored visual captions or embeddings.
  - **Spatial / Room cues:** *"in the kitchen"*, *"near the sofa"* $\rightarrow$ soft or hard filter via `rooms.py` and `anchors.py`.
  - **Coarse temporal windows:** *"just now"* ($\le 30$ min), *"this morning"* (06:00–12:00), *"this afternoon"* (12:00–17:00), *"earlier today"*, *"yesterday"* $\rightarrow$ converted by `timeutil.py` into soft time ranges relative to query time.
  - **Routine / Activity anchors:** *"after breakfast"*, *"while reading"*, *"after lunch"* $\rightarrow$ resolved against episode intervals in `activities.py`.

---

## 5. Restructuring the Evaluation Suite: The 4-Tier Query Protocol

Do **not** delete existing exact episodic tests. Instead, stratify all query benchmarks (`queries.jsonl`, `egolife_queries.json`, and `query.py`) into **four explicit, non-overlapping tiers** so every metric measures something scientifically honest.

### Tier Summary Table

| Tier | Name | Realism | Example Query | Ground Truth Form | Primary Metrics |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **T1** | **Unique / Enrolled Personal** | High (Daily patient use) | `"Where are my glasses?"` / `"Where is my mug?"` (enrolled VIP or unique in home) | Single target `(object_id, room, anchor)` | **Top-1 Localization Acc**, Room Acc, Anchor Acc |
| **T2** | **Ambiguous Class-Level** | High (Daily patient use) | `"Where is the mug?"` (2+ unregistered mugs exist) | Target instance ID(s) + `expected_ambiguous: true` | **Recall@3**, **MRR**, **Ambiguity Detection F1**, **False-Confidence Rate** |
| **T3** | **Fuzzy Human-Cue Episodic** | High (Realistic recall) | `"Where is the blue mug?"`, `"Where did I leave the mug in the kitchen?"`, `"Where was the mug this morning?"` | Single target (or small valid set) narrowed by cue | **Top-1 Acc**, **Recall@3**, Cue-Filter Precision |
| **T4** | **Exact Episodic (Oracle Upper-Bound)** | Low (Diagnostic stress test) | `"Where is the mug I put on the table on DAY3 at 12:02?"` | Exact `(object_id, episode/timestamp, room, anchor)` | **Top-1 Exact Retrieval Acc**, Temporal-Index Accuracy |

### What Each Tier Proves (Critical for FYP Defense & Reports)
- **T1** proves Aegis solves the #1 real patient workflow (*personal everyday essentials*) in one shot.
- **T2** proves Aegis handles *genuine household ambiguity* safely—surfacing the right object in the Top-3 visual cards (`Recall@3`) instead of hallucinating certainty (`False-Confidence Rate`).
- **T3** proves Aegis understands *natural human memory cues* (color, room, routine, coarse time) without brittle timestamp formatting.
- **T4** preserves your existing exact-timestamp/episode tests as a **Backend 4D Index Upper-Bound**, isolating pure scene-graph / temporal-retrieval accuracy from language ambiguity.

### New / Upgraded Metrics to Add in `src/aegis/evaluation/metrics.py`

1. **Top-1 Accuracy (Direct Resolution):** Standard exact room/anchor/object match on T1, T3, T4.
2. **Recall@K ($K \in \{1, 3\}$):** Fraction of queries where the ground-truth object placement appears within the top $K$ returned candidates. Essential for T2 (and informative on T3).
3. **Mean Reciprocal Rank (MRR):**
   $$\text{MRR} = \frac{1}{|Q|} \sum_{i=1}^{|Q|} \frac{1}{\text{rank}_i}$$
   Directly measures whether **salience/interaction ranking** beats naive recency (run an explicit ablation: *Recency-Only Baseline* vs. *Salience + Registry Ranker*).
4. **Ambiguity Detection Precision / Recall / F1:** Evaluates `predicted.is_ambiguous` against `ground_truth.expected_ambiguous` across T1 (should be `False`) and T2 (should be `True`).
5. **False-Confidence Rate (FCR) — Safety Metric for Dementia Care:**
   $$\text{FCR} = \frac{\#\{\text{queries where } \text{is\_ambiguous}=\text{False AND Top-1 is wrong}\}}{|Q|}$$
   In assistive healthcare, silently sending a dementia patient to the wrong room with full confidence is far worse than showing 2 photo choices. Lower FCR is a standout clinical metric.
6. **Evidence Crop Availability Rate (on T2):** Fraction of disambiguation candidates that include a valid, readable visual crop from `evidence.py` (since visual disambiguation requires images).

---

## 6. Recommended Annotation Schema Extensions

Keep all extensions **additive and backward-compatible** so existing JSONL/JSON fixtures load with sensible defaults:

```json
{
  "query_id": "q_mug_004",
  "query": "Where is the mug?",
  "query_tier": "T2_ambiguous_class",
  "ambiguity_expected": true,
  "cue_types": [],
  "personal_registry_enrolled": false,
  "query_time_ref": "DAY3 14:30:00",
  "ground_truth": {
    "target_object_id": "obj_mug_02",
    "acceptable_object_ids": ["obj_mug_02"],
    "expected_room": "living_room",
    "expected_anchor": "coffee_table",
    "expected_time_window": ["DAY3 12:00:00", "DAY3 12:05:00"]
  },
  "notes": "Two mugs exist in scene; obj_mug_01 is static in kitchen sink (seen 14:25), obj_mug_02 was carried to living room coffee table at 12:02."
}
```

**Defaults when legacy annotations omit new fields:**
- `query_tier`: infer `"T4_exact_episodic"` if explicit day/clock timestamp is present; otherwise default `"T1_unique_personal"` or `"unclassified"` (log a warning rather than crashing).
- `ambiguity_expected`: default `False`.
- `cue_types`: subset of `["visual", "room", "coarse_time", "activity", "exact_time"]`.

---

## 7. Built-In Ablations to Automate in `run.py` / `report.py`

To make the evaluation reports (`evaluation/reports/*/summary.md`) compelling and diagnostic, support a lightweight ranking-mode comparison flag (e.g., `--ranker recency_only | salience | full`):

1. **`recency_only` (Baseline):** Current behavior—ranks all class matches strictly by `last_seen_ts`, always returns Top-1.
2. **`salience` (Interaction + Displacement):** Ranks by hand-contact / placement / displacement + recency, with Top-$K$ ambiguity detection.
3. **`full` (Registry + Salience + Fuzzy Cues):** Adds `home_registry.py` VIP resolution and fuzzy human-cue filtering.

Reporting a side-by-side table of **T1 / T2 / T3 / T4** across these three modes quantitatively proves *why* each design layer exists.

---

## 8. Guardrails & Anti-Patterns (Strict Rules for Coding Agents)

- **DO NOT** hardcode dataset-specific rules or EgoLife-specific string hacks into `src/aegis/memory/reasoning.py`. All cue mappings (coarse time buckets, synonym classes) must live in config (`config/vocabulary.yaml`, `timeutil.py`, or evaluation config).
- **DO NOT** grade T2 (ambiguous class queries) solely with Top-1 exact match and treat failures as pipeline bugs; always report `Recall@3`, `MRR`, and `Ambiguity F1` alongside Top-1.
- **DO NOT** leak exact timestamps (`DAY3 12:02`) into T1, T2, or T3 prompt text. Keep exact-timestamp queries strictly isolated in **T4**.
- **DO NOT** break existing evaluation pipelines (`demo05`, `memory_control`, `option_c`, `controlled_room`, `egolife`) or existing unit tests. All new fields in `QueryResult` / schemas must be optional with safe defaults.
- **DO NOT** inflate `is_ambiguous = True` on every query to game `False-Confidence Rate`—`Ambiguity F1` and `T1 Direct Resolution Rate` explicitly guard against over-flagging ambiguity.

---

## 9. Phased Implementation Plan for the Agent

### Phase 1: Audit & Schema Alignment (Zero Breaking Changes)
1. Inspect `src/aegis/evaluation/{schema,query,metrics,egolife,report,run}.py` and `evaluation/annotations/egolife_queries.json`.
2. Add optional tier & ambiguity metadata fields (`query_tier`, `ambiguity_expected`, `cue_types`) to the evaluation query schema and templates (`evaluation/templates/queries.jsonl`, `annotation_guide.md`).
3. Tag existing queries (including `egolife_queries.json`) into `T1`–`T4` without deleting any existing test cases.

### Phase 2: Candidate-Aware Reasoning & Ranking (`src/aegis/memory/`)
1. Inspect `reasoning.py`, `home_registry.py`, `scene_graph.py`, `evidence.py`, and `activities.py`.
2. Extend the reasoning output structure to return ranked `candidates` (up to $K=3$ with evidence crop references and score breakdowns) plus `resolution_mode` and `is_ambiguous`.
3. Implement configurable ranker modes (`recency_only`, `salience`, `full`) utilizing existing placement/hand-contact/displacement signals and `home_registry.py` personal items.
4. Add fuzzy human-cue extraction/filtering (room, coarse time window via `timeutil.py`, activity window via `activities.py`, visual attributes if available).

### Phase 3: Tiered Metrics, Ablations & Reporting (`src/aegis/evaluation/`)
1. Implement `recall_at_k`, `mrr`, `ambiguity_f1`, `false_confidence_rate`, and `evidence_crop_rate` in `metrics.py`.
2. Update `query.py` and `report.py` to break down metrics **per tier (`T1`–`T4`)** and print the `recency_only` vs. `salience` vs. `full` ablation table in `summary.md` and `summary.json`.

### Phase 4: Verification & Regression Tests
1. Add targeted unit tests in `tests/test_evaluation_query.py`, `tests/test_evaluation_metrics.py`, and `tests/test_reasoning.py` covering:
   - Enrolled VIP mug resolving directly (`T1`, `is_ambiguous=False`).
   - Two unregistered mugs where an older *moved* mug outranks a newer *static* background mug (`T2`, `MRR` improvement + `is_ambiguous=True` when close).
   - Fuzzy cue narrowing (`T3`: room + coarse time window).
   - Exact episodic oracle query (`T4`) remaining backward-compatible.
2. Run the full verification suite:
   ```bash
   pytest tests/test_evaluation*.py tests/test_egolife.py tests/test_reasoning.py tests/test_home_registry.py
   ```