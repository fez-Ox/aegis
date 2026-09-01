# Aegis

A spatio-temporal memory system for assistive care.

The current implementation is a Modal-first geometry proof of concept. It is
kept in a dedicated [`poc/`](poc/) workspace so future production components
can grow independently.

## Repository layout

```text
poc/                    # runnable proposal-defense demonstration
  config/               # demo runtime configuration
  data/                 # local input videos (ignored)
  docs/                 # PoC implementation notes
  outputs/              # downloaded/generated artifacts (ignored)
  run_pipeline.py       # Modal pipeline entrypoint
  README.md             # PoC setup and usage
src/aegis/poc/          # PoC Python implementation
  core/                 # configuration, paths, and data contracts
  geometry/             # depth lifting and pose transforms
  ingestion/            # video normalization
  remote/               # Modal workers and model adapters
  visualization/        # package exports for visualization code
examples/               # standalone examples
  modal/                # Modal SDK starter example
poc/tests/              # PoC automated tests
```

## Run the PoC

See [`poc/README.md`](poc/README.md) for Modal setup, input upload, pipeline
commands, calibration options, and artifact download instructions.

## Development

```bash
uv sync --dev
uv run pytest
```
