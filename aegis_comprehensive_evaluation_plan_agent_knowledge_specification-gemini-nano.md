# Aegis Comprehensive Evaluation Specification & Agent Knowledge Base

> **Document Purpose:** Authoritative technical specification for designing, implementing, executing, and maintaining the end-to-end evaluation framework for **Aegis**.  
> **Intended Audience:** Engineering agents (e.g., repository coding agents reading alongside `AGENTS.md`, `docs/artifact_contracts.md`, and `docs/evaluation_plan.md`) and human reviewers preparing quantitative evidence for an assessment panel.

---

## 1. Agent Operating Constraints & Non-Negotiable Invariants

Before writing or modifying evaluation code, any agent operating on this repository MUST uphold the following invariants:

1. **Preserve Production Artifact Contracts:** Never break existing schemas defined in `docs/artifact_contracts.md` or `src/aegis/ingestion/contracts.py`. Evaluation code MUST consume production artifacts read-only or attach strictly optional telemetry hooks.
2. **Isolate Evaluation Modules:** Place all evaluation logic under `src/aegis/eval/` and expose a dedicated CLI entry point at `eval_pipeline.py`. Do not pollute core runtime modules (`ingestion/`, `geometry/`, `perception/`, `memory/`, `remote/`) with dataset-specific adapters or ground-truth parsing.
3. **Deterministic Reproducibility:** Every benchmark run, perturbation transform, and dataset split MUST accept an explicit integer `seed` (default `42`) and record git commit SHA, config hash, model checkpoint IDs, and hardware profile in `eval_report.json`.
4. **Tiered Execution Profiles:** Strictly decouple fast, CPU-safe regression checks (CI-runnable on `tests/fixtures/`) from GPU-intensive Modal or extrinsic benchmark runs so `.github/workflows/ci.yml` remains fast and deterministic.
5. **Zero Data Leakage:** Extrinsic dataset evaluations MUST run zero-shot (no fine-tuning on test scenes) and ingest raw frames through the same `video.py` / `keyframe.py` contract used in production—never via oracle keyframe injection unless explicitly labeled as an upper-bound oracle ablation.
6. **Panel-Ready Quantitative Outputs:** Every evaluation command MUST emit both machine-readable JSON (`eval_report.json`) and publication-ready Markdown/LaTeX summary tables with confidence intervals or percentile bounds ($\text{p50}$, $\text{p95}$, $\text{p99}$).

---

## 2. Subsystem-to-Metric Grounding Map

Use this mapping to trace every quantitative metric back to its exact source modules in the Aegis codebase.

| Pipeline Layer | Codebase Modules | Primary Quantitative Metrics | Evaluation Scope |
| :--- | :--- | :--- | :--- |
| **Ingestion & Keyframing** | `src/aegis/ingestion/video.py`, `keyframe.py`, `buffer.py`, `live_pipeline.py`, `live_handoff.py`, `contracts.py` | Sampling ratio $\rho$, max temporal/angular gap ($\Delta t_{\max}$, $\Delta \theta_{\max}$), frame drop rate ($\%$), blur rejection precision, chunk handoff latency ($\text{ms}$), contract compliance ($\%$) | Intrinsic + Live stress |
| **3D/4D Visual Geometry** | `src/aegis/geometry/vggt_runner.py`, `backproject.py`, `transforms.py` | $\text{ATE}_{\text{RMSE}}$ ($\text{m}$), $\text{RPE}_{\text{trans}}$ ($\text{m}$), $\text{RPE}_{\text{rot}}$ ($\text{deg}$), depth $\text{AbsRel}$, Chamfer Distance ($\text{cm}$), sliding-window scale drift ($\%$ per $10\text{ m}$) | Extrinsic (ScanNet, ADT) |
| **2D Perception & 3D Lifting** | `src/aegis/perception/detector.py`, `src/aegis/geometry/lifting.py` | 2D $\text{mAP}_{50:95}$, volume-stratified recall (Tiny/Medium/Large), 3D centroid error $e_{\text{pos}}$ ($\text{cm}$), $\text{IoU}_{3\text{D}}@0.25/0.50$, depth-bleed rate ($\%$) | Intrinsic + Extrinsic |
| **4D Scene Graph & Topology** | `src/aegis/memory/scene_graph.py`, `rooms.py`, `home_registry.py` | $\text{HOTA}$, $\text{IDF1}$, $\text{IDSW}/100\text{ kf}$, node duplication factor, relocation $\text{F1}$, $\Delta t_{\text{detect}}$, room $\text{ARI}/\text{NMI}$, cross-session re-localization ($\%$), longevity scaling | Multi-session + Extrinsic |
| **Reasoning & Retrieval** | `src/aegis/memory/reasoning.py` | $\text{Recall}@k$, $\text{MRR}$, $\text{tIoU}@0.3/0.5$, 3D grounding $\text{Acc}@0.5\text{ m}/1.0\text{ m}$, room-match accuracy, hallucination rate ($\%$), abstention $\text{F1}$, $\text{ECE}$ | Intrinsic + EgoLifeQA / Ego4D / OpenEQA |
| **Systems & Cloud Compute** | `run_pipeline.py`, `run_server.py`, `src/aegis/remote/modal_app.py`, `workers.py`, `api.py` | Per-stage latency ($\text{p50}/\text{p95}/\text{p99}$), Real-Time Factor ($\text{RTF}$), cold vs. warm container start ($\text{s}$), peak VRAM/RAM ($\text{GB}$), uplink bandwidth ($\text{KB/s}$), cost ($\$/\text{hr}$) | Systems profiling |
| **Privacy & Mobile UX** | `src/aegis/ingestion/live_storage.py`, `apps/mobile/lib/services/api_service.dart`, `patient_view.dart`, `caregiver_view.dart` | Raw-video local retention vs. egress ratio ($\%$), PII redaction precision/recall ($\%$), RBAC isolation pass rate ($\%$), mobile query RTT ($\text{ms}$), task time ($\text{s}$), $\text{SUS}$ score | Security audit + Pilot UX |

