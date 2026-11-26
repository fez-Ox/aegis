"""F5.11 DFD level 0 and F5.12 DFD level 1 (Gane–Sarson).

Run from the repository root:
    uv run --no-project --with matplotlib python fyp1FinalReport/ThesisFigs/src/fig_dfd.py

Gane–Sarson shapes: process = rounded box with a number strip; data store = open-ended
box with an ID cell; external entity = square with a shadow.
Verified against: ingestion (live capture writes captures/<session>/ frames and
index.jsonl; promote_live_segments + upload_dataset_to_modal_volume), remote/workers.py
(run_preprocess, run_vggt, run_detect_and_lift on the volume; evidence crops),
memory/ingest.py + compaction.py (memory.db rows, summaries), home_registry.py
(home_map.json), personal.py (meta.personal_items), remote/api.py (/query, /ask,
/rooms/rename, /enroll, /capture/pause|resume), apps (SharedPreferences: profile,
server URL; caregiver search history via HistoryService).
"""

import matplotlib.patches as mp

from boxdraw import Canvas, STYLE, INK, LINE, MUTED

PROC_FILL, PROC_EDGE = "#FCE8D0", "#D9822B"
STORE_FILL, STORE_EDGE = "#DFF0E3", "#2E8B57"
ENT_FILL, ENT_EDGE = "#F1F3F5", "#6B7785"


def process(c, cx, cy, w, h, num, name, fs=6.8):
    x, y = cx - w / 2, cy - h / 2
    c.ax.add_patch(mp.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.08",
                                     facecolor=PROC_FILL, edgecolor=PROC_EDGE, lw=1.2, zorder=3))
    c.ax.plot([x, x + w], [y + h - 0.2, y + h - 0.2], color=PROC_EDGE, lw=1.0, zorder=4)
    c.ax.text(cx, y + h - 0.1, num, ha="center", va="center", fontsize=fs, fontweight="bold", zorder=5)
    c.text_in(x, y, w, h - 0.2, name, bold_first=False, fs=fs, z=5)
    return (x, y, w, h)


def store(c, cx, cy, w, sid, name, fs=6.6, h=0.36):
    x, y = cx - w / 2, cy - h / 2
    c.ax.add_patch(mp.Rectangle((x, y), w, h, facecolor=STORE_FILL, edgecolor="none", zorder=3))
    c.ax.plot([x + w, x, x, x + w], [y + h, y + h, y, y], color=STORE_EDGE, lw=1.2, zorder=4)
    c.ax.plot([x + 0.32, x + 0.32], [y, y + h], color=STORE_EDGE, lw=1.0, zorder=4)
    c.ax.text(x + 0.16, cy, sid, ha="center", va="center", fontsize=fs, fontweight="bold", zorder=5)
    c.ax.text(x + 0.38, cy, name, ha="left", va="center", fontsize=fs, zorder=5, linespacing=1.1)
    return (x, y, w, h)


def entity(c, cx, cy, w, h, name, fs=7.0):
    x, y = cx - w / 2, cy - h / 2
    c.ax.add_patch(mp.Rectangle((x + 0.05, y - 0.05), w, h, facecolor="#C9CED6", edgecolor="none", zorder=2))
    c.ax.add_patch(mp.Rectangle((x, y), w, h, facecolor=ENT_FILL, edgecolor=ENT_EDGE, lw=1.2, zorder=3))
    c.text_in(x, y, w, h, name, bold_first=False, fs=fs, z=5)
    return (x, y, w, h)


def flow(c, p, q, label=None, at=None, rad=0.0, fs=6.2, ha="center"):
    c.ax.annotate("", xy=q, xytext=p, zorder=6,
                  arrowprops=dict(arrowstyle="-|>", color=LINE, lw=1.0, shrinkA=0, shrinkB=0,
                                  connectionstyle=f"arc3,rad={rad}"))
    if label:
        lx, ly = at or ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
        c.ax.text(lx, ly, label, ha=ha, va="center", fontsize=fs, color=INK, zorder=7, linespacing=1.12,
                  bbox=dict(facecolor="white", edgecolor="none", pad=0.4, alpha=0.95))


