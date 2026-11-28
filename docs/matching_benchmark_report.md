# Cross-session matching — controlled A/B report

## Why a controlled benchmark

Every session has its own VGGT world origin, so real cross-session coordinates
are not comparable and there is no public ground truth for "which mug on day 4
is the mug from day 3". `scripts/matching_bench.py` therefore derives sessions
from the six real scene graphs with a known similarity transform, id renaming,
room-signature dropout, appearance noise, 12–15 % item dropout and novel-item
distractors. Six cross-video pairs are negative cases where nothing should
match. 18 same-home + 6 cross-home scenarios give exact ground truth for
rooms, anchors and instances.

Run: `uv run python scripts/matching_bench.py`

## Adopted generic settings

| Setting | Legacy | Shipped | Reason |
|---|---:|---:|---|
| pair bare rooms | off | **on** | unsigned rooms paired by id order instead of abandoned |
| singleton needs evidence | off | **on** | same anchored place / same room / appearance required |
| carried needs appearance | off | **on** | only when both sides have appearance |
| appearance threshold | 0.35 | **0.25** | fewer cross-home false merges |

Measured (aggregated over 18 same-home + 6 cross-home scenarios):

| | same-home room R | anchor R | instance R | cross-home FP (rooms / anchors / instances) |
|---|---:|---:|---:|---:|
| legacy | 0.556 | 0.639 | 0.811 | 3 / 3 / 16 |
| **shipped** | **1.000** | **0.807** | **0.811** | 3 / 3 / **4** |

Same-home precision remains 1.000 at all three levels; cross-home false
identity merges drop from 16 to 4 with no recall loss.

Settings are wired through `MatchingConfig` (`memory.matching`), `ingest.py`,
the `aegis-memory` CLI and `run_pipeline.py`. All five runtime YAMLs document
them.

## Honest limits and rejected variants

- Cross-home room/anchor false positives remain 3 each: a single unsigned room
  cannot be distinguished from another home's single unsigned room.
- Tightening `appearance_margin` to 0.15/0.20 cut nothing and reduced same-home
  recall (F1 0.606/0.581); rejected. A looser threshold 0.5 raised cross-home
  FPs to 19; rejected.
- A real re-ingestion stress test (demo03 graph replayed three times with
  renamed ids) produced 62 instances with legacy settings and 64 with shipped:
  a two-instance assignment difference between two mugs, not a lost match.
  This is a small regression in that synthetic scenario and is recorded here
  rather than hidden.
- Matching is still symbolic: no 3D distance is used across sessions, and an
  object with no appearance, no anchored place and no shared room becomes new.
- 490 tests pass (480 existing + 10 matching tests); ruff clean.
