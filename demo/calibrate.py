"""One command that chooses --segment-frames and records the evidence.

No GPU and no Modal needed for the normal path: it reads the stage timings
already written by your real pipeline runs in ``outputs/*/benchmark_stats.json``
and, if you give it a short live capture, the accepted keyframe rate from
``aegis.evaluation.summarise_live_session``.

It writes two files:

    outputs/evaluation/vggt_window.json   # what demo/preflight.py validates
    demo/demo.conf                        # defaults sourced by demo/run_demo.sh

Optional ``--measure`` re-runs the GPU sweep on Modal and streams its output
instead of leaving you staring at a silent terminal for eight minutes.

Usage:
    uv run python -m demo.calibrate --capture captures/short-walk
    uv run python -m demo.calibrate --capture captures/short-walk --measure
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from aegis.core.config import load_config
from aegis.evaluation.measurements import summarise_live_session

DEFAULT_GPU_TOTAL_GB = 22.06  # measured on this workspace's L4
VRAM_HEADROOM = 0.85
DEFAULT_TARGET_SECONDS = 90.0
DEFAULT_ACCEPTED_FPS = 0.5  # stated as an assumption when no capture is given


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def local_vggt_evidence(
    outputs_root: Path, gpu_total_gb: float
) -> tuple[list[dict[str, Any]], float | None]:
    """Return (rows, seconds per keyframe) from real downloaded stage stats."""
    rows: list[dict[str, Any]] = []
    seconds_per_keyframe: list[float] = []
    for stats_path in sorted(outputs_root.glob("*/benchmark_stats.json")):
        stats = _read_json(stats_path) or {}
        stages = stats.get("stages", {})
        vggt = stages.get("vggt", {}) if isinstance(stages, dict) else {}
        keyframes = vggt.get("keyframe_count")
        peak = vggt.get("peak_vram_gb")
        elapsed = vggt.get("elapsed_seconds")
        if not keyframes or not peak or not elapsed:
            continue
        fraction = round(float(peak) / gpu_total_gb, 3)
        seconds_per_keyframe.append(float(elapsed) / float(keyframes))
        rows.append(
            {
                "keyframes": int(keyframes),
                "seconds": round(float(elapsed), 2),
                "peak_vram_gb": round(float(peak), 2),
                "vram_fraction": fraction,
                "ok": fraction <= VRAM_HEADROOM,
                "source": stats_path.parent.name,
            }
        )
    rows.sort(key=lambda row: row["keyframes"])
    typical = (
        round(sorted(seconds_per_keyframe)[len(seconds_per_keyframe) // 2], 3)
        if seconds_per_keyframe
        else None
    )
    return rows, typical


def accepted_keyframe_rate(capture: Path | None) -> tuple[float | None, str]:
    if capture is None:
        return None, f"assumption: {DEFAULT_ACCEPTED_FPS} kept frames/second"
    summary = summarise_live_session(capture)
    duration = float(summary.get("wall_duration_seconds") or 0)
    kept = int(summary.get("frames_kept") or 0)
    if duration <= 0 or kept <= 0:
        return None, "capture had no kept frames; falling back to the assumption"
    return round(kept / duration, 3), f"measured from {capture}"


def choose_segment_frames(
    recommended_max: int,
    rate: float,
    target_seconds: float,
) -> int:
    # Keep a segment near the target wall-time of walking, but never exceed
    # the proven reconstruction ceiling. Round to a multiple of 10.
    wanted = int(round(target_seconds * rate / 10.0) * 10)
    ceiling = min(recommended_max, 120)
    floor = min(20, ceiling)
    value = max(floor, min(wanted, ceiling))
    return value - (value % 10)


def modal_measurement(
    dataset_id: str, sizes: list[int], config_path: Path
) -> str | None:
    """Run the GPU sweep, streaming output so the terminal is never silent."""
    cmd = [
        "uv",
        "run",
        "modal",
        "run",
        "scripts/measure_vggt_window.py",
        "--dataset-id",
        dataset_id,
        "--sizes",
        ",".join(str(size) for size in sizes),
        "--config-path",
        str(config_path),
    ]
    print(
        "==> Modal measurement (first run can take ~10 min; progress streams below)",
        flush=True,
    )
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    output: list[str] = []
    assert process.stdout is not None
    for line in process.stdout:
        output.append(line)
        print(line, end="", flush=True)
    process.wait()
    return "".join(output) if process.returncode == 0 else None


def _parse_json_blob(text: str) -> dict[str, Any] | None:
    matches = re.findall(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    for candidate in reversed(matches):
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and "recommended_max_keyframes" in value:
            return value
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outputs-root", type=Path, default=Path("outputs"))
    parser.add_argument("--config-path", type=Path, default=Path("config/live.yaml"))
    parser.add_argument(
        "--capture",
        type=Path,
        default=None,
        help="a short live capture used to measure the kept-frame rate",
    )
    parser.add_argument("--gpu-total-gb", type=float, default=DEFAULT_GPU_TOTAL_GB)
    parser.add_argument("--target-seconds", type=float, default=DEFAULT_TARGET_SECONDS)
    parser.add_argument(
        "--measure",
        action="store_true",
        help="also run a fresh Modal GPU sweep (streams progress)",
    )
    parser.add_argument("--measure-dataset", default="demo04")
    parser.add_argument(
        "--segment-frames",
        type=int,
        default=None,
        help="override the computed recommendation",
    )
    args = parser.parse_args(argv)

    config = load_config(str(args.config_path))
    rows, spk = local_vggt_evidence(args.outputs_root, args.gpu_total_gb)
    proven = [row["keyframes"] for row in rows if row.get("ok")]
    recommended_max = max(proven) if proven else int(config.vggt.max_keyframes)

    if args.measure:
        sizes = [
            size for size in (32, 64, 96, 120) if size <= config.vggt.max_keyframes
        ]
        if config.vggt.max_keyframes not in sizes:
            sizes.append(config.vggt.max_keyframes)
        text = modal_measurement(args.measure_dataset, sizes, args.config_path)
        fresh = _parse_json_blob(text) if text else None
        if fresh and fresh.get("recommended_max_keyframes"):
            recommended_max = max(
                recommended_max, int(fresh["recommended_max_keyframes"])
            )
            rows.extend(fresh.get("rows", []))
            fresh_spk = [
                row["seconds"] / row["keyframes"]
                for row in fresh.get("rows", [])
                if row.get("ok") and row.get("keyframes") and row.get("seconds")
            ]
            if fresh_spk:
                spk = round(sum(fresh_spk) / len(fresh_spk), 3)

    rate, rate_source = accepted_keyframe_rate(args.capture)
    using_default = rate is None
    if rate is None:
        rate = DEFAULT_ACCEPTED_FPS
    segment_frames = args.segment_frames or choose_segment_frames(
        recommended_max, rate, args.target_seconds
    )
    if segment_frames > recommended_max:
        print(
            f"error: {segment_frames} exceeds the proven ceiling {recommended_max}; "
            "lower --segment-frames",
            file=sys.stderr,
        )
        return 2

    result_dir = Path("outputs/evaluation")
    result_dir.mkdir(parents=True, exist_ok=True)
    result_path = result_dir / "vggt_window.json"
    result_path.write_text(
        json.dumps(
            {
                "gpu_total_gb": args.gpu_total_gb,
                "rows": rows,
                "recommended_max_keyframes": recommended_max,
                "seconds_per_keyframe": spk,
                "accepted_keyframe_rate": rate,
                "accepted_rate_source": rate_source,
                "segment_frames": segment_frames,
                "config_path": str(args.config_path),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    conf = Path("demo/demo.conf")
    conf.parent.mkdir(parents=True, exist_ok=True)
    conf.write_text(
        "# generated by demo/calibrate.py — run_demo.sh sources this\n"
        f"SEGMENT_FRAMES={segment_frames}\n"
        f"DATASET_ID=live_demo\n"
        f"HOME_ID=aegis-demo\n",
        encoding="utf-8",
    )

    seconds_of_walk = round(segment_frames / rate, 1)
    process_seconds = round(segment_frames * (spk or 2.0), 1)
    print("=" * 78)
    print("  AEGIS DEMO CALIBRATION")
    print("=" * 78)
    print(f"  Proven reconstruction ceiling : {recommended_max} keyframes")
    print(f"  Typical VGGT time             : {spk or '~2.0 (assumed)'} s/keyframe")
    print(f"  Kept-frame rate               : {rate} fps  ({rate_source})")
    print(f"  --> USE --segment-frames {segment_frames}")
    print(
        f"      That is ~{seconds_of_walk} s of walking per segment and "
        f"~{process_seconds} s to process."
    )
    if using_default:
        print(
            "      NOTE: pass --capture <short-session> to replace the rate assumption."
        )
    print(f"  Wrote {result_path}")
    print(f"  Wrote {conf} (run_demo.sh picks this up automatically)")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
