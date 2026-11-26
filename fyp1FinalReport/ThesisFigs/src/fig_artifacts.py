"""F5.8 Live-session artifacts (ch5-live-session-artifacts.png).

Run from the repository root:
    uv run --no-project --with matplotlib python fyp1FinalReport/ThesisFigs/src/fig_artifacts.py

Verified against: src/aegis/ingestion/live_storage.py (frame_{sequence:08d}_{stamp}.jpg,
index.jsonl, session.json, session_state.json), contracts.py (schema version 2,
FRAME_TIMESTAMP_SOURCES, GAP_REASONS, SESSION_STATUSES, frame and gap fields),
segment_runner.py (STATE_FILENAME = pipeline_state.json), live_handoff.py
(frames/frame_{id:06d}.jpg, metadata.json with preprocess_source "live_session",
source_metadata.json, live_session.json, live_timestamps.json; segments split after
segment_frames or at a long gap), core/config.py (segment_frames 120),
download.py (upload_dataset_to_modal_volume).
"""

from boxdraw import Canvas, INK, MUTED, STYLE

c = Canvas(6.0, 4.35, font=7.2)
MONO = "DejaVu Sans Mono"


def folder(x, y, w, h, title, style):
    fill, edge = STYLE[style]
    import matplotlib.patches as mp
    c.ax.add_patch(mp.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.04",
                                     facecolor="#FFFFFF", edgecolor=edge, lw=1.2, zorder=1))
    c.ax.add_patch(mp.FancyBboxPatch((x, y + h - 0.3), w, 0.3, boxstyle="round,pad=0,rounding_size=0.04",
                                     facecolor=fill, edgecolor=edge, lw=1.2, zorder=2))
    c.ax.text(x + 0.1, y + h - 0.15, title, fontsize=7.6, fontweight="bold", family=MONO,
              va="center", zorder=3)


def entry(x, y, name, desc, fs=6.6):
    c.ax.text(x, y, name, fontsize=fs + 0.3, family=MONO, fontweight="bold", va="top", color=INK, zorder=4)
    if desc:
        c.ax.text(x + 0.12, y - 0.15, desc, fontsize=fs, va="top", color=INK, linespacing=1.18, zorder=4)


# ----------------------------------------------------------- capture folder
H = 4.35
folder(0.05, 0.08, 3.55, H - 0.13, "captures/<session_id>/", "A")
x = 0.18
entry(x, H - 0.42, "frame_<sequence:08d>_<stamp>.jpg …", "sampled JPEG frames")
entry(x, H - 0.8, "index.jsonl", "one JSON record per line, record_schema_version 2:")
entry(x + 0.12, H - 1.17, "frame record", "record_type, session_id, sequence, frame_path,\n"
      "source_id, capture_timestamp, timestamp_source\n"
      "{source_capture | laptop_receive_decode |\n ingestion | unknown}, received_at,\n"
      "ingestion_timestamp, width, height, encoding: jpeg,\n"
      "sample_rate_target_hz, source_protocol,\n"
      "keyframe {accepted, reason, sharpness,\n brightness, visual_change}", fs=6.3)
entry(x + 0.12, H - 2.43, "gap record", "gap_start, gap_end, duration_seconds,\n"
      "reason {disconnect | pause | storage_stall |\n source_stall | dropped_frames},\n"
      "dropped_estimate, sequence_before,\nsequence_after, recovered", fs=6.3)
entry(x, H - 3.32, "session.json", "manifest: status {running | completed | time_limit |\n"
      "stopped | disconnected | storage_error}, pauses[], counts")
entry(x, H - 3.82, "session_state.json", "crash checkpoint")
c.ax.text(1.95, H - 3.82, "pipeline_state.json", fontsize=6.9, family=MONO, fontweight="bold",
          va="top", color=INK, zorder=4)
c.ax.text(2.07, H - 3.97, "segment runner progress", fontsize=6.6, va="top", color=INK, zorder=4)

# ----------------------------------------------------------- promoted dataset
folder(4.0, 1.55, 1.95, H - 1.6, "data/<id>_seg0001/", "A")
x = 4.1
entry(x, H - 0.42, "frames/", "frame_<id:06d>.jpg", fs=6.4)
entry(x, H - 0.85, "metadata.json", "schema v2,\npreprocess_source:\nlive_session", fs=6.4)
entry(x, H - 1.5, "live_session.json", None, fs=6.4)
entry(x, H - 1.72, "live_timestamps.json", None, fs=6.4)
entry(x, H - 1.94, "source_metadata.json", None, fs=6.4)
c.note(4.1, 1.85, "← promote_live_segments:\n≤ 120 frames per segment,\nsplit at long gaps", fs=6.2,
       color=INK)

# ----------------------------------------------------------- Modal volume
folder(4.0, 0.08, 1.95, 0.95, "/data/<dataset_id>/", "N")
c.note(4.97, 0.4, "Modal volume\naegis-poc-data", ha="center", fs=6.8, color=INK)

c.arrow((3.6, 1.85), (4.0, 1.85))
c.arrow((4.97, 1.55), (4.97, 1.03))
c.note(5.04, 1.29, "upload_dataset_to_\nmodal_volume", fs=6.2, color=INK)
c.save("ch5-live-session-artifacts")
