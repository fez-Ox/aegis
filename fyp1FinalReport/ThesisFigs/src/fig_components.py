"""F5.2 UML component diagram (ch5-components.png).

Run from the repository root:
    uv run --no-project --with matplotlib python fyp1FinalReport/ThesisFigs/src/fig_components.py

Dependencies are the package imports in src/aegis (top-level and lazy, checked with
grep): ingestion/geometry/perception → core; memory → core, geometry;
evaluation → core, memory; nlq → memory.repository (lazy); remote.api → core, memory,
nlq; remote.workers → core, ingestion, geometry, perception, memory, visualization.
Endpoints from apps/*/lib/services/api_service.dart. Artifacts and their producers
are drawn in F5.8 and the DFD (F5.12), so they are not repeated here.
"""

import matplotlib.patches as mp

from boxdraw import Canvas, STYLE, INK, LINE, MUTED, top, bottom, left, right

c = Canvas(6.0, 5.6, font=7.2)


def comp(x, y, w, h, name, provides, style):
    """Component box: name, component icon, provided interfaces below the name."""
    c.box(x, y, w, h, "", style, fs=6.8)
    c.text_in(x, y, w, h - 0.2, name + ("\n" + provides if provides else ""), fs=6.6)
    ix, iy = x + w - 0.2, y + h - 0.2
    c.ax.add_patch(mp.Rectangle((ix, iy), 0.13, 0.13, facecolor="white", edgecolor=LINE, lw=0.7, zorder=6))
    for dy in (0.02, 0.07):
        c.ax.add_patch(mp.Rectangle((ix - 0.035, iy + dy), 0.07, 0.035, facecolor="white",
                                    edgecolor=LINE, lw=0.7, zorder=7))
    return (x, y, w, h)


def group(x, y, w, h, title, ha="left"):
    c.ax.add_patch(mp.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.04",
                                     fill=False, edgecolor=MUTED, lw=0.9, linestyle=(0, (4, 2.5)), zorder=1))
    tx = x + 0.08 if ha == "left" else x + w - 0.08
    c.note(tx, y + h - 0.1, title, fs=6.8, color=INK, weight="bold", ha=ha)


def dep(p, q, label=None, at=None):
    c.arrow(p, q, label, label_at=at, dashed=True, fs=6.4)


# ------------------------------------------------------------- clients (top)
group(0.05, 4.38, 5.9, 1.17, "Android devices and terminal (clients)")
pat = comp(0.2, 4.47, 1.75, 0.78, "Patient App", "/query, /ask, /health,\n/datasets, /scene_graph", "D")
car = comp(2.12, 4.47, 1.75, 0.78, "Caregiver App", "+ /rooms, /rooms/rename,\n/enroll, /timeline,\n/capture/status", "D")
cli = comp(4.05, 4.47, 1.75, 0.78, "aegis-ask CLI", "nlq/cli.py: HTTP API\nor local graph", "D")

# ------------------------------------------------------------- Modal apps
group(0.05, 2.75, 2.85, 1.15, "Modal app aegis-memory-api")
api = comp(0.2, 2.85, 2.55, 0.88, "remote.api", "api.py, serve.py\nprovides HTTP API /api/v1", "C")
group(3.1, 2.75, 2.85, 1.15, "Modal app aegis-poc")
wrk = comp(3.25, 2.85, 2.55, 0.88, "remote.workers", "workers.py, modal_app.py\nrun_preprocess, run_vggt,\n"
           "run_detect_and_lift, run_rerun", "N")

# assembly connector: ball on remote.api, one socket joined to all three clients
bx, by = 1.475, 4.03
c.ax.plot([bx, bx], [api[1] + api[3], by - 0.06], color=LINE, lw=1.0, zorder=5)
c.ax.add_patch(mp.Circle((bx, by), 0.06, facecolor="white", edgecolor=LINE, lw=1.1, zorder=6))
c.ax.add_patch(mp.Arc((bx, by), 0.2, 0.2, theta1=20, theta2=160, color=LINE, lw=1.1, zorder=6))
c.note(bx - 0.14, by, "HTTP API", fs=6.6, color=INK, weight="bold", ha="right")
c.ax.plot([bx, bx], [by + 0.1, 4.25], color=LINE, lw=1.0, zorder=5)
c.ax.plot([pat[0] + pat[2] / 2, cli[0] + cli[2] / 2], [4.25, 4.25], color=LINE, lw=1.0, zorder=5)
for b in (pat, car, cli):
    sx = b[0] + b[2] / 2
    c.ax.plot([sx, sx], [b[1], 4.25], color=LINE, lw=1.0, zorder=5)

# ------------------------------------------------------------- library packages
group(0.05, 0.3, 5.9, 2.25, "aegis library (src/aegis)", ha="right")
W, H, Y = 0.8, 1.1, 1.15
xs = [0.15, 0.98, 1.81, 2.64, 3.47, 4.3, 5.13]
ev = comp(xs[0], Y, W, H, "evaluation", "reports;\nneeds\nmemory", "N")
nlq = comp(xs[1], Y, W, H, "nlq", "AnswerEngine\n.ask,\nDictionary-\nIndex", "C")
mem = comp(xs[2], Y, W, H, "memory", "Memory-\nRepository,\nHomeStore,\ningest_session,\ncompact", "B")
geo = comp(xs[3], Y, W, H, "geometry", "run_vggt_\nreconstruction,\nGravityFrame,\nlift_detection_\nto_3d", "A")
per = comp(xs[4], Y, W, H, "perception", "detect_and_\ntrack_objects", "A")
ing = comp(xs[5], Y, W, H, "ingestion", "FrameSource,\npromote_live_\nsegments", "A")
vis = comp(xs[6], Y, W, H, "visualiz-\nation", "run_rerun", "N")
core = comp(0.15, 0.38, 5.7, 0.42, "core", "RuntimeConfig, Vocabulary, DatasetPaths, models  ·  used by every package", "N")

# dependencies (dashed «use»)
dep((api[0] + 0.6, api[1]), top(nlq), "AnswerEngine", at=(0.3, 2.42))
dep((api[0] + 1.6, api[1]), top(mem), "MemoryRepository", at=(1.98, 2.42))
c.arrow(bottom(nlq), bottom(mem), dashed=True, rad=0.6)
c.arrow(bottom(mem), bottom(geo), dashed=True, rad=0.6)
c.note(1.79, 0.9, "graph view", ha="center", fs=5.8, color=INK)
c.note(2.62, 0.9, "GravityFrame", ha="center", fs=5.8, color=INK)
for t in (geo, per, ing, vis):
    dep((wrk[0] + 0.2 + (t[0] - geo[0]) * 0.75, wrk[1]), top(t))
dep((wrk[0] + 0.05, wrk[1]), (mem[0] + mem[2] - 0.1, mem[1] + mem[3]))
c.note(5.95, 0.12, "Dashed arrow: «use» (import).  Ball and socket: the HTTP API provided by remote.api "
       "and required by the clients.", ha="right", fs=6.2)
c.save("ch5-components")
