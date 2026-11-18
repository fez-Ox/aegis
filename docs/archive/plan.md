> **ARCHIVED — historical snapshot.** Current facts: `CONTEXT.md`; current work: `TODO.md`.

# Aegis — Implementation Plan for Milestone 1, Milestone 2 and §6 Improvements

**Written:** 2026-11-14 against `develop` @ `8183015` (129 tests pass, Ruff clean).
**Covers:** every open item in `context/todo.md` Milestone 1 (§1.4), Milestone 2 (§2.3–§2.8) and §6 (A1–A11, M1–M8, C1–C13).
**Does not cover (Part I):** Milestone 3 and 4 features, except where a §6 item touches them (A9, C9, C13, FR1.3 control).
**Part II** (appended 2026-11-16, after Appendix B) is the implementation plan for Milestone 3, Milestone 4 and §5: work packages WP16–WP35.
**Companion documents:** `context/todo.md` (what), `context/answer.md` (why), this file (how).

This plan makes the design decisions. An implementing agent should not need to redesign anything. Where a number must be measured before it can be trusted, the plan says so and gives the default to ship with.

---

## 0. How to use this plan

### 0.1 Rules for the implementing agent

1. Work one work package (WP) at a time, in the order of §0.4. One branch and one PR per WP, named `feat/wp<NN>-<slug>` off `develop`.
2. Before editing, read every file listed under "Files" for that WP. Line numbers in this plan refer to `8183015` and will drift.
3. After every WP: `uv run pytest` must pass and
   `uvx ruff check src tests run_pipeline.py run_server.py && uvx ruff format --check src tests run_pipeline.py run_server.py` must be clean.
4. Python 3.12, `uv` only (`uv add`, never `pip install`). No new runtime dependency unless this plan names it.
5. Do not tick an item in `context/todo.md` without a passing test, a measured result or a recorded artifact. When a WP lands, tick its todo items and cite the test name or artifact path.
6. Never reintroduce a scale or axis transform on VGGT-Ω coordinates. Derived quantities (up vector, floor offset, unit scale) are stored beside the coordinates.
7. Safe failure over fabrication. If evidence is missing, return `None`, a weaker relation or an explicit "unknown". Never a default location, a default anchor or a default confidence.
8. Where this plan says "rewrite test X", the old assertions encode demo-specific or Z-up behaviour that is being removed on purpose. Do not keep the old behaviour to keep the old test green.
9. Tests must not need a GPU, Modal or network. Use synthetic arrays and `tmp_path`.
10. If something in the code contradicts this plan, stop and report it. Do not guess.

### 0.2 Facts about the current system that every WP relies on

| Fact | Where | Consequence |
|---|---|---|
| World frame = camera frame of the first reconstructed keyframe. OpenCV axes: +X right, +Y down, +Z forward. | `geometry/vggt_runner.py:177-194` | "Up" is only −Y if the phone started level. It usually did not. |
| Poses are `T_world_camera` (camera-to-world), 4×4, in `outputs/geometry/poses.json`. Column 1 of the rotation is the camera's down axis in world coordinates. | `remote/workers.py:258-283` | Camera up in world = `−R[:, 1]`. |
| Pointmaps are `(N, H, W, 3)` float32 world points; confmaps `(N, H, W)`. All keyframes in one `pointmaps.npz`. | `workers.py:238-245` | ≈ 4.3 MB per keyframe, loaded whole. |
| Scale is whatever VGGT-Ω produces. It is close to metric indoors but not calibrated. | report §limitations | Thresholds written as metres are assumptions. |
| `BoundingBox3D.size` is `(x_rot, y_rot, z)` with yaw fitted in world X–Y. | `geometry/lifting.py:139-188` | Wrong in a Y-down frame. Fixed in WP03. |
| Scene graph is rebuilt per dataset. Instance IDs restart at 1. | `memory/scene_graph.py`, `workers.py:87-108` | No multi-session memory. Fixed in WP07. |
| Modal images ship only `.py` files (`add_local_python_source("aegis", copy=True)`). | `remote/modal_app.py` | Data files (YAML) do not reach workers unless they travel inside the config dict. |
| The API reads `r4d_scene_graph.json` from `outputs/<dataset_id>/objects/` on the laptop. Tests read `tests/fixtures/<id>/objects/`. | `remote/api.py:160-182`, `tests/conftest.py` | The laptop is the home hub. The persistent store lives there, not on a Modal volume. |
| Fixtures are schema v1 graphs with a `timeline` key and relations `inside`, `on_surface`, `carried_by_user`, `moving_towards`. | `tests/fixtures/*` | Readers must keep accepting v1. Do not regenerate fixtures. |

### 0.3 Decisions this plan makes

| # (todo §7) | Decision | Status |
|---|---|---|
| 6 | One SQLite file per home, on the laptop: `<store_root>/<home_id>/memory.db`. Standard library `sqlite3`, WAL mode. | Decided here |
| 7 | Compaction runs as an explicit job (`aegis-memory compact`), also called at the end of every ingest. Summaries are template text plus a JSON sidecar. No language model. | Decided here |
| 10 | Gravity from a RANSAC floor-plane fit, validated against the camera path. Phone IMU is a later upgrade. | Decided here |
| 9 | Evidence crops are object-only crops kept as derived evidence, behind `memory.evidence.enabled`. | **Needs supervisor confirmation.** Ship enabled; the flag makes it reversible. |
| 5 | Encryption at rest is Milestone 4. The store opens through one function (`open_store`) so SQLCipher can replace `sqlite3` there. | Deferred, seam prepared |
| — | Cross-session memory is symbolic (room, anchor, relation). Coordinates stay session-local. | Decided here (A3) |
| — | Long recordings are processed as short segments, each an ordinary dataset. Segments meet in the store, not in a stitched point cloud. | Decided here (A5, A10) |
| — | The relation name `on_surface` is kept (it means "on"). New relations: `under`, `above`, `next_to`, `near`, `in_room`. `moving_towards` is no longer produced. | Decided here |
| — | Vocabulary source of truth is `config/vocabulary.yaml`, loaded locally and carried to Modal inside the runtime config. | Decided here (A7) |

### 0.4 Work packages, order and todo coverage

Order matters. Each WP lists what it depends on.

| WP | Title | Depends on | Todo items closed |
|---|---|---|---|
| 01 | Vocabulary ontology | — | A7, C8 (matching half), part of C4 |
| 02 | Gravity frame and scale unit | — | A4, decision #10, C6 |
| 03 | Lifting: oriented boxes, vertical span, support surface | 01, 02 | C2, part of 2.6 |
| 04 | Planar geometry and relation classifier | 02, 03 | C4, 2.6 (vertical relations) |
| 05 | Scene graph rebuild: generic identity, state runs, events, wall-clock | 01–04 | C1, A2 (session half), A8, 2.6 (confidence), 2.5 (events half), 1.4 wall-clock |
| 06 | API correctness and graph lifecycle | 05 | C3, C5, C9, A6, 2.7 (cache, corrupt graph) |
| 07 | Persistent home store and session ingest | 05, 06 | A1, A2, A3, 2.7 (restart, append-only), decision #6 |
| 08 | Per-home room identity | 07 | 2.3 (all), FR3.6, FR3.7, AC-31 |
| 09 | Activity history | 07 | 2.5 |
| 10 | Evidence crops | 05, 07 | A11 |
| 11 | Compaction and tiered retention | 07, 09, 10 | 2.4 (all), FR4, AC-07, AC-08, AC-23 |
| 12 | Live path: JPEG frames, segments, bounded reconstruction | 07 | C12, A5, A10, M3, M5, 1.4 (PNG, micro-batch) |
| 13 | Perception quality and cost | 01, 12 | M1, M2, M4, M6, M7, M8 |
| 14 | Client and cleanup | 06 | A9, C7, C10, C11, C13, 1.4 (FR1.3 in app) |
| 15 | Measurements and recorded evidence | all | 1.4 (AC-01, AC-02, AC-03, AC-29), 2.6 (AC-04), 2.8 (AC-22), §5.2 doc fixes tied to these WPs |

WP01 and WP02 are independent and can run in parallel. WP08–WP10 can run in parallel after WP07.

### 0.5 Target module layout after all WPs

```
config/vocabulary.yaml                      WP01
src/aegis/core/vocabulary.py                WP01
src/aegis/geometry/gravity.py               WP02
src/aegis/geometry/planar.py                WP04
src/aegis/memory/relations.py               WP04
src/aegis/memory/anchors.py                 WP05  (moved out of scene_graph.py)
src/aegis/memory/association.py             WP05
src/aegis/memory/runs.py                    WP05
src/aegis/memory/scene_graph.py             WP05  (dataclasses + orchestration only)
src/aegis/memory/repository.py              WP06  (JSON graph repo; store repo added in WP07)
src/aegis/memory/store.py                   WP07
src/aegis/memory/ingest.py                  WP07
src/aegis/memory/matching.py                WP07  (room, anchor, instance matching; pure functions)
src/aegis/memory/activities.py              WP09
src/aegis/memory/evidence.py                WP10
src/aegis/memory/summaries.py               WP11
src/aegis/memory/compaction.py              WP11
src/aegis/memory/cli.py                     WP07  (`aegis-memory` entry point)
src/aegis/visualization/rerun_scene.py      WP14  (moved out of workers.py)
scripts/…                                   WP11, WP13, WP15
```

---

## WP01 — Vocabulary ontology

**Closes:** A7, C8 (label matching), and the "bed cannot be an anchor" part of C4.
**Why:** roles are decided today by six lists that disagree, and labels are normalised in three places. `window` is prompted but is in no list, so windows are stored as personal objects.

### Files

- New: `config/vocabulary.yaml`, `src/aegis/core/vocabulary.py`, `tests/test_vocabulary.py`
- Edit: `src/aegis/core/config.py`, `config/demo.yaml`, `config/demo03.yaml`, `config/demo04.yaml`, `config/demo06.yaml`, `run_pipeline.py`
- Later WPs remove the old lists: `scene_graph.ANCHOR_CLASS_NAMES`, `_normalise_label`, `_anchor_group_label`; `rooms.ROOM_LANDMARK_ROOM_TYPES`, `normalise_landmark_label`; `lifting.CONTAINER_LABELS` and the size filters; `detector._canonical_label`; `workers._memory_label_key`; `reasoning.ITEM_SYNONYMS`, `PLURAL_ITEMS`; `run_pipeline.COMPREHENSIVE_INDOOR_CLASSES`. In WP01 only add the new module and switch `rooms.py`, `detector.py` and `run_pipeline.py`. The rest switch in the WP that rewrites that file.

### Design

**YAML schema** (`config/vocabulary.yaml`):

```yaml
version: 1
entries:
  - id: shoes                 # canonical id: lower case, single spaces, unique
    display: Shoes            # used in labels: "Shoes #1"
    prompts: [shoes, shoe]    # sent to the detector; each prompt belongs to exactly one entry
    synonyms: [sneaker, sneakers, boots, footwear, slippers]   # accepted in queries only
    role: object              # object | anchor | landmark | hand
    plural: true              # grammar: "are" instead of "is"
    importance: normal        # normal | high   (high = longer hot retention)
    max_extent: 0.85          # largest plausible box dimension, in scale units; null = no check
  - id: bed
    display: Bed
    prompts: [bed]
    role: anchor
    room_type: Bedroom        # this entry also votes for room typing
    container: false          # true = objects can be "inside"
    support_surface: true     # true = objects can rest "on" it; lifting fits a support height
    open_underneath: true     # true = objects can be "under" it
    max_extent: 4.5
```

Field defaults: `synonyms: []`, `plural: false`, `importance: normal`, `max_extent: null`, `room_type: null`, `container: false`, `support_surface: false`, `open_underneath: false`.

**Entries to create.** Keep today's anchor grouping so existing labels (`Storage Cabinet #1`, `Desk #1`, `Kitchen Counter #1`) do not change.

Anchors (role `anchor`):

| id | prompts | container | support_surface | open_underneath | room_type | max_extent |
|---|---|---|---|---|---|---|
| storage cabinet | storage cabinet, cabinet, cupboard, shelf | true | true | false | — | 4.5 |
| refrigerator | refrigerator, fridge | true | false | false | Kitchen | 4.5 |
| kitchen counter | kitchen counter, counter | false | true | false | Kitchen | 4.5 |
| desk | desk, table | false | true | true | — | 4.5 |
| dining table | dining table | false | true | true | Dining Room | 4.5 |
| coffee table | coffee table | false | true | true | Living Room | 4.5 |
| drawer | drawer | true | false | false | — | 4.5 |
| sink | sink | true | false | false | — | 4.5 |
| podium | podium, lectern, rostrum, stand | false | true | false | — | 4.5 |
| bed | bed | false | true | true | Bedroom | 4.5 |
| sofa | sofa, couch | false | true | false | Living Room | 4.5 |
| chair | chair | false | true | true | — | 4.5 |
| wardrobe | wardrobe | true | false | false | Bedroom | 4.5 |
| nightstand | nightstand | false | true | false | Bedroom | 4.5 |
| stove | stove, oven | false | true | false | Kitchen | 4.5 |
| kitchen island | kitchen island | false | true | false | Kitchen | 4.5 |

Landmarks (role `landmark`; room evidence only, never an anchor, never an object):

| id | prompts | room_type |
|---|---|---|
| door | door, front door | Entryway |
| stairs | stairs, staircase | Stairway |
| television | television, tv | Living Room |
| toilet | toilet | Bathroom |
| bathtub | bathtub | Bathroom |
| shower | shower | Bathroom |
| bathroom sink | bathroom sink | Bathroom |
| window | window | — |

Hand (role `hand`): id `hand`, prompts `hand, human hand, hands`.

Objects (role `object`). `max_extent: 0.85` for every entry marked †. Take synonyms from `reasoning.ITEM_SYNONYMS` and prompts from `run_pipeline.COMPREHENSIVE_INDOOR_CLASSES`, with these corrections: `cup` and `mug` are their own entry (`mug`), not synonyms of `bottle`; `bag`, `handbag`, `purse` are split from `backpack`.

| id | prompts | synonyms | plural | importance |
|---|---|---|---|---|
| shoes † | shoes, shoe | sneaker, sneakers, boots, footwear, slippers | true | normal |
| bottle † | bottle, water bottle, plastic bottle | flask, tumbler | false | normal |
| mug † | mug, cup | drink | false | normal |
| keys | keys, keychain | key, car key, house key | true | high |
| glasses | glasses, reading glasses, sunglasses | spectacles, specs, eyewear | true | high |
| cell phone | cell phone, phone | mobile phone, smartphone, mobile | false | high |
| wallet | wallet | billfold | false | high |
| purse | purse, handbag | bag | false | high |
| backpack | backpack | rucksack, pack | false | normal |
| medicine | medicine, pill bottle | pills, meds, prescription, vitamins, medication, tablets | false | high |
| remote control | remote control | remote, tv remote | false | normal |
| hearing aid | hearing aid | hearing aids | false | high |
| walking stick | walking stick | cane | false | high |
| watch | watch | wristwatch | false | normal |
| charger | charger | phone charger | false | normal |
| laptop | laptop | computer, notebook | false | normal |
| book | book | books, novel, magazine | false | normal |
| cooking pot † | cooking pot, pot, pan | pots, pans, saucepan, cookware | false | normal |
| bowl † | bowl | bowls, basin | false | normal |
| plate † | plate, dish | plates, dishes | false | normal |
| cutlery | fork, spoon, knife | cutlery | false | normal |
| food | food | leftover, leftovers, meal, snack, groceries | false | normal |
| food container † | food container, container | lunch box, tupperware | false | normal |
| clothes | clothes, shirt, pants | clothing, laundry, garment, garments | true | normal |
| towel | towel | towels | false | normal |
| trash bin | trash bin, wastebasket | bin, dustbin | false | normal |
| garbage bag | garbage bag | trash bag, bin bag | false | normal |
| rubbish | rubbish | trash, garbage, waste | false | normal |
| basket † | basket | — | false | normal |
| box | box | carton | false | normal |

**Module** (`src/aegis/core/vocabulary.py`):

```python
ROLES = ("object", "anchor", "landmark", "hand")

def normalise_label(label: str) -> str:
    """Lower-case, replace '_' with ' ', collapse whitespace, strip."""

@dataclass(frozen=True, slots=True)
class VocabEntry:
    id: str
    display: str
    prompts: tuple[str, ...]
    synonyms: tuple[str, ...] = ()
    role: str = "object"
    plural: bool = False
    importance: str = "normal"
    max_extent: float | None = None
    room_type: str | None = None
    container: bool = False
    support_surface: bool = False
    open_underneath: bool = False
    known: bool = True            # False for labels not in the file

class Vocabulary:
    def __init__(self, entries: Sequence[VocabEntry]) -> None: ...   # validates, builds lookup tables
    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> Vocabulary: ...  # the parsed YAML or the serialised form
    @classmethod
    def load(cls, path: str | Path) -> Vocabulary: ...
    def to_mapping(self) -> dict[str, Any]: ...                       # round-trips through from_mapping
    def entry(self, label: str) -> VocabEntry: ...                    # never raises; see "unknown labels"
    def canonical(self, label: str) -> str: ...                       # entry(label).id
    def role(self, label: str) -> str: ...
    def display(self, label: str) -> str: ...
    def detector_prompts(self) -> tuple[str, ...]: ...                # all prompts, file order, no duplicates
    def room_type(self, label: str) -> str | None: ...
    def resolve_query(self, text: str) -> VocabEntry | None: ...      # see below
    def entries(self) -> tuple[VocabEntry, ...]: ...

def default_vocabulary() -> Vocabulary: ...
```

Rules:

- **Validation in `__init__`** (raise `ValueError` naming the offending entry): `id` unique and equal to `normalise_label(id)`; `role` in `ROLES`; `importance` in `{"normal", "high"}`; every prompt and synonym already normalised; a prompt appears in exactly one entry; a synonym may not equal a prompt or id of a different entry; `container`, `support_surface`, `open_underneath` only on role `anchor`; `max_extent` positive or `None`; `prompts` non-empty.
- **Label lookup** (`entry`): normalise, then exact match against ids, then prompts. No substring matching. If nothing matches, return `VocabEntry(id=normalised, display=normalised.title(), prompts=(normalised,), role="object", known=False)`. This keeps open-vocabulary runs (`--classes`) working. Log one warning per unknown label per process.
- **Query lookup** (`resolve_query`): normalise the text; build candidate phrases = ids ∪ prompts ∪ synonyms of entries whose role is `object`; return the entry whose phrase matches on word boundaries (`\b…\b`) with the **longest** phrase. Also try a trailing-`s`-stripped and a `+s` variant of each word of the text. Return `None` when nothing matches. No substring-in-word matches (`"cup"` must not match `"cupboard"`).
- **`default_vocabulary()`**: `functools.lru_cache`. Path = env `AEGIS_VOCABULARY_FILE` if set, else `Path(__file__).resolve().parents[3] / "config" / "vocabulary.yaml"`. If the file does not exist raise `FileNotFoundError` with a message saying workers must pass the vocabulary explicitly. Never fall back to a built-in list.

**Config integration** (`core/config.py`):

- `RuntimeConfig` gets `vocabulary: Mapping[str, Any]` (the `to_mapping()` form; default = empty mapping) and a helper method `def vocab(self) -> Vocabulary` that returns `Vocabulary.from_mapping(self.vocabulary)` if non-empty, else `default_vocabulary()`.
- `load_config(path)`: after reading the YAML, read optional top-level key `vocabulary_file` (default `"vocabulary.yaml"`), resolve it relative to the config file's directory, load it, and place `to_mapping()` under `raw["vocabulary"]` before calling `from_mapping`. `config_to_dict` then carries it to Modal automatically (`asdict` handles nested dicts).
- `RuntimeConfig.from_mapping`: if `perception.target_classes` is absent, set it to `vocab.detector_prompts()`. If present (demo configs), keep it as is.
- `config/demo.yaml`: delete the hand-written `perception.target_classes` block so it derives from the vocabulary. `demo03.yaml`, `demo04.yaml`, `demo06.yaml` keep their task-scoped lists.
- `run_pipeline.py`: delete `COMPREHENSIVE_INDOOR_CLASSES` and the merge branch at lines 252-261. `--classes` still overrides.

**Switch `rooms.py` now:** replace `ROOM_LANDMARK_ROOM_TYPES` and `normalise_landmark_label` with vocabulary calls. `is_room_landmark_label(label, vocabulary=None)` returns `vocabulary.role(label) == "landmark"`. Room-type votes come from any entry with a `room_type`, whether its role is `landmark` or `anchor`. `extract_room_regions` gets a keyword `vocabulary: Vocabulary | None = None` (`None` → `default_vocabulary()`). Evidence labels use `entry.display`.

**Switch `detector.py` now:** `_canonical_label` is deleted; `detect_and_track_objects` gets keyword `vocabulary: Vocabulary`; label = `vocabulary.canonical(raw_label)`; `is_hand = vocabulary.role(label) == "hand"`. `workers.run_detect_and_lift` passes `config.vocab()`.

### Tests (`tests/test_vocabulary.py`)

- `test_file_loads_and_every_prompt_maps_to_one_entry`
- `test_roles_partition_labels` — `bed` is `anchor` with `room_type == "Bedroom"`; `window` and `door` are `landmark`; `hand` is `hand`.
- `test_unknown_label_is_object_and_marked_unknown`
- `test_resolve_query_longest_match` — `"where is my water bottle"` → `bottle`; `"my mug"` → `mug`; `"cupboard"` → `None`; `"reading glasses"` → `glasses`; `"sneakers"` → `shoes`.
- `test_validation_rejects_duplicate_prompt`, `test_validation_rejects_anchor_flags_on_object`
- `test_round_trip_to_mapping`
- `test_config_carries_vocabulary` — `config_to_dict(load_config("config/demo.yaml"))["vocabulary"]` rebuilds an equal vocabulary; `perception.target_classes` equals `detector_prompts()`.
- Update `tests/test_rooms.py::test_room_landmark_label_gate`: `bed` and `sofa` are no longer landmarks (they are anchors that vote); `door`, `television`, `window` are.

### Done when

All tests pass; `grep -rn "COMPREHENSIVE_INDOOR_CLASSES\|ROOM_LANDMARK_ROOM_TYPES\|_canonical_label" src run_pipeline.py` returns nothing.

---

## WP02 — Gravity frame and scale unit

**Closes:** A4, decision #10, C6.
**Why:** every vertical statement ("above", "under", "on the floor") and every floor-plane computation needs the real up direction. Today it is assumed.

### Files

- New: `src/aegis/geometry/gravity.py`, `tests/test_gravity.py`
- Edit: `src/aegis/core/paths.py` (add `gravity: Path = geometry / "gravity.json"` to `DatasetPaths`), `src/aegis/core/config.py` (new `GravityConfig`), `src/aegis/remote/workers.py` (`run_vggt` writes `gravity.json`; `_clear_downstream_artifacts` removes it), `src/aegis/geometry/vggt_runner.py` (C6), `config/demo.yaml`

### Design

```python
@dataclass(frozen=True, slots=True)
class GravityFrame:
    up: tuple[float, float, float]        # unit vector, world coords, points away from the floor
    floor_offset: float | None            # dot(p, up) for points on the floor; None if unknown
    source: str                           # "floor_plane" | "camera_prior" | "assumed"
    confidence: float                     # 0..1
    inlier_ratio: float = 0.0
    camera_height: float | None = None    # median dot(c, up) - floor_offset over camera positions

    @classmethod
    def assumed(cls) -> GravityFrame      # up=(0,-1,0), floor_offset=None, source="assumed", confidence=0.0
    def basis(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]   # (e1, e2, up), right-handed, e1 x e2 = up
    def elevation(self, p) -> float       # dot(p, up); always defined
    def height(self, p) -> float | None   # elevation - floor_offset; None when floor_offset is None
    def horizontal(self, p) -> tuple[float, float]   # (dot(p, e1), dot(p, e2))
    def from_horizontal(self, h1: float, h2: float, elevation: float) -> np.ndarray   # h1*e1 + h2*e2 + elevation*up
    def unit(self, assumed_camera_height: float, min_confidence: float) -> float
    def is_reliable(self, min_confidence: float) -> bool   # source == "floor_plane" and confidence >= min_confidence
    def as_dict(self) -> dict[str, Any]
    @classmethod
    def from_dict(cls, raw: Mapping[str, Any] | None) -> GravityFrame   # None or {} -> assumed()
```

**Basis (must be exactly this, other code depends on it):**

```
x = (1, 0, 0)
e1 = x - dot(x, up) * up
if |e1| < 0.1:  z = (0, 0, 1);  e1 = z - dot(z, up) * up
e1 = e1 / |e1|
e2 = cross(up, e1)
```

For the assumed frame `up = (0, −1, 0)` this gives `e1 = (1, 0, 0)`, `e2 = (0, 0, 1)`, so `horizontal(p) == (x, z)`. That is exactly what `rooms.py` uses today, so legacy behaviour is unchanged when gravity is unknown. Check: `cross(e1, e2) == up`.

**`unit()`:** scale factor that turns "metre-like" thresholds into world units.
`unit = clamp(camera_height / assumed_camera_height, 0.5, 2.0)` when `is_reliable(min_confidence)` and `camera_height` is not `None`; otherwise `1.0`. Default `assumed_camera_height = 1.4`.

**Estimator:**

```python
def estimate_gravity(
    points: np.ndarray,                 # (N, 3) fused cloud, world coords
    camera_positions: np.ndarray,       # (K, 3)
    camera_rotations: np.ndarray | None = None,   # (K, 3, 3) world_from_camera
    *,
    iterations: int = 500,
    seed: int = 0,
    max_candidates: int = 20000,
    inlier_fraction_of_scale: float = 0.02,
    max_tilt_degrees: float = 60.0,
    max_below_fraction: float = 0.10,
    min_inliers: int = 200,
    min_inlier_ratio: float = 0.08,
    path_disagreement_degrees: float = 25.0,
) -> GravityFrame
```

Algorithm. Use `np.random.default_rng(seed)` so results are reproducible.

1. Drop non-finite points. If fewer than 50 points or no camera positions → return `GravityFrame.assumed()`.
2. **Prior up `u0`.** If rotations are given: `u0 = normalise(mean over k of −R_k[:, 1])`. If the mean has norm < 1e-6 or no rotations: `u0 = (0, −1, 0)`.
3. **Scene scale.** `c_med = median(camera_positions, axis=0)`. `scale = median(|points − c_med|)`. `tau = inlier_fraction_of_scale * scale`. If `scale <= 0` → assumed.
4. **Candidates.** Points with `dot(p − c_med, u0) < 0` (below the median camera). Subsample without replacement to `max_candidates`. If fewer than `min_inliers` candidates → go to step 9.
5. **RANSAC.** For each iteration: pick 3 distinct candidates; `n = cross(p1 − p0, p2 − p0)`; skip if `|n| < 1e-12`; normalise; flip so `dot(n, u0) > 0`; skip if `dot(n, u0) < cos(max_tilt_degrees)`. Signed distances `d = (candidates − p0) @ n`. `inliers = |d| < tau`. `below = d < −3 * tau`. Skip the plane if `below.mean() > max_below_fraction` (this rejects table tops, which have floor beneath them). Keep the plane with the most inliers.
6. If no plane survived, or inliers < `min_inliers`, or `inlier_ratio = inliers / len(candidates) < min_inlier_ratio` → go to step 9.
7. **Refine.** Least squares on the inlier points: subtract their mean, SVD, normal = last right-singular vector, flip so `dot(n, u0) > 0`. `floor_offset = mean(inlier_points @ n)`. Recompute the inlier ratio with the refined plane.
8. **Validate.** `heights = camera_positions @ n − floor_offset`. If `(heights > 0).mean() < 0.95` → go to step 9. `camera_height = median(heights)`.
   Camera-path cross-check, only when `K >= 10`: centre the camera positions, SVD, singular values `s1 ≥ s2 ≥ s3`; if `s2 > 0` and `s3 / s2 < 0.3`, take `m` = third right-singular vector flipped so `dot(m, u0) > 0`; `agree = angle(n, m) <= path_disagreement_degrees`. If the check is not applicable, `agree = True`.
   `confidence = min(1.0, inlier_ratio / 0.30) * (1.0 if agree else 0.5)`.
   Return `GravityFrame(up=n, floor_offset, source="floor_plane", confidence, inlier_ratio, camera_height)`.
9. **Fallback.** `up = u0`. `floor_offset = 2nd percentile of (points @ u0)`. `camera_height = median(camera_positions @ u0) − floor_offset`. `source = "camera_prior"`, `confidence = 0.2`, `inlier_ratio = 0.0`.

**Config** (`GravityConfig`, under `memory.gravity` in YAML):

```yaml
memory:
  gravity:
    enabled: true
    min_confidence: 0.5          # below this, vertical relations are not asserted
    assumed_camera_height: 1.4   # scale units; chest-held phone
    ransac_iterations: 500
```

Validate: `0 < min_confidence <= 1`, `assumed_camera_height > 0`, `ransac_iterations >= 50`.

**Worker** (`run_vggt`): after the point cloud and poses are computed, call `estimate_gravity(rec_result["global_points"], poses[:, :3, 3], poses[:, :3, :3], iterations=config.memory.gravity.ransac_iterations)` unless `gravity.enabled` is false (then `GravityFrame.assumed()`). Write `paths.gravity` as `{"schema_version": 1, "dataset_id": …, **gravity.as_dict()}`. Add `gravity_source`, `gravity_confidence`, `camera_height` to the stage result so they land in `benchmark_stats.json`.

**C6 — synthetic reconstruction.** In `vggt_runner.py` the `except Exception` branch at lines 196-239 fabricates poses and depth on CPU. Change it so the synthetic path runs only when env `AEGIS_ALLOW_SYNTHETIC_VGGT == "1"`. Otherwise re-raise as `RuntimeError("VGGT-Ω reconstruction failed: …")` on any device. Mark synthetic output: add `"synthetic": True` to the returned dict; `run_vggt` writes `"source": "synthetic"` into `poses.json` and the stage result. Grep the tests for any that depend on the fallback and set the env var in those tests with `monkeypatch.setenv`.

### Tests (`tests/test_gravity.py`)

Build synthetic scenes with a helper `make_room(tilt_deg, seed)`: a floor grid of 4,000 points at height 0 over a 4 × 4 area, a table top of 600 points at height 0.75 over 1 × 1, two walls of 1,500 points each, Gaussian noise σ = 0.005, cameras on a 10-point walking path at height 1.4 ± 0.03, all rotated by `R_x(tilt_deg)` about the world X axis so the first camera is pitched. Camera rotations = the same `R_x` (so `−R[:,1]` is the true up).

- `test_recovers_up_for_level_camera` — tilt 0: angle(up, true up) < 2°, `source == "floor_plane"`, `confidence >= 0.5`, `|camera_height − 1.4| < 0.05`.
- `test_recovers_up_for_pitched_camera` — tilt 40°: same assertions.
- `test_table_top_is_not_chosen_as_floor` — floor_offset matches the floor, not the table.
- `test_no_floor_falls_back_with_low_confidence` — walls only: `source == "camera_prior"`, `confidence < 0.5`.
- `test_empty_input_returns_assumed`
- `test_basis_for_assumed_frame_is_x_and_z` — `horizontal((1, 2, 3)) == (1.0, 3.0)`; `cross(e1, e2) == up`.
- `test_unit_scaling_and_clamp`
- `test_round_trip_dict`
- `test_deterministic_for_fixed_seed`
- In `tests/test_geometry.py` or a new test: `test_vggt_fallback_requires_opt_in` (no env → `RuntimeError`).

### Done when

Tests pass and `run_vggt` writes `gravity.json`. Nothing consumes it yet.

---

## WP03 — Lifting: oriented boxes, vertical span, support surface

**Closes:** C2 and the geometric half of todo 2.6.
**Depends on:** WP01, WP02.

### Files

- Edit: `src/aegis/core/models.py`, `src/aegis/geometry/lifting.py`, `src/aegis/geometry/transforms.py`, `src/aegis/remote/workers.py`, `tests/test_lifting.py`

### Design

**`BoundingBox3D` gains fields** (all optional, default `None`; add to `as_dict` only when not `None`):

```python
up_min: float | None = None       # elevation (dot with up) of the box bottom
up_max: float | None = None       # elevation of the box top
support_up: float | None = None   # elevation of the fitted support surface, anchors only
point_count: int | None = None    # points used for the fit
```

**New meaning of existing fields** (document in the dataclass docstring and in `docs/artifact_contracts.md`):

- `size = (length, width, height)`: `length` along the box's major horizontal axis `a`, `width` along `b`, `height` along `up`.
- `yaw`: angle of axis `a` in the gravity basis, measured from `e1` toward `e2`, in `(−π/2, π/2]`.
- `rotation`: quaternion `(x, y, z, w)` of the rotation matrix whose columns are `[a, b, up]` in world coordinates. This is `world_from_box`, which is what Rerun `Boxes3D` expects with half-sizes `size / 2`.
- `center`: world point at the middle of the three extents, so `center ± size/2` along `(a, b, up)` are the fitted bounds.

`detected_objects_3d.json` `schema_version` becomes `2`.

