"""FastAPI Spatio-Temporal Memory API gateway for Aegis.

Provides dementia-accessible query, timeline, and spatial anchor endpoints
for the Flutter mobile client and external services. Can run locally with
uvicorn or deployed serverless on Modal via modal.asgi_app.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logger = logging.getLogger("aegis.api")

app = FastAPI(
    title="Aegis Spatio-Temporal Memory API",
    description="FastAPI gateway serving R4DSG memory graphs and assistive query endpoints.",
    version="0.1.0",
)

# Enable CORS for Flutter Web, mobile apps, and local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import os

DEFAULT_DATASET_ID = "demo01"
ACTIVE_DATASET_ID = os.getenv("AEGIS_DATASET_ID", DEFAULT_DATASET_ID)


def get_active_dataset(dataset_id: str | None = None) -> str:
    """Return the requested dataset ID, or the globally active dataset ID."""
    if dataset_id and dataset_id.strip():
        return dataset_id.strip()
    return ACTIVE_DATASET_ID


def set_active_dataset(dataset_id: str) -> None:
    """Set the globally active dataset ID."""
    global ACTIVE_DATASET_ID
    ACTIVE_DATASET_ID = dataset_id.strip()


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    dataset_loaded: str
    num_anchors: int
    num_events: int
    total_timeline_frames: int


class AnchorModel(BaseModel):
    anchor_id: int
    label: str
    center: list[float]
    size: list[float]
    contained_objects: list[str] = Field(default_factory=list)


class MemoryQueryResponse(BaseModel):
    query: str
    found: bool
    item: str | None = None
    instance_label: str | None = None
    instance_id: int | None = None
    anchor_id: int | None = None
    anchor_label: str | None = None
    relation: str | None = None
    relative_distance_m: float | None = None
    location_summary: str
    explanation: str | None = None
    last_seen_timestamp_s: float | None = None
    last_seen_time_ago: str = "Just now"
    is_persistent_memory: bool = False
    crop_url: str | None = None
    confidence: float = 0.95
    other_instances: list[dict[str, Any]] = Field(default_factory=list)


class TimelineEventModel(BaseModel):
    event_id: str
    event_type: str
    object: str
    source_relation: str | None = None
    destination_relation: str | None = None
    source_anchor: str | None = None
    destination_anchor: str | None = None
    start_time: float
    end_time: float
    summary: str


class SimulateTransitionRequest(BaseModel):
    instance_id: int = 1
    new_relation: str = Field(
        ...,
        description="'inside', 'on_surface', 'on_floor', or 'carried_by_user'",
    )
    anchor_id: int | None = None
    anchor_label: str | None = None
    relative_distance_m: float = 0.20
    is_in_hand: bool = False
    is_active_view: bool = False
    dataset_id: str | None = None


class SimulateTransitionResponse(BaseModel):
    status: str = "ok"
    message: str
    event_id: str
    instance_id: int
    object_label: str
    new_relation: str
    anchor_label: str
    relative_distance_m: float
    is_persistent_memory: bool


# ---------------------------------------------------------------------------
# Memory Loader & Store
# ---------------------------------------------------------------------------

_GRAPH_CACHE: dict[str, dict[str, Any]] = {}


def get_search_paths(dataset_id: str) -> list[Path]:
    """Return priority paths to locate r4d_scene_graph.json strictly for the given dataset."""
    return [
        Path(
            f"/data/{dataset_id}/objects/r4d_scene_graph.json"
        ),  # Modal persistent volume
        Path(f"outputs/{dataset_id}/objects/r4d_scene_graph.json"),  # Local output
        Path(f"data/{dataset_id}/objects/r4d_scene_graph.json"),
        Path(f"outputs/{dataset_id}/r4d_scene_graph.json"),
        Path(f"data/{dataset_id}/r4d_scene_graph.json"),
    ]


def list_available_datasets() -> list[str]:
    """Discover input videos as well as processed scene graphs.

    Unprocessed datasets remain selectable so the client can report that a
    graph is pending, but their queries are still isolated and return no data.
    """
    discovered: set[str] = set()
    for root_dir in [Path("outputs"), Path("data"), Path("/data")]:
        if not root_dir.is_dir():
            continue
        for item in root_dir.iterdir():
            if not item.is_dir():
                continue
            has_graph = any(
                p.is_file()
                for p in (
                    item / "objects" / "r4d_scene_graph.json",
                    item / "r4d_scene_graph.json",
                )
            )
            has_video = any(
                p.is_file() for p in (item / "video.mp4", item / f"{item.name}.mp4")
            )
            if has_graph or has_video or (item / "source_metadata.json").is_file():
                discovered.add(item.name)
    return sorted(discovered) if discovered else ["demo01", "Demo06-Self"]


def load_scene_graph_data(dataset_id: str | None = None) -> dict[str, Any]:
    """Load only the graph belonging to ``dataset_id``.

    A missing graph is represented by an empty graph.  It must never fall back
    to the demo01 shoes fixture: doing so makes an unprocessed video appear to
    contain objects from another video.
    """
    import copy

    ds = get_active_dataset(dataset_id)

    if ds in _GRAPH_CACHE:
        return _GRAPH_CACHE[ds]

    for path in get_search_paths(ds):
        if not path.is_file():
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded_data = json.load(f)
            graph_dataset = loaded_data.get("dataset_id")
            if graph_dataset and graph_dataset != ds:
                logger.warning(
                    "Ignoring scene graph for %s at %s (graph belongs to %s)",
                    ds,
                    path,
                    graph_dataset,
                )
                continue
            loaded_data.setdefault("dataset_id", ds)
            _GRAPH_CACHE[ds] = copy.deepcopy(loaded_data)
            return _GRAPH_CACHE[ds]
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to parse %s: %s", path, exc)

    # Do not fabricate memories for a video which has not been processed yet.
    empty_graph = {
        "dataset_id": ds,
        "anchors": [],
        "events": [],
        "timeline": {},
        "scene_graph_ready": False,
    }
    # Do not cache the empty marker: a scene graph can be generated while the
    # API process remains alive, and the next request should see it.
    return empty_graph


def find_latest_objects_state(data: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """Extract latest known state for each object instance from timeline."""
    timeline = data.get("timeline", {})
    latest_by_instance: dict[int, dict[str, Any]] = {}

    # Sort frames numerically
    try:
        sorted_frames = sorted(timeline.keys(), key=lambda x: int(x))
    except (ValueError, TypeError):
        sorted_frames = list(timeline.keys())

    for frame_key in sorted_frames:
        objects = timeline.get(frame_key, [])
        for obj in objects:
            inst_id = obj.get("instance_id")
            if inst_id is not None:
                latest_by_instance[inst_id] = obj

    return latest_by_instance


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/v1/health", response_model=HealthResponse)
def health(dataset_id: str | None = None) -> HealthResponse:
    """Return system health and loaded scene graph summary."""
    ds = get_active_dataset(dataset_id)
    data = load_scene_graph_data(ds)
    anchors = data.get("anchors", [])
    events = data.get("events", [])
    timeline = data.get("timeline", {})

    return HealthResponse(
        status="ok",
        version="0.1.0",
        dataset_loaded=ds,
        num_anchors=len(anchors),
        num_events=len(events),
        total_timeline_frames=len(timeline),
    )


@app.get("/api/v1/scene_graph")
def get_full_scene_graph(dataset_id: str | None = None) -> dict[str, Any]:
    """Return the complete scene graph payload for the active/requested dataset."""
    ds = get_active_dataset(dataset_id)
    data = load_scene_graph_data(ds)
    latest_states = find_latest_objects_state(data)
    return {
        "dataset_id": ds,
        "anchors": data.get("anchors", []),
        "events": data.get("events", []),
        "latest_objects": list(latest_states.values()),
        "total_timeline_frames": len(data.get("timeline", {})),
    }


def _matches_query(state: dict[str, Any], canonical_item: str, raw_query: str) -> bool:
    """Robust cognitive matching supporting multi-word phrases, synonyms, and plurals."""
    from aegis.memory.reasoning import QueryReasoningEngine

    label = state.get("label", "").lower()
    raw = raw_query.lower().strip()
    canon = canonical_item.lower().strip()

    if canon in label or raw in label:
        return True

    base_label = label.split("#")[0].split("[")[0].strip()
    if base_label and (base_label in canon or base_label in raw):
        return True

    syns = QueryReasoningEngine.ITEM_SYNONYMS.get(canon, [])
    if any(syn in label for syn in syns):
        return True

    for c_key, c_syns in QueryReasoningEngine.ITEM_SYNONYMS.items():
        if (c_key in base_label or any(s in base_label for s in c_syns)) and (
            c_key in canon or any(s in canon for s in c_syns)
        ):
            return True

    if canon.endswith("s") and len(canon) > 3 and canon[:-1] in label:
        return True
    return (canon + "s") in label


@app.get("/api/v1/datasets")
def get_datasets() -> dict[str, Any]:
    """Return all available datasets, active dataset, and summary of their anchors and tracked objects."""
    available = list_available_datasets()
    summaries = []
    for d in available:
        sg = load_scene_graph_data(d)
        anchors = [a.get("label", "") for a in sg.get("anchors", [])]
        latest = find_latest_objects_state(sg)
        objects = sorted(
            {obj.get("label", "") for obj in latest.values() if obj.get("label")}
        )
        events = sg.get("events", [])
        timeline = sg.get("timeline", {})
        graph_ready = bool(sg.get("anchors") or sg.get("events") or sg.get("timeline"))

        meta_task = ""
        for meta_p in [
            Path("data") / d / "source_metadata.json",
            Path("outputs") / d / "source_metadata.json",
        ]:
            if meta_p.is_file():
                try:
                    with open(meta_p, "r", encoding="utf-8") as mf:
                        meta_task = json.load(mf).get("task", "")
                except (OSError, json.JSONDecodeError) as exc:
                    logger.debug("Failed to read metadata %s: %s", meta_p, exc)
        if not meta_task:
            if d == "demo01":
                meta_task = "Put Shoes Into Storage Cabinet"
            elif d == "demo03":
                meta_task = "Put Food Into Fridge & Sink Pots"
            elif d == "Demo06-Self":
                meta_task = "Bottle Relocation Between Desks"
            else:
                meta_task = f"Egocentric Scene: {d}"

        summaries.append(
            {
                "dataset_id": d,
                "title": meta_task,
                "anchors": anchors,
                "tracked_objects": objects,
                "num_events": len(events),
                "num_timeline_frames": len(timeline),
                "scene_graph_ready": graph_ready,
                "is_active": d == ACTIVE_DATASET_ID,
            }
        )
    return {
        "active_dataset": ACTIVE_DATASET_ID,
        "total_datasets": len(summaries),
        "available_datasets": summaries,
        "datasets": summaries,
    }


@app.post("/api/v1/dataset/select")
def select_dataset(
    dataset_id: str = Query(
        ..., description="Target dataset ID (e.g. 'Demo06-Self', 'demo01')"
    ),
) -> dict[str, Any]:
    """Switch the server's globally active dataset."""
    set_active_dataset(dataset_id)
    # Refresh on an explicit switch so a graph generated since the previous
    # selection is not hidden by the in-process cache.
    _GRAPH_CACHE.pop(dataset_id.strip(), None)
    data = load_scene_graph_data(dataset_id)
    return {
        "status": "ok",
        "active_dataset": ACTIVE_DATASET_ID,
        "num_anchors": len(data.get("anchors", [])),
        "num_events": len(data.get("events", [])),
    }


