"""DUSt3R multi-view 3D reconstruction adapter.

This module is imported only inside the Modal GPU DUSt3R worker.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

from aegis.poc.core.config import Dust3rConfig

DUST3R_SOURCE = Path("/opt/dust3r")


def _make_pairs(n_images: int) -> list[tuple[int, int]]:
    """Build a connected pair graph for DUSt3R multi-view alignment."""
    pairs: list[tuple[int, int]] = []
    for i in range(n_images - 1):
        pairs.append((i, i + 1))
        if i + 2 < n_images:
            pairs.append((i, i + 2))
    return pairs


def run_dust3r_reconstruction(
    image_paths: Sequence[Path],
    weights_path: Path,
    config: Dust3rConfig,
    *,
    actor_boxes_by_image: Sequence[list[tuple[float, float, float, float]]] | None = None,
) -> dict[str, Any]:
    """Execute DUSt3R multi-view inference, global alignment, and Layer 1 voxel grid fusion.

    Parameters
    ----------
    image_paths : Sequence[Path]
        List of paths to keyframe images.
    weights_path : Path
        Path to DUSt3R model checkpoint (.pth).
    config : Dust3rConfig
        DUSt3R configuration parameters.
    actor_boxes_by_image : Sequence[list[tuple[float, float, float, float]]] | None, optional
        Optional list of actor bounding boxes (x1, y1, x2, y2) per image to exclude from static map.

    Returns
    -------
    dict[str, Any]
        Dictionary containing:
        - 'pointmaps': np.ndarray of shape (N, H, W, 3)
        - 'confmaps': np.ndarray of shape (N, H, W)
        - 'poses': np.ndarray of shape (N, 4, 4)
        - 'global_points': np.ndarray of shape (M, 3)
        - 'global_colors': np.ndarray of shape (M, 3)
        - 'image_names': list[str]
    """
    import argparse

    import cv2
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("DUSt3R reconstruction requires a CUDA GPU")

    # Allowlist argparse.Namespace and wrap torch.load for PyTorch 2.6+ compatibility
    if hasattr(torch.serialization, "add_safe_globals"):
        torch.serialization.add_safe_globals([argparse.Namespace])

    _orig_torch_load = torch.load

    def _safe_torch_load(*args: Any, **kwargs: Any) -> Any:
        if "weights_only" not in kwargs:
            kwargs["weights_only"] = False
        return _orig_torch_load(*args, **kwargs)

    torch.load = _safe_torch_load  # type: ignore[assignment]

    # Add DUSt3R source to path if installed in /opt/dust3r
    if DUST3R_SOURCE.exists() and str(DUST3R_SOURCE) not in sys.path:
        sys.path.insert(0, str(DUST3R_SOURCE))

    from dust3r.cloud_opt import global_aligner
    from dust3r.image_pairs import make_pairs
    from dust3r.inference import inference
    from dust3r.model import AsymmetricCroCo3DStereo
    from dust3r.utils.image import load_images

    device = "cuda"
    model = AsymmetricCroCo3DStereo.from_pretrained(str(weights_path)).to(device)

    model.eval()

    # Load and resize images
    images = load_images([str(p) for p in image_paths], size=config.image_size)

    # Construct pair graph (sliding window for video sequences)
    scene_graph = "complete" if len(images) <= 8 else "swin-5-2"
    pairs = make_pairs(images, scene_graph=scene_graph, prefilter=None, symmetrize=True)

    if not pairs:
        pairs = []
        for i in range(len(images) - 1):
            pairs.append((images[i], images[i + 1]))
            if i + 2 < len(images):
                pairs.append((images[i], images[i + 2]))

    # Run pairwise ViT inference
    output = inference(pairs, model, device, batch_size=config.batch_size, verbose=False)

    # Merge batched output if returned as a list of batch dictionaries
    if isinstance(output, list):
        if not output:
            raise RuntimeError("DUSt3R inference produced empty results")
        if len(output) == 1 and isinstance(output[0], dict) and "view1" in output[0]:
            aligned_input = output[0]
        else:
            merged: dict[str, Any] = {"view1": {}, "view2": {}, "pred1": {}, "pred2": {}}
            for top_key in ["view1", "view2", "pred1", "pred2"]:
                first_sub = output[0][top_key]
                if isinstance(first_sub, dict):
                    merged[top_key] = {}
                    for sub_key in first_sub:
                        sub_vals = [item[top_key][sub_key] for item in output]
                        if torch.is_tensor(sub_vals[0]):
                            merged[top_key][sub_key] = torch.cat(sub_vals, dim=0)
                        elif isinstance(sub_vals[0], list):
                            merged[top_key][sub_key] = [elem for sub in sub_vals for elem in sub]
                        elif isinstance(sub_vals[0], tuple):
                            merged[top_key][sub_key] = tuple(elem for sub in sub_vals for elem in sub)
                        elif isinstance(sub_vals[0], np.ndarray):
                            merged[top_key][sub_key] = np.concatenate(sub_vals, axis=0)
                        else:
                            merged[top_key][sub_key] = sub_vals

                elif torch.is_tensor(first_sub):
                    merged[top_key] = torch.cat([item[top_key] for item in output], dim=0)
                else:
                    merged[top_key] = [item[top_key] for item in output]
            aligned_input = merged
    else:
        aligned_input = output

    # Perform joint global alignment optimization
    scene = global_aligner(aligned_input, device=device, verbose=False)
    scene.compute_global_alignment(init="mst", niter=config.niter, schedule="cosine", lr=0.01)

    # Retrieve 3D pointmaps and confidence maps
    pts3d = [pt.detach().cpu().numpy() if torch.is_tensor(pt) else np.asarray(pt) for pt in scene.get_pts3d()]
    conf = [c.detach().cpu().numpy() if torch.is_tensor(c) else np.asarray(c) for c in scene.get_conf()]
    raw_poses = [p.detach().cpu().numpy() if torch.is_tensor(p) else np.asarray(p) for p in scene.get_im_poses()]

    # Normalize poses so the first keyframe is at origin
    poses = np.stack(raw_poses, axis=0).astype(np.float64)
    origin_inv = np.linalg.inv(poses[0])
    poses = np.stack([origin_inv @ p for p in poses], axis=0)

    # Transform all pointmaps to the origin-normalized coordinate frame
    pointmaps: list[np.ndarray] = []
    for pt in pts3d:
        h, w, _ = pt.shape
        flat = pt.reshape(-1, 3).astype(np.float64)
        homogeneous = np.concatenate([flat, np.ones((len(flat), 1))], axis=1)
        transformed = (homogeneous @ origin_inv.T)[:, :3]
        pointmaps.append(transformed.reshape(h, w, 3).astype(np.float32))

    # Build filtered global point cloud with dynamic actor masking
    global_points_list: list[np.ndarray] = []
    global_colors_list: list[np.ndarray] = []

    for i, (pm, cm, img_path) in enumerate(zip(pointmaps, conf, image_paths, strict=True)):
        img = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
        if img is None:
            continue
        h, w, _ = pm.shape
        img_resized = cv2.resize(img, (w, h))
        img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)

        valid_mask = (cm >= config.min_conf_thr) & np.isfinite(pm).all(axis=2) & np.isfinite(cm)

        # Exclude dynamic human actor bounding boxes from static room fusion
        if actor_boxes_by_image is not None and i < len(actor_boxes_by_image):
            actor_boxes = actor_boxes_by_image[i]
            if actor_boxes:
                orig_h, orig_w = img.shape[:2]
                scale_x, scale_y = w / float(orig_w), h / float(orig_h)
                actor_mask = np.zeros((h, w), dtype=bool)
                for bx1, by1, bx2, by2 in actor_boxes:
                    ix1 = max(0, min(w - 1, round(bx1 * scale_x)))
                    iy1 = max(0, min(h - 1, round(by1 * scale_y)))
                    ix2 = max(0, min(w, round(bx2 * scale_x)))
                    iy2 = max(0, min(h, round(by2 * scale_y)))
                    actor_mask[iy1:iy2, ix1:ix2] = True
                valid_mask &= ~actor_mask

        if not np.any(valid_mask):
            continue

        valid_pts = pm[valid_mask]
        valid_cols = img_rgb[valid_mask]

        global_points_list.append(valid_pts)
        global_colors_list.append(valid_cols)

    if not global_points_list:
        raise RuntimeError("DUSt3R produced no valid points above the confidence threshold")

    all_pts = np.concatenate(global_points_list, axis=0)
    all_cols = np.concatenate(global_colors_list, axis=0)

    # Layer 1: Apply 3D Voxel Grid Downsampling to eliminate multi-view duplicate surfaces
    from aegis.poc.geometry.lifting import voxel_downsample

    voxel_pts, voxel_cols = voxel_downsample(all_pts, all_cols, voxel_size=0.0035)

    return {
        "pointmaps": np.stack(pointmaps, axis=0),  # (N, H, W, 3)
        "confmaps": np.stack(conf, axis=0),        # (N, H, W)
        "poses": poses.astype(np.float32),         # (N, 4, 4)
        "global_points": voxel_pts.astype(np.float32),
        "global_colors": voxel_cols.astype(np.uint8),
        "image_names": [p.name for p in image_paths],
    }
