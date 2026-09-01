# Aegis

A Modal-first spatio-temporal memory system for assistive care.

## Current PoC slice

The implemented pipeline runs all video processing, 3D reconstruction, and object perception remotely on Modal:

```text
video in Modal Volume
  -> remote frame sampling
  -> remote DUSt3R multi-view 3D reconstruction (L40S GPU)
  -> remote YOLO-World 2D detection & 3D bounding box lifting (L4 GPU)
  -> remote Rerun .rrd artifact with 3D boxes & motion trails
```

The local machine only validates configuration and submits Modal jobs. No local
GPU fallback is used.

## Setup

Python 3.12 is pinned by `.python-version` and `pyproject.toml`.

```bash
uv sync --dev
# Optional local viewer binary for opening the downloaded .rrd file:
uv sync --dev --group viewer
modal volume create aegis-poc-data
modal volume create aegis-model-cache
```

Modal authentication is required before running jobs:

```bash
modal token new
```

## Prepare a demo sequence

Place an indoor egocentric sequence in a local directory and upload the video:

```bash
mkdir -p poc/data/demo01
cp /path/to/video.mp4 poc/data/demo01/video.mp4
modal volume put aegis-poc-data poc/data/demo01/video.mp4 /demo01/video.mp4
```

## Run the remote pipeline

```bash
uv run modal run poc/run_pipeline.py \
  --config-path poc/config/demo.yaml \
  --dataset-id demo01 \
  --stage all
```

Individual stages are available for debugging:

```bash
uv run modal run poc/run_pipeline.py --config-path poc/config/demo.yaml --dataset-id demo01 --stage preprocess
uv run modal run poc/run_pipeline.py --config-path poc/config/demo.yaml --dataset-id demo01 --stage reconstruct
uv run modal run poc/run_pipeline.py --config-path poc/config/demo.yaml --dataset-id demo01 --stage detect
uv run modal run poc/run_pipeline.py --config-path poc/config/demo.yaml --dataset-id demo01 --stage rerun
```

Artifacts are written to the data Volume:

```text
/demo01/
  frames/
  metadata.json
  outputs/
    geometry/
      poses.json
      pointcloud.npz
      pointcloud.ply
      pointmaps.npz
    objects/
      detected_objects_3d.json
    viewer/
      demo.rrd
      manifest.json
```

Download and open the Rerun recording after the remote job completes:

```bash
mkdir -p poc/outputs/demo01/viewer
modal volume get aegis-poc-data /demo01/outputs/viewer/demo.rrd poc/outputs/demo01/viewer/demo.rrd
rerun poc/outputs/demo01/viewer/demo.rrd
```


The first DroidCalib and DROID-SLAM runs download their checkpoints into the
persistent `aegis-model-cache` Volume. Depth Anything V2 weights are cached in
the same Volume. CUDA extensions for both GPU geometry images are built into
their Modal images.

## Tests

```bash
uv run pytest
```
