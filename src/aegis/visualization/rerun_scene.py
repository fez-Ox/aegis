"""Rerun recording of a processed dataset: video, 3D memory, rooms, trajectory.

Moved out of :mod:`aegis.remote.workers`, which keeps only stage
orchestration. Coordinates are the raw VGGT-Ω world frame; "up" for room
pillars comes from the session gravity frame.
"""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from aegis.core.paths import dataset_paths
from aegis.remote.workers import (
    _config,
    _read_json,
    _record_benchmark_stats,
    _require_metadata,
    _write_json,
)

TRACK_PALETTE = [
    [34, 197, 94],  # Emerald Green
    [59, 130, 246],  # Vibrant Blue
    [239, 68, 68],  # Red
    [234, 179, 8],  # Amber
    [168, 85, 247],  # Purple
    [236, 72, 153],  # Pink
    [20, 184, 166],  # Teal
    [249, 115, 22],  # Orange
]


def _track_color(track_id: int) -> list[int]:
    return TRACK_PALETTE[(track_id - 1) % len(TRACK_PALETTE)]


ROOM_PALETTE = [
    [59, 130, 246],  # Blue
    [234, 179, 8],  # Amber
    [16, 185, 129],  # Emerald
    [236, 72, 153],  # Pink
    [168, 85, 247],  # Purple
    [20, 184, 166],  # Teal
    [249, 115, 22],  # Orange
    [148, 163, 184],  # Slate
]


def _room_color(room_id: int) -> list[int]:
    return ROOM_PALETTE[(room_id - 1) % len(ROOM_PALETTE)]


def _room_colored_trajectory(
    pose_records: Sequence[Mapping[str, Any]],
    trajectory_points: np.ndarray,
    rooms: Sequence[Mapping[str, Any]],
) -> tuple[list[np.ndarray], list[list[int]]] | None:
    """Split the camera trajectory into per-room colored line strips.

    Returns None when no room information is available so callers can fall
    back to the single-color trajectory.
    """

    from aegis.memory.rooms import RoomRegion, room_for_point

    if not rooms or len(trajectory_points) != len(pose_records):
        return None
    room_regions = [
        RoomRegion(
            room_id=int(room.get("room_id", 0)),
            label=str(room.get("label", "Room")),
            room_type=str(room.get("room_type", "Room")),
            centroid=tuple(float(v) for v in room.get("centroid", (0.0, 0.0, 0.0))),
            footprint=[
                tuple(float(v) for v in point) for point in room.get("footprint", [])
            ],
        )
        for room in rooms
    ]
    strips: list[np.ndarray] = []
    colors: list[list[int]] = []
    current_points: list[np.ndarray] = []
    current_room_id: int | None = None
    for index, record in enumerate(pose_records):
        position = trajectory_points[index]
        matrix = record.get("matrix")
        if matrix is None:
            room_region = None
        else:
            translation = np.asarray(matrix, dtype=np.float64)[:3, 3]
            room_region = room_for_point(translation, room_regions)
        room_id = room_region.room_id if room_region is not None else None
        if room_id != current_room_id and current_points:
            strips.append(np.asarray(current_points, dtype=np.float32))
            colors.append(
                _room_color(current_room_id)
                if current_room_id is not None
                else [251, 191, 36]
            )
            current_points = []
        current_points.append(
            [float(position[0]), float(position[1]), float(position[2])]
        )
        current_room_id = room_id
    if current_points:
        strips.append(np.asarray(current_points, dtype=np.float32))
        colors.append(
            _room_color(current_room_id)
            if current_room_id is not None
            else [251, 191, 36]
        )
    if not strips:
        return None
    return strips, colors


def _memory_label_key(label: str) -> str:
    """Normalize raw detection and persistent-memory labels for visualization."""
    key = " ".join(str(label).lower().strip().split())
    if "#" in key:
        key = key.split("#", 1)[0].strip()
    aliases = {
        "shoe": "shoes",
        "water bottle": "bottle",
        "rubbish": "garbage bag",
        "trash bag": "garbage bag",
    }
    return aliases.get(key, key)


