# Aegis — Implementation Plan for Milestone 1, Milestone 2 and §6 Improvements

**Written:** 2026-11-14 against `develop` @ `8183015` (129 tests pass, Ruff clean).
**Covers:** every open item in `context/todo.md` Milestone 1 (§1.4), Milestone 2 (§2.3–§2.8) and §6 (A1–A11, M1–M8, C1–C13).
**Does not cover:** Milestone 3 and 4 features, except where a §6 item touches them (A9, C9, C13, FR1.3 control).
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