---

## 3. Formal Intrinsic Evaluation & Mathematical Specifications

Agents implementing `geometry_metrics.py`, `memory_metrics.py`, and `qa_metrics.py` MUST follow these exact mathematical definitions.

### 3.1 Ingestion & Live Stream Backpressure (`src/aegis/ingestion/`)
* **Keyframe Sampling Ratio:**
  $$\rho = \frac{N_{\text{kept}}}{N_{\text{total}}}$$
  Report alongside **Maximum Unobserved Temporal Gap** $\Delta t_{\max} = \max_i (t_{i+1} - t_i)$ (in seconds), **Maximum Unobserved Angular Gap** $\Delta \theta_{\max}$ (in degrees, when IMU/pose ground truth exists), and **Interaction-Event Miss Rate** (fraction of ground-truth pick/place intervals containing zero retained keyframes).
* **Backpressure & Drop Rate:** Inject synthetic streams into `buffer.py` and `live_pipeline.py` at $15\text{ FPS}$, $30\text{ FPS}$, and $60\text{ FPS}$ under artificial worker slowdown ($1\times$, $2\times$, $4\times$). Record dropped-frame percentage, peak queue depth, and chunk handoff latency (`live_handoff.py`).
* **Contract Fuzzing:** Feed truncated chunks, empty detection frames, corrupt timestamps, and schema boundary cases into `contracts.py` validators; require $100\%$ deterministic pass or structured rejection (zero unhandled exceptions).

### 3.2 3D/4D Geometry & Lifting (`src/aegis/geometry/` & `src/aegis/perception/`)
* **Absolute Trajectory Error ($\text{ATE}_{\text{RMSE}}$):** Align predicted camera translations $\{\hat{\mathbf{t}}_i\}_{i=1}^N$ to metric ground truth $\{\mathbf{t}_i^{\text{gt}}\}_{i=1}^N$ via $\text{Sim}(3)$ Umeyama alignment $(s, \mathbf{R}, \mathbf{t}_0)$:
  $$\text{ATE}_{\text{RMSE}} = \sqrt{\frac{1}{N} \sum_{i=1}^{N} \left\| \mathbf{t}_i^{\text{gt}} - \left(s\mathbf{R}\hat{\mathbf{t}}_i + \mathbf{t}_0\right) \right\|_2^2}$$
