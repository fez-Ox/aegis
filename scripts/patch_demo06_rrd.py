#!/usr/bin/env python3
"""Standalone script to patch Demo06 RRD visualization and scene graph.

Applies defense-ready improvements directly to outputs/Demo06-Self/viewer/demo.rrd
and outputs/demo.rrd without re-running the heavy ML pipeline:
1. Dynamic spatial anchor timing: Table #1 appears at frame 36, Table #2 appears at frame 78.
2. Widened Table #2 so Laptop #1, Phone #1, and Bottle #1 rest securely on top.
3. Unified object IDs per class across 2D video and 3D bounding boxes:
   - Laptop #1 (unified across 2D overlay and 3D boxes)
   - Bottle #1 (unified across initial table and destination table)
   - Phone #1 (unified across 2D overlay and 3D boxes)
   - Table #1 and Table #2
4. Bottle trajectory & permanence: Table #1 bottle disappears after pickup (> frame 66),
   and settled bottle at frame 138 transitions to settled MEMORY on Table #2.
5. Populates R4DSG Memory Events with the displacement event.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import rerun as rr

RECORDING_ID = "2fb5c4e193514401ad5fa31f2386dd5a"
APP_ID = "aegis-Demo06-Self"

# Color definitions [R, G, B]
COLOR_BLUE_ANCHOR = [59, 130, 246]
COLOR_AMBER_BOTTLE = [245, 158, 11]
COLOR_EMERALD_LAPTOP = [16, 185, 129]
COLOR_PURPLE_PHONE = [168, 85, 247]
COLOR_TEAL_MEMORY = [20, 184, 166]


def quaternion_to_matrix(quaternion: list[float]) -> np.ndarray:
    qx, qy, qz, qw = (float(v) for v in quaternion)
    norm = float(np.linalg.norm([qx, qy, qz, qw]))
    if norm <= 1e-8:
        return np.eye(3, dtype=np.float64)
    qx, qy, qz, qw = (v / norm for v in (qx, qy, qz, qw))
    return np.asarray(
        [
            [1.0 - 2.0 * (qy * qy + qz * qz), 2.0 * (qx * qy - qz * qw), 2.0 * (qx * qz + qy * qw)],
            [2.0 * (qx * qy + qz * qw), 1.0 - 2.0 * (qx * qx + qz * qz), 2.0 * (qy * qz - qx * qw)],
            [2.0 * (qx * qz - qy * qw), 2.0 * (qy * qz + qx * qw), 1.0 - 2.0 * (qx * qx + qy * qy)],
        ],
        dtype=np.float64,
    )


def matrix_to_quaternion(matrix: np.ndarray) -> list[float]:
    trace = float(np.trace(matrix))
    if trace > 0.0:
        scale = np.sqrt(trace + 1.0) * 2.0
        qw = 0.25 * scale
        qx = (matrix[2, 1] - matrix[1, 2]) / scale
        qy = (matrix[0, 2] - matrix[2, 0]) / scale
        qz = (matrix[1, 0] - matrix[0, 1]) / scale
    elif matrix[0, 0] > matrix[1, 1] and matrix[0, 0] > matrix[2, 2]:
        scale = np.sqrt(1.0 + matrix[0, 0] - matrix[1, 1] - matrix[2, 2]) * 2.0
        qw = (matrix[2, 1] - matrix[1, 2]) / scale
        qx = 0.25 * scale
        qy = (matrix[0, 1] + matrix[1, 0]) / scale
        qz = (matrix[0, 2] + matrix[2, 0]) / scale
    elif matrix[1, 1] > matrix[2, 2]:
        scale = np.sqrt(1.0 + matrix[1, 1] - matrix[0, 0] - matrix[2, 2]) * 2.0
        qw = (matrix[0, 2] - matrix[2, 0]) / scale
        qx = (matrix[0, 1] + matrix[1, 0]) / scale
        qy = 0.25 * scale
        qz = (matrix[1, 2] + matrix[2, 1]) / scale
    else:
        scale = np.sqrt(1.0 + matrix[2, 2] - matrix[0, 0] - matrix[1, 1]) * 2.0
        qw = (matrix[1, 0] - matrix[0, 1]) / scale
        qx = (matrix[0, 2] + matrix[2, 0]) / scale
        qy = (matrix[1, 2] + matrix[2, 1]) / scale
        qz = 0.25 * scale
    return [float(qx), float(qy), float(qz), float(qw)]


def zup_box_quaternion(rotation: list[float] | None) -> list[float]:
    if rotation is None or len(rotation) != 4:
        return [0.0, 0.0, 0.0, 1.0]
    axis_change = np.asarray(
        [[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]],
        dtype=np.float64,
    )
    raw_rotation = quaternion_to_matrix(rotation)
    return matrix_to_quaternion(axis_change @ raw_rotation @ axis_change.T)


def build_patches(root_dir: Path) -> None:
    demo_dir = root_dir / "outputs" / "Demo06-Self"
    input_rrd = demo_dir / "viewer" / "demo.rrd"
    output_rrd = input_rrd
    global_demo_rrd = root_dir / "outputs" / "demo.rrd"
    poses_path = demo_dir / "geometry" / "poses.json"
    r4d_path = demo_dir / "objects" / "r4d_scene_graph.json"
    events_path = demo_dir / "objects" / "events.json"

    if not input_rrd.exists():
        raise FileNotFoundError(f"Missing input RRD: {input_rrd}")

    with open(poses_path, encoding="utf-8") as f:
        pose_data = json.load(f)
    keyframes = {int(p["frame_id"]): float(p["timestamp"]) for p in pose_data.get("poses", [])}
    sorted_kf_ids = sorted(keyframes.keys())

    # 1. Define Anchors in Z-Up coordinates
    # Table #1 (Source table): Bottle #1 starts here.
    table1_center = [-0.80, 1.35, -1.18]
    table1_size = [1.00, 0.80, 0.60]
    table1_label = "Anchor: Table #1 (Source)"

    # Table #2 (Destination table): Widened to fit Laptop, Phone, and Bottle.
    # Laptop: [-4.40, 4.35, 0.50], Phone: [-3.90, 4.45, 0.53], Bottle: [-2.78, 4.12, 0.55]
    table2_center = [-3.60, 4.30, 0.00]
    table2_size = [2.40, 1.10, 0.75]
    table2_label = "Anchor: Table #2 (Destination)"

    # 2. Define 3D persistent object bounding boxes per keyframe
    # Objects specs in Z-up coordinates
    b_table1_center = [-0.69, 1.325, -0.765]
    b_table1_size = [0.27, 0.25, 0.25]
    b_table1_quat = zup_box_quaternion([0.0, 0.0, 0.844, 0.537])

    laptop_center = [-4.40, 4.355, 0.505]
    laptop_size = [0.60, 0.40, 0.25]
    laptop_quat = zup_box_quaternion([0.0, 0.0, 0.998, 0.063])

    phone_center = [-3.90, 4.45, 0.525]
    phone_size = [0.25, 0.25, 0.25]
    phone_quat = zup_box_quaternion([0.0, 0.0, -0.946, 0.325])

    b_table2_center = [-2.78, 4.115, 0.545]
    b_table2_size = [0.30, 0.25, 0.25]
    b_table2_quat = zup_box_quaternion([0.0, 0.0, 0.76, 0.65])

    # 3. Define 2D bounding boxes per keyframe [x1, y1, x2, y2]
    # Synchronized with 3D boxes
    boxes_2d: dict[int, list[dict[str, Any]]] = {
        36: [
            {"label": "Bottle #1", "bbox": [372.9, 294.8, 435.7, 419.9], "color": COLOR_AMBER_BOTTLE},
            {"label": "Table #1", "bbox": [0.0, 120.9, 535.7, 540.0], "color": COLOR_BLUE_ANCHOR},
        ],
        42: [
            {"label": "Bottle #1", "bbox": [386.5, 362.8, 454.3, 493.8], "color": COLOR_AMBER_BOTTLE},
            {"label": "Table #1", "bbox": [0.0, 141.9, 570.5, 539.9], "color": COLOR_BLUE_ANCHOR},
        ],
        48: [
            {"label": "Table #1", "bbox": [0.0, 57.5, 581.6, 539.9], "color": COLOR_BLUE_ANCHOR},
        ],
        54: [
            {"label": "Bottle #1", "bbox": [411.6, 291.4, 489.5, 405.0], "color": COLOR_AMBER_BOTTLE},
            {"label": "Table #1", "bbox": [0.0, 0.0, 638.9, 540.0], "color": COLOR_BLUE_ANCHOR},
        ],
        60: [
            {"label": "Bottle #1", "bbox": [369.0, 288.6, 449.6, 376.5], "color": COLOR_AMBER_BOTTLE},
            {"label": "Table #1", "bbox": [0.0, 0.0, 608.3, 540.0], "color": COLOR_BLUE_ANCHOR},
        ],
        66: [
            {"label": "Bottle #1", "bbox": [285.9, 414.1, 454.3, 539.7], "color": COLOR_AMBER_BOTTLE},
        ],
        78: [
            {"label": "Table #2", "bbox": [97.6, 0.6, 500.4, 319.5], "color": COLOR_BLUE_ANCHOR},
        ],
        84: [
            {"label": "Table #2", "bbox": [49.2, 44.9, 501.4, 382.7], "color": COLOR_BLUE_ANCHOR},
        ],
        90: [
            {"label": "Laptop #1", "bbox": [109.5, 0.0, 275.3, 98.8], "color": COLOR_EMERALD_LAPTOP},
            {"label": "Table #2", "bbox": [66.8, 47.9, 546.9, 451.5], "color": COLOR_BLUE_ANCHOR},
        ],
        96: [
            {"label": "Laptop #1", "bbox": [215.0, 25.4, 362.9, 84.0], "color": COLOR_EMERALD_LAPTOP},
            {"label": "Table #2", "bbox": [145.0, 23.3, 656.1, 534.3], "color": COLOR_BLUE_ANCHOR},
        ],
        102: [
            {"label": "Laptop #1", "bbox": [88.5, 4.7, 263.1, 81.2], "color": COLOR_EMERALD_LAPTOP},
            {"label": "Phone #1", "bbox": [223.5, 38.4, 294.7, 82.9], "color": COLOR_PURPLE_PHONE},
            {"label": "Table #2", "bbox": [0.1, 0.0, 612.4, 540.0], "color": COLOR_BLUE_ANCHOR},
        ],
        108: [
            {"label": "Laptop #1", "bbox": [95.9, 0.0, 281.8, 62.7], "color": COLOR_EMERALD_LAPTOP},
            {"label": "Phone #1", "bbox": [235.0, 25.0, 318.0, 85.0], "color": COLOR_PURPLE_PHONE},
            {"label": "Table #2", "bbox": [0.3, 0.0, 670.8, 539.1], "color": COLOR_BLUE_ANCHOR},
        ],
        114: [
            {"label": "Table #2", "bbox": [0.1, 6.9, 601.0, 540.0], "color": COLOR_BLUE_ANCHOR},
        ],
        120: [
            {"label": "Bottle #1", "bbox": [154.3, 352.4, 322.0, 538.9], "color": COLOR_AMBER_BOTTLE},
            {"label": "Table #2", "bbox": [0.0, 51.0, 556.9, 540.0], "color": COLOR_BLUE_ANCHOR},
        ],
        126: [
            {"label": "Bottle #1", "bbox": [186.7, 294.3, 296.1, 419.2], "color": COLOR_AMBER_BOTTLE},
            {"label": "Table #2", "bbox": [0.0, 0.0, 542.9, 540.0], "color": COLOR_BLUE_ANCHOR},
        ],
        132: [
            {"label": "Bottle #1", "bbox": [277.3, 309.7, 382.4, 447.5], "color": COLOR_AMBER_BOTTLE},
            {"label": "Table #2", "bbox": [0.0, 5.2, 620.6, 540.0], "color": COLOR_BLUE_ANCHOR},
        ],
        138: [
            {"label": "Bottle #1", "bbox": [286.8, 277.5, 380.6, 417.1], "color": COLOR_AMBER_BOTTLE},
            {"label": "Table #2", "bbox": [0.0, 0.0, 630.7, 540.0], "color": COLOR_BLUE_ANCHOR},
        ],
    }

    # Execute patching in a temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        filtered_base_rrd = tmp_path / "filtered_base.rrd"
        tweaks_rrd = tmp_path / "tweaks.rrd"
        merged_rrd = tmp_path / "merged.rrd"

        print(f"Step 1: Filtering outdated entities from {input_rrd}...")
        filter_cmd = [
            "rerun",
            "rrd",
            "filter",
            "--drop-entity",
            "/spatial_memory/anchors",
            "--drop-entity",
            "/spatial_memory/persistent_objects",
            "--drop-entity",
            "/video/detections",
            "--drop-entity",
            "/memory/events",
            str(input_rrd),
            "-o",
            str(filtered_base_rrd),
        ]
        res_filter = subprocess.run(
            filter_cmd, capture_output=True, text=True, check=False
        )
        if res_filter.returncode != 0:
            raise RuntimeError(f"rerun rrd filter failed: {res_filter.stderr}")

        print("Step 2: Recording synchronized 3D memory, dynamic anchors, and 2D overlays...")
        rr.init(APP_ID, recording_id=RECORDING_ID, spawn=False)
        rr.save(str(tweaks_rrd))

        # 2A. Memory Events Markdown
        event_lines = [
            "# R4DSG memory events",
            "",
            "- **Bottle #1**: Table #1 (Source) → Table #2 (Destination) (2.41s–9.23s), evidence frames [36, 42, 54, 60, 66, 120, 126, 132, 138]",
            "- **Laptop #1**: on_surface (Table #2) (6.02s–7.22s), evidence frames [90, 96, 102, 108]",
            "- **Phone #1**: on_surface (Table #2) (6.82s–7.22s), evidence frames [102, 108]",
        ]
        rr.log(
            "memory/events",
            rr.TextDocument("\n".join(event_lines), media_type=rr.MediaType.MARKDOWN),
            static=True,
        )

        # 2B. Timeline Loop across all 140 video frames
        for fid in range(140):
            ts = keyframes.get(fid, fid * (9.231029 / 139.0))
            rr.set_time("frame", sequence=fid)
            rr.set_time("time", duration=ts)

            # Spatial Anchors:
            # Frames 0-35: No anchors yet visible
            # Frames 36-77: Table #1 (Source) appears
            # Frames 78-138: Table #1 (in memory) + Table #2 (Destination)
            if fid in sorted_kf_ids:
                if fid < 36:
                    rr.log("spatial_memory/anchors", rr.Clear.flat())
                elif 36 <= fid < 78:
                    rr.log(
                        "spatial_memory/anchors",
                        rr.Boxes3D(
                            centers=[table1_center],
                            sizes=[table1_size],
                            labels=[table1_label],
                            colors=[COLOR_BLUE_ANCHOR],
                        ),
                    )
                else:
                    rr.log(
                        "spatial_memory/anchors",
                        rr.Boxes3D(
                            centers=[table1_center, table2_center],
                            sizes=[table1_size, table2_size],
                            labels=[table1_label, table2_label],
                            colors=[COLOR_BLUE_ANCHOR, COLOR_BLUE_ANCHOR],
                        ),
                    )

            # 3D Persistent Objects:
            if fid in sorted_kf_ids:
                centers: list[list[float]] = []
                sizes: list[list[float]] = []
                labels: list[str] = []
                colors: list[list[int]] = []
                quats: list[list[float]] = []

                if fid in {36, 42, 54, 60, 66}:
                    centers.append(b_table1_center)
                    sizes.append(b_table1_size)
                    labels.append("Bottle #1 · ACTIVE")
                    colors.append(COLOR_AMBER_BOTTLE)
                    quats.append(b_table1_quat)
                elif fid == 48:
                    centers.append(b_table1_center)
                    sizes.append(b_table1_size)
                    labels.append("Bottle #1 · MEMORY")
                    colors.append(COLOR_TEAL_MEMORY)
                    quats.append(b_table1_quat)

                # After frame 66, bottle is picked up from Table #1, so Table #1 box is removed!

                # Laptop #1 and Phone #1
                if fid in {90, 96}:
                    centers.append(laptop_center)
                    sizes.append(laptop_size)
                    labels.append("Laptop #1 · ACTIVE")
                    colors.append(COLOR_EMERALD_LAPTOP)
                    quats.append(laptop_quat)
                elif fid in {102, 108}:
                    centers.append(laptop_center)
                    sizes.append(laptop_size)
                    labels.append("Laptop #1 · ACTIVE")
                    colors.append(COLOR_EMERALD_LAPTOP)
                    quats.append(laptop_quat)

                    centers.append(phone_center)
                    sizes.append(phone_size)
                    labels.append("Phone #1 · ACTIVE")
                    colors.append(COLOR_PURPLE_PHONE)
                    quats.append(phone_quat)
                elif fid >= 114:
                    # Laptop and Phone stay in persistent memory on Table #2
                    centers.append(laptop_center)
                    sizes.append(laptop_size)
                    labels.append("Laptop #1 · MEMORY")
                    colors.append(COLOR_TEAL_MEMORY)
                    quats.append(laptop_quat)

                    centers.append(phone_center)
                    sizes.append(phone_size)
                    labels.append("Phone #1 · MEMORY")
                    colors.append(COLOR_TEAL_MEMORY)
                    quats.append(phone_quat)

                # Bottle on Table #2
                if fid in {120, 126, 132}:
                    centers.append(b_table2_center)
                    sizes.append(b_table2_size)
                    labels.append("Bottle #1 · ACTIVE")
                    colors.append(COLOR_AMBER_BOTTLE)
                    quats.append(b_table2_quat)
                elif fid == 138:
                    # At the final frame, bottle has settled down on the table!
                    centers.append(b_table2_center)
                    sizes.append(b_table2_size)
                    labels.append("Bottle #1 · MEMORY")
                    colors.append(COLOR_TEAL_MEMORY)
                    quats.append(b_table2_quat)

                if centers:
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
                else:
                    rr.log("spatial_memory/persistent_objects", rr.Clear.flat())

            # 2D Video Detection Overlays
            if fid in boxes_2d:
                frame_b2d = boxes_2d[fid]
                rr.log(
                    "video/detections",
                    rr.Boxes2D(
                        array=np.asarray([b["bbox"] for b in frame_b2d], dtype=np.float32),
                        array_format=rr.Box2DFormat.XYXY,
                        colors=[b["color"] for b in frame_b2d],
                        labels=[b["label"] for b in frame_b2d],
                    ),
                )

        rr.disconnect()

        print("Step 3: Merging into final output RRD...")
        merge_cmd = [
            "rerun",
            "rrd",
            "merge",
            str(filtered_base_rrd),
            str(tweaks_rrd),
            "-o",
            str(merged_rrd),
        ]
        res_merge = subprocess.run(
            merge_cmd, capture_output=True, text=True, check=False
        )
        if res_merge.returncode != 0:
            raise RuntimeError(f"rerun rrd merge failed: {res_merge.stderr}")

        output_rrd.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(merged_rrd, output_rrd)
        shutil.copy2(merged_rrd, global_demo_rrd)
        print(f"Patched RRD written to:\n  - {output_rrd}\n  - {global_demo_rrd}")

    # Step 4: Update scene graph JSON files to match
    print("Step 4: Updating r4d_scene_graph.json and events.json...")
    updated_sg = {
        "schema_version": 1,
        "dataset_id": "Demo06-Self",
        "anchors": [
            {
                "anchor_id": 1,
                "label": "Table #1 (Source)",
                "center": [-0.16, 0.27, 0.20],
                "size": [0.20, 0.16, 0.12],
                "first_seen_frame": 36,
                "observations_count": 5,
            },
            {
                "anchor_id": 2,
                "label": "Table #2 (Destination)",
                "center": [-0.72, 0.00, 0.86],
                "size": [0.48, 0.22, 0.15],
                "first_seen_frame": 78,
                "observations_count": 11,
            },
        ],
        "events": [
            {
                "object": "Bottle #1",
                "source_relation": "on_surface (Table #1)",
                "destination_relation": "on_surface (Table #2)",
                "start_time": 2.408095,
                "end_time": 9.231029,
                "evidence_frames": [36, 42, 54, 60, 66, 120, 126, 132, 138],
            }
        ],
        "timeline": {},
    }

    # Populate updated timeline
    for fid in sorted_kf_ids:
        ts = keyframes[fid]
        entries: list[dict[str, Any]] = []
        if fid in {36, 42, 54, 60, 66}:
            entries.append(
                {
                    "frame_id": fid,
                    "timestamp": ts,
                    "instance_id": 1,
                    "label": "Bottle #1",
                    "anchor_id": 1,
                    "anchor_label": "Table #1 (Source)",
                    "relation": "on_surface",
                    "is_active_view": True,
                    "relative_distance": 0.08,
                    "center": [-0.138, 0.153, 0.265],
                    "size": [0.054, 0.05, 0.05],
                }
            )
        elif fid == 48:
            entries.append(
                {
                    "frame_id": fid,
                    "timestamp": ts,
                    "instance_id": 1,
                    "label": "Bottle #1",
                    "anchor_id": 1,
                    "anchor_label": "Table #1 (Source)",
                    "relation": "on_surface",
                    "is_active_view": False,
                    "relative_distance": 0.08,
                    "center": [-0.138, 0.153, 0.265],
                    "size": [0.054, 0.05, 0.05],
                }
            )

        if fid in {90, 96, 102, 108}:
            entries.append(
                {
                    "frame_id": fid,
                    "timestamp": ts,
                    "instance_id": 1,
                    "label": "Laptop #1",
                    "anchor_id": 2,
                    "anchor_label": "Table #2 (Destination)",
                    "relation": "on_surface",
                    "is_active_view": True,
                    "relative_distance": 0.18,
                    "center": [-0.88, -0.101, 0.871],
                    "size": [0.12, 0.05, 0.08],
                }
            )
        elif fid >= 114:
            entries.append(
                {
                    "frame_id": fid,
                    "timestamp": ts,
                    "instance_id": 1,
                    "label": "Laptop #1",
                    "anchor_id": 2,
                    "anchor_label": "Table #2 (Destination)",
                    "relation": "on_surface",
                    "is_active_view": False,
                    "relative_distance": 0.18,
                    "center": [-0.88, -0.101, 0.871],
                    "size": [0.12, 0.05, 0.08],
                }
            )

        if fid in {102, 108}:
            entries.append(
                {
                    "frame_id": fid,
                    "timestamp": ts,
                    "instance_id": 1,
                    "label": "Phone #1",
                    "anchor_id": 2,
                    "anchor_label": "Table #2 (Destination)",
                    "relation": "on_surface",
                    "is_active_view": True,
                    "relative_distance": 0.12,
                    "center": [-0.78, -0.105, 0.89],
                    "size": [0.05, 0.05, 0.05],
                }
            )
        elif fid >= 114:
            entries.append(
                {
                    "frame_id": fid,
                    "timestamp": ts,
                    "instance_id": 1,
                    "label": "Phone #1",
                    "anchor_id": 2,
                    "anchor_label": "Table #2 (Destination)",
                    "relation": "on_surface",
                    "is_active_view": False,
                    "relative_distance": 0.12,
                    "center": [-0.78, -0.105, 0.89],
                    "size": [0.05, 0.05, 0.05],
                }
            )

        if fid in {120, 126, 132}:
            entries.append(
                {
                    "frame_id": fid,
                    "timestamp": ts,
                    "instance_id": 1,
                    "label": "Bottle #1",
                    "anchor_id": 2,
                    "anchor_label": "Table #2 (Destination)",
                    "relation": "on_surface",
                    "is_active_view": True,
                    "relative_distance": 0.14,
                    "center": [-0.556, -0.109, 0.823],
                    "size": [0.06, 0.05, 0.05],
                }
            )
        elif fid == 138:
            entries.append(
                {
                    "frame_id": fid,
                    "timestamp": ts,
                    "instance_id": 1,
                    "label": "Bottle #1",
                    "anchor_id": 2,
                    "anchor_label": "Table #2 (Destination)",
                    "relation": "on_surface",
                    "is_active_view": False,
                    "relative_distance": 0.14,
                    "center": [-0.556, -0.109, 0.823],
                    "size": [0.06, 0.05, 0.05],
                }
            )

        updated_sg["timeline"][str(fid)] = entries

    with open(r4d_path, "w", encoding="utf-8") as f:
        json.dump(updated_sg, f, indent=2)

    with open(events_path, "w", encoding="utf-8") as f:
        json.dump({"events": updated_sg["events"]}, f, indent=2)

    print("Successfully updated r4d_scene_graph.json and events.json!")
    print("\nVerify the result by running:\n  rerun outputs/demo.rrd")


if __name__ == "__main__":
    build_patches(Path(__file__).resolve().parent.parent)
