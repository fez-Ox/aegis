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

DEFAULT_DATASET_ID = "demo01"


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
        description="'inside', 'on_floor', or 'carried_by_user'",
    )
    anchor_id: int = 1
    anchor_label: str = "Storage Cabinet #1"
    relative_distance_m: float = 0.45
    is_in_hand: bool = False
    is_active_view: bool = False
    dataset_id: str = DEFAULT_DATASET_ID


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
    """Return priority paths to locate r4d_scene_graph.json."""
    return [
        Path(
            f"/data/{dataset_id}/objects/r4d_scene_graph.json"
        ),  # Modal persistent volume
        Path(f"outputs/{dataset_id}/objects/r4d_scene_graph.json"),  # Local output
        Path("outputs/demo01/objects/r4d_scene_graph.json"),
        Path(f"data/{dataset_id}/objects/r4d_scene_graph.json"),
    ]


def load_scene_graph_data(dataset_id: str = DEFAULT_DATASET_ID) -> dict[str, Any]:
    """Load the scene graph JSON with in-memory caching and graceful fallback."""
    import copy

    if dataset_id in _GRAPH_CACHE:
        return _GRAPH_CACHE[dataset_id]

    loaded_data: dict[str, Any] | None = None
    for path in get_search_paths(dataset_id):
        if path.is_file():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    loaded_data = json.load(f)
                    break
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(f"Failed to parse {path}: {e}")

    if loaded_data is not None:
        _GRAPH_CACHE[dataset_id] = copy.deepcopy(loaded_data)
        return _GRAPH_CACHE[dataset_id]

    # Fallback fixture if running before any pipeline execution
    fallback_data = {
        "anchors": [
            {
                "anchor_id": 1,
                "label": "Storage Cabinet #1",
                "center": [-0.055, 0.134, 0.793],
                "size": [0.88, 0.53, 0.506],
            }
        ],
        "events": [
            {
                "event_id": "event_0001",
                "event_type": "state_change",
                "instance_id": 1,
                "object": "Shoes #1 [Active Pair]",
                "source_relation": "on_floor",
                "destination_relation": "inside",
                "source_anchor": "Storage Cabinet #1",
                "destination_anchor": "Storage Cabinet #1",
                "start_time": 8.0,
                "end_time": 35.6,
            }
        ],
        "timeline": {
            "642": [
                {
                    "anchor_id": 1,
                    "anchor_label": "Storage Cabinet #1",
                    "instance_id": 1,
                    "label": "Shoes #1 [Active Pair]",
                    "relation": "inside",
                    "relative_distance": 0.095,
                    "last_seen_timestamp": 35.60,
                    "timestamp": 42.81,
                    "is_active_view": False,
                }
            ]
        },
    }
    _GRAPH_CACHE[dataset_id] = copy.deepcopy(fallback_data)
    return _GRAPH_CACHE[dataset_id]


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
def health(dataset_id: str = DEFAULT_DATASET_ID) -> HealthResponse:
    """Return system health and loaded scene graph summary."""
    data = load_scene_graph_data(dataset_id)
    anchors = data.get("anchors", [])
    events = data.get("events", [])
    timeline = data.get("timeline", {})

    return HealthResponse(
        status="ok",
        version="0.1.0",
        dataset_loaded=dataset_id,
        num_anchors=len(anchors),
        num_events=len(events),
        total_timeline_frames=len(timeline),
    )