* **Relative Pose Error ($\text{RPE}$):** Over fixed stride $\Delta$ keyframes, compute translational drift (meters) and rotational drift (degrees) of relative transforms $\mathbf{E}_i = (\mathbf{Q}_i^{-1}\mathbf{Q}_{i+\Delta})^{-1}(\mathbf{P}_i^{-1}\mathbf{P}_{i+\Delta})$.
* **Sliding-Window Scale Drift:** Measure percentage change in local Umeyama scale factor $s_w$ across consecutive VGGT windows normalized by path length $L$:
  $$\text{ScaleDrift} = \frac{|s_{w+1} - s_w|}{s_w} \cdot \frac{10\text{ m}}{\Delta L_w} \times 100\%$$
* **Depth Accuracy:** Compute $\text{AbsRel} = \frac{1}{|M|}\sum_{p \in M} \frac{|\hat{d}_p - d_p^{\text{gt}}|}{d_p^{\text{gt}}}$ over valid depth pixels $M$ after median scaling (for monocular relative depth) or raw (for metric depth).
* **3D Reconstruction Accuracy (Chamfer Distance):** Bidirectional point-to-point distance between reconstructed point cloud $\hat{\mathcal{P}}$ and ground-truth surface sample $\mathcal{P}^{\text{gt}}$ (in cm):
  $$\text{CD}(\hat{\mathcal{P}}, \mathcal{P}^{\text{gt}}) = \frac{1}{|\hat{\mathcal{P}}|}\sum_{\hat{\mathbf{x}} \in \hat{\mathcal{P}}} \min_{\mathbf{y} \in \mathcal{P}^{\text{gt}}} \|\hat{\mathbf{x}} - \mathbf{y}\|_2 + \frac{1}{|\mathcal{P}^{\text{gt}}|}\sum_{\mathbf{y} \in \mathcal{P}^{\text{gt}}} \min_{\hat{\mathbf{x}} \in \hat{\mathcal{P}}} \|\mathbf{y} - \hat{\mathbf{x}}\|_2$$
* **3D Object Lifting Metrics (`lifting.py`):**
  * **Centroid Error:** $e_{\text{pos}} = \|\hat{\mathbf{c}} - \mathbf{c}^*\|_2$ (report median and $\text{p90}$ in cm).
  * **Volumetric 3D IoU:** $\text{IoU}_{3\text{D}} = \frac{\text{Vol}(\hat{B} \cap B^*)}{\text{Vol}(\hat{B} \cup B^*)}$, reporting $\text{mAP}@0.25$ and $\text{mAP}@0.50$.
  * **Depth-Bleed Rate:** Fraction of backprojected 3D points assigned to an object mask that fall $> 5\text{ cm}$ outside the ground-truth object bounding box/mesh.
* **Physical Volume-Stratified Recall (`detector.py`):** Partition ground-truth objects into three bins:
  * *Tiny:* $V < 0.002\text{ m}^3$ (keys, pill bottles, rings, earbuds)
  * *Medium:* $0.002\text{ m}^3 \le V \le 0.05\text{ m}^3$ (mugs, phones, eyeglasses, wallets)
  * *Large:* $V > 0.05\text{ m}^3$ (backpacks, chairs, laptops, appliances)

### 3.3 4D Scene Graph, Room Topology & Longevity (`src/aegis/memory/`)
* **Multi-Session Object Association (`scene_graph.py`):**
  * Compute $\text{HOTA}$, $\text{IDF1}$, and **ID-Switch Rate** ($\text{IDSW}$ normalized per $100$ keyframes) using Hungarian matching on 3D centroid distance ($\tau = 0.5\text{ m}$) + semantic class match.
  * **Node Duplication Factor:** $\text{NDF} = \frac{N_{\text{predicted\_nodes}}}{N_{\text{unique\_gt\_objects}}}$ (ideal $= 1.00$).
* **Relocation & State-Change Detection:**
  * On paired trajectories where an object moves $A \rightarrow B$ across time or sessions, report **Relocation $\text{F1}$** and **Temporal Detection Lag**:
    $$\Delta t_{\text{detect}} = t_{\text{graph\_update}} - t_{\text{physical\_move}}$$
* **Topological Room Clustering (`rooms.py`, `home_registry.py`):**
  * Evaluate predicted room labels against ground-truth room IDs using **Adjusted Rand Index ($\text{ARI}$)** and **Normalized Mutual Information ($\text{NMI}$)**.
  * Measure **Cross-Session Re-Localization Success Rate ($\%$):** Percentage of returning sessions that align to the persisted `home_registry.py` map within $0.5\text{ m}$ translation and $10^{\circ}$ yaw error.
