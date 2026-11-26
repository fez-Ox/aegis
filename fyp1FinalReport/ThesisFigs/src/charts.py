"""Charts for the FYP-1 final report (F2.3, F8.3, F8.4, F8.5, F9.1, F9.2).

Run from the repository root:
    uv run --with matplotlib python fyp1FinalReport/ThesisFigs/src/charts.py

Every number below is copied from the file named next to it; F9.1 is counted
live from git. Output: PNG, 300 dpi, sized for the 15 cm report text width so the
fonts print at their nominal size.
"""

from __future__ import annotations

import subprocess
from collections import Counter
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

OUT = Path(__file__).resolve().parent.parent
REPO = OUT.parent.parent

# Palette: module/owner colours of DIAGRAM_SPECS §0.3 (borders), validated with the
# dataviz palette checker; orange darkened for contrast on white.
BLUE, GREEN, ORANGE, PURPLE = "#2F6DB5", "#2E8B57", "#C26E1A", "#7B4BA8"
GREY, INK, MUTED, GRID = "#9AA5B1", "#1F2933", "#52606D", "#E4E7EB"
RED = "#C0392B"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.edgecolor": MUTED,
    "axes.labelcolor": INK,
    "axes.titlesize": 10,
    "axes.titleweight": "bold",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "axes.axisbelow": True,
    "grid.color": GRID,
    "grid.linewidth": 0.6,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "text.color": INK,
    "legend.frameon": False,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.facecolor": "white",
})
WIDTH_IN = 6.0  # ≈ 15.2 cm


def save(fig, name):
    fig.savefig(OUT / f"{name}.png")
    plt.close(fig)
    print("wrote", name)


# --------------------------------------------------------------------------- F2.3
def detector_ab():
    # docs/detection_benchmark.md, table "Variant | Prompts | P | R | F1 | FP/img"
    rows = [
        ("YOLOE-11l\ngeneric (93)", 0.357, 0.056, 0.097, 0.9),
        ("YOLOE-11l\ncompact (18)", 0.556, 0.056, 0.102, 0.4),
        ("YOLO-World m\ncompact (18)", 0.460, 0.191, 0.270, 2.0),
        ("SAM3 compact\nthr 0.5 (18)", 0.326, 0.798, 0.463, 14.7),
        ("SAM3 compact,\nclass thr,\nNMS 0.7 (shipped)", 0.718, 0.724, 0.721, 3.3),
    ]
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 3.3))
    w = 0.26
    for i, (label, p, r, f1, fp) in enumerate(rows):
        shipped = i == len(rows) - 1
        for j, (v, c) in enumerate([(p, BLUE), (r, ORANGE), (f1, PURPLE)]):
            ax.bar(i + (j - 1) * w, v, w - 0.03, color=c,
                   edgecolor=INK if shipped else "white",
                   linewidth=1.2 if shipped else 0.5)
        ax.text(i, max(p, r, f1) + 0.04, f"{fp} FP/img", ha="center",
                fontsize=8, color=MUTED, fontweight="bold" if shipped else "normal")
    ax.set_xticks(range(len(rows)), [r[0] for r in rows], fontsize=8)
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("score")
    ax.grid(axis="x", visible=False)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (BLUE, ORANGE, PURPLE)]
    ax.legend(handles, ["Precision", "Recall", "F1"], ncol=3, loc="upper left")
    save(fig, "ch2-detector-ab")


