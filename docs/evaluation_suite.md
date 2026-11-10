# Aegis Evaluation Suite

This is the single evaluation document for Aegis. It covers the held-out video
protocol, the controlled-room experiment, the Ego4D feasibility decision, the
memory-control study, and a concrete plan for proving long-term persistence.

Short version for the panel:

> We do not self-grade. The harness compares saved pipeline artifacts with
> independent human annotations or physical measurements. When the ground truth
> does not exist, it writes **NOT READY** instead of inventing a score. Claims
> are separated into what has been measured, what is planned, and what is still
> future work.

---

## 1. Evidence status at a glance

| Question | Option | Current status | Evidence |
|---|---|---|---|
| Does perception find the right objects, keep identities, detect events, localise rooms, and answer questions in an unseen care-style clip? | **A** — held-out video | **Protocol frozen; no result yet** | `demo05` is held out; annotations and pipeline outputs do not exist. `evaluation/reports/demo05/readiness.md` says `NOT_READY`. |
| Are 3D centres, relations, anchors, and rooms correct in a physically measured room? | **D** — controlled room | **Harness ready; no measurement yet** | Measurement CSV template and Umeyama-alignment checker exist. No controlled-room recording has been scored. |
| Can Aegis report a number on a public egocentric benchmark? | **C** — Ego4D | **NO-GO at 0%** | No access, data, adapter, or validated official score. Estimated 10.8 weeks of remaining work. |
| Does the memory stay bounded under compression without losing persisted state? | **Memory control** | **Feasible in principle on short clips** | 100% semantic/full/latest-state retention; 1.5–1.9× compression with exact geometry, 5.7–6.4× with stated interpolation error. |
| Does the memory remain correct for days or weeks in a real home? | **Long-term persistence** | **Not yet proven** | The current clips are minutes long. Section 7 defines the study that would prove it. |

The honest headline is therefore:

> The evaluation machinery is built and tested, but the two main accuracy claims
> (Option A and Option D) still need data. Option C is explicitly not claimed.
> Memory control is demonstrated on short clips. Long-term persistence is the
> next experiment, not a result.

---

## 2. Why a separate evaluation harness

The pipeline that produces predictions must not also define the scoring. The
evaluation package therefore:

- lives under `src/aegis/evaluation/` and is not imported by the pipeline;
- reads only saved artifacts (`r4d_scene_graph.json`,
  `detected_objects_3d.json`, `poses.json`) plus annotation files;
- reuses the API query path so the scored path is the production path;
- records input hashes, git commit, config path, Python version, and platform in
  every report;
- refuses to score a section whose inputs are absent (`NOT RUN`, not zero);
- keeps the full-resolution timeline untouched; compaction is an audited
  prototype, not a silent production change.

### 2.1 What "independent ground truth" means

Independent means the ground truth was not produced by Aegis. The allowed
sources are:

- a human annotator labelling the frozen video;
- physical measurements taken with a floor grid and known-size reference;
- caregiver logs of object moves during a longitudinal study;
- official benchmark annotations from Ego4D, if access is granted.

Pipeline output, model confidence, and scene-graph labels are never ground
truth.

---

## 3. Option A — held-out video protocol

### 3.1 Split discipline

| Role | Clip | Use |
|---|---|---|
| Development | `demo01`, `demo03`, `demo04` | Tune prompts, thresholds, tracking. |
| Held-out | `demo05` ("Sort Dirty Clothes") | Report final results; no tuning after freeze. |
| Optional generalisation | other rooms/tasks | Show transfer, not the headline number. |

The split unit is the **complete video**, never a frame. Frames from one video
must not appear in both development and held-out sets. `demo05` is deliberately
unprocessed: the raw video exists, but no scene graph, detections, or poses.
That is what makes it a genuine held-out clip.

Freeze before annotating:

1. the pipeline config;
2. the git commit;
3. the target class list and prompt policy;
4. the annotation guide;
5. the query bank;
6. the success targets in this document.

### 3.2 Metrics and targets

Targets are acceptance criteria frozen before scoring. They are not results.