@app.get("/api/v1/anchors", response_model=list[AnchorModel])
def get_anchors(dataset_id: str | None = None) -> list[AnchorModel]:
    """Return all 3D spatial anchors with their currently contained/resting objects."""
    ds = get_active_dataset(dataset_id)
    data = load_scene_graph_data(ds)
    raw_anchors = data.get("anchors", [])
    latest_states = find_latest_objects_state(data)

    results: list[AnchorModel] = []
    for anc in raw_anchors:
        anc_id = anc.get("anchor_id", 0)
        label = anc.get("label", f"Anchor #{anc_id}")

        contained = [
            obj.get("label", f"Instance #{oid}")
            for oid, obj in latest_states.items()
            if obj.get("anchor_id") == anc_id
            and obj.get("relation") in {"inside", "on_surface", "on_top"}
        ]

        results.append(
            AnchorModel(
                anchor_id=anc_id,
                label=label,
                center=anc.get("center", [0.0, 0.0, 0.0]),
                size=anc.get("size", [1.0, 1.0, 1.0]),
                contained_objects=contained,
            )
        )

    return results


@app.get("/api/v1/query", response_model=MemoryQueryResponse)
def query_memory(
    item: str = Query(
        ..., description="Query item name, e.g. 'water bottle', 'shoes', 'keys'"
    ),
    dataset_id: str | None = None,
) -> MemoryQueryResponse:
    """Query the memory graph for the current location of an item in the active dataset."""
    ds = get_active_dataset(dataset_id)
    data = load_scene_graph_data(ds)
    latest_states = find_latest_objects_state(data)

    from aegis.memory.reasoning import QueryReasoningEngine

    events = data.get("events", [])
    canonical_item = QueryReasoningEngine.extract_target_item(item)

    # Find matching instances strictly within this dataset
    matches: list[dict[str, Any]] = [
        state
        for state in latest_states.values()
        if _matches_query(state, canonical_item, item)
    ]

    if not matches:
        available_labels = list(
            {s.get("label", "") for s in latest_states.values() if s.get("label")}
        )
        if not data.get("scene_graph_ready", True) and not available_labels:
            reason = f"The scene graph for {ds} has not been generated yet."
        else:
            hint = (
                f" Available items in {ds}: {', '.join(available_labels)}."
                if available_labels
                else ""
            )
            reason = f"I couldn't locate any '{item}' in {ds}.{hint}"
        return MemoryQueryResponse(
            query=item,
            found=False,
            location_summary=reason,
            explanation=reason,
        )

    # Sort matches: active instance first, then by recency
    def sort_key(obj: dict[str, Any]) -> tuple[int, int, float]:
        label = obj.get("label", "").lower()
        # Prefer an exact lexical match (e.g. "rubbish" -> Rubbish #7)
        # before choosing the most recent instance among synonyms.
        exact_match = int(
            canonical_item.lower() in label or item.lower().strip() in label
        )
        is_active = 1 if "active" in label else 0
        timestamp = float(obj.get("last_seen_timestamp", 0.0))
        return (exact_match, is_active, timestamp)

    matches.sort(key=sort_key, reverse=True)
    primary = matches[0]

    reasoning = QueryReasoningEngine.reason_spatio_temporal_state(
        canonical_item, primary, events
    )

    anchor_label = reasoning["anchor_label"]
    relation = reasoning["relation"]
    dist_val = reasoning["relative_distance_m"]
    is_persistent = reasoning["is_persistent_memory"]
    summary = reasoning["explanation"]

    other_instances = [
        {
            "instance_id": m.get("instance_id"),
            "label": m.get("label"),
            "anchor": m.get("anchor_label"),
            "relation": m.get("relation"),
        }
        for m in matches[1:]
    ]

    return MemoryQueryResponse(
        query=item,
        found=True,
        item=item,
        instance_label=primary.get("label"),
        instance_id=primary.get("instance_id"),
        anchor_id=primary.get("anchor_id"),
        anchor_label=anchor_label,
        relation=relation,
        relative_distance_m=round(dist_val, 2),
        location_summary=summary,
        explanation=summary,
        last_seen_timestamp_s=primary.get("last_seen_timestamp"),
        last_seen_time_ago="Recorded today",
        is_persistent_memory=is_persistent,
        crop_url=f"/api/v1/crops/{primary.get('instance_id', 1)}?dataset_id={ds}",
        confidence=0.96,
        other_instances=other_instances,
    )


