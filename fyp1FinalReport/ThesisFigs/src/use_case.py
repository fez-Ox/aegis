"""F4.1 Use case diagram (ch4-use-case.png), drawn with fixed coordinates.

Graphviz cannot keep actors outside the system boundary without stacking every use
case in one row, so this diagram is placed by hand: shared use cases in the top
middle, user-only on the left, caregiver-only on the right. No association line
crosses an ellipse.

Run from the repository root:
    uv run --no-project --with matplotlib python fyp1FinalReport/ThesisFigs/src/use_case.py

Names match Table 4.1 (DIAGRAM_SPECS F4.1). UC-14 and UC-15 are left out until the
team adopts them. Status checked against src/aegis/remote/api.py (routes),
src/aegis/memory/compaction.py (compact, rollup), src/aegis/nlq/engine.py
(TEMPORAL/ACTIVITY abstain).
"""

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Ellipse, FancyBboxPatch  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "ch4-use-case.png"
INK, LINE, MUTED = "#1F2933", "#52606D", "#6B7785"
ACTOR_FILL, ACTOR_EDGE = "#E9DFF2", "#7B4BA8"
EW, EH = 1.36, 0.66  # ellipse width / height (inches)
FS = 7.6
DASH = (0, (4, 2.5))

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": FS})
W, H = 6.0, 7.6
fig = plt.figure(figsize=(W, H + 0.34))
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, W)
ax.set_ylim(-0.34, H)
ax.axis("off")

# legend (top) and system boundary
ax.text(W / 2, 7.53,
        "Solid ellipse: implemented (\"partial\" where marked). Dashed «planned»: not built.\n"
        "Authorisation is planned (FR8.1): UC-08, 09, 10 and 13 will «include» UC-07;\n"
        "the routes are currently unauthenticated.",
        ha="center", va="top", fontsize=FS - 0.6, color=MUTED, linespacing=1.25)
ax.add_patch(FancyBboxPatch((0.68, 0.5), 4.64, 6.3, boxstyle="round,pad=0,rounding_size=0.05",
                            fill=False, edgecolor=LINE, linewidth=1.1))
ax.text(W / 2, 6.62, "Aegis", ha="center", va="center", fontsize=9, fontweight="bold")

L, M, R = 1.62, 3.0, 4.38
UC = {
    # shared (top middle); UC-06 lowest so every «include» arrow stays clear
    "04": (M, 6.0, "UC-04 Review\nthe history\nof an object", "partial"),
    "11": (M, 5.28, "UC-11 Pause\ncapture or\ndelete history", "partial"),
    "02": (M, 4.56, "UC-02 Submit\na query by\nspeech or text", ""),
    "06": (M, 3.84, "UC-06 View\nevidence for\nan answer", ""),
    # primary user only (left)
    "03": (L, 3.10, "UC-03 Find the\nlast known location\nof an object", ""),
    "01": (L, 2.38, "UC-01 Capture\nand ingest\negocentric video", "partial"),
    "05": (L, 1.66, "UC-05 Recall\nearlier activity", "planned"),
    "07": (L, 0.94, "UC-07 Grant, scope\nand revoke\ncaregiver access", "planned"),
    # caregiver only (right)
    "08": (R, 3.10, "UC-08 Caregiver\nqueries episodic\nhistory", "partial"),
    "09": (R, 2.38, "UC-09 Caregiver\nverifies an\nobject state", "partial"),
    "10": (R, 1.66, "UC-10 Caregiver\nreviews an\nactivity summary", "partial"),
    "13": (R, 0.94, "UC-13 Caregiver\ncalibrates and\nnames rooms", ""),
    # middle, lower
    "ABS": (M, 2.25, "Abstain\n('not sure')", ""),
    "12": (M, 1.20, "UC-12 Maintain\nmemory by\ncompaction", ""),
}


def size(key):
    return {"ABS": 0.98, "12": 1.22}.get(key, EW) / 2, EH / 2


def ellipse(key):
    x, y, text, status = UC[key]
    planned = status == "planned"
    w, h = size(key)
    ax.add_patch(Ellipse((x, y), 2 * w, 2 * h, facecolor="white",
                         edgecolor=MUTED if planned else LINE, linewidth=1.1,
                         linestyle=DASH if planned else "-", zorder=3))
    lines = text.split("\n")
    if status == "partial":
        lines.append("(partial)")
    if planned:
        lines.insert(0, "«planned»")
    ax.text(x, y, "\n".join(lines), ha="center", va="center",
            fontsize=FS - (0.5 if len(lines) > 3 else 0), color=MUTED if planned else INK,
            zorder=4, linespacing=1.05)


