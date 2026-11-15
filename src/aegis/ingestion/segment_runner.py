"""Process a live capture as a sequence of bounded segments.

Each segment is promoted as its own dataset and handed to ``process`` (in
the pipeline: upload, preprocess, reconstruct, detect, download, ingest).
Progress is checkpointed in ``<capture>/pipeline_state.json`` after every
segment, so a restart resumes where it stopped. With ``follow=True`` the
runner keeps promoting complete segments while the capture is still
running and finishes with the remaining tail.
"""

from __future__ import annotations

import shutil
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from aegis.core.config import CameraConfig, VideoConfig
from aegis.ingestion.contracts import (
    load_session_manifest,
    read_json_object,
    write_json_atomic,
)
from aegis.ingestion.live_handoff import PromotionResult, promote_live_segments

STATE_FILENAME = "pipeline_state.json"


def load_state(session_dir: Path) -> dict[str, Any]:
    path = session_dir / STATE_FILENAME
    if path.exists():
        state = read_json_object(path)
        return {
            "next_sequence": int(state.get("next_sequence", 0)),
            "next_index": int(state.get("next_index", 1)),
            "segments_done": list(state.get("segments_done", [])),
        }
    return {"next_sequence": 0, "next_index": 1, "segments_done": []}


def save_state(session_dir: Path, state: dict[str, Any]) -> None:
    write_json_atomic(session_dir / STATE_FILENAME, state)


def capture_running(session_dir: Path) -> bool:
    return load_session_manifest(session_dir).get("status") == "running"


def run_live_segments(
    session_dir: str | Path,
    *,
    base_dataset_id: str,
    segment_frames: int,
    process: Callable[[PromotionResult], None],
    data_root: str | Path = Path("data"),
    video: VideoConfig | None = None,
    camera: CameraConfig | None = None,
    follow: bool = False,
    keep_frames: bool = False,
    poll_seconds: float = 10.0,
    sleep: Callable[[float], None] = time.sleep,
) -> list[str]:
    """Promote and process every not-yet-processed segment; returns their ids."""

    session = Path(session_dir)
    state = load_state(session)
    processed: list[str] = []
    while True:
        running = follow and capture_running(session)
        results = promote_live_segments(
            session,
            base_dataset_id=base_dataset_id,
            segment_frames=segment_frames,
            data_root=data_root,
            video=video,
            camera=camera,
            start_sequence=state["next_sequence"],
            first_index=state["next_index"],
            include_tail=not running,
        )
        for result in results:
            process(result)
            state["next_sequence"] = result.last_sequence + 1
            state["next_index"] += 1
            state["segments_done"].append(result.dataset_id)
            save_state(session, state)
            processed.append(result.dataset_id)
            if not keep_frames:
                shutil.rmtree(result.dataset_dir / "frames", ignore_errors=True)
        if not running:
            return processed
        sleep(poll_seconds)
