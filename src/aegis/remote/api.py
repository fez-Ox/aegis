"""FastAPI memory API for the Aegis mobile client.

Serves query, timeline, anchor and room endpoints from a dataset's scene
graph. Answers never contain invented values: a missing confidence is
``null``, an unknown anchor is ``null`` and an unprocessed dataset answers
"not generated yet". The demo simulator routes exist only when
``AEGIS_ENABLE_SIMULATOR=1``.
"""

from __future__ import annotations

import html
import json
import logging
import os
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from aegis.core.paths import validate_dataset_id
from aegis.core.vocabulary import default_vocabulary
from aegis.memory.compaction import compaction_ok
from aegis.memory.homes import DuplicateRoomLabelError, get_store
from aegis.memory.personal import personal_ids_for_query, resolve_alias
from aegis.memory.reasoning import (
    QueryReasoningEngine,
    event_summary,
    parse_query_cues,
    rank_candidates,
    room_phrase,
)
from aegis.memory.repository import (
    JsonGraphRepository,
    StoreRepository,
    clear_cache,
    get_repository,
    latest_states_from_graph,
)

logger = logging.getLogger("aegis.api")

API_VERSION = "0.2.0"

app = FastAPI(
    title="Aegis Spatio-Temporal Memory API",
    description="Memory graph queries and timeline for the Aegis client.",
    version=API_VERSION,
)

# TODO(M4 4.2): replace the wildcard with explicit origins behind auth.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULT_DATASET_ID = "demo01"
ACTIVE_DATASET_ID = os.getenv("AEGIS_DATASET_ID", DEFAULT_DATASET_ID)


