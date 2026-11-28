# Temporal answers and freshness (P1.1 / P1.3)

## Ground truth

`evaluation/annotations/temporal_queries.json` is derived once from the frozen
EgoLife bank and its independently labelled tiers sidecar: six query rows with
caption placement timestamps and coarse place nouns, plus verbatim T3/T4
prompts. No Aegis output is used.

`scripts/temporal_bench.py` scores the production `/api/v1/ask` path.

## Implemented

- `core/timeutil.time_ago()` — generic freshness buckets ("just now",
  "N minutes/hours ago", "yesterday", "N days ago", "over a week ago"), with
  `None` for missing/invalid timestamps and clock-skew clamping.
- `/api/v1/query` and `/api/v1/ask` now populate `last_seen_time_ago` from the
  state's own wall clock, measured against the memory timeline (not the host
  clock, which would call a fresh dataset "26 years old").
- `AnswerEngine._answer_temporal()` answers "when did I last see X" with a
  grounded time, place and evidence crop, and abstains honestly when the item
  is unknown, unobserved, undated, or outside a requested window.
- `/api/v1/ask` accepts `as_of` (snapshot time) and `at` (exact T4 oracle time).
  The oracle accepts a cue inside a state run's `[start, end]` interval, not
  just within 180 s of its end.
- Fixed a real integration bug: the NLQ dictionary maps "cup" → "cup" while
  the production vocabulary canonicalises it to "mug"; answers now canonicalise
  dictionary items before matching store states.
- `as_of` no longer peeks at evidence that ended after the question time.

## Measured result

| Mode | time/evidence correct | place correct | freshness present |
|---|---:|---:|---:|
| `as_of` (snapshot) | 5/6 | 1/6 | 5/6 |
| `latest` (no snapshot) | 0/6 | 3/6 | 6/6 |
| `at` (T4 oracle) | **6/6** | 3/6 | 6/6 |

Freshness wording: **6/6** exact matches against deterministic expectations.
Malformed `as_of` / `at` now abstain with `invalid_as_of` / `invalid_at`
instead of returning HTTP 500.

## Honest limits

- The bank's `expect_time` is a *placement* time from captions; "when did I
  last see X" legitimately returns the most recent sighting, so the two differ
  by hours or days. That is reported, not tuned away.
- Place accuracy is 3/6 for the oracle: the mug states in the durable store at
  those caption times are near chairs, while captions say table/desk. This is
  a scene-graph grounding difference, not a temporal bug.
- Activity ("what did I do this morning?") remains an explicit honest stub.
- 505 tests pass; ruff clean. 57 stress combinations across six datasets and
  temporal query forms returned 200 with well-shaped responses.