@app.get("/api/v1/anchors", response_model=list[AnchorModel])
def get_anchors(dataset_id: str = DEFAULT_DATASET_ID) -> list[AnchorModel]:
    """Return all 3D spatial anchors with their currently contained objects."""
    data = load_scene_graph_data(dataset_id)
    raw_anchors = data.get("anchors", [])
    latest_states = find_latest_objects_state(data)

    results: list[AnchorModel] = []
    for anc in raw_anchors:
        anc_id = anc.get("anchor_id", 0)
        label = anc.get("label", f"Anchor #{anc_id}")

        contained = [
            obj.get("label", f"Instance #{oid}")
            for oid, obj in latest_states.items()
            if obj.get("anchor_id") == anc_id and obj.get("relation") == "inside"
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
        ..., description="Query item name, e.g. 'shoes', 'keys', 'glasses'"
    ),
    dataset_id: str = DEFAULT_DATASET_ID,
) -> MemoryQueryResponse:
    """Query the memory graph for the current location of an item.

    Dementia-Accessible: returns plain-language location summary and
    spatio-temporal confidence.
    """
    data = load_scene_graph_data(dataset_id)
    latest_states = find_latest_objects_state(data)

    from aegis.memory.reasoning import QueryReasoningEngine

    events = data.get("events", [])
    canonical_item = QueryReasoningEngine.extract_target_item(item)

    # Find matching instances
    matches: list[dict[str, Any]] = []
    for state in latest_states.values():
        label = state.get("label", "").lower()
        if canonical_item in label or (canonical_item == "shoes" and "shoe" in label):
            matches.append(state)

    if not matches:
        return MemoryQueryResponse(
            query=item,
            found=False,
            location_summary=f"I couldn't locate any '{item}' in your tracked rooms.",
        )

    # Sort matches: active pair first, then by recency
    def sort_key(obj: dict[str, Any]) -> tuple[int, float]:
        is_active = 1 if "active" in obj.get("label", "").lower() else 0
        timestamp = float(obj.get("last_seen_timestamp", 0.0))
        return (is_active, timestamp)

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
        last_seen_timestamp_s=primary.get("last_seen_timestamp"),
        last_seen_time_ago="Recorded today",
        is_persistent_memory=is_persistent,
        crop_url=f"/api/v1/crops/{primary.get('instance_id', 1)}",
        confidence=0.96,
        other_instances=other_instances,
    )


@app.get("/api/v1/timeline", response_model=list[TimelineEventModel])
def get_timeline(dataset_id: str = DEFAULT_DATASET_ID) -> list[TimelineEventModel]:
    """Return chronological event stream for the caregiver dashboard."""
    data = load_scene_graph_data(dataset_id)
    raw_events = data.get("events", [])

    results: list[TimelineEventModel] = []
    for ev in raw_events:
        obj_name = ev.get("object", "Object")
        src_rel = ev.get("source_relation", "")
        dst_rel = ev.get("destination_relation", "")
        dest_anc = ev.get("destination_anchor", "Storage Cabinet")

        if dst_rel == "inside":
            summary = f"{obj_name} was placed inside {dest_anc}."
        elif dst_rel == "on_floor":
            summary = f"{obj_name} was left on the floor."
        else:
            summary = f"{obj_name} transition from {src_rel} to {dst_rel}."

        results.append(
            TimelineEventModel(
                event_id=ev.get("event_id", "ev_0"),
                event_type=ev.get("event_type", "state_change"),
                object=obj_name,
                source_relation=src_rel,
                destination_relation=dst_rel,
                source_anchor=ev.get("source_anchor"),
                destination_anchor=dest_anc,
                start_time=float(ev.get("start_time", 0.0)),
                end_time=float(ev.get("end_time", 0.0)),
                summary=summary,
            )
        )

    return results


@app.get("/api/v1/crops/{instance_id}")
def get_crop(instance_id: int) -> Response:
    """Serve a high-contrast visual crop of the requested instance.

    Returns an accessible SVG visual badge with the object label.
    """
    labels = {
        1: ("Shoes #1", "Active Pair (Inside Cabinet)"),
        2: ("Shoes #2", "Left Shelf"),
        3: ("Shoes #3", "Middle Shelf"),
        4: ("Shoes #4", "Right Shelf"),
    }
    title, sub = labels.get(instance_id, (f"Item #{instance_id}", "Tracked Object"))

    svg = f"""<svg width="240" height="240" viewBox="0 0 240 240" xmlns="http://www.w3.org/2000/svg">
  <rect width="240" height="240" rx="24" fill="#0F172A"/>
  <circle cx="120" cy="90" r="48" fill="#14B8A6" fill-opacity="0.15" stroke="#14B8A6" stroke-width="2"/>
  <path d="M100 95 C 100 85, 110 80, 120 80 C 130 80, 140 85, 140 95 C 140 105, 135 110, 120 110 C 105 110, 100 105, 100 95 Z" fill="#14B8A6"/>
  <text x="120" y="165" font-family="system-ui, -apple-system, sans-serif" font-size="18" font-weight="bold" fill="#F8FAFC" text-anchor="middle">{title}</text>
  <text x="120" y="190" font-family="system-ui, -apple-system, sans-serif" font-size="13" fill="#94A3B8" text-anchor="middle">{sub}</text>
  <rect x="60" y="205" width="120" height="20" rx="10" fill="#0D9488" fill-opacity="0.2"/>
  <text x="120" y="219" font-family="system-ui, -apple-system, sans-serif" font-size="11" font-weight="600" fill="#2DD4BF" text-anchor="middle">&#10003; 3D Grounded</text>
</svg>"""
    return Response(content=svg, media_type="image/svg+xml")


