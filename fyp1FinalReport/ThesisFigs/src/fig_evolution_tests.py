"""F5.4 design evolution (ch5-design-evolution.png) and F8.1 test levels
(ch8-test-levels.png).

Run from the repository root:
    uv run --no-project --with matplotlib python fyp1FinalReport/ThesisFigs/src/fig_evolution_tests.py

F5.4: mid report = commit 2298112 (17 Oct); final = develop. The numbers ①–⑨ match
the design-evolution table in NEW_CONTENT.md. Each row checked against the code:
config/demo.yaml + live.yaml (sam3 / yoloe), perception/detector.py (DINOv3),
geometry/gravity.py, memory/scene_graph.py (schema v2, state runs), relations.py
(9 relations), memory/store.py, compaction.py, memory/reasoning.py + nlq/engine.py,
remote/serve.py, apps/Patient App + apps/Caregiver App, ingestion/live_handoff.py.

F8.1: `uv run pytest --collect-only -q` on develop: 451 tests in 53 files, grouped
as DIAGRAM_SPECS F8.1; Flutter counts from `grep -c "testWidgets\\|test("`.
Coverage 79 % (10,759 statements) from the run on ce49dcc; CI floor 75 %
(.github/workflows/ci.yml --cov-fail-under=75).
"""

from boxdraw import Canvas, STYLE, INK, MUTED, LINE

# ------------------------------------------------------------------ F5.4
ROWS = [
    ("Capture", "YOLOE / YOLO-World + SAM 2",
     "SAM3 (demo) / YOLOE (live)\n+ SAM 2 + DINOv3 re-ID", 1),
    ("Geometry", "raw VGGT coordinates,\nno up-vector", "+ gravity frame (gravity.json)", 2),
    ("Memory", "per-frame timeline\n(schema v1)", "state runs + latest states\n(schema v2)", 3),
    ("Memory", "relations: on_surface,\ninside, in-hand", "9 relations in the\ngravity frame", 4),
    ("Memory", "JSON graph only", "+ SQLite home store,\ncross-session matching", 5),
    ("Memory", "compaction planned", "compaction + roll-up\nimplemented", 6),
    ("Query", "QueryReasoningEngine only", "+ rank_candidates,\n/ask NLQ engine", 7),
    ("Query", "local FastAPI", "Modal-deployed\naegis-memory-api", 8),
    ("Apps", "single apps/mobile", "Patient App + Caregiver App;\nlive sampler joined to the\npipeline by promotion + segments", 9),
]
LAYER_STYLE = {"Capture": "A", "Geometry": "A", "Memory": "B", "Query": "C", "Apps": "D"}
CIRCLED = "①②③④⑤⑥⑦⑧⑨"

c = Canvas(6.0, 6.0, font=7.8)
c.note(2.05, 5.82, "Mid report (17 Oct, 2298112)", ha="center", color=INK, fs=8.4,
       weight="bold")
c.note(4.45, 5.82, "FYP-1 final (develop)", ha="center", color=INK, fs=8.4, weight="bold")
y = 5.55
for layer, mid, final, n in ROWS:
    lines = max(mid.count("\n"), final.count("\n")) + 1
    h = 0.2 + 0.15 * lines
    y -= h
    st = LAYER_STYLE[layer]
    c.box(0.05, y, 0.85, h, layer, st, fs=7.4)
    c.box(1.0, y, 2.1, h, mid, "W", bold_first=False)
    b = c.box(3.4, y, 2.1, h, final, st, bold_first=False, lw=1.6)
    # highlight the changed box with an orange border
    c.ax.add_patch(__import__("matplotlib.patches", fromlist=["x"]).FancyBboxPatch(
        (3.4, y), 2.1, h, boxstyle="round,pad=0,rounding_size=0.04", fill=False,
        edgecolor=STYLE["C"][1], linewidth=1.8, zorder=5))
    c.arrow((3.1, y + h / 2), (3.4, y + h / 2))
    c.note(5.75, y + h / 2, CIRCLED[n - 1], ha="center", color=INK, fs=11)
    y -= 0.07
c.note(3.0, 0.12, "Orange border: changed since the mid report. Numbers match the "
       "design-evolution table.", ha="center")