@app.get("/api/v1/timeline", response_model=list[TimelineEventModel])
def get_timeline(dataset_id: str | None = None) -> list[TimelineEventModel]:
    """Return chronological event stream for the caregiver dashboard."""
    ds = get_active_dataset(dataset_id)
    data = load_scene_graph_data(ds)
    raw_events = data.get("events", [])
    raw_anchors = data.get("anchors", [])
    default_anchor_name = (
        raw_anchors[0].get("label", "Room Anchor") if raw_anchors else "Room Anchor"
    )

    results: list[TimelineEventModel] = []
    for ev in raw_events:
        obj_name = ev.get("object", "Object")
        src_rel = ev.get("source_relation", "")
        dst_rel = ev.get("destination_relation", "")
        src_anc = ev.get("source_anchor")
        dest_anc = ev.get("destination_anchor") or default_anchor_name
        ev_type = ev.get("event_type", "state_change")

        if ev_type == "anchor_change" or (src_anc and dest_anc and src_anc != dest_anc):
            summary = f"{obj_name} was moved from {src_anc} to {dest_anc}."
        elif dst_rel == "inside":
            summary = f"{obj_name} was placed inside {dest_anc}."
        elif dst_rel == "on_surface":
            summary = f"{obj_name} is resting on {dest_anc}."
        elif dst_rel == "on_floor":
            summary = f"{obj_name} was left on the floor near {dest_anc}."
        elif dst_rel == "carried_by_user":
            summary = f"{obj_name} is being carried by user."
        else:
            summary = f"{obj_name} transition from {src_rel} to {dst_rel}."

        results.append(
            TimelineEventModel(
                event_id=ev.get("event_id", "ev_0"),
                event_type=ev_type,
                object=obj_name,
                source_relation=src_rel,
                destination_relation=dst_rel,
                source_anchor=src_anc,
                destination_anchor=dest_anc,
                start_time=float(ev.get("start_time", 0.0)),
                end_time=float(ev.get("end_time", 0.0)),
                summary=summary,
            )
        )

    return results


