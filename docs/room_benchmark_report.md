# Room segmentation and typing — generic A/B report

## Ground truth authored from video frames

`evaluation/annotations/rooms_ground_truth.json` was written by viewing 12-frame
contact sheets (`scripts/make_contact_sheet.py`) from all five demo videos plus
a fresh EgoLife clip — no Aegis output was used. Labels:

| Video | Visual inspection | True rooms |
|---|---|---|
| demo01 | wooden shoe cabinet, tiled floor | Entryway (0–43 s) |
| demo_pots | glass dish cabinet with pots | Kitchen (0–77 s) |
| demo03 | stove, sink, counter, fridge | Kitchen (0–100 s) |
| demo04 | bin, mop, bagged waste | Utility (0–47 s) |
| demo05 | washing machine, two laundry baskets | Laundry (0–141 s) |
| stress_egolife_s00 | meeting table/TV/whiteboard → bed → return | Living Room (0–190, 245–300 s), Bedroom (190–245 s) |

`scripts/room_bench.py` re-extracts regions from poses + 3D boxes for a grid of
**137 generic variants** and scores segmentation accuracy, region precision /
recall, room-change F1 and a typing-accuracy metric.

## Adopted: radius 2.5 + evidence-robust typing

The previous default (`zone_link_radius=1.5`, any single landmark vote) gave:

| | seg | regions | labels |
|---|---:|---:|---|
| demo04 | 0.846 | 2 | Room #1, **Kitchen** (spurious) |
| demo05 | 1.000 | 1 | **Kitchen** (wrong; no stove in frame) |
| stress | 0.816 | 1 | Kitchen |

Shipped settings (radius 2.5; require **2 distinct landmarks** with confidence
≥ 0.8 before a type overrides "Room #N"):

| Video | seg before → after | label before → after |
|---|---:|---|
| demo01 | 1.000 → 1.000 | Room #1 → Room #1 |
| demo03 | 1.000 → 1.000 | Kitchen → Kitchen |
| demo04 | **0.846 → 1.000** | Room #1 + Kitchen → single Room #1 |
| demo05 | 1.000 → 1.000 | **Kitchen → Room #1** (false type removed) |
| demo_pots | 1.000 → 1.000 | Room #1 → Room #1 |
| stress | 0.816 → 0.816 | Kitchen → Kitchen (unchanged) |

No slice regresses; two confident false typings and one spurious region are
removed. Wired through `RoomMemoryConfig`, `scene_graph.py`, `workers.py` and
all five runtime YAMLs.

## Rejected (no universal gain)

- **Small radius (1.0) + same-type merge** gives stress 0.842 and room-change
  F1 0.5, but regresses demo04 to 0.812.
- **Doorway-step splitting** (0.6–1.5 m) creates 3–6 spurious zones on the
  multi-room clip (seg 0.71–0.75) while leaving single-room clips unchanged.
- **Landmark radius** (2–5 m) and min-keyframe count made no difference.

These knobs remain in `extract_room_regions` as documented experiment settings
(defaults preserve the adopted behaviour).

## Honest limits

- Typing accuracy is 1/6: the vocabulary has no room type for Laundry, Utility
  or this Entryway, so those rooms can only be neutral. The strict evidence
  rule makes them honestly neutral rather than confidently wrong.
- The multi-room stress clip is still under-segmented (one region, seg 0.816)
  because all six videos are processed with one generic radius; no tested
  generic rule fixed that without hurting a single-room video. This needs a
  different signal (visual room cues), not another clustering threshold.
- 470 + 10 = 480 tests pass; ruff clean.
