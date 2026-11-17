# Annotation guide (held-out video)

The evaluation is only as credible as its ground truth. These rules are written
to keep the annotator independent of the pipeline: annotate what is visible in
the video, not what the scene graph says.

## 1. Freeze first

- Record the git commit and pipeline config before annotating.
- Annotation keyframes are the pipeline keyframes listed in
  `outputs/<dataset>/geometry/poses.json`.
- Do not change prompts, target classes, or thresholds after this point.
- If a genuine annotation error is found later, log it in the report rather
  than silently editing the score.

## 2. Detection annotations (`detections.jsonl`)

- One record per annotated keyframe, with an `objects` array.
- `bbox` is `[x1, y1, x2, y2]` in pixels of the source frame.
- `label` is the ordinary object name (`shoes`, `shirt`, `basket`). Do not copy
  memory suffixes such as `#1` or `[Left Shelf]` into the label.
- `instance_id` is a stable integer for that physical object across the video.
  Two shoes are two instances. A sock that disappears and reappears keeps its
  ID.
- Mark partially visible objects as `"visibility": "occluded"`; do not delete
  them if their location is still inferable.
- Masks are optional but strongly recommended for at least the primary object
  class. Save binary PNGs relative to the annotation directory.
- Do not label hands as target objects. Hands are interaction context; the
  evaluation config excludes them.

### Label aliases

Open-vocabulary detectors emit synonyms. The config may collapse true
synonyms (`shoe` → `shoes`), but never collapse distinct instances or distinct
physical classes. Keep left/right shoes separate through `instance_id`.

## 3. Events (`events.jsonl`)

- Event types: `pickup`, `placement`, `state_change`, `room_change`.
- Times are seconds from the start of the video, with millisecond precision.
- `pickup`: hand takes hold of an object. `placement`: object is released at a
  new location. Use the visible contact interval, not the whole approach.
- Include `source_anchor` / `destination_anchor` when the location is clear.
  Leave them null when it is not; do not guess.
- `room_change` events use `source_room` / `destination_room` and are scored
  separately with the same time tolerance.

## 4. Rooms (`rooms.json`)

- Draw each room footprint as a polygon on the floor plane in pipeline world
  coordinates. If the reconstruction is scale-aligned, use the same alignment
  as the controlled-room protocol and say so.
- `frame_rooms` gives the true room at each annotated keyframe. A frame in a
  doorway is labelled with the room the wearer is entering only once the body
  centre has crossed the threshold.
- `room_changes` records the transition timestamp. The scorer tolerates ±1 s by
  default.
- Neutral labels (`Room #1`) validate segmentation only. Typed labels
  (`Kitchen`) validate naming and should come from caregiver calibration.

## 5. Question bank (`queries.jsonl`)

- Questions must be written **before** running the held-out evaluation.
- Cover four kinds:
  1. present object with a clear anchor (`Where are my shoes?`);
  2. present object in a named room (`Where is the shirt in the bedroom?`);
  3. object that was moved (`Where did the blue sock go?`);
  4. negative probes (`Where are my keys?` when no keys exist).
- Expected fields are checked only when present:
  - `expected_instance_label` — the memory instance, e.g. `Shoes #1`;
  - `expected_anchor` — the anchor label, without instance suffix;
  - `expected_room` — the room label;
  - `expected_relation` — `inside`, `on_surface`, `on_floor`, `carried_by_user`.
- A negative probe must have `expected_found: false`. Any `found: true` answer is
  a false-found failure, even if the answer names a real object.
- Do not paraphrase a question after seeing the pipeline answer.

## 6. Persistence cases (`persistence.jsonl`)

- Each case names a query, the expected instance, and the frame at which memory
  is tested.
- `occlusion_start` / `occlusion_end` mark when the object is not directly
  visible.
- `expect_persistent: true` means the answer must come from remembered state;
  an entry that is still flagged as an active view is a failure for that case.
- Include at least one relocation case and one long occlusion (> 10 keyframes).
- False merges are scored separately: two physical objects sharing one predicted
  ID is worse than two predicted IDs for one object.

## 7. Controlled-room measurements (CSV)

- Measure object centres from the room origin in metres.
- Record the room and anchor names exactly as they should appear in answers.
- Record a known-size reference (for example a 24 cm bottle) in the notes.
- `predicted_instance_id` is optional; when supplied it pins the pairing and
  removes association ambiguity.
- Repeat each measurement three times and use the median; note the spread.

## 8. Adjudication

- Two annotators label at least 20% of frames.
- Report agreement as mean box IoU and mean mask IoU on the overlap.
- Adjudicate disagreements before scoring. Store the adjudicated file as the
  ground truth and keep the originals for provenance.