def boundary_point(key, toward):
    x, y, *_ = UC[key]
    w, h = size(key)
    dx, dy = toward[0] - x, toward[1] - y
    t = 1 / math.sqrt((dx / w) ** 2 + (dy / h) ** 2)
    return x + dx * t, y + dy * t


def actor(x, y, name, label_side="below"):
    ax.add_patch(plt.Circle((x, y + 0.24), 0.09, facecolor=ACTOR_FILL, edgecolor=ACTOR_EDGE,
                            lw=1.1, zorder=5))
    for xs, ys in [([x, x], [y + 0.15, y - 0.07]), ([x - 0.14, x + 0.14], [y + 0.07, y + 0.07]),
                   ([x, x - 0.11], [y - 0.07, y - 0.24]), ([x, x + 0.11], [y - 0.07, y - 0.24])]:
        ax.plot(xs, ys, color=ACTOR_EDGE, lw=1.3, zorder=5)
    if label_side == "below":
        ax.text(x, y - 0.32, name, ha="center", va="top", fontsize=FS + 0.4, linespacing=1.1)
    else:
        ax.text(x + 0.22, y, name, ha="left", va="center", fontsize=FS + 0.4)


def assoc(anchor, key, side):
    """Line from the actor to the ellipse's side-most point (left or right)."""
    x, y, *_ = UC[key]
    w, _ = size(key)
    end = (x - w, y) if side == "left" else (x + w, y)
    ax.plot([anchor[0], end[0]], [anchor[1], end[1]], color=LINE, lw=1.0, zorder=2)


def dep(src, dst, label, label_at, src_pt=None, dst_pt=None):
    a = src_pt or boundary_point(src, UC[dst][:2])
    b = dst_pt or boundary_point(dst, UC[src][:2])
    ax.annotate("", xy=b, xytext=a, zorder=2,
                arrowprops=dict(arrowstyle="-|>", color=LINE, lw=0.9, linestyle=DASH,
                                shrinkA=0, shrinkB=0))
    ax.text(*label_at, label, ha="center", va="center", fontsize=FS - 1, color=LINE,
            bbox=dict(facecolor="white", edgecolor="none", pad=0.5), zorder=4)


for k in UC:
    ellipse(k)

USER, CARE = (0.28, 3.3), (5.72, 3.3)
actor(*USER, "Primary\nuser")
actor(*CARE, "Care-\ngiver")
CLOCK = (2.0, 0.16)
actor(*CLOCK, "System clock\n«timer»", label_side="right")

ua, ca = (USER[0] + 0.13, USER[1] + 0.09), (CARE[0] - 0.13, CARE[1] + 0.09)
for k in ["04", "11", "02", "06", "03", "01", "05", "07"]:
    assoc(ua, k, "left")
for k in ["04", "11", "02", "06", "08", "09", "10", "13"]:
    assoc(ca, k, "right")
x12, y12, *_ = UC["12"]
ax.plot([CLOCK[0] + 0.05, x12 - 0.25], [CLOCK[1] + 0.36, y12 - EH / 2 + 0.04], color=LINE, lw=1.0)

w, h = size("03")
dep("03", "06", "«include»", (2.22, 3.36), src_pt=(L + 0.3, 3.10 + h - 0.03))
dep("03", "02", "«include»", (1.55, 3.92), src_pt=(L - 0.25, 3.10 + h * 0.92),
    dst_pt=(M - EW / 2 + 0.03, 4.56 - 0.07))
dep("08", "06", "«include»", (3.78, 3.36), src_pt=(R - 0.3, 3.10 + h - 0.03))
dep("09", "06", "«include»", (3.48, 2.95), src_pt=(R - size("09")[0], 2.38),
    dst_pt=boundary_point("06", (3.6, 2.9)))
dep("ABS", "03", "«extend»\n{item unknown or\nnever observed}", (2.78, 2.95),
    src_pt=boundary_point("ABS", (L, 3.1)), dst_pt=boundary_point("03", (M, 2.25)))

fig.savefig(OUT, dpi=300, facecolor="white")
print("wrote", OUT.name)
