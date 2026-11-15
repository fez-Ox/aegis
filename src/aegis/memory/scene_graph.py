"""Relative 4D Scene Graph (R4DSG): per-session object memory.

Rooms -> Anchors -> Objects. One session's lifted 3D boxes become:

* anchors (furniture) clustered from repeated observations,
* rooms from the wearer's trajectory (:mod:`aegis.memory.rooms`),
* object instances (:mod:`aegis.memory.association`),
* debounced state runs and the events between them (:mod:`aegis.memory.runs`),
  with each observation's relation decided in the gravity frame
  (:mod:`aegis.memory.relations`).

No rule depends on a particular video, object class or frame number. When
evidence is missing the graph says so (no anchor, ``in_room``, uncertain)
instead of inventing a location.

Serialisation: :meth:`Relative4DSceneGraph.as_dict` is schema v2 and holds
runs and last-known states only. The per-keyframe view used by the Rerun
recorder is produced separately by :meth:`Relative4DSceneGraph.timeline_dict`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any

import numpy as np

from aegis.core.config import MemoryBuildConfig
from aegis.core.models import BoundingBox3D
from aegis.core.timeutil import to_utc_iso
from aegis.core.vocabulary import Vocabulary, default_vocabulary
from aegis.geometry.gravity import GravityFrame
from aegis.memory.anchors import SpatialAnchor, anchor_shape, extract_spatial_anchors
from aegis.memory.association import associate_instances
from aegis.memory.relations import box_footprint, classify_relation
from aegis.memory.rooms import (
    RoomRegion,
    extract_room_regions,
    implicit_room_from_anchors,
    room_for_point,
)
from aegis.memory.runs import (
    CARRIED,
    Observation,
    StateRun,
    build_events,
    build_state_runs,
    is_hand_cue,
)

__all__ = [
    "GRAPH_SCHEMA_VERSION",
    "ObjectMemoryEntry",
    "Relative4DSceneGraph",
    "SpatialAnchor",
    "build_relative_4d_scene_graph",
    "extract_spatial_anchors",
]

GRAPH_SCHEMA_VERSION = 2


@dataclass
class ObjectMemoryEntry:
    """A persistent object-memory snapshot at one keyframe (visualisation view)."""

    frame_id: int
    timestamp: float
    instance_id: int
    label: str
    center: tuple[float, float, float]
    size: tuple[float, float, float]
    anchor_id: int | None
    anchor_label: str | None
    relative_vector: tuple[float, float, float]
    relative_distance: float
    relation: str
    is_active_view: bool
    last_seen_timestamp: float
    rotation: tuple[float, float, float, float] | None = None
    yaw: float | None = None
    is_in_hand: bool = False
    carrier: str | None = None
    in_hand_offset: tuple[float, float, float] | None = None
    room_id: int | None = None
    room_label: str | None = None
    confidence: float = 0.0
    relation_certain: bool = True
    height_above_floor: float | None = None

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "frame_id": self.frame_id,
            "timestamp": self.timestamp,
            "instance_id": self.instance_id,
            "label": self.label,
            "center": list(self.center),
            "size": list(self.size),
            "anchor_id": self.anchor_id,
            "anchor_label": self.anchor_label,
            "relative_vector": list(self.relative_vector),
            "relative_distance": self.relative_distance,
            "relation": self.relation,
            "is_active_view": self.is_active_view,
            "last_seen_timestamp": self.last_seen_timestamp,
            "is_in_hand": self.is_in_hand,
            "confidence": self.confidence,
            "relation_certain": self.relation_certain,
        }
        if self.carrier is not None:
            data["carrier"] = self.carrier
        if self.in_hand_offset is not None:
            data["in_hand_offset"] = list(self.in_hand_offset)
        if self.room_id is not None:
            data["room_id"] = self.room_id
        if self.room_label is not None:
            data["room_label"] = self.room_label
        if self.rotation is not None:
            data["rotation"] = list(self.rotation)
        if self.yaw is not None:
            data["yaw"] = self.yaw
        if self.height_above_floor is not None:
            data["height_above_floor"] = self.height_above_floor
        return data


@dataclass
class Relative4DSceneGraph:
    """One session's memory graph."""

    anchors: list[SpatialAnchor] = field(default_factory=list)
    rooms: list[RoomRegion] = field(default_factory=list)
    memory_timeline: dict[int, list[ObjectMemoryEntry]] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    state_runs: list[dict[str, Any]] = field(default_factory=list)
    room_visits: list[dict[str, Any]] = field(default_factory=list)
    latest_states: list[dict[str, Any]] = field(default_factory=list)
    gravity: GravityFrame = field(default_factory=GravityFrame.assumed)
    session: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Schema v2: structure, runs, events and last-known states."""

        return {
            "schema_version": GRAPH_SCHEMA_VERSION,
            "session": dict(self.session),
            "gravity": self.gravity.as_dict(),
            "anchors": [anchor.as_dict() for anchor in self.anchors],
            "rooms": [room.as_dict() for room in self.rooms],
            "state_runs": list(self.state_runs),
            "latest_states": list(self.latest_states),
            "events": list(self.events),
            "room_visits": list(self.room_visits),
        }

    def timeline_dict(self) -> dict[str, list[dict[str, Any]]]:
        """Per-keyframe entries (visualisation only; grows with keyframes)."""

        return {
            str(frame_id): [entry.as_dict() for entry in entries]
            for frame_id, entries in self.memory_timeline.items()
        }


# --------------------------------------------------------------------- poses
def _pose_by_frame(
    camera_poses: Sequence[Any] | Mapping[int, Any] | None,
) -> dict[int, tuple[np.ndarray, np.ndarray]]:
    raw_items: list[tuple[int, Any]] = []
    if camera_poses is None:
        return {}
    if isinstance(camera_poses, Mapping):
        for key, value in camera_poses.items():
            matrix = value["matrix"] if isinstance(value, Mapping) else value
            raw_items.append((int(key), matrix))
    else:
        for item in camera_poses:
            if hasattr(item, "frame_id"):
                matrix = getattr(item, "matrix", None)
                if matrix is not None:
                    raw_items.append((int(item.frame_id), matrix))
            elif isinstance(item, Mapping) and "frame_id" in item and "matrix" in item:
                raw_items.append((int(item["frame_id"]), item["matrix"]))
    poses: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    for frame_id, matrix in raw_items:
        m = np.asarray(matrix, dtype=np.float64)
        if m.shape == (4, 4):
            poses[frame_id] = (m[:3, :3], m[:3, 3])
    return poses


# -------------------------------------------------------------------- events
def _wearer_room_events(
    wearer_room_by_frame: Mapping[int, RoomRegion | None],
    timestamps_by_frame: Mapping[int, float],
    wallclock: Mapping[int, str],
) -> list[dict[str, Any]]:
    """Compress the camera wearer's room trajectory into room_change events."""

    events: list[dict[str, Any]] = []
    ordered = sorted(
        (fid for fid, room in wearer_room_by_frame.items() if room is not None),
        key=lambda fid: (timestamps_by_frame.get(fid, 0.0), fid),
    )
    for previous_frame, frame_id in pairwise(ordered):
        previous_room = wearer_room_by_frame[previous_frame]
        room = wearer_room_by_frame[frame_id]
        if previous_room is None or room is None:
            continue
        if room.room_id == previous_room.room_id:
            continue
        events.append(
            {
                "event_id": "",
                "event_type": "room_change",
                "instance_id": 0,
                "object": "Camera Wearer",
                "source_anchor": None,
                "destination_anchor": None,
                "source_room": previous_room.label,
                "destination_room": room.label,
                "source_room_id": previous_room.room_id,
                "destination_room_id": room.room_id,
                "source_relation": None,
                "destination_relation": None,
                "start_time": float(timestamps_by_frame.get(previous_frame, 0.0)),
                "end_time": float(timestamps_by_frame.get(frame_id, 0.0)),
                "start_wallclock": wallclock.get(previous_frame),
                "end_wallclock": wallclock.get(frame_id),
                "source_frame": previous_frame,
                "destination_frame": frame_id,
                "evidence_frames": [previous_frame, frame_id],
            }
        )
    return events


