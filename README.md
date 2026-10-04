# Aegis

[![Aegis CI](https://github.com/fez-Ox/aegis/actions/workflows/ci.yml/badge.svg)](https://github.com/fez-Ox/aegis/actions/workflows/ci.yml)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A spatio-temporal memory system for assistive care.

Stores and retrieves memories that are grounded in both *when* (temporal) and *where* (spatial) events occurred, supporting assistive-care applications (e.g., context-aware reminders, activity recall for users and caregivers).

## Repository Layout

```text
config/               # Runtime pipeline configuration (demo.yaml)
data/                 # Local input videos and frames (ignored)
docs/                 # Architecture, design notes, and implementation plans
outputs/              # Downloaded/generated artifacts and Rerun recordings (.rrd)
run_pipeline.py       # Modal pipeline entrypoint
src/aegis/            # Core aegis Python package
  core/               # Configuration, paths, and data contracts
  geometry/           # VGGT-Ω 3D reconstruction, point lifting, and OBB fitting
  ingestion/          # Video normalization and frame extraction
  memory/             # R4DSG Relative 4D Scene Graph memory engine
  perception/         # YOLO-World + SAM 2 instance detection & segmentation
  remote/             # Modal worker functions and remote container images
  visualization/      # Rerun visualization utilities
tests/                # Automated test suite
```

## Quickstart

### Development

```bash
uv sync --dev
uv run pytest
uvx ruff check src tests run_pipeline.py
```

### Running the Pipeline on Modal

Execute the end-to-end pipeline remotely on Modal:

```bash
# Full pipeline (ingest, reconstruct with VGGT-Ω, detect with YOLO-World + SAM 2, lift & build R4DSG)
uv run modal run run_pipeline.py --dataset-id demo01 --stage all

# Visualize results in Rerun
rerun outputs/demo.rrd
```