| Layer | Metric | Target | Why it matters |
|---|---|---:|---|
| Detection | precision | ≥ 0.85 | False boxes waste caregiver trust. |
| Detection | recall | ≥ 0.75 | Missed objects break the memory. |
| Detection | F1 | ≥ 0.80 | Balanced headline. |
| Tracking | IDF1 | ≥ 0.75 | Same name on the same object. |
| Events | F1 (±1 s) | ≥ 0.75 | Pickup/placement is the memory update. |
| Rooms | per-keyframe accuracy | ≥ 0.90 | Room-grounded answers need it. |
| Rooms | room-change F1 | ≥ 0.70 | Transitions are safety-relevant. |
| Persistence | state recall | ≥ 0.90 | Occluded objects stay queryable. |
| Persistence | query recall | ≥ 0.90 | The API must answer from memory. |
| Queries | grounded accuracy | ≥ 0.80 | Instance + anchor + room + relation. |
| Isolation | leakage rate | = 0.00 | No foreign memories. |
| Latency | p95 | < 500 ms | Dementia-appropriate response. |

Detection uses class-aware matching at IoU 0.5. Mask IoU is reported only for
matched pairs that have both ground-truth and predicted masks. AP is
all-point interpolated per class.

Tracking reports IDF1, MOTA, ID switches, fragmentation, and mostly-tracked
ratio. **HOTA is not approximated.** A home-made HOTA would be less credible
than saying "use TrackEval". The harness keeps enough MOT information for that
export.

Room scoring has three parts:

1. per-keyframe accuracy after mapping predicted room IDs onto ground-truth IDs
   by maximum frame agreement;
2. Hydra-style region containment precision/recall on footprints;
3. room-change event F1 with the same ±1 s tolerance as object events.

Mapping IDs is necessary because a neutral `Room #2` in the prediction is not
required to have the same number as `Room #2` in the annotation. What matters
is that the same physical room is consistently identified.

### 3.3 Persistence scoring within a session

Each labelled case names a query, an expected instance, an anchor, a room, a
relation, and a check frame. The scorer:

- finds the memory entry at the last keyframe at or before the check frame;
- verifies label, instance ID, anchor, room, and relation;
- answers the query against a graph slice containing only memory known at that
  frame;
- checks whether the entry is still an active view when the case expects
  persistent memory;
- counts false merges when the predicted label differs from the expected label.

Occlusion survival is therefore measured on the **query path**, not just by
looking for a row in the timeline.

### 3.4 Ablations

The same question bank and persistence cases are re-run against four memory
variants:

| Variant | What is removed | What a drop means |
|---|---|---|
| `full` | nothing | Baseline. |
| `no_persistence` | remembered entries that are not currently visible | The score depends on object permanence. |
| `no_memory` | everything except the final active view | The score depends on history. |
| `no_rooms` | room IDs and labels | The score depends on room grounding. |

Ablations are diagnostic. They show which component a score depends on; they do
not prove that the component is correct.

### 3.5 Dataset isolation

For every pair of processed datasets, the harness probes the target dataset with
labels unique to the other dataset, plus configured items that must never appear
(`keys`, `wallet`, `glasses`, `medication`, `phone`). A `found: true` answer is
leakage. The target is exactly 0, because a care assistant that answers from
another resident's memory is worse than one that says "I don't know".

### 3.6 Latency

Latency is measured through the real FastAPI route after one warm-up request,
with 100 requests by default. The report keeps p50, p95, max, mean, and error
count. Graph-mode timings are also recorded, but the headline number should be
the HTTP route because that is what the mobile app calls.

### 3.7 Report contents

`summary.md` contains:

1. scorecard with claim, metric, result, target, verdict, n, and note;
2. inputs and hashes;
3. per-class detection table and mask summary;
4. tracking summary;
5. event failures;
6. room confusion matrix and region metrics;
7. persistence failures;
8. query failures with expected vs actual;
9. latency and dataset-isolation probes;
10. ablation table;
11. failure gallery;
12. method and limitations;
13. provenance;
14. exact reproduce command.

`summary.json` contains the same data plus typed records for downstream tools.

---

## 4. Option D — controlled-room experiment

### 4.1 Setup

- One room, measured with a floor grid and at least one known-size reference.
- 5–10 objects spanning `inside`, `on_surface`, `on_floor`, and
  `carried_by_user`.
- Each object measured three times from a fixed room origin; use the median.
- Record the room name and anchor name exactly as the caregiver would use them.
- Keep the camera path and object placement fixed across repeated runs.

### 4.2 Alignment

Monocular reconstruction is scale-ambiguous. Reporting raw 3D error in metres
would be dishonest. The checker therefore fits a similarity transform
(Umeyama: scale, rotation, translation) from predicted centres to measured
centres, then reports:

- **scale-aligned centre error** (mean, median, RMSE, p95, max);
- **fitted scale factor** and deviation from 1;
- fraction of objects within the target error;
- relation, anchor, and room accuracy (independent of alignment);
- per-object errors and unmatched measurements.

The scale factor is itself evidence. A value near 1 supports the claim that the
pipeline's units are approximately metric; a value far from 1 says the
reconstruction is only up to scale.

`--assume-metric-scale` adds a pass/fail check at ±10%, but it must be justified
by the protocol. With fewer than three non-collinear points, the checker reports
`INSUFFICIENT` rather than pretending that a fitted scale is meaningful.

### 4.3 Targets

| Measure | Target |
|---|---:|
| Mean scale-aligned centre error | ≤ 0.30 m |
| Relation accuracy | ≥ 0.80 |
| Anchor accuracy | ≥ 0.80 |
| Room accuracy | ≥ 0.90 |

These targets are deliberately modest. A single room is a demonstration, not a
generalisation study.

---

## 5. Option C — Ego4D feasibility

### 5.1 The question

Could Aegis report a number on Ego4D in time for the FYP-1 defence?

**Not as a result. Yes as a planned extension, if the checklist clears.**

The current decision is **NO-GO for an FYP-1 result claim**, because no
benchmark data, adapter, or validated score exists. The path to a future
conditional-go is concrete and encoded in `src/aegis/evaluation/option_c.py`.

A public-benchmark number produced on a different dataset, with different
splits, or with an unofficial metric would not survive panel review.

### 5.2 What Ego4D offers

| Task | What it measures | Relation to Aegis |
|---|---|---|
| **NLQ** (Natural Language Query) | Locate the temporal window for a natural-language query. | Tests query grounding and temporal memory. |
| **VQ2D** (Visual Query 2D) | Track a queried object through a response track with 2D boxes. | Tests 2D grounding and object permanence within a clip. |
| **VQ3D** (Visual Query 3D) | Localise a queried object in 3D. | Closest to R4DSG, but coverage is limited. |
| **EgoTracks** | Long-term single-object tracking. | Tests identity persistence and re-identification. |

### 5.3 Cost and access reality

| Item | Reality | Consequence |
|---|---|---|
| License | Gated access through Lab22; approval is typically fast (~48 h) after signing. | Access is not the main blocker. |
| Credentials | Valid for roughly 14 days. | Download, adapt, and score inside one window, or re-request. |
| Benchmark subset | Order of **~1 TB**. | Storage and transfer are real costs; the full set is not a laptop download. |
| Compute | VGGT-Ω + open-vocab detection + SAM 2 over many clips. | Modal GPU budget must be estimated from measured per-video runtime. |
| Adapter | 3–6 weeks of engineering to map clips, queries, tracks, and timestamps. | This is the dominant schedule risk. |
| Metric parity | Official Ego4D evaluation code and official splits are required. | A home-made approximation cannot be presented as a leaderboard number. |

### 5.4 Domain mismatch

Ego4D is general egocentric video. It is **not** an assistive-care dataset. A
strong Ego4D score would support claims about perception and spatial grounding
in diverse environments. It would not support claims about:

- usefulness for older adults or caregivers;
- clinical safety;
- memory accuracy for medication, appointments, or personal belongings;
- privacy behaviour in a home.

Ego4D is therefore **external generalisation evidence**, not a substitute for
Options A and D.

### 5.5 Readiness scorecard

The scorer uses eleven weighted prerequisites (100 points total):

| Category | Prerequisite | Weight | Blocker |
|---|---|---:|---|
| access | License approved and credentials issued | 20 | yes |
| access | Credentials valid for the evaluation window | 5 | no |
| data | Held-out benchmark videos downloaded | 10 | yes |
| data | Official annotations and splits downloaded | 10 | yes |
| engineering | Aegis → Ego4D adapter implemented | 15 | yes |
| engineering | Query/memory output mapping defined | 5 | no |
| science | Scoring validated against official definitions | 10 | no |
| engineering | GPU and storage budget confirmed | 10 | no |
| governance | Ethics/privacy review covers the benchmark | 5 | no |
| science | Protocol and success criteria frozen | 5 | no |
| science | Domain-mismatch risk stated and bounded | 5 | no |

Decision rule:

- **go** — no blockers missing and score ≥ 80%;
- **conditional-go** — score ≥ 50% but blockers or validation remain;
- **no-go** — score < 50%.