def _renumber_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort events chronologically and reassign stable event IDs."""

    ordered = sorted(
        events,
        key=lambda event: (
            float(event.get("start_time", 0.0)),
            event["event_type"] != "room_change",
            int(event.get("instance_id") or 0),
        ),
    )
    for index, event in enumerate(ordered):
        event["event_id"] = f"event_{index + 1:04d}"
    return ordered


def _room_visits(
    keyframes: Sequence[tuple[int, float]],
    wearer_room_by_frame: Mapping[int, RoomRegion | None],
    wallclock: Mapping[int, str],
) -> list[dict[str, Any]]:
    """The wearer's stays per room; one-keyframe blips join the previous stay."""

    raw: list[dict[str, Any]] = []
    for frame_id, timestamp in keyframes:
        room = wearer_room_by_frame.get(frame_id)
        if room is None:
            continue
        if raw and raw[-1]["room_id"] == room.room_id:
            raw[-1].update(end_frame=frame_id, end_time=timestamp)
            raw[-1]["keyframe_count"] += 1
        else:
            raw.append(
                {
                    "room_id": room.room_id,
                    "room_label": room.label,
                    "start_frame": frame_id,
                    "end_frame": frame_id,
                    "start_time": timestamp,
                    "end_time": timestamp,
                    "keyframe_count": 1,
                }
            )
    visits: list[dict[str, Any]] = []
    for visit in raw:
        if visits and (
            visit["keyframe_count"] < 2 or visits[-1]["room_id"] == visit["room_id"]
        ):
            visits[-1].update(end_frame=visit["end_frame"], end_time=visit["end_time"])
            visits[-1]["keyframe_count"] += visit["keyframe_count"]
        else:
            visits.append(dict(visit))
    for visit in visits:
        visit["start_wallclock"] = wallclock.get(visit["start_frame"])
        visit["end_wallclock"] = wallclock.get(visit["end_frame"])
    return visits