* **Longevity & Compaction Scaling Benchmark:**
  * Replay/synthesize continuous recording horizons at $10\text{ min}$, $1\text{ hr}$, $6\text{ hrs}$, $24\text{ hrs}$, and $7\text{ days}$.
  * Record `r4d_scene_graph.json` serialized size ($\text{MB}$), active node/edge counts, peak RAM ($\text{MB}$), and graph query latency ($\text{ms}$).
  * Fit empirical growth exponent $\alpha$ in $\text{Size}(T) \propto T^{\alpha}$ to prove sub-linear memory growth ($\alpha \ll 1$) driven by spatio-temporal deduplication rather than linear frame accumulation.

### 3.4 Spatio-Temporal Reasoning & Calibration (`src/aegis/memory/reasoning.py`)
Construct and evaluate a **5-Archetype Query Suite**:
1. **Last-Seen Localization:** *"Where did I leave my glasses?"*
2. **Episodic Temporal Ordering:** *"What did I place on the counter right before leaving the kitchen?"*
3. **Topological Containment:** *"Which room is my medication bottle in?"*
4. **Multi-Session State Delta:** *"Did my keys move since yesterday evening?"*
5. **Unanswerable / Adversarial Negative:** *"Where is my passport?"* (item never observed in the recording).

Compute two decoupled metric tiers:
* **Retrieval Tier (Graph/Keyframe Selection):** $\text{Recall}@1$, $\text{Recall}@3$, $\text{Recall}@5$, Mean Reciprocal Rank ($\text{MRR}$), and Temporal IoU ($\text{tIoU}@0.3$, $\text{tIoU}@0.5$).
* **End-to-End Answer Tier:**
  * **3D Grounding Accuracy:** $\text{Acc}@0.5\text{ m}$ and $\text{Acc}@1.0\text{ m}$ (predicted coordinate within radius of ground-truth object centroid).
  * **Room-Match Accuracy ($\%$):** Exact normalized match against ground-truth room label.
  * **Hallucination Rate ($\%$):** Fraction of Archetype-5 (unanswerable) queries where the system fabricates a location instead of abstaining.
  * **Abstention $\text{F1}$:** Harmonic mean of precision and recall on abstaining when evidence is absent or below confidence threshold.
  * **Expected Calibration Error ($\text{ECE}$):** Across $M = 10$ confidence bins $B_m$:
    $$\text{ECE} = \sum_{m=1}^{M} \frac{|B_m|}{n} \left| \text{acc}(B_m) - \text{conf}(B_m) \right|$$

---

## 4. Extrinsic Public Dataset Evaluation Adapters

To eliminate overfitting concerns on internal recordings (`demo01`, `demo03`, `demo04`, `Demo06-Self`), implement uniform adapters in `src/aegis/eval/datasets.py` that translate external datasets into a common `EvalEpisode` interface.

| Benchmark | Target Pipeline Stages | Ground-Truth Signals Consumed | Standard Validation Subset | Exact Panel Metrics |
| :--- | :--- | :--- | :--- | :--- |
| **EgoLife / EgoLifeQA** | End-to-end 4D memory + `reasoning.py` | Multi-day continuous egocentric streams + longitudinal QA pairs | $150$ multi-day QA pairs across $3\text{--}7$ day timelines | Multi-day QA Accuracy ($\%$), Cross-Day Persistence $\text{Recall}@1$, Memory growth ($\text{MB/day}$) |
| **Ego4D (NLQ & Goal-Step)** | `keyframe.py`, `scene_graph.py`, `reasoning.py` | Unscripted egocentric video + temporal query spans $[t_s, t_e]$ | $200$ stratified NLQ queries (object-centric subset) | $\text{R}@1\ (\text{tIoU}=0.3)$, $\text{R}@1\ (\text{tIoU}=0.5)$, $\text{R}@5\ (\text{tIoU}=0.3)$ |
| **ScanNet / ScanNet++ / ARKitScenes** | `vggt_runner.py`, `backproject.py`, `lifting.py`, `rooms.py` | Metric RGB-D camera poses, dense meshes, 3D oriented bboxes, room types | $20$ diverse multi-room indoor scans | $\text{ATE}_{\text{RMSE}}$ ($\text{m}$), Chamfer Distance ($\text{cm}$), 3D Box $\text{mAP}@0.25/0.50$, Room $\text{ARI}$ |
| **Ego-Exo4D / Aria Digital Twin (ADT)** | `vggt_runner.py`, `detector.py`, `lifting.py`, `scene_graph.py` | High-FPS egocentric video, 6-DoF head & object poses, hand-object events | $10$ multi-interaction indoor sequences | 3D Centroid Error $e_{\text{pos}}$ ($\text{cm}$), $\text{HOTA}$, $\text{IDSW}/100\text{ kf}$, State-Change $\text{F1}$ |
| **OpenEQA / SG3D** | `scene_graph.py`, `reasoning.py` | 3D indoor scenes + spatial relation & object-attribute QA pairs | $100$ object-localization & spatial-relation queries | Exact Spatial Accuracy ($\%$), LLM-Judge Match Score, Spatial Relation Precision (`on`/`in`/`next-to`) |

