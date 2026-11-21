# EgoLife multi-day memory evaluation

**Result (2026-11-22):** the run completed all 74 segments for **$8.71 metered,
$0 billed**. The frozen class-level queries do not demonstrate long-term memory
(full history never beats the 24 h ablation), but an oracle-assisted instance
diagnostic found that **12/12 matched ground-truth instances were still in the
store 1–4 days later**. See `outputs/evaluation/egolife_scored/FINAL_SUMMARY.md`.

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
| Ground truth | EgoLife's own DenseCaption SRT for the same 12:00 hour, A1_JAKE |

`vggt.max_keyframes` is 120, so a one-hour video cannot be reconstructed in one
pass; each day is cut into 5-minute segments. `recorded_at` is taken from the
**first clip of the segment**, not the nominal bucket start, because EgoLife
days start mid-bucket.

Querying needs no `as_of` parameter: after each day is ingested,
`HomeStore.latest_states()` is exactly "what the system knew at the end of this
day". The run therefore also produces an accuracy-vs-days curve for free.

## Commands

```bash
# Fetch into the Modal volume (~15-30 min; nothing downloads locally)
uv run python scripts/egolife_fetch.py --days 1-7 --modal

# Run it (~7.5 h wall clock, ~$5 GPU) using the videos already in the volume
uv run python scripts/egolife_eval.py --days 1-7 --execute --cleanup \
  --skip-existing --no-upload --out outputs/evaluation/egolife_modal

# Re-score from the downloaded graphs without any GPU (fresh store, chronological)
uv run python scripts/egolife_eval.py --days 1-7 --replay \
  --out outputs/evaluation/egolife_scored
```

Outputs: `report.json`, `report.md`, and `dayN_states.json` (the store's belief at
the end of each day). The report records the query bank's SHA-256. `--replay`
re-ingests the graphs into a separate `<home>_replay` store, so scoring is
reproducible from artifacts alone and never mutates the live evaluation store.

## Query bank

`evaluation/annotations/egolife_queries.json` contains 17 frozen queries. Ground
truth is **third-party and independent of Aegis**: EgoLife ships one dense
caption `.srt` per hour per participant, so `A1_JAKE_DAY*_12000000.srt` describes
exactly the hour the system processes. The bank was written before the run
finished, and its SHA-256 (`16e7c83f…`) is recorded in the report.

Selection rule:

1. Find a caption that explicitly places a vocabulary object at a named place
   (e.g. `我把数据线放到桌子上`, "I put the cable on the table", DAY1 12:04:19).
2. Keep the query only if no later caption places that object at a *different*
   named place. Placement-free mentions (holding, looking, pointing) do not
   invalidate it.
3. Ask on one or more later days. The longest clean gap is the garbage bag
   placed on DAY3 and asked about on DAY7.

`expect_place` is a coarse noun list, not a system label. Chinese `桌子` does not
distinguish desk from dining table, so both are accepted. This avoids the
circularity of writing ground truth by copying Aegis's own anchor names.

Scoring is on **presence** (is the object still remembered?) and **place** (does
the anchor label name the right surface?). Room and anchor exact-match rates are
still computed as diagnostics but carry no expected values in the bank.

The headline is the ablation: each query is answered twice, once from full
history and once from only the last 24 hours of state runs. If full history
beats "last day only" on a DAY7 question about a DAY3 placement, that is the
long-term-memory claim. `keys` and `wallet` (zero caption mentions all week) are
abstention tests in both conditions.

## Measured cost

One 5-minute segment on an L4: VGGT 200 s + detection 108 s = 0.086 GPU-hours
= **$0.069**. Preprocess is CPU (65 s). 74 segments ≈ **$5.1 GPU**.

## Known limitations

1. **EgoLifeQA cannot carry this evaluation.** Of 500 questions, 24 are about
   object location and only 5 span more than one day. It is not used.
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
5. **Captions are machine-generated.** The dense captions are third-party but
   not human-verified end to end; one placement (DAY1 12:04:19, cable on table)
   was checked against the video frame, which also confirmed the burned-in
   timestamp matches `recorded_at`. A panel should spot-check a larger sample.
6. **Short observable gaps.** Because only one hour per day is sampled, most GT
   placements are re-mentioned within a day or two; the longest clean gap is
   four days. This tests multi-day persistence, not week-long persistence.
7. **Coarse place granularity.** `桌子` maps to both "desk" and "dining table".
   Exact anchor identity is not scored against the captions.