# --------------------------------------------------------------------------- F8.3
def compaction_ratio():
    # evaluation/reports/memory_control/summary.md (Ratio, Centre p95 columns)
    intervals = ["0", "1", "10", "30"]
    ratio = {"demo04": [7.2, 1.9, 5.4, 6.4], "demo03": [5.7, 1.5, 4.4, 5.0]}
    p95 = {"demo04": [0.363, 0.000, 0.241, 0.245], "demo03": [0.219, 0.000, 0.137, 0.178]}
    colors = {"demo04": BLUE, "demo03": ORANGE}
    fig, (a, b) = plt.subplots(1, 2, figsize=(WIDTH_IN, 2.8))
    w = 0.36
    for k, (name, vals) in enumerate(ratio.items()):
        xs = [i + (k - 0.5) * w for i in range(4)]
        a.bar(xs, vals, w - 0.04, color=colors[name], label=name)
        for x, v in zip(xs, vals):
            a.text(x, v + 0.12, f"{v}×", ha="center", fontsize=7.5, color=INK)
    a.set_xticks(range(4), intervals)
    a.set_xlabel("snapshot interval (frames)")
    a.set_ylabel("compaction ratio (×)")
    a.set_title("(a) Size reduction", loc="left")
    a.set_ylim(0, 9.5)
    a.grid(axis="x", visible=False)
    a.legend(loc="upper center", ncol=2)
    for name, vals in p95.items():
        b.plot(range(4), vals, color=colors[name], linewidth=2, marker="o", markersize=5,
               label=name)
    b.set_xticks(range(4), intervals)
    b.set_xlabel("snapshot interval (frames)")
    b.set_ylabel("centre p95 error (scene units)")
    b.set_title("(b) Position error", loc="left")
    b.set_ylim(0, 0.45)
    b.legend(loc="upper center", ncol=2)
    fig.text(0.5, -0.04, "Semantic retention, latest-state exactness and query agreement "
             "= 100% in all 8 runs", ha="center", fontsize=8, color=MUTED)
    fig.tight_layout()
    save(fig, "ch8-compaction-ratio")


# --------------------------------------------------------------------------- F8.4
def storage_projection():
    # evaluation/reports/memory_control/summary.md, projection table (MiB)
    hours = [1, 8, 24]
    series = [
        ("demo04 original", [13.51, 108.1, 324.2], BLUE, "-"),
        ("demo04 compacted", [2.11, 16.9, 50.7], BLUE, "--"),
        ("demo03 original", [18.76, 150.1, 450.3], ORANGE, "-"),
        ("demo03 compacted", [3.27, 26.1, 78.4], ORANGE, "--"),
    ]
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 3.0))
    for name, vals, c, ls in series:
        ax.plot(hours, vals, color=c, linestyle=ls, linewidth=2, marker="o", markersize=5)
        ax.annotate(f"{name}  {vals[-1]:g} MiB", (hours[-1], vals[-1]),
                    xytext=(6, 0), textcoords="offset points", va="center", fontsize=8)
    ax.set_xticks(hours, [f"{h} h" for h in hours])
    ax.set_xlim(0, 36)
    ax.set_ylim(0, 480)
    ax.set_ylabel("memory size (MiB)")
    ax.set_xlabel("recording length")
    ax.set_title("Linear projection from short clips — not measured", loc="left")
    save(fig, "ch8-storage-projection")


# --------------------------------------------------------------------------- F8.5
def e2e_timing():
    # TODO.md (2026-11-20 CPU run) and docs/egolife.md (L4, one 5-min segment)
    bars = [
        ("VGGT reconstruction", 831, BLUE),
        ("detect + lift", 27, BLUE),
        ("deploy", 8, BLUE),
        ("VGGT reconstruction", 200, GREY),
        ("detection", 108, GREY),
    ]
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 2.7))
    ys = [4.4, 3.4, 2.4, 0.7, -0.3]
    for y, (label, s, c) in zip(ys, bars):
        ax.barh(y, s, 0.7, color=c)
        ax.text(s + 10, y, f"{s} s", va="center", fontsize=8)
    ax.set_yticks(ys, [b[0] for b in bars])
    ax.set_xlabel("seconds")
    ax.set_xlim(0, 950)
    ax.grid(axis="y", visible=False)
    ax.text(0, 5.15, "Measured: CPU run, 20 Nov 2026 (walk01-2, 79 frames)",
            fontsize=8, color=BLUE, fontweight="bold", va="bottom")
    ax.text(0, 1.35, "Reference: L4 GPU, one 5-min EgoLife segment", fontsize=8,
            color=MUTED, fontweight="bold", va="bottom")
    ax.set_ylim(-0.9, 5.7)
    save(fig, "ch8-e2e-timing")


# --------------------------------------------------------------------------- F9.1
PEOPLE = {"pez-Ox": "Faizan", "Faizan Ur Rehman Khan": "Faizan",
          "shah-paradox": "Shahmeer", "Ali Sher": "Ali Sher"}


