"""F5.1 Layered architecture (ch5-layered-architecture.png).

Five layers, top to bottom; arrows only between adjacent layers.
Run from the repository root:
    uv run --no-project --with matplotlib python fyp1FinalReport/ThesisFigs/src/fig_layers.py

Verified against: src/aegis/ingestion (OpenCVMjpegSource, ingest_live, KeyframeSelector,
FrameBuffer, LiveSessionWriter, promote_live_segments, ingest_video, preprocess_video,
upload_dataset_to_modal_volume; live_pipeline.py defaults sample_fps 2.0,
buffer_capacity 30, reconnect 3 s / timeout 30 s; core/config.py segment_frames 120,
max_keyframes 120); src/aegis/remote/modal_app.py (L4, AEGIS_GPU=cpu); workers.py
(estimate_gravity, lift_detection_to_3d); memory/ (scene_graph, ingest, matching,
compaction, home_registry, personal); remote/api.py (26 route handlers, 6 of them
/simulate; CORS *; resolve_repository); core/config.py RankingConfig; nlq/dictionary.py
(525 items); remote/serve.py (aegis-memory-api).
"""

from boxdraw import Canvas, top, bottom

c = Canvas(6.0, 7.05, font=7.6)
X0, X1 = 0.45, 5.87          # box area
G = 0.08                      # gap between boxes


def row(y, h, specs):
    """specs: list of (relative width, text, style). Returns the boxes."""
    total = sum(s[0] for s in specs)
    avail = X1 - X0 - G * (len(specs) - 1)
    x, out = X0, []
    for wrel, text, style in specs:
        w = avail * wrel / total
        out.append(c.box(x, y, w, h, text, style))
        x += w + G
    return out


BH = 0.92   # box height
layers = [  # (label, style, y of band)
    ("1 Capture &\nIngestion", "A", 5.82),
    ("2 3D + Percep-\ntion (Modal)", "A", 4.52),
    ("3 Memory", "B", 3.22),
    ("4 Query Service", "C", 1.92),
    ("5 Presentation", "D", 0.62),
]
for label, style, y in layers:
    c.band(0.05, y - 0.08, 5.9, BH + 0.16, label, style, label_w=0.33)

L1 = row(5.82, BH, [
    (1.0, "Phone camera\nIP Webcam app\nHTTP MJPEG\n/video", "A"),
    (1.25, "ingest_live\n2 fps sampling,\nKeyframeSelector,\nFrameBuffer(30),\ngap/pause records", "A"),
    (1.2, "LiveSession-\nWriter\nframe_*.jpg,\nindex.jsonl,\nsession.json", "A"),
    (1.15, "promote_live_\nsegments\n120-frame\nsegments →\ndata/<id>/", "A"),
    (1.0, "Batch video\ningest_video,\npreprocess_\nvideo", "A"),
])
L2 = row(4.52, BH, [
    (1.0, "preprocess_\nvideo_remote\nCPU: normalise\nframes", "A"),
    (1.3, "Reconstructor\nL4: VGGT-Ω,\n≤ 120 keyframes →\nposes, pointmaps", "A"),
    (1.1, "Gravity\nestimate_gravity:\nRANSAC floor →\ngravity.json", "A"),
    (1.32, "Perception\nL4: SAM3 / YOLOE\n+ SAM 2 + DINOv3\n→ lift_detection_\nto_3d (OBB)", "A"),
    (1.03, "CPU fallback\nAEGIS_GPU=cpu\nruns the same\nstages", "W"),
])
L3 = row(3.22, BH, [
    (1.35, "Session graph\nrelations, state\nruns, events,\nrooms → r4d_\nscene_graph.json", "B"),
    (1.35, "Home store\ningest_session →\nmemory.db;\nmatch_rooms /\nanchors / instances", "B"),
    (1.05, "Retention\ncompact (3 days\n→ summaries),\nrollup", "B"),
    (1.05, "Registry,\npersonal items\nhome_map.json,\nenroll / alias", "B"),
    (0.85, "Encryption\nat rest\n(planned,\nP1.8)", "P"),
])
L4 = row(1.92, BH, [
    (1.25, "FastAPI api.py\n/api/v1: 26 routes\n(6 /simulate);\nresolve_repository", "C"),
    (1.38, "/query\nrank_candidates:\nrecency, interaction,\ndisplacement,\npersonal, cue", "C"),
    (1.2, "/ask NLQ\nAnswerEngine +\nDictionaryIndex\n(525 items),\nabstention", "C"),
    (0.9, "serve.py\nModal CPU app\naegis-memory-\napi", "C"),
    (0.8, "CORS *\nno auth on\nmutating\nroutes", "R"),
    (0.88, "Planned\nLLM planner,\nauth, audit\n(P1.7, P1.9)", "P"),
])
L5 = row(0.62, BH, [
    (1.3, "Patient App\nFlutter: tiles, voice\n(on-device STT),\nanswer drawer, call", "D"),
    (1.3, "Caregiver App\nsearch; Home, Track,\nInterior, Status tabs;\nhistory, enroll, rename", "D"),
    (1.0, "aegis-ask CLI\nterminal; http or\nlocal transport", "D"),
    (1.0, "Rerun\noffline 3D memory\nrecording\n(run_rerun)", "D"),
])

# arrows between adjacent layers, labelled with protocol or artifact
c.arrow(bottom(L1[3]), top(L2[1]), "upload to volume aegis-poc-data",
        label_at=(bottom(L1[3])[0] - 1.55, 5.62))
c.arrow(bottom(L2[3]), top(L3[0]), "3D boxes + gravity + poses",
        label_at=(top(L3[0])[0] + 0.15, 4.32))
c.arrow(bottom(L3[1]), top(L4[0]), "graph / store rows via MemoryRepository",
        label_at=(top(L4[0])[0] + 0.5, 3.02))
c.arrow(bottom(L4[0]), top(L5[0]), "HTTPS JSON", label_at=(top(L5[0])[0] + 0.1, 1.72))
c.arrow(bottom(L4[0]), top(L5[1]))

c.note(5.95, 0.32, "Colour = layer.  Dashed: planned.  Red: security gap.", ha="right")
c.save("ch5-layered-architecture")