The current facts file sets every prerequisite to false. That produces a
**no-go at 0%**, which is the correct statement of the repository's evidence.
The scorer is not there to flatter the project; it is there to prevent an
unsupported claim.

### 5.6 Adapter contract

The adapter is the only bridge between Ego4D and Aegis. It must:

1. read official clips and annotations without re-splitting videos;
2. preserve `clip_uid`, `video_uid`, and clip-relative timestamps;
3. map NLQ queries to `QuerySpec` and temporal windows to
   `NLQAnnotation` / `NLQPrediction`;
4. map VQ2D response tracks to `BoxObservation` (xyxy pixels);
5. run Aegis on the clip window and write artifacts under
   `outputs/<clip_uid>/`;
6. score with the harness for sanity, then with the **official** Ego4D
   evaluation code for the reported number;
7. never tune prompts, classes, or thresholds on the test split.

The machine-readable contract is returned by `adapter_contract()` and included
in the generated report.

### 5.7 Current decision and what would change it

**For the FYP-1 defence: NO-GO.** Do not claim an Ego4D result. Report:

- the readiness score and the blockers;
- the adapter contract;
- the domain-mismatch caveat;
- Option A and Option D as the actual evidence.

**For a follow-on project: CONDITIONAL-GO**, if:

1. access is approved and credentials are valid;
2. a small official sample is downloaded and the adapter runs end-to-end;
3. the harness agrees with the official scorer on that sample;
4. the compute budget is estimated from measured runtime;
5. the protocol is frozen.

Only then should the full subset be run. A staged sample first is cheaper and
catches timestamp/adapter errors before a 1 TB job.

---

## 6. Memory control — bounded growth

### 6.1 The worry

The R4DSG timeline stores one entry per known instance per keyframe, including
instances that are currently occluded. That is what gives object permanence, but
raw size grows as:

```
entries ≈ frames × known instances
```

For a short demo this is small. For a full day it is not obviously safe. The
question is:

> Can the memory keep every object's latest state and every event, while storing
> far fewer per-frame entries and without breaking answers?

The prototype lives in `src/aegis/evaluation/memory_audit.py`; it is **not** a
silent change to the production memory engine.

### 6.2 What is measured

**Growth audit, per graph:**

- frames, duration, entries, instances, anchors, rooms, events;
- entries per frame and per instance;
- semantic state runs (a new run only when the state changes);
- canonical JSON bytes, gzip bytes, bytes per frame;
- linear projections to 8 h and 24 h, labelled as projections.

**Compact representation:**

1. per-instance state runs — start/end frame, timestamp, and all semantic
   fields (`label`, `anchor`, `room`, `relation`, `is_in_hand`, `carrier`);
2. sparse centre snapshots every N keyframes — `center`, `size`,
   `relative_vector`, `relative_distance`, `rotation`, `yaw`;
3. an exact latest state for every instance;
4. active-view ranges — enough to reconstruct `is_active_view` and
   `last_seen_timestamp` without storing a boolean per frame;
5. unchanged anchors, rooms, events, and frame timestamps.

Between snapshots, geometry is linearly interpolated from the nearest snapshots
and run endpoints. The snapshot interval is the tunable knob: larger intervals
compress more but increase reconstruction error.

**Retention metrics:**

| Metric | Meaning |
|---|---|
| **full retention** | semantic state + active-view flag + last-seen timestamp all match exactly |
| **semantic retention** | label, anchor, room, relation, carrier, hand state match |
| **label retention** | canonical label matches |
| **active-view retention** | `is_active_view` matches |
| **last-seen retention** | `last_seen_timestamp` matches within 1 µs |
| **centre error** | L2 distance between original and reconstructed centres, in scene units |
| **latest-state exactness** | every instance's final semantic state matches exactly |
| **query agreement** | answers from the compacted latest state match the original |

Query agreement uses the same `answer_query` path as the API. When no query file
is supplied, the audit generates label probes automatically and states that in
the report.

### 6.3 Measured results on the existing clips