def _v2_timeline(
    graph: Mapping[str, Any], keyframe_ids: set[int]
) -> dict[str, list[dict[str, Any]]]:
    """Build per-keyframe memory entries from a schema-v2 state_run list.

    v1 graphs carried a ``timeline`` dict, which the viewer consumes directly.
    v2 graphs store ``state_runs`` + ``latest_states`` instead; without this
    adapter no object boxes or 2D overlays are drawn for a v2 recording.
    """

    states = {
        int(state["instance_id"]): state
        for state in graph.get("latest_states", [])
        if isinstance(state, Mapping) and state.get("instance_id") is not None
    }
    timeline: dict[str, list[dict[str, Any]]] = {}
    for run in graph.get("state_runs", []):
        if not isinstance(run, Mapping) or run.get("instance_id") is None:
            continue
        try:
            start = int(run.get("start_frame", 0))
            end = int(run.get("end_frame", start))
        except (TypeError, ValueError):
            continue
        state = states.get(int(run["instance_id"]), {})
        for frame_id in keyframe_ids:
            if not start <= frame_id <= end:
                continue
            entry = {
                "instance_id": run["instance_id"],
                "label": run.get("instance_label") or state.get("label") or "Object",
                "center": run.get("center") or state.get("center"),
                "size": state.get("size"),
                "anchor_label": run.get("anchor_label") or state.get("anchor_label"),
                "room_label": run.get("room_label") or state.get("room_label"),
                "relation": run.get("relation"),
                "relation_certain": run.get("relation_certain", True),
                "confidence": run.get("confidence"),
                "is_active_view": True,
                "is_in_hand": bool(state.get("is_in_hand", False)),
                "evidence": run.get("evidence"),
            }
            timeline.setdefault(str(frame_id), []).append(entry)
    return timeline


def _associate_boxes_with_memory(
    boxes: Sequence[Mapping[str, Any]],
    memory_entries: Sequence[Mapping[str, Any]],
) -> dict[int, Mapping[str, Any]]:
    """Associate current detections with active R4DSG instances.

    Rerun must show semantic instance IDs rather than transient detector track
    IDs. The scene graph keeps only the best observation for each instance, so
    unmatched duplicate detections are intentionally omitted from the clean
    supervisor-facing overlay.
    """
    candidates: list[tuple[float, int, int]] = []
    active_entries = [
        entry for entry in memory_entries if bool(entry.get("is_active_view", False))
    ]
    for box_index, box in enumerate(boxes):
        if bool(box.get("is_hand", False)):
            continue
        box_center = np.asarray(box.get("center", ()), dtype=np.float64)
        if box_center.shape != (3,):
            continue
        box_label = _memory_label_key(str(box.get("label", "")))
        for entry_index, entry in enumerate(active_entries):
            if _memory_label_key(str(entry.get("label", ""))) != box_label:
                continue
            entry_center = np.asarray(entry.get("center", ()), dtype=np.float64)
            if entry_center.shape != (3,):
                continue
            distance = float(np.linalg.norm(box_center - entry_center))
            candidates.append((distance, box_index, entry_index))

    associations: dict[int, Mapping[str, Any]] = {}
    used_boxes: set[int] = set()
    used_entries: set[int] = set()
    # Greedy nearest-neighbour matching is deterministic and sufficient here:
    # boxes and memory entries originate from the same lifted 3D observation.
    for distance, box_index, entry_index in sorted(candidates):
        if box_index in used_boxes or entry_index in used_entries:
            continue
        associations[box_index] = active_entries[entry_index]
        used_boxes.add(box_index)
        used_entries.add(entry_index)
    return associations