### Adapter Implementation Rules (`src/aegis/eval/datasets.py`)
1. **Coordinate Frame Normalization:** Convert all dataset camera conventions (OpenGL/OpenCV/ARKit/Aria) into Aegis's canonical world frame via `src/aegis/geometry/transforms.py` before computing $\text{ATE}$, $\text{IoU}_{3\text{D}}$, or centroid distances.
2. **Input Pipeline Parity:** Always pass external video or image sequences through `video.py` and `keyframe.py` at the production target resolution and FPS cap.
3. **Manifest Caching:** Store deterministic split manifests (scene IDs, clip timestamps, query IDs) in `src/aegis/eval/manifests/` so repeated runs evaluate identical subsets.

---

## 5. Systems Telemetry, Latency & Cost Economics

Instrument `run_pipeline.py`, `src/aegis/remote/workers.py`, `src/aegis/remote/modal_app.py`, and `src/aegis/remote/api.py` with a lightweight, zero-overhead-when-disabled `TelemetryCollector` context manager.

### 5.1 Stage-Level Latency & Throughput
Record wall-clock time ($\text{ms}$) across all 6 stages for every processed chunk and query, reporting $\text{p50}$, $\text{p95}$, and $\text{p99}$:
1. `stage_1_keyframe_extract` (`keyframe.py`)
2. `stage_2_perception_2d` (`detector.py`)
3. `stage_3_geometry_vggt` (`vggt_runner.py`)
4. `stage_4_lifting_3d` (`lifting.py`)
5. `stage_5_scene_graph_update` (`scene_graph.py`, `rooms.py`)
6. `stage_6_query_reasoning` (`reasoning.py`)

Compute the **Real-Time Factor ($\text{RTF}$)**:
$$\text{RTF} = \frac{T_{\text{total\_processing}}}{T_{\text{video\_duration}}}$$
Target threshold for live viability: $\text{RTF} < 1.0$.

### 5.2 Cloud Resource & Unit Economics (`modal_app.py`, `workers.py`)
* **Container Startup Profile:** Measure cold-start time vs. warm-container invocation latency ($\text{s}$), comparing standard image pull against Modal memory/model snapshots.
* **Memory Ceilings:** Log peak GPU VRAM ($\text{GB}$) via `torch.cuda.max_memory_allocated()` and peak host RSS ($\text{GB}$) across worker batch sizes $B \in \{4, 8, 16\}$ keyframes.
* **Network Egress & Unit Cost:**
  $$\text{Cost}_{\$/\text{hr}} = \text{RTF} \times R_{\text{GPU}\ (\$/\text{hr})} + \text{Storage}_{\$/\text{hr}} + \text{LLM\_Query\_Cost}$$
  Report average client uplink bandwidth ($\text{KB/s}$) of compressed keyframes alongside total indexing cost per hour of continuous video.

---

## 6. Ablation Study, Robustness Perturbations & Failure Taxonomy

### 6.1 Mandatory Five-Way Ablation Suite (`src/aegis/eval/ablations.py`)
Implement config override presets (compatible with `src/aegis/core/config.py`) so all five variants execute cleanly through the same `eval_pipeline.py` runner:

| Variant ID | Configuration Override | Purpose / Hypothesis Tested |
| :--- | :--- | :--- |
| `full_aegis` | Default production config | Full system reference across accuracy, latency, and cost |
| `no_smart_keyframe` | Replace `keyframe.py` with fixed $1\text{ Hz}$ uniform sampling | Quantifies compute savings, blur rejection, and node deduplication gain |
| `no_3d_lifting` | Disable `vggt_runner.py` + `lifting.py`; use 2D frame-level VLM embeddings | Proves necessity of 3D geometry for proximity, room containment, and viewpoint invariance |
| `no_room_topology` | Disable `rooms.py` and `home_registry.py` clustering | Isolates contribution of topological room priors to retrieval precision |
| `raw_vlm_baseline` | Bypass 4D scene graph; pass sampled frames directly to a long-context VLM | Demonstrates orders-of-magnitude cost/latency efficiency and long-horizon retention of the 4D graph |

### 6.2 Deterministic Visual Perturbation Suite (`src/aegis/eval/perturbations.py`)
Apply seeded transforms to clean input streams prior to ingestion and plot accuracy degradation curves against perturbation severity:
* **Motion Blur:** Linear directional kernel sizes $k \in \{0, 5, 11, 21\}\text{ px}$ at randomized angles (simulating rapid head turns).
* **Low-Light / Exposure Drop:** Gamma scaling $\gamma \in \{1.0, 1.8, 2.5\}$ + sensor read noise $\sigma \in \{0, 8, 16\}$ (simulating dim rooms/hallways).
* **Partial Occlusion:** Synthetic rectangular cutouts masking $30\%$, $50\%$, and $70\%$ of target object bounding box areas.
* **Identical-Instance Clutter:** Multi-instance scenes containing $\ge 3$ visually identical distractors (e.g., identical mugs in different rooms) to verify metric-spatial disambiguation over appearance-only matching.

### 6.3 Root-Cause Failure Taxonomy
Implement an automated error-attribution pass in `runner.py` (with manual audit export for $n = 100$ sampled failures) classifying $100\%$ of failed queries into mutually exclusive root causes:
1. `PERCEPTION_MISS`: Target object never detected in 2D (`detector.py`) on any frame where it is visible.
2. `GEOMETRY_LIFT_ERROR`: Detected in 2D, but lifted 3D centroid error $e_{\text{pos}} > 0.5\text{ m}$ due to depth bleed or VGGT drift.
3. `ASSOCIATION_ID_SPLIT`: Correctly lifted, but fragmented into duplicate nodes or overwritten by stale observations (`scene_graph.py`).
4. `TOPOLOGY_MISASSIGN`: Correct object node exists, but assigned to wrong room cluster (`rooms.py`).
5. `REASONING_HALLUCINATION`: Correct node and room retrieved, but `reasoning.py` produced an inaccurate temporal/spatial answer or failed to abstain.

---

## 7. Privacy Auditing & Mobile Client UX Evaluation

### 7.1 Privacy & Access Control Verification
* **Data Minimization Ratio (`live_storage.py`, `workers.py`):** Measure percentage of raw captured bytes retained strictly on-device vs. ephemeral keyframes/embeddings transmitted remotely.
* **PII Redaction Audit:** Run a labeled test set containing human faces, screens, and paper documents through any pre-egress redaction stage; report redaction precision and recall ($\%$).
* **RBAC Isolation Suite (`tests/test_api.py`):** Automated API tests asserting:
  * Patient-scoped tokens receive `403 Forbidden` on caregiver configuration endpoints.
  * Cross-tenant queries against another user's `home_registry.py` namespace return zero leaked records.

### 7.2 Mobile Client Latency & Human Pilot Protocol (`apps/mobile/`)
* **Client-Side RTT Instrumentation (`apps/mobile/lib/services/api_service.dart`):** Measure end-to-end query round-trip time from user submission (`patient_view.dart`) to rendered `query_result.dart` / `timeline_event.dart` widget ($\text{p50}$, $\text{p95}$ in ms) over Wi-Fi and throttled 4G profiles.
* **Controlled Scavenger-Hunt User Study ($n = 8\text{--}12$ participants):**
  1. Record a $15$-minute multi-room walkthrough placing $10$ everyday target items (including Tiny, Medium, and Large classes).
  2. Have participants locate all $10$ items in randomized order under two conditions: **Aegis-Assisted** vs. **Unaided Recall/Search**.
  3. Record **Time-to-Locate ($\text{s}$)**, **Task Success Rate ($\%$)**, **Queries per Item**, and post-session **System Usability Scale ($\text{SUS}$, $0\text{--}100$)** score.

---