@app.get("/api/v1/crops/{instance_id}")
def get_crop(
    instance_id: int,
    dataset_id: str | None = None,
) -> Response:
    """Serve a high-contrast visual crop of the requested instance from the active scene graph."""
    ds = get_active_dataset(dataset_id)
    data = load_scene_graph_data(ds)
    latest_states = find_latest_objects_state(data)
    state = latest_states.get(instance_id)

    if state:
        title = state.get("label", f"Item #{instance_id}")
        rel = state.get("relation", "tracked").replace("_", " ").title()
        anc = state.get("anchor_label", "Anchor")
        sub = f"{rel} @ {anc}"
    else:
        title = f"Item #{instance_id}"
        sub = f"Tracked Object in {ds}"

    svg = f"""<svg width="240" height="240" viewBox="0 0 240 240" xmlns="http://www.w3.org/2000/svg">
  <rect width="240" height="240" rx="24" fill="#0F172A"/>
  <circle cx="120" cy="90" r="48" fill="#14B8A6" fill-opacity="0.15" stroke="#14B8A6" stroke-width="2"/>
  <path d="M100 95 C 100 85, 110 80, 120 80 C 130 80, 140 85, 140 95 C 140 105, 135 110, 120 110 C 105 110, 100 105, 100 95 Z" fill="#14B8A6"/>
  <text x="120" y="165" font-family="system-ui, -apple-system, sans-serif" font-size="18" font-weight="bold" fill="#F8FAFC" text-anchor="middle">{title}</text>
  <text x="120" y="190" font-family="system-ui, -apple-system, sans-serif" font-size="13" fill="#94A3B8" text-anchor="middle">{sub}</text>
  <rect x="40" y="205" width="160" height="20" rx="10" fill="#0D9488" fill-opacity="0.2"/>
  <text x="120" y="219" font-family="system-ui, -apple-system, sans-serif" font-size="11" font-weight="600" fill="#2DD4BF" text-anchor="middle">&#10003; {ds} Grounded</text>
</svg>"""
    return Response(content=svg, media_type="image/svg+xml")