| Dataset | Snapshot every | Frames | Entries | Instances | State runs | Ratio | Full retention | Centre p95 | Latest exact | Query agreement |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `demo04` | 0 | 117 | 268 | 5 | 13 | 7.2× | 100% | 0.363 | 100% | 100% |
| `demo04` | 1 | 117 | 268 | 5 | 13 | 1.9× | 100% | 0.000 | 100% | 100% |
| `demo04` | 30 | 117 | 268 | 5 | 13 | 6.4× | 100% | 0.245 | 100% | 100% |
| `demo03` | 0 | 100 | 981 | 16 | 58 | 5.7× | 100% | 0.219 | 100% | 100% |
| `demo03` | 1 | 100 | 981 | 16 | 58 | 1.5× | 100% | 0.000 | 100% | 100% |

Interpretation:

- **Exact geometry:** snapshot interval 1 gives 1.5–1.9× compression with zero
  centre error.
- **Balanced compression:** sparse snapshots give 5.7–6.4× compression with
  centre p95 ≈ 0.22–0.25 scene units, while semantic state, latest state, and
  query answers remain exact.
- **Projected 24 h storage:** 324 MiB → 51 MiB (`demo04`, balanced) and
  450 MiB → 78 MiB (`demo03`, balanced). These are linear projections, not
  measured 24 h runs.
- Queries use the exact latest state, so answer agreement does not depend on
  interpolating historical geometry.

### 6.4 What this proves — and does not prove

**Proves:**

- the representation can preserve every instance's semantic state, latest
  state, events, anchors, and rooms while storing fewer per-frame entries;
- query answers from the compacted latest state agree with the original;
- the size/accuracy trade-off is visible and tunable.

**Does not prove:**

- real-world persistence over days — the clips are minutes long;
- production database performance — the prototype serialises JSON;
- metric 3D accuracy — centre errors are in scene units;
- that compression is free — interpolation is an approximation, and the error is
  reported.

### 6.5 Recommended integration path

1. Keep the full-resolution timeline as an append-only archive, or delete it
   after compaction.
2. Serve queries from the compacted latest state and state runs.
3. Keep a sparse snapshot every 10–30 keyframes for point-in-time
   reconstruction. Choose the interval from measured error, not a guess.
4. Store events, anchors, and rooms unchanged; they are already small.
5. Add a retention policy: keep all state runs, downsample snapshots for
   sessions older than N days.
6. Move the prototype into the memory engine only after the evaluation tests
   cover reconstruction and query parity.

### 6.6 Verdict

- **Feasible in principle** — at least one tested interval preserved full
  semantic state, every latest state exactly, and exact geometry (centre
  p95 ≤ 0.05 scene units).
- **Feasible with a stated trade-off** — full semantic state and latest state
  are preserved, but exact geometry needs denser snapshots.
- **Needs attention** — no tested interval preserved full semantic state and
  latest state with bounded reconstruction error.

The current result is **feasible in principle** on short clips. It is a
representation result, not a claim that Aegis has run for a week in a care home.

---

## 7. Proving long-term persistence

This is the section that turns "the memory should persist" into a defensible
claim. It is deliberately stricter than the short-clip memory audit.

### 7.1 Define the claim precisely

There are three different claims, and they need different evidence:

| Claim | Meaning | Required evidence |
|---|---|---|
| **Within-session persistence** | An object stays queryable after it leaves the camera view during one recording. | Option A persistence cases; occlusion gaps of seconds to minutes. |
| **Long-term object memory** | An object keeps its identity and last-known location across days, including after re-observation. | Longitudinal home study with caregiver logs and repeated queries. |
| **Current-location accuracy** | Aegis knows where an object is *now*, even if nobody observed it move. | This is impossible without an observation or a sensor. The honest behaviour is "last seen at X; not seen since Y", not a confident false answer. |

The third row is the trap. A care assistant must not claim certainty it does
not have. Long-term persistence means **correct memory of the last observed
state**, not clairvoyance.

### 7.2 Minimum credible study

A 7-day pilot is enough for an FYP demonstration. A 30-day run is enough for a
stronger thesis claim. Both use the same protocol.

| Element | Pilot | Stronger study |
|---|---|---|
| Duration | 7 consecutive days | 30 consecutive days |
| Rooms | 2–3 | 3–5 |
| Objects | 8–12 | 15–20 |
| Recording | One 15–30 min walkthrough per day, plus event-triggered clips | Same, plus occasional longer sessions |
| Ground-truth audit | Morning and evening inventory by a caregiver | Same, plus weekly full room measurement |
| Relocation events | At least 20 logged moves | At least 50 logged moves |
| Query opportunities | At least 100 | At least 400 |
| Participants | One home | Two homes if ethics and time allow |