c.save("ch5-design-evolution")

# ------------------------------------------------------------------ F8.1
TIERS = [  # (label, count, files)
    ("Unit: geometry & perception", 47,
     "test_geometry 5, test_gravity 12, test_planar 6, test_lifting 15,\n"
     "test_detector_postprocess 6, test_vggt_checkpoint 3"),
    ("Unit: memory", 141,
     "test_anchors 4, test_association 6, test_relations 19, test_runs 5, test_rooms 9,\n"
     "test_scene_graph 18, test_room_identity 6, test_matching 15, test_store 4,\n"
     "test_ingest 12, test_compaction 14, test_activities 7, test_evidence 7,\n"
     "test_home_registry 4, test_restart_equivalence 3, test_wallclock 4, test_mid1_prototype 4"),
    ("Unit: config, vocabulary, query", 62,
     "test_config 10, test_vocabulary 19, test_reasoning 12, test_ranking 12, test_nlq 9"),
    ("Integration: ingestion / live", 64,
     "test_live_ingestion 13, test_live_contracts 12, test_live_handoff 8,\n"
     "test_live_segments 7, test_live_keyframe 6, test_live_buffer 3, test_live_cli 8,\n"
     "test_video_ingestion 5, test_capture_control 2"),
    ("Integration: API & serving", 38,
     "test_api 28, test_repository 4, test_serve_app 2, test_modal_compute 1,\n"
     "test_rerun_visualization 3"),
    ("Tooling: E2E runner & demo", 28, "test_run_e2e 17, test_demo_harness 7, test_demo_calibrate 4"),
]
assert sum(t[1] for t in TIERS) + 71 == 451

c = Canvas(6.0, 5.0, font=7.8)
cx = 2.15
import matplotlib.patches as mp  # noqa: E402


def trapezoid(y0, y1, hw0, hw1, style, dashed=False):
    fill, edge = STYLE[style]
    c.ax.add_patch(mp.Polygon([(cx - hw0, y0), (cx + hw0, y0), (cx + hw1, y1), (cx - hw1, y1)],
                              closed=True, facecolor=fill, edgecolor=edge, linewidth=1.1,
                              linestyle=(0, (4, 2.5)) if dashed else "-", zorder=2))


# top: system (dashed); middle: integration + tooling; base: unit
trapezoid(3.65, 4.85, 0.78, 0.06, "P", dashed=True)
trapezoid(2.25, 3.65, 1.42, 0.78, "C")
trapezoid(0.75, 2.25, 2.1, 1.42, "B")
c.note(cx, 4.02, "System /\nacceptance", ha="center", color=MUTED, fs=7.6, weight="bold")
c.note(cx, 3.28, "Integration + tooling: 130", ha="center", color=INK, fs=8, weight="bold")
c.note(cx, 2.78, "ingestion / live 64\nAPI & serving 38\nE2E runner & demo 28", ha="center",
       color=INK, fs=7.6)
c.note(cx, 1.92, "Unit: 250", ha="center", color=INK, fs=8, weight="bold")
c.note(cx, 1.35, "geometry & perception 47\nmemory 141\nconfig, vocabulary, query 62",
       ha="center", color=INK, fs=7.6)
c.note(cx + 0.95, 4.55, "one measured E2E run\n(20 Nov, CPU); 1-hour soak,\n"
       "p95 latency, usability:\nnot yet run", fs=7.0)

c.box(4.45, 0.75, 1.5, 4.1, "Evaluation &\nmeasurement: 71\n\ntest_egolife 30\n"
      "evaluation_metrics 13\nevaluation_query 8\nevaluation 6\nevaluation_option_c 6\n"
      "evaluation_memory_\naudit 4\nevaluation_controlled_\nroom 3\nevaluation_run 1",
      "N", fs=7.0)
c.note(3.0, 0.45, "Python: 451 tests in 53 files (pytest --collect-only, develop).  "
       "Flutter widget tests: Patient 14, Caregiver 11.", ha="center", fs=7.0)
c.note(3.0, 0.17, "Coverage 79 % (pytest --cov=aegis, 10,759 statements); CI floor 75 %.",
       ha="center", fs=7.0)
c.save("ch8-test-levels")
