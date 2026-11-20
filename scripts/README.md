# `scripts` — measurement and maintenance

Every measurement script writes a result through `scripts/_evidence.py` with
commit, dirty flag, config hash, model IDs and hardware so a number can be
traced. A result from a dirty tree is flagged as invalid evidence.

| Script | Measures |
|---|---|
| `run_e2e.py` | Runs the whole pipeline (capture → Modal → deploy → ask), blocking at human-only steps. `--dry-run` prints the commands. Not a measurement script. |
| `summarise_live_session.py` | One-hour soak, disconnect gaps, frame counts/backlog. |
| `evaluate_keyframes.py` | Scripted scene changes vs kept keyframes. |
| `evaluate_placements.py` | Object anchor/relation against ground truth. |
| `evaluate_rooms.py` | Room segmentation, transitions, region precision/recall. |
| `evaluate_activity_order.py` | Scripted activity order and timing. |
| `evaluate_hand_contact.py` | Pickup/placement events vs labelled times. |
| `compare_masks.py` | YOLOE direct masks vs SAM 2 refinement. |
| `measure_vggt_window.py` | Largest reconstruction window that fits the GPU. |
| `measure_store_growth.py` | Synthetic multi-day store growth (labelled synthetic). |
| `patch_demo06_rrd.py` | Demo06 Rerun artifact fix-up utility. |

These are offline/measurement tools, not part of the runtime pipeline. Results
are recorded in `TODO.md` (P2) once actually run.
