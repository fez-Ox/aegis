# Aegis — Proposal Defense POC Implementation Plan

## 1. POC Objective

Build a deterministic, polished proof-of-concept for **Aegis: an egocentric monocular spatio-temporal memory system**.

The POC should demonstrate, end-to-end:

> **Monocular egocentric video → camera trajectory + depth → persistent object identities → relative 3D object states → temporal memory → 3D/4D visualization → spatial-temporal retrieval**

The POC is **not** intended to solve the full Aegis scope. The proposal defense should establish technical feasibility of the core research idea, especially FR1–FR3, with an early prototype of FR5/FR7.

### Primary defense claim

> Aegis can transform a monocular first-person video stream into a persistent, queryable spatio-temporal memory in which objects retain identity and their spatial state can be inspected across time.

Do **not** make metric-global 4D reconstruction the central claim. The system should use relative/anchor-based spatial representations wherever monocular scale or global alignment is unreliable.

---

## 2. Recommended POC Experience

Use one **1–3 minute prerecorded egocentric video** in a controlled indoor environment. Deliberately move a few recognizable objects.

Example sequence:

1. User starts at a desk.
2. Mug is visible on desk.
3. User picks up mug.
4. User walks to kitchen/counter.
5. User places mug on counter.
6. User returns to desk.
7. User optionally moves keys or a bottle as a second object.

The final demo should show:

- Original egocentric video.
- 3D scene / point cloud or surfel representation.
- Camera trajectory.
- Persistent object IDs.
- Object positions/relations over time.
- Timeline scrubber.
- Natural-language query.
- Highlighted object and supporting video frame(s).

### Target demonstration questions

Minimum:

- `Where is the mug?`
- `Where was the mug before it was moved?`
- `Where did I leave the mug?`

Stretch:

- `What was next to the mug when it was on the desk?`
- `When did the mug move from the desk?`
- `Where was the blue bottle after I left the kitchen?`

---

## 3. Architecture

```text
                        EGOCENTRIC RGB VIDEO
                                  |
                                  v
                        Frame sampling / sync
                                  |
              +-------------------+-------------------+
              |                                       |
              v                                       v
      Camera / Depth Frontend                  Object Perception
      - monocular depth                         - open-vocab detection
      - camera poses / VO                       - segmentation
      - image features                          - tracking
              |                                       |
              +-------------------+-------------------+
                                  v
                         3D Object Lifting
                                  |
                                  v
                       Persistent Identity Layer
                                  |
                                  v
                       Relative 4D Memory Graph
                    +-------------+-------------+
                    |                           |
                    v                           v
             3D/4D Visualization          Query / Retrieval
                    |                           |
                    +-------------+-------------+
                                  |
                                  v
                         Evidence / Answer
```

### Core representation

Use an object-centric memory rather than storing every frame as the primary memory.

Conceptually:

```text
ObjectMemory {
    object_id
    canonical_label
    aliases
    appearance_embedding
    observations[]
    first_seen
    last_seen
    current_state
    anchor_relations[]
}

Observation {
    timestamp
    frame_id
    camera_pose
    position_3d
    bbox_2d
    mask
    anchor_id
    relation_to_anchor
    evidence_frame
}
```

Represent important transitions as:

```text
Mug #17
    t=14.2s  -- on --> Desk
    t=26.1s  -- held_by --> User
    t=41.7s  -- on --> Kitchen Counter
```

This follows the useful design direction of relative 4D scene memory: stable anchors + persistent object identities + anchor-relative temporal transitions. R4DSG explicitly uses this idea for monocular egocentric video. `https://arxiv.org/abs/2608.11017`

---

## 4. Concrete Technology Stack

### 4.1 Language/runtime

**Python 3.12**

Reason:
- best ecosystem coverage for vision models;
- easiest integration between PyTorch, OpenCV, Transformers and visualization;
- fast iteration for an FYP POC.

Use:

- `uv` for environment/package management.
- `PyTorch` as the ML runtime.
- `OpenCV` for video/frame processing.
- `NumPy` for geometry and numerical operations.
- `SciPy` for geometric utilities where required.

### 4.2 Hardware

Primary development:

- NVIDIA GPU with at least **12 GB VRAM** recommended.
- RTX 3080 10 GB can be used with reduced frame resolution/model sizes.
- 16–24 GB VRAM is preferable for running depth + segmentation + vision-language components together.

Fallback:

- Precompute expensive perception outputs offline.
- Run the viewer and memory/retrieval pipeline interactively from cached artifacts.

### 4.3 Video ingestion

Use:

- `OpenCV VideoCapture`
- optional `ffmpeg` preprocessing.

Store a normalized dataset format inside the PoC workspace:

```text
poc/data/
  demo01/
    video.mp4
    frames/
    metadata.json
```

Metadata:

```json
{
  "fps": 30,
  "sample_fps": 5,
  "resolution": [1280, 720],
  "duration_sec": 82.4
}
```

Do not run the entire pipeline at native camera FPS for the defense POC. Start with **3–5 FPS sampled frames**.

### 4.4 Monocular depth

Recommended first choice:

**Depth Anything V2** (metric or relative depth variant appropriate to the use case).

Use it primarily for:

- per-frame depth;
- approximate 3D lifting;
- local spatial relationships.

Implementation:

- Hugging Face Transformers where a supported checkpoint is available;
- otherwise the official Depth Anything V2 implementation.

Important design decision:

> Treat depth as locally useful geometry, not guaranteed globally metric truth.

Fuse relative geometry around local anchors instead of asserting centimeter-accurate global coordinates.

### 4.5 Camera pose / visual odometry

Preferred implementation path for POC:

**DROID-SLAM** or another strong monocular SLAM/visual odometry system with usable pretrained inference.

Use it to obtain:

```text
T_world_camera[t]
```

for each sampled frame.

Fallback if integration becomes unstable:

- use an offline monocular VO package;
- or use a benchmark/dataset sequence that already provides camera trajectory for initial validation;
- keep all camera poses behind one `PoseProvider` interface so the rest of Aegis is independent of the frontend.

Do not build your own SLAM implementation for the POC.

### 4.6 Object detection / segmentation

Primary choice:

**YOLO-World / YOLOE + SAM 2** style pipeline.

Recommended division of labor:

1. Open-vocabulary detector proposes object instances.
2. SAM 2 generates/refines masks and propagates them temporally.
3. A tracker assigns short-term track IDs.

Start with a closed list of known demo objects if necessary:

```text
mug
laptop
keys
bottle
chair
desk
counter
```

Then add open-vocabulary capability after the core pipeline works.

### 4.7 Multi-object tracking

Use **ByteTrack/BoT-SORT** for the first implementation.

The tracker should provide:

```text
track_id
bbox
confidence
frame_id
```

Do not treat tracker IDs as persistent memory IDs. Tracker IDs are temporary.

### 4.8 Persistent object identity

Implement an Aegis-specific identity layer above the short-term tracker.

For each track, compute:

- CLIP/DINO-family appearance embedding;
- semantic class label;
- color/appearance metadata;
- 3D position;
- spatial proximity to known anchors.

Associate a new track with an existing memory object when:

```text
semantic similarity high
AND
appearance similarity high
AND/OR
spatial/temporal consistency high
```

A simple weighted score is sufficient for the POC:

```text
score =
    0.40 * appearance_similarity +
    0.25 * semantic_similarity +
    0.20 * spatial_consistency +
    0.15 * temporal_consistency
```

Make these weights configurable.

### 4.9 3D lifting

For each object mask:

1. collect depth values inside the mask;
2. reject invalid/outlier depth;
3. back-project pixels to camera coordinates;
4. transform points using camera pose;
5. compute robust object center / bounding representation.

Basic back-projection:

```text
X = (u - cx) * Z / fx
Y = (v - cy) * Z / fy
Z = depth(u,v)
```

Then:

```text
P_world = T_world_camera * P_camera
```

For the POC, do not try to reconstruct watertight meshes for every object. Use:

- point clouds;
- oriented 3D boxes;
- object centroids;
- sparse Gaussian/surfel-like points.

### 4.10 Spatial anchors

Introduce stable scene anchors:

```text
desk
counter
door
sofa
cabinet
room
```

Anchor position can be estimated from aggregated observations.

Dynamic objects are stored **relative to anchors**:

```text
Mug #17
    anchor = desk
    relative_position = [dx, dy, dz]
```

When the mug moves:

```text
Mug #17
    t1 -> desk-relative
    t2 -> user-held
    t3 -> counter-relative
```

This is the key mechanism that makes the representation robust to imperfect monocular global scale/alignment.

### 4.11 Memory store

For the POC, avoid introducing a heavy distributed database.

Use:

- **SQLite** for structured memory/event records.
- **JSON/JSONL** for serialized observations and debugging.
- **FAISS** for optional embedding retrieval.

Suggested schema:

```text
objects
--------
id
label
description
first_seen
last_seen
embedding_path

observations
------------
id
object_id
timestamp
frame_id
anchor_id
x
y
z
bbox
confidence

relations
---------
id
subject_id
relation
object_id
start_time
end_time
confidence

events
------
id
start_time
end_time
type
participants
summary
```

### 4.12 Visualization

Recommended: **Rerun**.

Reason:

- designed for logging/visualizing multimodal spatial data;
- supports 3D views, timelines, images, trajectories and text;
- DAAAM itself uses Rerun for visualization, making it a particularly suitable choice for this POC.

Use Rerun as the core technical viewer, optionally wrapped by a lightweight web UI.

Suggested panels:

```text
+----------------------+------------------------------------+
| Egocentric Video     | 3D / 4D Memory                     |
|                      |                                    |
| [current frame]      | point cloud / objects / trajectory |
|                      |                                    |
+----------------------+------------------------------------+
| Timeline             | Memory / Query                      |
| ----●-----------     | Query: Where was the mug?          |
| 00:00       01:20    | Answer + evidence                  |
+----------------------+------------------------------------+
```

### 4.13 User interface

Keep the UI thin.

Recommended:

- **Gradio** or **Streamlit** for initial interaction layer;
- embed/launch the Rerun viewer separately or through the browser.

Do not spend POC time building a polished React frontend unless the rest of the pipeline is already stable.

### 4.14 Query engine

Do not start with an autonomous LLM agent.

Implement deterministic structured query translation first.

Pipeline:

```text
User question
     |
     v
LLM / parser
     |
     v
Structured query
     |
     v
SQLite / FAISS retrieval
     |
     v
Top memory events
     |
     v
Evidence frames + 3D entities
     |
     v
Answer generator
```

Example structured query:

```json
{
  "entity": "mug",
  "attribute": "location",
  "time": {"type": "last_observed"}
}
```

For a temporal query:

```json
{
  "entity": "mug",
  "operation": "previous_location"
}
```

The LLM should only interpret/generate language. Spatial-temporal facts must come from the memory store.

This separation is important for defense: it prevents the system from appearing to merely hallucinate an answer from the video.

---

## 5. Repository Structure

The runnable geometry demonstration lives in its own workspace. This keeps
large local inputs, generated artifacts, experiment configuration, and
proposal-defense notes together without mixing them into the future product
implementation.

```text
Aegis/
├── README.md
├── pyproject.toml
├── poc/
│   ├── README.md
│   ├── config/
│   │   └── demo.yaml
│   ├── data/
│   │   └── demo01/                 # local inputs; ignored by git
│   ├── docs/
│   │   └── implementation-plan.md
│   ├── outputs/                    # generated/downloaded artifacts; ignored
│   └── run_pipeline.py             # Modal entrypoint
├── src/aegis/
│   └── poc/
│       ├── core/
│       ├── geometry/
│       ├── ingestion/
│       ├── remote/
│       └── visualization/
├── examples/
│   └── modal/
└── poc/tests/
```

---

## 6. Implementation Phases

## Phase 0 — Environment and Data Contract

### Goal
Make the project reproducible before implementing perception.

### Tasks

- Create Python 3.12 environment with `uv`.
- Install PyTorch/CUDA.
- Install OpenCV, NumPy, SciPy, Transformers.
- Install Rerun.
- Define common data classes:
  - `Frame`
  - `Pose`
  - `Detection`
  - `Mask`
  - `Track`
  - `ObjectObservation`
  - `MemoryObject`
  - `MemoryEvent`
- Create YAML configuration under `poc/config/`.
- Record one clean egocentric demo sequence under `poc/data/`.

