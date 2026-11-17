# Live showcase — talk track

A 12–15 minute script. The goal is to show **what the system does and why it
is built that way**, not to claim completeness. Say the limitations out loud;
they are the most credible part of the demo.

## Before you start (0:00–2:00)

Start `demo/run_demo.sh`. While capture and the pipeline run, say:

> "The phone is not running our app. It is an IP Webcam MJPEG server, and we
> pull frames from a URL. That boundary is deliberate: `FrameSource` keeps the
> transport separate from persistence and memory, so a different camera needs
> no change to the pipeline."

Point at the capture terminal:

> "Samples arrive at 2 FPS, but we keep a frame only when it is sharp, exposed
> and visually different — with a forced interval so a static scene is still
> represented. A pause file or SIGUSR1 pauses; gaps are recorded, not hidden."

Run `demo/pipeline_status.py` on the projection so the audience can see the
frame count and any gaps.

## First segment (2:00–5:00)

Walk through two rooms and place a high-importance object (keys or medicine)
on a table or cabinet. Wait for the first segment. Say while waiting:

> "A segment is a bounded unit of work. VGGT produces about 4.3 MB of
> pointmaps per keyframe and loads them whole, so reconstructing an hour in
> one pass would not fit. Each segment is an ordinary dataset: upload,
> preprocess, reconstruct, detect and lift, build the memory graph, download,
> then ingest into the home store. The GPU containers stay warm between
> segments so models are not reloaded."

> "Segments do **not** share geometry. Every session has its own world origin,
> so the home store joins them symbolically by room and anchor, not by
> coordinates. That is why we can keep memory across sessions without a global
> metric map."

When the segment lands, run `demo/pipeline_status.py` again and read the stage
timings and gravity line aloud. If `gravity_source` is `floor_plane`, say:

> "Up is estimated from the floor plane, not assumed to be minus Y. The phone
> starts tilted, so height has to be derived. The raw VGGT coordinates are
> never rotated — the up vector and floor height live beside them."

If it says `assumed` or `camera_prior`, **drop the under/on-floor part** of the
talk and say so honestly.

## Grounded answer (5:00–7:00)

Open the segment's `.rrd` in Rerun:

> "Left: the egocentric video. Right: the 3D memory — room footprints,
> furniture anchors, and boxes labelled as persistent instances. The boxes
> say *which* instance, not just 'shoe'. Identity survives occlusion."

In the app, ask "where are my keys?":

> "The answer names the room, the anchor, the relation, and whether it is
> remembered rather than currently seen. It never invents a location. The app
> reads this segment's graph because that is what the current client sends."

## Durable memory (7:00–10:00)

In Swagger / `curl`, with `home_id`:

```bash
curl 'http://localhost:8000/api/v1/rooms?home_id=aegis-demo'
curl -X POST 'http://localhost:8000/api/v1/rooms/rename?home_id=aegis-demo&room_id=1&label=Kitchen'
curl 'http://localhost:8000/api/v1/query?item=keys&home_id=aegis-demo'
curl 'http://localhost:8000/api/v1/timeline?home_id=aegis-demo'
uv run aegis-memory show --home-id aegis-demo
uv run aegis-memory size --home-id aegis-demo
```

Say:

> "This is the part the app cannot show today. The home store keeps stable
> rooms, anchors and objects across sessions. It stores **state runs** — one
> row per stable placement — not one row per keyframe, so memory grows with
> changes, not with recording time. After three days, history is compacted
> into verified text summaries, but the last-known state is never compacted."

> "Renaming a room writes the room table and mirrors it to `home_map.json`.
> Caregiver labels survive restart and later sessions; query answers then say
> 'in the Kitchen' instead of 'in Room #1'."

Use the simulator presets (`/simulate/bottle_occluded`, `/simulate/floor`,
`/simulate/bottle_table2`, `/reset`) if live detection was unlucky. Say
explicitly that these are in-memory demo transitions, not observed memory.

## Pause / reconnect (10:00–11:00)

Toggle the app's Recording switch or touch/remove the pause file; optionally
drop phone Wi-Fi for 10 seconds. Show the gap in `session.json`:

> "Pauses and disconnects become explicit gap records with timestamps. That
> is what makes a recording trustworthy for 'when did the camera last see
> this?' questions."

## Honest close (11:00–13:00)

Say plainly:

> "What you just saw is Milestones 1 and 2: live capture, bounded processing,
> room-level spatial memory, persistent identities and a durable per-home
> store. The following are **planned, not implemented**: speech input,
> temporal questions like 'when did I last see my keys', computed confidence
> and abstention, evidence images in the app, authentication, TLS and
> encryption, and the caregiver portal. They are specified as WP16–WP35 in
> `context/plan.md` Part II. The 'Tap to Ask by Voice' button in the app is a
> stub today."

> "Two other limits worth stating: the app shows one segment's graph, not the
> whole home memory — the API with `home_id` does. And evidence crops kept
> past the 24-hour raw-frame rule still need supervisor confirmation."

## If asked "why not just stream into the pipeline?"

> "Because the expensive stage is reconstruction, and because raw frames are
> a privacy liability. Pulling at 2 FPS with keyframe selection, processing in
> bounded segments, and purging raw frames after 24 hours gives bounded GPU
> memory, bounded disk, and a clear artifact boundary. The cost of that choice
> is latency: memory updates every few minutes rather than every frame. We
> think that is the right trade for assistive recall, and we say so."

## Sources to quote

- `docs/running_aegis.md` — setup, Part B verification, current client contract.
- `docs/live_capture.md` — capture → promotion → segment runbook.
- `docs/artifact_contracts.md` — schemas, raw-coordinate invariant, home store.
- `context/answer.md` — why state runs, why ~50 MB steady state, why gravity.
- `context/plan.md` §0.3 and Part II — decisions and the roadmap slides.
- `docs/evaluation_suite.md` — what is measured versus proposed.

Do **not** repeat the old dossier's `S = 5.0×` or Z-up claims, and label any
storage figure as projected unless it has a result file behind it.
