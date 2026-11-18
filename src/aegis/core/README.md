# `aegis.core` — configuration, contracts, vocabulary

Shared primitives every other layer imports. No I/O beyond reading config/YAML.

| Module | Role |
|---|---|
| `config.py` | `RuntimeConfig` and frozen section dataclasses: video, VGGT, perception, rooms, gravity, memory build, evidence, retention, home/store settings. `load_config()` embeds `config/vocabulary.yaml` into the config so Modal workers receive the ontology without shipping data files. |
| `vocabulary.py` | `Vocabulary`/`VocabEntry` load and validate `config/vocabulary.yaml`; `entry/canonical/role/display/room_type`, `detector_prompts()`, `resolve_query()` (word-boundary, longest-first), `default_vocabulary()`. |
| `models.py` | Frozen data contracts: `CameraIntrinsics`, `Frame`, `Pose` (`T_world_camera`), `Detection2D` (bbox, mask, track id, hand cue, appearance), `BoundingBox3D` (center, size, yaw/quaternion, `up_min/up_max/support_up`, in-hand state). |
| `paths.py` | `DatasetPaths`/`dataset_paths()` resolve canonical local and Modal-volume paths; `validate_dataset_id()` rejects path separators. |
| `timeutil.py` | Fixed UTC ISO format (`YYYY-MM-DDTHH:MM:SS.ffffff+00:00`), `to_utc_iso`, `parse_iso`, `shift_iso`, `utc_now`. SQLite time ordering relies on this format. |

**Invariant:** `config/vocabulary.yaml` is the single label ontology. Do not
reintroduce hard-coded class lists in other layers.

Tests: `tests/test_config.py`, `tests/test_vocabulary.py`.