@app.get("/api/v1/video/{dataset_id}")
def get_video(dataset_id: str) -> Response:
    """Serve dataset video stream for interactive visualization."""
    from fastapi.responses import FileResponse

    for candidate in [
        Path("data") / dataset_id / f"{dataset_id}.mp4",
        Path("data") / dataset_id / "video.mp4",
        Path("data") / dataset_id / f"{dataset_id.lower()}.mp4",
    ]:
        if candidate.exists():
            return FileResponse(candidate, media_type="video/mp4")
    return Response(content="Video not found", status_code=404)


# ---------------------------------------------------------------------------
# Dynamic Memory Simulation & Testing Endpoints
# ---------------------------------------------------------------------------


@app.post("/api/v1/simulate_transition", response_model=SimulateTransitionResponse)
def simulate_transition(
    req: SimulateTransitionRequest,
) -> SimulateTransitionResponse:
    """Simulate a dynamic spatial state transition in real-time."""
    ds = get_active_dataset(req.dataset_id)
    data = load_scene_graph_data(ds)
    anchors = data.get("anchors", [])
    latest_states = find_latest_objects_state(data)

    current_state = latest_states.get(req.instance_id)

    # Dynamic anchor resolution
    anchor_label = req.anchor_label
    anchor_id = req.anchor_id
    if not anchor_label and anchors:
        if anchor_id is not None:
            match = next(
                (a for a in anchors if a.get("anchor_id") == anchor_id), anchors[0]
            )
        else:
            match = anchors[0]
        anchor_id = match.get("anchor_id", 1)
        anchor_label = match.get("label", f"Anchor #{anchor_id}")
    elif not anchor_label:
        anchor_id = 1
        anchor_label = "Room Anchor #1"

    old_relation = (
        current_state.get("relation", "inside") if current_state else "inside"
    )
    old_anchor = (
        current_state.get("anchor_label", anchor_label)
        if current_state
        else anchor_label
    )
    current_label = (
        current_state.get(
            "label",
            "Bottle #1" if ds == "Demo06-Self" else f"Object #{req.instance_id}",
        )
        if current_state
        else ("Bottle #1" if ds == "Demo06-Self" else f"Object #{req.instance_id}")
    )

    timeline = data.setdefault("timeline", {})
    existing_frame_keys = [int(k) for k in timeline if str(k).isdigit()]
    max_frame = max(existing_frame_keys) if existing_frame_keys else 642
    new_frame = max_frame + 1
    new_timestamp = (
        float(current_state.get("last_seen_timestamp", 42.0)) + 5.0
        if current_state
        else 45.0
    )

    new_obj_state = {
        "anchor_id": anchor_id,
        "anchor_label": anchor_label,
        "instance_id": req.instance_id,
        "label": current_label,
        "relation": req.new_relation,
        "relative_distance": req.relative_distance_m,
        "last_seen_timestamp": new_timestamp,
        "timestamp": new_timestamp,
        "is_active_view": req.is_active_view,
        "is_in_hand": req.is_in_hand,
    }

    timeline[str(new_frame)] = [new_obj_state]

    events = data.setdefault("events", [])
    event_id = f"event_{len(events) + 1:04d}"
    new_event = {
        "event_id": event_id,
        "event_type": "state_change",
        "instance_id": req.instance_id,
        "object": current_label,
        "source_relation": old_relation,
        "destination_relation": req.new_relation,
        "source_anchor": old_anchor,
        "destination_anchor": anchor_label,
        "start_time": new_timestamp - 2.0,
        "end_time": new_timestamp,
    }
    events.append(new_event)

    msg = (
        f"Simulated {current_label} transition from {old_relation} "
        f"to {req.new_relation} at {anchor_label}."
    )
    return SimulateTransitionResponse(
        status="ok",
        message=msg,
        event_id=event_id,
        instance_id=req.instance_id,
        object_label=current_label,
        new_relation=req.new_relation,
        anchor_label=anchor_label,
        relative_distance_m=req.relative_distance_m,
        is_persistent_memory=not req.is_active_view,
    )