# ======================================================================= level 0
c = Canvas(6.0, 4.3, font=7.0)
P = process(c, 3.0, 2.2, 1.5, 1.0, "0", "Aegis", fs=8.4)
cam = entity(c, 0.9, 3.7, 1.35, 0.55, "Phone camera")
usr = entity(c, 0.9, 2.2, 1.35, 0.55, "Primary user")
cg = entity(c, 5.1, 2.2, 1.35, 0.55, "Caregiver")
mod = entity(c, 2.0, 0.45, 1.6, 0.55, "Modal compute\nplatform")
hub = entity(c, 4.6, 0.45, 1.35, 0.55, "Model hub")

flow(c, (1.58, 3.7), (2.6, 2.7), "video frames", at=(2.05, 3.45))
flow(c, (1.58, 2.33), (2.25, 2.33), "question", at=(1.92, 2.5))
flow(c, (2.25, 2.07), (1.58, 2.07), "answer + evidence\n/ not sure", at=(1.92, 1.82))
flow(c, (4.42, 2.33), (3.75, 2.33), "question, room name,\nenrolled item,\npause / resume",
     at=(4.08, 2.85))
flow(c, (3.75, 2.07), (4.42, 2.07), "answers, timeline,\nrooms, status", at=(4.08, 1.68))
flow(c, (2.7, 1.7), (2.2, 0.73), "frames, config", at=(2.08, 1.25), ha="right")
flow(c, (2.5, 0.73), (3.0, 1.7), "3D boxes, poses,\nscene graph", at=(3.15, 1.15), ha="left")
flow(c, (3.92, 0.45), (2.8, 0.45), "weights", at=(3.36, 0.6))
c.note(5.95, 4.15, "No data stores at level 0.", ha="right", fs=6.4)
c.save("ch5-dfd-level0")

# ======================================================================= level 1
c = Canvas(6.0, 7.1, font=6.8)
PW, PH = 1.2, 0.74
# row 1 (capture)                        y = 6.55
cam = entity(c, 0.55, 6.55, 0.95, 0.5, "Phone\ncamera")
p1 = process(c, 1.85, 6.55, PW, PH, "1.0", "Capture &\nsample")
d1 = store(c, 3.35, 6.55, 1.45, "D1", "Live capture\ncaptures/<session>/")
p2 = process(c, 5.0, 6.55, PW, PH, "2.0", "Promote &\nupload")
# row 2 (Modal)                          y = 5.15
p4 = process(c, 1.85, 5.15, PW, PH, "4.0", "Build session\nmemory")
d2 = store(c, 3.35, 5.15, 1.45, "D2", "Modal volume\n/data/<dataset_id>/")
p3 = process(c, 5.0, 5.15, PW, PH, "3.0", "Reconstruct &\nperceive\n(on Modal)")
hub = entity(c, 5.0, 4.15, 1.0, 0.42, "Model hub")
# row 3 (home store)                     y = 3.6
d5 = store(c, 0.85, 3.95, 1.3, "D5", "Evidence\ncrops")
p5 = process(c, 3.35, 3.6, PW, PH, "5.0", "Ingest into\nhome & compact")
d3 = store(c, 1.62, 3.15, 1.5, "D3", "Home store\nmemory.db")
d4 = store(c, 5.0, 3.15, 1.4, "D4", "home_map.json")
# row 4 (answer, manage)                 y = 1.75
usr = entity(c, 0.55, 1.75, 0.95, 0.5, "Primary\nuser")
p6 = process(c, 2.1, 1.75, PW, PH, "6.0", "Answer\nquery")
cg = entity(c, 3.6, 1.75, 0.95, 0.5, "Caregiver")
p7 = process(c, 5.05, 1.75, PW, PH, "7.0", "Manage rooms,\nitems, capture")
d6 = store(c, 2.1, 0.45, 1.9, "D6", "App local storage\n(SharedPreferences)")


