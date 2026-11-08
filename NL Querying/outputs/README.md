# NLQ memory outputs

Per-dataset artifacts staged for answering questions live here:

```text
outputs/<dataset_id>/
├── objects/r4d_scene_graph.json   ← the memory the NLQ engine reads
├── objects/events.json
├── objects/detected_objects_3d.json
├── geometry/...
├── viewer/demo.rrd
└── benchmark_stats.json
```

They are produced by running the Modal pipeline through the wrapper:

```bash
uv run python "NL Querying/build_memory.py" \
    --video "NL Querying/sample_input_video.mp4" \
    --dataset-id nlq_sample
```

`build_memory.py` copies `outputs/<dataset_id>/` from the repo root into this
folder, and `comm/transports.py` searches this folder **first**. The generated
contents are ignored by git; only this README is tracked.