# ------------------------------------------------------------------- builder
def build_relative_4d_scene_graph(
    boxes_3d: Sequence[BoundingBox3D],
    all_frame_ids: Sequence[int],
    timestamps: Sequence[float],
    camera_poses: Sequence[Any] | Mapping[int, Any] | None = None,
    *,
    estimate_rooms: bool = True,
    zone_link_radius: float = 1.5,
    min_zone_keyframes: int = 3,
    vocabulary: Vocabulary | None = None,
    gravity: GravityFrame | None = None,
    wallclock_by_frame: Mapping[int, str] | None = None,
    settings: MemoryBuildConfig | None = None,
    assumed_camera_height: float = 1.4,
    min_gravity_confidence: float = 0.5,
) -> Relative4DSceneGraph:
    """Build one session's memory: anchors, rooms, instances, runs, events."""

    vocab = vocabulary or default_vocabulary()
    frame = gravity or GravityFrame.assumed()
    config = settings or MemoryBuildConfig()
    unit = frame.unit(assumed_camera_height, min_gravity_confidence)
    wallclock = {
        int(k): to_utc_iso(v) for k, v in (wallclock_by_frame or {}).items() if v
    }

    keyframes = sorted(
        ((int(f), float(t)) for f, t in zip(all_frame_ids, timestamps, strict=False)),
        key=lambda item: (item[1], item[0]),
    )
    timestamps_by_frame = dict(keyframes)
    pose_by_frame = _pose_by_frame(camera_poses)

    # Anchors and rooms -------------------------------------------------
    anchors = extract_spatial_anchors(
        boxes_3d,
        config.anchor_cluster_radius,
        vocabulary=vocab,
        gravity=frame,
        unit=unit,
    )
    rooms: list[RoomRegion] = []
    if estimate_rooms:
        rooms = extract_room_regions(
            camera_poses,
            boxes_3d,
            zone_link_radius=zone_link_radius,
            min_zone_keyframes=min_zone_keyframes,
            vocabulary=vocab,
            gravity=frame,
            unit=unit,
        )
    if not rooms:
        rooms = implicit_room_from_anchors(
            [anchor.center for anchor in anchors], gravity=frame, unit=unit
        )
    for anchor in anchors:
        bound = room_for_point(anchor.center, rooms, gravity=frame)
        if bound is not None:
            anchor.room_id, anchor.room_label = bound.room_id, bound.label
    anchors_by_id = {anchor.anchor_id: anchor for anchor in anchors}
    rooms_by_id = {room.room_id: room for room in rooms}
    wearer_room_by_frame = {
        fid: room_for_point(t_vec, rooms, gravity=frame)
        for fid, (_rot, t_vec) in pose_by_frame.items()
    }

    # Objects: only personal objects observed on a keyframe get memory.
    object_boxes = [
        box
        for box in boxes_3d
        if vocab.role(box.label) == "object"
        and not box.is_hand
        and int(box.frame_id) in timestamps_by_frame
    ]
    assignment, instances = associate_instances(
        object_boxes, vocabulary=vocab, unit=unit, settings=config
    )
    shapes = [anchor_shape(anchor, vocab) for anchor in anchors]
    observations: list[Observation] = []
    for index, box in enumerate(object_boxes):
        # Hook (Milestone 3, M8): when the result is uncertain, a VLM may be
        # asked one closed question about the evidence crop.
        relation = classify_relation(
            box_footprint(box, frame),
            shapes,
            frame,
            min_gravity_confidence=min_gravity_confidence,
            vertical_tolerance=config.vertical_tolerance,
        )
        observations.append(
            Observation(
                frame_id=int(box.frame_id),
                timestamp=timestamps_by_frame[int(box.frame_id)],
                instance_id=assignment[index],
                box=box,
                relation=relation.relation,
                anchor_id=relation.anchor_id,
                certain=relation.certain,
                hand_cue=is_hand_cue(box),
            )
        )

    def room_of(run: StateRun) -> int | None:
        if run.relation == CARRIED:
            room = wearer_room_by_frame.get(run.start_frame)
            return room.room_id if room else None
        anchor = anchors_by_id.get(run.anchor_id) if run.anchor_id else None
        if anchor is not None and anchor.room_id is not None:
            return anchor.room_id
        room = room_for_point(run.center, rooms, gravity=frame)
        return room.room_id if room else None

    runs_by_instance = build_state_runs(
        observations, settings=config, gravity=frame, room_of=room_of
    )
    names = {iid: track.display_name for iid, track in instances.items()}
    anchor_labels = {a.anchor_id: a.label for a in anchors}
    room_labels = {r.room_id: r.label for r in rooms}

    events = build_events(
        runs_by_instance,
        names=names,
        anchor_labels=anchor_labels,
        room_labels=room_labels,
        wallclock=wallclock.get,
    )
    events.extend(
        _wearer_room_events(wearer_room_by_frame, timestamps_by_frame, wallclock)
    )
    events = _renumber_events(events)

    timeline, latest = _timeline_and_latest(
        keyframes,
        runs_by_instance,
        names=names,
        canonical={iid: track.canonical for iid, track in instances.items()},
        appearance={iid: track.appearance for iid, track in instances.items()},
        anchors_by_id=anchors_by_id,
        rooms_by_id=rooms_by_id,
        wearer_room_by_frame=wearer_room_by_frame,
        pose_by_frame=pose_by_frame,
        wallclock=wallclock,
    )

    run_dicts: list[dict[str, Any]] = []
    for instance_id, runs in runs_by_instance.items():
        for run in runs:
            data = run.as_dict()
            data.update(
                instance_label=names[instance_id],
                anchor_label=anchor_labels.get(run.anchor_id),
                room_label=room_labels.get(run.room_id),
                start_wallclock=wallclock.get(run.start_frame),
                end_wallclock=wallclock.get(run.end_frame),
            )
            run_dicts.append(data)
    run_dicts.sort(key=lambda r: (r["start_time"], r["instance_id"]))

    session = {
        "dataset_id": None,
        "home_id": None,
        "started_at": wallclock.get(keyframes[0][0]) if keyframes else None,
        "ended_at": wallclock.get(keyframes[-1][0]) if keyframes else None,
        "time_source": "capture" if wallclock else "none",
        "keyframe_count": len(keyframes),
        "duration_seconds": (keyframes[-1][1] - keyframes[0][1]) if keyframes else 0.0,
        "first_timestamp": keyframes[0][1] if keyframes else 0.0,
    }
    return Relative4DSceneGraph(
        anchors=anchors,
        rooms=rooms,
        memory_timeline=timeline,
        events=events,
        state_runs=run_dicts,
        room_visits=_room_visits(keyframes, wearer_room_by_frame, wallclock),
        latest_states=latest,
        gravity=frame,
        session=session,
    )