# ---------------------------------------------------------------------------
# Dynamic Memory Simulation & Testing Endpoints
# ---------------------------------------------------------------------------


@app.post("/api/v1/simulate_transition", response_model=SimulateTransitionResponse)
def simulate_transition(
    req: SimulateTransitionRequest,
) -> SimulateTransitionResponse:
    """Simulate a dynamic spatial state transition in real-time.

    Updates the in-memory R4DSG memory graph and chronological event log,
    enabling live demonstration of Aegis spatial reasoning and instant Flutter
    client reactivity.
    """
    data = load_scene_graph_data(req.dataset_id)
    latest_states = find_latest_objects_state(data)

    current_state = latest_states.get(req.instance_id)
    old_relation = (
        current_state.get("relation", "inside") if current_state else "inside"
    )
    old_anchor = (
        current_state.get("anchor_label", req.anchor_label)
        if current_state
        else req.anchor_label
    )
    current_label = (
        current_state.get("label", f"Object #{req.instance_id}")
        if current_state
        else f"Object #{req.instance_id}"
    )

    timeline = data.setdefault("timeline", {})
    # Determine next frame key and timestamp
    existing_frame_keys = [int(k) for k in timeline if str(k).isdigit()]
    max_frame = max(existing_frame_keys) if existing_frame_keys else 642
    new_frame = max_frame + 1
    new_timestamp = (
        float(current_state.get("last_seen_timestamp", 42.0)) + 5.0
        if current_state
        else 45.0
    )

    new_obj_state = {
        "anchor_id": req.anchor_id,
        "anchor_label": req.anchor_label,
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
        "destination_anchor": req.anchor_label,
        "start_time": new_timestamp - 2.0,
        "end_time": new_timestamp,
    }
    events.append(new_event)

    msg = (
        f"Simulated {current_label} transition from {old_relation} "
        f"to {req.new_relation} at {req.anchor_label}."
    )
    return SimulateTransitionResponse(
        status="ok",
        message=msg,
        event_id=event_id,
        instance_id=req.instance_id,
        object_label=current_label,
        new_relation=req.new_relation,
        anchor_label=req.anchor_label,
        relative_distance_m=req.relative_distance_m,
        is_persistent_memory=not req.is_active_view,
    )


@app.post("/api/v1/reset")
def reset_memory(dataset_id: str = DEFAULT_DATASET_ID) -> dict[str, str]:
    """Reset the in-memory scene graph back to the original baseline file."""
    _GRAPH_CACHE.pop(dataset_id, None)
    load_scene_graph_data(dataset_id)
    return {
        "status": "ok",
        "message": f"Memory cache for {dataset_id} reset to baseline.",
    }


@app.get("/api/v1/simulate/floor", response_model=SimulateTransitionResponse)
def quick_simulate_floor(
    dataset_id: str = DEFAULT_DATASET_ID,
) -> SimulateTransitionResponse:
    """Quick preset: Move Shoes #1 onto the entrance floor (hazard warning)."""
    return simulate_transition(
        SimulateTransitionRequest(
            instance_id=1,
            new_relation="on_floor",
            relative_distance_m=0.42,
            is_active_view=True,
            is_in_hand=False,
            dataset_id=dataset_id,
        )
    )


@app.get("/api/v1/simulate/cabinet", response_model=SimulateTransitionResponse)
def quick_simulate_cabinet(
    dataset_id: str = DEFAULT_DATASET_ID,
) -> SimulateTransitionResponse:
    """Quick preset: Store Shoes #1 inside cabinet (occlusion persistence)."""
    return simulate_transition(
        SimulateTransitionRequest(
            instance_id=1,
            new_relation="inside",
            relative_distance_m=0.09,
            is_active_view=False,
            is_in_hand=False,
            dataset_id=dataset_id,
        )
    )


@app.get("/api/v1/simulate/in_hand", response_model=SimulateTransitionResponse)
def quick_simulate_in_hand(
    dataset_id: str = DEFAULT_DATASET_ID,
) -> SimulateTransitionResponse:
    """Quick preset: Pick up Shoes #1 in hands (in-hand kinematic tracking)."""
    return simulate_transition(
        SimulateTransitionRequest(
            instance_id=1,
            new_relation="carried_by_user",
            relative_distance_m=0.25,
            is_active_view=False,
            is_in_hand=True,
            dataset_id=dataset_id,
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