The study should be framed as a technical memory evaluation, not a clinical
trial. Do not recruit patients or claim clinical benefit without ethics
approval.

### 7.3 Ground truth that is independent of Aegis

Use three layers:

1. **Object inventory:** a fixed list of object IDs, labels, and home anchors.
2. **Caregiver move log:** timestamp, object, from-anchor/room, to-anchor/room,
   and whether the move was observed by the camera wearer. A simple form or
   spreadsheet is enough; it must not be generated from the scene graph.
3. **Daily verification walk:** the caregiver visits each object and records
   whether it is at the expected location. Repeat each measurement three times
   for the controlled-room subset and use the median.

Optional but useful:

- a known-size reference object in each room for scale calibration;
- QR/ArUco labels on storage anchors (not on objects) to make anchor IDs
  unambiguous;
- a wall clock or phone timestamp visible at the start of each session.

Do **not** use Aegis's own output to decide where an object was. That would make
the evaluation circular.

### 7.4 Test cases to label

| Case | Setup | Expected behaviour |
|---|---|---|
| **Static + occluded** | Object stays in a cabinet/drawer for days. | Same instance ID, same anchor, same room; `inside`; marked as remembered, not currently visible. |
| **Observed move** | Caregiver moves object while the wearer watches. | Same instance ID; new anchor/room; event logged; old location no longer claimed. |
| **Unobserved move** | Someone moves the object while the wearer is away. | Must say "last seen at X; not seen since Y" and express uncertainty. A confident wrong answer is a failure. |
| **Removed from home** | Object leaves the home and does not return. | Must not hallucinate it in the home. `found: false` or "not seen recently" is correct. |
| **Similar duplicates** | Two pairs of shoes, two bottles, etc. | Distinct instance IDs; no false merge; per-instance answers. |
| **Cross-room carry** | Object is carried from one room to another. | Room and anchor update; object remains the same instance. |
| **Re-observation after days** | Object disappears and reappears after a long gap. | Identity is recovered if evidence supports it; otherwise a new instance is created and the uncertainty is stated. |
| **Room rename** | Caregiver renames "Room #2" to "Kitchen". | Future answers use the calibrated name; old memories map to the same room. |

### 7.5 Metrics and proposed targets

These are proposed acceptance targets for the longitudinal study, not measured
results.

| Metric | Definition | Proposed target |
|---|---|---:|
| **Persistence recall at 1 day** | Correct instance + anchor + room for unchanged objects after ≥ 1 day | ≥ 0.90 |
| **Persistence recall at 7 days** | Same, after ≥ 7 days | ≥ 0.85 |
| **Persistence recall at 30 days** | Same, after ≥ 30 days | ≥ 0.75 |
| **Observed-move accuracy** | Correct new location after a logged move | ≥ 0.90 |
| **Unobserved-move calibration** | Correct "last seen + uncertainty" behaviour; no confident false current location | ≥ 0.90 |
| **Identity precision** | Predicted instance IDs that refer to the correct physical object | ≥ 0.95 |
| **False-merge rate** | Two physical objects assigned one ID | ≤ 0.02 |
| **False-found rate** | Query returns `found: true` for an object that is not in the home | ≤ 0.05 |
| **False-not-found rate** | Query returns `found: false` for a present object | ≤ 0.10 |
| **Query accuracy** | Correct instance + anchor + room + relation | ≥ 0.80 |
| **Storage growth** | Compacted bytes per day; slope over 30 days | sublinear / bounded |
| **Latency p95 at day 30** | HTTP query latency | < 500 ms |

Report confidence intervals (Wilson) for every proportion and state the
denominator. A single home is a case study, not a population estimate.

### 7.6 Analysis plan

1. **Survival curve:** persistence recall as a function of gap length
   (1 h, 1 day, 3 days, 7 days, 14 days, 30 days).
2. **Per-object breakdown:** which object classes survive and which fail.
3. **Per-room breakdown:** doorway transitions, occluded storage, and cluttered
   surfaces are likely failure modes.
4. **Failure taxonomy:** wrong instance, wrong anchor, wrong room, wrong
   relation, false found, false not found, confident stale answer.
5. **Ablations:** full memory, no-persistence, no-memory, no-rooms, and
   different snapshot intervals.
6. **Memory growth:** entries, state runs, canonical bytes, gzip bytes, and
   query latency per day. Fit a line and report the slope; do not just show a
   single endpoint.
