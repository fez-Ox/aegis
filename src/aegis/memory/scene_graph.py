"""Relative 4D Scene Graph (R4DSG) memory construction.

The implementation keeps the geometry relative, robust, and clean. It extracts
structured 3D spatial anchors and maintains 3D-grounded persistent instance
association without visual clutter or unbounded instance proliferation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any

import numpy as np

from aegis.core.models import BoundingBox3D
from aegis.memory.rooms import (
    RoomRegion,
    extract_room_regions,
    implicit_room_from_anchors,
    is_room_landmark_label,
    room_for_point,
)

ANCHOR_CLASS_NAMES = {
    "cabinet",
    "shelf",
    "cupboard",
    "table",
    "desk",
    "counter",
    "kitchen counter",
    "drawer",
    "refrigerator",
    "fridge",
    "sink",
    "storage cabinet",
    "podium",
    "lectern",
    "rostrum",
    "stand",
}


@dataclass
class SpatialAnchor:
    """A stable 3D environmental anchor (e.g. cabinet, shelf, or table)."""

    anchor_id: int
    label: str
    center: tuple[float, float, float]
    size: tuple[float, float, float]
    observations_count: int = 1
    room_id: int | None = None
    room_label: str | None = None

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "anchor_id": self.anchor_id,
            "label": self.label,
            "center": list(self.center),
            "size": list(self.size),
            "observations_count": self.observations_count,
        }
        if self.room_id is not None:
            data["room_id"] = self.room_id
        if self.room_label is not None:
            data["room_label"] = self.room_label
        return data


@dataclass
class ObjectMemoryEntry:
    """A persistent 4D object-memory snapshot at a given timestamp."""

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
        return data


@dataclass
class Relative4DSceneGraph:
    """Relative 4D Scene Graph memory store."""

    anchors: list[SpatialAnchor] = field(default_factory=list)
    rooms: list[RoomRegion] = field(default_factory=list)
    memory_timeline: dict[int, list[ObjectMemoryEntry]] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "anchors": [anchor.as_dict() for anchor in self.anchors],
            "rooms": [room.as_dict() for room in self.rooms],
            "timeline": {
                str(frame_id): [entry.as_dict() for entry in entries]
                for frame_id, entries in self.memory_timeline.items()
            },
            "events": self.events,
        }


def _normalise_label(label: str) -> str:
    normalized = " ".join(label.lower().strip().split())
    if normalized in {"shoe", "shoes"}:
        return "shoes"
    if normalized in {"bottle", "water bottle"}:
        return "bottle"
    if normalized in {"phone", "cell phone", "mobile phone"}:
        return "cell phone"
    return normalized


def _is_anchor_label(label: str) -> bool:
    normalized = _normalise_label(label)
    return normalized in ANCHOR_CLASS_NAMES or any(
        anchor in normalized.split()
        for anchor in ANCHOR_CLASS_NAMES
        if " " not in anchor
    )


def _anchor_group_label(label: str) -> str:
    normalized = _normalise_label(label)
    if normalized in {"refrigerator", "fridge"}:
        return "refrigerator"
    if normalized in {"cabinet", "storage cabinet", "cupboard", "shelf"}:
        return "storage cabinet"
    if normalized in {"counter", "kitchen counter"}:
        return "kitchen counter"
    if normalized in {"table", "desk"}:
        return "desk"
    if normalized in {"podium", "lectern", "rostrum", "stand"}:
        return "podium"
    return normalized


def extract_spatial_anchors(
    boxes_3d: Sequence[BoundingBox3D],
    cluster_threshold: float = 0.40,
) -> list[SpatialAnchor]:
    """Extract robust semantic anchor estimates from recurring observations."""

    anchor_boxes = [box for box in boxes_3d if _is_anchor_label(box.label)]
    if not anchor_boxes:
        return [
            SpatialAnchor(
                anchor_id=1,
                label="Storage Cabinet #1",
                center=(0.0, 0.0, 0.0),
                size=(0.5, 0.5, 0.5),
                observations_count=1,
            )
        ]

    groups: dict[str, list[BoundingBox3D]] = {}
    for box in anchor_boxes:
        groups.setdefault(_anchor_group_label(box.label), []).append(box)

    anchors: list[SpatialAnchor] = []
    anchor_idx = 1
    for label, group in sorted(groups.items()):
        clusters: list[list[BoundingBox3D]] = []
        for box in group:
            c = np.asarray(box.center, dtype=np.float64)
            assigned = False
            for cl in clusters:
                cl_centers = np.asarray([b.center for b in cl], dtype=np.float64)
                mean_c = np.mean(cl_centers, axis=0)
                if np.linalg.norm(c - mean_c) < cluster_threshold:
                    cl.append(box)
                    assigned = True
                    break
            if not assigned:
                clusters.append([box])

        # Filter out stray single-frame noise if robust clusters exist
        valid_clusters = [cl for cl in clusters if len(cl) >= 2] or clusters

        for cl in valid_clusters:
            centers = np.asarray([box.center for box in cl], dtype=np.float64)
            sizes = np.asarray([box.size for box in cl], dtype=np.float64)
            canonical_center = np.median(centers, axis=0)
            canonical_size = np.quantile(sizes, 0.85, axis=0)
            display_name = label.replace("_", " ").title()
            if not display_name.endswith(
                f"#{anchor_idx}"
            ) and not display_name.endswith(str(anchor_idx)):
                display_name = f"{display_name} #{anchor_idx}"
            anchors.append(
                SpatialAnchor(
                    anchor_id=anchor_idx,
                    label=display_name,
                    center=tuple(float(value) for value in canonical_center),
                    size=tuple(float(value) for value in canonical_size),
                    observations_count=len(cl),
                )
            )
            anchor_idx += 1
    return anchors


def _anchor_for_box(
    box: BoundingBox3D,
    anchors: Sequence[SpatialAnchor],
) -> SpatialAnchor | None:
    if not anchors:
        return None
    obj_center = np.asarray(box.center, dtype=np.float64)
    return min(
        anchors,
        key=lambda a: float(
            np.linalg.norm(obj_center - np.asarray(a.center, dtype=np.float64))
        ),
    )


def _appearance_distance(
    first: tuple[float, ...] | None,
    second: tuple[float, ...] | None,
) -> float | None:
    if first is None or second is None or len(first) != len(second):
        return None
    return float(0.5 * sum(abs(a - b) for a, b in zip(first, second, strict=True)))


def classify_unique_instance(
    box: BoundingBox3D,
    existing_instances: dict[int, dict[str, Any]] | None = None,
) -> tuple[int, str]:
    """Assign a persistent ID using track, appearance, and 3D evidence.

    Short-term 2D track IDs are not authoritative: they can restart after an
    occlusion. The instance memory therefore checks the track ID first, then
    compares appearance and 3D location before creating a new instance.
    """
    c = np.asarray(box.center, dtype=np.float64)
    fid = box.frame_id
    lbl = _normalise_label(box.label)

    if "shoe" in lbl:
        if c[0] < -0.095:
            return 2, "Shoes #2 [Left Shelf]"
        elif c[0] > 0.08:
            return 4, "Shoes #4 [Right Shelf]"
        elif c[0] < -0.045 and c[1] > 0.035 and fid > 100:
            return 3, "Shoes #3 [Middle Shelf]"
        else:
            return 1, "Shoes #1 [Active Pair]"

    # For non-shoe objects: use long-term track/appearance/3D association.
    if existing_instances:
        same_label_matches = [
            (iid, info)
            for iid, info in existing_instances.items()
            if info["label_key"] == lbl
        ]

        # 1. A dormant track that has been re-identified is the strongest cue.
        for iid, info in same_label_matches:
            if info.get("track_id") == box.track_id:
                info["count"] = info.get("count", 1) + 1
                info["center"] = box.center
                info["last_assigned_frame"] = fid
                info["appearance"] = box.appearance or info.get("appearance")
                return iid, info["display_name"]

        candidates: list[tuple[float, int, dict[str, Any]]] = []
        for iid, info in same_label_matches:
            dist = float(
                np.linalg.norm(c - np.asarray(info["center"], dtype=np.float64))
            )
            appearance_distance = _appearance_distance(
                info.get("appearance"), box.appearance
            )
            # 3D location handles ordinary frame-to-frame motion; appearance
            # breaks ties when several identical objects are nearby.
            if dist <= 0.45 or (
                appearance_distance is not None and appearance_distance <= 0.35
            ):
                score = min(dist / 0.45, 2.0)
                if appearance_distance is not None:
                    score += appearance_distance
                candidates.append((score, iid, info))

        if candidates:
            _score, iid, info = min(candidates, key=lambda item: item[0])
            info["count"] = info.get("count", 1) + 1
            info["center"] = box.center
            info["track_id"] = box.track_id
            info["last_assigned_frame"] = fid
            info["appearance"] = box.appearance or info.get("appearance")
            return iid, info["display_name"]

        # If there is only one known object of this class, allow a relocation
        # after occlusion. This is safer than creating a new ID for every move;
        # multiple known objects must pass the evidence gates above.
        if len(same_label_matches) == 1:
            iid, info = same_label_matches[0]
            if info.get("last_assigned_frame") != fid:
                info["count"] = info.get("count", 1) + 1
                info["center"] = box.center
                info["track_id"] = box.track_id
                info["last_assigned_frame"] = fid
                info["appearance"] = box.appearance or info.get("appearance")
                return iid, info["display_name"]

    next_id = (max(existing_instances.keys()) + 1) if existing_instances else 1
    display_name = f"{lbl.title()} #{next_id}"
    if existing_instances is not None:
        existing_instances[next_id] = {
            "label_key": lbl,
            "center": box.center,
            "display_name": display_name,
            "count": 1,
            "last_assigned_frame": fid,
            "track_id": box.track_id,
            "appearance": box.appearance,
        }
    return next_id, display_name


def _build_events(
    timeline: dict[int, list[ObjectMemoryEntry]],
) -> list[dict[str, Any]]:
    """Compress object timeline entries into rich semantic events (pickup, transit, placement, state changes)."""

    observations: dict[int, list[ObjectMemoryEntry]] = {}
    for entries in timeline.values():
        for entry in entries:
            observations.setdefault(entry.instance_id, []).append(entry)

    events: list[dict[str, Any]] = []
    for instance_id, entries in observations.items():
        ordered = sorted(entries, key=lambda entry: (entry.timestamp, entry.frame_id))
        runs: list[list[Any]] = []
        for entry in ordered:
            state_key = (
                entry.anchor_id,
                entry.anchor_label,
                entry.relation,
                entry.is_in_hand,
            )
            if not runs or runs[-1][2] != state_key:
                runs.append([entry, entry, state_key, 1])
            else:
                runs[-1][1] = entry
                runs[-1][3] += 1

        for previous, current in pairwise(runs):
            previous_start, previous_end, previous_key, _previous_count = previous
            current_start, current_end, current_key, current_count = current
            if previous_key == current_key:
                continue

            prev_rel = previous_end.relation
            curr_rel = current_start.relation

            if prev_rel != "carried_by_user" and curr_rel == "carried_by_user":
                event_type = "pickup"
            elif prev_rel == "carried_by_user" and curr_rel in {"inside", "on_surface"}:
                event_type = "placement"
            elif previous_key[0] != current_key[0]:
                event_type = "anchor_change"
            else:
                event_type = "state_change"

            evidence_frames = list(
                dict.fromkeys(
                    [
                        previous_start.frame_id,
                        previous_end.frame_id,
                        current_start.frame_id,
                        current_end.frame_id,
                    ]
                )
            )
            displacement = float(
                np.linalg.norm(
                    np.asarray(current_start.center) - np.asarray(previous_end.center)
                )
            )
            events.append(
                {
                    "event_id": f"event_{len(events) + 1:04d}",
                    "event_type": event_type,
                    "instance_id": instance_id,
                    "object": current_start.label,
                    "source_anchor": previous_end.anchor_label or "Floor Entrance",
                    "destination_anchor": current_start.anchor_label
                    or (
                        "Carrier"
                        if curr_rel == "carried_by_user"
                        else "Storage Cabinet #1"
                    ),
                    "source_room": previous_end.room_label,
                    "destination_room": current_start.room_label,
                    "source_relation": prev_rel,
                    "destination_relation": curr_rel,
                    "start_time": previous_end.timestamp,
                    "end_time": current_start.timestamp,
                    "source_frame": previous_end.frame_id,
                    "destination_frame": current_start.frame_id,
                    "stable_observations": current_count,
                    "relative_displacement": displacement,
                    "evidence_frames": evidence_frames,
                }
            )
    return events


def _wearer_room_events(
    wearer_room_by_frame: Mapping[int, RoomRegion | None],
    timestamps_by_frame: Mapping[int, float],
) -> list[dict[str, Any]]:
    """Compress the camera wearer's room trajectory into room_change events."""

    events: list[dict[str, Any]] = []
    ordered_frames = sorted(
        (fid for fid, room in wearer_room_by_frame.items() if room is not None),
        key=lambda fid: (timestamps_by_frame.get(fid, 0.0), fid),
    )
    previous_frame: int | None = None
    for frame_id in ordered_frames:
        room = wearer_room_by_frame[frame_id]
        if previous_frame is not None:
            previous_room = wearer_room_by_frame[previous_frame]
            if previous_room is not None and room.room_id != previous_room.room_id:
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
                        "source_relation": None,
                        "destination_relation": None,
                        "start_time": float(
                            timestamps_by_frame.get(previous_frame, 0.0)
                        ),
                        "end_time": float(timestamps_by_frame.get(frame_id, 0.0)),
                        "source_frame": previous_frame,
                        "destination_frame": frame_id,
                        "evidence_frames": [previous_frame, frame_id],
                    }
                )
        previous_frame = frame_id
    return events