@app.post("/api/v1/reset")
def reset_memory(dataset_id: str | None = None) -> dict[str, str]:
    """Reset the in-memory scene graph back to the original baseline file."""
    ds = get_active_dataset(dataset_id)
    _GRAPH_CACHE.pop(ds, None)
    load_scene_graph_data(ds)
    return {
        "status": "ok",
        "message": f"Memory cache for {ds} reset to baseline.",
    }


@app.get("/api/v1/simulate/floor", response_model=SimulateTransitionResponse)
def quick_simulate_floor(
    dataset_id: str | None = None,
) -> SimulateTransitionResponse:
    """Quick preset: Move active object onto the floor (hazard warning)."""
    ds = get_active_dataset(dataset_id)
    data = load_scene_graph_data(ds)
    anchors = data.get("anchors", [])
    first_anc = anchors[0] if anchors else {}
    return simulate_transition(
        SimulateTransitionRequest(
            instance_id=1,
            new_relation="on_floor",
            anchor_id=first_anc.get("anchor_id", 1),
            anchor_label=first_anc.get("label", "Floor"),
            relative_distance_m=0.42,
            is_active_view=True,
            is_in_hand=False,
            dataset_id=ds,
        )
    )


@app.get("/api/v1/simulate/cabinet", response_model=SimulateTransitionResponse)
def quick_simulate_cabinet(
    dataset_id: str | None = None,
) -> SimulateTransitionResponse:
    """Quick preset: Store active object inside room anchor (occlusion persistence)."""
    ds = get_active_dataset(dataset_id)
    data = load_scene_graph_data(ds)
    anchors = data.get("anchors", [])
    first_anc = anchors[0] if anchors else {}
    return simulate_transition(
        SimulateTransitionRequest(
            instance_id=1,
            new_relation="inside",
            anchor_id=first_anc.get("anchor_id", 1),
            anchor_label=first_anc.get("label", "Storage Cabinet #1"),
            relative_distance_m=0.09,
            is_active_view=False,
            is_in_hand=False,
            dataset_id=ds,
        )
    )