7. **Re-observation recovery:** time and number of observations needed to
   recover the correct identity after a gap.

### 7.7 Instrumentation changes to make the study possible

The current graph needs a little metadata before a multi-day study is clean:

- `session_id` and `capture_day` on every graph;
- `recording_start` and `recording_end` timestamps;
- `last_verified_at` and `verification_source` on each object instance;
- a `moved_unobserved` flag or event type for caregiver moves that the camera
  did not see;
- an `as_of` query parameter so the API can answer "what did Aegis know at time
  T?" without leaking later memory;
- per-day graph slices in the evaluation runner;
- per-day memory-audit output, not just one aggregate.

These are small schema additions, but they make the difference between a
demo and a defensible longitudinal evaluation.

### 7.8 What would falsify the claim

The long-term claim should be rejected if any of these happen:

- persistence recall falls below the proposed target at 7 or 30 days;
- false merges exceed 2%;
- Aegis confidently reports a current location after an unobserved move;
- a removed object is still reported as present in the home;
- storage or latency grows without bound over 30 days;
- the result depends on tuning after the study begins.

Report these failures. A negative result with a clear failure taxonomy is more
defensible than a polished number with no ground truth.

---

## 8. If Ego4D access is granted

Ego4D is useful, but it is **not a longitudinal care-home dataset**. Be precise
about what it can and cannot prove.

| Claim | Can Ego4D prove it? | Why |
|---|---|---|
| Perception and 2D grounding generalise to diverse egocentric video | **Yes** | Large, varied benchmark with official VQ2D/NLQ metrics. |
| Query grounding and temporal localisation generalise | **Yes** | NLQ measures temporal windows for natural-language queries. |
| Object identity survives occlusion within a clip | **Partly** | VQ2D response tracks and EgoTracks provide occlusion/reappearance cases, but only within one video. |
| Memory survives across days | **No** | Ego4D clips are not multi-day recordings of one home. |
| Aegis is useful for dementia care | **No** | Ego4D is general egocentric video, not a care population. |

### 8.1 Concrete Ego4D plan

Do a small, staged pilot before committing to the full benchmark.

1. **Access:** apply through Lab22. Approval is usually fast (~48 h), but
   credentials expire in ~14 days, so plan the work window.
2. **Small subset:** download only the official val clips needed for a pilot
   (for example 10–20 VQ2D/NLQ clips with long occlusion gaps). Do not start
   with the ~1 TB full set.
3. **Adapter:** implement the contract in Section 5.6. Run one clip end-to-end
   and verify timestamps, clip boundaries, and query IDs.
4. **Persistence stress set:** from VQ2D response tracks, select cases where the
   queried object is occluded or absent for a meaningful part of the clip. Add
   checkpoints before, during, and after the gap.
5. **Run Aegis:** process each clip window with the frozen pipeline. Write
   artifacts under `outputs/<clip_uid>/`.
6. **Score twice:**
   - official Ego4D metrics on the official split (VQ2D response-track IoU,
     NLQ R@tIoU);
   - Aegis-specific persistence metrics (instance retention, re-identification
     after occlusion, query answer correctness, false merge rate).
   Keep the two result sets separate. Never present Aegis-specific metrics as
   official leaderboard numbers.
7. **Report the domain caveat:** state clip durations and gap lengths. "Within
   a 10-minute clip" is not "across 30 days".

### 8.2 Ego4D persistence metrics to add

| Metric | What it measures |
|---|---|
| **Response-track presence** | Does Aegis keep a box on the queried object across the annotated track? |
| **Re-identification after occlusion** | After the object disappears and reappears, is it the same instance? |
| **Identity switch rate** | How often does the predicted identity change while the ground-truth object is stable? |
| **False merge rate** | Are two different objects collapsed into one memory? |
| **NLQ temporal IoU** | Does Aegis localise the right time window for "when did I last see X?" |
| **Answer correctness** | Does the grounded answer name the right instance/anchor/room? |

### 8.3 Go/no-go for the Ego4D pilot

- **Go to a 10-clip pilot** when access is approved and the adapter runs one clip
  end-to-end.
- **Go to a larger subset** only when the harness agrees with the official
  scorer on the pilot and the compute cost is measured.
- **Do not claim an Ego4D leaderboard result** until the official evaluation
  code has been run on the official split.
- **Do not claim long-term persistence from Ego4D.** Use it for external
  generalisation and within-clip occlusion evidence.