## 8. Canonical Data Contracts for `src/aegis/eval/`

Agents MUST implement these Pydantic models in `src/aegis/eval/schemas.py` to keep fixtures, extrinsic adapters, and report generators strictly typed.

### 8.1 Fixture Ground-Truth Annotation Schema (`gt_annotations.json`)
Place alongside existing fixtures (`tests/fixtures/demo01/`, `demo03/`, `demo04/`, `Demo06-Self/`):

```json
{
  "schema_version": "1.0.0",
  "dataset_id": "demo04",
  "coordinate_frame": "aegis_world_meters",
  "rooms": [
    {
      "room_id": "kitchen",
      "polygon_xy": [[0.0, 0.0], [4.2, 0.0], [4.2, 3.5], [0.0, 3.5]]
    }
  ],
  "objects": [
    {
      "gt_object_id": "obj_keys_01",
      "label": "keys",
      "volume_bin": "tiny",
      "states": [
        {
          "t_start_s": 0.0,
          "t_end_s": 142.5,
          "room_id": "kitchen",
          "centroid_xyz": [1.45, 0.82, 0.91],
          "bbox_size_xyz": [0.09, 0.05, 0.02]
        },
        {
          "t_start_s": 142.5,
          "t_end_s": 300.0,
          "room_id": "living_room",
          "centroid_xyz": [5.10, 1.20, 0.48],
          "bbox_size_xyz": [0.09, 0.05, 0.02]
        }
      ]
    }
  ],
  "queries": [
    {
      "query_id": "q_001",
      "archetype": "last_seen_localization",
      "prompt": "Where did I leave my keys?",
      "query_time_s": 280.0,
      "answerable": true,
      "expected_gt_object_id": "obj_keys_01",
      "expected_room_id": "living_room",
      "expected_centroid_xyz": [5.10, 1.20, 0.48],
      "expected_temporal_span_s": [142.5, 280.0]
    },
    {
      "query_id": "q_002",
      "archetype": "unanswerable_negative",
      "prompt": "Where is my passport?",
      "query_time_s": 280.0,
      "answerable": false
    }
  ]
}
```

### 8.2 Unified Evaluation Report Schema (`eval_report.json`)
```json
{
  "run_metadata": {
    "timestamp_utc": "2026-11-19T15:15:00Z",
    "git_commit": "<sha>",
    "seed": 42,
    "suite": "full",
    "ablation_variant": "full_aegis",
    "hardware": {"gpu": "L40S", "vram_gb": 48}
  },
  "ingestion": {"sampling_ratio": 0.11, "drop_rate_pct": 0.0, "max_temporal_gap_s": 1.2},
  "geometry": {"ate_rmse_m": 0.08, "rpe_trans_m": 0.02, "scale_drift_pct_per_10m": 1.4, "chamfer_cm": 3.1},
  "perception_lifting": {"map_50_95": 0.64, "centroid_err_median_cm": 9.5, "iou3d_25": 0.71, "recall_by_volume": {"tiny": 0.68, "medium": 0.86, "large": 0.94}},
  "memory_topology": {"hota": 0.76, "idf1": 0.81, "idsw_per_100kf": 1.2, "node_duplication_factor": 1.08, "relocation_f1": 0.88, "room_ari": 0.84},
  "reasoning_qa": {"recall_at_1": 0.85, "mrr": 0.89, "acc_0_5m": 0.80, "hallucination_rate_pct": 4.0, "abstention_f1": 0.93, "ece": 0.045},
  "systems": {"rtf": 0.34, "stage_latency_ms": {}, "peak_vram_gb": 11.2, "cost_usd_per_hr": 0.42},
  "failure_taxonomy_pct": {"PERCEPTION_MISS": 34.0, "GEOMETRY_LIFT_ERROR": 22.0, "ASSOCIATION_ID_SPLIT": 18.0, "TOPOLOGY_MISASSIGN": 11.0, "REASONING_HALLUCINATION": 15.0}
}
```

---

## 9. Target Package Architecture & Phased Implementation Checklist