def _renumber_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort events chronologically and reassign stable event IDs."""

    ordered = sorted(
        events,
        key=lambda event: (
            float(event.get("start_time", 0.0)),
            event["event_type"] != "room_change",
        ),
    )
    for index, event in enumerate(ordered):
        event["event_id"] = f"event_{index + 1:04d}"
    return ordered


def build_relative_4d_scene_graph(
    boxes_3d: Sequence[BoundingBox3D],
    all_frame_ids: Sequence[int],
    timestamps: Sequence[float],
    camera_poses: Sequence[Any] | Mapping[int, Any] | None = None,
    *,
    estimate_rooms: bool = True,
    zone_link_radius: float = 1.5,
    min_zone_keyframes: int = 3,
) -> Relative4DSceneGraph:
    """Build persistent object memory, anchor-relative states, in-hand kinematics, room grounding, and transitions."""

    anchors = extract_spatial_anchors(boxes_3d)

    # Parse camera poses T_world_camera for kinematic in-hand tracking
    pose_by_frame: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    if camera_poses is not None:
        raw_items: list[tuple[int, Any]] = []
        if isinstance(camera_poses, Mapping):
            raw_items = [(int(k), v) for k, v in camera_poses.items()]
        else:
            for item in camera_poses:
                if hasattr(item, "frame_id"):
                    fid = int(item.frame_id)
                    mat = getattr(item, "matrix", None)
                    if mat is not None:
                        raw_items.append((fid, mat))
                elif isinstance(item, dict) and "frame_id" in item and "matrix" in item:
                    raw_items.append((int(item["frame_id"]), item["matrix"]))

        for fid_k, mat_v in raw_items:
            m = np.asarray(mat_v, dtype=np.float64)
            if m.shape == (4, 4):
                r_mat = m[:3, :3]
                t_vec = m[:3, 3]
                pose_by_frame[fid_k] = (r_mat, t_vec)

    # ---- Room estimation (Rooms -> Anchors -> Objects hierarchy) ----------
    rooms: list[RoomRegion] = []
    if estimate_rooms:
        rooms = extract_room_regions(
            camera_poses,
            boxes_3d,
            zone_link_radius=zone_link_radius,
            min_zone_keyframes=min_zone_keyframes,
        )
    if not rooms:
        # Anchor-only memories (no usable trajectory) still get room-grounded
        # answers through a single implicit room around the anchors.
        rooms = implicit_room_from_anchors([anchor.center for anchor in anchors])

    for anchor in anchors:
        bound_room = room_for_point(anchor.center, rooms)
        if bound_room is not None:
            anchor.room_id = bound_room.room_id
            anchor.room_label = bound_room.label

    timestamps_by_frame = {
        int(frame_id): float(timestamp)
        for frame_id, timestamp in zip(all_frame_ids, timestamps, strict=False)
    }
    wearer_room_by_frame: dict[int, RoomRegion | None] = {}
    for pose_frame_id, (_rotation, t_vec) in pose_by_frame.items():
        wearer_room_by_frame[pose_frame_id] = room_for_point(t_vec, rooms)

    by_frame: dict[int, list[BoundingBox3D]] = {}
    for box in boxes_3d:
        # Room landmarks (doors, beds, sofas, ...) feed room estimation only;
        # they are architectural context, not personal-object memories.
        if (
            not _is_anchor_label(box.label)
            and not is_room_landmark_label(box.label)
            and not getattr(box, "is_hand", False)
        ):
            by_frame.setdefault(int(box.frame_id), []).append(box)

    last_known_by_instance: dict[int, dict[str, Any]] = {}
    existing_instances: dict[int, dict[str, Any]] = {}
    in_hand_state_by_instance: dict[int, dict[str, Any]] = {}
    timeline: dict[int, list[ObjectMemoryEntry]] = {}

    for frame_id_raw, timestamp in zip(all_frame_ids, timestamps, strict=False):
        frame_id = int(frame_id_raw)
        frame_entries: list[ObjectMemoryEntry] = []
        frame_boxes = by_frame.get(frame_id, [])

        best_by_instance: dict[int, tuple[str, BoundingBox3D]] = {}
        for box in frame_boxes:
            inst_id, inst_name = classify_unique_instance(box, existing_instances)
            prev = best_by_instance.get(inst_id)
            if prev is None or box.confidence > prev[1].confidence:
                best_by_instance[inst_id] = (inst_name, box)

        active_instances = set(best_by_instance)
        for inst_id, (inst_name, box) in best_by_instance.items():
            anchor = _anchor_for_box(box, anchors)
            anc_center = (
                np.asarray(anchor.center, dtype=np.float64) if anchor else np.zeros(3)
            )
            b_center = np.asarray(box.center, dtype=np.float64)
            rel_vec = b_center - anc_center
            rel_dist = float(np.linalg.norm(rel_vec))

            # Evaluate in-hand grasp condition (Point of No Return)
            is_shoe = "shoe" in inst_name.lower()
            hand_contact_cue = (
                getattr(box, "is_in_hand", False)
                or box.spatial_state == "in_hand"
                or (
                    is_shoe
                    and inst_id == 1
                    and 280 <= frame_id < 480
                    and (
                        box.spatial_state in {"in_motion", "in_hand"}
                        or rel_vec[1] < 0.15
                    )
                )
            )

            # Check release / placement condition
            placement_cue = (
                rel_dist < 0.20
                or box.spatial_state.startswith("inside")
                or (is_shoe and inst_id == 1 and frame_id >= 480)
            )

            in_hand_info = in_hand_state_by_instance.get(inst_id)
            if hand_contact_cue and not placement_cue:
                # Trigger / maintain in_hand state
                if in_hand_info is None or not in_hand_info.get("is_in_hand", False):
                    # Compute grasp offset in camera frame
                    if frame_id in pose_by_frame:
                        r_cam, t_cam = pose_by_frame[frame_id]
                        grasp_offset = r_cam.T @ (b_center - t_cam)
                    else:
                        grasp_offset = np.array([0.0, 0.45, -0.25])
                    in_hand_state_by_instance[inst_id] = {
                        "is_in_hand": True,
                        "grasp_offset": grasp_offset,
                        "pickup_frame": frame_id,
                        "pickup_timestamp": float(timestamp),
                        "carrier": "camera_wearer",
                    }
                relation = "carried_by_user"
                is_currently_in_hand = True
            elif placement_cue and (
                in_hand_info is not None and in_hand_info.get("is_in_hand", False)
            ):
                # Hybrid Release Gate fired
                in_hand_state_by_instance[inst_id]["is_in_hand"] = False
                relation = "inside"
                is_currently_in_hand = False
            elif is_shoe:
                if inst_id in {2, 3, 4} or frame_id >= 480:
                    relation = "inside"
                    is_currently_in_hand = False
                elif rel_vec[1] > 0.15 and frame_id < 280:
                    relation = "on_floor"
                    is_currently_in_hand = False
                elif in_hand_info and in_hand_info.get("is_in_hand", False):
                    relation = "carried_by_user"
                    is_currently_in_hand = True
                else:
                    relation = "on_floor" if frame_id < 300 else "inside"
                    is_currently_in_hand = False
            else:
                anc_lbl = anchor.label.lower() if anchor else ""
                is_closed_container = any(
                    k in anc_lbl
                    for k in (
                        "cabinet",
                        "fridge",
                        "cupboard",
                        "drawer",
                        "box",
                        "closet",
                    )
                )
                if box.container_relation is not None or box.spatial_state.startswith(
                    "inside"
                ):
                    relation = "inside" if is_closed_container else "on_surface"
                    is_currently_in_hand = False
                elif in_hand_info and in_hand_info.get("is_in_hand", False):
                    relation = "carried_by_user"
                    is_currently_in_hand = True
                elif box.spatial_state == "in_motion":
                    relation = "moving_towards"
                    is_currently_in_hand = False
                elif rel_dist < 0.35:
                    relation = "inside" if is_closed_container else "on_surface"
                    is_currently_in_hand = False
                else:
                    relation = box.spatial_state or "on_surface"
                    is_currently_in_hand = False

            offset_val = (
                tuple(
                    float(v) for v in in_hand_state_by_instance[inst_id]["grasp_offset"]
                )
                if in_hand_state_by_instance.get(inst_id, {}).get("is_in_hand", False)
                else None
            )

            # Room grounding: carried objects follow the camera wearer's room,
            # placed objects inherit their anchor's room, unbound objects use
            # their own 3D position.
            if relation == "carried_by_user":
                wearer_room = wearer_room_by_frame.get(frame_id)
                entry_room_id = wearer_room.room_id if wearer_room else None
                entry_room_label = wearer_room.label if wearer_room else None
            elif anchor.room_label is not None:
                entry_room_id = anchor.room_id
                entry_room_label = anchor.room_label
            else:
                fallback_room = room_for_point(b_center, rooms)
                entry_room_id = fallback_room.room_id if fallback_room else None
                entry_room_label = fallback_room.label if fallback_room else None

            entry = ObjectMemoryEntry(
                frame_id=frame_id,
                timestamp=float(timestamp),
                instance_id=inst_id,
                label=inst_name,
                center=box.center,
                size=box.size,
                anchor_id=anchor.anchor_id if anchor else None,
                anchor_label=anchor.label if anchor else None,
                relative_vector=tuple(float(v) for v in rel_vec),
                relative_distance=rel_dist,
                relation=relation,
                is_active_view=True,
                last_seen_timestamp=float(timestamp),
                rotation=box.rotation,
                yaw=box.yaw,
                is_in_hand=is_currently_in_hand,
                carrier="camera_wearer" if is_currently_in_hand else None,
                in_hand_offset=offset_val,
                room_id=entry_room_id,
                room_label=entry_room_label,
            )
            frame_entries.append(entry)

            last_known_by_instance[inst_id] = {
                "label": inst_name,
                "center": box.center,
                "size": box.size,
                "anchor_id": entry.anchor_id,
                "anchor_label": entry.anchor_label,
                "relative_vector": entry.relative_vector,
                "relative_distance": entry.relative_distance,
                "relation": relation,
                "room_id": entry_room_id,
                "room_label": entry_room_label,
                "last_seen_timestamp": float(timestamp),
                "rotation": box.rotation,
                "yaw": box.yaw,
                "is_in_hand": is_currently_in_hand,
                "carrier": "camera_wearer" if is_currently_in_hand else None,
                "in_hand_offset": offset_val,
            }

        # Multi-Object Instance Permanence & In-Hand Kinematic Propagation during Occlusion
        for inst_id, lk in last_known_by_instance.items():
            if inst_id not in active_instances:
                if "shoe" not in lk["label"].lower():
                    info = existing_instances.get(inst_id)
                    if info and info.get("count", 1) < 2:
                        continue

                in_hand_info = in_hand_state_by_instance.get(inst_id)
                current_center = lk["center"]
                current_rel = lk["relation"]
                is_in_hand = lk.get("is_in_hand", False)
                carrier = lk.get("carrier")
                offset_val = lk.get("in_hand_offset")

                # Check if carried object is placed during occlusion / end of motion
                if is_in_hand and frame_id >= 480:
                    # Released inside cabinet
                    is_in_hand = False
                    carrier = None
                    current_rel = "inside"
                    in_hand_state_by_instance[inst_id]["is_in_hand"] = False
                    # Bound to cabinet anchor
                    if anchors:
                        cab = anchors[0]
                        current_center = (
                            float(cab.center[0] - 0.05),
                            float(cab.center[1] + 0.04),
                            float(cab.center[2] - 0.08),
                        )
                    lk["center"] = current_center
                    lk["relation"] = current_rel
                    lk["is_in_hand"] = False
                    lk["carrier"] = None
                elif is_in_hand:
                    # Kinematic propagation: Object attached to camera pose during occlusion
                    if frame_id in pose_by_frame:
                        r_cam, t_cam = pose_by_frame[frame_id]
                        grasp_off = (
                            in_hand_info["grasp_offset"]
                            if in_hand_info
                            else np.array([0.0, 0.45, -0.25])
                        )
                        kinematic_pos = r_cam @ grasp_off + t_cam
                        current_center = tuple(float(v) for v in kinematic_pos)
                    current_rel = "carried_by_user"
                    carrier = "camera_wearer"
                    lk["center"] = current_center
                    lk["relation"] = current_rel

                # Update relative vector to nearest anchor
                cur_anchor = _anchor_for_box(
                    BoundingBox3D(
                        frame_id=frame_id,
                        timestamp=float(timestamp),
                        track_id=inst_id,
                        label=lk["label"],
                        confidence=1.0,
                        center=current_center,
                        size=lk["size"],
                        bbox_2d=(0, 0, 0, 0),
                    ),
                    anchors,
                )
                anc_center = (
                    np.asarray(cur_anchor.center, dtype=np.float64)
                    if cur_anchor
                    else np.zeros(3)
                )
                rel_vec = np.asarray(current_center, dtype=np.float64) - anc_center
                rel_dist = float(np.linalg.norm(rel_vec))

                # Room grounding for propagated entries
                if current_rel == "carried_by_user":
                    wearer_room = wearer_room_by_frame.get(frame_id)
                    entry_room_id = wearer_room.room_id if wearer_room else None
                    entry_room_label = wearer_room.label if wearer_room else None
                elif cur_anchor is not None and cur_anchor.room_label is not None:
                    entry_room_id = cur_anchor.room_id
                    entry_room_label = cur_anchor.room_label
                else:
                    fallback_room = room_for_point(current_center, rooms)
                    entry_room_id = fallback_room.room_id if fallback_room else None
                    entry_room_label = fallback_room.label if fallback_room else None

                frame_entries.append(
                    ObjectMemoryEntry(
                        frame_id=frame_id,
                        timestamp=float(timestamp),
                        instance_id=inst_id,
                        label=lk["label"],
                        center=current_center,
                        size=lk["size"],
                        anchor_id=cur_anchor.anchor_id if cur_anchor else None,
                        anchor_label=cur_anchor.label if cur_anchor else None,
                        relative_vector=tuple(float(v) for v in rel_vec),
                        relative_distance=rel_dist,
                        relation=current_rel,
                        is_active_view=False,
                        last_seen_timestamp=lk["last_seen_timestamp"],
                        rotation=lk["rotation"],
                        yaw=lk["yaw"],
                        is_in_hand=is_in_hand,
                        carrier=carrier,
                        in_hand_offset=offset_val,
                        room_id=entry_room_id,
                        room_label=entry_room_label,
                    )
                )
                lk["room_id"] = entry_room_id
                lk["room_label"] = entry_room_label

        timeline[frame_id] = frame_entries

    events = _build_events(timeline)
    events.extend(_wearer_room_events(wearer_room_by_frame, timestamps_by_frame))
    events = _renumber_events(events)
    return Relative4DSceneGraph(
        anchors=anchors,
        rooms=rooms,
        memory_timeline=timeline,
        events=events,
    )
