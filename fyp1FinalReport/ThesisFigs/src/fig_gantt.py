"""F3.1 FYP-1 Gantt (actual work from git) and F10.1 FYP-2 plan (ch10-fyp2-gantt.png).

Run from the repository root:
    uv run --no-project --with matplotlib python fyp1FinalReport/ThesisFigs/src/fig_gantt.py

F3.1: the planned dates are not in the repository, so only the ACTUAL bars are drawn
(dates from git, hashes checked with `git log -1 <hash>`; the M1/M2 pass starts at
0bfc257 on 12 Nov, not 15 Nov). When the team supplies planned dates, add them to
PLANNED below and they are drawn as hollow bars with a red slip bracket.
F10.1: rows and TODO IDs from DIAGRAM_SPECS F10.1; dates and owners are team input,
so the chart shows order and iteration only.
"""

from datetime import date, timedelta

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from pathlib import Path  # noqa: E402

OUT = Path(__file__).resolve().parent.parent
BLUE, GREEN, ORANGE = "#2F6DB5", "#2E8B57", "#C26E1A"
INK, MUTED, GRID, LINE = "#1F2933", "#52606D", "#E4E7EB", "#6B7785"
OWNER = {"Shahmeer": BLUE, "Faizan": GREEN, "Ali Sher": ORANGE}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 7.6,
                     "savefig.dpi": 300, "savefig.facecolor": "white"})
d = lambda s: date.fromisoformat(f"2026-{s}")  # noqa: E731

ROWS = [  # (label, start, end, owner)
    ("Batch pipeline + R4DSG baseline", "09-01", "10-04", "Faizan"),
    ("CI/CD, API, Flutter scaffold", "10-04", "10-04", "Faizan"),
    ("In-hand memory + Rerun", "10-09", "10-11", "Faizan"),
    ("Live MJPEG sampler", "10-11", "10-11", "Shahmeer"),
    ("Flutter UI redesign, search history", "10-12", "10-12", "Ali Sher"),
    ("Room hierarchy, registry, rooms API", "10-17", "10-17", "Faizan"),
    ("Live capture contracts, keyframes, gaps", "11-06", "11-07", "Shahmeer"),
    ("NLQ engine (first version)", "11-08", "11-09", "Ali Sher"),
    ("Evaluation suite (Options A/C/D, audit)", "11-09", "11-10", "Faizan"),
    ("M1/M2 pass: gravity, relations, runs,\nstore, rooms, compaction, segments", "11-12", "11-15", "Shahmeer"),
    ("Part II plan WP16–WP35", "11-16", "11-16", "Shahmeer"),
    ("Demo harness + calibrate", "11-17", "11-17", "Faizan"),
    ("NLQ consolidation, /ask, Modal serve", "11-18", "11-18", "Ali Sher"),
    ("E2E runner scripts/run_e2e.py", "11-20", "11-20", "Ali Sher"),
    ("EgoLife 7-day study", "11-21", "11-22", "Faizan"),
    ("Tiered query protocol + ranking", "11-22", "11-22", "Faizan"),
    ("SAM3 detector + benchmark", "11-22", "11-22", "Faizan"),
    ("Patient + Caregiver Apps, enrol, DINOv3", "11-23", "11-24", "Ali Sher"),
]
PLANNED: dict[str, tuple[str, str]] = {}  # label -> (start, end); team input
TODAY = d("11-27")

fig, ax = plt.subplots(figsize=(6.0, 5.6))
n = len(ROWS) + 1
# iteration bands
ax.axvspan(d("08-24"), d("10-12"), color="#F3F8FD", zorder=0)
ax.axvspan(d("10-12"), d("12-07"), color="#F3FAF5", zorder=0)
ax.text(d("08-25"), -0.85, "Iteration 1 (to week 41)", fontsize=7, color=BLUE, fontweight="bold")
ax.text(d("10-13"), -0.9, "Iteration 2 (week 42 onward)", fontsize=7, color=GREEN, fontweight="bold")
for i, (label, a, b, who) in enumerate(ROWS):
    start, end = d(a), d(b) + timedelta(days=1)
    ax.barh(i, (end - start).days, left=start, height=0.62, color=OWNER[who], zorder=3)
    if label in PLANNED:
        pa, pb = PLANNED[label]
        ax.barh(i, (d(pb) - d(pa)).days + 1, left=d(pa), height=0.62, fill=False,
                edgecolor=INK, lw=0.9, zorder=4)
# planned, not started
y = len(ROWS)
ax.barh(y, 10, left=d("11-27"), height=0.62, fill=False, edgecolor=LINE, lw=0.9, ls=(0, (3, 2)), zorder=3)
ax.text(d("11-27") - timedelta(days=1), y, "temporal answers, calibrated\nconfidence, auth/consent,\n"
        "encryption, usability study", ha="right", va="center", fontsize=6.2, color=MUTED)
