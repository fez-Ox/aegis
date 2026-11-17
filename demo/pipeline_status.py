"""Print the live memory-backbone state from local artifacts.

This is a read-only view of the running demo. It intentionally reads only
files that the capture and pipeline already write:

    captures/<session>/{session.json,session_state.json,index.jsonl,pipeline_state.json}
    outputs/<segment>/benchmark_stats.json
    outputs/_homes/<home>/{home_map.json,memory.db}

No Modal calls, no network, no GPU.

Usage:
    uv run python -m demo.pipeline_status \
        --session captures/demo-20261117-101500 \
        --base-dataset-id live_demo \
        --home-id aegis-demo
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _jsonl_counts(path: Path) -> tuple[int, int, dict[str, int]]:
    """Return (frame_count, gap_count, gap counts by reason)."""
    frames = gaps = 0
    by_reason: dict[str, int] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return 0, 0, {}
    for line in lines:
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("record_type") == "gap":
            gaps += 1
            reason = str(record.get("reason", "unknown"))
            by_reason[reason] = by_reason.get(reason, 0) + 1
        else:
            frames += 1
    return frames, gaps, by_reason


def _manifest(session_dir: Path) -> dict[str, Any]:
    """session.json, falling back to the checkpoint written mid-capture."""
    for name in ("session.json", "session_state.json"):
        data = _read_json(session_dir / name)
        if data is not None:
            return data
    return {}


def capture_status(session_dir: Path) -> dict[str, Any]:
    manifest = _manifest(session_dir)
    frames, gaps, gap_reasons = _jsonl_counts(session_dir / "index.jsonl")
    state = _read_json(session_dir / "pipeline_state.json") or {}
    return {
        "session_id": manifest.get("session_id", session_dir.name),
        "status": manifest.get("status", "no manifest yet"),
        "frames_written": frames,
        "reported_frame_count": manifest.get("frame_count"),
        "gaps_in_index": gaps,
        "gap_reasons": gap_reasons,
        "segments_done": state.get("segments_done", []),
        "next_sequence": state.get("next_sequence", 0),
    }


def segment_statuses(
    base_dataset_id: str, outputs_root: Path = Path("outputs")
) -> list[dict[str, Any]]:
    """Read one benchmark_stats.json per promoted segment, in id order."""
    if not outputs_root.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    pattern = f"{base_dataset_id}_seg*/benchmark_stats.json"
    for stats_path in sorted(outputs_root.glob(pattern)):
        stats = _read_json(stats_path) or {}
        stages = stats.get("stages", {}) if isinstance(stats, dict) else {}
        vggt = stages.get("vggt", {}) if isinstance(stages, dict) else {}
        detect = stages.get("detect_and_lift", {}) or stages.get("detect", {})
        detect = detect if isinstance(detect, dict) else {}
        preprocess = stages.get("preprocess", {}) if isinstance(stages, dict) else {}
        rerun = stages.get("rerun", {}) if isinstance(stages, dict) else {}

        def secs(mapping: Any) -> float | None:
            value = (
                mapping.get("elapsed_seconds") if isinstance(mapping, dict) else None
            )
            return round(float(value), 1) if value is not None else None

        rows.append(
            {
                "segment": stats_path.parent.name,
                "keyframes": vggt.get("keyframe_count"),
                "preprocess_s": secs(preprocess),
                "vggt_s": secs(vggt),
                "detect_s": secs(detect),
                "rerun_s": secs(rerun),
                "events": detect.get("events"),
                "anchors": rerun.get("total_anchors"),
                "rooms": rerun.get("total_rooms"),
                "gravity_source": (vggt.get("gravity_source") or "unknown"),
                "gravity_confidence": vggt.get("gravity_confidence"),
                "rrd_mb": rerun.get("recording_size_mb"),
            }
        )
    return rows


def store_status(home_id: str, store_root: Path) -> dict[str, Any]:
    db_path = store_root / home_id / "memory.db"
    map_path = store_root / home_id / "home_map.json"
    result: dict[str, Any] = {
        "home_id": home_id,
        "db_exists": db_path.is_file(),
        "db_bytes": db_path.stat().st_size if db_path.is_file() else None,
    }
    # Counts through the real store API. Never open_store() when the file is
    # absent: that would create a database as a side effect of *viewing* status.
    if db_path.is_file():
        try:
            from aegis.memory.store import open_store

            store = open_store(home_id, store_root)
            try:
                result["counts"] = store.counts()
                result["sessions"] = [row["session_id"] for row in store.sessions()]
                result["latest_states"] = [
                    f"{state['label']}: {state['relation']} "
                    f"({state.get('anchor_label') or 'no anchor'})"
                    for state in store.latest_states()
                ]
            finally:
                store.close()
        except Exception as exc:  # noqa: BLE001 - status must never crash the show
            result["store_error"] = f"{type(exc).__name__}: {exc}"

    registry = _read_json(map_path) or {}
    result["rooms"] = [
        f"{room.get('label')} [{room.get('label_source')}]"
        for room in registry.get("rooms", [])
        if isinstance(room, dict)
    ]
    return result


def _fmt(value: Any, width: int = 8) -> str:
    return str("" if value is None else value).rjust(width)


def render(
    session_dir: Path,
    base_dataset_id: str,
    home_id: str,
    store_root: Path,
    outputs_root: Path = Path("outputs"),
) -> str:
    capture = capture_status(session_dir)
    segments = segment_statuses(base_dataset_id, outputs_root)
    store = store_status(home_id, store_root)

    lines: list[str] = []
    lines.append("=" * 96)
    lines.append("  AEGIS LIVE MEMORY BACKBONE")
    lines.append("=" * 96)
    lines.append(
        f"  Capture: {capture['session_id']}  status={capture['status']}  "
        f"frames={capture['frames_written']} (manifest={capture['reported_frame_count']})"
    )
    gaps = ", ".join(f"{k}={v}" for k, v in capture["gap_reasons"].items()) or "none"
    lines.append(f"  Gaps: {capture['gaps_in_index']}  [{gaps}]")
    lines.append(
        f"  Segments promoted: {len(capture['segments_done'])}  "
        f"next_sequence={capture['next_sequence']}"
    )
    lines.append("")
    lines.append(
        f"  {'segment':<34}{'kf':>5}{'prep':>8}{'vggt':>8}{'detect':>8}"
        f"{'rerun':>8}{'events':>8}{'rooms':>7}"
    )
    lines.append("  " + "-" * 92)
    if not segments:
        lines.append("  (no processed segments yet — waiting on the first one)")
    for row in segments:
        lines.append(
            f"  {row['segment']:<34}{_fmt(row['keyframes'], 5)}"
            f"{_fmt(row['preprocess_s'])}{_fmt(row['vggt_s'])}{_fmt(row['detect_s'])}"
            f"{_fmt(row['rerun_s'])}{_fmt(row['events'])}{_fmt(row['rooms'], 7)}"
        )
        if row["gravity_source"] and row["gravity_source"] != "unknown":
            lines.append(
                f"  {'':<34}gravity={row['gravity_source']} "
                f"confidence={row['gravity_confidence']}  rrd={row['rrd_mb']} MB"
            )
    lines.append("")
    lines.append(
        f"  Home store: {store['home_id']}  "
        f"db={store['db_bytes'] if store['db_bytes'] is not None else 'absent'} bytes"
    )
    if "store_error" in store:
        lines.append(f"  Store error: {store['store_error']}")
    if "counts" in store:
        counts = ", ".join(f"{k}={v}" for k, v in store["counts"].items() if v)
        lines.append(f"  Rows: {counts or 'empty'}")
        lines.append(f"  Sessions ingested: {', '.join(store['sessions']) or 'none'}")
        lines.append("  Latest memory:")
        for item in store["latest_states"] or ["(none)"]:
            lines.append(f"    - {item}")
    lines.append(f"  Rooms (home_map.json): {', '.join(store['rooms']) or 'none'}")
    lines.append("=" * 96)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path, help="captures/<session> directory")
    parser.add_argument("--base-dataset-id", default="live_demo")
    parser.add_argument("--home-id", default="aegis-demo")
    parser.add_argument(
        "--store-root",
        type=Path,
        default=Path("outputs/_homes"),
        help="AEGIS_STORE_ROOT (default: outputs/_homes)",
    )
    parser.add_argument(
        "--outputs-root",
        type=Path,
        default=Path("outputs"),
        help="downloaded artifacts root (default: outputs)",
    )
    args = parser.parse_args(argv)
    print(
        render(
            args.session,
            args.base_dataset_id,
            args.home_id,
            args.store_root,
            args.outputs_root,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
