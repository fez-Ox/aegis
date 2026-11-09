# Option C — Ego4D Benchmark Feasibility

## 1. The question

Could Aegis report a number on a public egocentric benchmark — Ego4D — in time
for the FYP-1 defence?

The answer this document defends is:

> **Not as a result. Yes as a planned extension, if the checklist clears.**
> The current decision is **NO-GO for the FYP-1 result claim**, because no
> benchmark data, adapter, or validated score exists. The path to a future
> conditional-go is concrete and is encoded in
> `src/aegis/evaluation/option_c.py`.

This is the honest position. A public-benchmark number that was produced on a
different dataset, with different splits, or with an unofficial metric would not
survive panel review.

## 2. What Ego4D offers

Ego4D is a large egocentric video benchmark. The tasks most relevant to Aegis
are:

| Task | What it measures | Relation to Aegis |
|---|---|---|
| **NLQ** (Natural Language Query) | Locate the temporal window for a natural-language query. | Tests query grounding and temporal memory. |
| **VQ2D** (Visual Query 2D) | Track a queried object through a response track with 2D boxes. | Tests 2D grounding and object permanence. |
| **VQ3D** (Visual Query 3D) | Localise a queried object in 3D. | Closest to R4DSG, but coverage is limited. |
| **EgoTracks** | Long-term single-object tracking. | Tests identity persistence. |

## 3. Cost and access reality

| Item | Reality | Consequence |
|---|---|---|
| License | Gated access through Lab22; approval is typically fast (~48 h) after signing. | Access is not the main blocker. |
| Credentials | Valid for roughly 14 days. | Download, adapt, and score inside one window, or re-request. |
| Benchmark subset | Order of **~1 TB**. | Storage and transfer are real costs; the full set is not a laptop download. |
| Compute | VGGT-Ω + open-vocab detection + SAM 2 over many clips. | Modal GPU budget must be estimated from measured per-video runtime. |
| Adapter | 3–6 weeks of engineering to map clips, queries, tracks, and timestamps. | This is the dominant schedule risk. |
| Metric parity | Official Ego4D evaluation code and official splits are required. | A home-made approximation cannot be presented as a leaderboard number. |

## 4. Domain mismatch

Ego4D is general egocentric video. It is **not** an assistive-care dataset. A
strong Ego4D score would support claims about perception and spatial grounding
in diverse environments. It would not support claims about:

- usefulness for older adults or caregivers;
- clinical safety;
- memory accuracy for medication, appointments, or personal belongings;
- privacy behaviour in a home.

Those claims need the held-out care-style clips and, eventually, a user study.
The evaluation suite therefore treats Option C as **external generalisation
evidence**, not as a substitute for Options A and D.

## 5. Readiness scorecard

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

## 6. Adapter contract

The adapter is the only bridge between Ego4D and Aegis. It must:

1. Read official clips and annotations without re-splitting videos.
2. Preserve `clip_uid`, `video_uid`, and clip-relative timestamps.
3. Map NLQ queries to `QuerySpec` and temporal windows to
   `NLQAnnotation` / `NLQPrediction`.
4. Map VQ2D response tracks to `BoxObservation` (xyxy pixels).
5. Run Aegis on the clip window and write artifacts under
   `outputs/<clip_uid>/`.
6. Score with the harness for sanity, then with the **official** Ego4D
   evaluation code for the reported number.
7. Never tune prompts, classes, or thresholds on the test split.

The machine-readable contract is returned by `adapter_contract()` and included
in the generated report.

## 7. Ego4D-style scoring in this repository

`score_nlq` computes temporal IoU and Recall@tIoU (0.3 and 0.5), matching the
standard NLQ headline metrics. `score_vq2d` computes timestamp-matched box IoU
and presence rate. Both are **readiness estimates**:

- they are useful for testing the adapter and catching timestamp bugs;
- they do not implement the official leaderboard protocol;
- they must not be quoted as official Ego4D results.

The tests use synthetic windows and boxes, so the scoring logic is verified
without downloading the dataset.

## 8. Go / no-go recommendation

### For the FYP-1 defence

**NO-GO.** Do not claim an Ego4D result. Report:

- the readiness score and the blockers;
- the adapter contract;
- the domain-mismatch caveat;
- Option A and Option D as the actual evidence.

This is defensible because it distinguishes *what was measured* from *what is
planned*. A panel can inspect the harness, the templates, and the checklist.

### For a follow-on project

**CONDITIONAL-GO**, if:

1. access is approved and credentials are valid;
2. a small official sample is downloaded and the adapter runs end-to-end;
3. the harness agrees with the official scorer on that sample;
4. the compute budget is estimated from measured runtime;
5. the protocol is frozen.

Only then should the full subset be run. A staged sample first is cheaper and
catches timestamp/adapter errors before a 1 TB job.

## 9. What would change the decision

| Evidence | Effect |
|---|---|
| Portal approval + credentials | Clears the access blocker. |
| Local official sample + adapter run | Clears the engineering blocker. |
| Agreement with official scorer on the sample | Clears the science blocker. |
| Measured GPU cost for the subset | Makes the budget credible. |
| Frozen protocol + domain caveat | Makes the claim defensible. |

Until then, Option C remains **future work with a testable plan**, not a result.

## 10. Reproduce the readiness report

```bash
uv run python -m aegis.evaluation.option_c \
  --facts evaluation/configs/option_c_facts.yaml \
  --output-dir evaluation/reports/option_c
```

Outputs: `summary.json` and `summary.md` with the decision, score, missing
prerequisites, effort estimate, and adapter contract.