### 9.1 Target File Layout
```text
src/aegis/eval/
├── __init__.py
├── schemas.py           # Pydantic models: GTAnnotations, EvalEpisode, StageTelemetry, EvalReport
├── telemetry.py         # Wall-clock, VRAM/RAM, bandwidth, and Modal cost profiler
├── geometry_metrics.py  # Umeyama Sim(3) ATE/RPE, AbsRel, Chamfer Distance, 3D IoU, depth bleed
├── memory_metrics.py    # HOTA, IDF1, IDSW, NDF, relocation F1, Room ARI/NMI, longevity scaling
├── qa_metrics.py        # Recall@k, MRR, tIoU, Acc@0.5m/1.0m, hallucination rate, abstention F1, ECE
├── datasets.py          # Adapters: FixtureAdapter, EgoLifeAdapter, Ego4DAdapter, ScanNetAdapter, ADTAdapter, OpenEQAAdapter
├── perturbations.py     # Seeded motion blur, gamma/noise low-light, occlusion cutouts
├── ablations.py         # Config override presets (5-way ablation matrix)
├── taxonomy.py          # Automated failure attribution + manual audit CSV/JSON exporter
├── reporting.py         # Exports eval_report.json, Markdown tables, LaTeX tables, and Rerun overlays
├── manifests/           # Deterministic split ID lists for external datasets
└── runner.py            # Orchestrator binding adapters, pipeline execution, metrics, and reporting
eval_pipeline.py         # CLI entry point (--suite, --ablation, --perturbation, --seed, --output-dir)
tests/test_eval_metrics.py  # Unit tests verifying every metric on synthetic ground-truth edge cases
```

### 9.2 Phased Execution Plan for Agents

#### Phase 1: Core Schemas, Metrics & Unit Tests (CPU-Only)
- [ ] Implement `schemas.py`, `geometry_metrics.py`, `memory_metrics.py`, `qa_metrics.py`, and `telemetry.py`.
- [ ] Write `tests/test_eval_metrics.py` testing analytical known-answer cases (e.g., exact $\text{Sim}(3)$ transform yields $\text{ATE} = 0$, perfect cluster permutation yields $\text{ARI} = 1.0$, calibrated probabilities yield $\text{ECE} = 0.0$).
- [ ] **Verification:** `uv run pytest tests/test_eval_metrics.py` passes $100\%$.

#### Phase 2: Fixture Ground Truth, CLI Runner & CI Regression Gate
- [ ] Create `gt_annotations.json` for `tests/fixtures/demo01`, `demo03`, `demo04`, and `Demo06-Self` (minimum $25$ stratified queries across all 5 archetypes per fixture).
- [ ] Implement `runner.py`, `reporting.py`, and `eval_pipeline.py`.
- [ ] Add a `fixture-fast` evaluation job to `.github/workflows/ci.yml` that fails PRs if $\text{Recall}@1$ drops $> 3\%$, $\text{IDSW}$ increases $> 3\%$, or $\text{p95}$ query latency regresses $> 10\%$ against a committed baseline JSON.
- [ ] **Verification:** `uv run python eval_pipeline.py --suite fixture-fast --output-dir artifacts/eval_ci` emits valid `eval_report.json` and `summary.md`.

#### Phase 3: Systems Profiling, Ablations & Perturbations
- [ ] Wire optional `TelemetryCollector` hooks into `run_pipeline.py` and `src/aegis/remote/workers.py`.
- [ ] Implement `ablations.py` (5-way matrix) and `perturbations.py` (blur, low-light, occlusion).
- [ ] Add a longevity stress script simulating $10\text{ min} \rightarrow 7\text{ day}$ graph growth against `scene_graph.py`.
- [ ] **Verification:** `uv run python eval_pipeline.py --suite ablations --dataset demo04` produces a complete 5-row comparison table.

#### Phase 4: Extrinsic Dataset Adapters & Visual Error Proof
- [ ] Implement dataset adapters in `datasets.py` starting with **ScanNet** (geometry + rooms) and **Ego4D-NLQ / EgoLifeQA** (longitudinal memory + QA), followed by **Aria Digital Twin** and **OpenEQA**.
- [ ] Extend Rerun visualization (`scripts/patch_demo06_rrd.py` / `reporting.py`) to log ground-truth vs. predicted 3D bounding boxes and centroid error vectors into `.rrd` files for panel live demos.
- [ ] Add automated privacy/RBAC checks to `tests/test_api.py` and mobile RTT logging to `apps/mobile/lib/services/api_service.dart`.
- [ ] **Verification:** Run full panel report generation and verify all LaTeX/Markdown tables render cleanly with zero `NaN` or missing fields.