def _validated(dataset_id: str) -> str:
    try:
        return validate_dataset_id(dataset_id.strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid dataset_id") from exc


def get_active_dataset(dataset_id: str | None = None) -> str:
    """Return the requested (validated) dataset ID, or the active one."""

    if dataset_id and dataset_id.strip():
        return _validated(dataset_id)
    return ACTIVE_DATASET_ID


def set_active_dataset(dataset_id: str) -> None:
    """Set the globally active dataset ID."""

    global ACTIVE_DATASET_ID
    ACTIVE_DATASET_ID = _validated(dataset_id)


def simulator_enabled() -> bool:
    return os.getenv("AEGIS_ENABLE_SIMULATOR") == "1"


def require_simulator() -> None:
    if not simulator_enabled():
        raise HTTPException(status_code=404, detail="Not Found")


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = API_VERSION
    dataset_loaded: str
    scene_graph_ready: bool
    num_anchors: int
    num_rooms: int
    num_events: int
    total_timeline_frames: int
    simulator_enabled: bool = False
    compaction_ok: bool | None = None


class AnchorModel(BaseModel):
    anchor_id: int
    label: str
    center: list[float]
    size: list[float]
    room_id: int | None = None
    room_label: str | None = None
    contained_objects: list[str] = Field(default_factory=list)


class RoomModel(BaseModel):
    room_id: int
    label: str
    room_type: str = "Room"
    centroid: list[float] = Field(default_factory=list)
    anchors: list[str] = Field(default_factory=list)
    objects: list[str] = Field(default_factory=list)
    keyframe_count: int = 0


class MemoryQueryResponse(BaseModel):
    query: str
    found: bool
    item: str | None = None
    instance_label: str | None = None
    instance_id: int | None = None
    anchor_id: int | None = None
    anchor_label: str | None = None
    room_id: int | None = None
    room_label: str | None = None
    relation: str | None = None
    relation_certain: bool | None = None
    height_above_floor: float | None = None
    relative_distance_m: float | None = None
    location_summary: str
    explanation: str | None = None
    last_seen_timestamp_s: float | None = None
    last_seen_at: str | None = None
    # Real freshness wording is Milestone 3 (todo 3.4); never a constant.
    last_seen_time_ago: str | None = None
    is_persistent_memory: bool = False
    crop_url: str | None = None
    confidence: float | None = None
    other_instances: list[dict[str, Any]] = Field(default_factory=list)
    # Ambiguity-aware answers. Optional so older clients keep working.
    resolution_mode: str | None = None
    is_ambiguous: bool = False
    ambiguity_reason: str | None = None
    candidates: list[dict[str, Any]] = Field(default_factory=list)


class TimelineEventModel(BaseModel):
    event_id: str
    event_type: str
    object: str
    tier: str = "detailed"
    period_start: str | None = None
    period_end: str | None = None
    source_relation: str | None = None
    destination_relation: str | None = None
    source_anchor: str | None = None
    destination_anchor: str | None = None
    source_room: str | None = None
    destination_room: str | None = None
    start_time: float | None = None
    end_time: float | None = None
    start_wallclock: str | None = None
    end_wallclock: str | None = None
    activity_id: int | None = None
    summary: str


class SimulateTransitionRequest(BaseModel):
    instance_id: int = 1
    new_relation: str = Field(
        ...,
        description="'inside', 'on_surface', 'under', 'on_floor', 'carried_by_user', ...",
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
    anchor_label: str | None
    relative_distance_m: float
    is_persistent_memory: bool


# ---------------------------------------------------------------------------
# Memory loading
# ---------------------------------------------------------------------------


def get_search_paths(dataset_id: str) -> list[Path]:
    """Priority paths of ``r4d_scene_graph.json`` for exactly this dataset."""

    fixture_root = os.getenv("AEGIS_TEST_FIXTURE_ROOT")
    paths: list[Path] = []
    # CI uses small tracked fixtures instead of downloaded artifacts; opt-in
    # through the environment variable only.
    if fixture_root:
        paths.append(
            Path(fixture_root) / dataset_id / "objects" / "r4d_scene_graph.json"
        )
    paths.extend(
        [
            Path(f"/data/{dataset_id}/objects/r4d_scene_graph.json"),
            Path(f"outputs/{dataset_id}/objects/r4d_scene_graph.json"),
            Path(f"data/{dataset_id}/objects/r4d_scene_graph.json"),
            Path(f"outputs/{dataset_id}/r4d_scene_graph.json"),
            Path(f"data/{dataset_id}/r4d_scene_graph.json"),
        ]
    )
    return paths


def repository_for(dataset_id: str) -> JsonGraphRepository:
    return get_repository(dataset_id, get_search_paths(dataset_id))


def resolve_repository(
    dataset_id: str | None, home_id: str | None
) -> tuple[str, JsonGraphRepository | StoreRepository]:
    """Explicit home -> store; explicit dataset -> graph file; then defaults.

    Without either parameter, ``AEGIS_HOME_ID`` selects a home store and
    otherwise the active dataset's graph file is used.
    """

    if home_id and home_id.strip():
        home = _validated(home_id)
        return home, StoreRepository(get_store(home))
    if dataset_id and dataset_id.strip():
        ds = _validated(dataset_id)
        return ds, repository_for(ds)
    env_home = os.getenv("AEGIS_HOME_ID")
    if env_home:
        home = _validated(env_home)
        return home, StoreRepository(get_store(home))
    return ACTIVE_DATASET_ID, repository_for(ACTIVE_DATASET_ID)


def list_available_datasets() -> list[str]:
    """Datasets with an input video, metadata or a processed graph."""

    discovered: set[str] = set()
    roots = [Path("outputs"), Path("data"), Path("/data")]
    fixture_root = os.getenv("AEGIS_TEST_FIXTURE_ROOT")
    if fixture_root:
        roots.append(Path(fixture_root))
    for root_dir in roots:
        if not root_dir.is_dir():
            continue
        for item in root_dir.iterdir():
            if not item.is_dir() or item.name.startswith(("_", ".")):
                continue
            try:
                validate_dataset_id(item.name)
            except ValueError:
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
    return sorted(discovered)


def load_scene_graph_data(dataset_id: str | None = None) -> dict[str, Any]:
    """Raw graph dict of one dataset (empty, not ready, when missing)."""

    return repository_for(get_active_dataset(dataset_id)).data


def find_latest_objects_state(data: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """Latest known state per instance of a v1 or v2 graph dict."""

    return latest_states_from_graph(data)


def room_summary_clause(room: str | None) -> str:
    """Grammar-aware room suffix (" in the Kitchen")."""

    return room_phrase(room)


def _label_base(label: str) -> str:
    return str(label).split("[")[0].split("#")[0].strip()


def _state_canonical(state: dict[str, Any]) -> str:
    canonical = state.get("canonical")
    if canonical:
        return str(canonical)
    return default_vocabulary().canonical(_label_base(state.get("label", "")))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/v1/health", response_model=HealthResponse)
def health(dataset_id: str | None = None, home_id: str | None = None) -> HealthResponse:
    ds, repo = resolve_repository(dataset_id, home_id)
    return HealthResponse(
        dataset_loaded=ds,
        scene_graph_ready=repo.ready,
        num_anchors=len(repo.anchors()),
        num_rooms=len(repo.rooms()),
        num_events=len(repo.events()),
        total_timeline_frames=repo.keyframe_count(),
        simulator_enabled=simulator_enabled(),
        compaction_ok=(
            compaction_ok(repo.store) if isinstance(repo, StoreRepository) else None
        ),
    )


@app.get("/api/v1/scene_graph")
def get_full_scene_graph(
    dataset_id: str | None = None, home_id: str | None = None
) -> dict[str, Any]:
    ds, repo = resolve_repository(dataset_id, home_id)
    return {
        "dataset_id": ds,
        "scene_graph_ready": repo.ready,
        "anchors": repo.anchors(),
        "rooms": repo.rooms(),
        "events": repo.events(),
        "latest_objects": list(repo.latest_states().values()),
        "total_timeline_frames": repo.keyframe_count(),
    }


@app.get("/api/v1/datasets")
def get_datasets() -> dict[str, Any]:
    summaries = []
    for d in list_available_datasets():
        repo = repository_for(d)
        title = ""
        for meta_path in (
            Path("data") / d / "source_metadata.json",
            Path("outputs") / d / "source_metadata.json",
        ):
            if meta_path.is_file():
                try:
                    title = json.loads(meta_path.read_text(encoding="utf-8")).get(
                        "task", ""
                    )
                except (OSError, json.JSONDecodeError) as exc:
                    logger.debug("Failed to read metadata %s: %s", meta_path, exc)
        objects = sorted(
            {
                s.get("label", "")
                for s in repo.latest_states().values()
                if s.get("label")
            }
        )
        rooms = [r.get("label", "") for r in repo.rooms()]
        summaries.append(
            {
                "dataset_id": d,
                "title": title or f"Egocentric scene: {d}",
                "anchors": [a.get("label", "") for a in repo.anchors()],
                "rooms": rooms,
                "num_rooms": len(rooms),
                "tracked_objects": objects,
                "num_events": len(repo.events()),
                "num_timeline_frames": repo.keyframe_count(),
                "scene_graph_ready": repo.ready,
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
    dataset_id: str = Query(..., description="Target dataset ID"),
) -> dict[str, Any]:
    set_active_dataset(dataset_id)
    repo = repository_for(ACTIVE_DATASET_ID)
    return {
        "status": "ok",
        "active_dataset": ACTIVE_DATASET_ID,
        "num_anchors": len(repo.anchors()),
        "num_events": len(repo.events()),
    }


@app.get("/api/v1/anchors", response_model=list[AnchorModel])
def get_anchors(
    dataset_id: str | None = None, home_id: str | None = None
) -> list[AnchorModel]:
    _ds, repo = resolve_repository(dataset_id, home_id)
    latest = repo.latest_states()
    results: list[AnchorModel] = []
    for anchor in repo.anchors():
        anchor_id = anchor.get("anchor_id", 0)
        results.append(
            AnchorModel(
                anchor_id=anchor_id,
                label=anchor.get("label", f"Anchor #{anchor_id}"),
                center=anchor.get("center", [0.0, 0.0, 0.0]),
                size=anchor.get("size", [0.0, 0.0, 0.0]),
                room_id=anchor.get("room_id"),
                room_label=anchor.get("room_label"),
                contained_objects=[
                    obj.get("label", f"Instance #{oid}")
                    for oid, obj in latest.items()
                    if obj.get("anchor_id") == anchor_id
                    and obj.get("relation")
                    in {"inside", "on_surface", "on_top", "under"}
                ],
            )
        )
    return results


@app.get("/api/v1/rooms", response_model=list[RoomModel])
def get_rooms(
    dataset_id: str | None = None, home_id: str | None = None
) -> list[RoomModel]:
    _ds, repo = resolve_repository(dataset_id, home_id)
    latest = repo.latest_states()
    anchors = repo.anchors()
    results: list[RoomModel] = []
    for room in repo.rooms():
        room_id = room.get("room_id", 0)
        results.append(
            RoomModel(
                room_id=room_id,
                label=room.get("label", f"Room #{room_id}"),
                room_type=room.get("room_type", "Room"),
                centroid=room.get("centroid", []),
                anchors=[
                    a.get("label", f"Anchor #{a.get('anchor_id', 0)}")
                    for a in anchors
                    if a.get("room_id") == room_id
                ],
                objects=[
                    obj.get("label", f"Instance #{oid}")
                    for oid, obj in latest.items()
                    if obj.get("room_id") == room_id
                ],
                keyframe_count=int(room.get("keyframe_count", 0)),
            )
        )
    return results


@app.post("/api/v1/rooms/rename")
def rename_room(
    room_id: int = Query(..., description="Room to rename"),
    label: str = Query(..., min_length=1, max_length=40, description="New room name"),
    dataset_id: str | None = None,
    home_id: str | None = None,
) -> dict[str, Any]:
    """Rename one room (caregiver calibration) and persist it."""

    new_label = label.strip()
    if not new_label:
        raise HTTPException(status_code=422, detail="label must not be empty")
    ds, repo = resolve_repository(dataset_id, home_id)
    if not repo.ready:
        raise HTTPException(status_code=404, detail=f"No scene graph found for '{ds}'.")
    try:
        repo.rename_room(room_id, new_label)
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail=f"Room #{room_id} was not found in '{ds}'."
        ) from exc
    except DuplicateRoomLabelError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "status": "ok",
        "dataset_id": ds,
        "room_id": room_id,
        "label": new_label,
        "message": f"Room #{room_id} renamed to '{new_label}'.",
    }


def _matching_states(
    latest: dict[int, dict[str, Any]], item: str
) -> tuple[str, list[dict[str, Any]]]:
    """Target name and the states that match a query, by vocabulary id."""

    vocab = default_vocabulary()
    entry = vocab.resolve_query(QueryReasoningEngine.strip_room_words(item))
    if entry is not None:
        return entry.id, [s for s in latest.values() if _state_canonical(s) == entry.id]
    phrase = QueryReasoningEngine.item_phrase(item)
    return phrase, [
        s
        for s in latest.values()
        if phrase and _label_base(s.get("label", "")).lower() == phrase
    ]


def _crop_url(
    repo: JsonGraphRepository | StoreRepository, key: str, state: dict[str, Any]
) -> str | None:
    instance_id = state.get("instance_id")
    if isinstance(repo, StoreRepository):
        if state.get("evidence_id") is None:
            return None
        return f"/api/v1/crops/{instance_id}?home_id={key}"
    return f"/api/v1/crops/{instance_id}?dataset_id={key}"


@app.get("/api/v1/query", response_model=MemoryQueryResponse)
def query_memory(
    item: str = Query(..., description="Query, e.g. 'water bottle', 'my keys'"),
    dataset_id: str | None = None,
    home_id: str | None = None,
) -> MemoryQueryResponse:
    """Where is an item, according to this dataset's (or home's) memory."""

    ds, repo = resolve_repository(dataset_id, home_id)
    latest = repo.latest_states()
    target, matches = _matching_states(latest, item)
    room_filter = QueryReasoningEngine.extract_room_filter(item)

    # A patient may name the item only by its enrolled alias ("dad's cup"),
    # which is not a vocabulary class: resolve it to the enrolled instance's
    # canonical class before deciding the item is unknown.
    if not matches and isinstance(repo, StoreRepository):
        alias_id = resolve_alias(repo.store, item)
        if alias_id is not None:
            row = repo.store.one(
                "SELECT canonical FROM instance WHERE instance_id = ?", (alias_id,)
            )
            if row:
                target, matches = _matching_states(latest, row["canonical"])

    if not matches:
        available = sorted(
            {s.get("label", "") for s in latest.values() if s.get("label")}
        )
        if not repo.ready:
            reason = f"The scene graph for {ds} has not been generated yet."
        else:
            hint = (
                f" Available items in {ds}: {', '.join(available)}."
                if available
                else ""
            )
            reason = f"I couldn't locate any '{item}' in {ds}.{hint}"
        return MemoryQueryResponse(
            query=item, found=False, location_summary=reason, explanation=reason
        )

    if room_filter:
        room_matches = [
            m for m in matches if room_filter in str(m.get("room_label", "")).lower()
        ]
        if not room_matches:
            known_rooms = sorted(
                {str(m["room_label"]) for m in matches if m.get("room_label")}
            )
            where = (
                f" It was last seen in {', '.join(known_rooms)}." if known_rooms else ""
            )
            reason = f"I couldn't find any '{target}'{room_phrase(room_filter.title())}.{where}"
            return MemoryQueryResponse(
                query=item,
                found=False,
                item=item,
                location_summary=reason,
                explanation=reason,
            )
        matches = room_matches

    personal_ids = (
        personal_ids_for_query(repo.store, item, target)
        if isinstance(repo, StoreRepository)
        else ()
    )
    ranking = rank_candidates(
        matches,
        target,
        mode="full",
        cues=parse_query_cues(item),
        personal_ids=personal_ids,
    )
    candidates = ranking["candidates"]
    primary_id = candidates[0]["instance_id"] if candidates else None
    primary = next(
        (m for m in matches if m.get("instance_id") == primary_id), matches[0]
    )
    reasoning = QueryReasoningEngine.reason_spatio_temporal_state(
        target, primary, repo.events()
    )
    distance = primary.get("relative_distance")
    confidence = primary.get("confidence")
    if ranking["is_ambiguous"]:
        places = ", ".join(
            f"{c.get('label') or target} at "
            f"{c.get('anchor_label') or c.get('room_label') or 'unknown'}"
            for c in candidates
        )
        location_summary = (
            f"I found several possible {target}s: {places}. Which one do you mean?"
        )
    else:
        location_summary = reasoning["explanation"]
    return MemoryQueryResponse(
        query=item,
        found=True,
        item=item,
        instance_label=primary.get("label"),
        instance_id=primary.get("instance_id"),
        anchor_id=primary.get("anchor_id"),
        anchor_label=primary.get("anchor_label"),
        room_id=primary.get("room_id"),
        room_label=primary.get("room_label"),
        relation=reasoning["relation"],
        relation_certain=reasoning["relation_certain"],
        height_above_floor=primary.get("height_above_floor"),
        relative_distance_m=round(float(distance), 2) if distance is not None else None,
        location_summary=location_summary,
        explanation=reasoning["explanation"],
        last_seen_timestamp_s=primary.get("last_seen_timestamp"),
        last_seen_at=primary.get("last_seen_wallclock"),
        is_persistent_memory=reasoning["is_persistent_memory"],
        crop_url=_crop_url(repo, ds, primary),
        confidence=float(confidence) if confidence is not None else None,
        other_instances=[
            {
                "instance_id": m.get("instance_id"),
                "label": m.get("label"),
                "anchor": m.get("anchor_label"),
                "relation": m.get("relation"),
            }
            for m in matches
            if m.get("instance_id") != primary_id
        ],
        resolution_mode=ranking["resolution_mode"],
        is_ambiguous=ranking["is_ambiguous"],
        ambiguity_reason=ranking["ambiguity_reason"],
        candidates=[{**c, "crop_url": _crop_url(repo, ds, c)} for c in candidates],
    )


@app.get("/api/v1/timeline", response_model=list[TimelineEventModel])
def get_timeline(
    dataset_id: str | None = None,
    home_id: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> list[TimelineEventModel]:
    """Chronological events with one plain sentence each.

    For a home store, history older than the detail window comes back as
    ``tier="summarised"`` lines (``event_type="summary"``).
    """

    _ds, repo = resolve_repository(dataset_id, home_id)
    results: list[TimelineEventModel] = []
    if isinstance(repo, StoreRepository):
        try:
            summaries = repo.store.summaries(start, end)
            events = repo.events_between(start, end)
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail="start/end must be ISO-8601 with a timezone"
            ) from exc
        for line in summaries:
            results.append(
                TimelineEventModel(
                    event_id=f"summary_{line['summary_id']:06d}",
                    event_type="summary",
                    object=str(
                        line["sidecar"].get("label")
                        or line["subject_key"].split(":")[0].title()
                    ),
                    tier="summarised",
                    period_start=line["period_start"],
                    period_end=line["period_end"],
                    summary=line["text"],
                )
            )
    else:
        events = repo.events()
    for event in events:
        results.append(
            TimelineEventModel(
                event_id=str(event.get("event_id", "")),
                event_type=event.get("event_type", "state_change"),
                object=event.get("object", "Object"),
                source_relation=event.get("source_relation"),
                destination_relation=event.get("destination_relation"),
                source_anchor=event.get("source_anchor"),
                destination_anchor=event.get("destination_anchor"),
                source_room=event.get("source_room"),
                destination_room=event.get("destination_room"),
                start_time=float(event.get("start_time", 0.0)),
                end_time=float(event.get("end_time", 0.0)),
                start_wallclock=event.get("start_wallclock"),
                end_wallclock=event.get("end_wallclock"),
                activity_id=event.get("activity_id"),
                summary=event_summary(event),
            )
        )
    return results


class ActivityModel(BaseModel):
    activity_id: int
    room_id: int | None = None
    room_label: str | None = None
    start_at: str
    end_at: str
    event_count: int
    summary: str
    events: list[str] = Field(default_factory=list)
    tier: str = "detailed"


@app.get("/api/v1/activities", response_model=list[ActivityModel])
def get_activities(
    home_id: str = Query(..., description="Home whose activity history to list"),
    start: str | None = None,
    end: str | None = None,
) -> list[ActivityModel]:
    """Room stays with the object changes inside them (home store only)."""

    _home, repo = resolve_repository(None, home_id)
    try:
        rows = repo.store.activities(start, end)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail="start/end must be ISO-8601 with a timezone"
        ) from exc
    return [ActivityModel(**row) for row in rows]


@app.get("/api/v1/crops/{instance_id}")
def get_crop(
    instance_id: int, dataset_id: str | None = None, home_id: str | None = None
) -> Response:
    """Evidence crop of an object.

    With ``home_id`` this is the real JPEG behind the object's last-known
    state (404 when none exists). The per-dataset path still returns a
    labelled placeholder card until Milestone 3 replaces it.
    """

    if home_id:
        _home, repo = resolve_repository(None, home_id)
        state = repo.latest_states().get(instance_id)
        evidence_id = state.get("evidence_id") if state else None
        row = (
            repo.store.one(
                "SELECT path FROM evidence WHERE evidence_id = ?", (evidence_id,)
            )
            if evidence_id is not None
            else None
        )
        path = repo.store.dir / str(row["path"]) if row is not None else None
        if path is None or not path.is_file():
            raise HTTPException(
                status_code=404, detail="no evidence crop for this object"
            )
        return Response(content=path.read_bytes(), media_type="image/jpeg")

    ds = get_active_dataset(dataset_id)
    state = repository_for(ds).latest_states().get(instance_id)
    if state:
        title = state.get("label", f"Item #{instance_id}")
        relation = str(state.get("relation") or "tracked").replace("_", " ").title()
        anchor = state.get("anchor_label") or "no anchor"
        subtitle = f"{relation} @ {anchor}"
    else:
        title = f"Item #{instance_id}"
        subtitle = f"Tracked object in {ds}"
    title, subtitle, dataset = (html.escape(str(v)) for v in (title, subtitle, ds))
    svg = f"""<svg width="240" height="240" viewBox="0 0 240 240" xmlns="http://www.w3.org/2000/svg">
  <rect width="240" height="240" rx="24" fill="#0F172A"/>
  <circle cx="120" cy="90" r="48" fill="#14B8A6" fill-opacity="0.15" stroke="#14B8A6" stroke-width="2"/>
  <text x="120" y="165" font-family="system-ui, sans-serif" font-size="18" font-weight="bold" fill="#F8FAFC" text-anchor="middle">{title}</text>
  <text x="120" y="190" font-family="system-ui, sans-serif" font-size="13" fill="#94A3B8" text-anchor="middle">{subtitle}</text>
  <text x="120" y="219" font-family="system-ui, sans-serif" font-size="11" fill="#2DD4BF" text-anchor="middle">{dataset}</text>
</svg>"""
    return Response(content=svg, media_type="image/svg+xml")


@app.get("/api/v1/video/{dataset_id}")
def get_video(dataset_id: str) -> Response:
    from fastapi.responses import FileResponse

    ds = _validated(dataset_id)
    for candidate in (
        Path("data") / ds / f"{ds}.mp4",
        Path("data") / ds / "video.mp4",
        Path("data") / ds / f"{ds.lower()}.mp4",
    ):
        if candidate.exists():
            return FileResponse(candidate, media_type="video/mp4")
    return Response(content="Video not found", status_code=404)


# ---------------------------------------------------------------------------
# Live capture control (FR1.3). Configured by AEGIS_CAPTURE_DIR (the
# aegis-ingest --output-root) and AEGIS_CAPTURE_PAUSE_FILE (its --pause-file).
# TODO(M4 4.2): protect these mutating routes with caregiver auth.
# ---------------------------------------------------------------------------


class CaptureStatusModel(BaseModel):
    available: bool
    session_id: str | None = None
    status: str | None = None
    paused: bool = False
    frame_count: int | None = None
    last_frame_at: str | None = None


def _capture_settings() -> tuple[Path, Path] | None:
    capture_dir = os.getenv("AEGIS_CAPTURE_DIR")
    pause_file = os.getenv("AEGIS_CAPTURE_PAUSE_FILE")
    if not capture_dir or not pause_file:
        return None
    return Path(capture_dir), Path(pause_file)


def _capture_status() -> CaptureStatusModel:
    settings = _capture_settings()
    if settings is None:
        return CaptureStatusModel(available=False)
    capture_dir, pause_file = settings
    from aegis.ingestion.contracts import ContractError, load_session_manifest
    from aegis.ingestion.live_handoff import find_latest_live_session

    paused = pause_file.exists()
    session = find_latest_live_session(capture_dir)
    if session is None:
        return CaptureStatusModel(available=True, paused=paused)
    try:
        manifest = load_session_manifest(session)
    except (ContractError, OSError, ValueError):
        return CaptureStatusModel(
            available=True, paused=paused, session_id=session.name
        )
    state_path = session / "session_state.json"
    updated = None
    if state_path.exists():
        try:
            updated = json.loads(state_path.read_text(encoding="utf-8")).get(
                "updated_at"
            )
        except (OSError, json.JSONDecodeError):
            updated = None
    return CaptureStatusModel(
        available=True,
        session_id=str(manifest.get("session_id")),
        status=str(manifest.get("status")),
        paused=paused,
        frame_count=manifest.get("frame_count"),
        last_frame_at=updated or manifest.get("ended_at"),
    )


@app.get("/api/v1/capture/status", response_model=CaptureStatusModel)
def capture_status() -> CaptureStatusModel:
    return _capture_status()


def _require_capture() -> tuple[Path, Path]:
    settings = _capture_settings()
    if settings is None:
        raise HTTPException(
            status_code=503,
            detail="live capture control is not configured on this server "
            "(set AEGIS_CAPTURE_DIR and AEGIS_CAPTURE_PAUSE_FILE)",
        )
    return settings


@app.post("/api/v1/capture/pause", response_model=CaptureStatusModel)
def capture_pause() -> CaptureStatusModel:
    """Pause capture (the capture loop pauses while the pause file exists)."""

    _capture_dir, pause_file = _require_capture()
    pause_file.parent.mkdir(parents=True, exist_ok=True)
    pause_file.touch()
    return _capture_status()


@app.post("/api/v1/capture/resume", response_model=CaptureStatusModel)
def capture_resume() -> CaptureStatusModel:
    _capture_dir, pause_file = _require_capture()
    pause_file.unlink(missing_ok=True)
    return _capture_status()


# ---------------------------------------------------------------------------
# Demo simulator (AEGIS_ENABLE_SIMULATOR=1 only; changes live in memory)
# ---------------------------------------------------------------------------


@app.post(
    "/api/v1/simulate_transition",
    response_model=SimulateTransitionResponse,
    dependencies=[Depends(require_simulator)],
)
def simulate_transition(req: SimulateTransitionRequest) -> SimulateTransitionResponse:
    ds = get_active_dataset(req.dataset_id)
    repo = repository_for(ds)
    current = repo.latest_states().get(req.instance_id)
    if current is None:
        raise HTTPException(
            status_code=404, detail=f"Instance #{req.instance_id} is not in '{ds}'."
        )

    anchor_id, anchor_label = req.anchor_id, req.anchor_label
    if anchor_label is None and anchor_id is not None:
        match = next(
            (a for a in repo.anchors() if a.get("anchor_id") == anchor_id), None
        )
        anchor_label = match.get("label") if match else None
    old_relation = current.get("relation")
    old_anchor = current.get("anchor_label")
    timestamp = float(current.get("last_seen_timestamp") or 0.0) + 5.0

    new_state = dict(current)
    new_state.update(
        anchor_id=anchor_id,
        anchor_label=anchor_label,
        relation=req.new_relation,
        relation_certain=True,
        relative_distance=req.relative_distance_m,
        last_seen_timestamp=timestamp,
        timestamp=timestamp,
        is_active_view=req.is_active_view,
        is_in_hand=req.is_in_hand,
    )
    event_id = f"event_{len(repo.events()) + 1:04d}"
    event = {
        "event_id": event_id,
        "event_type": "state_change",
        "instance_id": req.instance_id,
        "object": current.get("label", f"Object #{req.instance_id}"),
        "source_relation": old_relation,
        "destination_relation": req.new_relation,
        "source_anchor": old_anchor,
        "destination_anchor": anchor_label,
        "source_room": current.get("room_label"),
        "destination_room": current.get("room_label"),
        "start_time": timestamp - 2.0,
        "end_time": timestamp,
    }
    repo.apply_simulated_state(req.instance_id, new_state, event)
    return SimulateTransitionResponse(
        message=(
            f"Simulated {event['object']} transition from {old_relation} "
            f"to {req.new_relation}."
        ),
        event_id=event_id,
        instance_id=req.instance_id,
        object_label=str(event["object"]),
        new_relation=req.new_relation,
        anchor_label=anchor_label,
        relative_distance_m=req.relative_distance_m,
        is_persistent_memory=not req.is_active_view,
    )


@app.post("/api/v1/reset", dependencies=[Depends(require_simulator)])
def reset_memory(dataset_id: str | None = None) -> dict[str, str]:
    """Drop simulated changes: reload the graph from disk."""

    ds = get_active_dataset(dataset_id)
    clear_cache(ds)
    repository_for(ds)
    return {"status": "ok", "message": f"Memory for {ds} reloaded from disk."}


def _preset(
    dataset_id: str | None,
    relation: str,
    *,
    anchor_index: int | None = 0,
    active: bool,
    in_hand: bool = False,
    distance: float = 0.2,
) -> SimulateTransitionResponse:
    ds = get_active_dataset(dataset_id)
    anchors = repository_for(ds).anchors()
    anchor = (
        anchors[anchor_index]
        if anchor_index is not None and len(anchors) > anchor_index
        else None
    )
    return simulate_transition(
        SimulateTransitionRequest(
            instance_id=1,
            new_relation=relation,
            anchor_id=anchor.get("anchor_id") if anchor else None,
            anchor_label=anchor.get("label") if anchor else None,
            relative_distance_m=distance,
            is_active_view=active,
            is_in_hand=in_hand,
            dataset_id=ds,
        )
    )


_SIM = {
    "response_model": SimulateTransitionResponse,
    "dependencies": [Depends(require_simulator)],
}


@app.get("/api/v1/simulate/floor", **_SIM)
def quick_simulate_floor(dataset_id: str | None = None) -> SimulateTransitionResponse:
    return _preset(dataset_id, "on_floor", active=True, distance=0.42)


@app.get("/api/v1/simulate/cabinet", **_SIM)
def quick_simulate_cabinet(dataset_id: str | None = None) -> SimulateTransitionResponse:
    return _preset(dataset_id, "inside", active=False, distance=0.09)


@app.get("/api/v1/simulate/in_hand", **_SIM)
def quick_simulate_in_hand(dataset_id: str | None = None) -> SimulateTransitionResponse:
    return _preset(
        dataset_id, "carried_by_user", anchor_index=None, active=False, in_hand=True
    )


@app.get("/api/v1/simulate/bottle_table1", **_SIM)
def quick_simulate_bottle_table1(
    dataset_id: str | None = None,
) -> SimulateTransitionResponse:
    return _preset(dataset_id, "on_surface", anchor_index=0, active=True, distance=0.09)


@app.get("/api/v1/simulate/bottle_occluded", **_SIM)
def quick_simulate_bottle_occluded(
    dataset_id: str | None = None,
) -> SimulateTransitionResponse:
    return _preset(
        dataset_id, "on_surface", anchor_index=0, active=False, distance=0.09
    )


@app.get("/api/v1/simulate/bottle_table2", **_SIM)
def quick_simulate_bottle_table2(
    dataset_id: str | None = None,
) -> SimulateTransitionResponse:
    return _preset(dataset_id, "on_surface", anchor_index=1, active=True, distance=0.05)


# ---------------------------------------------------------------------------
# Modal serverless wrapper
# ---------------------------------------------------------------------------

try:
    import modal

    from aegis.remote.modal_app import CPU_IMAGE, DATA_MOUNT, data_volume
    from aegis.remote.modal_app import app as modal_app

    @modal_app.function(image=CPU_IMAGE, volumes={DATA_MOUNT: data_volume})
    @modal.asgi_app()
    def fastapi_gateway() -> FastAPI:
        """Modal ASGI entrypoint for serverless deployment."""
        return app

except ImportError:
    pass


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("aegis.remote.api:app", host="0.0.0.0", port=8000, reload=True)