def run_rerun(dataset_id: str, raw_config: Mapping[str, Any]) -> dict[str, Any]:
    """Create an offline Rerun recording containing video, geometry, 3D boxes, and motion trails."""

    t0 = time.perf_counter()
    config = _config(raw_config)
    paths = dataset_paths(config, dataset_id)
    metadata = _require_metadata(paths)
    if not paths.poses.exists():
        raise FileNotFoundError(f"pose artifact is missing: {paths.poses}")
    if not paths.pointcloud_npz.exists():
        raise FileNotFoundError(
            f"point-cloud artifact is missing: {paths.pointcloud_npz}"
        )

    import rerun as rr
    import rerun.blueprint as rrb

    from aegis.geometry.gravity import GravityFrame

    gravity = (
        GravityFrame.from_dict(_read_json(paths.gravity))
        if paths.gravity.exists()
        else GravityFrame.assumed()
    )
    up_vector = np.asarray(gravity.up, dtype=np.float64)

    pose_data = _read_json(paths.poses)
    pose_records = pose_data.get("poses", [])
    pose_by_frame = {int(record["frame_id"]): record for record in pose_records}
    pointcloud = np.load(paths.pointcloud_npz)
    points = pointcloud["points"]
    colors = pointcloud["colors"]
    trajectory = np.asarray(
        [
            np.asarray(record["matrix"], dtype=np.float32)[:3, 3]
            for record in pose_records
        ]
    )

    def to_scene(pt: Sequence[float]) -> list[float]:
        """Raw VGGT-Ω world point (single source of truth for scale)."""

        return [float(pt[0]), float(pt[1]), float(pt[2])]

    def to_scene_size(sz: Sequence[float]) -> list[float]:
        return [float(sz[0]), float(sz[1]), float(sz[2])]

    def raw_rotation(rotation: Sequence[float] | None) -> list[float]:
        """Pass-through quaternion (xyzw) with a neutral identity fallback."""

        if rotation is None or len(rotation) != 4:
            return [0.0, 0.0, 0.0, 1.0]
        return [float(value) for value in rotation]

    def camera_frustum(record: Mapping[str, Any], depth: float) -> np.ndarray:
        matrix = np.asarray(record["matrix"], dtype=np.float64)
        rotation = matrix[:3, :3]
        origin = matrix[:3, 3]
        half_width = depth * 0.62
        half_height = depth * 0.40
        corners_camera = np.asarray(
            [
                [-half_width, -half_height, depth],
                [half_width, -half_height, depth],
                [half_width, half_height, depth],
                [-half_width, half_height, depth],
            ],
            dtype=np.float64,
        )
        corners_world = corners_camera @ rotation.T + origin
        points = [to_scene(origin)]
        points.extend(to_scene(point) for point in corners_world)
        # A closed pyramid wireframe with rays to two additional corners.
        return np.asarray(
            [
                points[0],
                points[1],
                points[2],
                points[3],
                points[4],
                points[1],
                points[0],
                points[3],
                points[0],
                points[2],
                points[0],
                points[4],
            ],
            dtype=np.float32,
        )

    # Precompute smooth camera trajectory positions across all frames
    all_frame_records = metadata.get("frames", [])
    all_fids = [int(f["frame_id"]) for f in all_frame_records]
    interp_positions: dict[int, list[float]] = {}
    if len(pose_records) > 0 and len(all_fids) > 0:
        kf_ids = np.array([int(r["frame_id"]) for r in pose_records], dtype=np.float32)
        kf_pos = np.array(
            [np.asarray(r["matrix"], dtype=np.float32)[:3, 3] for r in pose_records]
        )
        all_fid_arr = np.array(all_fids, dtype=np.float32)
        ix = np.interp(all_fid_arr, kf_ids, kf_pos[:, 0])
        iy = np.interp(all_fid_arr, kf_ids, kf_pos[:, 1])
        iz = np.interp(all_fid_arr, kf_ids, kf_pos[:, 2])
        for fid, x, y, z in zip(all_fids, ix, iy, iz, strict=True):
            interp_positions[fid] = to_scene([float(x), float(y), float(z)])

    # Load 3D object detections, motion trails, events, and R4DSG.
    motion_trails_by_track: dict[int, list[list[float]]] = {}
    boxes_by_frame: dict[int, list[dict[str, Any]]] = {}
    r4d_anchors: list[dict[str, Any]] = []
    r4d_rooms: list[dict[str, Any]] = []
    r4d_timeline: dict[str, list[dict[str, Any]]] = {}
    r4d_events: list[dict[str, Any]] = []

    r4d_path = paths.objects_json.parent / "r4d_scene_graph.json"
    if r4d_path.exists():
        r4d_data = _read_json(r4d_path)
        r4d_anchors = r4d_data.get("anchors", [])
        r4d_rooms = r4d_data.get("rooms", [])
        r4d_timeline = r4d_data.get("timeline", {})
        if not r4d_timeline and r4d_data.get("state_runs"):
            r4d_timeline = _v2_timeline(r4d_data, set(pose_by_frame))
        r4d_events = r4d_data.get("events", [])
    timeline_path = paths.objects_json.parent / "r4d_timeline.json"
    if timeline_path.exists():
        r4d_timeline = _read_json(timeline_path).get("timeline", {})

    if paths.objects_json.exists():
        obj_data = _read_json(paths.objects_json)
        for tid_str, trail in obj_data.get("motion_trails", {}).items():
            motion_trails_by_track[int(tid_str)] = trail
        for box in obj_data.get("boxes_3d", []):
            boxes_by_frame.setdefault(int(box["frame_id"]), []).append(box)

    paths.rerun_recording.parent.mkdir(parents=True, exist_ok=True)
    rr.init(f"aegis-{dataset_id}", spawn=False)
    rr.save(str(paths.rerun_recording))

    # Send a video/3D blueprint with a compact event panel.
    blueprint = rrb.Blueprint(
        rrb.Horizontal(
            rrb.Spatial2DView(
                name="Egocentric Video",
                origin="video",
            ),
            rrb.Vertical(
                rrb.Spatial3DView(
                    name="R4DSG 3D Spatial Memory",
                    origin="spatial_memory",
                    line_grid=True,
                ),
                rrb.TextDocumentView(
                    name="R4DSG Memory Events",
                    origin="memory/events",
                ),
                row_shares=[3.0, 1.0],
            ),
            column_shares=[1.0, 1.35],
        ),
        collapse_panels=True,
    )
    rr.send_blueprint(blueprint)

    # Set View Coordinates to the raw VGGT-Ω world convention (OpenCV-style:
    # +X right, +Y down, +Z forward). Display hint only — no data transform.
    rr.log("spatial_memory", rr.ViewCoordinates.RIGHT_HAND_Y_DOWN, static=True)

    # 1. Log Spatial Anchors (The Room's Permanent Reference Frame)
    if r4d_anchors:
        anc_centers = [to_scene(a["center"]) for a in r4d_anchors]
        anc_sizes = [to_scene_size(a["size"]) for a in r4d_anchors]
        anc_labels = [
            (
                f"Anchor: {a['label']} #{a['anchor_id']}"
                + (f" · {a['room_label']}" if a.get("room_label") else "")
            )
            for a in r4d_anchors
        ]
        rr.log(
            "spatial_memory/anchors",
            rr.Boxes3D(
                centers=anc_centers,
                sizes=anc_sizes,
                labels=anc_labels,
                colors=[[59, 130, 246] for _ in r4d_anchors],  # Clean Blue
            ),
            static=True,
        )

    # 1B. Log Room-Level Depictions (Rooms -> Anchors -> Objects hierarchy)
    # One entity group per room so the viewer can toggle rooms individually:
    # a translucent floor slab (triangulated mesh), a closed outline,
    # corner wall pillars, and a labeled centroid marker.
    if r4d_rooms:
        for room in r4d_rooms:
            footprint = room.get("footprint") or []
            if len(footprint) < 3:
                continue
            room_id = int(room.get("room_id", 1))
            room_label = str(room.get("label", f"Room #{room_id}"))
            room_entity = f"spatial_memory/rooms/room_{room_id}"
            color = _room_color(room_id)
            polygon = np.asarray(
                [to_scene(point) for point in footprint], dtype=np.float32
            )

            # Translucent convex floor slab: fan-triangulate the convex hull.
            triangles = np.asarray(
                [[0, i, i + 1] for i in range(1, len(polygon) - 1)],
                dtype=np.uint32,
            )
            slab_alpha = 46  # ~18% opacity keeps the room readable as a zone
            rr.log(
                f"{room_entity}/floor",
                rr.Mesh3D(
                    vertex_positions=polygon,
                    triangle_indices=triangles,
                    vertex_colors=[[(*color, slab_alpha)] for _ in polygon],
                ),
                static=True,
            )

            # Closed outline on the room plane.
            closed_loop = np.vstack([polygon, polygon[:1]])
            rr.log(
                f"{room_entity}/outline",
                rr.LineStrips3D(
                    [closed_loop],
                    radii=0.02,
                    colors=[color],
                    labels=[f"Room: {room_label}"],
                ),
                static=True,
            )

            # Corner wall pillars rising along the session's up vector.
            pillar_height = 1.2
            pillars = np.asarray(
                [
                    [list(point), list(np.asarray(point) + pillar_height * up_vector)]
                    for point in polygon
                ],
                dtype=np.float32,
            )
            rr.log(
                f"{room_entity}/walls",
                rr.LineStrips3D(pillars, radii=0.02, colors=[color]),
                static=True,
            )

            # Labeled centroid marker: the summoning point for each room.
            centroid = room.get("centroid")
            if centroid:
                keyframe_count = int(room.get("keyframe_count", 0) or 0)
                room_type = str(room.get("room_type", "Room"))
                observation_note = (
                    f"{keyframe_count} obs" if keyframe_count else "no trajectory"
                )
                rr.log(
                    f"{room_entity}/label",
                    rr.Points3D(
                        [to_scene(centroid)],
                        radii=0.05,
                        colors=[color],
                        labels=[
                            f"Room: {room_label} · {room_type} · {observation_note}"
                        ],
                    ),
                    static=True,
                )

    # 2. Log Camera Trajectory in VGGT World Coordinates, colored by room
    if len(trajectory) > 0:
        trajectory_zup = np.asarray(
            [to_scene(pt) for pt in trajectory], dtype=np.float32
        )
        trajectory_strips = _room_colored_trajectory(
            pose_records, trajectory_zup, r4d_rooms
        )
        if trajectory_strips is not None:
            strips, colors = trajectory_strips
            rr.log(
                "spatial_memory/camera_trajectory",
                rr.LineStrips3D(strips, radii=0.015, colors=colors),
                static=True,
            )
        else:
            rr.log(
                "spatial_memory/camera_trajectory",
                rr.LineStrips3D(
                    [trajectory_zup], radii=0.015, colors=[[251, 191, 36]]
                ),  # Amber
                static=True,
            )

    # 2C. Add a minimal visual reference frame and clean ground grid.
    if len(points) > 0:
        point_extent = np.ptp(points, axis=0)
        reference_extent = max(float(np.max(point_extent)) * 0.6, 1.0)
    else:
        reference_extent = 2.5
    axis_length = max(reference_extent * 0.18, 0.25)
    rr.log(
        "spatial_memory/reference_axes",
        rr.Arrows3D(
            vectors=[
                [axis_length, 0.0, 0.0],
                [0.0, axis_length, 0.0],
                [0.0, 0.0, axis_length],
            ],
            origins=[[0.0, 0.0, 0.0]] * 3,
            colors=[[239, 68, 68], [239, 68, 68], [59, 130, 246]],
            labels=["X right", "Y down", "Z forward"],
        ),
        static=True,
    )

    # Reference grid on the floor plane of the gravity frame (the fitted
    # floor when known, else just below the lowest camera position).
    if gravity.floor_offset is not None:
        floor_elevation = float(gravity.floor_offset)
    elif len(trajectory) > 0:
        floor_elevation = float(min(gravity.elevation(p) for p in trajectory))
    else:
        floor_elevation = 0.0
    grid_values = np.linspace(-reference_extent, reference_extent, 9)
    grid_strips = []
    for value in grid_values:
        for start, end in (
            ((-reference_extent, float(value)), (reference_extent, float(value))),
            ((float(value), -reference_extent), (float(value), reference_extent)),
        ):
            grid_strips.append(
                np.asarray(
                    [
                        gravity.from_horizontal(start[0], start[1], floor_elevation),
                        gravity.from_horizontal(end[0], end[1], floor_elevation),
                    ],
                    dtype=np.float32,
                )
            )
    rr.log(
        "spatial_memory/reference_grid",
        rr.LineStrips3D(
            grid_strips,
            radii=0.003,
            colors=[[120, 130, 145]],
        ),
        static=True,
    )

    if not r4d_events and paths.events_json.exists():
        r4d_events = _read_json(paths.events_json).get("events", [])
    event_lines = ["# R4DSG memory events", ""]
    if r4d_events:
        for event in r4d_events:
            ev_type = str(event.get("event_type", "transition")).upper()
            if ev_type == "ROOM_CHANGE":
                event_lines.append(
                    f"- **[{ev_type}] {event['object']}**: "
                    f"{event.get('source_room', 'unknown')} → {event.get('destination_room', 'unknown')} "
                    f"({event['start_time']:.2f}s–{event['end_time']:.2f}s)"
                )
                continue
            source_room = event.get("source_room")
            destination_room = event.get("destination_room")
            room_badges = ""
            if source_room or destination_room:
                room_badges = (
                    f", rooms {source_room or '?'} → {destination_room or '?'}"
                )
            event_lines.append(
                f"- **[{ev_type}] {event['object']}**: "
                f"{event.get('source_relation', 'unknown')} → {event.get('destination_relation', 'unknown')} "
                f"({event['start_time']:.2f}s–{event['end_time']:.2f}s)"
                f"{room_badges}, "
                f"evidence frames {event.get('evidence_frames', [])}"
            )
    else:
        event_lines.append("No stable relation transitions were detected.")
    rr.log(
        "memory/events",
        rr.TextDocument("\n".join(event_lines), media_type=rr.MediaType.MARKDOWN),
        static=True,
    )

    # 3. Log All Video Frames, Camera Motion, and 4D Object Memory
    keyframe_id_set = set(pose_by_frame.keys())
    for frame in all_frame_records:
        frame_id = int(frame["frame_id"])

        rr.set_time("frame", sequence=frame_id)
        if "timestamp" in frame:
            rr.set_time("time", duration=float(frame["timestamp"]))

        # 3A. Log Pristine Egocentric Video Frame (compressed to JPEG for compact RRD size)
        if config.visualization.log_video and (
            frame_id % config.visualization.video_stride == 0
        ):
            image_path = paths.frames / str(frame["filename"])
            if image_path.exists():
                try:
                    import cv2

                    img = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
                    if img is not None:
                        ok, buf = cv2.imencode(
                            ".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 80]
                        )
                        if ok:
                            rr.log(
                                "video/egocentric_stream",
                                rr.EncodedImage(
                                    contents=buf.tobytes(), media_type="image/jpeg"
                                ),
                            )
                        else:
                            rr.log(
                                "video/egocentric_stream",
                                rr.EncodedImage(path=image_path),
                            )
                    else:
                        rr.log(
                            "video/egocentric_stream", rr.EncodedImage(path=image_path)
                        )
                except ImportError:
                    try:
                        import io

                        from PIL import Image

                        with Image.open(image_path) as pil_img:
                            buf = io.BytesIO()
                            pil_img.convert("RGB").save(buf, format="JPEG", quality=80)
                            rr.log(
                                "video/egocentric_stream",
                                rr.EncodedImage(
                                    contents=buf.getvalue(), media_type="image/jpeg"
                                ),
                            )
                    except (OSError, ValueError):
                        rr.log(
                            "video/egocentric_stream", rr.EncodedImage(path=image_path)
                        )

        # 3B. Show only lifted detections represented by active R4DSG
        # instances. The overlay must use persistent instance IDs, not the
        # detector's short-term track IDs.
        frame_boxes = boxes_by_frame.get(frame_id, [])
        mem_entries = r4d_timeline.get(str(frame_id), [])
        box_associations = _associate_boxes_with_memory(frame_boxes, mem_entries)
        display_boxes: list[dict[str, Any]] = []
        for box_index, box in enumerate(frame_boxes):
            if bool(box.get("is_hand", False)):
                display_box = dict(box)
                display_box["_memory_entry"] = None
                display_boxes.append(display_box)
            elif box_index in box_associations:
                display_box = dict(box)
                display_box["_memory_entry"] = box_associations[box_index]
                display_boxes.append(display_box)

        if display_boxes:
            sorted_boxes = sorted(
                display_boxes,
                key=lambda b: float(b.get("confidence", 0.0)),
                reverse=True,
            )
            clean_boxes: list[dict[str, Any]] = []
            for b in sorted_boxes:
                b_xyxy = b["bbox_2d"]
                is_overlap = False
                for c in clean_boxes:
                    c_xyxy = c["bbox_2d"]
                    iw = max(0.0, min(b_xyxy[2], c_xyxy[2]) - max(b_xyxy[0], c_xyxy[0]))
                    ih = max(0.0, min(b_xyxy[3], c_xyxy[3]) - max(b_xyxy[1], c_xyxy[1]))
                    inter = iw * ih
                    union = (
                        (b_xyxy[2] - b_xyxy[0]) * (b_xyxy[3] - b_xyxy[1])
                        + (c_xyxy[2] - c_xyxy[0]) * (c_xyxy[3] - c_xyxy[1])
                        - inter
                    )
                    if union > 0 and (inter / union) > 0.35:
                        is_overlap = True
                        break
                if not is_overlap:
                    clean_boxes.append(b)
                if len(clean_boxes) >= 3:
                    break

            clean_labels: list[str] = []
            clean_colors: list[list[int]] = []
            for box in clean_boxes:
                memory_entry = box.get("_memory_entry")
                if memory_entry is not None:
                    lbl = str(memory_entry["label"])
                    if memory_entry.get("is_in_hand", False):
                        lbl += " [In Hand]"
                        clean_colors.append([245, 158, 11])  # Amber #F59E0B
                    else:
                        clean_colors.append(
                            _track_color(int(memory_entry["instance_id"]))
                        )
                else:
                    # Hands are not R4DSG object instances; hide their
                    # transient detector track IDs in the supervisor view.
                    lbl = "Hand"
                    clean_colors.append([244, 63, 94])  # Rose
                clean_labels.append(lbl)

            rr.log(
                "video/detections",
                rr.Boxes2D(
                    array=np.asarray(
                        [box["bbox_2d"] for box in clean_boxes], dtype=np.float32
                    ),
                    array_format=rr.Box2DFormat.XYXY,
                    colors=clean_colors,
                    labels=clean_labels,
                ),
            )

        # 3C. Smooth Camera Pose in Z-Up
        if frame_id in interp_positions:
            cam_position = interp_positions[frame_id]
            rr.log(
                "spatial_memory/camera",
                rr.Points3D(
                    [cam_position],
                    colors=[[255, 64, 64]],
                    radii=0.035,
                ),
            )

        # 4D. Log R4DSG Persistent Object Memory and Relational Edges
        if frame_id in keyframe_id_set:
            mem_entries = r4d_timeline.get(str(frame_id), [])
            if mem_entries:
                centers = [to_scene(e["center"]) for e in mem_entries]
                sizes = [to_scene_size(e["size"]) for e in mem_entries]
                labels = []
                colors = []
                in_hand_links = []
                cam_pos = interp_positions.get(frame_id)

                for e in mem_entries:
                    is_in_hand = e.get("is_in_hand", False)
                    relation = e.get("relation", "")
                    anchor_lbl = e.get("anchor_label", "Anchor")
                    base_lbl = e["label"]
                    obj_center = to_scene(e["center"])
                    room_lbl = e.get("room_label")
                    # Room badge for placed / persisted objects: the label
                    # becomes "Keys #1 · [Inside Desk #1 · Living Room]".
                    if room_lbl and not is_in_hand:
                        base_lbl = f"{base_lbl} · {room_lbl}"

                    if is_in_hand:
                        labels.append(f"{base_lbl} · [Carried by User]")
                        colors.append([245, 158, 11])  # Amber #F59E0B
                        if cam_pos is not None:
                            in_hand_links.append(
                                np.asarray([cam_pos, obj_center], dtype=np.float32)
                            )
                    elif relation == "inside":
                        labels.append(f"{base_lbl} · [Inside {anchor_lbl}]")
                        colors.append([16, 185, 129])  # Emerald #10B981
                    elif e["is_active_view"]:
                        labels.append(f"{base_lbl} · ACTIVE")
                        colors.append(_track_color(int(e["instance_id"])))
                    else:
                        labels.append(f"{base_lbl} · ✦ PERSISTENT MEMORY")
                        colors.append([20, 184, 166])  # Teal #14B8A6

                quats = [raw_rotation(e.get("rotation")) for e in mem_entries]

                rr.log(
                    "spatial_memory/persistent_objects",
                    rr.Boxes3D(
                        centers=centers,
                        sizes=sizes,
                        labels=labels,
                        colors=colors,
                        quaternions=quats,
                    ),
                )

                if in_hand_links:
                    rr.log(
                        "spatial_memory/in_hand_link",
                        rr.LineStrips3D(
                            in_hand_links,
                            radii=0.015,
                            colors=[[245, 158, 11]],  # Amber
                            labels=["Carried Link"],
                        ),
                    )
                else:
                    rr.log("spatial_memory/in_hand_link", rr.Clear.flat())

            else:
                rr.log("spatial_memory/persistent_objects", rr.Clear.flat())
                rr.log("spatial_memory/in_hand_link", rr.Clear.flat())

    _write_json(
        paths.viewer_manifest,
        {
            "schema_version": 1,
            "dataset_id": dataset_id,
            "recording": str(paths.rerun_recording),
            "frame_count": len(all_frame_records),
            "keyframe_count": len(pose_records),
            "point_count": len(points),
            "total_anchors": len(r4d_anchors),
            "total_rooms": len(r4d_rooms),
            "total_tracks": len(motion_trails_by_track),
            "total_events": len(r4d_events),
            "open_command": f"rerun outputs/{dataset_id}/viewer/demo.rrd",
        },
    )
    elapsed = time.perf_counter() - t0
    file_size_mb = (
        round(paths.rerun_recording.stat().st_size / (1024**2), 2)
        if paths.rerun_recording.exists()
        else 0.0
    )

    stage_result = {
        "stage": "rerun",
        "dataset_id": dataset_id,
        "frame_count": len(all_frame_records),
        "keyframe_count": len(pose_records),
        "point_count": len(points),
        "total_anchors": len(r4d_anchors),
        "total_rooms": len(r4d_rooms),
        "total_tracks": len(motion_trails_by_track),
        "total_events": len(r4d_events),
        "recording": str(paths.rerun_recording),
        "recording_size_mb": file_size_mb,
        "elapsed_seconds": round(elapsed, 2),
    }
    _record_benchmark_stats(paths, dataset_id, "rerun", stage_result)
    return stage_result