### 8.4 If access does not arrive

Run the home study in Section 7 without Ego4D. Report Option C as future work
with the readiness score and adapter contract. That is still defensible: the
panel can see that the benchmark path is specified and costed, even if it was
not executed.

---

## 9. Panel-ready claims matrix

Use this table to keep claims aligned with evidence.

| Claim | Evidence required | Current status |
|---|---|---|
| Aegis detects and tracks care objects in an unseen clip | Option A detection/tracking on `demo05` | Protocol frozen; no result yet |
| Aegis grounds objects in rooms and anchors | Option A rooms/anchors + Option D | Harness ready; no result yet |
| Aegis remembers occluded objects within a session | Option A persistence cases | Harness ready; no result yet |
| Aegis answers only from the selected dataset | Isolation probes | Harness ready; target leakage = 0 |
| Aegis is fast enough for a care app | API latency p95 | Harness ready; no held-out result yet |
| Aegis reconstructs a measured room accurately | Option D controlled room | Harness ready; no measurement yet |
| Aegis memory stays bounded | Memory-control audit | Feasible on short clips |
| Aegis persists across days | Longitudinal home study | Not yet proven; protocol in Section 7 |
| Aegis generalises to diverse egocentric video | Ego4D pilot | NO-GO at 0%; plan in Section 8 |
| Aegis is clinically useful | Clinical/user study | Not claimed |

---

## 10. Reproducibility

Every report records:

- config path and dataset ID;
- git commit, branch, and dirty flag;
- SHA-256 of every input file;
- Python version and platform;
- generated timestamp;
- the exact command to reproduce.

The harness has no hidden dependency on SciPy, matplotlib, pandas, pycocotools,
or TrackEval. It uses NumPy and the standard library. MOT export is available
for anyone who wants the official HOTA implementation.

---

## 11. What this evaluation does not prove

- It does not prove clinical usefulness or safety.
- It does not replace a usability study with older adults or caregivers.
- It does not prove generalisation beyond the annotated clips.
- It does not make 3D errors metric without a measured room and a scale check.
- It does not turn a readiness report into a result.
- It does not approximate HOTA or official Ego4D metrics.
- It does not prove multi-day persistence until the Section 7 study is run.

---

## 12. Commands

```bash
# Option A (writes readiness.md until annotations and predictions exist)
uv run python -m aegis.evaluation.run \
  --config evaluation/configs/demo05.yaml

# Option D
uv run python -m aegis.evaluation.controlled_room \
  --measurements evaluation/annotations/controlled_room/measurements.csv \
  --scene-graph outputs/controlled_room/objects/r4d_scene_graph.json \
  --output-dir evaluation/reports/controlled_room

# Memory control
uv run python -m aegis.evaluation.memory_audit \
  --graphs outputs/demo04/objects/r4d_scene_graph.json \
           outputs/demo03/objects/r4d_scene_graph.json \
  --snapshot-intervals 0,1,10,30 \
  --output-dir evaluation/reports/memory_control

# Option C readiness
uv run python -m aegis.evaluation.option_c \
  --facts evaluation/configs/option_c_facts.yaml \
  --output-dir evaluation/reports/option_c

# Tests and lint
uv run pytest
uvx ruff check src tests run_pipeline.py run_server.py
uvx ruff format --check src tests run_pipeline.py run_server.py
```

## 13. Generated reports

| Report | Purpose |
|---|---|
| `evaluation/reports/demo05/readiness.md` | What is missing before Option A can be scored. This is a status, not a result. |
| `evaluation/reports/memory_control/summary.md` | Measured compression, retention, and query agreement. |
| `evaluation/reports/option_c/summary.md` | Readiness score, blockers, effort, and adapter contract. |

---

## 14. Recommended next actions

1. **Annotate `demo05`** using the templates in `evaluation/templates/`.
   Freeze the query bank before looking at any pipeline answer.
2. **Run the controlled-room experiment** with a floor grid and known-size
   reference. Report scale-aligned error, not absolute metres.
3. **Start the 7-day persistence pilot** in Section 7. Even a small pilot with
   caregiver logs is stronger evidence than another short clip.
4. **If Ego4D access arrives**, run the 10-clip pilot in Section 8 before
   committing to the full subset. Keep official metrics and Aegis-specific
   persistence metrics separate.
5. **Keep the frozen protocol.** Any change after seeing held-out results must
   be reported as a new experiment, not hidden in the final number.
