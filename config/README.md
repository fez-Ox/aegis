# `config` — runtime configuration

| File | Role |
|---|---|
| `vocabulary.yaml` | **Single label ontology.** Version 1; entries have `id`, `display`, detector `prompts`, query `synonyms`, `role` (`object`/`anchor`/`landmark`/`hand`), plural/importance, and anchor affordances (`container`, `support_surface`, `open_underneath`, `room_type`, `max_extent`). Every other label list is generated from it. |
| `demo.yaml` | Generic runtime config. Prompts derive from the vocabulary; sets video FPS, VGGT stride/dtype/size, detector/SAM 2 settings, rooms, gravity, live capture, evidence and retention defaults. |
| `live.yaml` | Live capture variant: `vggt.keyframe_stride: 1`, `max_keyframes` cap, segment settings — live frames are already keyframe-selected at ≤2 FPS. |
| `demo01.yaml`, `demo03.yaml`, `demo04.yaml`, `demo06.yaml` | Task-scoped prompt lists and thresholds for those specific recordings. Use these only for reproducing those demos. |

`RuntimeConfig.vocab()` resolves the embedded vocabulary mapping when running
on Modal (data files are not shipped in the image).