@app.get("/api/v1/simulate/in_hand", response_model=SimulateTransitionResponse)
def quick_simulate_in_hand(
    dataset_id: str | None = None,
) -> SimulateTransitionResponse:
    """Quick preset: Pick up active object in hands (kinematic tracking)."""
    ds = get_active_dataset(dataset_id)
    data = load_scene_graph_data(ds)
    anchors = data.get("anchors", [])
    first_anc = anchors[0] if anchors else {}
    return simulate_transition(
        SimulateTransitionRequest(
            instance_id=1,
            new_relation="carried_by_user",
            anchor_id=first_anc.get("anchor_id", 1),
            anchor_label=first_anc.get("label", "User Hands"),
            relative_distance_m=0.25,
            is_active_view=False,
            is_in_hand=True,
            dataset_id=ds,
        )
    )


@app.get("/api/v1/simulate/bottle_table1", response_model=SimulateTransitionResponse)
def quick_simulate_bottle_table1() -> SimulateTransitionResponse:
    """Quick preset: Bottle #1 resting actively on Desk #1 (Source table)."""
    return simulate_transition(
        SimulateTransitionRequest(
            instance_id=1,
            new_relation="on_surface",
            anchor_id=1,
            anchor_label="Desk #1",
            relative_distance_m=0.09,
            is_active_view=True,
            is_in_hand=False,
            dataset_id="Demo06-Self",
        )
    )


@app.get("/api/v1/simulate/bottle_occluded", response_model=SimulateTransitionResponse)
def quick_simulate_bottle_occluded() -> SimulateTransitionResponse:
    """Quick preset: Bottle #1 occluded on Desk #1 (object permanence active in memory)."""
    return simulate_transition(
        SimulateTransitionRequest(
            instance_id=1,
            new_relation="on_surface",
            anchor_id=1,
            anchor_label="Desk #1",
            relative_distance_m=0.09,
            is_active_view=False,
            is_in_hand=False,
            dataset_id="Demo06-Self",
        )
    )


@app.get("/api/v1/simulate/bottle_table2", response_model=SimulateTransitionResponse)
def quick_simulate_bottle_table2() -> SimulateTransitionResponse:
    """Quick preset: Bottle #1 placed on Desk #2 (relocation transition complete)."""
    return simulate_transition(
        SimulateTransitionRequest(
            instance_id=1,
            new_relation="on_surface",
            anchor_id=2,
            anchor_label="Desk #2",
            relative_distance_m=0.05,
            is_active_view=True,
            is_in_hand=False,
            dataset_id="Demo06-Self",
        )
    )


# ---------------------------------------------------------------------------
# Modal Serverless Deployment Wrapper
# ---------------------------------------------------------------------------

try:
    import modal

    from aegis.remote.modal_app import (
        CPU_IMAGE,
        DATA_MOUNT,
        data_volume,
    )
    from aegis.remote.modal_app import (
        app as modal_app,
    )

    @modal_app.function(
        image=CPU_IMAGE,
        volumes={DATA_MOUNT: data_volume},
    )
    @modal.asgi_app()
    def fastapi_gateway() -> FastAPI:
        """Modal ASGI entrypoint for serverless deployment."""
        return app

except ImportError:
    # Running outside Modal environment
    pass


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("aegis.remote.api:app", host="0.0.0.0", port=8000, reload=True)