def commit_timeline():
    # git log --no-merges on develop; commits that only touch the report folder
    # (fyp1FinalReport/) are report writing, not development, and are excluded.
    log = subprocess.run(
        ["git", "log", "develop", "--no-merges", "--name-only",
         "--format=@@%H|%ad|%an", "--date=format:%G-%V"],
        cwd=REPO, capture_output=True, text=True, check=True).stdout
    counts: Counter = Counter()
    for block in log.split("@@")[1:]:
        head, *files = [ln for ln in block.strip().splitlines() if ln]
        _, week, author = head.split("|")
        if files and all(f.startswith("fyp1FinalReport/") for f in files):
            continue
        counts[(int(week.split("-")[1]), PEOPLE[author])] += 1
    weeks = list(range(35, 49))
    people = [("Faizan", GREEN), ("Shahmeer", BLUE), ("Ali Sher", ORANGE)]
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 3.0))
    bottom = [0] * len(weeks)
    for name, c in people:
        vals = [counts[(w, name)] for w in weeks]
        ax.bar(weeks, vals, 0.72, bottom=bottom, color=c, label=name,
               edgecolor="white", linewidth=0.8)
        bottom = [b + v for b, v in zip(bottom, vals)]
    for w, total in zip(weeks, bottom):
        if total:
            ax.text(w, total + 2, str(total), ha="center", fontsize=7.5, color=MUTED)
    # x position = ISO week + weekday offset (Mon = -0.4 … Sun = +0.45)
    for x, label, row, ha in [(40.45, "v0.1.0-mid1 (4 Oct)", 0, "right"),
                              (41.75, "v0.2.0-mid2 (13 Oct)", 1, "left"),
                              (43.1, "mid report (22 Oct)", 2, "left"),
                              (47.6, "NLQ → develop (24 Nov)", 0, "right")]:
        ax.axvline(x, color=GREY, linewidth=1, linestyle=":")
        ax.text(x + (-0.1 if ha == "right" else 0.1), 168 - row * 12, label,
                fontsize=7.5, color=MUTED, ha=ha, va="center")
    ax.set_xticks(weeks, [f"W{w}" for w in weeks], fontsize=8)
    ax.set_ylim(0, 175)
    ax.set_ylabel("non-merge commits")
    ax.set_xlabel("ISO week (2026)")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="center left", bbox_to_anchor=(0.12, 0.45))
    save(fig, "ch9-commit-timeline")
    print("  counts:", dict(sorted(counts.items())))


