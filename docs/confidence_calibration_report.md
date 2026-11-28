# P1.2 — calibrated answer confidence and abstention

## What changed

`reasoning.py` now exposes `calibrated_confidence(state, moment, config)` and
`reference_time(states)`. A candidate's answer confidence is raw detection confidence multiplied by
penalising identity/support/recency factors (neutral = 1.0, so a weak detection
is never inflated):

| Factor | Meaning |
|---|---|
| detection | raw detector confidence from the state run |
| identity | 1.0 for a certain relation, else `uncertain_identity` (0.0) |
| support | 1.0 with ≥1 observation, else `uncertain_identity` |
| recency | `0.5 ** (age_hours / confidence_half_life_hours)` |

Missing optional fields are neutral, not punitive (graph-only states lack wall
clock and evidence ids). `reference_time` falls back to the newest evidence in
memory so a historical dataset is not judged "stale" against the host clock.

Abstention reasons are distinct: **`stale`** (evidence older than 7 days) and
**`low_confidence`** (score below 0.35). No candidates still reports
`not_found`. Genuine multi-instance ambiguity keeps priority: it shows
candidate photos (`disambiguate`) rather than hiding them behind an abstention.

Wired into both answer paths: `rank_candidates()` (`/api/v1/query`) and
`AnswerEngine` (`/api/v1/ask`, `aegis-ask`, both mobile apps). The API returns
`abstain_reason` and an honest summary string instead of a guessed location.
`ConfidenceConfig` (`memory.confidence` in YAML) holds all settings; weights,
threshold, half-life and staleness are category-independent.

## Ground truth and harness

`scripts/confidence_bench.py` consumes the **frozen 17-query EgoLife bank** and
its independent `ambiguity_expected` sidecar (manual caption pass), plus the
CPU-only rescore report:

```bash
uv run python scripts/egolife_eval.py --home egolife_jake --rescore \
    --days 1-7 --ranker all
uv run python scripts/confidence_bench.py --out outputs/evaluation/confidence_bench.json
```

No ground truth is derived from Aegis output. "Withhold" means the system must
not give one confident answer: the candidate place is wrong or the class is
genuinely ambiguous. Every setting is generic and checked per ask-day.

## Measured result

| Policy | Direct answers | Wrong direct | Withhold recall | Withhold F1 |
|---|---:|---:|---:|---:|
| Baseline (no threshold, no identity veto) | 5 | 5 | 0.706 | 0.828 |
| **Shipped calibration** | **2** | **2** | **0.882** | **0.938** |

Per ask-day withhold F1, baseline → shipped:
day 4 `1.000 → 1.000`, day 5 `0.667 → 1.000`, day 6 `0.857 → 1.000`,
day 7 `0.824 → 0.889`. **Every slice improves or holds.**

## Demo videos (five different environments)

`evaluation/annotations/demo_queries.json` is a second, hand-labelled bank:
15 queries authored from extracted frames of demo01, demo_pots, demo03,
demo04 and demo05 (shoe cabinet, dish rack, kitchen, waste/bathroom, laundry).
`scripts/demo_confidence_bench.py` scores each video's R4DSG graph:

```
                     direct  wrong  withhold_recall  withhold_F1
baseline                10      4          0.417        0.588
shipped calibration     10      4          0.417        0.588
```

Per-video withhold F1 (baseline = shipped): demo01 0.800, demo03 0.667,
demo04 0.000, demo05 0.667, demo_pots 0.667. **No change on any video.**

Why: the four wrong demo answers are confidently misplaced, not weakly
evidenced — e.g. `Garbage Bag #5` conf 0.913, `Bottle #8` conf 0.838,
`Shoes #4` conf 0.512, all with `relation_certain=True`, ≥1 observation and
evidence within seconds of the session end. None of detection/identity/support/
recency fires, so the policy correctly leaves them alone. Session-graph states
are now enriched from `state_runs` (`observation_count`, evidence, relative
time) so calibration sees the same features as the durable home store — the
result is unchanged.

**This is the key generalisation finding:** calibration helps EgoLife because
that memory contains genuinely uncertain/stale states; it does **not** improve
accuracy on our five demo videos, where the errors are semantic (wrong place),
not confidence-related.

## Honest limits

- The **false-confidence rate stays 1.0**: the two remaining direct answers
  are still wrong. Calibration removed 60% of harmful confident answers but
  cannot correct a confidently misplaced object — that needs better place
  evidence (a separate backbone task), not a confidence formula.
- Mean confidence of answered queries rose 0.372 → 0.930, so the remaining
  answers are *more* overconfident, not calibrated in the strict ECE sense.
- 17 queries from one participant is a small bank; T1 enrollment and
  visual-trait/activity cues remain NOT RUN.

## Verification

```
ruff check / format --check: clean
pytest -q: 459 passed
EgoLife bench: 5 direct/5 wrong → 2 direct/2 wrong, F1 0.828 → 0.938
Demo bench:    10 direct/4 wrong → 10 direct/4 wrong, F1 0.588 → 0.588
```
