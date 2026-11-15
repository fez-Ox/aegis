# Evaluation Quick Start

The single source of truth for the evaluation protocol, metrics, Option C
decision, memory-control study, and the long-term persistence plan is:

**[`docs/evaluation_suite.md`](../docs/evaluation_suite.md)**

This directory contains only the runnable harness, templates, configs, and
generated reports. Start with the main document, then use these commands.

```bash
# Option A — held-out video
uv run python -m aegis.evaluation.run \
  --config evaluation/configs/demo05.yaml

# Option D — controlled room
uv run python -m aegis.evaluation.controlled_room \
  --measurements evaluation/annotations/controlled_room/measurements.csv \
  --scene-graph outputs/controlled_room/objects/r4d_scene_graph.json \
  --output-dir evaluation/reports/controlled_room

# Memory control
uv run python -m aegis.evaluation.memory_audit \
  --graphs outputs/demo04/objects/r4d_scene_graph.json \
           outputs/demo03/objects/r4d_scene_graph.json \
  --snapshot-intervals 0,1,10,30 \
  --output-dir evaluation/reports/memory_control

# Option C — Ego4D readiness
uv run python -m aegis.evaluation.option_c \
  --facts evaluation/configs/option_c_facts.yaml \
  --output-dir evaluation/reports/option_c
```

## Directory contents

| Path | Contents |
|---|---|
| `configs/demo05.yaml` | Frozen held-out protocol and targets. |
| `configs/option_c_facts.yaml` | Ego4D readiness checklist. |
| `templates/` | Annotation templates and annotation guide. |
| `annotations/` | Human ground truth (not created yet). |
| `reports/` | Generated scorecards and readiness reports. |

Tests: `uv run pytest tests/test_evaluation_*.py`.