labels = [r[0] for r in ROWS] + ["Planned, not started (Iteration 3+)"]
ax.set_yticks(range(n), labels, fontsize=6.6)
ax.invert_yaxis()
for day, name, row, ha in [("10-04", "v0.1.0-mid1 (4 Oct)", 0, "right"),
                           ("10-13", "v0.2.0-mid2 (13 Oct)", 1, "left"),
                           ("10-22", "mid report (22 Oct)", 0, "left"),
                           ("11-24", "NLQ → develop (24 Nov)", 2, "right")]:
    ax.plot(d(day), -0.35, marker="D", color=INK, markersize=5, zorder=5, clip_on=False)
    ax.axvline(d(day), color=GRID, lw=0.8, zorder=1)
    ax.text(d(day), -1.35 - row * 0.5, name, ha=ha, fontsize=6.2, color=INK, va="center")
ax.axvline(TODAY, color="#C0392B", lw=1.1, zorder=5)
ax.text(TODAY + timedelta(days=1), 9.0, "today, 27 Nov", color="#C0392B", fontsize=6.4, va="center",
        ha="left", rotation=90)
ax.set_ylim(n - 0.4, -2.6)
ax.set_xlim(d("08-24"), d("12-07"))
ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0, interval=1))
ax.xaxis.set_major_formatter(mdates.DateFormatter("W%V"))
ax.tick_params(axis="x", labelsize=6.2)
ax.grid(axis="x", color=GRID, lw=0.6)
ax.set_axisbelow(True)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in OWNER.values()]
ax.legend(handles, list(OWNER), loc="lower left", ncol=3, frameon=False, fontsize=6.8,
          bbox_to_anchor=(0.0, -0.1))
fig.text(0.01, 0.005, "Actual work from git (filled). Planned dates are team input and not yet added.",
         fontsize=6.2, color=MUTED)
fig.tight_layout()
fig.savefig(OUT / "ch3-gantt-plan-vs-actual.png", bbox_inches="tight")
plt.close(fig)
print("wrote ch3-gantt-plan-vs-actual")

# ---------------------------------------------------------------- F10.1
IT3 = [("Temporal answers", "P1.1"), ("Calibrated confidence", "P1.2"), ("Freshness", "P1.3"),
       ("Evidence refs", "P1.4"), ("Multi-instance clarification + query log", "P1.5"),
       ("Speech confirm step", "P1.6"), ("Scale-relative room linking (TC12 fix)", "—"),
       ("demo05 annotation + scoring", "P2.5"), ("Room metrics", "P2.3")]
IT4 = [("Auth / grants / consent / audit / CORS", "P1.7"), ("Encryption + deletion", "P1.8"),
       ("Optional LLM planner", "P1.9"), ("1-hour soak + disconnect tests", "P2.1"),
       ("Placement / activity ground truth", "P2.2"), ("Controlled room", "P2.4"),
       ("Latency p95 + compaction before/after", "P2.8"), ("7 / 30-day persistence pilot", "P2.7"),
       ("Usability study (after ethics approval)", "—"), ("Thesis writing", "—")]
fig, ax = plt.subplots(figsize=(6.0, 5.0))
rows = [(f"{t} ({i})" if i != "—" else t, 3) for t, i in IT3] + [(f"{t} ({i})" if i != "—" else t, 4) for t, i in IT4]
for k, (label, it) in enumerate(rows):
    x0 = 0.0 if it == 3 else 1.0
    ax.barh(k, 1.0, left=x0, height=0.6, fill=False, edgecolor=GREEN if it == 3 else BLUE,
            lw=1.0, ls=(0, (3, 2)))
ax.axvspan(0, 1, color="#F3FAF5", zorder=0)
ax.axvspan(1, 2, color="#F3F8FD", zorder=0)
ax.set_yticks(range(len(rows)), [r[0] for r in rows], fontsize=6.6)
ax.invert_yaxis()
ax.set_xlim(0, 2)
ax.set_xticks([0.5, 1.5], ["Iteration 3", "Iteration 4"], fontsize=7.4)
for x, name in [(1.0, "FYP-2 mid\nevaluation"), (2.0, "FYP-2 final +\nthesis submission")]:
    ax.plot(x, -0.9, marker="D", color=INK, markersize=5, clip_on=False)
    ax.text(x, -1.4, name, ha="center", fontsize=6.2)
ax.set_ylim(len(rows) - 0.4, -1.9)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
fig.text(0.01, 0.005, "Dates and owners are team input (TBD); bars show the iteration only.",
         fontsize=6.2, color=MUTED)
fig.tight_layout()
fig.savefig(OUT / "ch10-fyp2-gantt.png", bbox_inches="tight")
plt.close(fig)
print("wrote ch10-fyp2-gantt")
