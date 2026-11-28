"""Evidence crops: one small object-only image per state run.

A crop is cut from the run's sharpest observation (highest detection
confidence), padded a little, resized so its long side is ``max_side`` and
saved as JPEG. Full frames are never kept here; raw frames are purged under
the 24-hour rule while these crops remain as derived evidence (decision #9,
to be confirmed with the supervisor; controlled by ``memory.evidence``).
"""

from __future__ import annotations

import shutil
from collections.abc import Mapping, MutableMapping, Sequence
from pathlib import Path
from typing import Any

CARRIED = "carried_by_user"


def answer_evidence(
    state: Mapping[str, Any],
    *,
    crop_url: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """One complete evidence record for a non-abstaining answer.

    Every record carries an observation id, a timestamp, the anchor/room when
    known, and either a crop URL or an explicit text fallback. Missing image
    evidence is never silently represented as a null crop alone.
    """
    observation = (
        state.get("instance_id")
        or state.get("evidence_id")
        or state.get("activity_id")
    )
    observed_at = (
        state.get("last_seen_wallclock")
        or state.get("observed_at")
        or state.get("last_seen_at")
        or state.get("last_seen_ts")
    )
    anchor = state.get("anchor_label")
    room = state.get("room_label")
    description = description or "Object state from memory."
    if crop_url:
        fallback = None
    else:
        place = ", ".join(str(value) for value in (anchor, room) if value)
        fallback = f"No image crop available; {description}" + (
            f" ({place})." if place else "."
        )
    return {
        "observation_id": f"state:{observation}" if observation is not None else None,
        "observed_at": observed_at,
        "anchor_label": anchor,
        "room_label": room,
        "crop_url": crop_url,
        "text_fallback": fallback,
        "description": description,
    }


def evidence_complete(record: Mapping[str, Any]) -> bool:
    """Whether a record satisfies the P1.4 contract."""
    return bool(
        record.get("observation_id")
        and record.get("observed_at")
        and (record.get("anchor_label") or record.get("room_label"))
        and (record.get("crop_url") or record.get("text_fallback"))
    )


def crop_box(
    width: int, height: int, bbox: Sequence[float], pad: float
) -> tuple[int, int, int, int] | None:
    """Padded, clipped integer crop rectangle, or None when empty."""

    x1, y1, x2, y2 = (float(v) for v in bbox)
    pad_x, pad_y = (x2 - x1) * pad, (y2 - y1) * pad
    left = max(0, round(x1 - pad_x))
    top = max(0, round(y1 - pad_y))
    right = min(width, round(x2 + pad_x))
    bottom = min(height, round(y2 + pad_y))
    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom


def write_run_crops(
    runs: Sequence[MutableMapping[str, Any]],
    frames_dir: Path,
    frame_filename_by_id: Mapping[int, str],
    out_dir: Path,
    *,
    max_side: int = 320,
    pad: float = 0.15,
    quality: int = 85,
) -> int:
    """Write a crop per run and record it as ``run["evidence"]``.

    Carried runs get no crop (the object is in the wearer's hand). A run
    whose frame cannot be read gets ``evidence = None``; the stage goes on.
    Returns the number of crops written.
    """

    import cv2

    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for run in runs:
        run["evidence"] = None
        if run.get("relation") == CARRIED or run.get("best_bbox_2d") is None:
            continue
        filename = frame_filename_by_id.get(int(run.get("best_frame", -1)))
        if filename is None:
            continue
        image = cv2.imread(str(frames_dir / filename), cv2.IMREAD_COLOR)
        if image is None:
            continue
        height, width = image.shape[:2]
        rect = crop_box(width, height, run["best_bbox_2d"], pad)
        if rect is None:
            continue
        left, top, right, bottom = rect
        crop = image[top:bottom, left:right]
        scale = max_side / max(crop.shape[:2])
        if scale < 1.0:
            crop = cv2.resize(
                crop,
                (
                    max(1, round(crop.shape[1] * scale)),
                    max(1, round(crop.shape[0] * scale)),
                ),
                interpolation=cv2.INTER_AREA,
            )
        name = f"run_{int(run['instance_id'])}_{int(run.get('start_frame', 0))}.jpg"
        path = out_dir / name
        if not cv2.imwrite(str(path), crop, [cv2.IMWRITE_JPEG_QUALITY, int(quality)]):
            continue
        run["evidence"] = {
            "path": f"evidence/{name}",
            "frame_id": int(run["best_frame"]),
            "width": int(crop.shape[1]),
            "height": int(crop.shape[0]),
        }
        written += 1
    return written


def copy_into_store(
    store: Any,
    *,
    source: Path,
    session_id: str,
    instance_id: int,
    captured_at: str,
    meta: Mapping[str, Any],
    folder: str | None = None,
) -> int | None:
    """Copy one crop into ``<home>/evidence/<folder>/`` and add its row.

    ``session_id`` owns the row (the run's session); ``folder`` is the
    session being ingested, so a replacement crop never reuses a path.
    """

    if not source.is_file():
        return None
    relative = Path("evidence") / (folder or session_id) / source.name
    target = store.dir / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return store.insert(
        "evidence",
        {
            "session_id": session_id,
            "instance_id": instance_id,
            "path": str(relative),
            "captured_at": captured_at,
            "frame_id": meta.get("frame_id"),
            "width": meta.get("width"),
            "height": meta.get("height"),
            "bytes": target.stat().st_size,
        },
    )


def delete_evidence(store: Any, evidence_id: int) -> None:
    row = store.one("SELECT path FROM evidence WHERE evidence_id = ?", (evidence_id,))
    if row is None:
        return
    shared = store.one(
        "SELECT COUNT(*) FROM evidence WHERE path = ? AND evidence_id != ?",
        (row["path"], evidence_id),
    )[0]
    if not shared:
        (store.dir / str(row["path"])).unlink(missing_ok=True)
    store.execute("DELETE FROM evidence WHERE evidence_id = ?", (evidence_id,))