def lbl(x, y, t, ha="center"):
    c.ax.text(x, y, t, ha=ha, va="center", fontsize=6.0, color=INK, zorder=7, linespacing=1.1,
              bbox=dict(facecolor="white", edgecolor="none", pad=0.3, alpha=0.95))


# row 1
flow(c, (1.03, 6.55), (1.25, 6.55)); lbl(1.14, 6.9, "camera\nframes")
flow(c, (2.45, 6.55), (2.63, 6.55)); lbl(2.54, 6.12, "frames +\nindex.jsonl")
flow(c, (4.08, 6.55), (4.4, 6.55)); lbl(4.24, 6.82, "session")
flow(c, (5.0, 6.18), (4.0, 5.33)); lbl(4.62, 5.88, "segment dataset")
# row 2
flow(c, (4.4, 5.25), (4.08, 5.25)); lbl(4.24, 5.55, "poses, gravity,\n3D boxes")
flow(c, (4.08, 5.05), (4.4, 5.05)); lbl(4.24, 4.78, "frames")
flow(c, (5.0, 4.36), (5.0, 4.78)); lbl(5.32, 4.57, "weights", ha="left")
flow(c, (2.63, 5.25), (2.45, 5.25)); lbl(2.54, 5.6, "boxes, poses,\ngravity")
flow(c, (2.45, 5.05), (2.63, 5.05)); lbl(2.54, 4.72, "scene\ngraph v2")
flow(c, (1.4, 4.78), (1.0, 4.13)); lbl(0.85, 4.48, "evidence\ncrops")
# row 3
flow(c, (3.35, 4.97), (3.35, 3.97)); lbl(3.35, 4.42, "graph\n(downloaded)")
flow(c, (2.75, 3.38), (2.37, 3.25)); lbl(2.42, 3.6, "rows,\nsummaries")
flow(c, (3.95, 3.38), (4.3, 3.22)); lbl(4.2, 3.55, "registry")
# row 4: answering
flow(c, (1.03, 1.88), (1.5, 1.88)); lbl(1.26, 2.12, "question")
flow(c, (1.5, 1.62), (1.03, 1.62)); lbl(1.26, 1.3, "answer +\nevidence /\nnot sure")
flow(c, (1.62, 2.97), (1.9, 2.12)); lbl(1.6, 2.55, "store rows")
flow(c, (0.3, 3.77), (1.5, 2.05)); lbl(0.78, 2.45, "crop")
flow(c, (2.68, 4.97), (2.5, 2.12)); lbl(2.62, 2.5, "session\ngraph")
flow(c, (3.13, 1.88), (2.7, 1.88)); lbl(2.91, 2.08, "question")
flow(c, (2.7, 1.62), (3.13, 1.62)); lbl(2.91, 1.25, "answers,\ntimeline")
flow(c, (1.95, 1.38), (1.95, 0.63)); lbl(1.55, 1.0, "profile,\nserver URL")
flow(c, (2.25, 0.63), (2.25, 1.38)); lbl(2.65, 1.0, "search\nhistory")
# row 4: management
flow(c, (4.08, 1.75), (4.45, 1.75)); lbl(4.27, 1.15, "room names,\nitems,\npause / resume")
flow(c, (5.05, 2.12), (5.05, 2.97)); lbl(5.35, 2.55, "home_map\n.json", ha="left")
flow(c, (4.6, 2.12), (2.37, 3.08)); lbl(3.75, 2.62, "room labels,\npersonal_items")
c.note(5.95, 0.32, "7.0 also writes room labels to D2 and the\ncapture pause flag; not drawn.",
       ha="right", fs=6.0)
c.save("ch5-dfd-level1")