# --------------------------------------------------------------------------- F9.2
def branch_graph():
    # git log --merges (hashes verified with `git log -1 <hash>`)
    lanes = ["main", "develop", "feat/NLQ", "feat/memory-plan", "feat/evaluation-suite",
             "feature branches\n(Oct)"]
    y = {name: len(lanes) - 1 - i for i, name in enumerate(lanes)}
    d = lambda s: date.fromisoformat(f"2026-{s}")  # noqa: E731
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 3.4))
    spans = {"main": ("09-28", "11-24"), "develop": ("09-28", "11-24"),
             "feat/NLQ": ("11-08", "11-24"), "feat/memory-plan": ("11-06", "11-17"),
             "feat/evaluation-suite": ("11-09", "11-17"),
             "feature branches\n(Oct)": ("09-28", "10-11")}
    lane_color = {"main": INK, "develop": BLUE, "feat/NLQ": ORANGE,
                  "feat/memory-plan": GREEN, "feat/evaluation-suite": GREEN,
                  "feature branches\n(Oct)": PURPLE}
    for name, (a, b) in spans.items():
        ax.plot([d(a), d(b)], [y[name]] * 2, color=lane_color[name], linewidth=2.2,
                solid_capstyle="round")

    def merge(day, src, dst, label=None, dy=0.0):
        ax.annotate("", xy=(d(day), y[dst]), xytext=(d(day), y[src]),
                    arrowprops=dict(arrowstyle="-|>", color=lane_color[src], lw=1.3,
                                    shrinkA=3, shrinkB=3))
        ax.plot(d(day), y[dst], "o", color="white", markeredgecolor=lane_color[src],
                markersize=6, markeredgewidth=1.6, zorder=5)
        if label:
            ax.text(d(day), y[dst] + 0.28 + dy, label, fontsize=7, ha="center", color=MUTED)

    merge("10-04", "feature branches\n(Oct)", "develop")
    merge("10-09", "feature branches\n(Oct)", "develop")
    merge("10-09", "develop", "main")
    merge("10-11", "develop", "main")
    merge("10-12", "develop", "main")
    merge("11-07", "main", "develop")
    merge("11-15", "develop", "feat/NLQ")
    merge("11-15", "feat/memory-plan", "feat/NLQ")
    merge("11-15", "feat/evaluation-suite", "feat/NLQ")
    merge("11-17", "feat/evaluation-suite", "develop")
    merge("11-17", "feat/memory-plan", "develop")
    merge("11-23", "main", "feat/NLQ")
    notes = [("10-04", "feature branches", "5 merges\n4 Oct", "right"),
             ("10-09", "feature branches", "in-hand\n9 Oct", "left"),
             ("10-10", "main", "develop → main ×3, 9–12 Oct", "center"),
             ("11-07", "develop", "main → develop\n7 Nov", "right"),
             ("11-15", "feat/NLQ", "3 merges 15 Nov,\n2 into develop 17 Nov", "right")]
    for day, lane, text, ha in notes:
        up = lane.endswith("+")
        lane = lane.rstrip("+")
        key = lane if lane in y else "feature branches\n(Oct)"
        dx = {"right": -0.6, "left": 0.6, "center": 0}[ha]
        if lane == "main":
            yy = y[key] + 0.62
        elif lane == "feature branches" or up:
            yy = y[key] + 0.45
        else:
            yy = y[key] - 0.38
        ax.text(mdates.date2num(d(day)) + dx, yy, text, fontsize=7, color=MUTED, ha=ha,
                va="center")
    for day, tag in [("10-04", "v0.1.0-mid1"), ("10-13", "v0.2.0-mid2")]:
        ax.plot(d(day), y["main"], "D", color=INK, markersize=6, zorder=6)
        ax.text(mdates.date2num(d(day)) + (-0.8 if tag.endswith("mid1") else 0.8),
                y["main"] + 0.3, tag, fontsize=7.5, fontweight="bold",
                ha="right" if tag.endswith("mid1") else "left", va="center")
    # 21–22 Nov: work committed directly on main
    ax.plot([d("11-21"), d("11-22")], [y["main"]] * 2, color=RED, linewidth=5,
            solid_capstyle="butt")
    ax.text(mdates.date2num(d("11-20")), y["main"] + 0.32, "direct commits\non main 21–22 Nov",
            fontsize=7, color=RED, ha="right", va="center")
    # 24 Nov: develop fast-forwarded to feat/NLQ
    ax.annotate("", xy=(d("11-24"), y["develop"]), xytext=(d("11-24"), y["feat/NLQ"]),
                arrowprops=dict(arrowstyle="-|>", color=ORANGE, lw=1.3, linestyle="--"))
    ax.text(mdates.date2num(d("11-24")) + 0.8, y["feat/NLQ"] - 0.55,
            "23 Nov: main → feat/NLQ\n24 Nov: develop fast-\nforwarded to feat/NLQ", fontsize=7, ha="left",
            va="center", color=MUTED)
    # planned final merge + tag
    ax.plot([d("11-24"), d("12-04")], [y["main"]] * 2, color=INK, linewidth=1.5,
            linestyle="--")
    ax.plot(d("12-04"), y["main"], "D", color="white", markeredgecolor=INK,
            markersize=6, markeredgewidth=1.4)
    ax.text(d("12-04"), y["main"] + 0.32, "v0.3.0-fyp1-final\n(planned)", fontsize=7,
            ha="center", color=MUTED)
    ax.set_yticks(list(y.values()), list(y.keys()), fontsize=8)
    ax.set_ylim(-0.6, len(lanes) + 0.05)
    ax.set_xlim(d("09-25"), d("12-10"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0, interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.grid(axis="y", visible=False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    save(fig, "ch9-branch-graph")


if __name__ == "__main__":
    detector_ab()
    compaction_ratio()
    storage_projection()
    e2e_timing()
    commit_timeline()
    branch_graph()
