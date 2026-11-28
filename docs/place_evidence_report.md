# P1 backbone — place-evidence grounding experiments

## Root-cause fix adopted: rank the JSON graph path properly

`JsonGraphRepository.latest_states_from_graph()` now derives the same ranking
features the durable home store has, from each instance's `state_runs` and
`events`: `observation_count`, evidence, `last_seen_wallclock` /
`last_moved_wallclock` (relative seconds mapped to a fixed epoch),
`first_room_id` / `first_anchor_id` and `placement_count`.

Before this, **every candidate on the JSON graph path scored exactly 0.0**: the
salience ranker saw no recency, interaction or displacement features and
silently stopped ranking. This is the single largest robustness fix in this
round — it affects all five demo videos and any new dataset processed by the
pipeline, not just the confidence work.

Measured on the 15 hand-labelled demo queries
(`scripts/demo_confidence_bench.py`, `evaluation/annotations/demo_queries.json`):

| | direct | wrong | withhold recall | withhold F1 |
|---|---:|---:|---:|---:|
| before enrichment | 10 | 4 | 0.417 | 0.588 |
| **after enrichment** | **7** | **3** | **0.667** | **0.800** |

Per video (before → after): demo01 `0.800→1.000`, demo03 `0.667→1.000`,
demo04 `0.000→0.000`, demo05 `0.667→0.667`, demo_pots `0.667→1.000`.
459 tests pass, ruff clean.

## Rejected as defaults: hard place-evidence rules

`scripts/place_evidence_bench.py` A/Bs generic priors over the 15 demo queries
and 17 frozen EgoLife queries. All settings are category-independent.

| Variant | wrong direct | withhold F1 |
|---|---:|---:|
| baseline | 8 | 0.766 |
| anchorless penalty 0.3 / 0.6 | 8 | 0.723 (regresses demo05, demo_pots) |
| carried penalty 0.5 | 8 | 0.739 |
| require anchor for direct | 5 | 0.824 |
| both penalties + require | 5 | 0.800 |

`require_anchor` improves EgoLife day7 (`0.667→0.889`) and overall F1, but
regresses demo05 (`0.667→0.500`): the anchored basket candidate ("near Stove",
weak relation) is visually wrong while the room-level answer is correct.
No tested variant improved **every** slice, so all three knobs
(`anchorless_penalty`, `carried_penalty`, `require_anchor_for_direct`) remain
**off by default**. They stay in `RankingConfig` as documented experiment
knobs so the A/B is reproducible.

## Stress testing (`tests/test_backbone_stress.py`)

Added 10 stress tests; **470 tests pass** in total. Coverage:

- `GET /api/v1/query` and `GET /api/v1/ask` for all five datasets × 15 query
  forms (class names, room constraints, visual traits, empty/whitespace,
  unicode, unknown words, 5 000-character string). Every response is 200 with
  bounded candidates and finite confidence in [0, 1].
- `rank_candidates` across three ranker modes × three config sets × four
  queries on all five graphs — no NaN/inf, bounded scores.
- Determinism of graph enrichment, empty and malformed graphs, v1 timeline
  graphs, and pathological query strings.
- Durable-store path: all 17 frozen EgoLife queries through both endpoints
  produced only honest `abstain` / `disambiguate` / `direct` outcomes, no 5xx.
- Ranking latency on 1 158 EgoLife instances: 5.3–12.4 ms per query (10-run
  average), so the enrichment has no practical cost.

### Fresh unseen input (Modal, `stress_egolife_s00`)

Full pipeline on `egolife_d1_s00` (different source, 1 502 frames): 895
detections/masks, 97 tracks, 50 events, two rooms. GT in
`evaluation/annotations/stress_egolife_queries.json` was authored by viewing
frames at t=5/15/30/45 s (red-cap bottle on the checkered table, trash bin by
the kitchen counter, no toilet or cooking pot).

- Ranking is **functional on newly produced artifacts**: top scores 0.650
  (bottle), 0.900 (trash bin) instead of the previous constant 0.0.
- GT score: 1 direct (wrong), 3 correct withholds, withhold F1 0.857.
- Both `/api/v1/query` and `/api/v1/ask` return 200 for all four queries with
  honest abstentions for absent classes.
- Residual error is again semantic: the top trash bin is in "Room #2" while
  the frame shows it beside the kitchen counter — a room-typing issue, not a
  ranking or confidence issue.

## What this means for generality

The enrichment fix generalises: any new graph produced by the pipeline now
has a functional ranker. The remaining demo04 errors are semantic (objects
carried or not visible in the sampled frame), not ranking or confidence
errors — fixing them needs better place evidence at acquisition time, not
another ranking prior.
