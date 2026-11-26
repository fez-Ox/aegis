"""F5.3 UML deployment diagram (ch5-deployment.png).

Run from the repository root:
    uv run --no-project --with matplotlib python fyp1FinalReport/ThesisFigs/src/fig_deployment.py

Verified against: src/aegis/remote/modal_app.py (CPU_IMAGE debian_slim python 3.12;
VGGT_IMAGE on CUDA 12.8.1, torch 2.7.1; Reconstructor 24 GB / Perception 16 GB GPU
memory via _compute; GPU_TYPE L4; scaledown_window=WARM_SECONDS=2; volumes
aegis-poc-data and aegis-model-cache; secret aegis-secrets; preprocess_video_remote,
rerun_remote, fetch_egolife_day), src/aegis/remote/serve.py (aegis-memory-api,
serve_memory_api, CPU), run_pipeline.py (_ingest_into_home), run_server.py (:8000),
.github/workflows/ci.yml (ruff, pytest --cov-fail-under=75, flutter analyze/test) and
cd.yml (release APK), apps/*/pubspec.yaml (aegis_patient / aegis_caregiver 0.3.0+3),
apps/*/android/.../network_security_config.xml (cleartextTrafficPermitted="true"),
core/config.py and perception/detector.py (model ids), geometry/vggt_runner.py
(FALLBACK_REPO).
"""

from boxdraw import Canvas, node, top, bottom, left, right, STYLE

c = Canvas(6.0, 6.55, font=7.2)

# ---------------------------------------------------------------- row 1
phone1 = node(c, 0.05, 5.55, 1.75, 0.85, "«device»\nWearer's Android phone")
c.box(0.15, 5.6, 1.55, 0.42, "IP Webcam app\nMJPEG :8080/video", "W", bold_first=False, fs=6.8)
c.box(2.1, 5.72, 1.65, 0.5, "Auth service /\nencrypted store\n(planned, FYP-2)", "P",
      bold_first=False, fs=6.4)
hf = node(c, 4.0, 5.55, 1.9, 0.85, "«device»\nHugging Face Hub")
c.note(4.95, 5.79, "facebook/VGGT-Omega (gated),\nwincentIsMe/VGGT-Omega,\nsam2-hiera-large, sam3,\n"
       "dinov3-vits16", ha="center", fs=6.4, color="#1F2933")

# ---------------------------------------------------------------- row 2
laptop = node(c, 0.05, 2.0, 1.75, 3.2, "«device»\nDeveloper laptop")
c.note(0.92, 4.77, "Linux, Python 3.12, uv", ha="center", fs=6.6)
lap_items = ["aegis-ingest\n(live_cli.py)", "run_pipeline.py", "scripts/run_e2e.py",
             "run_server.py\nUvicorn :8000 (optional)", "memory.db, home_map.json\n(outputs/_homes/<home>/)",
             "captures/<session>/"]
y = 4.55
for t in lap_items:
    h = 0.24 if "\n" not in t else 0.38
    y -= h + 0.06
    c.box(0.13, y, 1.59, h, t, "B" if "memory.db" in t else "W", bold_first=False, fs=6.4)

modal = node(c, 2.35, 2.0, 3.55, 3.2, "«device»\nModal cloud")
c.box(2.45, 3.92, 1.62, 0.78, "«executionEnvironment»\nCPU container\npreprocess_video_remote,\n"
      "rerun_remote,\nfetch_egolife_day", "A", bold_first=False, fs=6.1)
rec = c.box(4.17, 3.92, 1.62, 0.78, "«executionEnvironment»\nReconstructor (GPU)\nL4, 24 GB,\n"
            "CUDA 12.8.1, torch 2.7.1,\nscaledown 2 s", "A", bold_first=False, fs=6.1)
c.box(4.17, 2.98, 1.62, 0.84, "«executionEnvironment»\nPerception (GPU)\nL4, 16 GB\nSAM3 / YOLOE,\nSAM 2, DINOv3",
      "A", bold_first=False, fs=6.1)
c.box(2.45, 3.44, 0.8, 0.38, "volume\naegis-poc-data", "N", bold_first=False, fs=5.9)
c.box(3.28, 3.44, 0.79, 0.38, "volume\nmodel-cache", "N", bold_first=False, fs=5.9)
c.box(2.45, 2.98, 1.62, 0.38, "secret aegis-secrets\n(name only)", "N", bold_first=False, fs=5.9)
api = c.box(2.45, 2.1, 3.34, 0.78, "«executionEnvironment» aegis-memory-api\nASGI web endpoint (CPU): "
            "serve_memory_api → FastAPI + NLQ\n ", "C",
            bold_first=False, fs=6.2)
c.ax.text(4.12, 2.25, "CORS *; no authentication on mutating routes", ha="center", va="center",
          fontsize=6.2, color="#C0392B", zorder=8,
          bbox=dict(facecolor="#FCE8D0", edgecolor="none", pad=0.6))

# ---------------------------------------------------------------- row 3
gh = node(c, 0.05, 0.45, 1.75, 1.2, "«device»\nGitHub")
c.note(0.92, 0.86, "CI (ci.yml): ruff, pytest\n--cov-fail-under=75,\nflutter analyze / test\n"
       "CD (cd.yml): release\npatient APK", ha="center", fs=6.1, color="#1F2933")
for x0, title, app in [(2.35, "Patient's phone", "Patient App APK\naegis_patient 0.3.0+3\n+ Android speech"),
                       (4.15, "Caregiver's phone", "Caregiver App APK\naegis_caregiver 0.3.0+3")]:
    node(c, x0, 0.45, 1.75, 1.2, "«device»\n" + title)
    c.box(x0 + 0.1, 0.53, 1.55, 0.5, app, "D", bold_first=False, fs=6.2)
    c.ax.text(x0 + 0.875, 1.14, "cleartext LAN permitted", ha="center", va="center", fontsize=6.0,
              color="#C0392B", zorder=8)

# ---------------------------------------------------------------- paths
c.arrow((0.92, 5.55), (0.92, 5.2), "HTTP MJPEG over Wi-Fi LAN", label_at=(0.99, 5.38), fs=6.6)
c.arrow((1.8, 4.2), (2.35, 4.2))
c.note(2.07, 4.55, "Modal\nclient\n(gRPC/\nHTTPS)", ha="center", fs=6.0, color="#1F2933")
c.arrow((4.98, 4.7), (4.98, 5.55))
c.note(4.92, 5.37, "HTTPS weights (HF_TOKEN\nfrom aegis-secrets)", ha="right", fs=6.0, color="#1F2933")
c.arrow((3.0, 1.65), (3.0, 2.1), "HTTPS JSON", label_at=(3.07, 1.85), fs=6.2)
c.arrow((4.9, 1.65), (4.9, 2.1))
c.arrow((2.6, 1.65), (1.62, 2.0), dashed=True)
c.note(1.55, 1.86, "HTTP over LAN (dev)", ha="right", fs=6.0, color="#1F2933")
c.arrow((1.8, 0.85), (2.35, 0.85))
c.note(2.07, 0.66, "release\nAPK", ha="center", fs=6.0, color="#1F2933")
c.note(3.0, 0.2, "Home-store ingest runs on the laptop after download (_ingest_into_home).  "
       "Red: security gap.  Dashed: planned or dev only.", ha="center", fs=6.0)
c.save("ch5-deployment")