def _run_at(runs: Sequence[StateRun], timestamp: float) -> StateRun:
    """The run covering ``timestamp``; a gap belongs to the earlier run."""

    chosen = runs[0]
    for run in runs:
        if run.start_time <= timestamp:
            chosen = run
        else:
            break
    return chosen


def _timeline_and_latest(
    keyframes: Sequence[tuple[int, float]],
    runs_by_instance: Mapping[int, Sequence[StateRun]],
    *,
    names: Mapping[int, str],
    canonical: Mapping[int, str],
    appearance: Mapping[int, tuple[float, ...] | None],
    anchors_by_id: Mapping[int, SpatialAnchor],
    rooms_by_id: Mapping[int, RoomRegion],
    wearer_room_by_frame: Mapping[int, RoomRegion | None],
    pose_by_frame: Mapping[int, tuple[np.ndarray, np.ndarray]],
    wallclock: Mapping[int, str],
) -> tuple[dict[int, list[ObjectMemoryEntry]], list[dict[str, Any]]]:
    """Per-keyframe entries (debounced state) and the last-known states."""

    timeline: dict[int, list[ObjectMemoryEntry]] = {fid: [] for fid, _t in keyframes}
    latest: list[dict[str, Any]] = []
    final_frame = keyframes[-1][0] if keyframes else None

    for instance_id, runs in runs_by_instance.items():
        observed = {obs.frame_id: obs for run in runs for obs in run.observations}
        ordered = sorted(observed.values(), key=lambda o: (o.timestamp, o.frame_id))
        first_time = ordered[0].timestamp
        last_obs = ordered[0]
        entry: ObjectMemoryEntry | None = None
        for frame_id, timestamp in keyframes:
            if timestamp < first_time:
                continue
            obs = observed.get(frame_id)
            if obs is not None:
                last_obs = obs
            run = _run_at(runs, timestamp)
            box = last_obs.box
            center = np.asarray(box.center, dtype=np.float64)
            carried = run.relation == CARRIED
            # While carried and out of view, the object moves with the
            # camera: keep its offset from the last frame it was seen in.
            if obs is None and carried:
                then = pose_by_frame.get(last_obs.frame_id)
                now = pose_by_frame.get(frame_id)
                if then is not None and now is not None:
                    r_then, t_then = then
                    r_now, t_now = now
                    center = r_now @ (r_then.T @ (center - t_then)) + t_now

            anchor = anchors_by_id.get(run.anchor_id) if run.anchor_id else None
            if anchor is not None:
                rel_vec = center - np.asarray(anchor.center, dtype=np.float64)
            else:
                rel_vec = np.zeros(3)
            room_id = run.room_id
            if carried:
                wearer_room = wearer_room_by_frame.get(frame_id)
                if wearer_room is not None:
                    room_id = wearer_room.room_id
            room = rooms_by_id.get(room_id) if room_id is not None else None
            entry = ObjectMemoryEntry(
                frame_id=frame_id,
                timestamp=timestamp,
                instance_id=instance_id,
                label=names[instance_id],
                center=tuple(float(v) for v in center),
                size=box.size,
                anchor_id=anchor.anchor_id if anchor else None,
                anchor_label=anchor.label if anchor else None,
                relative_vector=tuple(float(v) for v in rel_vec),
                relative_distance=float(np.linalg.norm(rel_vec)),
                relation=run.relation,
                is_active_view=obs is not None,
                last_seen_timestamp=last_obs.timestamp,
                rotation=box.rotation,
                yaw=box.yaw,
                is_in_hand=carried,
                carrier="camera_wearer" if carried else None,
                room_id=room.room_id if room else None,
                room_label=room.label if room else None,
                confidence=float(last_obs.box.confidence),
                relation_certain=run.certain,
                height_above_floor=run.height_above_floor,
            )
            timeline[frame_id].append(entry)

        if entry is None:
            continue
        last_run = runs[-1]
        latest.append(
            {
                "instance_id": instance_id,
                "label": names[instance_id],
                "canonical": canonical.get(instance_id),
                "relation": last_run.relation,
                "relation_certain": last_run.certain,
                "anchor_id": entry.anchor_id,
                "anchor_label": entry.anchor_label,
                "room_id": entry.room_id,
                "room_label": entry.room_label,
                "center": list(entry.center),
                "size": list(entry.size),
                "relative_distance": entry.relative_distance,
                "last_seen_timestamp": entry.last_seen_timestamp,
                "last_seen_wallclock": wallclock.get(ordered[-1].frame_id),
                "is_active_view": final_frame in observed,
                "is_in_hand": last_run.relation == CARRIED,
                "confidence": last_run.confidence,
                "height_above_floor": last_run.height_above_floor,
                "frame_id": ordered[-1].frame_id,
                "appearance": (
                    list(appearance[instance_id])
                    if appearance.get(instance_id) is not None
                    else None
                ),
            }
        )
    latest.sort(key=lambda state: state["instance_id"])
    return timeline, latest
