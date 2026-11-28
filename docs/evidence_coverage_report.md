# P1.4 — evidence on every non-abstaining answer

## Implemented

`memory.evidence.answer_evidence()` is the single builder for answer evidence.
Every record carries:

- `observation_id` (instance / activity id),
- `observed_at` (wall clock, or the state's `last_seen_at` / relative timestamp),
- `anchor_label` / `room_label` when known,
- `crop_url` **or** an explicit `text_fallback` describing the place.

`evidence_complete()` enforces the contract. It is wired into `/api/v1/query`
(new `evidence` list) and all three NLQ handlers (locate, temporal, activity),
replacing ad-hoc per-handler dictionaries.

Two real gaps found by the benchmark and fixed: graph candidates expose
`last_seen_at` rather than `last_seen_wallclock`, and a shared default evidence
id made several candidates look like the same observation.

## Measured

`scripts/evidence_bench.py` sweeps `/query` and `/ask` across the six datasets
plus the EgoLife home (locate, temporal, activity questions):

```
responses 51   non-abstaining 19   fully evidenced 19   coverage 1.000
HTTP errors 0
```

Before the two fixes, coverage was 0.526.

513 tests pass; ruff clean.