### Exit criterion
A command such as:

```bash
uv run modal run poc/run_pipeline.py --config-path poc/config/demo.yaml --stage preprocess
```

produces normalized frames and metadata.

---

## Phase 1 — Monocular Geometry Frontend

### Goal
Demonstrate that monocular video can be converted into a moving-camera spatial representation.

### Tasks

1. Run monocular depth on sampled frames.
2. Run monocular VO/SLAM to obtain camera poses.
3. Back-project sampled frames into 3D.
4. Transform points into a common coordinate frame.
5. Visualize point cloud + camera trajectory in Rerun.

### Output

```text
poc/outputs/demo01/geometry/
    poses.json
    depth/
    pointcloud.ply
```

### Exit criterion
A viewer shows:

- recognizable room geometry;
- continuous camera trajectory;
- visually coherent local 3D structure.

This is the **first standalone POC milestone**.

---

## Phase 2 — Object Perception

### Goal
Attach semantic entities to the 3D representation.

### Tasks

1. Run detector.
2. Generate masks.
3. Track objects across neighboring frames.
4. Lift masks into 3D.
5. Visualize object centers/boxes with labels.

### Exit criterion
The viewer can show:

```text
Mug #3
Laptop #1
Chair #2
Desk #1
```

at approximately correct locations.

Do not implement persistent identity yet beyond short-term tracking.

---

## Phase 3 — Persistent Object Memory

### Goal
Turn tracks into persistent episodic entities.

### Tasks

1. Implement object embeddings.
2. Implement track-to-memory association.
3. Assign persistent IDs.
4. Introduce stable anchors.
5. Convert observations to anchor-relative states.
6. Persist objects/events in SQLite.

### Exit criterion
The same mug seen before and after an occlusion/movement is represented as:

```text
Mug #17
```

rather than:

```text
Mug Track 4
Mug Track 12
```

---

## Phase 4 — Temporal Memory and 4D Visualization

### Goal
Make temporal evolution explicit.

### Tasks

- Store timestamps on every observation.
- Detect location/state transitions.
- Create event intervals.
- Add timeline-based rendering.
- Render historical object positions.
- Highlight current vs historical locations.

Example event:

```text
EVENT 07
--------------------------------
Object: Mug #17
From: Desk
To: Kitchen Counter
Start: 00:24.1
End: 00:42.8
Evidence: frames 361–642
```

### Exit criterion
Scrubbing the timeline changes the visible state of the memory.

This is the **main 4D-memory defense milestone**.

---

## Phase 5 — Queryable Memory

### Goal
Demonstrate that the representation is useful rather than merely visual.

### Tasks

1. Implement a small structured query DSL.
2. Implement question → structured query parsing.
3. Retrieve relevant object/event records.
4. Return supporting frames and timestamps.
5. Highlight the result in Rerun.
6. Generate a short grounded answer.

### Initial supported query classes

```text
LOCATION(entity)
LAST_LOCATION(entity)
PREVIOUS_LOCATION(entity)
WHEN_MOVED(entity)
NEAR(entity_a, entity_b)
WHAT_WAS_AT(location, time)
```

### Exit criterion
At least five scripted natural-language questions return correct answers and evidence.

---

## Phase 6 — Defense Demo Polish

### Goal
Make the POC reliable and understandable in a live defense.

### Tasks

- Precompute the demo pipeline.
- Cache all expensive outputs.
- Add loading/progress screens.
- Add clear labels and timestamps.
- Add 5–10 scripted questions.
- Add one replay sequence.
- Add fallback screenshots/video in case live rendering fails.
- Prepare a one-command launcher.

### Defense launcher

```bash
uv run modal run poc/run_pipeline.py --config-path poc/config/demo.yaml --stage all
```

The launcher should:

1. open the video;
2. load the precomputed 4D memory;
3. open the Rerun viewer;
4. open the query UI.

---

## 7. Suggested POC Milestones

### Milestone A — Spatial reconstruction

Input:

```text
video.mp4
```

Output:

```text
camera trajectory + 3D point cloud
```

Demonstrates feasibility of FR1–FR3 at the geometric level.

### Milestone B — Object-aware reconstruction

Output:

```text
3D scene + semantic objects + track IDs
```

