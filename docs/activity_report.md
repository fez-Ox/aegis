# Activity / routine answers (P1.1, final part)

## What changed

`AnswerEngine` no longer stubs `Intent.ACTIVITY`. `memory_view_from_repo`
includes the store's activity rows, and `_answer_activity()`:

- parses human time cues relative to the snapshot (`as_of`), not the host clock;
- accepts an exact `at` time with a ±10 minute window;
- summarises up to three room stays with the objects moved, attaching one
  evidence record per stay;
- abstains honestly with `no_activity_history`, `no_activities_in_window`, or
  `invalid_at` rather than inventing an activity.

The clock prefix of a stored activity summary is stripped without splitting on
the colon inside `HH:MM`, so answers read "You were in Kitchen, Mug #1 moved…".

## Measured result

`evaluation/annotations/activity_queries.json` is derived from the frozen
EgoLife caption bank (object and place nouns, no Aegis output).
`scripts/activity_bench.py` scores `/api/v1/ask` with `at` set to each caption
time:

```
n=5  answered=5/5  object_match=5/5  place_match=5/5  with_evidence=5/5
```

A 45-case stress sweep (7 question forms × 6 datasets plus three `home_id`
variants) returned 200 with well-shaped responses every time.

## Honest limits

- Activity answers require a durable home (`home_id`). A single graph queried
  by `dataset_id` has no activity history and abstains honestly; building
  activities from a graph without ingested sessions is not implemented.
- The summary is the stored template text: it lists object moves, not inferred
  goals ("made coffee"). No LLM writes answer text.
- Time-window cues are coarse (`this morning`, `yesterday`) plus an exact-time
  oracle; arbitrary natural-language ranges are not parsed.
- 509 tests pass; ruff clean.
