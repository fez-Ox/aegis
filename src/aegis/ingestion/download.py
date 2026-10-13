"""Video downloading, ingestion, and staging utilities for Aegis.

Allows importing any local video or downloading longer indoor egocentric videos
(e.g., from HuggingFace egocentric benchmarks, OC-NaVQA, Ego4D) into the canonical
data directory and synchronizing with Modal storage volumes.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Curated indoor egocentric benchmark datasets and tasks
EGOCENTRIC_PRESETS: dict[str, dict[str, str]] = {
    "arrange_pots": {
        "dataset": "Hubdata/egocentric-iphone-rgb",
        "file": "#10_iPhone_Arrange_Pots_And_Pans.mp4",
        "task": "Arrange Pots And Pans in Kitchen",
        "url": "https://huggingface.co/datasets/Hubdata/egocentric-iphone-rgb/resolve/main/%2310_iPhone_Arrange_Pots_And_Pans.mp4",
    },
    "make_coffee": {
        "dataset": "Hubdata/egocentric-iphone-rgb",
        "file": "#12_iPhone_Make_Coffee.mp4",
        "task": "Make Coffee in Kitchen",
        "url": "https://huggingface.co/datasets/Hubdata/egocentric-iphone-rgb/resolve/main/%2312_iPhone_Make_Coffee.mp4",
    },
    "sort_clothes": {
        "dataset": "Hubdata/egocentric-iphone-rgb",
        "file": "#17_iPhone_Sort_Dirty_Clothes_Take1.mp4",
        "task": "Sort Dirty Clothes in Bedroom / Laundry",
        "url": "https://huggingface.co/datasets/Hubdata/egocentric-iphone-rgb/resolve/main/%2317_iPhone_Sort_Dirty_Clothes_Take1.mp4",
    },
    "put_shoes": {
        "dataset": "Hubdata/egocentric-iphone-rgb",
        "file": "#05_iPhone_Put_Shoes_Into_The_Cabinet_Actor5_Take1.mp4",
        "task": "Put Shoes Into The Storage Cabinet",
        "url": "https://huggingface.co/datasets/Hubdata/egocentric-iphone-rgb/resolve/main/%2305_iPhone_Put_Shoes_Into_The_Cabinet_Actor5_Take1.mp4",
    },
    "fridge_food": {
        "dataset": "Hubdata/egocentric-iphone-rgb",
        "file": "#32_iPhone_Put_Leftover_Food_Into_The_Fridge_Compartment.mp4",
        "task": "Put Leftover Food Into The Fridge Compartment",
        "url": "https://huggingface.co/datasets/Hubdata/egocentric-iphone-rgb/resolve/main/%2332_iPhone_Put_Leftover_Food_Into_The_Fridge_Compartment.mp4",
    },
    "set_table": {
        "dataset": "Hubdata/egocentric-iphone-rgb",
        "file": "#33_iPhone_Set_The_Dining_Table_Take1.mp4",
        "task": "Set The Dining Table",
        "url": "https://huggingface.co/datasets/Hubdata/egocentric-iphone-rgb/resolve/main/%2333_iPhone_Set_The_Dining_Table_Take1.mp4",
    },
    "empty_trash": {
        "dataset": "Hubdata/egocentric-iphone-rgb",
        "file": "#08_iPhone_Empty_The_Trash.mp4",
        "task": "Empty The Trash",
        "url": "https://huggingface.co/datasets/Hubdata/egocentric-iphone-rgb/resolve/main/%2308_iPhone_Empty_The_Trash.mp4",
    },
    "pick_place_table": {
        "dataset": "HoyerChou/EgocentricVideos",
        "file": "2026-01-05_19-35-47-pick-place.mp4",
        "task": "Pick and Place Manipulation on Table",
        "url": "https://huggingface.co/datasets/HoyerChou/EgocentricVideos/resolve/main/2026-01-05_19-35-47-pick-place.mp4",
    },
}


def probe_video(video_path: Path) -> dict[str, Any]:
    """Inspect video properties (duration, fps, resolution, frame count) using OpenCV."""
    import cv2

    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"OpenCV could not open video: {video_path}")

    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        if fps <= 0:
            fps = 30.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps > 0 else 0.0
        size_bytes = video_path.stat().st_size
    finally:
        cap.release()

    return {
        "path": str(video_path.resolve()),
        "fps": round(fps, 3),
        "width": width,
        "height": height,
        "resolution": [width, height],
        "frame_count": frame_count,
        "duration_seconds": round(duration, 3),
        "size_mb": round(size_bytes / (1024**2), 2),
    }


def download_file(url: str, dest_path: Path, chunk_size: int = 1024 * 1024) -> Path:
    """Download file from HTTP/HTTPS URL with streaming."""
    import httpx

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_dest = dest_path.with_suffix(dest_path.suffix + ".downloading")

    print(f"Downloading from {url} -> {dest_path.name}...")
    headers = {"User-Agent": "Aegis-SpatioTemporal-Ingestion/0.1.0"}
    with httpx.stream(
        "GET", url, headers=headers, follow_redirects=True, timeout=600.0
    ) as resp:
        if resp.status_code != 200:
            raise RuntimeError(
                f"Download failed with HTTP status {resp.status_code}: {url}"
            )
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        with open(temp_dest, "wb") as f:
            for chunk in resp.iter_bytes(chunk_size=chunk_size):
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = (downloaded / total) * 100
                    print(
                        f"\r  • Progress: {downloaded / (1024**2):.1f} / {total / (1024**2):.1f} MB ({pct:.1f}%)",
                        end="",
                        flush=True,
                    )
        print()

    temp_dest.replace(dest_path)
    print(
        f"✓ Download complete: {dest_path} ({dest_path.stat().st_size / (1024**2):.1f} MB)"
    )
    return dest_path


def ingest_video(
    source: str | Path,
    dataset_id: str | None = None,
    output_dir: Path | None = None,
    task_description: str | None = None,
    upload_to_modal: bool = False,
    modal_volume: str = "aegis-poc-data",
) -> dict[str, Any]:
    """Ingest any input video (file path, URL, or egocentric preset) into data/<dataset_id>/.

    Parameters
    ----------
    source : str | Path
        Local file path, http/https URL, or preset key (e.g., 'sort_clothes', 'make_coffee').
    dataset_id : str | None, optional
        Target dataset identifier (e.g. 'demo05', 'demo_kitchen'). Inferred if None.
    output_dir : Path | None, optional
        Target data directory. Defaults to Path('data') / dataset_id.
    task_description : str | None, optional
        Optional description of the task or scene.
    upload_to_modal : bool, optional
        Whether to immediately sync the video to the Modal storage volume.
    modal_volume : str, optional
        Name of the Modal data volume (default: 'aegis-poc-data').

    Returns
    -------
    dict[str, Any]
        Metadata dictionary with video properties and dataset paths.
    """
    source_str = str(source).strip()

    # 1. Check if source is a recognized preset key
    preset_meta: dict[str, str] = {}
    if source_str in EGOCENTRIC_PRESETS:
        preset_key = source_str
        preset_meta = EGOCENTRIC_PRESETS[preset_key]
        source_url = preset_meta["url"]
        task_description = task_description or preset_meta.get("task")
        if not dataset_id:
            dataset_id = f"demo_{preset_key}"
    elif source_str.startswith(("http://", "https://")):
        source_url = source_str
        if not dataset_id:
            # Extract clean name from URL
            filename = urllib.parse.unquote(
                Path(urllib.parse.urlparse(source_url).path).name
            )
            base = Path(filename).stem.replace("#", "").replace(" ", "_").lower()
            dataset_id = base[:24] if base else "custom_video"
    else:
        source_url = ""
        local_src = Path(source_str)
        if not local_src.exists():
            raise FileNotFoundError(f"Input video does not exist: {local_src}")
        if not dataset_id:
            base = local_src.stem.replace(" ", "_").lower()
            dataset_id = base[:24] if base else "custom_video"

    # Clean dataset_id to be filesystem and Modal-safe
    dataset_id = "".join(c if (c.isalnum() or c in "._-") else "_" for c in dataset_id)
    target_data_dir = output_dir or (Path("data") / dataset_id)
    target_data_dir.mkdir(parents=True, exist_ok=True)
    target_video_file = target_data_dir / "video.mp4"

    # 2. Populate target video file
    if source_url:
        if not target_video_file.exists() or target_video_file.stat().st_size == 0:
            download_file(source_url, target_video_file)
        else:
            print(f"Using existing cached video: {target_video_file}")
    else:
        local_src = Path(source_str).resolve()
        if local_src != target_video_file.resolve():
            print(f"Copying video {local_src} -> {target_video_file}...")
            shutil.copy2(local_src, target_video_file)
        else:
            print(f"Using existing video at: {target_video_file}")

    # 3. Probe video properties
    info = probe_video(target_video_file)

    # 4. Write source_metadata.json
    meta = {
        "dataset_id": dataset_id,
        "source": source_str,
        "source_url": source_url or None,
        "task": task_description or f"Egocentric Activity: {dataset_id}",
        "duration_seconds": info["duration_seconds"],
        "fps": info["fps"],
        "resolution": info["resolution"],
        "frame_count": info["frame_count"],
        "size_mb": info["size_mb"],
        "preset": preset_meta.get("task"),
    }
    meta_path = target_data_dir / "source_metadata.json"
    meta_path.write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    info["metadata_file"] = str(meta_path)
    info["dataset_id"] = dataset_id
    info["dataset_dir"] = str(target_data_dir)

    print("=" * 68)
    print("  📹 VIDEO INGESTION COMPLETED")
    print("=" * 68)
    print(f"  • Dataset ID:        {dataset_id}")
    print(f"  • Video File:        {target_video_file}")
    print(
        f"  • Duration:          {info['duration_seconds']}s ({info['duration_seconds'] / 60:.2f} min)"
    )
    print(
        f"  • Resolution / FPS:  {info['resolution'][0]}x{info['resolution'][1]} @ {info['fps']} fps"
    )
    print(f"  • Frame Count:       {info['frame_count']} frames")
    print(f"  • Task:              {meta['task']}")
    print("-" * 68)

    # 5. Upload to Modal volume if requested
    if upload_to_modal:
        upload_to_modal_volume(
            target_video_file, f"{dataset_id}/video.mp4", volume_name=modal_volume
        )

    return info


def upload_to_modal_volume(
    local_path: Path,
    remote_path: str,
    volume_name: str = "aegis-poc-data",
    force: bool = True,
) -> bool:
    """Upload a local video or file to the specified Modal volume."""
    print(f"Syncing {local_path} -> modal://{volume_name}/{remote_path}...")
    cmd = [
        sys.executable,
        "-m",
        "modal",
        "volume",
        "put",
        volume_name,
        str(local_path),
        remote_path,
    ]
    if force:
        cmd.append("--force")

    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode == 0:
        print(f"  ✓ Uploaded to Modal Volume: {remote_path}")
        return True
    else:
        err = res.stderr.strip() or res.stdout.strip()
        print(f"  ⚠ Modal upload warning: {err}")
        return False