### Milestone C — Persistent 4D memory

Output:

```text
object identities + spatial states + timestamps + transitions
```

### Milestone D — Memory retrieval

Input:

```text
"Where was the mug before it was moved?"
```

Output:

```text
Desk, 00:24
Evidence frame 381
3D highlight: Mug #17
```

This is the version to present at the proposal defense.

---

## 8. What NOT to Build for the First POC

Do not spend initial development time on:

- real-time end-to-end processing;
- custom SLAM;
- custom detector training;
- photorealistic 4D rendering;
- neural radiance fields;
- full 4D Gaussian splatting;
- distributed databases;
- speech recognition;
- caregiver authentication;
- mobile deployment;
- complex autonomous agents;
- long-horizon autonomous planning.

These are later research/product components, not prerequisites for proving the core idea.

---

## 9. Important Engineering Abstractions

Keep interfaces modular so individual research components can be replaced.

### `DepthProvider`

```python
class DepthProvider:
    def predict(self, frame) -> np.ndarray:
        ...
```

### `PoseProvider`

```python
class PoseProvider:
    def estimate(self, frames) -> list[Pose]:
        ...
```

### `ObjectPerceptor`

```python
class ObjectPerceptor:
    def detect(self, frame) -> list[Detection]:
        ...
```

### `IdentityManager`

```python
class IdentityManager:
    def update(self, tracks, geometry) -> list[MemoryObject]:
        ...
```

### `MemoryStore`

```python
class MemoryStore:
    def add_observation(self, observation):
        ...

    def add_event(self, event):
        ...

    def query(self, structured_query):
        ...
```

### `QueryEngine`

```python
class QueryEngine:
    def answer(self, question: str):
        ...
```

This architecture will let the eventual FYP replace individual components with improved research methods without redesigning the memory layer.

---

## 10. Evaluation for the POC

The proposal defense does not need the final benchmark evaluation, but the demo should be measurable.

Create a small ground-truth table manually for the demo video:

| Question | Ground truth |
|---|---|
| Where is the mug? | kitchen counter |
| Where was the mug before? | desk |
| When did the mug move? | 00:24–00:43 |
| What was beside the mug? | laptop |
| Where are the keys? | desk |

Report:

- object persistence accuracy;
- location accuracy;
- temporal ordering accuracy;
- query answer accuracy;
- retrieval latency.

For spatial accuracy, use a coarse metric first:

```text
correct anchor / incorrect anchor
```

Then add continuous position error where reliable metric scale exists.

---

## 11. Recommended Initial Configuration

```yaml
video:
  sample_fps: 5
  width: 960
  height: 540

perception:
  depth: depth_anything_v2
  detector: yoloe
  segmentation: sam2
  tracker: botsort
  embedding: dinov2

geometry:
  pose_provider: droid_slam
  coordinate_mode: relative_anchor

memory:
  database: sqlite
  vector_index: faiss
  persistence_threshold: 0.65
  observation_merge_distance: 1.0

visualization:
  backend: rerun

query:
  parser: llm_structured
  allowed_operations:
    - location
    - last_location
    - previous_location
    - when_moved
    - near
    - state_at_time
```

Treat these as initial values, not scientifically justified final parameters. Tune them against the demo sequence and record all final configuration values.

---

## 12. Dependency Risk Management

### Highest-risk component: monocular camera trajectory

If SLAM is unstable:

1. Lower resolution.
2. Increase frame sampling density.
3. Use shorter sequences.
4. Avoid feature-poor areas.
5. Cache poses offline.

Do **not** redesign the entire system around this one component.

### Second-highest-risk component: persistent object identity

Start with one or two deliberately obvious objects and limited movement. Expand only after identity association works.

### Third-highest-risk component: semantic query understanding

Use a finite query grammar first. LLM parsing can be added once deterministic retrieval works.

### General strategy

Every expensive or probabilistic module should have a cached artifact:

```text
raw video
   ↓
frames
   ↓
depth.cache
poses.cache
tracks.cache
masks.cache
embeddings.cache
   ↓
memory.sqlite
   ↓
rerun log
```

This makes the defense demo reproducible.

---

## 13. Suggested Development Order

Implement strictly in this order:

```text
1. Video ingestion
2. Frame sampling
3. Depth
4. Camera pose
5. Rerun 3D visualization
6. Object detection
7. Segmentation
8. Tracking
9. Mask → 3D lifting
10. Persistent identity
11. Anchor-relative states
12. SQLite memory
13. Timeline visualization
14. Deterministic query engine
15. Natural-language parser
16. UI polish
```

Do not implement the LLM agent first. The memory representation is the project's core.

---

## 14. Definition of Done for Proposal Defense

The POC is sufficient when the following sequence works without manual intervention:

```text
START
  |
  v
Load egocentric video
  |
  v
Display camera trajectory + 3D environment
  |
  v
Display persistent objects
  |
  v
Scrub timeline
  |
  v
Show Mug #17 moving Desk → Hand → Kitchen Counter
  |
  v
Ask: "Where did I leave the mug?"
  |
  v
Return: Kitchen Counter
  |
  v
Highlight object in 3D
  |
  v
Show timestamp + evidence frame
```

If this works reliably, the defense has a concrete demonstration that Aegis is more than a conventional video QA system: it creates a **persistent spatio-temporal representation** that can be inspected and queried.

---

## 15. Relationship to the Research Direction

The POC should explicitly position itself between the relevant recent systems:

- **DAAAM** demonstrates real-time hierarchical 4D scene-graph memory, but its input assumes RGB-D. Its implementation uses segmentation/tracking, geometric lifting and Rerun visualization. `https://github.com/MIT-SPARK/DAAAM`
- **FARM** demonstrates object-level spatial memory and relational language retrieval from RGB-D streams. `https://github.com/GoldenGait/FARM-Project`
- **GESTO** extends spatio-temporal memory with human-object interactions and event structure, again using RGB-D. `https://arxiv.org/abs/2608.10886`
- **R4DSG** is particularly aligned with Aegis's monocular egocentric constraint: it proposes relative 4D scene-graph memory from long RGB egocentric video, using persistent identities and anchor-relative changes. `https://arxiv.org/abs/2608.11017`
- **ReViV** is a newly published monocular egocentric 4D reconstruction direction and may become relevant to a later version of the perception frontend. `https://arxiv.org/abs/2607.17790`

Aegis's POC should therefore emphasize the research gap:

> **Persistent spatio-temporal episodic memory from monocular egocentric video, rather than simply 3D mapping or transcript-based retrieval.**

---

## 16. Final Recommended Stack

| Layer | Recommendation |
|---|---|
| Language | Python 3.12 |
| Env | uv |
| ML | PyTorch |
| Video | OpenCV + FFmpeg |
| Depth | Depth Anything V2 |
| Monocular pose | DROID-SLAM (or replaceable monocular VO frontend) |
| Detection | YOLOE / YOLO-World |
| Segmentation | SAM 2 |
| Tracking | BoT-SORT / ByteTrack |
| Appearance features | DINOv2 initially; CLIP optional for text-image semantics |
| 3D geometry | NumPy + Open3D |
| Memory DB | SQLite |
| Vector search | FAISS |
| Visualization | Rerun |
| Query parser | Structured LLM output |
| UI | Gradio initially |
| Configuration | YAML |
| Tests | pytest |
| Deployment | Local workstation first |

### Priority

**Must have:**

`video → pose → depth → objects → 3D → persistent IDs → temporal memory → Rerun → query`

**Should have:**

`anchor-relative relations → evidence frames → natural-language parser`

**Can wait:**

`speech → caregiver portal → long-term abstraction → event hierarchy → real-time streaming → mobile deployment`

---

## 17. First Coding Sprint

The first implementation sprint should produce only this:

```text
INPUT:
    60–90 s egocentric MP4

OUTPUT:
    1. sampled RGB frames
    2. monocular depth maps
    3. camera trajectory
    4. accumulated 3D point cloud
    5. Rerun viewer showing video + trajectory + point cloud
```

Do not add the query system yet.

The second sprint should add:

```text
objects + masks + tracks + 3D object centers
```

The third sprint should add:

```text
persistent identities + temporal states + queryable SQLite memory
```

This sequencing minimizes integration risk and ensures a usable spatial reconstruction exists before the semantic-memory layer is built.
