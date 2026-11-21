# EgoLife multi-day memory evaluation

Tests whether Aegis still knows where an object is after days of intervening
activity, using a public 7-day egocentric dataset instead of a home recording.

## Why not just fetch the evidence clip and the question clip

Fetching only `target_time` and `query_time` reduces the task to two unrelated
30-second videos in a database. Nothing has to persist, and a "answer from the
most recent clip" baseline scores identically. The protocol below keeps a
contiguous window per day and ingests the days in order, so every query has to
survive the days in between.

## Protocol

| Setting | Value |
|---|---|
| Participant | `A1_JAKE` (the only participant with human-written EgoLifeQA) |
| Window | 12:00–13:00 every day, 7 days |
| Segments | 5 minutes, one Modal dataset per segment |
| Keyframes | every 3 s (5 fps, stride 15), 100 per segment |
| Ingest order | chronological; a query on day N sees only days 1..N |

`vggt.max_keyframes` is 120, so a one-hour video cannot be reconstructed in one
pass; each day is cut into 5-minute segments. `recorded_at` is taken from the
**first clip of the segment**, not the nominal bucket start, because EgoLife
days start mid-bucket.

Querying needs no `as_of` parameter: after each day is ingested,
`HomeStore.latest_states()` is exactly "what the system knew at the end of this
day". The run therefore also produces an accuracy-vs-days curve for free.

## Commands

```bash
# Download 7 hours (cached, ~10 GB) and cut segments
uv run python scripts/egolife_fetch.py --days 1-7

# Plan and cost only
uv run python scripts/egolife_eval.py --days 1-7

# Run it (~7.5 h wall clock, ~$5 GPU)
uv run python scripts/egolife_eval.py --days 1-7 --execute --cleanup
```

Outputs: `outputs/evaluation/egolife/report.json`, `report.md`, and
`dayN_states.json` (the store's belief at the end of each day, used to build
the query bank).

## Query bank

`evaluation/annotations/egolife_queries.json` is empty by design. Fill it after
the first run by checking `dayN_states.json` against the video, then freeze the
file's SHA-256 before scoring. Filling it in after seeing the answers
invalidates the result.

Each query is scored on presence, room, anchor, and — as an ablation — the same
question answered from only the last 24 hours of evidence. The ablation is the
headline: if full history beats "last day only" on day-5 questions about day-1
objects, that is the long-term memory claim.

## Measured cost

One 5-minute segment on an L4: VGGT 200 s + detection 108 s = 0.086 GPU-hours
= **$0.069**. Preprocess is CPU (65 s). 74 segments ≈ **$5.1 GPU**.

## Known limitations

1. **EgoLifeQA cannot carry this evaluation.** Of 500 questions, 24 are about
   object location and only 5 span more than one day. It is a secondary,
   independent check; the main result depends on the manual query bank.
2. **Room identity is unstable across sessions.** Measured on two consecutive
   segments: session 1 produced four rooms, session 2 one, and session 2's room
   matched the wrong home room, so none of its anchors matched. The cause is
   that `memory.rooms.zone_link_radius` is an absolute distance in VGGT units,
   and VGGT scale is arbitrary per reconstruction. Room and anchor counts in
   the report measure this directly; linear growth is the failure signature.
3. **Domain.** EgoLife is a shared house of six volunteers planning a party,
   not a care home. It supports "memory survives days in real egocentric
   video", not "this helps dementia care".
4. **Temporal resolution.** One keyframe every 3 s will miss placements shorter
   than that.
5. **The query bank is written by us**, not an independent annotator. Two
   annotators on a subset and the pre-run hash are the only mitigations.