**`transforms.py`:** add `quaternion_from_matrix(m: np.ndarray) -> tuple[float, float, float, float]` (xyzw, Shepperd's method, result normalised with `w >= 0`) if no equivalent exists. Test vector: columns `[(1,0,0), (0,0,1), (0,−1,0)]` → `(0.70710678, 0, 0, 0.70710678)`.

**`lift_detection_to_3d` signature additions:** `gravity: GravityFrame | None = None`, `vocabulary: Vocabulary | None = None`. `None` gravity → `GravityFrame.assumed()`. `None` vocabulary → `default_vocabulary()`.

Replace lines 139-239 with:

1. `e1, e2, up = gravity.basis()`. `h1 = pts @ e1`, `h2 = pts @ e2`, `v = pts @ up` (on the inlier points).
2. Yaw: if at least 5 points and the 2×2 covariance of `(h1, h2)` is finite, take the eigenvector of the largest eigenvalue `(vx, vy)`; if `vx < 0` or (`vx == 0` and `vy < 0`) negate it; `yaw = atan2(vy, vx)`. Otherwise `yaw = 0.0`.
3. `a_c = h1*cos(yaw) + h2*sin(yaw)`, `b_c = −h1*sin(yaw) + h2*cos(yaw)`.
4. For each of `a_c`, `b_c`, `v`: `lo, hi = quantile(lower_quantile), quantile(upper_quantile)`; `extent = max(hi − lo, min_extent)`; `mid = (lo + hi) / 2`. `min_extent = 0.05 * unit` where `unit` is a new keyword argument `unit: float = 1.0`.
5. `a_axis = cos(yaw)*e1 + sin(yaw)*e2`, `b_axis = −sin(yaw)*e1 + cos(yaw)*e2`. `center = mid_a*a_axis + mid_b*b_axis + mid_v*up`. `rotation = quaternion_from_matrix(np.column_stack([a_axis, b_axis, up]))`.
6. `up_min = lo_v`, `up_max = hi_v`, `point_count = len(inlier_pts)`.
7. **Support surface.** If `vocabulary.entry(label).support_surface` and `point_count >= 50`: histogram `v` restricted to the upper half of `[lo_v, hi_v]` with bin width `max(0.05 * (hi_v − lo_v), 1e-6)`; take the bin with the most points; `support_up = median(v in that bin)`. Otherwise `support_up = None`.
8. **Plausibility filter** replaces the two hard-coded class tuples: `limit = vocabulary.entry(label).max_extent`; if `limit is not None` and `max(size) > limit * unit` → return `None`. Remove the volume checks.
9. Remove the `try/except` fallback that produced an axis-aligned box. The new code has no branch that can raise for finite input; let unexpected errors surface.

The outlier rejection at lines 130-137 stays, with the absolute floor `0.08` replaced by `0.08 * unit`.

**`evaluate_spatial_containment_and_states`:** relations are no longer decided here (WP04/WP05 own them).

- Signature adds `vocabulary: Vocabulary | None = None`, `unit: float = 1.0`.
- Smoothing: keep `_smooth_track_boxes` but use it only to compute velocities. The returned boxes keep their **raw** `center`, `size`, `rotation`, `up_min`, `up_max`. Do not smooth sizes at all (axes `a` and `b` can swap between frames).
- Delete the axis-aligned containment block (lines 380-396) and `CONTAINER_LABELS`, `_is_container_label`. `container_relation` is always `None` from now on (the field stays for JSON compatibility).
- Structure test uses the vocabulary: `role in {"anchor", "landmark"}` → `spatial_state = "static_structure"`; `role == "hand"` → `"hand"`.
- Hand proximity: `dist_to_hand <= hand_distance * unit`, with `hand_distance` a new keyword (default `0.35`) fed from `config.perception.hand_contact_max_distance`.
- Resulting `spatial_state` values: `static_structure`, `hand`, `in_hand`, `in_motion`, `on_surface` (meaning "static object"; kept as the legacy default string).
- Every `BoundingBox3D(...)` reconstruction in this file must copy the four new fields. Prefer `dataclasses.replace(box, spatial_state=…, …)` over rebuilding by hand.

**Worker** (`run_detect_and_lift`): load `GravityFrame.from_dict(_read_json(paths.gravity))` if the file exists, else assumed. Compute `unit = gravity.unit(cfg.assumed_camera_height, cfg.min_confidence)`. Pass `gravity`, `vocabulary=config.vocab()`, `unit` to lifting and to the state evaluation.

### Tests (`tests/test_lifting.py`)

- Rewrite `test_lift_detection_oriented_bounding_box`: the diagonal now lies in world **(x, z)** with constant `y`. Assert `abs(yaw) ≈ π/4` (atol 0.15), `size[2]` (height) equals the minimum extent, `size[0] > size[1]`.
- New `test_obb_height_is_along_up_for_tilted_gravity`: a box-shaped point set 1.0 × 0.5 × 0.2 (length × width × height), rotated by `R_x(40°)`; pass `GravityFrame(up=R_x(40°) @ (0,−1,0), floor_offset=…, source="floor_plane", confidence=1.0)`. Assert `size ≈ (1.0, 0.5, 0.2)` within 10 %, `up_max − up_min ≈ 0.2`.
- New `test_rotation_quaternion_matches_axes`: rotate local unit vectors by the quaternion and compare with `a`, `b`, `up`.
- New `test_support_surface_of_table`: 2,000 points on a top at elevation 0.75, 400 points on four legs from 0 to 0.75; label `desk`. Assert `support_up ≈ 0.75` (atol 0.03). Same points with label `shoes` → `support_up is None`.
- New `test_max_extent_filter_uses_vocabulary`.
- Rewrite `test_evaluate_spatial_containment_and_states`: cabinet → `static_structure`; static shoes → `on_surface`, `container_relation is None`; moving shoes → `in_motion`. Assert returned centres equal the input centres (no smoothing leak).
- Existing centre assertions (`test_lift_detection_to_3d_basic` and the mask test) should still hold because the data are symmetric. If one fails, the cause is the median → midpoint change; verify by hand before editing the expected value.

### Done when

Tests pass. Record in the PR one Rerun screenshot of `demo01` showing boxes aligned with the furniture (they were visibly rolled before).

---

## WP04 — Planar geometry and relation classifier

**Closes:** C4 and the "vertical relations" item of todo 2.6.
**Depends on:** WP02, WP03.

### Files

- New: `src/aegis/geometry/planar.py`, `src/aegis/memory/relations.py`, `tests/test_planar.py`, `tests/test_relations.py`
- Edit: `src/aegis/memory/rooms.py` (use `planar.py` and the gravity frame)

### `geometry/planar.py`

Pure functions on 2D points (`tuple[float, float]`), polygons as counter-clockwise lists:

```python
def convex_hull(points) -> list[Point]                      # move from rooms.convex_hull_2d; keep a re-export there
def polygon_area(polygon) -> float                          # shoelace, absolute value
def point_in_convex(point, polygon, eps=1e-9) -> bool       # move from rooms._point_in_footprint
def clip_convex(subject, clip) -> list[Point]               # Sutherland–Hodgman; both convex, CCW
def overlap_fraction(subject, clip) -> float                # area(clip_convex) / area(subject); 0.0 if area(subject) == 0
def distance_point_to_polygon(point, polygon) -> float      # 0.0 if inside; else min distance to an edge segment
def oriented_rectangle(center, length, width, yaw) -> list[Point]   # 4 corners, CCW
```

Degenerate polygons (fewer than 3 points): `polygon_area = 0`, `point_in_convex = False`, `distance_point_to_polygon` = distance to the point or segment.

### `memory/relations.py`

```python
RELATIONS = ("inside", "on_surface", "under", "above", "next_to", "on_floor",
             "near", "in_room", "carried_by_user")
PLACED_RELATIONS = frozenset({"inside", "on_surface", "under", "above", "next_to", "on_floor", "near", "in_room"})

@dataclass(frozen=True, slots=True)
class Footprint3D:
    polygon: tuple[tuple[float, float], ...]   # horizontal coords, CCW
    up_min: float
    up_max: float
    support_up: float | None = None

@dataclass(frozen=True, slots=True)
class AnchorShape:
    anchor_id: int
    footprint: Footprint3D
    container: bool
    support_surface: bool
    open_underneath: bool

@dataclass(frozen=True, slots=True)
class RelationResult:
    relation: str
    anchor_id: int | None
    certain: bool
    overlap: float
    gap: float

def box_footprint(box: BoundingBox3D, gravity: GravityFrame) -> Footprint3D
def classify_relation(obj: Footprint3D, anchors: Sequence[AnchorShape], gravity: GravityFrame, *,
                      min_gravity_confidence: float = 0.5, vertical_tolerance: float = 0.15,
                      overlap_threshold: float = 0.5, floor_tolerance_fraction: float = 0.06) -> RelationResult
```

`box_footprint`: centre `(h1, h2) = gravity.horizontal(box.center)`; polygon = `oriented_rectangle(centre, size[0], size[1], yaw or 0.0)`. `up_min`/`up_max` from the box if present; if `None` (legacy box) use `elevation(center) ∓ size[2]/2`.

**`classify_relation` — exact rules.**

Definitions: `H = max(obj.up_max − obj.up_min, 1e-6)`; `oc = (obj.up_min + obj.up_max) / 2`; `centre = centroid of obj.polygon`.
`reliable = gravity.is_reliable(min_gravity_confidence)`.
`on_floor_obj = reliable and gravity.floor_offset is not None and (obj.up_min − gravity.floor_offset) <= floor_tol`, where `floor_tol = floor_tolerance_fraction * gravity.camera_height` if `camera_height` is known, else `0.5 * H`.

For each anchor `a` compute `ov = overlap_fraction(obj.polygon, a.polygon)`, `gap = distance_point_to_polygon(centre, a.polygon)`, `span = max(a.up_max − a.up_min, 1e-6)`, `tol = vertical_tolerance * max(span, H)`, `s = a.support_up if a.support_up is not None else a.up_max`, `reach = 0.5 * sqrt(polygon_area(a.polygon))`.

If `ov >= overlap_threshold`, evaluate in this order and take the first that matches:

| Order | Condition | Relation | certain |
|---|---|---|---|
| 1 | `obj.up_min > a.up_max + tol` | `above` | True |
| 2 | `a.container` and `oc > a.up_max` | `on_surface` (resting on top of the container) | True |
| 3 | `a.container` and `a.up_min − tol <= oc <= a.up_max` | `inside` | True |
| 4 | `a.container` (object below the container) | `near` | False |
| 5 | `abs(obj.up_min − s) <= tol` | `on_surface` | True |
| 6 | `obj.up_min > s + tol` (above the surface but not above the whole anchor, for example against a headboard) | `on_surface` | False |
| 7 | `a.open_underneath` and `obj.up_max <= s − tol` | `under` | True |
| 8 | otherwise (object straddles the surface, or the anchor has no space beneath) | `near` | False |

If `ov < overlap_threshold` and `gap <= reach`: `on_floor` when `on_floor_obj`, else `next_to`; `certain = True`.
Otherwise the anchor is not a candidate.

Choose among candidates by priority, then larger `ov`, then smaller `gap`:
`inside` 6, `on_surface` (certain) 6, `under` 5, `on_floor` 4, `next_to` 3, `above` 2, `on_surface` (uncertain) 2, `near` 1.

If there is no candidate:
- `on_floor_obj` → `on_floor`, with `anchor_id` = nearest anchor if its `gap <= 3 * reach`, else `None`; `certain = True`.
- else nearest anchor by `gap`: if `gap <= 3 * reach` → `near`, `certain = False`; otherwise `in_room`, `anchor_id = None`, `certain = True`.
- no anchors at all → `on_floor` if `on_floor_obj` else `in_room`, `anchor_id = None`.

Last step, when `not reliable`: map `under`, `above`, `on_floor` → `near` with `certain = False` (keep the anchor; if the anchor is `None`, return `in_room`). `inside`, `on_surface`, `next_to` are kept but `certain` becomes `False`.

### `rooms.py` changes

Every horizontal computation goes through the gravity frame. Add keyword `gravity: GravityFrame | None = None` (`None` → assumed) to `extract_room_regions`, `room_for_point`, `implicit_room_from_anchors`.

- `_horizontal_distance(a, b, gravity)` = Euclidean distance between `gravity.horizontal(a)` and `gravity.horizontal(b)`.
- Footprint 3D points: `gravity.from_horizontal(h1, h2, e_med)` with `e_med = median(elevation(position))` over the zone. For the assumed frame this reproduces today's `(x, median_y, z)`.
- `room_for_point` projects the stored 3D footprint back with `gravity.horizontal`.
- Add keyword `unit: float = 1.0`; `zone_link_radius` and the `max(zone_link_radius, 2.0)` landmark radius are multiplied by `unit`; the `implicit_room_from_anchors` margin `1.0` likewise.
- Delete `_HORIZONTAL_AXES`.

All nine existing room tests must pass unchanged with the default (assumed) frame.

### Tests

`tests/test_planar.py`: hull of a square with an interior point; area of a unit square; clip of two overlapping unit squares offset by (0.5, 0) has area 0.5; `overlap_fraction` of a contained square is 1.0 and of a disjoint one is 0.0; distance from (2, 0.5) to the unit square is 1.0; `oriented_rectangle` at yaw π/2 swaps the extents.

`tests/test_relations.py` — fixture: gravity `up=(0,−1,0)`, `floor_offset=−1.4`, `source="floor_plane"`, `confidence=1.0`, `camera_height=1.4` (so `height(p) = 1.4 − y`). Bed: footprint x ∈ [−1, 1], z ∈ [2, 4]; elevation from −1.4 (floor) to −0.8 (headboard top), `support_up = −0.9` (mattress, 0.5 above the floor); flags `support_surface=True, open_underneath=True`. Shoes: 0.3 × 0.2 footprint, 0.1 tall.

- `test_shoes_on_bed` — shoes elevation −0.9…−0.8 over the bed → `on_surface`.
- `test_shoes_under_bed` — shoes elevation −1.4…−1.3 over the bed → `under`.
- `test_shoes_on_floor_beside_bed` — same elevation, centre at x = 1.3 → `on_floor`, anchor = bed.
- `test_object_next_to_anchor_not_on_floor` — elevation −0.9, x = 1.3 → `next_to`.
- `test_inside_container` and `test_on_top_of_container` — a cabinet 1 × 0.5 footprint, 1.8 tall, `container=True`.
- `test_above_anchor` — object 0.5 above the bed's top → `above`.
- `test_far_from_everything_is_in_room`
- `test_low_gravity_confidence_never_asserts_under_or_floor` — confidence 0.2: the under-bed case returns `near`, `certain=False`.
- `test_pitched_frame_gives_same_answers` — rotate every input by `R_x(40°)` and pass the rotated gravity; all of the above results are unchanged. This is the test for the elevation problem.
- `test_no_anchors`

### Done when

Tests pass. The classifier is not wired into the builder yet.

---

## WP05 — Scene graph rebuild

**Closes:** C1, A2 (per-session half), A8, the confidence and vertical items of 2.6, the event half of 2.5, the wall-clock item of 1.4.
**Depends on:** WP01–WP04.

This is the largest WP. Split `scene_graph.py` (901 lines) into the modules below and delete every demo-specific rule: the shoe X-thresholds (`:289-297`), the frame-range gates 280/300/480 (`:621-641`, `:669-681`, `:795-812`), the fabricated `Storage Cabinet #1` (`:193-202`), the fabricated grasp offset `[0.0, 0.45, −0.25]` (`:652`, `:820`), and the event defaults `"Floor Entrance"`, `"Storage Cabinet #1"`, `"Carrier"` (`:437-443`).

### Files

- New: `src/aegis/memory/anchors.py`, `association.py`, `runs.py`
- Rewrite: `src/aegis/memory/scene_graph.py`
- Edit: `src/aegis/core/config.py` (`MemoryBuildConfig`), `src/aegis/remote/workers.py`, `tests/test_scene_graph.py`
- New tests: `tests/test_anchors.py`, `tests/test_association.py`, `tests/test_runs.py`

### Settings

```python
@dataclass(frozen=True, slots=True)
class MemoryBuildSettings:
    anchor_cluster_radius: float = 0.40        # x unit
    association_radius: float = 0.45           # x unit
    appearance_threshold: float = 0.35
    min_observations: int = 2                  # an instance is confirmed after this many observations
    min_run_observations: int = 2              # debounce for state changes
    trailing_single_confidence: float = 0.5    # a final single observation may commit a state above this
    min_gravity_confidence: float = 0.5
    vertical_tolerance: float = 0.15
    assumed_camera_height: float = 1.4
```

Expose as `memory.build` in YAML through a `MemoryBuildConfig` dataclass with the same fields and range validation. `MemoryConfig` gains `build`, `gravity` and (WP07) `home_id`.

### `anchors.py`

```python
@dataclass
class SpatialAnchor:
    anchor_id: int
    label: str                       # "Storage Cabinet #1"
    canonical: str                   # vocabulary id
    center: tuple[float, float, float]
    size: tuple[float, float, float]
    rotation: tuple[float, float, float, float] | None = None
    yaw: float | None = None
    footprint: list[tuple[float, float]] = field(default_factory=list)   # horizontal coords, CCW
    up_min: float | None = None
    up_max: float | None = None
    support_up: float | None = None
    observations_count: int = 1
    room_id: int | None = None
    room_label: str | None = None

def extract_spatial_anchors(boxes_3d, *, vocabulary=None, gravity=None, unit=1.0,
                            cluster_radius=0.40) -> list[SpatialAnchor]
def anchor_shape(anchor, vocabulary) -> AnchorShape
```

`extract_spatial_anchors`:

1. Anchor boxes = boxes whose vocabulary role is `anchor`. **If there are none, return `[]`.**
2. Group by `vocabulary.canonical(label)`; iterate groups in sorted id order.
3. Cluster within a group exactly as today (running-mean centre, threshold `cluster_radius * unit`). Keep clusters with ≥ 2 members when any exist, else all clusters.
4. Per cluster: drop members whose `max(size)` exceeds twice the cluster median of `max(size)`. `center` = median of member centres. Medoid = member whose centre is nearest that median; take `size`, `rotation`, `yaw` from the medoid.
5. `footprint` = `planar.convex_hull` of all member footprint corners (`box_footprint(member, gravity).polygon`). `up_min` = 15th percentile of member `up_min`; `up_max` = 85th percentile of member `up_max`; `support_up` = median of the non-`None` member values, else `None`. For legacy boxes without `up_min`, derive from `elevation(center) ∓ size[2]/2`.
6. Label = `f"{vocabulary.display(canonical)} #{anchor_idx}"` with one running `anchor_idx` across all groups, as today.

`as_dict` adds `canonical`, `rotation`, `yaw`, `footprint`, `up_min`, `up_max`, `support_up` when present.

### `association.py`

```python
@dataclass
class InstanceTrack:
    instance_id: int
    canonical: str
    display_name: str            # "Shoes #1"
    center: tuple[float, float, float]
    track_id: int
    appearance: tuple[float, ...] | None
    count: int
    last_frame: int

def associate_instances(boxes, *, vocabulary, unit, settings) -> tuple[dict[int, int], dict[int, InstanceTrack]]
```

Input: object boxes only (role `object`, `is_hand` false), any order. Process in `(timestamp, frame_id, −confidence)` order. Returns `box_index → instance_id` and the instance table.

Rules — this is the existing non-shoe path of `classify_unique_instance`, applied to **every** class:

1. Candidates = instances with the same canonical id that have not already been assigned a box in this frame.
2. Same `track_id` as an existing candidate → that instance.
3. Otherwise score candidates with `dist <= association_radius * unit` **or** `appearance_distance <= appearance_threshold`: `score = min(dist / (association_radius * unit), 2.0) + (appearance_distance if available else 0)`; take the lowest.
4. Otherwise, if exactly one instance of this canonical exists and it was not assigned in this frame → reuse it (relocation after occlusion).
5. Otherwise create `instance_id = max(existing) + 1` (IDs are unique across classes, starting at 1), `display_name = f"{vocabulary.display(canonical)} #{instance_id}"`.
6. Update the matched instance: `center`, `track_id`, `appearance` (keep old if new is `None`), `count += 1`, `last_frame`.

If two boxes in one frame map to the same instance, rule 1 prevents it: the lower-confidence box goes through rules 3–5 against the remaining instances.

`_appearance_distance` moves here unchanged.

### `runs.py`

```python
@dataclass(frozen=True, slots=True)
class Observation:
    frame_id: int
    timestamp: float
    instance_id: int
    box: BoundingBox3D
    relation: str                 # raw, before debouncing
    anchor_id: int | None
    certain: bool
    hand_cue: bool

@dataclass
class StateRun:
    instance_id: int
    relation: str
    anchor_id: int | None
    room_id: int | None
    start_frame: int
    end_frame: int
    start_time: float
    end_time: float
    observation_count: int
    confidence: float             # mean detection confidence x (1.0 if every observation certain else 0.6)
    certain: bool
    center: tuple[float, float, float]        # median of observed centres
    height_above_floor: float | None          # median of (box.up_min - floor_offset); None if floor unknown
    best_frame: int                           # frame of the highest-confidence observation (evidence source, WP10)
    best_bbox_2d: tuple[float, float, float, float]

def build_state_runs(observations: Sequence[Observation], *, settings, gravity, room_of) -> list[StateRun]
def build_events(runs_by_instance, anchors_by_id, rooms_by_id, wallclock) -> list[dict]
```

**Carry rule (replaces every shoe/frame rule).** Per instance, in time order, keep a flag `carried`:

- Observation with `hand_cue` → raw state is `("carried_by_user", None)`.
- Observation without `hand_cue` → raw state is the classifier result `(relation, anchor_id)`.
- `hand_cue = box.is_in_hand or box.spatial_state == "in_hand"`.

**Debounce.** Walk the raw states `s_1 … s_n` of one instance:

```
current = s_1 ; run starts at observation 1
pending = None ; pending_start = None ; pending_count = 0
for i in 2..n:
    if s_i == current:          pending = None ; pending_count = 0
    elif s_i == pending:        pending_count += 1
    else:                       pending = s_i ; pending_start = i ; pending_count = 1
    if pending is not None and pending_count >= min_run_observations:
        close the current run at observation pending_start - 1
        current = pending ; new run starts at pending_start ; pending = None ; pending_count = 0
at the end:
    if pending is not None and pending_start == n            # a single trailing observation
       and box_n.confidence >= trailing_single_confidence
       and (certain_n or s_n[0] == "carried_by_user"):
        close the current run at n - 1 ; add a one-observation run for s_n
    else:
        observations in a discarded pending stretch count toward the current run
```

Two raw states are equal when both `relation` and `anchor_id` are equal.

**Confirmation.** An instance with fewer than `min_observations` observations in total produces no runs and no entries. Exception: none. (This replaces the "shoes are always persistent" special case.)

**Events.** For consecutive runs `prev → cur` of one instance:

| Condition | `event_type` |
|---|---|
| `cur.relation == "carried_by_user"` | `pickup` |
| `prev.relation == "carried_by_user"` | `placement` |
| `prev.anchor_id != cur.anchor_id` | `anchor_change` |
| otherwise | `state_change` |

Event dict (superset of today's keys so the API and Rerun keep working):

```python
{
  "event_id": "",                       # filled by _renumber_events
  "event_type": …, "instance_id": …, "object": display_name,
  "source_anchor": label or None,       "destination_anchor": label or None,
  "source_anchor_id": id or None,       "destination_anchor_id": id or None,
  "source_room": label or None,         "destination_room": label or None,
  "source_room_id": id or None,         "destination_room_id": id or None,
  "source_relation": prev.relation,     "destination_relation": cur.relation,
  "start_time": prev.end_time,          "end_time": cur.start_time,
  "start_wallclock": iso or None,       "end_wallclock": iso or None,
  "source_frame": prev.end_frame,       "destination_frame": cur.start_frame,
  "stable_observations": cur.observation_count,
  "relative_displacement": |cur.center - prev.center|,
  "evidence_frames": unique [prev.start_frame, prev.end_frame, cur.start_frame, cur.end_frame],
  "confidence": min(prev.confidence, cur.confidence),
}
```

No fabricated anchor names. `None` means "no anchor".

`_wearer_room_events` keeps its logic and gains `source_room_id`, `destination_room_id`, `start_wallclock`, `end_wallclock`.

### `scene_graph.py` — the builder

Signature (existing positional calls stay valid):

```python
def build_relative_4d_scene_graph(
    boxes_3d, all_frame_ids, timestamps, camera_poses=None, *,
    estimate_rooms=True, zone_link_radius=1.5, min_zone_keyframes=3,
    gravity: GravityFrame | None = None,
    vocabulary: Vocabulary | None = None,
    wallclock_by_frame: Mapping[int, str] | None = None,
    settings: MemoryBuildSettings | None = None,
) -> Relative4DSceneGraph
```

Stages:

1. Resolve defaults. `unit = gravity.unit(settings.assumed_camera_height, settings.min_gravity_confidence)`.
2. Parse poses into `pose_by_frame` (keep today's parsing; move it to a helper).
3. `anchors = extract_spatial_anchors(...)`. May be empty.
4. Rooms: `extract_room_regions(camera_poses, boxes_3d, zone_link_radius=…, min_zone_keyframes=…, vocabulary=…, gravity=…, unit=unit)`; if empty and anchors exist, `implicit_room_from_anchors`. Bind each anchor to `room_for_point(anchor.center, rooms, gravity=gravity)`.
5. `wearer_room_by_frame` from pose translations.
6. Object boxes = role `object` and not `is_hand`. Landmarks, anchors and hands never enter object memory.
7. `associate_instances`.
8. For each object box build an `Observation`: `classify_relation(box_footprint(box, gravity), [anchor_shape(a, vocabulary) for a in anchors], gravity, …)`.
9. `build_state_runs` → `state_runs`. Room of a run: `carried_by_user` → wearer's room at `start_frame`; else the anchor's room when the run has an anchor; else `room_for_point(run.center)`.
10. `events = build_events(...) + _wearer_room_events(...)`, then `_renumber_events`.
11. `room_visits`: compress `wearer_room_by_frame` in time order into `[{"room_id", "room_label", "start_frame", "end_frame", "start_time", "end_time", "start_wallclock", "end_wallclock", "keyframe_count"}]`. A visit shorter than 2 keyframes is merged into the previous visit.
12. `latest_states`: one dict per confirmed instance from its last run (fields below).
13. **Legacy per-keyframe timeline** (`memory_timeline`), still needed by the Rerun stage and by existing tests. For each keyframe and each confirmed instance whose first observation is at or before that keyframe, emit one `ObjectMemoryEntry`:
    - observed in this frame → geometry from the box, `is_active_view=True`;
    - not observed → geometry from the last observation, `is_active_view=False`. If the current run is `carried_by_user` and both the pickup pose and this frame's pose exist, `center = R_now @ (R_pickupᵀ @ (c_pickup − t_pickup)) + t_now`. If either pose is missing, keep the last observed centre. Never invent an offset.
    - `relation`, `anchor_id`, `anchor_label`, `room_id`, `room_label` come from the **run** that covers this time (debounced), not from the raw per-frame classification. A keyframe between two runs belongs to the earlier run.
    - `relative_vector`/`relative_distance` to the run's anchor when it has one; otherwise `(0, 0, 0)` and `0.0`.
    - New entry fields: `confidence` (detection confidence of the last observation), `relation_certain`, `height_above_floor`.

**`ObjectMemoryEntry`** gains `confidence: float = 0.0`, `relation_certain: bool = True`, `height_above_floor: float | None = None`; `as_dict` always writes `confidence` and `relation_certain`.

**`Relative4DSceneGraph`** gains `state_runs`, `room_visits`, `latest_states`, `gravity`, `session`.

`as_dict()` — schema version 2, **without** the per-keyframe timeline:

```python
{
  "schema_version": 2,
  "session": {"dataset_id": None, "home_id": None, "started_at": iso|None, "ended_at": iso|None,
              "time_source": "capture"|"recorded_at"|"none", "keyframe_count": int},
  "gravity": gravity.as_dict(),
  "anchors": [...], "rooms": [...],
  "state_runs": [...],          # StateRun as dict + "instance_label", "anchor_label", "room_label",
                                #   "start_wallclock", "end_wallclock"
  "latest_states": [...],       # see below
  "events": [...],
  "room_visits": [...],
}
```

`timeline_dict()` returns the old `{"<frame_id>": [entry, …]}` mapping.

`latest_states` item — same keys the API reads today plus the new ones:
`instance_id, label, canonical, relation, relation_certain, anchor_id, anchor_label, room_id, room_label, center, size, relative_distance, last_seen_timestamp, last_seen_wallclock, is_active_view (observed in the final keyframe), is_in_hand, confidence, height_above_floor, frame_id`.

**Wall-clock.** `wallclock_by_frame[frame_id]` is an ISO-8601 string with timezone. Normalise every stored value to UTC with the fixed format `YYYY-MM-DDTHH:MM:SS.ffffff+00:00` (helper `core/timeutil.py::to_utc_iso(dt)` and `parse_iso(s)`; create this small module). When the mapping is `None`, all `*_wallclock` fields are `None` and `session.time_source = "none"`.

### Worker changes (`run_detect_and_lift`)

- Build `wallclock_by_frame` from `metadata["frames"][i]["capture_timestamp"]` when present (live datasets). For batch videos: if `source_metadata.json` has `recorded_at` (ISO string), `wallclock = recorded_at + timestamp` and `time_source = "recorded_at"`; else `None`. Add CLI option `--recorded-at` to `run_pipeline.py` that writes `recorded_at` into `source_metadata.json` at ingest.
- Pass `gravity`, `vocabulary`, `wallclock_by_frame`, `settings` to the builder.
- Fill `session.dataset_id`.
- Write three files: `r4d_scene_graph.json` (v2, no timeline), `r4d_timeline.json` (`{"schema_version": 1, "dataset_id": …, "timeline": graph.timeline_dict()}`), `events.json` (unchanged shape).
- **Delete the two embedded copies** in `spatial_memory_graph.json` (`objects` and `r4d_scene_graph` keys at lines 482-484). Keep the file as a small manifest: counts plus relative paths to the other artifacts. Grep for readers of `spatial_memory_graph.json` first and update them.
- `run_rerun` reads the timeline from `r4d_timeline.json` (fall back to `r4d_scene_graph.json["timeline"]` for old datasets). Anchor boxes use `rotation` when present.
- `_clear_downstream_artifacts` also removes `r4d_timeline.json`.
- `run_pipeline._download_outputs`: do not download `r4d_timeline.json`.

### Tests

Coordinates in new tests are Y-down with an explicit `GravityFrame` (floor at `y = 1.4`, as in WP04).

`tests/test_association.py`: same track id reuses the instance; a track restart within the radius reuses it; two same-class objects far apart and with different appearance get two IDs; a single known instance relocates; two boxes of one class in one frame never share an instance; **shoes are treated like any other class** (three pairs far apart → three IDs, regardless of X position).

`tests/test_anchors.py`: no anchor boxes → `[]`; two cabinet observations → one anchor with a hull footprint; a `bed` box becomes an anchor; an outlier-sized member is dropped.

`tests/test_runs.py`: one flickering observation does not create a run or an event; two consecutive observations in a new state do; a trailing single observation commits only above the confidence threshold; an instance with one observation yields nothing; pickup → placement produces exactly `pickup` then `placement`.

`tests/test_scene_graph.py` — rewrite these, keep the rest:

| Test | Change |
|---|---|
| `test_multi_instance_object_persistence` | Give each pair two observations. Assert two instances, both present with `is_active_view False` in the last keyframe. |
| `test_in_hand_kinematic_attachment_during_occlusion` | Two in-hand observations (frames 300 and 310) so the instance is confirmed; poses for 300, 310, 350, 400. Assert the centre follows the camera. No reliance on frame numbers. |
| `test_hybrid_release_gate_and_events` | Sequence: on the floor (2 obs) → in hand (2 obs) → inside the cabinet (2 obs, no hand cue). Assert relations `on_floor`, `carried_by_user`, `inside` and events `pickup`, `placement`. Add a second test: if the object is never seen again after pickup it **stays** `carried_by_user`. |
| `test_bottle_occlusion_and_relocation_r4dsg` | Put the bottle on top of each desk in the new geometry. Assertions unchanged. |
| `test_long_term_reidentification_reuses_instance_id` | No anchors now means `anchor_label is None` and relation `in_room`. Assert instance IDs `[1, 1]`. |
| `test_room_landmarks_are_excluded_from_object_memory` | `sofa` is now an anchor and votes for Living Room; `door` is a pure landmark. Assert neither appears as an object and `keys` does. |

New tests:

- `test_no_anchor_is_fabricated` — a graph built from object boxes only has `anchors == []` and no event names a cabinet.
- `test_shoes_on_and_under_bed_in_pitched_session` — the whole pipeline from boxes to `latest_states` with a 40° pitched frame; one pair `on_surface`, one pair `under`.
- `test_as_dict_has_no_timeline_and_has_runs`
- `test_wallclock_is_carried_into_runs_and_events`
- `test_confidence_is_stored_on_entries_and_runs`
- `test_event_carries_room_ids`
- `test_graph_size_is_independent_of_keyframe_count` — same scene with 10 and with 200 keyframes of an unmoved object: `len(json.dumps(graph.as_dict()))` differs by less than 5 %.

### Done when

Tests pass, and `grep -n "shoe\|480\|280\|Floor Entrance\|Storage Cabinet #1" src/aegis/memory/*.py` returns nothing. Re-run `demo01`, `demo04`, `Demo06-Self` through the pipeline and attach to the PR, for each: the list of `latest_states` (label, relation, anchor), the event list, and `gravity.json`. Differences from the old output are expected; list them and say for each whether the new answer is right according to the video.

---

## WP06 — API correctness and graph lifecycle

**Closes:** C3, C5, C9, A6 (per-dataset half), 2.7 (cache invalidation, corrupt graph).
**Depends on:** WP05.

### Files

- New: `src/aegis/memory/repository.py`, `tests/test_repository.py`
- Edit: `src/aegis/remote/api.py`, `src/aegis/memory/reasoning.py`, `tests/test_api.py`, `tests/test_reasoning.py`, `tests/test_mid1_prototype.py`, `tests/conftest.py`

### `repository.py`

```python
class MemoryRepository(Protocol):
    ready: bool
    def anchors(self) -> list[dict]: ...
    def rooms(self) -> list[dict]: ...
    def events(self) -> list[dict]: ...
    def latest_states(self) -> dict[int, dict]: ...
    def rename_room(self, room_id: int, label: str) -> dict: ...
    def keyframe_count(self) -> int: ...

class JsonGraphRepository:
    """One r4d_scene_graph.json. Accepts schema v1 (timeline) and v2 (latest_states)."""
```

- Loading: v2 → `latest_states` from the list keyed by `instance_id`. v1 → scan `timeline` in numeric frame order once and cache the result (this is today's `find_latest_objects_state`).
- **Cache invalidation:** the module-level cache maps `dataset_id → (path, mtime_ns, size, repository)`. On every access `stat` the file; reload when `mtime_ns` or `size` changed or the path disappeared. Simulator mutations live in the cached object and survive until the file changes or `/reset` is called.
- **Corrupt file:** JSON errors or a wrong top-level type → log a warning, return a not-ready empty repository, **do not cache**.
- A graph whose `dataset_id` differs from the requested one is rejected as today.

`api.py` keeps `load_scene_graph_data` and `find_latest_objects_state` as thin wrappers over the repository so other callers (`run_server.py`) keep working.

### C3 — room rename

`JsonGraphRepository.rename_room(room_id, label)`:

1. Find the room; `KeyError` → HTTP 404.
2. `old_label = room["label"]`; set the new label.
3. Anchors: `anchor["room_id"] == room_id` → update `room_label`.
4. `latest_states`, `state_runs`, `room_visits` (v2) or every `timeline` entry (v1): match on `room_id`.
5. Events: for each side, if the event has `source_room_id`/`destination_room_id` match on the id; **else** (v1 graph) update only when the stored label **equals `old_label` exactly**. Never use a prefix test.
6. Write atomically (temp file + `replace`), refresh the cache entry.

### C5 — input validation

- `get_active_dataset`: validate with `core.paths.validate_dataset_id`; on `ValueError` raise `HTTPException(400, "invalid dataset_id")`. Apply to every endpoint, including `/video/{dataset_id}`, `/dataset/select` and `SimulateTransitionRequest.dataset_id`.
- `/crops/{instance_id}`: escape every interpolated string with `html.escape` (the SVG is replaced by real crops in WP10; until then it must at least be safe).
- CORS stays as is until Milestone 4 (todo 4.2). Leave a `# TODO(M4 4.2)` comment only.

### A6 — simulator

- `simulate_transition`, `/reset` and the six `/simulate/*` routes are registered only when env `AEGIS_ENABLE_SIMULATOR == "1"`. Put them on an `APIRouter` and `app.include_router` conditionally at import time.
- Remove the `Demo06-Self` and `642` literals: unknown instance → HTTP 404; next frame = `max(existing) + 1`, or `1` for an empty graph.
- `tests/conftest.py` sets `AEGIS_ENABLE_SIMULATOR=1` before `aegis.remote.api` is imported.
- `run_server.py`: add `--enable-simulator` which sets the env var before importing the app. Check the import order in that file.
- `list_available_datasets`: return `[]` when nothing is found (not the invented `["demo01", "Demo06-Self"]`). `get_datasets`: remove the hard-coded titles; title = `source_metadata.task` or `f"Egocentric scene: {d}"`.

### Query path

- Replace `_matches_query` and `QueryReasoningEngine.extract_target_item` matching with the vocabulary:
  1. `entry = vocabulary.resolve_query(text)` after room words are removed (keep the existing room stripping).
  2. If found: matches = states whose `canonical` equals `entry.id` (v2), or whose label base — text before `#` or `[` — satisfies `vocabulary.canonical(base) == entry.id` (v1).
  3. If not found: fall back to an exact, case-insensitive comparison between the cleaned query phrase and the label base. This keeps open-vocabulary labels such as "Garbage Bag" queryable. No substring matching.
- Sort key: most recent `last_seen_timestamp` first. Remove the `"active" in label` rule.
- `confidence`: return `primary.get("confidence")` when present, else `None`. Change `MemoryQueryResponse.confidence` to `float | None = None`. Remove the constant `0.96`.
- `last_seen_time_ago`: change to `str | None = None` and return `None`. Remove `"Recorded today"`. Real freshness is Milestone 3 (todo 3.4).
- New response fields: `relation_certain: bool | None`, `height_above_floor: float | None`.
- `get_anchors`: an object counts as contained when its relation is in `{"inside", "on_surface", "under"}`.
- `get_timeline`: remove `default_anchor_name`. Summaries must handle `None` anchors.

### C9 — answer wording (`reasoning.py`)

At most two sentences. No "safely", "securely", "Aegis remembers". The room clause is appended by `_insert_room_clause` as today. `{V}` = "is"/"are"; `{W}` = "was"/"were". Plural comes from `vocabulary.entry(...).plural`; delete `PLURAL_ITEMS` and `ITEM_SYNONYMS`.

| Relation | Seen in the final keyframe | From memory (not in view) |
|---|---|---|
| `inside` | Your {item} {V} inside {anchor}. | Your {item} {W} last seen inside {anchor}. |
| `on_surface` | Your {item} {V} on {anchor}. | Your {item} {W} last seen on {anchor}. |
| `under` | Your {item} {V} under {anchor}. | Your {item} {W} last seen under {anchor}. |
| `above` | Your {item} {V} above {anchor}. | Your {item} {W} last seen above {anchor}. |
| `next_to` | Your {item} {V} next to {anchor}. | Your {item} {W} last seen next to {anchor}. |
| `on_floor`, anchor known | Your {item} {V} on the floor beside {anchor}. | Your {item} {W} last seen on the floor beside {anchor}. |
| `on_floor`, no anchor | Your {item} {V} on the floor. | Your {item} {W} last seen on the floor. |
| `near`, `moving_towards` | Your {item} {V} near {anchor}. | Your {item} {W} last seen near {anchor}. |
| `in_room`, room known | Your {item} {V} in {room}. | Your {item} {W} last seen in {room}. |
| `in_room`, no room | I have seen your {item}, but I can't tell where {it is / they are}. | same |
| `carried_by_user` | You are holding your {item}. | You were last seen carrying your {item}. |

When `relation_certain` is false, append the second sentence: "I'm not fully sure about the exact spot."

Timeline summaries (`get_timeline`) by event type:

| Event | Summary |
|---|---|
| `room_change` | "You moved from {src_room} to {dst_room}." (with the article rule of `room_summary_clause`) |
| `pickup` | "{object} was picked up from {src_anchor}." — or "{object} was picked up." when the anchor is `None` |
| `placement` | "{object} was placed {phrase(dst_relation)} {dst_anchor}{room}." — or "{object} was put down{room}." when the anchor is `None` |
| `anchor_change` | "{object} moved from {src_anchor} to {dst_anchor}{room}." |
| `state_change` | "{object} is now {phrase(dst_relation)} {dst_anchor}{room}." |

`phrase`: `inside → "inside"`, `on_surface → "on"`, `under → "under"`, `above → "above"`, `next_to → "next to"`, `on_floor → "on the floor beside"`, `near → "near"`.

### Tests

- `tests/test_repository.py`: v1 and v2 graphs load to the same `latest_states` shape; a file rewritten on disk is picked up without restart (`test_new_graph_is_visible_without_restart`); a corrupt file gives a not-ready repository and is retried on the next call (`test_corrupt_graph_is_not_cached`).
- `tests/test_api.py`:
  - `test_rename_only_touches_the_renamed_room` — a v1 graph with two neutral rooms and events in both; rename room 1; events of room 2 are unchanged. **This is the C3 regression test.**
  - `test_rename_matches_events_by_room_id` — v2 graph.
  - `test_invalid_dataset_id_is_rejected` — `dataset_id=../../etc` → 400 on `/query`, `/video/…`, `/rooms/rename`.
  - `test_corrupt_graph_returns_not_found_not_500`
  - `test_query_confidence_is_not_a_constant` — v1 fixture → `confidence is None`; v2 graph → the stored value.
  - `test_simulator_routes_absent_without_flag` — build a fresh app instance with the env var unset (use `importlib.reload` in a subprocess-safe way, or factor app creation into `create_app()` and call it).
  - Update `test_rename_room_endpoint_persists` if its event assertion relied on the prefix rule (the `demo01` fixture has one room, so it should still pass).
  - Update `test_crops_endpoint` only if escaping changes the expected text.
- `tests/test_reasoning.py`: replace sentence assertions with the exact templates above; add one test per new relation and one asserting no answer has more than two sentences.
- Add `tests/test_restart_equivalence.py::test_json_graph_survives_restart` — query, clear the cache (simulating a restart), query again, compare responses. The store-level restart test is in WP07.

### Done when

Tests pass; `grep -n "0.96\|Recorded today\|Demo06-Self\|642" src/aegis/remote/api.py` returns nothing.

---

## WP07 — Persistent home store and session ingest

**Closes:** A1, A2, A3, 2.7 (restart equivalence, append-only decision), decision #6.
**Depends on:** WP05, WP06.

**Idea.** A *session* is one processed dataset (a batch video or one live segment). Its graph is session-local and disposable. The *home store* is the durable memory: it accumulates sessions for one home, keeps stable IDs for rooms, anchors and objects, and stores state runs, not frames. History is append-only across sessions; a session's own rows are replaced only when that same session is re-ingested.

### Files

- New: `src/aegis/memory/store.py`, `matching.py`, `ingest.py`, `cli.py`; tests `tests/test_store.py`, `test_matching.py`, `test_ingest.py`, `test_restart_equivalence.py`
- Edit: `src/aegis/core/config.py` (`memory.home_id`, `memory.store_root`), `src/aegis/memory/repository.py` (`StoreRepository`), `src/aegis/remote/api.py` (`home_id` parameter), `run_pipeline.py` (ingest after download), `pyproject.toml` (`aegis-memory = "aegis.memory.cli:main"`), `docs/artifact_contracts.md`

### Locations

- `store_root`: env `AEGIS_STORE_ROOT`, else `config.memory.store_root`, default `"outputs/_homes"`.
- `home_id`: validated with `validate_dataset_id`; default `config.memory.home_id = "home01"`.
- Files: `<store_root>/<home_id>/memory.db`, `<store_root>/<home_id>/home_map.json` (WP08), `<store_root>/<home_id>/evidence/…` (WP10).
- `_homes` starts with an underscore so `list_available_datasets` must skip directories whose name starts with `_`. Add that filter.

### Schema (`store.py`)

`open_store(home_id, store_root=None) -> HomeStore`. It is the only place a connection is created. `sqlite3.connect(path)`, then `PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON`, `PRAGMA synchronous=NORMAL`. `row_factory = sqlite3.Row`. Create the schema when `PRAGMA user_version == 0`, then set it to `1`. A higher version than the code knows → raise.

All timestamps are UTC ISO-8601 text in the fixed format from `core/timeutil.py`, so string comparison is chronological.

```sql
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
-- rows: home_id, created_at

CREATE TABLE session (
  session_id        TEXT PRIMARY KEY,
  started_at        TEXT NOT NULL,
  ended_at          TEXT NOT NULL,
  time_source       TEXT NOT NULL CHECK (time_source IN ('capture','recorded_at','ingest')),
  ingested_at       TEXT NOT NULL,
  graph_sha256      TEXT NOT NULL,
  keyframe_count    INTEGER NOT NULL,
  gravity_confidence REAL,
  last_wearer_room_id INTEGER REFERENCES room(room_id)
);

CREATE TABLE room (
  room_id       INTEGER PRIMARY KEY,
  label         TEXT NOT NULL,
  room_type     TEXT NOT NULL,
  label_source  TEXT NOT NULL CHECK (label_source IN ('auto','caregiver')),
  signature     TEXT NOT NULL,              -- JSON array of strings, sorted
  session_count INTEGER NOT NULL DEFAULT 1,
  last_seen_session TEXT,
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL
);

CREATE TABLE anchor (
  anchor_id     INTEGER PRIMARY KEY,
  canonical     TEXT NOT NULL,
  label         TEXT NOT NULL,              -- "Desk #2"; ordinal is per canonical within the home
  ordinal       INTEGER NOT NULL,
  room_id       INTEGER REFERENCES room(room_id),
  home_x        REAL, home_y REAL,          -- horizontal position in the home frame; NULL until aligned
  match_quality TEXT NOT NULL DEFAULT 'unique' CHECK (match_quality IN ('unique','aligned','resident','ordinal','new')),
  observations  INTEGER NOT NULL DEFAULT 0,
  last_seen_session TEXT,
  UNIQUE (canonical, ordinal)
);

CREATE TABLE instance (
  instance_id   INTEGER PRIMARY KEY,
  canonical     TEXT NOT NULL,
  label         TEXT NOT NULL,              -- "Keys #3"
  importance    TEXT NOT NULL,
  appearance    TEXT,                       -- JSON array or NULL
  created_at    TEXT NOT NULL,
  observation_count INTEGER NOT NULL DEFAULT 0,
  -- last-known state: never compacted
  last_relation TEXT,
  last_relation_certain INTEGER,
  last_anchor_id INTEGER REFERENCES anchor(anchor_id),
  last_room_id  INTEGER REFERENCES room(room_id),
  last_seen_at  TEXT,
  last_confidence REAL,
  last_height   REAL,
  last_run_id   INTEGER,
  last_session_id TEXT,
  last_evidence_id INTEGER
);

CREATE TABLE state_run (
  run_id        INTEGER PRIMARY KEY,
  instance_id   INTEGER NOT NULL REFERENCES instance(instance_id),
  session_id    TEXT NOT NULL REFERENCES session(session_id),
  relation      TEXT NOT NULL,
  relation_certain INTEGER NOT NULL,
  anchor_id     INTEGER REFERENCES anchor(anchor_id),
  room_id       INTEGER REFERENCES room(room_id),
  start_at      TEXT NOT NULL,              -- first observation supporting this state
  end_at        TEXT NOT NULL,              -- last observation supporting this state
  observation_count INTEGER NOT NULL,
  confidence    REAL NOT NULL,
  height_above_floor REAL,
  center_x REAL, center_y REAL, center_z REAL,   -- session-local; NULL after compaction
  evidence_id   INTEGER
);
CREATE INDEX state_run_instance_end ON state_run(instance_id, end_at);
CREATE INDEX state_run_end ON state_run(end_at);
CREATE INDEX state_run_session ON state_run(session_id);

CREATE TABLE event (
  event_id      INTEGER PRIMARY KEY,
  session_id    TEXT NOT NULL REFERENCES session(session_id),
  event_type    TEXT NOT NULL,              -- pickup | placement | anchor_change | state_change | room_change | moved_while_unobserved
  instance_id   INTEGER REFERENCES instance(instance_id),   -- NULL for room_change
  from_relation TEXT, to_relation TEXT,
  from_anchor_id INTEGER, to_anchor_id INTEGER,
  from_room_id INTEGER, to_room_id INTEGER,
  start_at      TEXT NOT NULL,
  end_at        TEXT NOT NULL,
  confidence    REAL,
  activity_id   INTEGER,
  evidence_id   INTEGER
);
CREATE INDEX event_end ON event(end_at);
CREATE INDEX event_session ON event(session_id);

CREATE TABLE room_visit (
  visit_id   INTEGER PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES session(session_id),
  room_id    INTEGER REFERENCES room(room_id),
  start_at   TEXT NOT NULL,
  end_at     TEXT NOT NULL
);
CREATE INDEX room_visit_end ON room_visit(end_at);
```

Tables `activity` (WP09), `evidence` (WP10), `summary` and `compaction_log` (WP11) are created in this WP too, so the schema version does not change between WPs. Their definitions are in those sections.

`HomeStore` exposes small, typed methods (no SQL outside `store.py`): `transaction()` context manager, `get_session`, `delete_session_rows`, `insert_*`, `update_instance_last_known`, `rooms()`, `anchors()`, `instances()`, `latest_states()`, `events(start=None, end=None)`, `runs_for_instance`, `recompute_last_known(instance_id)`, `db_size_bytes()`, `close()`.

### Matching (`matching.py`) — pure functions, no database

All three matchers take plain dataclasses and return mappings, so they can be tested without SQLite.

**Rooms** — `match_rooms(session_rooms, home_rooms, *, contiguous_previous_room_id=None, first_keyframe_session_room_id=None) -> dict[int, int | None]` (session room id → home room id, `None` = create).

Signature of a room = sorted set of `display` names of its landmark evidence ∪ canonical ids of the anchors bound to it.

1. **Continuity.** If `contiguous_previous_room_id` is given (this session started ≤ 10 s after the previous session of the same home ended — live segments), the session room that contains the first keyframe maps to that home room.
2. **Signature.** For each remaining session room with a non-empty signature, compute Jaccard similarity against every unassigned home room with a non-empty signature and, when both rooms are typed (`room_type != "Room"`), the same `room_type`. Accept the best when it is ≥ 0.5 and exceeds the second best by ≥ 0.1. Process session rooms in descending best-score order; each home room is used once.
3. **Single bare room.** If exactly one session room is still unassigned, its signature is empty, and the home has exactly one unassigned room with an empty signature → match them.
4. Everything else → `None` (new room).

Centroid distance is **not** used: positions from different sessions are in different frames.

**Anchors** — `match_anchors(session_anchors, home_anchors, room_map, *, session_residents, home_residents) -> dict[int, tuple[int | None, str]]` (session anchor id → (home anchor id or `None`, match quality)).

Work per `(canonical, mapped home room)` group:

1. **Unique.** One session anchor and one home anchor in the group → match, quality `unique`.
2. **Aligned.** If steps 1 across the whole home produced ≥ 2 matches whose home anchors have `home_x/home_y`, estimate a 2D similarity transform (rotation, uniform scale, translation; no reflection; Umeyama in 2D) from session horizontal centres to home coordinates. With ≥ 3 matches, reject the transform if the RMS residual exceeds 25 % of the mean pairwise distance between the matched home anchors. With a valid transform, match the remaining anchors of each group greedily by nearest transformed position, accepting a pair only if the distance is less than half the distance to the next-nearest candidate. Quality `aligned`.
3. **Residents.** For still-unmatched anchors in a group: a session anchor matches the home anchor with the largest overlap between the canonical ids of objects resting on/in it at the **start** of the session and the home anchor's last-known residents; accept when the overlap is ≥ 1 and unique. Quality `resident`.
4. **Ordinal.** If the group has the same number of unmatched session and home anchors, pair them in ascending id order. Quality `ordinal`. This can be wrong; the quality flag lowers answer confidence later.
5. Remaining session anchors → new home anchors, quality `new`, `ordinal = max(ordinal for that canonical) + 1`, label `f"{display} #{ordinal}"`.

After matching, set `home_x/home_y` for new anchors when a valid transform exists; if the home has no positioned anchors yet (first session), the home frame **is** that session's horizontal frame: store the session horizontal centres directly.

**Instances** — `match_instances(session_instances, home_instances, anchor_map) -> dict[int, int | None]`.

Per canonical id, one-to-one, tiers in order:

1. **Location continuity.** A session instance whose first run, after anchor mapping, has the same `(relation, anchor_id)` as a home instance's last-known state matches it. If several home instances share that state, prefer the smallest appearance distance when both have descriptors, else the lowest `instance_id`. Skip this tier when the session's first relation is `in_room` with no anchor.
2. **Carried over.** Home instance last known `carried_by_user` and the session instance's first run is `carried_by_user` → match (segment boundary during a carry).
3. **Unique by class.** Exactly one unmatched home instance and exactly one unmatched session instance of this canonical → match.
4. **Appearance.** Smallest appearance distance ≤ 0.35 with a margin ≥ 0.1 over the second best → match.
5. Otherwise create a new instance; label `f"{display} #{instance_id}"` using the new home `instance_id`.

### Ingest (`ingest.py`)

```python
def ingest_session(store: HomeStore, graph: Mapping[str, Any], *, vocabulary: Vocabulary,
                   now: datetime | None = None) -> IngestReport
```

`IngestReport`: `session_id`, `status` (`"ingested"`, `"unchanged"`, `"replaced"`), counts of rooms/anchors/instances created and matched, runs inserted and extended, events inserted.

Steps, all inside one transaction:

1. Require `graph["schema_version"] == 2`; else `ValueError("re-run the detect stage: scene graph v1 cannot be ingested")`.
2. `session_id = graph["session"]["dataset_id"]`. `sha = sha256(json.dumps(graph, sort_keys=True))`.
3. If the session exists with the same `sha` → return `unchanged`. If it exists with a different `sha` → `delete_session_rows(session_id)` (runs, events, visits, activities, evidence rows of that session), then `recompute_last_known` for every instance that had runs there, and continue with status `replaced`. Instances, anchors and rooms created by the old ingest are kept. A run of an **earlier** session that the old ingest had extended keeps its extended `end_at` and count; this is accepted, because the object was in fact observed there, and it is noted in the report's `detail`.
4. **Time.** If `session.time_source` is `"capture"` or `"recorded_at"`, use the graph's wall-clock values. If `"none"`: `ended_at = now`, `started_at = now − duration`, convert every relative time `t` to `started_at + t`, and store `time_source = "ingest"`. This is the only place a time is synthesised, and it is labelled.
5. Reject a session whose `started_at` is earlier than the latest `ended_at` already stored minus 1 s **unless** it is a replacement: `ValueError("sessions must be ingested in chronological order")`. (Out-of-order ingest would corrupt cross-session events.)
6. Rooms: build inputs, call `match_rooms`. Continuity input: previous session = the one with the latest `ended_at`; contiguous when `started_at − previous.ended_at <= 10 s` and `previous.last_wearer_room_id` is not `NULL`. Create or update rows. A matched room keeps its `label` and `label_source`; `signature` becomes the union; `session_count += 1`. A new room gets `label_source='auto'`; if its auto label collides with an existing label, append ` #k` with the smallest free `k ≥ 2`.
7. Anchors: `match_anchors`; create/update rows.
8. Instances: `match_instances`; create/update rows (`appearance` updated when the session provides one).
9. Runs, per instance in time order:
   - First run of the session: if the instance has a last-known state with the same `(relation, anchor_id, room_id)` **and** its `last_run_id` row still exists → **extend** that row: `end_at = run.end`, `observation_count += n`, `confidence = max(old, new)`, `session_id` unchanged. No event.
   - Otherwise insert a new row. If the instance already had a last-known state, also insert an event `moved_while_unobserved` from the last-known state to this run, `start_at = last_seen_at`, `end_at = run.start`.
   - Later runs: insert rows.
10. Events: insert the session's events with ids remapped (instance, anchor, room). Events that reference an unconfirmed or unmapped instance are skipped and counted in the report.
11. Room visits: insert remapped. Set `session.last_wearer_room_id` to the last visit's room.
12. `update_instance_last_known` for every touched instance from its newest run (by `end_at`).
13. Insert the `session` row.

### API

- `StoreRepository(HomeStore)` implements `MemoryRepository` by turning rows into the same dict shapes the JSON repository returns (labels resolved by joins). `latest_states()` reads the `instance` table only.
- Endpoints `health`, `query`, `timeline`, `anchors`, `rooms`, `rooms/rename`, `scene_graph` gain an optional `home_id` query parameter. Resolution: explicit `home_id` → store; else explicit `dataset_id` → JSON; else env `AEGIS_HOME_ID` set → store; else the active dataset → JSON. Validate `home_id` like `dataset_id`.
- `query` on a store: `last_seen_timestamp_s` is `None`; add `last_seen_at` (ISO string) to the response model.
- `timeline` on a store accepts `start` and `end` (ISO strings) and returns events ordered by `end_at`.
- Open one `HomeStore` per `home_id` per process, lazily, guarded by a lock; each request uses its own cursor.

### CLI (`aegis-memory`)

```
aegis-memory ingest <graph.json> [--home-id H] [--store-root R] [--config-path C]
aegis-memory show   [--home-id H]            # rooms, anchors, instances with last-known state
aegis-memory size   [--home-id H]            # file size and row counts per table
```

`run_pipeline.py`: add `--home-id` (default from config) and `--no-ingest`. After `_download_outputs`, when the graph file was downloaded and `--no-ingest` is not set, call `ingest_session` and print the report.

### Tests

`tests/test_matching.py`: one test per tier of each matcher, plus: rooms with disjoint signatures are not merged; two desks in one room with a valid transform are matched by position; with no transform and no residents they fall to `ordinal`; an instance left on an anchor is recognised next session; a moved single instance is recognised by tier 3; two identical objects are not merged without evidence.

`tests/test_store.py`: schema creation and reopening; unknown `user_version` raises; `transaction()` rolls back on error.

`tests/test_ingest.py` (graphs built with helper `make_session_graph(...)`, not from fixtures):

- `test_first_session_creates_rooms_anchors_instances`
- `test_reingest_same_graph_is_noop`
- `test_reingest_changed_graph_replaces_only_that_session`
- `test_second_session_same_place_extends_run_and_adds_no_event`
- `test_second_session_moved_object_adds_moved_while_unobserved_event`
- `test_instance_ids_are_stable_across_sessions`
- `test_out_of_order_session_is_rejected`
- `test_session_without_wallclock_is_labelled_ingest_time`
- `test_store_rows_grow_with_changes_not_keyframes` — ingest two sessions of an unmoved scene with 20 and 2,000 keyframes; row counts are equal.
- `test_v1_graph_is_rejected`

`tests/test_restart_equivalence.py::test_store_survives_restart` (AC-06): ingest two sessions, record the `/query` answer for every instance and the `/timeline` output, close the store and clear every cache, reopen, compare for equality.

`tests/test_api.py`: `test_query_by_home_id`, `test_invalid_home_id_is_rejected`.

### Done when

Tests pass. `docs/artifact_contracts.md` has a "Home store" section with the schema, and states that history is append-only across sessions (the 2.7 decision).

---

## WP08 — Per-home room identity

**Closes:** todo 2.3 (all six items), FR3.6, FR3.7, AC-31. Fixes the report claim that rename writes the registry.
**Depends on:** WP07.

### Design

The `room` table is the source of truth. `home_map.json` is a mirror written after every room change, so the artifact the report describes exists and is human-readable.

- `home_id` exists in config (`memory.home_id`, WP07), separate from `dataset_id`. `source_metadata.json` gains `home_id` when a dataset is ingested (`run_pipeline.py` writes it).
- `home_registry.py`:
  - `HomeRoomRecord` gains `room_id: int`, `signature: list[str]`, `label_source: str`. Drop `centroid` from matching; keep the field for backward-compatible loading but stop writing it.
  - Delete `match_room_into_registry` and `calibrate_from_rooms` (proximity matching across sessions is invalid — A3). Room matching lives in `matching.match_rooms`.
  - New `export_registry(store, store_root) -> Path` builds a `HomeRoomRegistry` from the `room` table and calls `save_registry`.
  - New `seed_store_from_registry(store, registry)`: when `memory.db` has no rooms but `home_map.json` exists (restore case), insert its rooms with their labels and `label_source`.
  - `load_registry` keeps its corrupt-file fallback.
- `ingest_session` calls `export_registry` after committing.
- `open_store` calls `seed_store_from_registry` when the room table is empty and a readable registry exists.
- `StoreRepository.rename_room(room_id, label)`:
  1. Strip the label; reject empty or longer than 40 characters (HTTP 422).
  2. Reject a label already used by another room of the home (HTTP 409).
  3. `UPDATE room SET label=?, label_source='caregiver', updated_at=?`.
  4. `export_registry`.
  Nothing else needs rewriting: runs, events and instances reference `room_id`.
- A caregiver label is never overwritten by ingest (step 6 of ingest already keeps `label` on a match).
- Unknown `room_id` → 404.
- Legacy path (`dataset_id`) keeps renaming inside the JSON graph (WP06).

### Tests

- Rewrite `tests/test_home_registry.py`: keep the round-trip and corrupt-file tests (updated fields); delete the two matching tests (their behaviour is replaced by `test_matching.py`); add `test_export_matches_room_table`, `test_seed_store_from_registry`.
- `tests/test_room_identity.py`:
  - `test_rename_writes_home_map_json` — after `POST /rooms/rename?home_id=…` the file contains the label with `label_source == "caregiver"`.
  - `test_rename_survives_restart_and_new_session` (AC-31) — rename, close and reopen the store, ingest a new session that sees the same room → the label is still the caregiver's, the new session's runs carry the same `room_id`, and `/query` names the room.
  - `test_rename_unknown_room_is_404`, `test_rename_duplicate_label_is_409`
  - `test_corrupt_home_map_is_ignored_and_rewritten`
  - `test_rename_survives_reingest_of_same_session`

### Done when

Tests pass; todo 2.3 items ticked; report Table 3.8 / UC-13 are now true (note this in todo §5.2).

---

## WP09 — Activity history

**Closes:** todo 2.5.
**Depends on:** WP07.

### Definition

An **activity** is one stay of the wearer in one room, together with the object events that ended during it. It is the unit behind "what did I do this morning?" and the daily summary.

### Design

Table (created in WP07's schema):

```sql
CREATE TABLE activity (
  activity_id INTEGER PRIMARY KEY,
  session_id  TEXT NOT NULL REFERENCES session(session_id),
  room_id     INTEGER REFERENCES room(room_id),
  start_at    TEXT NOT NULL,
  end_at      TEXT NOT NULL,
  event_count INTEGER NOT NULL,
  summary     TEXT NOT NULL
);
CREATE INDEX activity_end ON activity(end_at);
```

`activities.py`:

```python
def build_activities(visits, events, *, min_gap_seconds=10.0) -> list[ActivityDraft]
def activity_summary(draft, names) -> str
```

1. Sort room visits by start. Merge two consecutive visits to the same room when the gap between them is < `min_gap_seconds`.
2. A session with no visits (no poses or no rooms) yields one activity covering the whole session with `room_id = NULL`.
3. Assign each non-`room_change` event to the activity whose `[start_at, end_at]` contains the event's `end_at`; if none contains it, to the nearest activity in time.
4. Activities with zero events are kept (a visit is itself an activity).
5. Summary template, deterministic, local time from `memory.retention.timezone` (WP11 config; default `Asia/Karachi`), 24-hour clock:
   - with events: `"{HH:MM}–{HH:MM} {room}: {clause}; {clause}; …"` where each clause is the WP06 event summary without its final full stop and without the room suffix. More than 6 events → the first 5 clauses then `"and {n} more changes"`.
   - without events: `"{HH:MM}–{HH:MM} {room}: no objects moved."`
   - `room_id` NULL → use `"Home"` as the room name.

`ingest_session` step 11b: build activities, insert rows, set `event.activity_id`.

API: `GET /api/v1/activities?home_id=&start=&end=` returns `[{activity_id, room_id, room_label, start_at, end_at, event_count, summary, events: [event_id, …], tier: "detailed"}]`. `GET /api/v1/timeline` gains `activity_id` on each event.

### Tests (`tests/test_activities.py`)

- `test_two_rooms_give_two_activities`
- `test_short_excursion_is_merged`
- `test_events_are_assigned_by_end_time`
- `test_session_without_rooms_has_one_home_activity`
- `test_summary_is_deterministic_and_caps_clauses`
- `test_scripted_sequence_order_and_times` (AC-05 harness): a scripted list of 10 ground-truth actions with times; build a matching session graph; assert at least 7 of 10 appear in the correct order within ±1 s. This is the automated form; the recorded real-video run is in WP15.

---

## WP10 — Evidence crops

**Closes:** A11.
**Depends on:** WP05, WP07. Privacy decision #9 pending — implement behind `memory.evidence.enabled` (default `true`).

### Design

Table:

```sql
CREATE TABLE evidence (
  evidence_id INTEGER PRIMARY KEY,
  session_id  TEXT NOT NULL REFERENCES session(session_id),
  instance_id INTEGER NOT NULL REFERENCES instance(instance_id),
  path        TEXT NOT NULL,          -- relative to <store_root>/<home_id>/
  captured_at TEXT NOT NULL,
  frame_id    INTEGER,
  width INTEGER, height INTEGER, bytes INTEGER
);
```

**On Modal** (`run_detect_and_lift`, new helper `memory/evidence.py::write_run_crops(runs, frames_dir, frame_filename_by_id, out_dir, max_side=320, pad=0.15, quality=85)`):

- For every state run except `carried_by_user` runs: open the frame `run.best_frame`, crop `run.best_bbox_2d` expanded by `pad` on each side and clipped to the image, resize so the longer side is `max_side`, save JPEG as `outputs/objects/evidence/run_<instance_id>_<start_frame>.jpg`.
- Record on the run in the graph: `"evidence": {"path": "evidence/run_<…>.jpg", "frame_id": …, "width": …, "height": …}`. A run whose frame cannot be read gets `"evidence": None`; do not fail the stage.
- The crop contains only the object's box. Never write a full frame.

**Download:** `_download_outputs` fetches the `outputs/objects/evidence/` directory to `outputs/<dataset_id>/objects/evidence/`.

**Ingest:** copy each crop to `<store_root>/<home_id>/evidence/<session_id>/<file>`, insert an `evidence` row, set `state_run.evidence_id` and `instance.last_evidence_id`. When a run is *extended* (same state re-observed), replace the evidence only if the new crop file is larger in bytes (a proxy for sharper and bigger); delete the replaced file.

**API:** `GET /api/v1/crops/{instance_id}?home_id=` returns the JPEG of `instance.last_evidence_id` (`image/jpeg`); 404 when there is none. `query` sets `crop_url` only when evidence exists, else `None`. The legacy `dataset_id` path keeps the (escaped) SVG until Milestone 3 removes it.

### Tests (`tests/test_evidence.py`)

- `test_crop_is_clipped_padded_and_resized` — synthetic 640×480 image; assert output size and that pixels come from the box region.
- `test_missing_frame_gives_none_not_error`
- `test_carried_runs_have_no_crop`
- `test_ingest_copies_crop_and_links_it`
- `test_extended_run_keeps_better_crop`
- `test_crop_endpoint_serves_jpeg_and_404`
- `test_disabled_flag_writes_nothing`

---

## WP11 — Compaction and tiered retention

**Closes:** todo 2.4 (all items), FR4.1–FR4.4, AC-07, AC-08, AC-23, UC-12 A1.
**Depends on:** WP07, WP09, WP10.

### Config (`memory.retention`)

```yaml
memory:
  retention:
    hot_days: 3                  # full detail kept this long (FR4.1)
    important_hot_days: 7        # for vocabulary entries with importance: high
    timezone: Asia/Karachi       # calendar days for summaries (zoneinfo name)
    keep_last_evidence: true     # keep the crop behind each object's last-known state
    weekly_rollup_after_days: 30
    monthly_rollup_after_days: 365
```

Validate: `hot_days >= 1`, `important_hot_days >= hot_days`, timezone loadable with `zoneinfo.ZoneInfo`.

### Tables

```sql
CREATE TABLE summary (
  summary_id   INTEGER PRIMARY KEY,
  level        TEXT NOT NULL CHECK (level IN ('day','week','month')),
  period_start TEXT NOT NULL,          -- local date 'YYYY-MM-DD' of the first day of the period
  period_end   TEXT NOT NULL,          -- local date of the last day, inclusive
  kind         TEXT NOT NULL CHECK (kind IN ('object','activity')),
  subject_key  TEXT NOT NULL,          -- 'instance:<id>' or 'activity:<n>'
  text         TEXT NOT NULL,
  sidecar      TEXT NOT NULL,          -- JSON
  created_at   TEXT NOT NULL,
  UNIQUE (level, period_start, kind, subject_key)
);
CREATE INDEX summary_period ON summary(period_start);

CREATE TABLE compaction_log (
  id INTEGER PRIMARY KEY,
  ran_at TEXT NOT NULL,
  day TEXT NOT NULL,                   -- local date compacted
  status TEXT NOT NULL CHECK (status IN ('ok','failed','skipped')),
  runs_deleted INTEGER NOT NULL DEFAULT 0,
  events_deleted INTEGER NOT NULL DEFAULT 0,
  summaries_written INTEGER NOT NULL DEFAULT 0,
  detail TEXT
);
```

### Summaries (`summaries.py`) — templates only

**Object-day line**, one per instance per local day on which it has a run or event ending that day:

- Text: `"{label}: last {phrase} {anchor}{room} at {HH:MM}; moved {n} time(s){also}."`
  - `phrase` as in WP06; no anchor → `"last seen{room} at {HH:MM}"`; `carried_by_user` → `"last seen being carried at {HH:MM}"`.
  - `n` = number of that instance's events that day, excluding `room_change`. `n == 0` → `"; not moved"`.
  - `{also}` = `"; also seen in {room list}"` for other rooms of that day's runs, at most three names.
  - For `importance: high` instances append every move: `" Moves: {HH:MM} {event clause}; …"`.
- Sidecar:
  ```json
  {"instance_id": 3, "canonical": "keys", "label": "Keys #3",
   "last": {"relation": "on_surface", "relation_certain": true, "anchor_id": 4, "room_id": 2, "at": "<UTC ISO>"},
   "rooms": [2, 5], "anchors": [4, 7],
   "event_types": {"pickup": 2, "placement": 2},
   "moves": [{"at": "<UTC ISO>", "type": "placement", "to_anchor_id": 4, "to_room_id": 2, "to_relation": "on_surface"}],
   "source_runs": 5, "source_events": 4}
  ```
  `moves` is filled only for high-importance instances.

**Activity line**, one per activity ending that day: text = `activity.summary`; sidecar = `{"room_id", "start_at", "end_at", "event_types": {…}, "instance_ids": […], "anchor_ids": […]}`.

### Compaction (`compaction.py`)

```python
def compact(store: HomeStore, *, now: datetime, config: RetentionConfig, vocabulary: Vocabulary) -> CompactionReport
```

Local day of a row = local date of its `end_at` in `config.timezone`.

1. `cutoff_day = (now in local time).date() − hot_days`. Days strictly before `cutoff_day` are eligible. For high-importance instances the cutoff is `− important_hot_days`.
2. For each eligible day `D` that still has un-summarised detail, oldest first, each day in its **own transaction**:
   a. Collect the day's runs, events, visits and activities.
   b. Build the summaries.
   c. **Verify** before deleting anything. All of these must hold, else mark the day `failed`:
      - every instance with a run on `D` has an object summary;
      - each object summary's `last` equals the instance's final state on `D` computed directly from the runs (relation, anchor id, room id, time);
      - every `room_id` and `anchor_id` in every sidecar exists in the `room` / `anchor` table;
      - every activity on `D` has an activity summary;
      - no summary text is empty or contains the string `"None"`.
   d. On failure: roll back the day, insert a `compaction_log` row with `status='failed'` and the reason, **keep all source rows**, continue with the next day (UC-12 A1).
   e. On success: `INSERT OR REPLACE` the summaries; delete that day's `event`, `room_visit` and `activity` rows; delete `state_run` rows whose `end_at` falls on `D`, **except**:
      - rows referenced by any `instance.last_run_id` — keep the row, set `center_x/y/z = NULL`;
      - rows of high-importance instances while `D` is inside their longer window (their events of that day are kept too).
      Delete `evidence` rows and files of deleted runs. Evidence of a kept last-known run is kept when `keep_last_evidence` is true, else deleted and `instance.last_evidence_id` set to `NULL`.
      Insert a `compaction_log` row with `status='ok'` and counts.
3. The `instance` table (last-known state) is never touched. The `room`, `anchor`, `session` tables are never touched. So room IDs and labels survive by construction; the verify step checks it mechanically.
4. A run that started before the cutoff but ends inside the hot window is not eligible (it is still current).
5. Idempotent: running `compact` twice with the same `now` changes nothing the second time.

**Roll-up** (`rollup(store, now, config)`): day-level object summaries older than `weekly_rollup_after_days` are replaced by one week-level line per instance per ISO week: `"{label}: mostly {phrase} {anchor}{room} ({k} of {d} days); last there on {date}; moved {n} time(s) this week."` If the last state of every day in the week is identical: `"{label}: unchanged, {phrase} {anchor}{room}, all week."` The sidecar keeps the last state, the set of rooms and anchors and the summed event types. Week lines older than `monthly_rollup_after_days` roll into month lines the same way. Activity lines are dropped at the weekly roll-up (their counts go into a single `"activity:week"` line: `"{n} room visits; most time in {room}."`).

**Triggers.** `ingest_session` calls `compact` then `rollup` after its own transaction has committed (never inside a query). CLI: `aegis-memory compact [--home-id] [--now ISO]`. If the last `compaction_log` row is `failed`, `aegis-memory show` and `/api/v1/health` (store mode) report `compaction_ok: false`.

### Serving summarised history (FR4.3, AC-23)

- `HomeStore.history(start, end, instance_id=None)` returns a merged, time-ordered list of items, each with `tier`: `"detailed"` (from `event`) or `"summarised"` (from `summary`, with `text` and the parsed sidecar).
- `GET /api/v1/timeline?home_id=&start=&end=` returns both kinds; `TimelineEventModel` gains `tier: str = "detailed"`. For a summarised item: `event_type = "summary"`, `object` = label or room, `summary` = text, `start_time`/`end_time` omitted, `period_start`/`period_end` filled.
- "Where is X" is always answered from `instance` (last-known state), so it stays `detailed` regardless of age. If the last-known run's geometry was nulled, the answer still has room, anchor and relation.

### Growth measurement (FR4.4, NFR-P3, AC-07)

`scripts/measure_store_growth.py`:

- Deterministic synthetic generator (`--seed`, default 0): 5 rooms, 20 anchors, `--objects` 100, `--changes-per-day` 1000, `--hours-per-day` 12. Each simulated day is emitted as 144 five-minute session graphs (schema v2) so the real `ingest_session` path is exercised. Evidence is disabled in the generator (crops are measured separately in WP15).
- For day 1 … `--days` (default 14): ingest the day, run `compact`/`rollup` with `now` = end of that day, then record: file size after `PRAGMA wal_checkpoint(TRUNCATE)`, row counts per table, bytes of `summary` text.
- Output `outputs/evaluation/store_growth.csv` and a PNG plot (matplotlib is not a dependency: write the CSV always, plot only if matplotlib imports).
- Also emit the same stream through the **old** representation's size model (entries = keyframes × objects × 1.1 KB, from the measured `demo04` figure) as a comparison column, clearly labelled "projected, not measured".

Report in the PR: the table, and whether detail size is flat after day 3 and total growth per day after day 3.

### Tests (`tests/test_compaction.py`, `tests/test_summaries.py`)

- `test_rows_inside_hot_window_are_untouched` (retention boundary: a run ending 2 days 23 h ago stays; one ending on the day before the cutoff goes)
- `test_summary_content_has_identity_location_room_event_types` (FR4.2)
- `test_last_known_state_survives_compaction` — after compacting everything, `/query` still returns room, anchor and relation for every instance. This is the report's own failure example.
- `test_room_labels_survive_compaction` — a caregiver-renamed room is named in old summaries' sidecars by id and resolves to the current label.
- `test_summarised_items_are_flagged` (AC-23)
- `test_failed_verification_keeps_source_rows` — monkeypatch the summary builder to drop one instance; assert `status == "failed"`, zero rows deleted, `compaction_ok` false.
- `test_compaction_is_idempotent`
- `test_high_importance_instances_keep_detail_longer`
- `test_run_spanning_cutoff_is_kept`
- `test_evidence_files_are_deleted_with_runs_and_kept_for_last_known`
- `test_weekly_rollup_reduces_rows_and_says_unchanged`
- `test_growth_is_bounded` — run the generator for 10 simulated days at reduced scale (`--objects 20 --changes-per-day 100`); assert `detail_rows(day 10) <= 1.2 * detail_rows(day 4)` and summary rows grow by at most `objects + activities_per_day` per day.
- `test_accuracy_before_and_after_compaction` (AC-08 harness) — a fixed list of 20 `where` questions with known answers; answer before and after compaction; assert the drop is ≤ 15 percentage points (expected: 0, because last-known state is retained).

### Done when

Tests pass; the growth CSV is attached to the PR; todo 2.4 items ticked with the test names.

---

## WP12 — Live path: JPEG frames, segments, bounded reconstruction

**Closes:** C12, A5, A10, M3, M5, and the PNG and micro-batch items of todo 1.4.
**Depends on:** WP07.

### C12 — JPEG end to end

- `live_handoff.promote_live_session`:
  - `_FRAME_GLOB` cleanup removes both `frame_*.png` and `frame_*.jpg`.
  - If no resize is needed (`video is None` or the source size equals the target): `shutil.copyfile(source_jpg, frames_dir / f"frame_{id:06d}.jpg")`. No decode, no re-encode.
  - If a resize is needed: decode, resize, `cv2.imwrite(path, image, [cv2.IMWRITE_JPEG_QUALITY, 90])`.
  - `filename` in metadata ends in `.jpg`. The first-frame decode that measures the source size stays.
- Contract: `metadata.frames[].filename` may be `.png` (batch video) or `.jpg` (live). The schema version stays 2 because the field's type and meaning are unchanged. Update `docs/artifact_contracts.md` and the module docstring of `live_handoff.py`.
- Every consumer already resolves frames through `metadata["frames"][i]["filename"]` (`workers.py:216`, `detector.py:331`, `workers.py:1074`). Grep for `".png"` and `frame_*.png` in `src/` to confirm; `ingestion/video.py` keeps PNG for batch video.
- Tests: update `tests/test_live_handoff.py` to expect `.jpg`; add `test_promotion_copies_bytes_when_no_resize` (file hash equal to the source) and `test_promotion_resizes_to_jpeg`.

### A5 / A10 / M3 — segments instead of one whole-session run

A long capture is cut into **segments**. Each segment is promoted as its own dataset, processed by the unchanged four stages, downloaded and ingested as a session. Segments share nothing geometric; the home store joins them (WP07 continuity rule for rooms, carried-over rule for objects). This bounds GPU memory, RAM and disk per step and makes the live path incremental.

- Config:
  ```yaml
  live:
    segment_frames: 120          # frames per segment; 0 = one dataset for the whole session
  vggt:
    max_keyframes: 120           # hard limit per reconstruction; run_vggt raises above it
  ```
  `120` is the default because 108 keyframes is known to work today (`demo01`: 648 frames, stride 6). **Measure the real limit on the L4 in WP15 and adjust.**
- For live configs set `vggt.keyframe_stride: 1`. Live frames are already keyframe-selected at ≤ 2 FPS, so every frame is reconstructed and detected (this is the M3 fix: no detection gap of 3 s). Add `config/live.yaml` = `demo.yaml` with `vggt.keyframe_stride: 1` and `video.sample_fps` unused. Batch 15 FPS videos keep stride 6 (2.5 detections per second).
- `live_handoff.promote_live_segments(session_dir, *, base_dataset_id, segment_frames, data_root, video, camera, start_sequence=0) -> list[PromotionResult]`:
  - Read the index once. Cut frame records into consecutive chunks of `segment_frames`. A final chunk with fewer than 8 frames is merged into the previous one.
  - Also cut at any recorded gap longer than 30 s (a new segment starts after the gap).
  - Dataset ids: `f"{base_dataset_id}_seg{n:04d}"`, `n` from 1.
  - Each segment's metadata is a normal live-promoted metadata with `timestamp` starting at 0 for its first frame and `capture_timestamp` preserved, plus `segment: {"index": n, "base_dataset_id": …, "first_sequence": …, "last_sequence": …}`.
  - `start_sequence` skips frames already promoted: only frames with `sequence >= start_sequence` are considered. This is what makes it incremental.
- `run_pipeline.py --stage live`:
  - New options `--segment-frames` (default from config) and `--follow` (keep promoting new segments while the capture is still running: poll `index.jsonl` every 10 s, process each complete segment, stop when `session.json` status is no longer `running` and no frames remain).
  - Progress is checkpointed in `captures/<session>/pipeline_state.json`: `{"next_sequence": int, "segments_done": [dataset ids]}`, written atomically after each segment's ingest. A restart resumes from it.
  - Per segment: promote → upload → `preprocess` → `vggt` → `detect` → download → `ingest_session`. The `rerun` stage runs only with `--rerun`.
  - After a segment is ingested successfully, delete its local `data/<segment>/frames/` unless `--keep-frames` (raw-frame retention is Milestone 4; this only avoids unbounded local growth). Leave the Modal volume copy to the M4 purge job, but print its size.
- `run_vggt`: raise `ValueError` with a clear message when the number of keyframes exceeds `vggt.max_keyframes` ("lower video.sample_fps, raise vggt.keyframe_stride, or use --segment-frames").
- Pointmap storage (A5 memory): write one file per keyframe, `outputs/geometry/pointmaps/<frame_id>.npz` (`points` float32, `conf` float32, compressed), plus `pointmaps_index.json` listing frame ids. `run_detect_and_lift` loads one at a time. Delete the `pointmaps/` directory at the end of a successful detect stage unless `geometry.keep_pointmaps: true`. Keep reading the old single `pointmaps.npz` when the directory is absent. Add `pointmaps_dir` and `pointmaps_index` to `DatasetPaths`.

### A10 — load models once

- Convert the two GPU functions in `modal_app.py` to classes: `@app.cls(gpu="L4", …)` with a `@modal.enter()` method that loads the model, and a `@modal.method()` `run(dataset_id, config)`. Keep the existing function names as thin module-level wrappers if anything else calls them; update `run_pipeline.py` to call `Reconstructor().run.remote(...)` / `Perception().run.remote(...)`.
- Move model construction out of the hot path: `vggt_runner.load_model(config, token) -> model` and `run_vggt_reconstruction(image_paths, config, *, model=None, …)`; `detector.load_models(config, sam2_config, weights_dir) -> DetectorModels` and `detect_and_track_objects(..., models=None)`. `None` keeps today's behaviour (load inside), so tests and single runs still work.
- Set `scaledown_window=300` on both classes so consecutive segments reuse a warm container.
- Running detection in parallel with reconstruction requires persisting masks between functions. **Not in this WP.** Record it as a follow-up in todo §6 with the measured stage times from WP15, so the decision is made on numbers.

### M5 — honour VGGT settings

- `load_and_preprocess_images(..., image_resolution=config.image_size)` instead of the literal `512`.
- Wrap the forward pass in `torch.autocast("cuda", dtype=…)` when on CUDA: `bfloat16` → `torch.bfloat16`, `float16` → `torch.float16`, `float32` → no autocast. Validate `vggt.dtype` in `config.py` against those three values. Keep the `.float()` conversions after the forward pass.
- Remove the duplicate `cv2` image loading at the top of `run_vggt_reconstruction`; it is only needed by the synthetic branch — move it inside that branch.
- `vggt.batch_size` is unused and has no meaning for a multi-view forward pass: delete the field from `VggtConfig` and from all YAML files.
- Set `vggt.image_size: 512` in every YAML file and as the `VggtConfig` default. Every run so far has used 512 (the literal in the code) with the checkpoint `vggt_omega_1b_512.pt`; the configured `518` was never applied. Changing the resolution is a separate experiment, not part of this WP.

### Tests

- `tests/test_live_segments.py`: `test_segments_split_by_frame_count`, `test_short_tail_is_merged`, `test_long_gap_starts_new_segment`, `test_start_sequence_skips_promoted_frames`, `test_segment_metadata_validates_and_keeps_capture_timestamps`, `test_pipeline_state_resume` (drive the segment loop with the Modal calls replaced by fakes).
- `tests/test_ingest.py::test_contiguous_segments_share_room_and_carried_object` — two segment graphs 2 s apart: the wearer's room maps to the same home room; an object carried at the end of segment 1 and placed in segment 2 is one instance with a `pickup` then a `placement`.
- `tests/test_config.py`: `vggt.dtype` validation; `vggt.max_keyframes`; `live.segment_frames`.
- Pointmap per-file writer/reader round trip with small arrays.

### Done when

Tests pass, and one real capture of at least 10 minutes has been processed with `--segment-frames 120` end to end, with the per-segment stage times and peak VRAM from `benchmark_stats.json` recorded in the PR.

---

## WP13 — Perception quality and cost

**Closes:** M1, M2, M4, M6, M7, M8.
**Depends on:** WP01, WP12. Each change is gated by a measurement; the gate and the default are stated.

### M4 — detection cap and suppression (do first; it is a correctness fix)

In `detector.py:382-404`:

- Suppress a box only when it has the **same canonical label** as a kept box and IoU > `perception.duplicate_iou` (new, default `0.5`). Different classes never suppress each other. Hands are a class like any other under this rule.
- Replace the literal cap `6` with `perception.max_detections_per_frame` (new, default `30`).
- Tests (`tests/test_detector_postprocess.py`): factor the suppression into a pure function `suppress_duplicates(boxes, duplicate_iou, max_detections)` and test: overlapping `shoes` and `storage cabinet` both survive; two overlapping `shoes` boxes collapse to the higher-confidence one; the cap is honoured.

### M7 — batched inference

- Decode each frame once (`cv2.imread`), pass arrays to `model.predict(list_of_bgr_arrays, …)` in batches of `perception.batch_size` (new, default `8`). Ultralytics accepts a list of numpy arrays in BGR.
- Keep the per-frame post-processing loop unchanged; iterate results in order.
- No test beyond the existing suite (needs a GPU model); verify on Modal that detection counts for `demo04` equal the pre-change counts and record the stage time before and after.

### M1 — one segmenter where it is enough

- New `sam2.mode: always | fallback | off` (default `fallback`).
  - `fallback`: use the YOLOE mask when it exists and `mask_area / bbox_area >= 0.15`; call SAM 2 only for boxes that fail this.
  - `always`: today's behaviour. `off`: never call SAM 2.
- SAM 2 `set_image` is called only if at least one box in the frame needs it.
- **Gate.** `scripts/compare_masks.py --dataset-id <id>` runs both modes on the same keyframes and reports: mean IoU between YOLOE and SAM 2 masks per class, median shift of the lifted 3D centre between modes as a fraction of object size, and detect-stage time. Run on `demo01` and `demo04`. Keep `fallback` as default only if mean mask IoU ≥ 0.80 **and** median centre shift ≤ 10 % of object size on both. Otherwise set the default back to `always` and record the numbers in todo M1.
- Test: the mask-selection rule as a pure function (`choose_mask(direct_mask, bbox, min_area_ratio)`).

### M2 — re-identification

Two changes, separately gated.

1. **Appearance descriptor.** New `perception.reid_backend: hsv | dino` (default `hsv` until measured).
   - `dino`: DINOv2 ViT-S/14 (`facebook/dinov2-small` through `transformers`, already installed in the VGGT image; add `transformers>=4.48,<5` to `PERCEPTION_IMAGE`). Input: the box crop with pixels outside the mask set to the image mean, resized to 224 × 224, ImageNet normalisation. Output: the CLS embedding, L2-normalised, 384 floats.
   - Per-detection descriptors stay in memory during tracking. Persist one descriptor **per track**: the mean of its detections' embeddings, re-normalised, written to `outputs/objects/track_embeddings.npz` (`track_ids`, `embeddings`). `BoundingBox3D.appearance` keeps the HSV histogram for compatibility.
   - Distance for `dino` = `1 − cosine`. Thresholds are separate config values: `perception.reid_embedding_threshold` (default `0.35`, **to be tuned**), used in the tracker's dormant matching and, through `InstanceTrack.embedding`, in `association.py` and `matching.match_instances` tier 4 in place of the HSV distance when both sides have embeddings. Store `instance.appearance` as a JSON object `{"kind": "dino", "v": […]}` or `{"kind": "hsv", "v": […]}`; compare only like with like.
   - **Gate.** On `demo04` (the dataset with the most instances) and one recording with two same-coloured objects: count identity switches and duplicate instances with `hsv` and with `dino`. Switch the default to `dino` only if duplicates + switches go down and detect-stage time rises by less than 25 %.
2. **Tracker.** Keep the custom tracker. Replacing it with Ultralytics' built-in trackers or SAM 2 video propagation is not justified until annotated tracking metrics exist (`docs/evaluation_plan.md` §3: IDF1, ID switches). Record this as the decision in todo M2.

Tests: `1 − cosine` distance helper; like-with-like comparison rule; the embedding path is skipped cleanly when `transformers` is missing (falls back to `hsv` with one warning).

### M6 — hands (evaluation only)

Script `scripts/evaluate_hand_contact.py`: for a dataset with hand-labelled pickup and put-down times (a small JSON: `[{"object": "shoes", "pickup": 12.4, "putdown": 18.0}, …]`), report precision and recall of `pickup` and `placement` events within ±1 s. Run on `demo01` and `demo04`. Decision rule: if recall of `pickup` < 0.7, open a todo item to evaluate a dedicated hand-object detector; otherwise keep the open-vocabulary hand prompt. No model change in this WP.

### M8 — vision-language model

Decision recorded, no code: a VLM is called only when an event is created (to caption its evidence crop, cached on the run) and for relations with `relation_certain == False` (one closed question about the crop). Never per frame. This is Milestone 3 (todo 3.7). Add the two hook points as comments at the places they will be called: `runs.build_events` and `relations.classify_relation`'s caller.

---

## WP14 — Client and cleanup

**Closes:** A9, C7, C10, C11, C13, and "FR1.3 in the app" from todo 1.4.
**Depends on:** WP06.

### A9 — no fabricated answers in the app

`apps/mobile/lib/services/api_service.dart`:

- Delete `_mockQueryFallback` and `_mockTimelineFallback` and every call to them.
- `queryItem` on timeout, socket error or non-200: return a `QueryResult` with `found: false`, `locationSummary: "Can't reach Aegis memory. Check the connection and try again."`, `confidence: null`, and a new boolean `unreachable: true`. Add `unreachable` to the model (default `false`) and make `confidence` nullable in `models/query_result.dart`.
- `fetchTimeline` on failure: return an empty list and set a public `lastError` string the views can show.
- Patient view: when `unreachable` is true show the message in the neutral (not success) style and do not add it to the recent-search history.
- Timeouts: one constant `const requestTimeout = Duration(seconds: 5)`.
- If widget tests need canned data, put it in `apps/mobile/test/fixtures/` and inject it through the existing `http.Client` constructor parameter with `MockClient`.
- Tests (`apps/mobile/test/api_service_test.dart`): a client that throws → `unreachable == true`, `found == false`, no location text containing an anchor name; a 200 response parses as before; `confidence: null` parses.

### C13 — remaining Flutter items

- `home_screen.dart:542-544`: remove branching on dataset names. The simulation sheet is shown only when `GET /api/v1/health` reports `simulator_enabled: true` (add that boolean to `HealthResponse`, true when `AEGIS_ENABLE_SIMULATOR=1`), and it lists presets from the instances returned by `/scene_graph` instead of hard-coded scenarios.
- `flutter analyze` and `flutter test` must pass (CI already runs them).

### FR1.3 — pause/resume from the app

Server (`api.py`), available only when env `AEGIS_CAPTURE_DIR` is set (the directory passed to `aegis-ingest --output-root`) and `AEGIS_CAPTURE_PAUSE_FILE` is set (the path passed to `aegis-ingest --pause-file`):

- `GET /api/v1/capture/status` → `{"available": bool, "session_id": str | null, "status": str | null, "paused": bool, "frame_count": int | null, "last_frame_at": str | null}`. Read the newest session with `find_latest_live_session` and its `session_state.json`. `paused` = the pause file exists.
- `POST /api/v1/capture/pause` → create the pause file (empty). `POST /api/v1/capture/resume` → delete it. Both return the status object. When not configured: HTTP 503 with a clear message.
- Read `live_cli.py` and `live_pipeline.py` first to confirm the pause-file semantics (file present = paused) and adjust if it differs.

App: a "Recording" row in the home screen with a switch bound to these endpoints; hidden when `available` is false. Show "Paused" in the amber style.

Tests: `tests/test_capture_control.py` with `tmp_path` and monkeypatched env — status without configuration is `available: false`; pause creates the file; resume removes it; both are idempotent.

Until Milestone 4 adds auth these routes are unauthenticated like the rest of the API. Add them to the list in todo 4.2 ("protect mutating endpoints").

### C7 — dead code

- `core/paths.py`: delete `dust3r_model_path` (reads `config.dust3r`, which does not exist), `model_paths` and `calibration_model_path` if grep shows no callers.
- `core/config.py`: delete `DepthConfig`, `PoseConfig`, `GeometryConfig` and their YAML sections **only after** grepping `src/`, `tests/`, `run_pipeline.py`, `run_server.py`, `scripts/` for each field. `CameraConfig` self-calibration fields: delete those with no reader. Update `tests/test_config.py` accordingly.
- Remove the `dust3r` aliases: `workers.run_dust3r`, the `"dust3r"` stage name in `run_pipeline.py`, and messages mentioning dust3r.
- `DatasetPaths`: remove `depth`, `depth_manifest` if unused after the above.
- `AGENTS.md`: fix the stale path `src/aegis/poc/memory/scene_graph.py`; update the layout section for the new modules; replace "15 FPS / 648 frames" invariants that describe one demo with the general rule.

### C10 — split `workers.py`

- Move everything from `TRACK_PALETTE` to the end of `run_rerun` into `src/aegis/visualization/rerun_scene.py` as `build_rerun_recording(paths, config) -> dict`. `workers.run_rerun` becomes a thin wrapper that calls it and records benchmark stats. Update `tests/test_rerun_visualization.py` imports.
- Use the gravity frame for the room pillars (`up` instead of `−Y`) and anchor rotations.
- `_write_ply`: write binary little-endian PLY with one `numpy` structured array (`x, y, z` as `<f4`; `red, green, blue` as `u1`) and `tofile`. Test: header fields and that the byte length equals `header + 15 * n`.

### C11 — tests and coverage

- Add `pytest-cov` to the dev group (`uv add --dev pytest-cov`). CI runs `uv run pytest --cov=aegis --cov-report=term-missing --cov-fail-under=<N>` where `N` is the measured coverage after WP11, rounded down to a multiple of 5. Record `N` in the PR.
- Confirm these regression tests exist (each was specified above): vertical relations (`test_relations.py`), multi-session identity (`test_ingest.py`), the rename bug (`test_api.py::test_rename_only_touches_the_renamed_room`), no fabricated anchor (`test_scene_graph.py`).

---

## WP15 — Measurements and recorded evidence

**Closes:** todo 1.4 (AC-01, AC-02, AC-03, AC-29), 2.6 (AC-04), 2.8 (AC-22, SC9), and the measurement notes of §5.2.

Each item is a protocol plus a script that writes a JSON result under `outputs/evaluation/`. Every result file starts with the same header, produced by a shared helper `scripts/_evidence.py::run_header()`:

```json
{"git_commit": "…", "git_dirty": false, "config_path": "…", "config_sha256": "…",
 "model_ids": {"vggt": "…", "detector": "…", "sam2": "…"},
 "hardware": {"laptop": "…", "phone": "…", "gpu": "…"}, "recorded_at": "<UTC ISO>", "operator": "…"}
```

`hardware.laptop` and `hardware.phone` are passed on the command line (`--laptop`, `--phone`); the script refuses to run without them. A result is valid only with `git_dirty: false`.

Nothing here can be ticked from a simulated clock. If a run misses its target, record the miss.

### P1 — One-hour soak (NFR-R1, AC-01)

1. Phone on charger, IP Webcam streaming, laptop on mains. Free disk ≥ 10 GB.
2. `uv run aegis-ingest --url <stream> --config-path config/live.yaml --max-duration 3600 --session-id soak_<date>`.
3. Walk through at least three rooms; leave the phone static for at least 10 minutes in the middle.
4. `uv run python scripts/summarise_live_session.py captures/soak_<date> --laptop … --phone …` → `outputs/evaluation/soak_<date>.json` with: wall duration, frames received, frames kept, effective FPS (must be ≥ 1), gap count and total gap seconds by reason, max and p95 inter-frame interval, bytes on disk, mean JPEG size, crashes (0).
5. Pass: duration ≥ 3600 s, effective received FPS ≥ 1, no crash, no `storage_error` status.

The script reads `session.json` and `index.jsonl` only; write it so it also works on any past session.

### P2 — Disconnect recovery (AC-03)

During a capture, switch the phone's Wi-Fi off for 10 s (stopwatch), three times, at least 2 minutes apart. The summary script lists each `disconnect` gap with `started_at`, `ended_at` and `resume_seconds` (first frame after the gap minus the gap start). Pass: all three resume in ≤ 15 s and each is recorded as a gap.

### P3 — Keyframe selection (AC-02)

1. Script a 2-minute clip with exactly 5 deliberate scene changes at noted times (turn to a different wall or room), with still periods between.
2. Capture it live with keyframe selection on. Write the change times to `captures/<session>/scene_changes.json` (`[{"t": seconds_from_start}, …]`).
3. `scripts/evaluate_keyframes.py <session>`: a change is detected if a kept frame exists within 2 s after it. Report detected / 5, kept-frame count, duplicates suppressed. Pass: ≥ 4 of 5.

### P4 — Backlog under a stalled consumer (NFR-P2, AC-29)

1. Add debug flags to `aegis-ingest`: `--inject-stall-at SECONDS --inject-stall-for SECONDS`, which make the storage step sleep once. Read `buffer.py` and `live_pipeline.py` first: use the existing backlog counters; if `session.json` does not already record `max_backlog_frames` and `max_backlog_seconds`, add them (plus a test in `tests/test_live_buffer.py`).
2. Run 10 minutes with `--inject-stall-at 300 --inject-stall-for 10` on the real phone stream.
3. Result: max backlog frames and seconds, frames dropped, time to drain. Pass: max backlog ≤ 30 s and the stall is recorded as a gap or drop count, not silent loss.

### P5 — Reconstruction limit and throughput (inputs for WP12 defaults)

`scripts/measure_vggt_window.py`: run the `vggt` stage on the first N keyframes of one long dataset for N ∈ {32, 64, 96, 120, 160}; record peak VRAM, time, and success/OOM. Set `vggt.max_keyframes` and `live.segment_frames` to the largest N with peak VRAM ≤ 85 % of the L4's memory. Record seconds of pipeline time per second of video for a full segment (must be < 1 for the live path to keep up; report the number either way).

### P6 — Object placement accuracy (AC-04, Iteration 1 exit criterion)

1. Record one session: 5 distinct objects, each placed at a known anchor and relation, written beforehand in `ground_truth.json`: `[{"object": "keys", "anchor": "desk", "relation": "on_surface", "room": "…"}, …]`. Include at least one `under`, one `inside` and one `on_floor`. Move two objects during the recording and note their final places.
2. Process and ingest. `scripts/evaluate_placements.py --home-id … --ground-truth …` compares each object's last-known canonical anchor and relation with the ground truth and counts duplicate identities (instances per ground-truth object − 1).
3. Pass: ≥ 70 % correct (anchor **and** relation), ≤ 20 % duplicates. Report per-object results and `gravity.json`.
4. Repeat with 10 placements for the Iteration 1 criterion (≥ 70 % last-location correct).

### P7 — Rooms (AC-22, SC9)

Annotation format `rooms_ground_truth.json` for one multi-room recording (≥ 3 rooms, at least one revisit):

```json
{"rooms": [{"name": "Kitchen", "intervals": [[0.0, 41.5], [120.0, 150.2]]}, …],
 "transitions": [{"t": 41.5, "from": "Kitchen", "to": "Hallway"}, …],
 "queries": [{"item": "keys", "room": "Kitchen"}, …]}
```

`scripts/evaluate_rooms.py --dataset-id … --ground-truth …` (definitions follow `docs/evaluation_plan.md` §3 "Rooms"):

- Map each predicted room to the ground-truth room it overlaps most in keyframe time (one-to-one, greedy by overlap).
- **Segmentation accuracy** = keyframes whose predicted room maps to the ground-truth room at that time / all keyframes. Target ≥ 0.90.
- **Region precision / recall** = predicted rooms that map to a distinct ground-truth room / predicted rooms; ground-truth rooms that received a predicted room / ground-truth rooms.
- **`room_change` F1** with ±1 s tolerance, one-to-one matching in time order. Target ≥ 0.70.
- **Correct-room query rate** over `queries`, after the caregiver rename step has been applied to the home (rename the rooms through the API to the ground-truth names, then query). Target ≥ 0.90.

Add `tests/test_room_evaluation.py` with a synthetic ground truth and prediction to pin the metric arithmetic (perfect prediction → 1.0 everywhere; one late transition outside tolerance → F1 drops as computed by hand).

### P8 — Activity order (AC-05) and storage (AC-07)

- AC-05: record a scripted sequence of 10 actions with noted times; run `scripts/evaluate_activity_order.py` (same matching as the WP09 harness test). Target ≥ 70 % in the correct order. Use a ±2 s time tolerance, because the reference times are noted by hand, and write the tolerance into the result file.
- AC-07: attach `outputs/evaluation/store_growth.csv` from WP11, plus one real number: the size of `memory.db` and the evidence directory after ingesting all recordings made for P1–P7.

### Documentation closed by this WP

- `context/todo.md`: tick 1.4, 2.6, 2.8 items with the result file paths; update §0 status rows.
- `docs/live_capture.md`: the segment workflow and the new flags.
- `docs/evaluation_plan.md`: replace relation names with the new set; point the room section at `scripts/evaluate_rooms.py`.
- `docs/artifact_contracts.md`: gravity artifact, graph v2, timeline file, home store, evidence, JPEG frames, segments.

---

## Appendix A — Traceability: every todo item to its plan

### Milestone 1 (§1.4)

| Todo item | Plan |
|---|---|
| NFR-R1 / AC-01 physical soak | WP15 P1 |
| AC-03 disconnect on the real stream | WP15 P2 |
| AC-02 scripted keyframe clip | WP15 P3 |
| AC-29 / NFR-P2 backlog measurement | WP15 P4 |
| FR1.3 pause/resume in the app + endpoint | WP14 |
| Stop re-encoding promoted frames to PNG | WP12 (C12) |
| Micro-batch the live path | WP12 (segments) |
| Wall-clock capture time in the scene graph | WP05 (A8), stored in WP07 |

### Milestone 2

| Todo item | Plan |
|---|---|
| 2.3 `home_id` in config/metadata | WP07, WP08 |
| 2.3 load registry before building, apply matched labels | WP07 `match_rooms` at ingest + WP08 (labels live in the store; the per-session graph stays session-local by design) |
| 2.3 rename writes `home_map.json` | WP08 |
| 2.3 rename bug | WP06 (C3) |
| 2.3 cross-session matching with per-session origins | WP07 matching (symbolic; continuity; no proximity) |
| 2.3 tests incl. AC-31 | WP08 |
| 2.4 persistence technology, summary format/trigger | §0.3, WP07, WP11 |
| 2.4 state runs instead of per-keyframe timeline | WP05 (session), WP07 (store) |
| 2.4 hot tier, background job, summaries, last-known kept | WP11 |
| 2.4 room labels survive, summarised flag, failure flag | WP11 |
| 2.4 growth curve, before/after accuracy, tests | WP11, WP15 P8 |
| 2.5 activity definition, grouping, API, summaries | WP09 |
| 2.5 ground-truth order test (AC-05) | WP09 harness, WP15 P8 |
| 2.6 remove demo rules | WP05 (C1) |
| 2.6 confidence on every observation | WP05 |
| 2.6 gravity-aligned height and vertical relations | WP02, WP03, WP04, WP05 |
| 2.6 oriented-box vertical axis | WP03 (C2) |
| 2.6 AC-04 recorded run | WP15 P6 |
| 2.7 restart-equivalence test | WP06 (JSON), WP07 (store) |
| 2.7 cache invalidation | WP06 |
| 2.7 corrupt graph at API level | WP06 |
| 2.7 append-only vs rebuilt | WP07 (append-only across sessions; documented) |
| 2.8 annotate, measure, record | WP15 P7 |

### §6 improvements

| Item | Plan | Item | Plan |
|---|---|---|---|
| A1 | WP07 | M1 | WP13 |
| A2 | WP05, WP07 | M2 | WP13 |
| A3 | WP02 (unit), WP07 (symbolic matching, 2D alignment) | M3 | WP12 (stride 1 in segments) |
| A4 | WP02 | M4 | WP13 |
| A5 | WP12 | M5 | WP12 |
| A6 | WP06, WP07 | M6 | WP13 (evaluation + decision rule) |
| A7 | WP01 | M7 | WP13 |
| A8 | WP05, WP07 | M8 | WP13 (decision; code in M3) |
| A9 | WP14 | C1 | WP05 |
| A10 | WP12 (segments, warm models); parallel detect deferred with reason | C2 | WP03 |
| A11 | WP10 | C3 | WP06 |
| C4 | WP01, WP04, WP05 | C5 | WP06 |
| C6 | WP02 | C7 | WP14 |
| C8 | WP01, WP06 | C9 | WP06 |
| C10 | WP14 | C11 | WP14 (+ tests in each WP) |
| C12 | WP12 | C13 | WP14 |

---

## Appendix B — Known limitations this plan accepts

State these in the report rather than hiding them.

1. **Anchor identity across sessions can be ambiguous** when a room has several anchors of one type and fewer than two other anchors to align on. Such matches are marked `ordinal` and should lower answer confidence (Milestone 3 uses `anchor.match_quality`).
2. **Rooms with identical signatures can merge** (two bare rooms each containing only a desk). The calibration walkthrough and caregiver naming reduce this; it is not eliminated.
3. **Tier 3 instance matching merges a replaced object** with the original when exactly one object of that class existed before and one is seen now.
4. **Scale is assumed, not measured.** `unit` comes from an assumed camera height of 1.4 and is clamped to [0.5, 2.0]. Relation tolerances are relative to object and anchor size, so they do not depend on it; clustering and association radii do.
5. **Storage cabinet groups cabinet, cupboard and shelf** as today. An open shelf is treated as a container. Splitting them changes existing labels and needs a re-evaluation.
6. **Segments do not share geometry.** An object visible only across a segment boundary is matched symbolically. A relation that needs both segments' geometry cannot be computed.
7. **Evidence crops may contain incidental background** inside the object's bounding box. Decision #9 must be confirmed with the supervisor before the report claims a privacy property for them.
8. **Gravity needs visible floor.** Sessions that never see the floor fall back to the camera prior with confidence 0.2; in those sessions `under`, `above` and `on_floor` are reported as `near`.


---
---

# Part II — Implementation Plan for Milestone 3 (Voice Agent) and Milestone 4 (Portal & Testing)

**Written:** 2026-11-16 against `feat/memory-plan` @ `c69cc9c` (326 tests pass, Ruff clean, coverage 80%). Milestones 1 and 2 (WP01–WP15) are treated as done.
**Covers:** every open item in `context/todo.md` §3.2–§3.7, §4.2–§4.6, §5.1 and §5.2, and decisions #1–#5, #8, #9, #11, #12.
**Sources read:** the whole of `src/aegis`, `apps/mobile`, `tests`, `run_server.py`, `run_pipeline.py`, `context/specification.md` (restatement of `fyp_report/main.pdf`), `fyp_report/chapters/*`.

Part II continues the WP numbering (WP16–WP35). §0.1 rules 3–10 of Part I still apply. Part II adds its own rules, facts and decisions below.

---

## II.0 How to use Part II

### II.0.1 Additional rules

1. Branch from the branch that contains WP01–WP15 (`feat/memory-plan` today, `develop` once it is merged). One branch per WP: `feat/wp<NN>-<slug>`. Commit after every feature or fix.
2. Never add an AI or assistant attribution to a commit, PR or contributor list (`CLAUDE.md`). No `Co-Authored-By` trailer.
3. Flutter is **not installed** on the development laptop. If `flutter` is on `PATH`, run `flutter analyze --no-fatal-infos && flutter test` in `apps/mobile`. If it is not, push the branch and read the `flutter-ci` job. Do not tick a Flutter todo item until that job is green.
4. Every new wall-clock value goes through `aegis.core.timeutil` (`to_utc_iso`, `parse_iso`). Never call `datetime.now()` in query, auth or privacy code. Take `now` as a parameter; the API gets it from `remote/settings.py::current_time()` (WP16).
5. Every answer sentence comes from a template in `memory/reasoning.py`. No f-string answer text in `api.py` or `answering.py`. This is what keeps the two-sentence rule testable.
6. A non-abstaining answer without an evidence item is a bug. The answer engine downgrades it to an abstention (WP20) rather than send it.
7. New runtime dependencies allowed by Part II, and only these: `sqlcipher3`, `cryptography` (WP27). Optional dependency group `speech`: `faster-whisper` (WP23). Optional group `llm`: `anthropic` (WP24). Flutter: `speech_to_text`, `shared_preferences`, `crypto`.
8. Security code fails closed. An unreadable token, a missing grant, a store that cannot be opened or a scope that is not listed means "deny", never "allow".
9. Do not weaken an existing test to make a security change pass. Tests that predate auth keep working because `tests/conftest.py` sets `AEGIS_AUTH_DISABLED=1` (WP26); new security tests remove that variable.

### II.0.2 Facts about the system after Milestones 1–2 that Part II relies on

| Fact | Where | Consequence |
|---|---|---|
| Two read paths exist. `home_id` reads the SQLite home store through `StoreRepository`; `dataset_id` reads one session's `r4d_scene_graph.json` through `JsonGraphRepository`. | `remote/api.py::resolve_repository` | Wall-clock history, summaries and evidence rows exist only in the home store. All temporal features are home-store features. |
| `HomeStore.latest_states()` returns `last_seen_timestamp: None` and `is_active_view: False`. `query_memory` sorts matches by `last_seen_timestamp`. | `memory/store.py:468-500`, `api.py:590` | For a home store the "most recent" instance is arbitrary today. Fixed in WP16. Store answers are always worded "was last seen". |
| `instance.last_confidence` is the run confidence: mean detector score of the run, already multiplied by 0.6 when the relation is uncertain. | `memory/runs.py:166-182` | Do not penalise an uncertain relation a second time. |
| `anchor.match_quality` is one of `unique, aligned, resident, ordinal, new`. | `store.py:66` | `ordinal` is a guess (Appendix B.1) and lowers answer confidence. |
| `event.evidence_id` is never written. Evidence rows hang off `state_run.evidence_id`. Carried runs have no crop. | `memory/ingest.py`, `memory/evidence.py:59` | Evidence for an event is the crop of the run that begins when the event ends. |
| Summary periods are **local calendar dates** (`YYYY-MM-DD`, zone `memory.retention.timezone`). `HomeStore.summaries(start, end)` compares only the first ten characters of its arguments. | `store.py:436-466`, `compaction.py` | Pass local date strings, not UTC timestamps. `get_timeline` passes UTC today; fixed in WP29. |
| Compaction never deletes `session`, `room`, `anchor`, `instance` rows or the run behind each last-known state. | `compaction.py` docstring | Recording coverage ("was the camera on?") can be answered for any past period from `session`. |
| Object summary sidecar: `{instance_id, canonical, label, last:{relation, relation_certain, anchor_id, room_id, at}, rooms, anchors, event_types, moves, source_runs, source_events}`. `moves` is filled only for `importance: high` objects. Activity sidecar: `{room_id, start_at, end_at, event_types, instance_ids, anchor_ids}`; rolled-up activity sidecar: `{visits, seconds_by_room}`. | `memory/summaries.py` | Summarised answers have day granularity for normal objects and exact move times only for important ones. |
| The API does not load a `RuntimeConfig`. It is configured only by environment variables. | `remote/api.py` | WP16 adds `remote/settings.py` so thresholds live in YAML. |
| CORS is a wildcard with credentials. There is no auth. `GET /simulate/*` mutates memory. | `api.py:46-53, 1000-1037` | WP26. |
| The store is plaintext SQLite; `open_store` is the single place a connection is made. | `store.py:570-585` | WP27 replaces the driver there. |
| Raw imagery exists in four places: `captures/<session>/frame_*.jpg`; the promoted dataset directory (`PromotionResult.dataset_dir`) with `frames/`; `outputs/<dataset_id>/` (the `.rrd` contains video); the Modal volume `/data/<dataset_id>/`. | `ingestion/live_storage.py:144`, `live_handoff.py`, `run_pipeline.py:476-545` | The 24-hour purge (WP28) must cover all four. |
| The Flutter client always sends `dataset_id`, never `home_id`. It branches on dataset names for its quick tiles and titles. The caregiver card states "All tracked items are safely stored…" and "Fall Hazard" without server evidence. "Tap to Ask by Voice" re-submits the text field. | `apps/mobile/lib/views/patient/patient_view.dart:29-103, 415-422`, `caregiver_view.dart:171-190` | WP30–WP32 remove all three. |
| Theme colours used for text fail WCAG AA on the white card (measured 2026-11-16): `primaryTeal #D97706` 3.19, `tealAccent #EAB308` 1.92, `royalAmethyst #CA8A04` 2.94, `alertAmber #F59E0B` 2.15, `tertiaryLabel #A8A29E` 2.52, `#C084FC` 2.64, `systemGreen` 2.22, `systemRed` 3.55, `systemBlue` 4.02, white on `primaryTeal` 3.19. `textMuted #78716C` is 4.80 on white but 4.48 on the canvas `#FAF7F0`. | `apps/mobile/lib/theme/app_theme.dart` | WP30 replaces text colours; values are given there. |
| `sqlcipher3` 0.6.5 installs as a self-contained wheel on Python 3.12 / Linux (SQLCipher 4.20.0). Verified: WAL mode, `sqlite.Row`, `PRAGMA user_version`, `BEGIN IMMEDIATE`, wrong key raises `DatabaseError: file is not a database`, a plaintext file opens without a key, and `ATTACH … KEY` + `sqlcipher_export` converts a plaintext database. | scratch test, 2026-11-16 | WP27 can depend on it. |

### II.0.3 Decisions Part II makes

| # (todo §7) | Decision | Status |
|---|---|---|
| 1 | Benchmark = the team's own scripted multi-room phone recordings, `Aegis-TestSet-v1` (WP33). An Ego4D subset stays a secondary, optional set. | Decided here; record in the report before any number is reported |
| 2 | Speech: on-device platform recognition in the app (`speech_to_text`). A server endpoint (`faster-whisper`, CPU) exists for the reproducible AC-13 measurement and for clients without on-device recognition. | Decided here |
| 3 | Rule-based parsing and retrieval stay primary. An LLM may only turn a sentence into a `ParsedQuery`; it never words an answer and never sees memory. Off by default (WP24). | Decided here; WP24 is optional |
| 4 | Local accounts in the home store. Passwords: `hashlib.scrypt`. Sessions: opaque random tokens, SHA-256 stored, 60-minute lifetime. Grants are checked on **every** request, so a revocation takes effect on the next request. | Decided here |
| 5 | Database: SQLCipher (AES-256). Evidence crops and `home_map.json`: AES-256-GCM. Key outside the store directory. Transport: TLS on the gateway with a self-signed certificate the app pins by fingerprint. | Decided here |
| 8 | `query.abstain_below` ships at **0.25** and is replaced by the value read from the precision/abstention curve (`scripts/abstention_curve.py`, WP33). | Default decided; value must be measured |
| 9 | Evidence crops are kept past 24 hours as derived evidence. | **Still needs supervisor confirmation.** `memory.evidence.enabled: false` reverses it; WP20's text fallback keeps answers grounded without images. |
| 11 | Iteration 3 = WP16–WP24 and WP33. Iteration 4 = WP25–WP32, WP34, WP35. Owners in §II.0.4. Dates are the team's to set. | Scope decided; dates open |
| 12 | Room calibration UI lives in the caregiver view behind the `rooms` scope. | Decided here |
| — | One home per server. `AEGIS_HOME_ID` names it; a request for another home is refused when auth is on. | Decided here (constraint C5) |
| — | Temporal questions are answered only from the home store. On a `dataset_id` they return `status: "unsupported"`. | Decided here |
| — | The server clock is the reference for "now". `AEGIS_NOW` overrides it for tests and recorded demos; every answer carries `as_of`, and `/health` reports `clock_override`. | Decided here |

### II.0.4 Work packages, order and todo coverage

| WP | Title | Depends on | Owner | Todo items closed |
|---|---|---|---|---|
| 16 | Query foundations: settings, clock, store schema v2, repository reads | — | M-C | groundwork; fixes store ordering bug |
| 17 | Time words: saying and parsing relative time | 16 | M-C | 3.3 (parser), 3.4 (real relative time) |
| 18 | Query parser and intent routing | 17 | M-C | 3.3 (routing) |
| 19 | Confidence, freshness and abstention | 16, 17 | M-C | 3.4, 3.5; AC-12, AC-28 |
| 20 | Evidence references and real crops | 19 | M-C | 3.6; AC-11 |
| 21 | Temporal answers over detailed and summarised tiers | 18, 20 | M-C | 3.3; AC-10, AC-23 at query level |
| 22 | Clarification, query log, `/ask` endpoint | 21 | M-C | 3.7 (clarification, log) |
| 23 | Speech input | 22 (server), 31 (app) | M-C | 3.2; AC-13 tooling |
| 24 | Optional LLM query planner | 22 | M-C | 3.7 (optional agent); may be deferred with a reason |
| 25 | Accounts, sessions, grants, consent, audit (store level) | 16 | M-D | 4.2 (mechanism, login, grants, consent) |
| 26 | API enforcement, scopes, CORS, access endpoints | 22, 25 | M-D | 4.2 (all), 4.3 (scope, audit); AC-16, AC-17, AC-18, AC-26 |
| 27 | Encryption at rest and TLS | 25 | M-D | 4.3 (TLS, AES-256); AC-20 |
| 28 | Raw-frame purge, history deletion, privacy statement | 26, 27 | M-D | 4.3 (purge, deletion, statement); AC-30, AC-20 |
| 29 | Portal API: object states, daily summary, sessions, timeline filters | 22, 26 | M-D | 4.4 (server side) |
| 30 | App foundation: session, settings, text size, contrast, API client | 26, 29 | M-D | 4.4 (base), 4.5 (text sizes, contrast) |
| 31 | App: patient view (ask, voice, evidence, clarification) | 30 | M-D | 3.2 (microphone), 4.4 (evidence display) |
| 32 | App: caregiver portal and primary-user controls | 30 | M-D | 4.4 (all remaining) |
| 33 | Benchmark `Aegis-TestSet-v1` and runner | 22 | Team | 5.1 (tooling), decision #8 curve |
| 34 | Measurements and recorded evidence | all | Team | 3.x and 4.x measurements, 4.6, 5.1 (results) |
| 35 | Report and documentation | all | Team | 5.2 |

WP16–WP22 are strictly sequential. WP25–WP28 can run in parallel with WP17–WP22 after WP16. WP33 can start after WP22.

### II.0.5 Target layout after Part II

```
src/aegis/core/config.py            WP16  + QueryConfig, AuthConfig, PrivacyConfig, SpeechConfig
src/aegis/core/timewords.py         WP17  describe_when, parse_time_window
src/aegis/core/keys.py              WP27  store key loading / generation
src/aegis/core/crypto.py            WP27  AES-256-GCM file protection
src/aegis/memory/store.py           WP16  schema v2, migration, new reads; WP27 SQLCipher
src/aegis/memory/query_parser.py    WP18  ParsedQuery, parse_query
src/aegis/memory/confidence.py      WP19
src/aegis/memory/answering.py       WP19–WP22  the answer engine (no FastAPI imports)
src/aegis/memory/reasoning.py       WP19–WP21  every answer template
src/aegis/memory/auth.py            WP25
src/aegis/memory/privacy.py         WP28  purge, deletion, verification
src/aegis/memory/portal.py          WP29  object states, daily summary
src/aegis/memory/cli.py             WP25, WP27, WP28  new sub-commands
src/aegis/remote/settings.py        WP16
src/aegis/remote/security.py        WP26
src/aegis/remote/maintenance.py     WP28
src/aegis/remote/api.py             all   routes only
src/aegis/speech/transcriber.py     WP23
src/aegis/llm/planner.py            WP24  (optional)
src/aegis/evaluation.py             WP23, WP33  word_error_rate, benchmark scoring
scripts/abstention_curve.py, run_benchmark.py, evaluate_speech.py,
        measure_query_latency.py, verify_encryption.py, verify_purge.py     WP23, WP27, WP28, WP33, WP34
benchmark/aegis_testset_v1/         WP33
docs/privacy_limitations.md, docs/usability_protocol.md, docs/security.md   WP27, WP28, WP34
apps/mobile/lib/...                 WP30–WP32 (file list in WP30)
```

### II.0.6 Environment variables (complete list after Part II)

| Variable | Meaning | Set by |
|---|---|---|
| `AEGIS_HOME_ID` | The one home this server serves. Default `home01`. | `run_server.py --home-id` |
| `AEGIS_STORE_ROOT` | Store root (exists today). | tests, operator |
| `AEGIS_CONFIG` | YAML runtime config for the API. Unset = defaults. | `run_server.py --config` |
| `AEGIS_NOW` | ISO-8601 time with zone that replaces the server clock. | tests, recorded demos |
| `AEGIS_AUTH_DISABLED` | `1` turns auth off (developer mode). | `tests/conftest.py`, `run_server.py --no-auth` |
| `AEGIS_CORS_ORIGINS` | Comma-separated exact origins. | operator |
| `AEGIS_STORE_KEY` / `AEGIS_STORE_KEY_FILE` | 64 hex characters / path to a file holding them. | operator |
| `AEGIS_REQUIRE_ENCRYPTION` | `1` = refuse to open a store without a key. | `run_server.py` (unless `--allow-plaintext`) |
| `AEGIS_DISABLE_MAINTENANCE` | `1` = do not start the hourly maintenance thread. | `tests/conftest.py` |
| `AEGIS_CAPTURE_DIR`, `AEGIS_CAPTURE_PAUSE_FILE`, `AEGIS_ENABLE_SIMULATOR`, `AEGIS_TEST_FIXTURE_ROOT`, `AEGIS_DATASET_ID`, `AEGIS_VOCABULARY_FILE` | Unchanged. | — |
| `AEGIS_LLM_PLANNER` | `1` enables WP24. | operator |

---

## WP16 — Query foundations

**Goal:** give the API a config and a clock, add every table Part II needs in one schema migration, add the store reads the answer engine needs, and fix the ordering bug.

### Files
- New: `src/aegis/remote/settings.py`, `tests/test_settings.py`, `tests/test_store_v2.py`.
- Change: `src/aegis/core/config.py`, `src/aegis/memory/store.py`, `src/aegis/memory/repository.py`, `src/aegis/remote/api.py`, `config/demo.yaml`, `config/live.yaml`, `tests/conftest.py`.

### Config (`core/config.py`)

Add four flat frozen dataclasses (same style as `RetentionConfig`) and four fields on `RuntimeConfig` (`query`, `auth`, `privacy`, `speech`). Parse each with `_section(Cls, raw.get("<name>"), "<name>")` inside `RuntimeConfig.from_mapping`. If `from_mapping` checks top-level keys, add the four names.

```python
@dataclass(frozen=True, slots=True)
class QueryConfig:
    fresh_hours: float = 6.0             # NFR-R3
    abstain_below: float = 0.25          # decision #8; replace after WP33
    recency_half_life_hours: float = 72.0
    min_recency_factor: float = 0.5
    ordinal_anchor_factor: float = 0.7   # anchor.match_quality == "ordinal"
    single_observation_factor: float = 0.8
    max_options: int = 4                 # clarification list length
    day_start_hour: int = 5
    noon_hour: int = 12
    evening_hour: int = 17
    breakfast_hour: int = 8
    lunch_hour: int = 13
    dinner_hour: int = 20
    log_queries: bool = True
    log_retention_days: int = 30

@dataclass(frozen=True, slots=True)
class AuthConfig:
    session_minutes: int = 60
    max_failed_logins: int = 5
    lockout_minutes: int = 15
    invite_hours: int = 72
    audit_retention_days: int = 30       # NFR-S3
    min_password_length: int = 8

@dataclass(frozen=True, slots=True)
class PrivacyConfig:
    raw_retention_hours: float = 24.0    # NFR-S4
    purge_session_outputs: bool = True
    exempt_datasets: str = ""            # comma-separated ids of consented test recordings

@dataclass(frozen=True, slots=True)
class SpeechConfig:
    confirm_below: float = 0.80          # FR6.3
    model: str = "base.en"
    max_seconds: float = 15.0
    max_bytes: int = 2_000_000
```

Validation in `__post_init__` (raise `ValueError` with the section name): `0 < abstain_below < 1`; `fresh_hours > 0`; `0 < min_recency_factor <= 1`; `0 <= day_start_hour < noon_hour < evening_hour <= 23`; meal hours in `0..23`; `session_minutes >= 5`; `max_failed_logins >= 1`; `min_password_length >= 8`; `raw_retention_hours > 0`; `0 < confirm_below <= 1`.

Add the four sections with their defaults, commented, to `config/demo.yaml` and `config/live.yaml`.

### `remote/settings.py`

```python
@lru_cache(maxsize=1)
def get_settings() -> RuntimeConfig:
    path = os.getenv("AEGIS_CONFIG")
    return load_config(path) if path else RuntimeConfig.from_mapping({})

def reset_settings() -> None: get_settings.cache_clear()

def clock_overridden() -> bool: return bool(os.getenv("AEGIS_NOW"))

def current_time() -> datetime:
    """Server time (UTC). AEGIS_NOW replaces it for tests and recorded demos."""
    override = os.getenv("AEGIS_NOW")
    return parse_iso(override).astimezone(UTC) if override else utc_now()

def local_zone() -> ZoneInfo: return ZoneInfo(get_settings().memory.retention.timezone)

def server_home() -> str: return validate_dataset_id(os.getenv("AEGIS_HOME_ID") or "home01")
```

`current_time()` is read on every call (not cached), so `monkeypatch.setenv("AEGIS_NOW", ...)` works inside a test.

### Store schema v2 (`memory/store.py`)

Set `SCHEMA_VERSION = 2`. Keep `_SCHEMA` unchanged and add `_SCHEMA_V2`:

```sql
CREATE TABLE query_log (
  query_id INTEGER PRIMARY KEY,
  asked_at TEXT NOT NULL,
  user_id INTEGER, username TEXT, role TEXT,
  modality TEXT NOT NULL CHECK (modality IN ('text','speech')),
  text TEXT NOT NULL,
  intent TEXT NOT NULL,
  status TEXT NOT NULL,
  instance_id INTEGER,
  evidence TEXT,               -- JSON list of observation ids
  confidence REAL,
  tier TEXT,
  latency_ms INTEGER
);
CREATE INDEX query_log_asked ON query_log(asked_at);

CREATE TABLE user (
  user_id INTEGER PRIMARY KEY,
  username TEXT NOT NULL UNIQUE COLLATE NOCASE,
  role TEXT NOT NULL CHECK (role IN ('primary','caregiver')),
  display_name TEXT,
  password_hash TEXT,          -- NULL until an invited caregiver accepts
  invite_hash TEXT,
  invite_expires_at TEXT,
  status TEXT NOT NULL CHECK (status IN ('active','invited','disabled')),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE access_grant (
  grant_id INTEGER PRIMARY KEY,
  caregiver_id INTEGER NOT NULL REFERENCES user(user_id),
  granted_by INTEGER NOT NULL REFERENCES user(user_id),
  scopes TEXT NOT NULL,        -- JSON list
  history_days INTEGER,        -- NULL = no limit
  granted_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  expires_at TEXT,
  revoked_at TEXT
);
CREATE INDEX access_grant_caregiver ON access_grant(caregiver_id);

CREATE TABLE auth_session (
  token_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES user(user_id),
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  revoked_at TEXT
);

CREATE TABLE consent (
  consent_id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES user(user_id),
  kind TEXT NOT NULL CHECK (kind IN ('capture','caregiver_access')),
  subject_id INTEGER,          -- caregiver user_id for caregiver_access
  statement_version TEXT NOT NULL,
  given_at TEXT NOT NULL,
  withdrawn_at TEXT
);

CREATE TABLE audit_log (
  audit_id INTEGER PRIMARY KEY,
  at TEXT NOT NULL,
  username TEXT NOT NULL,      -- as typed; unknown names are logged too
  user_id INTEGER,
  role TEXT,
  action TEXT NOT NULL,
  result TEXT NOT NULL CHECK (result IN ('allowed','denied','error')),
  reason TEXT,
  detail TEXT,
  remote_addr TEXT
);
CREATE INDEX audit_log_at ON audit_log(at);
```

Opening logic in `HomeStore.__init__`:

- `user_version == 0`: run `_SCHEMA`, then `_SCHEMA_V2`, set `user_version = 2`, insert the `meta` rows as today.
- `user_version == 1`: call `wal_checkpoint(TRUNCATE)`, copy the file to `memory.v1.bak.db` beside it (skip if that file already exists), then inside one `BEGIN IMMEDIATE … COMMIT` run `_SCHEMA_V2` statement by statement and set `user_version = 2`. `executescript` commits implicitly, so split `_SCHEMA_V2` on `;` and use `execute`.
- `user_version > SCHEMA_VERSION`: unchanged (raise).

Add the six table names to `TABLES`. Keep two tuples for later WPs: `HISTORY_TABLES = ("evidence", "event", "state_run", "activity", "room_visit", "summary", "compaction_log", "query_log", "instance", "anchor", "session", "room")` (this order is a safe delete order under the foreign keys) and `ACCOUNT_TABLES = ("auth_session", "consent", "access_grant", "audit_log", "user")`.

### New store reads (all SQL stays in `store.py`)

Every method returns plain `dict`s with names resolved, like `events()` does.

| Method | SQL rule | Returns |
|---|---|---|
| `latest_states()` (extend) | add `LEFT JOIN state_run sr ON sr.run_id = i.last_run_id` and select `a.match_quality` | adds keys `run_id`, `run_start_at`, `observation_count` (of that run; `None` if no run), `anchor_match_quality`, `importance`, `session_id` |
| `sessions_between(start, end)` | `ended_at >= start AND started_at <= end`, either bound optional | session rows |
| `room_visits(start, end)` | `v.end_at >= start AND v.start_at <= end`, `LEFT JOIN room` | `{visit_id, room_id, room_label, start_at, end_at, session_id}` ordered by `start_at` |
| `run_at(instance_id, at)` | `instance_id = ? AND start_at <= ? ORDER BY start_at DESC, run_id DESC LIMIT 1` with anchor and room labels | one run dict or `None` |
| `runs_in_window(instance_id, start, end)` | `end_at >= start AND start_at <= end` | run dicts ordered by `start_at` |
| `run_starting_at(instance_id, at)` | first run with `start_at >= shift_iso(at, -1.0)` ordered by `start_at` | run dict or `None` (the run an event led to) |
| `events_for_instance(instance_id, start=None, end=None, types=None)` | call `events(start, end)`, filter in Python | event dicts |
| `object_summaries(instance_id, start_date=None, end_date=None)` | call `summaries(start_date, end_date)`, keep `kind == "object"` and `subject_key == f"instance:{id}"` | newest last |
| `evidence_row(evidence_id)` | by primary key | `{evidence_id, path, captured_at, instance_id, session_id, width, height, bytes}` or `None` |
| `log_query(**values)` | `insert("query_log", values)` | id |

All bounds are passed through `to_utc_iso` except the summary dates.

### Repository changes (`memory/repository.py`)

- Add to both repositories: `has_history: bool` (`StoreRepository`: `True`; `JsonGraphRepository`: `False`) and `home_id: str | None` (`StoreRepository`: `store.home_id`; JSON: `None`).
- `JsonGraphRepository.latest_states()` stays as is. Add `JsonGraphRepository.evidence_path(instance_id) -> Path | None`: for a v2 graph, take the last entry of `data["state_runs"]` for that instance that has `evidence` with a `path`; return `self.path.parent / path` if that file exists, else `None`. For v1 graphs return `None`.

### API changes in this WP

- Replace the sort in `query_memory` with one helper used everywhere:

```python
def _recency_key(state: dict[str, Any]) -> tuple[str, float]:
    return (str(state.get("last_seen_wallclock") or ""), float(state.get("last_seen_timestamp") or 0.0))
```
  `matches.sort(key=_recency_key, reverse=True)`. Fixed-format UTC text sorts chronologically.
- `HealthResponse` gains `home_id: str | None`, `auth_required: bool = False` (filled in WP26), `clock_override: bool`, `as_of: str`.
- `tests/conftest.py`: add `os.environ.setdefault("AEGIS_AUTH_DISABLED", "1")` and `os.environ.setdefault("AEGIS_DISABLE_MAINTENANCE", "1")` now, so later WPs do not break the suite midway.

### Tests

`tests/test_settings.py`
- `test_defaults_without_config_file`, `test_config_file_is_loaded` (write a YAML with `query: {fresh_hours: 2}` to `tmp_path`, set `AEGIS_CONFIG`, call `reset_settings()`).
- `test_unknown_query_setting_is_rejected`, `test_invalid_ranges_are_rejected` (parametrised over the validation rules).
- `test_clock_override` (`AEGIS_NOW=2026-11-16T10:30:00+05:00` gives `05:30Z`).

`tests/test_store_v2.py`
- `test_new_store_has_v2_tables`.
- `test_v1_store_is_migrated_and_backed_up`: build a v1 file by executing `_SCHEMA` and `PRAGMA user_version=1` with plain `sqlite3`, insert one room, open with `open_store`, assert the room survives, `user_version == 2`, the new tables exist and `memory.v1.bak.db` exists.
- `test_latest_states_expose_run_and_anchor_quality`.
- `test_run_at_and_runs_in_window`, `test_sessions_between`, `test_room_visits_between`.
- `test_most_recent_instance_wins_in_home_query`: two `keys` instances with different anchors in two sessions; `/api/v1/query?item=keys&home_id=` must name the later one. This fails on today's code.

### Done when
All 326 existing tests pass, the new ones pass, and `uv run aegis-memory show --home-id <existing home>` still works on a store created before this WP.

---

## WP17 — Time words

**Goal:** one module that says a past moment in plain words and reads a time expression out of a question (FR5.3, todo 3.3, 3.4).

### Files
- New: `src/aegis/core/timewords.py`, `tests/test_timewords.py`.

### `describe_when(then, now, zone) -> str`

`then` and `now` are aware datetimes; `delta = now - then`; dates are compared in `zone`. 24-hour clock, as the summaries already use.

| Condition (first match) | Result |
|---|---|
| `delta < 90 s` (including negative) | `just now` |
| `delta < 60 min` | `1 minute ago` / `N minutes ago` (`N = round(delta / 60 s)`) |
| same local date | `today at HH:MM` |
| local date is yesterday | `yesterday at HH:MM` |
| fewer than 7 local days ago | `on Monday at HH:MM` (English weekday name from a fixed tuple, not `strftime`, so the locale cannot change it) |
| same year | `on 12 Nov at HH:MM` |
| otherwise | `on 12 Nov 2025 at HH:MM` |

Also `describe_day(day: date, today: date) -> str`: `today`, `yesterday`, `on Monday` (within 7 days), `on 12 Nov`, `on 12 Nov 2025`. And `clock(value, zone) -> "HH:MM"`.

### `parse_time_window(text, *, now, zone, config) -> tuple[TimeWindow | None, str]`

```python
@dataclass(frozen=True, slots=True)
class TimeWindow:
    start: datetime      # aware, UTC
    end: datetime        # aware, UTC, never after `now`
    label: str           # words to reuse in the answer: "this morning", "yesterday", "on 12 Nov"
    future: bool = False # the expression lies entirely after `now`
```

The second return value is the lower-cased text with the matched expression removed and whitespace collapsed. The parser of WP18 looks for the object in that remainder, so "morning" or "lunch" never becomes an item.

Algorithm:

1. `clean = " ".join(text.lower().replace("?", " ").replace(",", " ").split())`.
2. Find at most one **day/period expression** with the table below (try rows in order; first match wins).
3. Find at most one **clock expression**: `\b(?:at|around|about)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm|o'?clock)?\b`. Reject hours above 23 and minutes above 59 (treat as no match).
4. Combine: clock only → the clock on a day chosen by the rule below; day/period only → that window; both → the clock on the first local date of the day window.
5. Clamp: `end = min(end, now)`. If `start >= now` return the window with `future=True`, `start = end = now`.
6. Convert to UTC.

`D` = today's local date; `h(x)` = `D` at hour `x` local; hours come from `QueryConfig`.

| # | Pattern (regex, `\b` on both sides) | Start | End | Label |
|---|---|---|---|---|
| 1 | `day before yesterday` | `D−2 00:00` | `D−1 00:00` | `the day before yesterday` |
| 2 | `yesterday (morning\|afternoon\|evening\|night)` | period of `D−1` (row 6–8 hours) | | `yesterday <period>` |
| 3 | `last night` | `D−1` at `evening_hour` | `D` at `day_start_hour` | `last night` |
| 4 | `yesterday` | `D−1 00:00` | `D 00:00` | `yesterday` |
| 5 | `(?:this\|in the)? ?morning` | `h(day_start_hour)` | `h(noon_hour)` | `this morning` |
| 6 | `(?:this\|in the)? ?afternoon` | `h(noon_hour)` | `h(evening_hour)` | `this afternoon` |
| 7 | `(?:this\|in the)? ?evening\|tonight` | `h(evening_hour)` | `D+1 00:00` | `this evening` |
| 8 | `(before\|after) (breakfast\|lunch\|dinner)` | before: `h(day_start_hour)` → meal hour; after: meal hour → `D+1 00:00` | | `before lunch` |
| 9 | `(?:at\|during\|over) (breakfast\|lunch\|dinner)(?: time)?` | meal hour − 1 h | meal hour + 1 h | `at lunch` |
| 10 | `(?:in the )?(?:last\|past) (\w+ )?(minute\|hour\|day\|week)s?` | `now − N·unit` | `now` | `in the last N <unit>s` (N defaults to 1; accept digits and `a, an, one … twelve, couple`=2, `few`=3) |
| 11 | `(\w+) (minute\|hour\|day\|week)s? ago` | minutes: `t−5 min`; hours: `t−30 min`; days: local day `D−N` 00:00; weeks: Monday of the week containing `D−7N` | minutes: `t+5 min`; hours: `t+30 min`; days: next midnight; weeks: + 7 days | `N <unit>s ago` (`t = now − N·unit`) |
| 12 | `last week` | Monday of last week 00:00 | Monday of this week 00:00 | `last week` |
| 13 | `this week` | Monday of this week 00:00 | `now` | `this week` |
| 14 | `(?:on \|last \|this )?(monday\|…\|sunday)` | the most recent such local day that is not after `D`; with the prefix `last` and today being that weekday, use `D−7` | next midnight | `on Monday` |
| 15 | `(?:on )?(\d{1,2})(?:st\|nd\|rd\|th)?(?: of)? (january\|…\|december\|jan\|…\|dec)` and the reversed order `(month) (\d{1,2})` | that date this year, or last year if it is after `D` | next midnight | `on 12 Nov` |
| 16 | `(\d{4})-(\d{2})-(\d{2})` | that date | next midnight | `on 12 Nov` (add the year if not this year) |
| 17 | `today\|earlier(?: today)?\|so far` | `D 00:00` | `now` | `today` |
| 18 | `recently\|lately\|just now\|a moment ago` | `now − fresh_hours` | `now` | `recently` |

Rows 5–7 when `now` is before the period's start: use `D−1` and the label `yesterday <period>`.

Clock rule (step 4): with an explicit `am`/`pm`, the hour is fixed. Without one and `hour < 12`, there are two candidates, `hour` and `hour + 12`. With no day expression choose the latest candidate that is not after `now` today; if neither has happened yet today, use `hour + 12` yesterday. With a day expression choose `hour + 12` when `hour` is 1–6, else `hour`. The window is ±30 minutes; the label is `around HH:MM`, prefixed with the day label when there is one (`yesterday around 15:00`).

Invalid dates (31 February) are treated as no match.

### Tests (`tests/test_timewords.py`)

Fix `NOW = 2026-11-16T10:30:00+05:00` (a Monday), zone `Asia/Karachi`, default `QueryConfig`. One parametrised test `test_windows` with these rows (local times):

| Text | Start | End | Label / flag |
|---|---|---|---|
| `what did i do this morning` | Mon 05:00 | Mon 10:30 (clamped) | `this morning` |
| `where were my keys yesterday` | Sun 00:00 | Mon 00:00 | `yesterday` |
| `last night` | Sun 17:00 | Mon 05:00 | `last night` |
| `yesterday evening` | Sun 17:00 | Mon 00:00 | `yesterday evening` |
| `before lunch` | Mon 05:00 | Mon 10:30 | `before lunch` |
| `after lunch` | — | — | `future is True` |
| `in the last 2 hours` | Mon 08:30 | Mon 10:30 | `in the last 2 hours` |
| `in the past hour` | Mon 09:30 | Mon 10:30 | `in the last 1 hour` |
| `3 days ago` | Fri 13 00:00 | Sat 14 00:00 | `3 days ago` |
| `on friday` | Fri 13 00:00 | Sat 14 00:00 | `on Friday` |
| `on monday` | Mon 16 00:00 | Mon 10:30 | `on Monday` |
| `last monday` | Mon 9 00:00 | Tue 10 00:00 | `on Monday` |
| `on 12 november` | Thu 12 00:00 | Fri 13 00:00 | `on 12 Nov` |
| `on 25 december` | 2025-12-25 00:00 | 2025-12-26 00:00 | `on 25 Dec 2025` |
| `2026-11-10` | Tue 10 00:00 | Wed 11 00:00 | `on 10 Nov` |
| `around 9` | Mon 08:30 | Mon 09:30 | `around 09:00` |
| `at 3 pm` | Sun 14:30 | Sun 15:30 | `yesterday around 15:00` |
| `yesterday at 3` | Sun 14:30 | Sun 15:30 | `yesterday around 15:00` |
| `last week` | Mon 9 00:00 | Mon 16 00:00 | `last week` |
| `the day before yesterday` | Sat 14 00:00 | Sun 15 00:00 | `the day before yesterday` |
| `this evening` | — | — | `future is True` |
| `where are my keys` | — | — | window is `None`, remainder equals the cleaned text |

More tests:
- `test_remainder_drops_the_time_words` (`"where were my keys yesterday morning"` → `"where were my keys"`).
- `test_room_number_is_not_a_clock` (`"keys in room 2"` → `None`).
- `test_describe_when` (parametrised over all seven rows of the table, including a negative delta and a different year).
- `test_no_vocabulary_phrase_is_a_time_word`: no id, prompt or synonym in `default_vocabulary()` equals a weekday, month, `morning`, `afternoon`, `evening`, `night`, `today`, `yesterday`, `breakfast`, `lunch`, `dinner`. If this fails, the vocabulary entry must be renamed, not the parser.
- `test_daylight_saving_zone` with `Europe/London` across 2026-10-25: `yesterday` is 25 hours long. This proves local midnights are built with `datetime.combine(day, time.min, tzinfo=zone)`, as `compaction._bounds` does.

### Done when
The table above passes exactly. No other module is changed in this WP.

---

## WP18 — Query parser and intent routing

**Goal:** turn any typed or spoken sentence into a `ParsedQuery` (todo 3.3 intent routing). Pure functions, no store access.

### Files
- New: `src/aegis/memory/query_parser.py`, `tests/test_query_parser.py`.
- Change: `src/aegis/memory/reasoning.py` (extend `STOP_WORDS` only).

### Types

```python
@dataclass(frozen=True, slots=True)
class ParsedQuery:
    raw: str
    intent: str                 # "where" | "when" | "what_happened" | "did_i"
    subject: str                # "object" | "self"
    item: VocabEntry | None     # vocabulary entry when the object is known
    item_phrase: str            # words to say back when it is not ("umbrella")
    room_filter: str | None     # QueryReasoningEngine.extract_room_filter result
    window: TimeWindow | None
    action: str | None          # "place" | "pickup" | "move" | "see" | "visit" | "unknown" | None
    action_phrase: str | None   # the user's verb phrase, only for "unknown"
```

### `parse_query(text, *, now, zone, config, vocabulary=None) -> ParsedQuery`

1. `window, rest = parse_time_window(text, now=now, zone=zone, config=config)`.
2. `room_filter = QueryReasoningEngine.extract_room_filter(rest)`.
3. `item = vocabulary.resolve_query(QueryReasoningEngine.strip_room_words(rest))`.
4. Intent, first rule that matches `rest`:

| # | Rule (regex on `rest`) | Intent | Subject |
|---|---|---|---|
| 1 | `^(when\|what time\|how long ago)\b` | `when` | `object` if `item` else `self` |
| 2 | `^where (was\|were\|have) i\b` or `^what (did i do\|have i done\|was i doing\|happened)\b` with no `item` | `what_happened` | `self` |
| 3 | `\bwhat happened (to\|with)\b` or `^what did i do with\b` or `^(show\|tell) me (what\|everything)\b` | `what_happened` | `object` if `item` else `self` |
| 4 | `^(did\|have\|had\|was\|were\|has) (i\|we\|you)\b` or `^(did\|has\|have) (anyone\|someone\|somebody)\b` or `^(is\|are\|was\|were) (my\|the) .+ (in\|on\|inside\|under)\b` with a `room_filter` | `did_i` | `object` if `item` else `self` |
| 5 | otherwise | `where` | `object` |

5. Action (only for `when` and `did_i`; else `None`). Search `rest` for the first phrase of each list, longest phrase first across all lists:

| Action | Phrases |
|---|---|
| `place` | put down, set down, put away, put, placed, place, left, leave, kept, keep, stored, store, dropped, drop, returned, return |
| `pickup` | picked up, pick up, took out, take out, took, take, taken, grabbed, grab, removed, remove, carried, carry |
| `move` | moved, move, shifted, shift, touched, touch, used, use, handled |
| `see` | saw, see, seen, noticed, had, have |
| `visit` | went to, go to, gone to, been in, been to, was in, were in, entered, visited, walked into |

   Match on whole words. `have`/`had` count as `see` only when an `item` exists and no other action matched. If nothing matches: for `when` use `see`; for `did_i` with a `room_filter` and no `item` use `visit`; for `did_i` with an `item` and a `room_filter` use `place`; otherwise `unknown`, and `action_phrase` is `rest` with the leading auxiliary and pronoun removed (`"did i have breakfast"` → `"have breakfast"`).
6. `item_phrase`: `item.id` when known, else `QueryReasoningEngine.item_phrase(rest)` after removing the matched action phrase. Extend `STOP_WORDS` in `reasoning.py` with: `when, did, do, does, done, was, were, have, has, had, been, last, time, it, them, you, we, with, at, around, about, ever, please, can, could, tell, show, anyone, someone, happened, happen, any, there, here, now, still, again, this, that`.
7. A sentence that is only an object name (`"keys"`) gives `intent="where"`. An empty sentence raises `ValueError("empty query")`.

### Tests (`tests/test_query_parser.py`)

One parametrised test `test_routing` with at least these rows (`NOW` as in WP17):

| Text | intent | subject | item | room | action | window label |
|---|---|---|---|---|---|---|
| `where are my keys` | where | object | keys | — | — | — |
| `keys` | where | object | keys | — | — | — |
| `keys in the kitchen` | where | object | keys | kitchen | — | — |
| `where were my keys yesterday` | where | object | keys | — | — | yesterday |
| `when did i last see my glasses` | when | object | glasses | — | see | — |
| `when did i put my keys down` | when | object | keys | — | place | — |
| `what time did i take my medicine` | when | object | medicine entry | — | pickup | — |
| `what did i do this morning` | what_happened | self | — | — | — | this morning |
| `where was i last night` | what_happened | self | — | — | — | last night |
| `what happened to my phone yesterday` | what_happened | object | phone entry | — | — | yesterday |
| `did i move my keys today` | did_i | object | keys | — | move | today |
| `did i go to the kitchen this morning` | did_i | self | — | kitchen | visit | this morning |
| `did i leave my keys in the kitchen` | did_i | object | keys | kitchen | place | — |
| `did i have breakfast this morning` | did_i | self | — | — | unknown (`have breakfast`) | this morning |
| `where is my umbrella` (not in vocabulary) | where | object | `None`, phrase `umbrella` | — | — | — |

The vocabulary has `keys`, `glasses`, `medicine`, `wallet`, `mug` and `cell phone` (which is what "phone" should resolve to; if it does not, assert what `resolve_query` really returns and note it — do not add vocabulary entries in this WP). `umbrella` is not in the vocabulary.

Also: `test_empty_query_raises`, `test_action_longest_phrase_wins` (`"picked up"` is `pickup`, not `place` via `put`), `test_parser_is_pure` (same input twice gives equal dataclasses).

### Done when
The routing table passes and `tests/test_reasoning.py` is unchanged and green.


---

## WP19 — Confidence, freshness and abstention

**Goal:** replace the stored-score passthrough with a computed answer confidence, report freshness against the 6-hour window, and abstain explicitly (FR5.5, NFR-R3, SC6, AC-12, AC-28; todo 3.4, 3.5).

### Files
- New: `src/aegis/memory/confidence.py`, `src/aegis/memory/answering.py`, `tests/test_confidence.py`, `tests/test_answering_where.py`.
- Change: `src/aegis/memory/reasoning.py`, `src/aegis/remote/api.py`, `tests/test_api.py`, `tests/test_reasoning.py`.

### The answer contract (used by WP19–WP22 and by the app)

`answering.py` defines the engine's result. It is a plain dataclass so it can be tested without FastAPI.

```python
ANSWERING = frozenset({"answered", "stale", "ambiguous", "not_seen_in_window"})

@dataclass
class Answer:
    query: str
    intent: str
    status: str
    text: str                              # at most two sentences
    as_of: str                             # UTC ISO of "now" used
    state: dict[str, Any] | None = None    # the primary memory state, if any
    confidence: float | None = None
    confidence_parts: dict[str, float] = field(default_factory=dict)
    freshness: str = "unknown"             # "fresh" | "stale" | "unknown"
    last_seen_at: str | None = None
    last_seen_text: str | None = None      # describe_when(...)
    tier: str = "detailed"                 # "detailed" | "summarised" | "mixed"
    window_label: str | None = None
    evidence: list[dict[str, Any]] = field(default_factory=list)   # WP20
    options: list[dict[str, Any]] = field(default_factory=list)    # WP22
    items: list[str] = field(default_factory=list)                 # extra lines for the UI
    facts: dict[str, Any] = field(default_factory=dict)            # machine-checkable, WP21/WP33
    known_items: list[str] = field(default_factory=list)

    @property
    def abstained(self) -> bool: return self.status not in ANSWERING
```

Status values (complete list; no other string may be used):

| Status | Meaning | Abstains |
|---|---|---|
| `answered` | Grounded answer. | no |
| `stale` | Grounded, but the last sighting is older than `fresh_hours`. | no |
| `ambiguous` | Several instances in different places; options listed. | no |
| `not_seen_in_window` | Not seen in the asked period; an older sighting is cited. | no |
| `low_confidence` | Evidence exists but confidence is below the threshold. | yes |
| `never_observed` | No memory of the object. | yes |
| `no_match_in_room` | Seen, but not in the asked room. | yes |
| `no_activity` | Nothing recorded or nothing changed in the asked period. | yes |
| `unsupported_activity` | The activity cannot be recognised ("breakfast"). | yes |
| `unsupported` | Temporal question on a `dataset_id`. | yes |
| `future_time` | The asked period has not happened yet. | yes |
| `not_ready` | The dataset has no scene graph. | yes |

### `confidence.py`

```python
def answer_confidence(state, *, now, config) -> tuple[float | None, dict[str, float]]:
```

- `detection = state.get("confidence")`. If it is `None` return `(None, {})`; a missing score is never replaced by a default. This happens only for schema-v1 demo graphs (the tracked fixtures have no scores; `test_query_confidence_is_not_a_constant` asserts `None` for them). Home-store states always have a score (`state_run.confidence` is `NOT NULL`).
- `identity = config.ordinal_anchor_factor if state.get("anchor_match_quality") == "ordinal" else 1.0`.
- `support = config.single_observation_factor if state.get("observation_count") == 1 else 1.0` (missing count → `1.0`).
- `age_hours`: from `state["last_seen_wallclock"]` and `now`; `None` when there is no wall-clock time.
- `recency = 1.0` when `age_hours is None or age_hours <= fresh_hours`, else `max(min_recency_factor, 0.5 ** ((age_hours - fresh_hours) / recency_half_life_hours))`.
- `value = round(clamp(detection, 0, 1) * identity * support * recency, 2)`.
- Parts: `{"detection", "identity", "support", "recency"}`, each rounded to 2 decimals.

`freshness(state, now, config) -> str`: `"unknown"` without wall-clock time, `"fresh"` when `age_hours <= fresh_hours`, else `"stale"`.

The relation-certainty penalty is already inside `detection` (fact table). Do not add it again.

### Templates (`reasoning.py`)

Move `_place` out of `summaries.py` into `reasoning.py` as the public `place_phrase(relation, anchor, room) -> str` and import it back into `summaries.py`. Add these functions; each returns finished text.

`name` below is `QueryReasoningEngine`'s item name (`entry.id`, e.g. `keys`); `is/are`, `was/were`, `it/they`, `it/them` follow `entry.plural`.

| Function | Text |
|---|---|
| `where_answer(name, state, when, plural)` | The existing `_location_sentence(...)`. When `when` is given, insert `, {when}` before the final full stop: `Your keys were last seen on Desk #1 in the Kitchen, today at 14:05.` Then, if the relation is uncertain and not carried, append ` I'm not fully sure about the exact spot.` |
| `stale_answer(name, state, when, plural)` | The same first sentence with `in_view=False`, then ` I have not seen {it/them} since, so {it/they} may have moved.` The uncertain sentence is not added (two-sentence limit). |
| `low_confidence_answer(name, state, when, plural)` | `I'm not sure where your {name} {is/are}.` If the state has an anchor or a room: ` My last unclear sighting was {place_phrase}{, when}.` |
| `never_observed_answer(phrase)` | `I haven't seen your {phrase}.` |
| `not_ready_answer(dataset_id)` | `The scene graph for {dataset_id} has not been generated yet.` (existing wording) |
| `no_match_in_room_answer(name, room, known_rooms)` | Existing wording from `query_memory`: `I couldn't find any '{name}' in the {Room}. It was last seen in {rooms}.` Move it here unchanged. |

**Voice.** A caregiver must not be told "Your keys…" or "You were in the Kitchen". Add to `reasoning.py`:

```python
@dataclass(frozen=True, slots=True)
class Voice:
    owner: str      # "your" | "the"
    you: str        # "You" | "The wearer"
    you_were: str   # "You were" | "The wearer was"
    you_are: str    # "You are" | "The wearer is"
    you_obj: str    # "you" | "the wearer"

PATIENT = Voice("your", "You", "You were", "You are", "you")
CARER = Voice("the", "The wearer", "The wearer was", "The wearer is", "the wearer")
```

Every template function in this plan (WP19–WP22, WP29) and the existing `_location_sentence` take `voice: Voice = PATIENT` and build their words from it: `Your {name}` is `f"{voice.owner.capitalize()} {name}"`, `You put your {name}` is `f"{voice.you} put {voice.owner} {name}"`, `I did not see you` is `f"I did not see {voice.you_obj}"`. The templates in this plan are written in the patient voice for readability. The default keeps every existing test unchanged. The engine functions take `voice` and pass it down; the API chooses `CARER` when the caller's role is `caregiver` (WP26) and `PATIENT` otherwise.

`sentence_count(text) -> int` (public, used by tests and by the engine's guard): count matches of `[.!?](?=\s|$)`.

### Engine: `answer_where(parsed, repo, *, now, zone, settings, instance_id=None) -> Answer`

This replaces the body of `query_memory`. Steps:

1. `latest = repo.latest_states()`. Candidates: when `parsed.item` exists, states whose canonical equals `parsed.item.id` (use the existing `_state_canonical` logic, moved into `answering.py`); else states whose base label equals `parsed.item_phrase`.
2. `instance_id` given: keep only that instance (unknown id → `never_observed`).
3. No candidates: `not_ready` when `not repo.ready`, else `never_observed`. Fill `known_items` with the sorted distinct labels.
4. Room filter (existing substring rule on `room_label`): none left → `no_match_in_room`.
5. Sort with `_recency_key` descending. `primary = matches[0]`. Ambiguity handling is added in WP22; until then keep today's behaviour (`other_instances`).
6. `confidence, parts = answer_confidence(primary, ...)`; `fresh = freshness(primary, ...)`; `when = describe_when(...)` when the state has wall-clock time, else `None`.
7. Status: `low_confidence` when `confidence is not None and confidence < settings.query.abstain_below`; else `stale` when `fresh == "stale"`; else `answered`. A `None` confidence cannot be compared with a threshold: the answer is given with `confidence: null` (legacy v1 graphs only). The fixture-backed API tests rely on this.
8. Text from the matching template. `last_seen_at`, `last_seen_text` filled.
9. Guard: `assert sentence_count(text) <= 2` in tests; in production, if it is more than 2, keep the first two sentences and log an error.

A JSON-graph state without wall-clock time: `freshness = "unknown"`, `recency = 1.0`, no time phrase. This keeps the demo datasets answerable without inventing a time.

### API (`remote/api.py`)

- `MemoryQueryResponse` gains, all optional with defaults: `status: str = "answered"`, `abstained: bool = False`, `intent: str = "where"`, `answer: str | None`, `as_of: str | None`, `freshness: str = "unknown"`, `confidence_parts: dict[str, float]`, `tier: str = "detailed"`, `window_label: str | None`, `evidence: list[EvidenceRef]` (model defined in WP20; an empty list for now), `options: list[dict]`, `items: list[str]`, `facts: dict`, `known_items: list[str]`.
- `location_summary`, `explanation` and `answer` all carry `Answer.text`. `found = not answer.abstained`. `last_seen_time_ago = answer.last_seen_text`. `confidence = answer.confidence`. For an abstention set `anchor_id`, `anchor_label`, `relation`, `room_id`, `room_label`, `crop_url` to `None` **except** for `low_confidence`, where the candidate stays in the structured fields (UC-03 A2: "state uncertainty and show last evidence") and `found` is `False`.
- One function `_to_response(answer: Answer, repo, key) -> MemoryQueryResponse` builds the model. `query_memory` becomes: parse (`parse_query`), call the engine, convert. In this WP only `intent == "where"` without a window is implemented; other intents return `status="unsupported"` with the text `I can't answer that kind of question yet.` until WP21 replaces it.

### Tests

`tests/test_confidence.py`
- `test_missing_score_gives_none`.
- `test_v1_graph_without_scores_is_answered_with_null_confidence` (fixture `demo01`, `shoes`: status `answered`, `confidence is None`).
- `test_ordinal_anchor_lowers_confidence`, `test_single_observation_lowers_confidence`.
- `test_recency_decay_and_floor` (age 6 h → 1.0; 78 h → 0.5; 1000 h → floor).
- `test_confidence_varies_across_inputs` (replaces the idea of a constant; at least three distinct values).

`tests/test_answering_where.py` (store built with `make_session_graph`, `now` passed explicitly)
- `test_fresh_object_is_answered_with_time` — text contains `today at`.
- `test_object_older_than_six_hours_is_stale` — status `stale`, text contains `may have moved`, does not contain ` is on ` / ` are on ` (AC-28: not presented as current).
- `test_exactly_six_hours_is_still_fresh` (boundary).
- `test_low_confidence_abstains` — run confidence 0.1 → status `low_confidence`, `abstained`, text starts `I'm not sure`.
- `test_never_observed_abstains_without_location` — five different unseen objects (`wallet`, `passport`, `umbrella`, `charger`, `watch`; pick ones absent from the test store): all five abstain, none has an anchor or room in the response (AC-12).
- `test_three_abstention_kinds_are_distinct` — never observed / stale / low confidence give three different statuses (todo 3.5).
- `test_threshold_is_configurable` — same state answers with `abstain_below=0.05` and abstains with `0.95`.
- `test_no_wallclock_gives_unknown_freshness` (JSON fixture `demo01`).
- `test_every_template_is_at_most_two_sentences` — sweep relations × plural × certain × status.

`tests/test_api.py`: no test asserts the old not-found sentence literally; `test_query_unfound_item` asserts that `wallet` is in the summary and `found` is `False`, which the new sentence keeps. Add an assertion that the available labels are in `known_items`. `test_query_confidence_is_not_a_constant` (confidence `None` on `demo01`) must keep passing unchanged.

### Done when
`grep -n "0.96" src apps/mobile/lib` finds nothing, the suite is green, and todo items 3.4 (all three) and 3.5 (first four) can be ticked with the test names above.

---

## WP20 — Evidence references and real crops

**Goal:** every non-abstaining answer cites stored evidence, with an image when one exists and a text description when it does not (FR5.4, SC5, AC-11; todo 3.6).

### Files
- Change: `src/aegis/memory/answering.py`, `src/aegis/memory/reasoning.py`, `src/aegis/remote/api.py`, `tests/test_evidence.py`, `tests/test_api.py`.
- New: `tests/test_evidence_refs.py`.

### Evidence item

```python
class EvidenceRef(BaseModel):
    kind: str                    # "crop" | "observation" | "event" | "summary" | "coverage"
    observation_id: str          # "run:123" | "event:45" | "summary:7" | "session:<id>" | "graph:<dataset>:<instance>"
    description: str             # always present, plain words
    observed_at: str | None = None        # UTC ISO
    observed_at_text: str | None = None   # describe_when
    anchor_label: str | None = None
    room_label: str | None = None
    evidence_id: int | None = None        # row in `evidence`
    crop_url: str | None = None
    tier: str = "detailed"
```

Builders in `answering.py` (they return dicts with exactly these keys):

- `evidence_for_state(repo, state, *, now, zone)`:
  - Home store: `observation_id = f"run:{state['run_id']}"`. If `state["evidence_id"]` is set **and** the file `store.dir / row.path` exists: `kind="crop"`, `evidence_id`, `crop_url = f"/api/v1/evidence/{evidence_id}?home_id={home}"`. Otherwise `kind="observation"` and no URL.
  - JSON graph: `observation_id = f"graph:{dataset}:{instance_id}"`; `kind="crop"` with `crop_url = f"/api/v1/crops/{instance_id}?dataset_id={dataset}"` when `repo.evidence_path(instance_id)` is not `None`, else `kind="observation"`.
  - `description` from `reasoning.evidence_description(label, relation, anchor, room, when, has_image)`: `Mug #2 seen on Desk #1 in the Kitchen, today at 14:05.` and, when there is no image, ` (no image stored)` before the full stop.
- `evidence_for_event(store, event, ...)` (used in WP21): `observation_id = f"event:{n}"`; the crop comes from `store.run_starting_at(instance_id, event["end_wallclock"])`; description is `event_summary(event)` plus the time.
- `evidence_for_summary(row)`: `kind="summary"`, `observation_id = f"summary:{summary_id}"`, `description = row["text"]`, `tier="summarised"`, `observed_at_text = describe_day(period_start)`.
- `evidence_for_coverage(sessions, label)`: `kind="coverage"`, `observation_id = f"session:{first_id}"`, description `Recording covered {HH:MM}–{HH:MM} {label} ({n} session(s)).`

### Guard

At the end of every engine entry point call `_finalise(answer)`:

1. If `answer.status in ANSWERING` and `answer.evidence` is empty → set `status="low_confidence"`, replace the text with `low_confidence_answer(...)` (or `I'm not sure; I have no stored evidence for that.` when there is no state), log `logger.error("answer without evidence downgraded: %s", query)`.
2. Every evidence item must have a non-empty `description` and `observation_id`; drop items that do not, then re-apply rule 1.
3. `sentence_count(answer.text) <= 2`, as in WP19.

### Endpoints

- New `GET /api/v1/evidence/{evidence_id}?home_id=`: look the row up with `store.evidence_row`; 404 `no evidence image` when the row or the file is missing; else the JPEG bytes (`media_type="image/jpeg"`, header `Cache-Control: private, max-age=300`). Reading goes through one helper `_read_evidence_file(store, path) -> bytes` so WP27 can add decryption in one place.
- `GET /api/v1/crops/{instance_id}`: with `home_id`, redirect logic stays as today but calls the same helper. With `dataset_id`, return the real JPEG from `repo.evidence_path(instance_id)` or **404**. Delete the SVG card and the `html` import. A placeholder image is not evidence.
- `_crop_url` is deleted; `crop_url` on the response is the first evidence item's `crop_url`.

### Tests

`tests/test_evidence_refs.py`
- `test_answer_with_crop_cites_it` — ingest with a crop (reuse `_graph_with_crop` from `tests/test_evidence.py`; move it to `tests/_graphs.py`), answer has one `crop` item whose URL returns 200 `image/jpeg`.
- `test_purged_crop_falls_back_to_text` — delete the file from the store directory; the answer is still `answered`, the item is `kind="observation"`, `crop_url is None`, description contains `no image stored` (todo 3.6 fallback).
- `test_carried_object_has_text_evidence`.
- `test_evidence_coverage_is_total` — build a store with 12 objects across relations (`on_surface`, `inside`, `under`, `on_floor`, `in_room`, `carried_by_user`), with and without crops, fresh and stale; ask about each; every answer with `status in ANSWERING` has at least one evidence item with a description and an observation id (AC-11, 100%).
- `test_answer_without_evidence_is_downgraded` — monkeypatch the builder to return `[]`; the status becomes `low_confidence`.
- `test_dataset_crop_is_real_or_404` — a v2 graph in `tmp_path` with an evidence file returns the JPEG; fixture `demo01` (v1) returns 404 and `crop_url is None`.

Rewrite `test_crops_endpoint` and the `crop_url is not None` line of `test_query_shoes_endpoint` in `tests/test_api.py`: the fixture is a v1 graph without crops, so the correct expectations are 404 and `None` (Part I rule 8).

### Done when
`grep -n "svg" src/aegis/remote/api.py` finds nothing; todo 3.6 items can be ticked.

---

## WP21 — Temporal answers over detailed and summarised tiers

**Goal:** answer "when", "what happened" and "did I" questions, from detail rows when they exist and from summaries when they do not, and label summarised answers (FR5.2, FR5.3, FR4.3, UC-05, AC-10, AC-23).

### Files
- Change: `src/aegis/memory/answering.py`, `src/aegis/memory/reasoning.py`, `src/aegis/remote/api.py`.
- New: `tests/test_answering_temporal.py`.

### Entry point

```python
def answer(parsed, repo, *, now, zone, settings, instance_id=None, max_history_days=None) -> Answer:
```

Dispatch, in order:

1. `parsed.window` with `future=True` → `future_time`, text `That time has not happened yet.`
2. Temporal question (`intent != "where"` or `parsed.window is not None`) and `not repo.has_history` → `unsupported`, text `I can only answer that from the home memory, not from a single video.`
3. `max_history_days` (caregiver limit, WP26): if the window starts before `now − max_history_days`, clamp `start`; if the whole window is before it, raise `PermissionError("outside granted history")`.
4. `where` without window → `answer_where` (WP19). `where` with window → `answer_where_then`. `when` → `answer_when`. `what_happened` → `answer_what_happened`. `did_i` → `answer_did_i`.

### Shared helpers

- `_instances(parsed, repo, instance_id)` — the candidate list from WP19 steps 1–5, most recent first. Temporal answers use the first one and, when there are several, set `answer.options` (WP22 format) so the user can pick another.
- `_local_dates(window, zone) -> (str, str)` — first and last local dates as `YYYY-MM-DD`, for `store.summaries`.
- `_coverage(store, window)` — `sessions = store.sessions_between(start, end)`; returns `(sessions, recorded: bool)`.
- `_default_window(now, zone, config)` — local today 00:00 → `now`, label `today`. Used when a question that needs a period has none.
- Tier: `detailed` when only detail rows were used, `summarised` when only summary rows were used, `mixed` when both. A summarised or mixed answer **must** start with `From summarised history: ` (function `summarised_prefix(text)` lower-cases the first letter of `text` unless it starts with a label such as `Keys #1`) and carry `tier != "detailed"`.
- Second-person event sentence, `reasoning.event_you_sentence(name, event, plural) -> str` (no trailing full stop, so a time can follow):

| Event type | Text |
|---|---|
| `placement` | `You put your {name} {place_phrase(dst_relation, dst_anchor, dst_room)}` |
| `pickup` | `You picked up your {name} from {src_anchor}` / `You picked up your {name}` |
| `anchor_change` | `Your {name} moved from {src_anchor} to {dst_anchor}` |
| `state_change` | `Your {name} changed place` |
| `moved_while_unobserved` | `Your {name} {was/were} moved while I was not watching` |

### `answer_where_then` — "where were my keys yesterday?"

`W = parsed.window`. For the primary instance:

1. `runs = store.runs_in_window(id, W.start, W.end)`. If any: take the last; status `answered`; text `{Label}, your {name} {was/were} {place}, last seen there at {HH:MM}.` where `{Label}` is the window label capitalised (`Yesterday`). Evidence: the run (`evidence_for_state` on a state dict built from the run). `facts = {"reference_time": run.end_at, "anchor_label", "room_label", "relation"}`.
2. Else `rows = store.object_summaries(id, *_local_dates(W))`. If any: newest row; resolve `sidecar["last"]` ids to labels with `store.anchors()` / `store.rooms()`; status `answered`, tier `summarised`; text `From summarised history: {label} your {name} {was/were} last {place} at {HH:MM}.` Evidence: the summary.
3. Else `run = store.run_at(id, W.start)` (older knowledge). If found: status `not_seen_in_window`; text `I did not see your {name} {label}. Before that, {it/they} {was/were} {place}, {describe_when(run.end_at)}.` Evidence: that run.
4. Else `never_observed`.

### `answer_when`

- Action `see` (or none): for the primary instance, `status` and confidence as in `answer_where`; text `I last saw your {name} {when}, {place}.` (`when` from `describe_when`; if there is no wall-clock time: `unsupported`). Evidence: the state.
- Action `place`, `pickup` or `move`. Event types: `place` → `{placement, anchor_change}`; `pickup` → `{pickup}`; `move` → `{pickup, placement, anchor_change, state_change, moved_while_unobserved}`.
  1. `events = store.events_for_instance(id, W.start, W.end, types)` (no window → all time). If any: last event `e`; text `{event_you_sentence} {describe_when(e.end)}.` For `moved_while_unobserved`: `Your {name} {was/were} moved between {describe_when(e.start)} and {describe_when(e.end)}; I did not see it happen.` Status `answered`. Evidence: `evidence_for_event`. `facts = {"reference_time": e.end, "event_type": e.type}`.
  2. Else summaries for the instance (window dates, or all): newest row whose `sidecar["event_types"]` has one of the types. If its `moves` list is non-empty: last matching move → `From summarised history: your {name} {was/were} last moved {describe_when(move.at)}.` Else: `From summarised history: your {name} {was/were} moved {n} time(s) {describe_day(period_start)}.` (for week or month rows: `in the week of 9 Nov` / `in Nov 2026`). Status `answered`, tier `summarised`, evidence: the summary, `facts = {"reference_date": period_start, "count": n}`.
  3. Else `no_activity`: `I have not seen your {name} being moved{ label}.` If a window was given and `_coverage` says nothing was recorded, the text is `I have no record of {label}. The camera was not recording then.` and `facts["capture_gap"] = True` (UC-05 A1).

### `answer_what_happened`

`W = parsed.window or _default_window(...)`.

Subject `object`:
1. `events = store.events_for_instance(id, W.start, W.end, MOVE_TYPES)`. `n > 0`: text `Your {name} {was/were} moved {n} time(s) {label}. Most recently, {lower-first event_you_sentence} at {HH:MM}.`; `items` = one line per event (`{HH:MM} {event_summary}`); evidence: last event.
2. Else summaries in the window dates: text = `From summarised history: ` + the newest row's `text` (it is already one or two sentences); `items` = the other rows' texts; evidence: the summary.
3. Else, if the object is known: status `no_activity`, text `Nothing happened to your {name} {label}.` plus, when an older event exists, ` The last change I saw was {describe_when}.` If nothing was recorded in `W`, use the camera sentence instead of the second sentence.

Subject `self`:
1. `activities = store.activities(W.start, W.end)`. If any: `rooms` = distinct room labels in order (`None` → `an unnamed area`), at most three named, then `and N more`; `moved = sum(event_count)`. Sentence 1: `{Label} you were in {rooms}.` Sentence 2: `I did not see any objects move.` when `moved == 0`, else `I saw {moved} object change(s), most recently: {event_summary(last non-room event in W)}`. `items` = the activity summary lines. Evidence: the last event when there is one, else coverage. `facts = {"rooms": [...], "moved": moved}`.
2. Else activity summaries in the window dates: text `From summarised history, {label}: {newest row text}`; `items` = all rows; evidence: summary; `facts["rooms"]` from the sidecars' `room_id` (or the keys of `seconds_by_room`).
3. Else `no_activity`: nothing recorded → `I have no record of {label}. The camera was not recording then.` (`capture_gap = True`); recorded → `I was recording {label} but did not see anything change.`

### `answer_did_i`

`W = parsed.window or _default_window(...)`, except rule D3.

- **D1, action `visit`** (needs `room_filter`; without one treat as `unknown`). `visits = [v for v in store.room_visits(W.start, W.end) if room_filter in (v.room_label or "").lower()]`.
  - Found: `Yes. You were in the {Room} {label}, from {HH:MM} to {HH:MM}.` (first visit; when several: `…, {n} times, first at {HH:MM}.`). Status `answered`, `facts = {"polarity": "yes", "reference_time": first.start}`, evidence: coverage.
  - Not found, recorded: `I did not see you in the {room} {label}.` Status `answered`, `polarity: "no"`, evidence: coverage.
  - Not found, not recorded, summaries exist for the dates: use activity sidecars; `From summarised history: yes, you were in the {Room} {describe_day}.` or the "did not see" sentence with the prefix.
  - Nothing recorded: `no_activity` with the camera sentence.
- **D2, action `place`, `pickup`, `move` with an item and a window (or no room filter).** Events as in `answer_when`. Found: `Yes. {event_you_sentence} {describe_when}.` (`polarity: "yes"`). Not found and recorded: `I did not see you {put down|pick up|move} your {name} {label}.` (`polarity: "no"`, evidence: coverage). Not recorded: camera sentence, `no_activity`. Summarised: `From summarised history: yes, your {name} {was/were} moved {describe_day}.`
- **D3, action `place` with an item, a room filter and no window** ("did I leave my keys in the kitchen?"). Take the `answer_where` result **without** the room filter. If it abstains, return it unchanged. Else compare the state's room with the filter: text `Yes. ` or `No. ` followed by the first sentence only of the where-answer (drop the second sentence to stay within two). `polarity` set accordingly. Evidence: the state.
- **D4, action `see` with an item.** Runs in the window exist → `Yes. I saw your {name} {describe_when(last run end)}, {place}.`; else recorded → `I did not see your {name} {label}.` (`polarity: "no"`); else camera sentence.
- **D5, action `unknown`.** Status `unsupported_activity`. Sentence 1: `I can't tell whether you did that.` Sentence 2: sentence 1 of the `self` branch of `answer_what_happened` for `W` if activities exist, otherwise the camera sentence or nothing. This is the honest answer to "Did I have breakfast?": the system recognises rooms and object changes, not meals.

Confidence for temporal answers: event-based answers carry `event["confidence"]` when present, state-based ones the WP19 value, summarised ones `None`. An event confidence below `abstain_below` turns the answer into `low_confidence` with the text `I'm not sure. I may have seen your {name} being moved {describe_when}, but the sighting was unclear.`

### API
`query_memory` now passes every intent to `answer(...)`. `PermissionError` from step 3 becomes HTTP 403.

### Tests (`tests/test_answering_temporal.py`)

Build one store fixture `history_store` with a fixed timeline in `Asia/Karachi` (use `make_session_graph`, three rooms, anchors desk/drawer/refrigerator):

| Local time | Session | Content |
|---|---|---|
| Fri 13 Nov 09:00 | `f1` | keys on desk (Kitchen); mug on desk |
| Sat 14 Nov 10:00 | `s1` | keys carried, then placed inside drawer (Bedroom); wearer Kitchen → Bedroom |
| Sun 15 Nov 20:00 | `u1` | glasses on nightstand/desk (Bedroom); wearer in Bedroom only |
| Mon 16 Nov 08:10 | `m1` | wearer Kitchen 08:10–08:40, mug picked up and placed on the refrigerator anchor; keys still in drawer (seen) |

`NOW = Mon 16 Nov 10:30`. Tests:

- `test_when_did_i_put_keys` → text contains `on Saturday at 10:` and `Drawer`; `facts["event_type"] == "placement"`.
- `test_when_did_i_last_see_glasses` → `yesterday at 20:`.
- `test_where_were_keys_on_friday` → `Desk`, status `answered`, tier `detailed`.
- `test_where_were_glasses_this_morning` → `not_seen_in_window`, cites yesterday.
- `test_what_did_i_do_this_morning` → mentions `Kitchen`; `facts["moved"] >= 1`; `items` non-empty.
- `test_what_happened_last_night_with_no_recording_gap` and `test_no_recording_says_camera_was_off` (ask about `the day before yesterday at 3 pm` → `capture_gap`).
- `test_did_i_go_to_the_kitchen_this_morning` → `polarity == "yes"`; `…to the bedroom this morning` → `"no"` with coverage evidence.
- `test_did_i_move_my_keys_today` → `"no"`; `…on saturday` → `"yes"`.
- `test_did_i_leave_keys_in_kitchen` → starts `No.`; names the Bedroom drawer.
- `test_unknown_activity_is_not_guessed` (`did i have breakfast this morning`) → `unsupported_activity`, text contains `can't tell`, no meal word asserted as fact.
- `test_future_window` (`this evening`) → `future_time`.
- `test_dataset_path_is_unsupported` (fixture `demo01`).
- **Summarised tier:** run `compact(store, now=NOW + 5 days, config=RetentionConfig())`, set `now = NOW + 5 days`, then:
  - `test_summarised_where_then` (`where were my keys on 13 november`) → tier `summarised`, text starts `From summarised history:`.
  - `test_summarised_what_happened` and `test_summarised_did_i_visit`.
  - `test_every_answer_from_compacted_history_is_labelled` — loop over 8 questions about the compacted days; for every answer whose evidence items are all `kind="summary"`, assert `tier == "summarised"` and the prefix (AC-23, 100%).
- `test_temporal_set_of_ten` — ten questions with expected `status`, `polarity`, `event_type` and time tolerance; assert at least 6 correct (AC-10 at fixture level; the recorded benchmark run is WP34). Store the ten in a module-level list so WP33 can reuse them.
- `test_all_temporal_texts_are_at_most_two_sentences` — run every question above and check `sentence_count`.
- `test_history_limit_clamps_and_denies` — `max_history_days=1`: `yesterday` is clamped, `on friday` raises `PermissionError`.

### Done when
All of todo §3.3 can be ticked with the test names above (the ≥ 60% line is ticked only as `[~]` until the WP34 run).

---

## WP22 — Clarification, query log and the `/ask` endpoint

**Goal:** handle several matching instances (UC-03 A3), log every home query with its evidence (UC-03 postcondition), and give clients one endpoint for whole questions (todo 3.7).

### Files
- Change: `src/aegis/memory/answering.py`, `src/aegis/memory/reasoning.py`, `src/aegis/remote/api.py`, `src/aegis/memory/store.py`.
- New: `tests/test_clarification.py`, `tests/test_query_log.py`.

### Clarification (in `answer_where`, replacing WP19 step 5's placeholder)

After the room filter, with `matches` sorted most recent first and no `instance_id`:

1. Group by place key `(relation, anchor_id, room_id)`. One group → not ambiguous; continue with `matches[0]`.
2. Otherwise status `ambiguous`. `options = [option(m) for m in matches[:settings.query.max_options]]` with

   `option = {"instance_id", "label", "place": place_phrase(...), "last_seen_at", "last_seen_text", "confidence", "crop_url"}`.
3. Text (`reasoning.ambiguous_answer`):
   - two instances: `I know of 2 {plural_name}. One was last seen {place₁}, and one {place₂}.`
   - more: `I know of {n} {plural_name}. The one seen most recently was {place₁}; choose one below for the others.`
   - `plural_name`: `entry.display.lower()` when `entry.plural`; otherwise add `s` (`es` after `s, x, ch, sh`; `y` after a consonant → `ies`).
4. The structured fields (`instance_id`, `anchor_label`, …) describe `matches[0]`, as today. Evidence: one item per listed option. `other_instances` keeps its current content for old clients.
5. Options with confidence below the threshold are listed last and their `place` is prefixed with `possibly `. If **all** are below it, the answer is `low_confidence` for `matches[0]` instead.

A follow-up names the choice with `instance_id` (query parameter on `/query`, body field on `/ask`), which removes the ambiguity (WP19 step 2).

### `/ask`

```python
class AskRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=300)
    home_id: str | None = None
    dataset_id: str | None = None
    instance_id: int | None = None
    modality: str = Field("text", pattern="^(text|speech)$")
    transcript_confidence: float | None = None

@app.post("/api/v1/ask", response_model=MemoryQueryResponse)
```

Both `/ask` and `GET /query?item=` call one function `_answer_request(text, dataset_id, home_id, instance_id, modality, principal)`:

1. `start = time.perf_counter()`; `now = current_time()`; `settings = get_settings()`.
2. `parsed = parse_query(text, now=now, zone=local_zone(), config=settings.query)`; `ValueError` → 422.
3. `key, repo = resolve_repository(dataset_id, home_id)`.
4. `answer = answering.answer(parsed, repo, now=now, zone=..., settings=settings, instance_id=instance_id, max_history_days=...)`.
5. If `repo.has_history` and `settings.query.log_queries`: `store.log_query(asked_at=to_utc_iso(now), username=…, role=…, user_id=…, modality=modality, text=text[:300], intent=answer.intent, status=answer.status, instance_id=…, evidence=json.dumps([e["observation_id"] for e in answer.evidence]), confidence=answer.confidence, tier=answer.tier, latency_ms=round((perf_counter() - start) * 1000))`. Until WP26 the user fields are `None`/`"local"`/`"primary"`. A logging failure is caught and logged; it never fails the answer.
6. Return `_to_response(...)`. Add `latency_ms` to the response model.

`store.purge_query_log(before_iso) -> int` deletes rows older than `log_retention_days`; it is called by the maintenance job of WP28 and after compaction in `ingest_session` (next to `rollup`).

### Tests

`tests/test_clarification.py`
- `test_two_instances_in_different_places_are_listed` — status `ambiguous`, both places in the text, two options, two evidence items, at most two sentences.
- `test_three_instances_offer_a_choice` — text contains `choose one below`.
- `test_same_place_is_not_ambiguous`.
- `test_instance_id_selects_one`.
- `test_room_filter_resolves_ambiguity` (`keys in the bedroom`).
- `test_all_low_confidence_abstains`.

`tests/test_query_log.py`
- `test_home_query_is_logged_with_evidence` — one row; `evidence` JSON equals the answer's observation ids; `latency_ms >= 0`.
- `test_abstention_is_logged` (status `never_observed`).
- `test_dataset_query_is_not_logged`.
- `test_old_rows_are_purged`.
- `test_ask_and_query_agree` — `POST /ask {"text": "where are my keys"}` and `GET /query?item=where are my keys` return the same `status`, `instance_id` and `answer`.
- `test_ask_rejects_empty_and_too_long_text` (422).

### Done when
Todo §3.7 "clarification" and "query log" can be ticked. `tests/test_api.py` multi-instance fixture tests (`test_query_shoes_endpoint` and the demo06 test) are updated only where the summary wording changed; their assertions on `instance_label`, `relation` and `anchor_label` must still hold unchanged.


---

## WP23 — Speech input

**Goal:** spoken questions (FR6.1), a confirm-or-correct step when the transcript is uncertain (FR6.3), and a reproducible way to measure AC-13. Typed input stays fully supported (NFR-U4).

Two parts. The server part is in this WP. The microphone in the app is specified here and built in WP31.

### Files
- New: `src/aegis/speech/__init__.py`, `src/aegis/speech/transcriber.py`, `scripts/evaluate_speech.py`, `tests/test_speech.py`.
- Change: `pyproject.toml` (dependency group), `src/aegis/remote/api.py`, `src/aegis/evaluation.py`.

### Server transcription

`pyproject.toml`: add under `[dependency-groups]` `speech = ["faster-whisper>=1.0"]`. It is **not** a default dependency; install with `uv sync --dev --group speech`. CI does not install it.

```python
@dataclass(frozen=True, slots=True)
class Transcript:
    text: str
    confidence: float | None    # 0..1, None when the engine gives none
    duration_seconds: float

class Transcriber(Protocol):
    def transcribe(self, wav_bytes: bytes) -> Transcript: ...

class FasterWhisperTranscriber:
    def __init__(self, model: str = "base.en") -> None: ...   # lazy import; device="cpu", compute_type="int8"
    def transcribe(self, wav_bytes: bytes) -> Transcript: ...

class SpeechUnavailable(RuntimeError): ...

def get_transcriber() -> Transcriber:   # FastAPI dependency; cached instance; raises SpeechUnavailable on ImportError
```

`FasterWhisperTranscriber.transcribe`: write nothing to disk; pass `io.BytesIO(wav_bytes)` to `model.transcribe(..., language="en", beam_size=1, vad_filter=True)`. Text = segments joined and stripped. Confidence = `exp(mean(segment.avg_logprob))` clipped to `[0, 1]`, `None` when there are no segments. Before using the library for the first time, read its README for the current `transcribe` signature; do not guess parameter names.

Endpoint:

```
POST /api/v1/transcribe        Content-Type: audio/wav      body = the WAV bytes
→ 200 {"text": str, "confidence": float | null, "needs_confirmation": bool, "duration_seconds": float}
```

- Read the body with `await request.body()` (no multipart dependency). Reject: wrong content type → 415; empty or larger than `speech.max_bytes` → 413; not a RIFF/WAVE header (`body[:4] == b"RIFF" and body[8:12] == b"WAVE"`) → 400; duration above `speech.max_seconds` (read with the standard `wave` module) → 413.
- `needs_confirmation = confidence is None or confidence < speech.confirm_below or not text`.
- `SpeechUnavailable` → 503 `speech transcription is not installed on this server`.
- The endpoint only transcribes. The client then calls `/ask` with `modality="speech"` and `transcript_confidence`. Audio is never stored.

### App behaviour (built in WP31)

1. Tap the microphone. The app asks the platform recogniser (`speech_to_text`) to listen in `en_US`, at most 10 seconds, stopping after 2 seconds of silence.
2. While listening, show the partial words and a Stop button.
3. Final result with confidence ≥ 0.80: put the words in the text field and send them (`modality: "speech"`).
4. Final result with confidence below 0.80, or with no confidence reported (the plugin reports 0 or −1 on some devices): show `I heard: "<words>"` with two buttons, **Ask** and **Edit**. Edit puts the words in the text field and focuses it.
5. Recogniser unavailable, permission denied, or no words: show `Voice is not available. Please type your question.` and focus the text field (UC-02 A1).

The app does not record audio for the server endpoint in this plan. Reason to state in the report: NFR-U4 makes speech best-effort, and on-device recognition avoids sending audio off the phone.

### `scripts/evaluate_speech.py` (AC-13)

Input: a directory with `queries.tsv` (columns `file`, `speaker`, `text`) and the WAV files (16 kHz mono; recorded from the test speakers reading the ten benchmark questions).

For each row: transcribe with `FasterWhisperTranscriber`; compute word accuracy `1 − WER`; run `answering.answer` on the reference text and on the transcript against `--home-id`, with `--now`; the pair is *equivalent* when `status`, `intent`, primary `instance_id` and `facts.get("polarity")` are equal.

`aegis.evaluation.word_error_rate(reference, hypothesis) -> float`: lower-case, strip punctuation, word-level Levenshtein distance divided by the reference length (0 words → 0.0 when both empty, else 1.0).

Output through `scripts/_evidence.py` (`run_header`, `write_result`): per-row results, mean word accuracy, equivalent count, speakers. Targets: mean word accuracy ≥ 0.80, equivalent on 10 of 10 (report the real number).

The on-device recogniser is measured by hand in WP34 (P13) because it cannot be scripted.

### Tests (`tests/test_speech.py`)
- `test_word_error_rate` (identical → 0; one substitution in four words → 0.25; empty cases).
- `test_transcribe_endpoint_with_fake` — override `get_transcriber` through `app.dependency_overrides` with a fake returning `Transcript("where are my keys", 0.93, 1.2)`; build a valid WAV in memory with the `wave` module; assert 200 and `needs_confirmation is False`.
- `test_low_confidence_needs_confirmation` (0.5 → `True`), `test_missing_confidence_needs_confirmation`.
- `test_rejects_wrong_type_empty_oversize_and_non_wav` (415, 413, 413, 400).
- `test_unavailable_engine_is_503`.
- `test_speech_and_text_give_the_same_answer` — `/ask` with `modality="speech"` and the same text as a typed request returns the same `status` and `instance_id`; the `query_log` row has `modality = 'speech'`.

### Done when
Todo §3.2 item 1 (decision) and item 3 (transcript + confidence, server side) can be ticked. Items 2 and 4 are ticked in WP31 and WP34.

---

## WP24 — Optional LLM query planner

**Status:** optional (report: "VLM/tool-calling agent … optional"). If the team skips it, record "deferred: rule-based parser meets AC-09/AC-10" in the Definition of Done and do not build it. Nothing else in Part II depends on it.

**Design, if built.** The model is a *parser of last resort*. It receives only the user's sentence and returns a `ParsedQuery`-shaped JSON object. It never sees memory contents and never writes answer text, so it cannot invent a location (TC5).

- Files: `src/aegis/llm/planner.py`, `tests/test_llm_planner.py`; dependency group `llm = ["anthropic"]`.
- Trigger: `AEGIS_LLM_PLANNER=1` **and** the rule parser produced `intent == "where"` with `item is None`, or `action == "unknown"`. In every other case the rules win.
- Call: one request with a 2-second timeout to `claude-haiku-5-5`, asking for a JSON object `{"intent", "subject", "item_text", "room_text", "time_text", "action"}` with the enumerations of WP18. Read the Anthropic SDK documentation for the exact request shape before writing the call.
- Validation: `intent` and `action` must be in the WP18 enumerations; `item_text` is resolved with `vocabulary.resolve_query` (not trusted as an id); `time_text` goes through `parse_time_window`; `room_text` through `extract_room_filter`. Any error, timeout, invalid JSON or unknown value → keep the rule-based result.
- Privacy: the sentence leaves the laptop. State this in `docs/privacy_limitations.md` and keep the feature off by default.
- Tests use a fake client; no network.

Event captions by a VLM (decision M8) remain out of scope for Part II: answers are grounded by crops and templates.

---

## WP25 — Accounts, sessions, grants, consent and audit (store level)

**Goal:** the authentication and authorisation mechanism as pure store operations, testable without HTTP (FR8.1, FR8.4, FR8.5, NFR-S3, UC-07; todo 4.2).

### Files
- New: `src/aegis/memory/auth.py`, `tests/test_auth.py`.
- Change: `src/aegis/memory/cli.py`.

### Constants and types

```python
ROLE_PRIMARY, ROLE_CAREGIVER = "primary", "caregiver"
SCOPE_OBJECT_STATE, SCOPE_HISTORY, SCOPE_SUMMARIES, SCOPE_ROOMS = "object_state", "history", "summaries", "rooms"
ALL_SCOPES = frozenset({...})
DEFAULT_CAREGIVER_SCOPES = (SCOPE_OBJECT_STATE, SCOPE_SUMMARIES)     # NFR-S2
CONSENT_VERSION = "2026-11"

@dataclass(frozen=True, slots=True)
class Principal:
    user_id: int | None
    username: str
    role: str
    scopes: frozenset[str]          # primary: ALL_SCOPES
    history_days: int | None        # caregiver limit; None = no limit
    display_name: str | None = None

class AuthError(Exception):
    def __init__(self, reason: str) -> None: ...   # reason is one of the codes below
```

Reason codes: `invalid_credentials`, `account_locked`, `account_disabled`, `invite_pending`, `invite_invalid`, `no_active_grant`, `grant_revoked`, `grant_expired`, `weak_password`, `invalid_username`, `username_taken`, `session_expired`.

### Functions (all take `store` first and `now: datetime` where time matters)

| Function | Behaviour |
|---|---|
| `validate_username(name)` | 3–64 characters from `[A-Za-z0-9._@+-]`, else `AuthError("invalid_username")`. Email addresses fit (UC-07 "invites a caregiver by email address"). |
| `hash_password(password, *, min_length)` | `AuthError("weak_password")` when shorter than `min_length` or longer than 128. `salt = secrets.token_bytes(16)`; `hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)`. Stored text: `scrypt$16384$8$1$<salt b64>$<hash b64>`. |
| `verify_password(password, stored)` | Parse the stored text, recompute with the stored parameters, compare with `hmac.compare_digest`. A malformed or `None` value returns `False`. |
| `create_user(store, username, role, *, password=None, display_name=None, now)` | Insert; `status="active"` with a password, `"invited"` without. Duplicate → `username_taken`. Returns `user_id`. |
| `record_consent(store, user_id, kind, *, subject_id=None, now)` / `withdraw_consent(...)` | Insert a row / set `withdrawn_at` on the open row. |
| `invite_caregiver(store, primary_id, username, *, scopes, history_days, expires_at, display_name, now, config)` | Validate scopes ⊆ `ALL_SCOPES` and non-empty. Create the caregiver as `invited`; `code = secrets.token_urlsafe(9)`; store `sha256(code)` and `invite_expires_at = now + invite_hours`. Insert the `access_grant`. Record `caregiver_access` consent for the primary user with `subject_id = caregiver_id`. Returns `(caregiver_id, grant_id, code)`. The code is shown once and never stored in clear. |
| `accept_invite(store, username, code, password, *, now, config)` | User must be `invited`, the code must match by `compare_digest`, not expired; set the password, `status="active"`, clear the invite fields. Else `invite_invalid`. |
| `active_grant(store, caregiver_id, now)` | Newest grant with `revoked_at IS NULL` and (`expires_at IS NULL` or `expires_at > now`). Returns a dict or `None`. |
| `update_grant(store, grant_id, *, scopes=None, history_days=..., expires_at=..., now)` | "Restrict": change fields, set `updated_at`. Unknown id → `KeyError`. |
| `revoke_grant(store, grant_id, now)` | Set `revoked_at`; withdraw the matching consent. Sessions are **not** deleted: the next request is refused by the grant check and that refusal is logged with the caregiver's name. |
| `login(store, username, password, *, now, config, remote_addr=None)` | Steps below. Returns `(token, Principal, expires_at)`. |
| `resolve_token(store, token, now)` | `sha256(token)` lookup; `None` when missing, revoked or expired. Then load the user (`disabled` → `None`) and build the `Principal`; for a caregiver use `active_grant`; no active grant → raise `AuthError("grant_revoked")` or `("grant_expired")` so the caller can log the precise reason. |
| `logout(store, token, now)` | Set `revoked_at`. |
| `change_password(store, user_id, old, new, *, now, config)` | Verify the old one, store the new hash, revoke the user's other sessions. |
| `record_audit(store, *, at, username, action, result, user_id=None, role=None, reason=None, detail=None, remote_addr=None)` | Insert. `detail` is cut to 200 characters. |
| `list_audit(store, *, since=None, limit=200, role=None)` | Newest first. |
| `purge_audit(store, before_iso)` | Delete older rows; returns the count. |
| `purge_sessions(store, now)` | Delete `auth_session` rows expired more than a day ago. |

`login` steps:

1. Count `audit_log` rows with this username (case-insensitive), `action = 'auth.login'`, `result = 'denied'`, `at >= now − lockout_minutes`. If the count is `>= max_failed_logins`: audit `denied / account_locked`, raise.
2. Load the user. If there is none, run `verify_password(password, DUMMY_HASH)` anyway (a module-level hash computed at import) so timing does not reveal which names exist; audit `denied / invalid_credentials`; raise `invalid_credentials`.
3. `status == "invited"` → `invite_pending`; `"disabled"` → `account_disabled`. Both audited as denied.
4. Wrong password → audit denied, raise `invalid_credentials`.
5. Caregiver without an active grant → audit denied with `no_active_grant`, raise.
6. `token = secrets.token_urlsafe(32)`; insert `auth_session` with `sha256(token)` and `expires_at = now + session_minutes`; audit `allowed`.

Every denial writes exactly one audit row with the username **as typed** (AC-16). Passwords and tokens are never written to the log, the audit table or an exception message.

### CLI (`aegis-memory`)

Restructure `main` so each sub-command adds its own arguments (the current loop over four names does not scale). New sub-commands; all accept `--home-id`, `--store-root`, `--config-path`:

```
aegis-memory user add --username NAME --role primary|caregiver [--display-name TEXT] [--password-stdin] --consent
aegis-memory user list
aegis-memory user disable --username NAME
aegis-memory user passwd --username NAME [--password-stdin]
aegis-memory audit list [--limit N]
```

- Without `--password-stdin` the password is read twice with `getpass.getpass`.
- `user add --role primary` requires `--consent` and records a `capture` consent row. Without the flag print: `The primary user (or their authorised representative) must consent to capture. Re-run with --consent once consent has been given.` and exit 2.
- Only one active primary user may exist; a second is refused (single home, single patient).
- `user add --role caregiver` is for tests and recovery; the normal path is the invite (WP26).

### Tests (`tests/test_auth.py`)
- `test_hash_roundtrip_and_format`, `test_weak_password_rejected`, `test_malformed_hash_is_false`.
- `test_login_success_returns_token_and_principal`.
- `test_five_invalid_credentials_are_denied_and_logged` — wrong password, unknown user, empty password, invited-but-not-accepted user, disabled user: five `AuthError`s, five `audit_log` rows with `result='denied'`, each with the typed username, a timestamp and a reason (AC-16).
- `test_lockout_after_repeated_failures_and_expiry` (sixth attempt with the right password is `account_locked`; after `lockout_minutes` it works).
- `test_unknown_user_takes_the_dummy_path` (monkeypatch `verify_password` to count calls).
- `test_invite_accept_flow`, `test_invite_code_is_single_use_and_expires`.
- `test_revoked_grant_blocks_existing_token` — `resolve_token` raises `grant_revoked` for a token issued before the revocation (AC-17 at store level).
- `test_expired_grant_and_expired_session`.
- `test_restrict_changes_scopes_on_next_resolve`.
- `test_token_is_not_stored_in_clear` — the raw token does not appear in any column of `auth_session`.
- `test_audit_purge_keeps_thirty_days`.
- `test_cli_user_add_requires_consent` and `test_cli_second_primary_is_refused`.

### Done when
The tests pass and no HTTP code was touched.

---

## WP26 — API enforcement, scopes, CORS and access endpoints

**Goal:** every request is authenticated and authorised; caregivers act only inside their grant; every caregiver access is logged and visible to the primary user (FR8.1–FR8.6, NFR-S2, NFR-S3; AC-16, AC-17, AC-18, AC-26; todo 4.2 all, §6 C8).

### Files
- New: `src/aegis/remote/security.py`, `tests/test_security_api.py`, `tests/_secure.py` (fixtures).
- Change: `src/aegis/remote/api.py`, `run_server.py`, `tests/conftest.py`, `docs/running_aegis.md`.

### `remote/security.py`

```python
def auth_disabled() -> bool: return os.getenv("AEGIS_AUTH_DISABLED") == "1"

LOCAL = Principal(None, "local", ROLE_PRIMARY, ALL_SCOPES, None)

def auth_store() -> HomeStore: return get_store(server_home())

def current_principal(request: Request) -> Principal: ...
def optional_principal(request: Request) -> Principal | None: ...
def guard(action: str, *, scope: str | None = None, primary_only: bool = False): ...   # returns a dependency
def authorise(request, principal, *, action, scope=None, primary_only=False, detail=None) -> None: ...
```

`current_principal`:
1. `auth_disabled()` → `LOCAL`.
2. Header `Authorization: Bearer <token>`; missing or malformed → 401 `authentication_required` with `WWW-Authenticate: Bearer`.
3. `resolve_token(auth_store(), token, current_time())`. `None` → audit (`username="unknown"`, `action="auth.token"`, `denied`, `session_expired`) and 401. `AuthError` → audit with the caregiver's username and the reason, 403 with that reason as `detail`.

`authorise` (called by `guard`, and directly by `/ask` and `/query` because their scope depends on the parsed intent):
1. **Home check.** If the request has a `home_id` query parameter (or body field, passed in by the caller) and it differs from `server_home()` → 403 `wrong_home`.
2. `primary_only` and role is not primary → denied `not_permitted`.
3. `scope` given, role is caregiver, `scope not in principal.scopes` → denied `out_of_scope`.
4. Audit: write a row when the role is caregiver (allowed or denied), and for any denial. A primary user's allowed read is not audited (their questions are in `query_log`); their access-management and deletion actions are (the endpoints do it).
5. Denied → `HTTPException(403, detail=<reason>)`.

`resolve_repository` change: when auth is on and the caller gave no `dataset_id`, always use `server_home()`. A `dataset_id` request with auth on requires `primary_only` (the demo datasets are a developer feature).

### Route policy (complete; anything not listed is `primary_only`)

| Route | Requirement | Audit action |
|---|---|---|
| `GET /health` | public. Without a valid token it returns only `status`, `version`, `auth_required`, `home_id`, `clock_override`, `as_of`; counts are filled only for an authenticated caller. | — |
| `POST /auth/login`, `POST /auth/accept` | public | `auth.login`, `auth.accept` |
| `POST /auth/logout`, `GET /auth/me`, `POST /auth/password` | any authenticated user | `auth.logout`, —, `auth.password` |
| `GET /query`, `POST /ask` — intent `where` without a window | scope `object_state` | `query.where` (detail: the question) |
| `GET /query`, `POST /ask` — any other intent or a window | scope `history`; `max_history_days = principal.history_days` | `query.history` |
| `GET /objects` (WP29) | scope `object_state` | `objects.list` |
| `GET /evidence/{id}`, `GET /crops/{id}?home_id=` | scope `object_state` | `evidence.view` |
| `GET /timeline`, `GET /sessions` (WP29) | scope `history` | `timeline.view` |
| `GET /activities`, `GET /summary/daily` (WP29) | scope `summaries` | `summary.view` |
| `GET /rooms` | scope `rooms` | `rooms.list` |
| `POST /rooms/rename` | scope `rooms` | `rooms.rename` (detail: id and new label) |
| `GET /capture/status` | any authenticated user | — |
| `POST /transcribe` | any authenticated user | — |
| `POST /capture/pause`, `POST /capture/resume` | primary | `capture.pause`, `capture.resume` |
| `GET/POST/PATCH/DELETE /access/grants…`, `GET /access/log` | primary | `access.grant`, `access.update`, `access.revoke`, `access.log.view` |
| `POST /history/delete` (WP28) | primary + password | `history.delete` |
| `GET /video/{dataset_id}`, `GET /scene_graph`, `GET /anchors`, `GET /datasets`, `POST /dataset/select`, `GET /crops/{id}?dataset_id=`, all `/simulate*`, `POST /reset` | primary; simulator routes also need `AEGIS_ENABLE_SIMULATOR=1` as today | `video.view` etc. |

Raw video is therefore never reachable with a caregiver token (NFR-S2). For history routes with a caregiver `history_days` limit: `/timeline`, `/activities`, `/sessions` clamp `start` to `now − history_days`; `/summary/daily` for an older date → 403 `outside_history`.

The simulator presets move from `GET` to `POST` (`/simulate/floor` etc.); update `ApiService.simulatePreset`, `run_server.py`'s printed hints and `tests/test_mid1_prototype.py` / `tests/test_api.py` accordingly. A `GET` must not change memory.

### Auth and access endpoints

```
POST /api/v1/auth/login     {username, password}
  → 200 {token, token_type: "bearer", expires_at, user: {username, role, display_name, scopes, history_days, home_id}}
  → 401 {"detail": "invalid_credentials"} | 403 {"detail": "no_active_grant" | "invite_pending" | "account_disabled"} | 429 {"detail": "account_locked"}
POST /api/v1/auth/accept    {username, invite_code, password}   → 200 {"status": "ok"} | 400 {"detail": "invite_invalid" | "weak_password"}
POST /api/v1/auth/logout    → 200
GET  /api/v1/auth/me        → the `user` object
POST /api/v1/auth/password  {old_password, new_password}

GET    /api/v1/access/grants                 → [{grant_id, username, display_name, status, scopes, history_days, granted_at, expires_at, revoked_at, consent_given_at}]
POST   /api/v1/access/grants                 {username, display_name?, scopes?, history_days?, expires_at?}
                                              → 201 {grant_id, username, invite_code, invite_expires_at}
PATCH  /api/v1/access/grants/{grant_id}      {scopes?, history_days?, expires_at?}
DELETE /api/v1/access/grants/{grant_id}      → 200 {"status": "revoked"}
GET    /api/v1/access/log?since=&limit=      → [{at, username, role, action, result, reason, detail}]
```

Login must never reveal whether a username exists: unknown user and wrong password both return 401 `invalid_credentials`. With auth disabled, `/auth/login` returns 409 `auth_disabled` and `/auth/me` returns the `LOCAL` user. Request bodies are pydantic models with length limits (username ≤ 64, password ≤ 128, display name ≤ 60).

### CORS

Replace the wildcard:

```python
origins = [o.strip() for o in os.getenv("AEGIS_CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=None if origins else r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=False,                       # bearer header, no cookies
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
```

The Android app is not a browser and is not affected. The Flutter web build is served from `localhost` in development; for another origin the operator sets `AEGIS_CORS_ORIGINS`.

### Input validation sweep (§6 C8)

Every route parameter named `dataset_id` or `home_id` must pass through `_validated`. Check each route in `api.py`; `simulate_transition` takes `dataset_id` in the body and `get_active_dataset` validates it — confirm with a test. `room_id`, `instance_id`, `evidence_id`, `grant_id` are typed `int` in the signatures.

### `run_server.py`

New flags: `--home-id` (sets `AEGIS_HOME_ID`), `--config` (`AEGIS_CONFIG`), `--no-auth` (sets `AEGIS_AUTH_DISABLED=1`, prints a three-line warning, binds `127.0.0.1` only). Default is auth on. With auth on and no active primary user in the home store: print

```
No primary user exists for home '<id>'. Create one first:
  uv run aegis-memory user add --home-id <id> --username <name> --role primary --consent
```

and exit with status 2. The banner prints `Auth: required` or `Auth: DISABLED (developer mode)`. Simulator hints are printed only with `--enable-simulator`.

### Test fixtures (`tests/_secure.py`)

```python
@pytest.fixture
def secure(tmp_path, monkeypatch):
    """Auth on, home 'homeS' with a primary user, one caregiver and a small memory."""
```
It: removes `AEGIS_AUTH_DISABLED`; sets `AEGIS_STORE_ROOT`, `AEGIS_HOME_ID=homeS`, `AEGIS_NOW`; opens the store, ingests two sessions (keys, mug, two rooms, one crop), creates `patient` (primary, with consent), invites `carer@example.com` with the default scopes and accepts the invite; yields an object with `client`, `login(username, password) -> headers`, `primary` and `carer` header dicts and `store`; calls `close_stores()` and `reset_settings()` on teardown.

### Tests (`tests/test_security_api.py`)

- `test_every_route_needs_a_token` — iterate `app.routes`; for every path under `/api/v1/` except `/health`, `/auth/login`, `/auth/accept`, send the route's method without a token and assert 401. This test fails automatically when someone adds an unprotected route.
- `test_five_invalid_credentials_are_denied_and_logged` — HTTP version of the WP25 test, plus a request with a made-up token; all denied; `GET /access/log` as the primary user shows the rows with username, time and result (AC-16).
- `test_login_does_not_reveal_usernames` (same status and body for unknown user and wrong password).
- `test_revocation_blocks_the_next_request` — caregiver token works; primary `DELETE`s the grant; the same token gets 403 `grant_revoked`; a new login gets 403 `no_active_grant`; both are in the log (AC-17).
- `test_restricting_scopes_applies_immediately` (`PATCH` removes `summaries`; `/summary/daily` → 403).
- `test_five_caregiver_actions_appear_in_the_log` — query, objects list, evidence image, daily summary, one denied timeline request: five rows, in order, with action names (AC-18).
- `test_caregiver_scope_matrix` — default grant: three in-scope requests succeed (`/ask` where, `/objects`, `/summary/daily`); two out-of-scope are refused with 403: `GET /video/<session>` and `POST /ask {"text": "what did she do last week"}` (AC-26). Also `/scene_graph`, `/access/grants`, `/history/delete` → 403.
- `test_history_days_limit` (grant with `history`, `history_days=1`).
- `test_caregiver_answers_use_the_carer_voice` — the answer text does not contain `Your ` or `You `.
- `test_rooms_rename_needs_the_rooms_scope` (403 without, 200 with; AC-31 behaviour unchanged).
- `test_other_home_is_refused` (`home_id=other` → 403 `wrong_home`).
- `test_mutating_routes_are_primary_only` — rename without scope, `dataset/select`, `reset`, `simulate_transition`, `capture/pause`.
- `test_simulator_presets_are_post`.
- `test_cors_has_no_wildcard` — a preflight from `https://evil.example` gets no `access-control-allow-origin`; one from `http://localhost:5000` does.
- `test_public_health_hides_counts`.
- `test_passwords_and_tokens_never_reach_logs` — `caplog` at DEBUG during login and a failed login; neither secret appears.
- `test_auth_disabled_keeps_old_behaviour` (one legacy request without a token under `AEGIS_AUTH_DISABLED=1`).

### Done when
All of todo §4.2 can be ticked; `grep -n 'allow_origins=\["\*"\]' src` finds nothing; the 326 pre-existing tests still pass untouched except the simulator `GET`→`POST` change.

---

## WP27 — Encryption at rest and TLS

**Goal:** AES-256 for the memory store, evidence crops and `home_map.json`; TLS between the app and the gateway (NFR-S1, AC-20, decision #5; todo 4.3 item 1).

### Files
- New: `src/aegis/core/keys.py`, `src/aegis/core/crypto.py`, `scripts/verify_encryption.py`, `tests/test_encryption.py`, `tests/test_tls_cert.py`, `docs/security.md`.
- Change: `pyproject.toml` (`uv add sqlcipher3 cryptography`), `src/aegis/memory/store.py`, `src/aegis/memory/evidence.py`, `src/aegis/memory/home_registry.py`, `src/aegis/memory/cli.py`, `src/aegis/remote/api.py`, `run_server.py`.

### Keys (`core/keys.py`)

- The master key is 32 random bytes written as 64 hex characters.
- `load_store_key(home_id) -> bytes | None`, first hit wins: `AEGIS_STORE_KEY` (hex) → file named by `AEGIS_STORE_KEY_FILE` → `~/.config/aegis/keys/<home_id>.key` if it exists → `None`. A value that is not exactly 64 hex characters raises `ValueError` (never fall back to plaintext on a malformed key).
- `generate_store_key(home_id, path=None) -> Path`: create the directory with mode `0700`, write the file with `os.open(..., O_WRONLY | O_CREAT | O_EXCL, 0o600)`; refuse to overwrite.
- `derive(master, purpose: bytes) -> bytes`: HKDF-SHA256, 32 bytes, `info=purpose`. `db_key = derive(master, b"aegis/db/v1")`, `file_key = derive(master, b"aegis/files/v1")`.
- The key file must **not** live under the store root. `docs/security.md` says so and tells the operator to back the key up separately; losing it loses the memory.

### Files (`core/crypto.py`)

Format: 4 bytes magic `AEG1`, 12 bytes random nonce, then AES-256-GCM ciphertext with tag; associated data `b"aegis-file-v1"`.

```python
def encrypt_bytes(key: bytes, data: bytes) -> bytes
def decrypt_bytes(key: bytes, blob: bytes) -> bytes         # InvalidTag → CryptoError
def is_encrypted(blob: bytes) -> bool                        # blob[:4] == b"AEG1"
def write_protected(path: Path, data: bytes, key: bytes | None) -> None   # atomic: temp file + replace; plaintext when key is None
def read_protected(path: Path, key: bytes | None) -> bytes   # plaintext passthrough when the file is not encrypted; CryptoError when it is encrypted and key is None
```

### Store (`memory/store.py`)

- `HomeStore.__init__(self, home_id, path, key: bytes | None = None)`. `self.file_key = derive(key, b"aegis/files/v1") if key else None`.
- With a key: `from sqlcipher3 import dbapi2 as driver` (import inside the branch so machines without the wheel still run unencrypted stores and tests); connect; **first statement** `PRAGMA key = "x'<db_key hex>'"`; then `SELECT count(*) FROM sqlite_master`. A `DatabaseError` here → close and raise `StoreKeyError("wrong key, or the store is not encrypted; run 'aegis-memory encrypt'")`.
- Without a key: standard `sqlite3`. If the file exists and its first 16 bytes are not `b"SQLite format 3\x00"` → `StoreKeyError("this store is encrypted; set AEGIS_STORE_KEY or AEGIS_STORE_KEY_FILE")`.
- `row_factory = driver.Row`. The rest of the class is unchanged; `sqlite3.Row` in type hints may stay.
- `open_store(home_id, store_root=None, *, key=_UNSET)`: when `key` is not passed, `key = load_store_key(home_id)`. If `AEGIS_REQUIRE_ENCRYPTION=1` and the key is `None` → `StoreKeyError`.
- The v1→v2 backup copy made in WP16 is plaintext only when the store is plaintext; for an encrypted store it is a copy of the encrypted file. Keep that behaviour.

### Evidence and registry

- `evidence.copy_into_store`: replace `shutil.copyfile` with `write_protected(target, source.read_bytes(), store.file_key)`. The `bytes` column stores the **plaintext** length (`_attach_evidence` compares it with the new crop's file size).
- `api._read_evidence_file` (WP20): `read_protected(path, store.file_key)`.
- `home_registry.save_registry(registry, base_dir, key=None)` writes through `write_protected`; `load_registry(home_id, base_dir, key=None)` reads through `read_protected` and treats `CryptoError` like a corrupt file (empty registry). `export_registry(store)` and the seeding call in `open_store` pass `store.file_key`.

### `aegis-memory encrypt --home-id ID`

1. Refuse when the store is already encrypted.
2. Key: use `load_store_key`; when there is none, `generate_store_key` and print its path.
3. Open the plaintext file with the `sqlcipher3` driver and no key; `PRAGMA wal_checkpoint(TRUNCATE)`; read `PRAGMA user_version`.
4. `ATTACH DATABASE '<dir>/memory.enc.db' AS enc KEY "x'<db_key hex>'"`; `SELECT sqlcipher_export('enc')`; `PRAGMA enc.user_version = <n>` (the export does not carry it over); `DETACH DATABASE enc`.
5. Verify: open `memory.enc.db` with the key; every table's row count equals the plaintext count; `user_version` equal.
6. Replace: delete `memory.db-wal`, `memory.db-shm`, any `memory.v*.bak.db`; `os.replace("memory.enc.db", "memory.db")`.
7. Encrypt in place every file under `<home>/evidence/` that is not already encrypted, and `home_map.json`.
8. Print a report: tables, rows, files encrypted, key path. Any failure before step 6 leaves the original untouched and exits 1.

`aegis-memory rekey` is out of scope; say so in `docs/security.md`.

### TLS

- `aegis-memory tls-cert --host <LAN IP> [--host …] [--out ~/.config/aegis/tls]`: with `cryptography`, generate an EC P-256 key and a self-signed certificate (CN `aegis`, SAN: `localhost`, `127.0.0.1`, `10.0.2.2` and every `--host`; validity 825 days). Write `aegis.key` (mode `0600`) and `aegis.crt`; print the SHA-256 fingerprint of the DER certificate as 64 lower-case hex characters. Refuse to overwrite without `--force`.
- `run_server.py --tls-cert PATH --tls-key PATH`: pass `ssl_certfile` / `ssl_keyfile` to `uvicorn.run`; print the URL with `https://` and the fingerprint. Binding rule: with TLS → `0.0.0.0`; without TLS → `127.0.0.1` only, unless `--insecure-http` is given (prints `WARNING: serving memory over plain HTTP on the network`). `adb reverse` keeps working over loopback, so USB development needs no certificate.
- `run_server.py` sets `AEGIS_REQUIRE_ENCRYPTION=1` unless `--allow-plaintext`.
- `/health` gains `tls: bool` (`request.url.scheme == "https"`) and `encrypted_at_rest: bool` (only for an authenticated caller).
- The app pins the fingerprint (WP30).

### `scripts/verify_encryption.py` (AC-20 inspection)

`--home-id`, `--store-root`, `--probe TEXT` (a room or object label known to be in the store; repeatable). Checks, each printed PASS/FAIL, exit 1 on any FAIL:
1. `memory.db` does not start with `SQLite format 3`.
2. No probe string occurs in the raw bytes of `memory.db`, `memory.db-wal` or `home_map.json`.
3. No file under `evidence/` starts with the JPEG magic `FF D8`; every one starts with `AEG1`.
4. `home_map.json` is not parseable as JSON.
5. Opening with the configured key works and `counts()` is non-empty.
6. Optional `--url https://…`: a TLS handshake succeeds and the certificate fingerprint equals `--fingerprint`; the same host on `http://` is refused or not listening.
Writes a result file through `scripts/_evidence.py`.

### Tests

`tests/test_encryption.py` (skip the module with `pytest.importorskip("sqlcipher3")`; CI installs it because it is a normal dependency)
- `test_encrypted_store_roundtrip` (ingest, close, reopen with the key, same `latest_states`).
- `test_database_file_has_no_plaintext` (header and a known label are absent from the raw bytes, including the WAL before checkpoint).
- `test_wrong_key_is_refused`, `test_missing_key_on_encrypted_store_is_refused`, `test_key_on_plaintext_store_is_refused`.
- `test_malformed_key_raises_not_plaintext_fallback`.
- `test_require_encryption_flag`.
- `test_evidence_and_home_map_are_encrypted_and_served` (file starts with `AEG1`; `/api/v1/evidence/{id}` returns a JPEG beginning `FF D8`).
- `test_crypto_roundtrip_and_tamper_detection` (flip one byte → `CryptoError`).
- `test_encrypt_command_migrates_a_plaintext_home` (row counts equal, `user_version` kept, old files gone, crops encrypted, restart-equivalence of `latest_states`).
- `test_compaction_and_rename_work_on_an_encrypted_store` (one call each; guards against driver differences).
- `test_key_file_permissions_and_no_overwrite`.

`tests/test_tls_cert.py`
- `test_certificate_has_expected_sans_and_fingerprint` (parse with `cryptography.x509`).
- `test_refuses_to_overwrite`.

### Done when
`uv run python scripts/verify_encryption.py --home-id <id> --probe Kitchen` passes on a real home, and todo 4.3 item 1 can be ticked with that result file.

---

## WP28 — Raw-frame purge, history deletion and the privacy statement

**Goal:** raw frames are gone after 24 hours with a check that proves it (NFR-S4, AC-30); the primary user can delete all history, verifiably (NFR-S5, UC-11, AC-20); the limits are written down (todo 4.3 items 4–6).

### Files
- New: `src/aegis/memory/privacy.py`, `src/aegis/remote/maintenance.py`, `scripts/verify_purge.py`, `docs/privacy_limitations.md`, `tests/test_privacy.py`.
- Change: `src/aegis/memory/cli.py`, `src/aegis/remote/api.py`, `run_pipeline.py`, `docs/live_capture.md`.

### What counts as raw material

A dataset id is **patient material** when the home store has a `session` row with that id, or its dataset directory contains `live_session.json`, and it is not listed in `privacy.exempt_datasets` (consented scripted test recordings and the public demo clips).

```python
@dataclass(frozen=True, slots=True)
class RawRoots:
    captures: Path = Path("captures")
    data: Path = Path("data")
    outputs: Path = Path("outputs")
    volume: str | None = None        # Modal data volume name; None = do not touch the volume

@dataclass(frozen=True, slots=True)
class RawItem:
    location: str    # "capture" | "data" | "outputs" | "volume"
    path: str
    captured_at: datetime
    bytes: int
```

`find_raw_material(roots, store, *, cutoff, exempt) -> list[RawItem]` lists everything captured before `cutoff`:

| Location | What | Age taken from |
|---|---|---|
| capture | `frame_*.jpg` in every directory under `roots.captures` that has `session.json` or `session_state.json` | the file's mtime |
| data | for patient datasets under `roots.data/<id>/`: the `frames/` tree, `video.mp4`, `<id>.mp4` | the store session's `ended_at`, else the directory mtime |
| outputs | for patient datasets under `roots.outputs/<id>/`: `viewer/`, `geometry/`, `objects/evidence/`, `objects/*.json` (everything except `benchmark_stats.json`), only when `privacy.purge_session_outputs` | same |
| volume | `<id>/` on the Modal volume for patient datasets | the store session's `ended_at` |

`live_handoff.promote_live_session` writes to `data/<dataset_id>` (`data_root` defaults to `Path("data")`), so `roots.data` covers promoted live sessions and segments.

`index.jsonl`, `session.json` and `session_state.json` are kept: they hold timestamps and gap records (needed for AC-25), not images. `outputs/_homes` is never touched by the purge.

`purge_raw(roots, store, *, now, retention_hours, exempt, dry_run=False, run=subprocess.run) -> PurgeReport`:
1. `cutoff = now − retention_hours`. `items = find_raw_material(...)`.
2. Delete local files and trees (`unlink`, `shutil.rmtree`). For the volume: `run(["modal", "volume", "rm", "-r", volume, f"{id}"], check=False)`; a non-zero exit is recorded in `errors`.
3. `remaining = find_raw_material(...)` again (for the volume: `modal volume ls <volume> <id>` must fail or be empty).
4. Return `PurgeReport(deleted, bytes_freed, remaining, errors, cutoff)`. `verified = not remaining and not errors`.

If frames of a live capture are purged before they were processed, log a warning with the count; the 24-hour rule wins.

### Where the purge runs

- `aegis-memory purge-frames [--older-than-hours 24] [--captures DIR] [--data-root DIR] [--outputs-root DIR] [--remote] [--dry-run]`: prints the report as JSON; exit 1 when not verified. `--remote` adds the Modal volume named in the config.
- `run_pipeline._ingest_into_home`: after a successful ingest, call `purge_raw` with `--remote` semantics for sessions older than the cutoff (not the one just ingested, unless it is already old).
- `remote/maintenance.py::run_maintenance(now)`: local purge (no volume), `purge_query_log`, `purge_audit`, `purge_sessions`. A daemon thread started in the FastAPI `lifespan` runs it at start-up and then hourly; it is not started when `AEGIS_DISABLE_MAINTENANCE=1`. Exceptions are logged, never raised. `/health` (authenticated) reports `last_maintenance_at` and `raw_frames_overdue` (the length of the last `remaining` list).
- `docs/live_capture.md`: a cron line for laptops that do not keep the server running: `0 * * * * cd <repo> && uv run aegis-memory purge-frames --remote`.

`scripts/verify_purge.py` (AC-30): runs `find_raw_material` with the 24-hour cutoff and writes a result file listing every remaining path; PASS means none.

### History deletion

`delete_history(store, *, roots, now, exempt) -> DeletionReport`:

1. Collect the session ids from `session`.
2. `PRAGMA secure_delete = ON`.
3. One transaction: `DELETE FROM <table>` for each table in `HISTORY_TABLES`, in that order.
4. `PRAGMA wal_checkpoint(TRUNCATE)`; `VACUUM`.
5. Remove `<home>/evidence/` and `<home>/home_map.json`.
6. `purge_raw` for those session ids with `retention_hours = 0` (everything, including the volume when configured).
7. Verify: every table in `HISTORY_TABLES` has 0 rows; the evidence directory and `home_map.json` do not exist; `find_raw_material` with `cutoff = now` returns nothing for those ids. Any failure goes into `report.failures`; `report.verified = not failures`.
8. Accounts, grants, consent and the audit log are kept. The caller writes the audit row.

Endpoint:

```
POST /api/v1/history/delete   {password, confirm}     primary only
```
`confirm` must equal `"DELETE"` (else 400). The password is re-checked with `verify_password` (wrong → 403, audited). On success: 200 with the report and an audit row `history.delete / allowed`. When `verified` is false: **500** with the report and an audit row `history.delete / error` — the system reports the failure instead of claiming success (UC-11 A2). The deletion is immediate and has no undo; there is no soft-delete.

CLI: `aegis-memory delete-history --home-id ID --yes` (same function; refuses without `--yes`).

### `docs/privacy_limitations.md`

Write these sections, in plain statements, each tied to what the code does:

1. **What is stored.** Structured memory (rooms, furniture, objects, state runs, events, summaries), object-only evidence crops, query log, account and audit data. No audio. No full frames after 24 hours.
2. **Evidence crops.** Cut to the object's box plus 15% padding; they can contain background, including parts of a bystander. Kept until the run they belong to is compacted, and the last-known crop is kept longer (`keep_last_evidence`). Decision #9 and its status (confirmed by the supervisor on <date>, or pending). How to turn crops off.
3. **Bystanders.** Recording happens only with the primary user's consent; other household members should be told; test recordings include only consenting participants. The system does not detect or blur faces.
4. **Raw frames.** Where they exist (four places), the 24-hour rule, how it is verified, and that the Modal volume is a cloud service.
5. **Encryption.** What is encrypted (database, crops, room map), with which algorithm, and what is not (data in memory while the server runs; raw frames during their 24 hours; per-session working files until purged). The key is on the same laptop: this protects a copied or stolen store directory, not a compromised running machine.
6. **Access.** One primary user, invited caregivers, scopes, the audit log and its 30-day retention; the lockout can be used to block a caregiver temporarily by guessing wrong passwords.
7. **Deletion.** What "delete history" removes and keeps; backups made outside Aegis are not covered.
8. **Speech and optional language model.** On-device recognition; the optional server transcription; WP24 sends the question text to a cloud model when enabled.
9. **Not a medical device; no clinical claim.**

### Tests (`tests/test_privacy.py`)

All paths under `tmp_path`; file ages set with `os.utime`.
- `test_old_capture_frames_are_removed_and_metadata_kept`.
- `test_frames_younger_than_24h_stay`.
- `test_dataset_frames_video_and_outputs_are_removed_for_home_sessions`.
- `test_exempt_and_non_home_datasets_are_untouched` (a demo dataset directory with frames survives).
- `test_volume_purge_calls_modal_and_reports_failure` (fake `run`).
- `test_verification_lists_what_remains` (make one file undeletable by monkeypatching `Path.unlink` to raise; `verified is False`, the path is in `remaining`).
- `test_dry_run_deletes_nothing`.
- `test_home_store_is_never_purged`.
- `test_delete_history_empties_everything_and_verifies` — after it: all history tables 0 rows, no evidence files, no `home_map.json`, raw frames gone, the user and audit rows still present; a query answers `never_observed`; `open_store` after restart does not resurrect rooms.
- `test_delete_history_api_requires_password_and_confirm` (400, 403, then 200).
- `test_failed_deletion_reports_failure_not_success` (500 and `verified: false`).
- `test_deleted_text_is_not_in_the_database_file` (plaintext store: a unique room label is absent from the raw file after `VACUUM`).
- `test_maintenance_purges_logs_and_frames`.

### Done when
`scripts/verify_purge.py` passes on the development laptop after a real live session older than 24 hours (recorded in WP34), and todo 4.3 items 4–6 can be ticked.

---

## WP29 — Portal API: object states, daily summary, sessions, timeline filters

**Goal:** the server side of the caregiver portal (FR8.2, FR8.3, FR7.4; UC-09, UC-10; AC-25).

### Files
- New: `src/aegis/memory/portal.py`, `tests/test_portal_api.py`.
- Change: `src/aegis/remote/api.py`, `src/aegis/memory/store.py`.

### `GET /api/v1/objects?home_id=` (scope `object_state`)

`portal.object_states(repo, *, now, zone, settings, voice) -> list[dict]`, one entry per instance in `latest_states()`:

```
{instance_id, label, canonical, importance,
 status,            # "answered" | "stale" | "low_confidence"  (WP19 rule)
 freshness,         # "fresh" | "stale" | "unknown"
 place,             # place_phrase(...)  e.g. "on Desk #1 in the Kitchen"; "being carried" for carried
 anchor_label, room_label,
 last_seen_at, last_seen_text,
 confidence,
 evidence}          # one EvidenceRef (WP20)
```
Order: `importance == "high"` first, then most recently seen. For `low_confidence`, `place` is prefixed with `possibly `. This is UC-09: the caregiver sees the state, when it was observed, whether it is stale, and the evidence.

### `GET /api/v1/summary/daily?date=YYYY-MM-DD&home_id=` (scope `summaries`)

`portal.daily_summary(store, day, *, now, zone, settings, voice) -> dict`:

```
{date, tier, text,                       # text: at most two sentences
 recorded_minutes, sessions,             # from session rows overlapping the local day
 rooms: [{room_label, minutes}],         # from room_visit (detailed) or activity sidecars (summarised)
 activities: [ActivityModel],            # detailed tier only
 lines: [str],                           # activity lines (detailed) or summary texts (summarised)
 object_lines: [{label, text}],          # objects that changed that day
 evidence: [EvidenceRef]}
```

- Window = the local day (`compaction._bounds`); a future date → 422.
- Detailed (activity rows exist): `text` = the two sentences of the `self` branch of `answer_what_happened` with the label `describe_day(day)`; `object_lines` = for each instance with events that day, `{label, text: "<n> change(s); last: <event_summary>"}`.
- Summarised (no activity rows, summary rows cover the date at day, week or month level): `tier="summarised"`; `text = "From summarised history, {label}: {n} room visit(s) recorded."`; `lines` = the summary texts; `object_lines` from the object summaries (`text` = the summary text after the label).
- Neither: `tier="detailed"`, `text` = `No activity was recorded {label}.` when no session overlaps the day, else `Recording ran {label} but nothing changed.` (UC-10 A1).

### `GET /api/v1/sessions?home_id=&date=` (scope `history`)

`[{session_id, started_at, ended_at, keyframe_count, time_source, event_count}]`, newest first; `date` filters to sessions overlapping that local day. This feeds the timeline filter.

### `GET /api/v1/timeline` additions

- New query parameters `date` (local day; exclusive with `start`/`end` → 422 when combined) and `session_id`.
- For a home store: convert `start`/`end` to local dates before calling `store.summaries` (fixes the UTC-slice bug in the fact table).
- `StoreRepository.events_between(start, end, session_id=None)` filters on the `session_id` already present in each event.
- Each item keeps `tier`. Items are ordered by time: summaries by `period_start`, then events by `end_wallclock`.
- The response model gains `session_id: str | None`.

### Tests (`tests/test_portal_api.py`) — reuse the `history_store` fixture of WP21 (move it to `tests/_graphs.py`)
- `test_objects_lists_state_time_freshness_and_evidence` (keys stale, mug fresh).
- `test_objects_order_puts_important_first`.
- `test_daily_summary_detailed`, `test_daily_summary_no_recording`, `test_daily_summary_after_compaction_is_labelled_summarised` (UC-10 A2).
- `test_daily_summary_text_is_at_most_two_sentences`.
- `test_sessions_filter_by_local_date` (a session at 23:30 UTC belongs to the next local day in `Asia/Karachi`).
- `test_timeline_filters_by_date_and_session`.
- `test_timeline_matches_the_session_log` — every event row of the store for one session appears once, in chronological order, with matching type and time (AC-25 at fixture level).
- `test_timeline_summary_dates_are_local` (the regression for the UTC-slice bug).

### Done when
The endpoints exist behind the WP26 policy table and the tests pass.


---

## WP30 — App foundation: session, settings, text size, contrast, API client

**Goal:** the app logs in, talks to the home memory, remembers its settings, offers three text sizes and meets WCAG AA text contrast (FR7.3, NFR-U3, AC-24; todo 4.4 base, 4.5 items 1–2).

All paths are under `apps/mobile/`. Flutter rule II.0.1-3 applies to WP30–WP32.

### Files

```
pubspec.yaml                                   + shared_preferences, crypto, speech_to_text (WP31)
lib/main.dart                                  AppScope, text scaler, start-up routing
lib/state/app_state.dart                       NEW  ChangeNotifier: session, text size, mode
lib/services/settings_store.dart               NEW  shared_preferences wrapper
lib/services/http_client_factory.dart          NEW  conditional import
lib/services/http_client_io.dart               NEW  fingerprint pinning
lib/services/http_client_web.dart              NEW
lib/services/api_service.dart                  REWRITE
lib/models/query_result.dart                   extend (Answer fields)
lib/models/evidence_ref.dart, object_state.dart, daily_summary.dart,
           access_models.dart, room_info.dart, session_info.dart, user_session.dart   NEW
lib/models/timeline_event.dart                 extend (tier, wall-clock, session)
lib/theme/app_theme.dart                       text-safe colours, textPairs
lib/views/login_screen.dart                    NEW
lib/views/home_screen.dart                     REWRITE: role-based shell
lib/views/settings/settings_screen.dart        NEW
test/contrast_test.dart, test/api_service_test.dart, test/login_test.dart, test/text_size_test.dart   NEW
test/widget_test.dart                          REWRITE
test/support/fake_server.dart                  NEW  shared MockClient
android/app/src/main/AndroidManifest.xml, res/xml/network_security_config.xml
```

Add packages with `flutter pub add shared_preferences crypto` (and `speech_to_text` in WP31) so the resolver picks versions that match the SDK; commit `pubspec.lock`. Do not add a state-management package.

### Server change needed first
`HealthResponse` gains `home_ready: bool` (the home store has at least one session). Public.

### `AppState` (`lib/state/app_state.dart`)

```dart
enum TextSize { small, medium, large }          // scale 0.9, 1.0, 1.3
enum AppMode { home, dataset }

class AppState extends ChangeNotifier {
  UserSession? session;          // null = not logged in (token kept in memory only)
  bool authRequired = true;      // from /health
  AppMode mode = AppMode.home;
  String? homeId;                // from /health or the login response
  TextSize textSize = TextSize.medium;
  bool caregiverPreview = false; // developer mode only
  double get textScale;
  bool get isCaregiver;          // session?.role == 'caregiver' || caregiverPreview
  bool hasScope(String scope);   // primary / developer mode: always true
}
class AppScope extends InheritedNotifier<AppState> { static AppState of(BuildContext c); }
```

`MaterialApp.builder` wraps the child in `MediaQuery(data: mq.copyWith(textScaler: TextScaler.linear(state.textScale)), child: child)`. Every screen must stay usable at 1.3: replace fixed `childAspectRatio` grids with `mainAxisExtent: 112 * scale`, wrap rows of badges in `Wrap`, and never put scaled text in a fixed-height box.

The token is **not** written to disk. Closing the app means logging in again; sessions last 60 minutes anyway.

### Settings store
Keys: `base_url`, `text_size`, `pinned_fingerprint`, `last_username`. `SettingsStore.load()` at start-up; tests call `SharedPreferences.setMockInitialValues({})`.

### HTTP client and certificate pinning

`http_client_factory.dart`: `export 'http_client_web.dart' if (dart.library.io) 'http_client_io.dart';` Both files define `http.Client createHttpClient({String? pinnedSha256, void Function(String fingerprint)? onUnknownCertificate})`.

- IO (`http_client_io.dart`): `HttpClient()..badCertificateCallback = (cert, host, port) { final fp = sha256.convert(cert.der).toString(); if (pinnedSha256 != null && fp == pinnedSha256) return true; onUnknownCertificate?.call(fp); return false; }` wrapped in `IOClient`. A certificate signed by a public authority never reaches the callback and is accepted normally.
- Web: `http.Client()`; the browser decides. Say in Settings that on the web the certificate must be accepted in the browser.

Trust on first use: when a request fails with a handshake error and `onUnknownCertificate` delivered a fingerprint, show a dialog: `This server's certificate is not known. Fingerprint: <8 groups of 8 hex>. Compare it with the one printed by run_server.py.` Buttons **Trust** (save the pin, rebuild the client, retry) and **Cancel**. A changed fingerprint for an already pinned server shows `The server's certificate has changed.` and offers only Cancel and **Forget and re-check**.

Android manifest: remove `android:usesCleartextTraffic="true"` from `src/main/AndroidManifest.xml` and set `cleartextTrafficPermitted="false"` on the `base-config` of `network_security_config.xml`; keep the `domain-config` that allows cleartext for `localhost`, `127.0.0.1` and `10.0.2.2` (USB `adb reverse` and the emulator). LAN connections must use `https://`. `updateBaseUrl` keeps a typed scheme; for a bare host it now defaults to `https://<host>:8000`, except loopback hosts, which default to `http://`.

### `ApiService` rewrite

- Constructor: `ApiService({String baseUrl, http.Client? client, AppState? state})`. Tests inject a `MockClient`.
- One private `_send(method, path, {query, body})` that: adds `Authorization: Bearer <token>` when logged in; adds the scope parameter (`home_id=<id>` in home mode, `dataset_id=<id>` in dataset mode) for memory routes; applies the 5-second timeout; maps results to

```dart
class ApiResult<T> { final T? data; final ApiError? error; bool get ok; }
enum ApiErrorKind { unreachable, unauthorised, forbidden, notFound, invalid, server }
class ApiError { final ApiErrorKind kind; final String message; final String? reason; }
```
- A 401 on any route clears `state.session` and notifies; the shell then shows the login screen with `Your session has ended. Please sign in again.`
- No method returns invented data. `unreachable` carries the existing message `Can't reach Aegis memory. Check the connection and try again.`
- Methods (each maps to one endpoint): `health()`, `login`, `acceptInvite`, `logout`, `ask(text, {instanceId, modality, transcriptConfidence})`, `objects()`, `timeline({date, sessionId})`, `sessions({date})`, `dailySummary(date)`, `rooms()`, `renameRoom(id, label)`, `grants()`, `createGrant(...)`, `updateGrant(...)`, `revokeGrant(id)`, `accessLog()`, `captureStatus()`, `setCapturePaused(bool)`, `deleteHistory(password)`, `changePassword`, and the developer ones `datasets()`, `selectDataset`, `simulatePreset` (now `POST`), `resetMemory`.
- `evidenceUrl(String path)` returns the absolute URL; `authHeaders` is public so `Image.network(url, headers: api.authHeaders)` can fetch crops.
- The in-memory search history stays, keyed by home or dataset, for the patient's "recent questions".

`QueryResult` gains: `status`, `abstained`, `intent`, `answer`, `tier`, `freshness`, `windowLabel`, `evidence` (`List<EvidenceRef>`), `options`, `items`, `knownItems`, `asOf`, `latencyMs`. Unknown or missing fields parse to safe defaults (`status` defaults to `found ? 'answered' : 'never_observed'`) so the app still works against an older server.

### Start-up flow (`main.dart`)

1. Load settings. Call `health()`.
2. Unreachable → a full-screen `Can't reach Aegis memory` with **Retry** and **Server settings**. No other content.
3. `auth_required == true` and no session → `LoginScreen`.
4. `auth_required == false` (developer mode) → the shell as a primary user, with a thin `Developer mode — sign-in is off` banner. Mode is `home` when `home_ready`, else `dataset`.
5. A health response without the new fields (old server, or the 404 that the old widget tests returned) is treated as developer mode + dataset mode.

### Login screen
Fields: username, password (obscured, with a show/hide toggle), **Sign in**; a link **I have an invite code** that opens three fields (username, code, new password) and calls `acceptInvite`, then signs in. Errors are shown in words: `invalid_credentials` → `That username or password is not right.`; `account_locked` → `Too many attempts. Try again in 15 minutes.`; `no_active_grant` → `Your access has ended. Ask the person you care for to grant it again.`; `invite_pending` → `Use your invite code first.`; unreachable → the standard message. The server address is editable from a gear icon.

### Shell (`home_screen.dart`)
Bottom navigation chosen by role and scopes:

| Role | Tabs |
|---|---|
| Primary (and developer mode) | **Ask** (WP31) · **Timeline** (WP32 timeline tab) · **Settings** |
| Caregiver | **Objects** (`object_state`) · **Summary** (`summaries`) · **Timeline** (`history`) · **Rooms** (`rooms`) · **Account** — a tab is shown only when its scope is granted |

The old "Patient Recall / Caregiver Audit" segmented control is removed: who you are is decided by signing in, not by a switch. In developer mode Settings has **Preview caregiver view**, which shows the caregiver tabs with every scope.

### Settings screen
Sections: **Text size** (three large buttons `A` small, `A` medium, `A` large; the change applies immediately and is saved); **Account** (name, role, sign out, change password); **Server** (address, connection state, certificate fingerprint, forget pin); for the primary user **Sharing** and **Privacy** (WP32); **Developer** (only in developer mode or for the primary user: dataset switcher, simulator when the server enables it, last answer latency, caregiver preview).

### Theme: text colours that meet AA

Measured contrast (white card / `#FAF7F0` canvas). Add these constants and use them for **every text and every icon that carries meaning**; the existing bright colours remain only for fills, borders and decorative icon backgrounds.

| New constant | Value | White | Canvas | Replaces as text colour |
|---|---|---|---|---|
| `textHighContrast` (unchanged) | `#1C1917` | 17.49 | 16.35 | — |
| `textMuted` (change value) | `#57534E` | 7.63 | 7.13 | `#78716C` |
| `textHint` | `#6B655F` | 5.75 | 5.37 | `tertiaryLabel` |
| `brandText` | `#B45309` | 5.02 | 4.69 | `primaryTeal` as text |
| `accentText` | `#92400E` | 7.09 | 6.63 | `tealAccent`, `royalAmethyst`, `#C084FC` as text |
| `warningText` | `#9A3412` | 7.31 | 6.83 | `alertAmber` as text |
| `successText` | `#15803D` | 5.02 | 4.69 | `systemGreen` as text |
| `dangerText` | `#B91C1C` | 6.47 | 6.05 | `systemRed` as text |
| `infoText` | `#4338CA` | 7.90 | 7.39 | `systemIndigo`, `systemBlue` as text |
| `buttonFill` | `#B45309` | white text on it: 5.02 | | the `primaryTeal` gradient behind white text |

On the segmented track `#ECE7DE` only `textHighContrast` and `textMuted` pass; do not put `brandText` there. Snack bars keep `#065F46`, `#0F766E`, `#991B1B` with white text (7.68, 5.47, 8.31).

Expose the pairs the app uses as `static const List<(String name, Color fg, Color bg)> textPairs` in `AppTheme`. After the change, `grep -n "tealAccent\|alertAmber\|tertiaryLabel\|royalAmethyst\|C084FC\|systemGreen\|systemRed\|systemBlue" lib/` must show these colours only in non-text positions (`color:` of a `BoxDecoration`, a border, `withOpacity` fills).

`web/index.html`: change the body background from `#0F172A` to `#FAF7F0` (it flashes dark before the light app loads).

### Tests

- `test/contrast_test.dart`: implement the WCAG relative-luminance formula in the test; every entry of `AppTheme.textPairs` must be ≥ 4.5. Print a table (name, ratio); this printed table is the AC-24 contrast record.
- `test/text_size_test.dart`: pump the app at each of the three sizes on a 360×640 surface; `tester.takeException()` is null (no overflow); the text scaler equals 0.9 / 1.0 / 1.3; changing the size in Settings updates the scaler and is saved.
- `test/api_service_test.dart`: bearer header is sent after login; `home_id` is added in home mode and `dataset_id` in dataset mode; 401 clears the session; unreachable gives `ApiErrorKind.unreachable` and no data; an old-server `QueryResult` JSON parses; bare LAN host becomes `https://…:8000`, loopback stays `http://`.
- `test/login_test.dart`: wrong password shows the message and stays on the login screen; success shows the role's tabs; a caregiver without the `history` scope has no Timeline tab; the invite flow calls `/auth/accept` then `/auth/login`.
- `test/support/fake_server.dart`: one configurable `MockClient` (`FakeServer`) with health, login, ask, objects, timeline, sessions, summary, rooms, grants, access log; it records requests so tests can assert headers and bodies.
- Rewrite `test/widget_test.dart` on top of `FakeServer`. Keep the meaning of the existing cases (answer shown from the server, unreachable shows the message and never a location, the recent-question history, LAN host normalisation, null confidence parsing); drop assertions on dataset-specific tiles and titles, which are being removed.

### Done when
`flutter analyze --no-fatal-infos` and `flutter test` pass in CI; todo 4.5 items 1 and 2 can be ticked with `test/text_size_test.dart` and the printed contrast table.

---

## WP31 — App: patient view

**Goal:** ask by typing or by voice, see a short answer with its evidence, time and place, and choose between several matches (FR6.1, FR6.3, FR7.1, FR7.2, NFR-U2; AC-14; todo 3.2 microphone, 4.4 evidence display).

### Files
```
lib/views/patient/patient_view.dart          REWRITE
lib/views/patient/answer_card.dart           NEW
lib/widgets/evidence_image.dart              NEW
lib/services/speech_input.dart               NEW
android/app/src/main/AndroidManifest.xml     RECORD_AUDIO + recogniser query
test/patient_view_test.dart, test/answer_card_test.dart, test/voice_test.dart   NEW
```

### Remove
`_getDatasetHumanTitle`, `_configureQuickItems` and every branch on a dataset name; the "ACTIVE VIDEO SCENE" card (it moves to Settings › Developer); the `✦ PERSISTENT MEMORY` badge; the `(~0.1m)` distance text; the `"Room Anchor"` placeholder.

### Layout (top to bottom)
1. Prompt line: `Ask where something is, or what you did.`
2. Ask field (`Key('ask-field')`, hint `Type your question`) with a send button (`Key('ask-send')`).
3. Microphone button (`Key('mic-button')`), full width, label `Ask by voice`; while listening the label is `Listening… tap to stop` and partial words show under it.
4. Quick tiles: up to four objects from `GET /objects` (label without the `#n` suffix; high-importance first). Tapping sends `Where is my <label>?`. Icon from a small `canonical → IconData` map (`keys`, `glasses`, `phone`/`cell phone`, `wallet`, `medicine`, `bottle`, `mug`/`cup`, `remote`, `bag`), default `Icons.category_rounded`. No tiles when the list is empty or the server is unreachable.
5. Three suggestion chips, fixed text: `What did I do this morning?`, `Where were my keys yesterday?`, `Did I go to the kitchen today?` Shown only in home mode.
6. The answer card.
7. Recent questions (last three), tap to ask again.

### `AnswerCard`

| Part | Rule |
|---|---|
| Status chip | `answered`, `not_seen_in_window` → `ANSWER`; `stale` → `SEEN EARLIER`; `ambiguous` → `MORE THAN ONE`; `low_confidence` → `NOT SURE`; `never_observed` → `NOT SEEN`; `no_match_in_room` → `NOT IN THAT ROOM`; `no_activity` → `NOTHING RECORDED`; `unsupported_activity`, `unsupported` → `CAN'T TELL`; `future_time` → `NOT YET`; unreachable → `NO CONNECTION`. Colours: `successText` for `ANSWER`, `warningText` for the middle group, `textMuted` otherwise. |
| Answer text | `result.answer`, 20 pt bold, `textHighContrast`. Never truncated. |
| Badge | `From summarised history` when `tier != 'detailed'`. |
| Evidence | The first evidence item. With `cropUrl`: `EvidenceImage` (rounded, max height 220, `semanticLabel: description`). Without, or when the image fails to load: the `description` text in a bordered box with an image-off icon. An abstention without evidence shows `No stored evidence.` |
| Time row | clock icon + `lastSeenText` (or the evidence's `observedAtText`). Hidden when both are null. |
| Place row | pin icon + anchor label and room label joined by `, `. Hidden when both are null. |
| Options | For `ambiguous`: one tappable row per option (`label — place — lastSeenText`); tapping re-asks with `instanceId`. |
| Details | When `items` is non-empty: a `Show details` expander listing them. |

No confidence number is shown to the primary user (low load, TC6); the caregiver views show it as a percentage.

`EvidenceImage` uses `Image.network(api.evidenceUrl(path), headers: api.authHeaders, errorBuilder: …, loadingBuilder: …)`.

### Voice (`speech_input.dart`)

```dart
class SpeechResult { final String words; final double? confidence; final bool isFinal; }
abstract class SpeechInput {
  Future<bool> initialize();                 // false = not available or permission denied
  Future<void> listen(void Function(SpeechResult) onResult, {Duration max, Duration pause});
  Future<void> stop();
}
class PlatformSpeechInput implements SpeechInput { /* speech_to_text */ }
class FakeSpeechInput implements SpeechInput { /* test double: scripted results */ }
```

`PatientView` takes an optional `SpeechInput` (default `PlatformSpeechInput`). `PlatformSpeechInput` maps the plugin's confidence to `null` when it is `<= 0` (some devices report 0 or −1 for "unknown"). Locale `en_US`, `max` 10 s, `pause` 2 s. Read the `speech_to_text` README for the current API and the platform setup before coding; the Android manifest needs `<uses-permission android:name="android.permission.RECORD_AUDIO"/>` and, inside `<queries>`, `<intent><action android:name="android.speech.RecognitionService"/></intent>`.

Behaviour is the five steps of WP23 "App behaviour". The confirm bar has `Key('heard-text')`, `Key('heard-ask')`, `Key('heard-edit')`. Requests made from voice send `modality: "speech"` and the confidence.

### Latency probe (for AC-19)
`PatientView` starts a `Stopwatch` when a question is submitted (for voice: when the final words arrive) and stops it in a post-frame callback after the answer card is built. The last 20 values are kept in `AppState.latencies` and listed in Settings › Developer with their median and maximum. This is the "query received → answer displayed" time.

### Tests
`test/answer_card_test.dart` — one test per status: chip text, answer text, evidence image present when a URL is given, description shown when it is not, `From summarised history` badge, options rendered and tappable, details expander; a test that no card contains a `%` sign in the patient view.
`test/patient_view_test.dart` — typing and sending shows the server's answer; quick tiles come from `/objects`; an unreachable server shows `NO CONNECTION` and no place text; tapping an option re-asks with `instance_id`; five different answers each show answer text, a time and an evidence element (AC-14 at widget level).
`test/voice_test.dart` — high-confidence result is sent at once with `modality: speech`; low-confidence result shows the confirm bar, **Ask** sends it, **Edit** fills the field; missing confidence asks for confirmation; unavailable recogniser shows `Voice is not available. Please type your question.` and focuses the field; typed-only and voice-only flows both complete (AC-24 flows).

### Done when
CI is green; todo §3.2 item 2 and §4.4 item 1 (patient side) can be ticked.

---

## WP32 — App: caregiver portal and primary-user controls

**Goal:** the caregiver can verify object states, read a daily summary, browse the timeline and name rooms; the primary user can share and stop sharing, read the access log, pause capture and delete history (FR7.4, FR8.2–FR8.6; UC-07, UC-09, UC-10, UC-11, UC-13; todo 4.4 all remaining).

### Files
```
lib/views/caregiver/objects_tab.dart        NEW   UC-09
lib/views/caregiver/summary_tab.dart        NEW   UC-10
lib/views/caregiver/timeline_tab.dart       NEW   FR7.4, AC-25
lib/views/caregiver/rooms_tab.dart          NEW   UC-13
lib/views/caregiver/caregiver_view.dart     DELETE (replaced by the tabs)
lib/views/settings/sharing_screen.dart      NEW   UC-07, FR8.5
lib/views/settings/privacy_screen.dart      NEW   UC-11
lib/views/capture_control.dart              move into privacy_screen; keep the widget
test/objects_tab_test.dart, summary_tab_test.dart, timeline_tab_test.dart,
     rooms_tab_test.dart, sharing_test.dart, privacy_test.dart      NEW
```

### Remove
The status card that says `All tracked items are safely stored…`, `Displaced Item Alert … (Fall Hazard)` and `In-Transit Activity`. The server never said these; alerts and hazard detection are out of scope (report §4.2). Also remove the "Active Anchors / Instances" metric tiles computed from the event list, and the `Window: 3.0s - 5.0s` line.

### Objects tab (scope `object_state`)
- A search field at the top (`Check an object…`) that calls `ask` and shows an `AnswerCard` with the confidence percentage visible.
- Below it the list from `GET /objects`: label; place; `Seen <lastSeenText>`; a badge `STALE` (`warningText`) when `freshness == 'stale'`, `NOT SURE` when `status == 'low_confidence'`; the confidence as a percentage; a thumbnail when the evidence has an image. Tapping a row opens a sheet with the full evidence image, description, time, room and anchor.
- A stale row's subtitle reads `Not seen for more than 6 hours` (UC-09 A1).
- Pull to refresh. Empty list: `Nothing has been observed yet.`

### Summary tab (scope `summaries`)
- A date row: previous day, the date (`Mon 16 Nov`), next day (disabled for today), and a calendar button (`showDatePicker`, last date = today, first date = today − 365 days or the grant's `history_days`).
- Content from `GET /summary/daily`: the `text`; a `From summarised history` badge when `tier == 'summarised'`; `Recorded for <n> min in <k> session(s)`; time per room; the activity lines; the object lines.
- No activity: the server's sentence, nothing else.
- 403 `outside_history`: `That day is outside the access you were given.`

### Timeline tab (scope `history`; also the primary user's Timeline)
- Filters: the same date row; a session drop-down filled from `GET /sessions?date=` with `All sessions` first.
- Items in time order. Detailed events: `HH:MM`, the server's `summary`, the room. Summarised items: the period (`12 Nov` or `9–15 Nov`), the text, a `Summarised` badge.
- `TimelineEvent` gains `tier`, `startWallclock`, `endWallclock`, `periodStart`, `periodEnd`, `sessionId`. Dataset mode (no wall-clock) shows `+12.4 s` from `endTime` instead of a clock time.
- Empty: `No events recorded on this day.`

### Rooms tab (scope `rooms`)
- List from `GET /rooms`: label, type, the furniture in it, a pencil button.
- Rename dialog: one field (1–40 characters, trimmed), **Save**. 409 → `Another room already has that name.`; 404 → refresh the list; success → snack bar `Room renamed.` and refresh.
- Rooms named by a caregiver show a small `named` tag (`label_source`; add the field to `RoomModel` on the server and to the model).

### Sharing screen (primary user)
- **People with access**: one card per grant — name, username, status (`Invited`, `Active`, `Ended`), scopes in words (`Check where things are`, `Daily summaries`, `Past events`, `Name rooms`), limit (`Last 7 days` / `No limit`), end date.
- **Invite someone**: username (email), display name, four scope switches (the first two on by default), optional history limit (None, 1, 7, 30 days), optional end date. On success show the invite code once, large, with `Share this code with <name>. It works once and expires in 72 hours.` and a copy button.
- Per grant: **Change** (same form, `PATCH`) and **Stop sharing** (confirm dialog: `Stop sharing with <name>? They will lose access immediately.` → `DELETE`).
- **Access log**: newest first — time, who, what in words (map action codes: `query.where` → `Asked where something is`, `objects.list` → `Viewed object list`, `evidence.view` → `Viewed a picture`, `summary.view` → `Viewed a daily summary`, `timeline.view` → `Viewed the timeline`, `rooms.rename` → `Renamed a room`, `auth.login` → `Signed in`, …; unknown codes are shown as they are), and `Allowed` / `Refused` with the reason. A filter chip `Refused only`.

### Privacy screen (primary user)
- **Recording**: the existing `CaptureControl` switch. Hidden text when capture is not configured: `Recording is not set up on this server.`
- **Delete all history**: a red-outlined button. Step 1 dialog explains: `This removes everything Aegis remembers: objects, places, events, summaries and pictures. It cannot be undone. People you share with keep their accounts but will see nothing.` Step 2: type the password and the word `DELETE`. On 200: `History deleted.` and the app returns to an empty Ask tab. On 500: `Deletion could not be confirmed. Nothing is reported as deleted. Details: …` with the `failures` list (UC-11 A2). On 403: `That password is not right.`
- A link **What Aegis stores** showing the text of `docs/privacy_limitations.md` §1–§3 (copy the text into a Dart constant; keep it in sync).

### Tests
- `objects_tab_test`: stale badge and subtitle; low-confidence badge; evidence sheet; refresh; empty state; confidence shown as a percentage.
- `summary_tab_test`: detailed day; summarised badge; no-activity sentence; date navigation calls the API with the new date; `outside_history` message.
- `timeline_tab_test`: order by time; summarised badge; session filter sends `session_id`; dataset mode shows relative seconds; the items equal the fake server's log in order (AC-25 at widget level).
- `rooms_tab_test`: rename success, 409 message, validation of empty and 41-character names.
- `sharing_test`: invite shows the code once; stop sharing calls `DELETE` after confirmation; the log lists five actions with allowed/refused; `Refused only` filter.
- `privacy_test`: the delete flow needs both the password and `DELETE`; a 500 shows the failure text and never `History deleted.`; the capture switch calls pause/resume.
- A caregiver session never renders the Sharing or Privacy screens (the Settings sections are absent).

### Done when
CI is green and every line of todo §4.4 can be ticked with a widget test name.

---

## WP33 — Benchmark `Aegis-TestSet-v1` and its runner

**Goal:** a documented, repeatable test set and a scorer for SC1–SC3, SC5, SC6, AC-08–AC-12 (todo §5.1; decisions #1, #8). The recordings themselves are made by the team in WP34; this WP builds the format, the tools and their tests.

### Files
- New: `benchmark/aegis_testset_v1/README.md`, `manifest.yaml`, `queries.yaml`, `ground_truth/placements.yaml`, `ground_truth/events.yaml` (templates with one worked example each), `scripts/run_benchmark.py`, `scripts/abstention_curve.py`, `tests/test_benchmark.py`.
- Change: `src/aegis/evaluation.py`.

### Recording protocol (`README.md`)

State, in this order: purpose; owner (assign one team member by name); participants (team members, consenting, no bystanders; a signed consent note per participant kept outside the repository); the home (rooms and anchors with the names used in ground truth); device and capture settings; the scripts below; the limitations (one home, healthy volunteers, scripted actions, single camera wearer, daytime lighting, a small number of objects; results do not generalise to people with dementia).

Scripts to record (each a separate live or batch session, with `--recorded-at`):

| Id | Content | Feeds |
|---|---|---|
| `S1` placements | 10 objects placed one after another at 10 known anchors across at least 2 rooms; each object held to the camera first | AC-04, AC-09, Iteration 1 exit |
| `S2` activity | a scripted sequence across 3 rooms with 8 pick-ups/placements at announced times (clap or spoken marker for the annotator) | AC-05, AC-10 |
| `S3` next day | a second session a day later: 3 objects moved, 7 untouched, one object carried out of view | AC-10, moved-while-unobserved |
| `S4` rooms | a walk through every room with revisits | AC-22 |
| `S5` distractors | a session with objects that are **not** queried later, plus the 5 "never observed" objects kept out of the house | AC-12 |

To exercise compaction without waiting days, the sessions are ingested with `--recorded-at` values spread over five calendar days (documented in `manifest.yaml`). Say so in the report: the recordings are real, the dates assigned to them are the experiment's design.

### Formats

`manifest.yaml`
```yaml
testset: aegis_testset_v1
home_id: bench01
timezone: Asia/Karachi
now: "2026-11-20T10:30:00+05:00"      # the clock used for every query unless a query overrides it
sessions:
  - {id: s1_placements, source: captures/…, recorded_at: "2026-11-16T09:00:00+05:00", config: config/live.yaml}
exempt_from_purge: true               # also list these ids in privacy.exempt_datasets
```

`queries.yaml` — a list; `kind` is `spatial`, `temporal`, `unanswerable` or `room`:
```yaml
- id: q01
  kind: spatial
  text: "where are my keys"
  expect: {canonical: keys, anchor_any_of: ["Desk #1"], relation_any_of: [on_surface], room: Kitchen}
- id: q11
  kind: temporal
  text: "when did i put my keys down"
  expect: {status_any_of: [answered], event_type: placement, time: "2026-11-16T09:04:10+05:00", tolerance_minutes: 10}
- id: q14
  kind: temporal
  text: "did i go to the kitchen this morning"
  now: "2026-11-16T12:00:00+05:00"
  expect: {polarity: "yes"}
- id: q21
  kind: unanswerable
  text: "where is my passport"
  expect: {abstain: true}
```
The set holds at least 10 spatial, 10 temporal (at least 4 with relative time words, at least 2 answered from summaries after compaction), 5 unanswerable and 5 room-constrained queries.

### Scoring (`aegis.evaluation.score_answer(answer: dict, expect: dict) -> dict`)

Returns `{"correct": bool, "reasons": [str]}`. An expectation key that is absent is not checked.

| Key | Rule |
|---|---|
| `abstain: true` | `answer["abstained"]` and `anchor_label is None` and `room_label is None` (for `low_confidence` the candidate fields count as a fabricated location → incorrect for an unanswerable query) |
| `status_any_of` | `answer["status"]` in the list |
| `canonical` | the primary state's canonical equals it |
| `anchor_any_of` | `anchor_label` equals one, case-insensitive |
| `relation_any_of` | `relation` in the list |
| `room` | `room_label` equals it, case-insensitive |
| `polarity` | `facts["polarity"]` equals it |
| `event_type` | `facts["event_type"]` equals it |
| `time` + `tolerance_minutes` (default 10) | `abs(facts["reference_time"] − time) <= tolerance` |
| `rooms_include` | every listed room is in `facts["rooms"]` |
| `tier` | `answer["tier"]` equals it |

A spatial or temporal query is correct only when the answer is not an abstention **and** every checked key passes. Aggregates (`aegis.evaluation.summarise_benchmark`): accuracy per kind; evidence coverage = share of non-abstaining answers with at least one evidence item whose `description` is non-empty (and whose crop file exists when `crop_url` is set); abstention correctness = share of unanswerable queries that abstain; fabricated locations = count of unanswerable queries with any location field set; summarised-label rate = share of answers whose evidence is all `summary` that have `tier == "summarised"`.

### `scripts/run_benchmark.py`

```
uv run python scripts/run_benchmark.py --testset benchmark/aegis_testset_v1 \
    --store-root outputs/_bench --laptop "…" --phone "…" [--compare-compaction] [--out …]
```
- Loads the manifest and queries; opens the home store (the sessions must already be ingested; print the exact `run_pipeline.py` commands when a session is missing).
- Calls `answering.answer` directly (no HTTP) with each query's `now`, `PATIENT` voice and the settings from `--config-path`.
- Writes per-query rows (`id, kind, text, status, answer, correct, reasons, confidence, tier, evidence ids, latency_ms`) and the aggregates through `scripts/_evidence.py`.
- `--compare-compaction` (AC-08, SC3): copy the store directory; run all queries with `now = manifest.now + (hot_days + 1) days` on the copy **before** compaction; run `compact` + `rollup` on the copy at that time; run the queries again; report both accuracies per kind and the drop in percentage points, plus room-label survival (every room id named in a pre-compaction answer still resolves to the same label). Both runs use the same `now`, so freshness does not differ between them.
- Exit code 0 always (it measures; it does not gate). Targets are printed beside the results as "proposed target", never as pass/fail of the system.

### `scripts/abstention_curve.py` (decision #8)

Runs the spatial and unanswerable queries with `abstain_below` from 0.05 to 0.95 in steps of 0.05 and writes, per threshold: answered count, correct among answered (precision), abstained count, wrongly abstained (a correct answer suppressed), fabricated locations. Recommendation printed: the lowest threshold with zero fabricated locations and precision ≥ 0.80; if none exists, the threshold with the highest precision. The team then sets `query.abstain_below` in the config and records the choice and the curve file in the report.

### Tests (`tests/test_benchmark.py`)
- `test_score_spatial_correct_and_wrong_anchor`, `test_score_temporal_time_tolerance`, `test_score_polarity`, `test_unanswerable_needs_no_location`.
- `test_aggregates` on a hand-made list.
- `test_runner_on_synthetic_testset` — build a tiny test set in `tmp_path` from the WP21 `history_store` timeline and its ten temporal questions; run `run_benchmark.main([...])`; the output file has a header, per-query rows and aggregates.
- `test_compare_compaction_reports_a_drop_and_leaves_the_original_store_untouched`.
- `test_abstention_curve_is_monotone` (answered count never increases with the threshold).
- `test_template_files_parse` (the YAML templates load and every query passes a schema check).

### Done when
The tools run on the synthetic set. Todo §5.1 items 1–2 are ticked when the README names the owner and the first recordings exist; the result items stay open until WP34.

---

## WP34 — Measurements and recorded evidence

**Goal:** run every Milestone 3 and 4 acceptance check on real hardware and record the results. Nothing here is ticked from a unit test.

Rules: every run writes a file under `outputs/evaluation/` through `scripts/_evidence.py` (commit, config hash, model ids, hardware, operator); the working tree must be clean; a missed target is reported as missed.

| # | Check | Procedure | Record | Proposed target |
|---|---|---|---|---|
| P9 | AC-09, SC1 spatial accuracy | Ingest `S1`, `S3`; `run_benchmark.py` | `benchmark_<ts>.json` → spatial accuracy | ≥ 70% |
| P10 | AC-10, SC2 temporal accuracy | Ingest `S2`, `S3`; same run | temporal accuracy | ≥ 60% |
| P11 | AC-11, SC5 evidence coverage | same run | evidence coverage | 100% |
| P12 | AC-12, SC6 abstention | same run, unanswerable queries; then `abstention_curve.py`, choose the threshold, re-run | abstention correctness, fabricated count, curve file, chosen threshold | ≥ 4 of 5 abstain; 0 fabricated |
| P13 | AC-13 speech | (a) `evaluate_speech.py` on recordings of the ten questions by at least 3 speakers; (b) on the phone, speak the same ten questions, note the words the app shows and whether the answer matches the typed answer | word accuracy per speaker; equivalent answers out of 10; phone model, Android version | ≥ 80%; equivalent |
| P14 | AC-14 answer screens | Five different questions on the phone; screenshot each | five screenshots; checklist: answer ≤ 2 sentences, time shown, evidence shown | 5 of 5 |
| P15 | AC-15, SC8, NFR-U1 usability | Follow `docs/usability_protocol.md` | per-participant sheet | 5 of 5 within 60 s, unassisted |
| P16 | AC-16 | Five invalid sign-ins against the running TLS server (wrong password, unknown user, empty password, expired invite, made-up token); then read the access log as the primary user | request/response transcript + log screenshot | 5 denied, 5 logged |
| P17 | AC-17 | Caregiver signed in on one phone; primary stops sharing on another; caregiver pulls to refresh | times of revoke and of the refused request | refused on the next request |
| P18 | AC-18 | Five caregiver actions; primary opens the access log | screenshot | 5 of 5 listed |
| P19 | AC-19, SC4, NFR-P1 latency | (a) `scripts/measure_query_latency.py --n 100 --warmup 10` against the running server on the T480 with a real home store; (b) on the phone, 20 questions (10 typed, 10 spoken), read the values from Settings › Developer | p50, p95, max for (a) and (b); store size; hardware | p95 ≤ 5 s |
| P20 | AC-20 | `scripts/verify_encryption.py --probe <room label> --url https://… --fingerprint …`; then delete history in the app; then `aegis-memory size` and `sqlcipher` inspection of the tables | result file; post-delete row counts | all PASS; all history tables 0 |
| P21 | AC-24 | Typed-only query; voice-only query; change text size through all three; `flutter test test/contrast_test.dart` output | screenshots at 3 sizes; contrast table | both flows; 3 sizes; all pairs ≥ 4.5 |
| P22 | AC-25 | After a 10-minute live session (the P4 run of Part I), open the timeline filtered to that session; export `GET /timeline?session_id=` and compare with the store's event rows and with the annotator's log | diff (should be empty); screenshot | chronological and matching |
| P23 | AC-26 | Caregiver with the default grant: three in-scope requests, then `GET /video/<session>` and a history question | transcript with status codes | 3 succeed, 2 refused |
| P24 | AC-28 | Ask about an object last seen more than 6 hours ago (use the real clock, not `AEGIS_NOW`) | screenshot + response JSON | states when last seen; `status: stale` |
| P25 | AC-30 | 25 hours after a live session, run `scripts/verify_purge.py --remote` | result file listing remaining paths | none remain |
| P26 | AC-08, SC3 | `run_benchmark.py --compare-compaction` | accuracy before/after, drop, room-label survival | drop ≤ 15 points |
| P27 | AC-23 | In the P26 output, every answer built only from summaries | summarised-label rate | 100% |
| P28 | NFR-P3 with real recordings | `aegis-memory size` after each ingested benchmark day and after compaction | table of bytes and rows per day | growth recorded |
| P29 | AC-31 with auth | Rename a room as a caregiver with the `rooms` scope, restart the server, ingest another session | transcript | label survives; refused without the scope |

### `scripts/measure_query_latency.py`
Arguments: `--url`, `--username`/`--password-stdin` (or `--no-auth`), `--home-id`, `--queries` (a text file, one question per line; default: the benchmark's spatial and temporal texts), `--n 100`, `--warmup 10`, plus the common evidence arguments. It signs in once, sends `POST /ask` sequentially with `httpx`, measures wall time per request with `time.perf_counter`, and records p50, p95, max, the server-reported `latency_ms` percentiles, the count of non-200 responses, the number of instances and runs in the store. It refuses to report when fewer than 100 timed requests succeeded.

### `docs/usability_protocol.md` (AC-15, SC8)
Write the protocol before any session: purpose and the statement that this is not a clinical study; participants (5 adults, healthy volunteers, not team members, mixed ages and, where possible, both genders; consent wording); setting (phone model, text size medium, a home store prepared from the benchmark recordings, real clock); the task, read once and not explained further (`Use this app to find out where the keys are.`); what the facilitator may say (nothing until 60 s have passed); measures (time from the app's first screen to the participant reading the answer aloud; modality chosen; errors; whether help was needed; one free comment); the record sheet (participant code, age band, gender, smartphone use, time in seconds, assisted yes/no, notes); how results are reported (count within 60 s unassisted, median time, limitations).

### After the runs
For each row above, tick the matching todo item (or mark it `[~]` with the reason) and cite the result file. Update `context/implementation_log.md`.

---

## WP35 — Report and documentation

**Goal:** close todo §5.2 so that the report matches the system.

1. `docs/running_aegis.md`: sign-in set-up (`aegis-memory user add`, key generation, `aegis-memory encrypt`, `aegis-memory tls-cert`, the new `run_server.py` flags), the app's first-run steps (server address, trust the certificate, sign in), the developer mode, the purge cron line. Extend the confirmation checklist with one line per P-row of WP34.
2. `docs/artifact_contracts.md`: store schema v2 (the six tables), the encrypted file format (`AEG1`), the `query_log` and `audit_log` retention, the answer contract (statuses, evidence item, `facts`).
3. `docs/security.md` (started in WP27): key handling, backup, TLS and pinning, roles and scopes table, lockout, what is logged, known gaps.
4. `docs/evaluation_plan.md`: add the benchmark section (WP33), the abstention curve, the speech and usability protocols; keep every target labelled "proposed".
5. `docs/fyp1_mid_defense_dossier.md`: rewrite the stale claims (55 tests, `S = 5.0×`, Z-up frame) or mark the file as historical at the top and link to the current documents.
6. Report (`fyp_report/chapters`): update the test count and the test-suite tables from `uv run pytest --collect-only -q`; M1 status (live path connected); Chapter 4 status columns for FR4–FR8 and NFR-S; the use-case diagram (add UC-13), component diagram (answer engine, auth, home store, speech), class diagram (store tables), data-flow diagram (purge, compaction, encryption boundary), sequence diagrams (ask a question; caregiver sign-in and scoped query; revoke). Record decisions #1–#5, #8, #9, #11, #12 with their status from §II.0.3. Fill Iteration 3 and 4 scope from §II.0.4.
7. `README.md` and `AGENTS.md`: module list and commands.
8. Consolidated compute/storage/device account (panel item 3) from `benchmark_stats.json` and the P19/P28 files.
9. `context/todo.md`: update §0 status snapshot for FR5–FR8 and NFR-R/P/S/U; tick only with evidence.

No measured number is written into the report before its P-row result file exists.

---

## Appendix C — Traceability: every Milestone 3, 4 and §5 todo item to its plan

### Milestone 3

| Todo item | WP | Closing evidence |
|---|---|---|
| 3.2 ASR provider and placement (decision #2) | 23 | §II.0.3; `tests/test_speech.py` |
| 3.2 Microphone capture in the patient view | 31 | `test/voice_test.dart` |
| 3.2 Transcript + confidence, confirm/correct | 23, 31 | `test_low_confidence_needs_confirmation`, `voice_test` |
| 3.2 Speech/text equivalence, accuracy ≥ 80% | 23, 34 (P13) | `evaluate_speech` result file |
| 3.3 Intent routing | 18 | `test_routing` |
| 3.3 Relative-time parser | 17 | `test_windows` |
| 3.3 Hot and summarised tiers, labelled | 21 | `test_every_answer_from_compacted_history_is_labelled` |
| 3.3 "Capture may have been off" | 21 | `test_no_recording_says_camera_was_off` |
| 3.3 Ten temporal queries ≥ 60% | 21, 34 (P10) | `test_temporal_set_of_ten`; benchmark file |
| 3.4 Real relative time | 17, 19 | `test_describe_when`, `test_fresh_object_is_answered_with_time` |
| 3.4 Six-hour window; stale wording | 19 | `test_object_older_than_six_hours_is_stale` |
| 3.4 Stale-object test | 19, 34 (P24) | same; screenshot |
| 3.5 Computed confidence | 19 | `tests/test_confidence.py` |
| 3.5 Configurable threshold (decision #8) | 19, 33 | `test_threshold_is_configurable`; curve file |
| 3.5 Three abstention kinds | 19 | `test_three_abstention_kinds_are_distinct` |
| 3.5 Five unanswerable, ≥ 4 abstain | 19, 34 (P12) | `test_never_observed_abstains_without_location`; benchmark file |
| 3.6 Evidence reference on every answer | 20 | `test_evidence_coverage_is_total` |
| 3.6 Real crop on the per-dataset path; decision #9 | 20 | `test_dataset_crop_is_real_or_404`; supervisor confirmation still needed |
| 3.6 Text fallback when purged | 20 | `test_purged_crop_falls_back_to_text` |
| 3.6 Evidence-coverage test | 20, 34 (P11) | same; benchmark file |
| 3.7 Clarification flow | 22, 31 | `tests/test_clarification.py`, `answer_card_test` |
| 3.7 Query log with evidence | 22 | `test_home_query_is_logged_with_evidence` |
| 3.7 Optional tool-calling agent / VLM | 24 | built, or deferred with the stated reason |

### Milestone 4

| Todo item | WP | Closing evidence |
|---|---|---|
| 4.2 Mechanism and credential storage (decision #4) | 25 | `tests/test_auth.py` |
| 4.2 Caregiver login | 25, 26, 30 | `test_login_success…`, `login_test` |
| 4.2 Grant / restrict / revoke, enforced per request | 25, 26, 32 | `test_revocation_blocks_the_next_request`; P17 |
| 4.2 Patient identity boundary and consent record | 25, 26 | `test_cli_user_add_requires_consent`, `test_other_home_is_refused` |
| 4.2 Protect mutating endpoints; validate ids | 26 | `test_mutating_routes_are_primary_only`, `test_every_route_needs_a_token` |
| 4.2 Explicit CORS | 26 | `test_cors_has_no_wildcard` |
| 4.2 AC-16 and AC-17 tests | 25, 26 | named tests; P16, P17 |
| 4.3 TLS; AES-256 at rest | 27 | `tests/test_encryption.py`; P20 |
| 4.3 Caregiver scope excludes raw video and out-of-scope history | 26 | `test_caregiver_scope_matrix`; P23 |
| 4.3 Access audit log, 30 days, visible to the primary user | 25, 26, 32 | `test_five_caregiver_actions_appear_in_the_log`, `test_audit_purge_keeps_thirty_days`; P18 |
| 4.3 Raw-frame purge with verification | 28 | `tests/test_privacy.py`; P25 |
| 4.3 Full, immediate, irreversible deletion | 28, 32 | `test_delete_history_empties_everything_and_verifies`; P20 |
| 4.3 Privacy-limitation statement | 28 | `docs/privacy_limitations.md` |
| 4.4 Evidence display in both views | 31, 32 | `answer_card_test`, `objects_tab_test`; P14 |
| 4.4 Object-state verification with stale indicator | 29, 32 | `test_objects_lists_state_time_freshness_and_evidence`, `objects_tab_test` |
| 4.4 Daily activity summary view | 29, 32 | `test_daily_summary_*`, `summary_tab_test` |
| 4.4 Access-log view | 26, 32 | `sharing_test` |
| 4.4 Room list / rename screen (decision #12) | 32 | `rooms_tab_test`; P29 |
| 4.4 Timeline with session/date filter | 29, 32 | `test_timeline_filters_by_date_and_session`, `timeline_tab_test`; P22 |
| 4.4 Capture pause and delete-history controls | 28, 32 | `privacy_test` |
| 4.5 Three text sizes | 30 | `text_size_test`; P21 |
| 4.5 Measured contrast ≥ 4.5:1 | 30 | `contrast_test` table; P21 |
| 4.5 First-time-user task | 34 (P15) | usability sheets |
| 4.6 Latency p50/p95/max over ≥ 100 requests | 34 (P19) | latency file |
| 4.6 Ingestion backlog | Part I P4 | — |
| 4.6 Storage growth after retention | 34 (P28) | size table |
| 4.6 Hardware, config, versions with every measurement | 34 | `scripts/_evidence.py` header |

### §5

| Todo item | WP |
|---|---|
| 5.1 Dataset and annotation strategy (decision #1) | 33 |
| 5.1 Build `Aegis-TestSet-v1`, assign an owner | 33, 34 |
| 5.1 Spatial and temporal accuracy | 34 (P9, P10) |
| 5.1 Accuracy drop after compaction | 33, 34 (P26) |
| 5.1 Evidence coverage and abstention correctness | 34 (P11, P12) |
| 5.1 Iteration 1 exit criterion | 34 (P9 on `S1`) and Part I P6 |
| 5.1 Document dataset limitations | 33 (`README.md`) |
| 5.2 all items | 35 |

---

## Appendix D — Limitations Part II accepts

State these in the report.

1. **Activities are room stays and object changes, not recognised actions.** "Did I have breakfast?" is answered with "I can't tell" plus what was observed. A meal, a medication intake or a conversation is not detected.
2. **Temporal answers from summaries are coarse.** For objects of normal importance, compacted history keeps the last place and a move count per day, not move times. Only `importance: high` objects keep their move times.
3. **"Now" is the laptop's clock.** A wrong system clock makes freshness and relative time wrong. Sessions without capture time (`time_source: ingest`) are placed at ingest time and say so in the store.
4. **Confidence is a product of heuristics**, not a calibrated probability. The threshold is chosen from a small benchmark of one home.
5. **The parser is English and rule-based.** Unusual phrasings fall back to a "where" question or to "I can't tell". Urdu is not supported.
6. **Speech depends on the phone's recogniser.** Its accuracy is measured on a few speakers; accented or impaired speech may do worse, and typed input is the guaranteed path.
7. **One home, one primary user.** Accounts live in that home's store. There is no password reset by email; the operator resets a password with the CLI.
8. **The lockout can be abused** to keep a caregiver out for 15 minutes by guessing wrong passwords for their username.
9. **The encryption key is on the same laptop.** It protects a copied store, not a compromised running system. Raw frames are plaintext during their 24 hours.
10. **The certificate is self-signed.** Safety depends on the user comparing the fingerprint once. On the web build the browser's warning must be accepted by hand.
11. **Session tokens live for 60 minutes and are kept in memory.** Closing the app signs the user out.
12. **The 24-hour purge needs the laptop to be on** (server maintenance thread or cron). The Modal volume is purged only by the CLI or the pipeline, not by the server.
13. **Deletion covers Aegis's own storage.** Copies made by the operating system, cloud provider snapshots or manual backups are outside it.
14. **Evidence crops can contain background**, including parts of other people (Appendix B.7). Decision #9 needs the supervisor's confirmation.
15. **The Modal ASGI wrapper (`fastapi_gateway`) is not a deployment target for home data.** The home store and its key are on the laptop; the wrapper has no users and refuses every memory request once auth is on.
16. **Usability evidence is five healthy volunteers.** It supports no claim about people with cognitive impairment.
