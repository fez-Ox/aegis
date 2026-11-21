"""Download EgoLife day windows and cut them into pipeline-sized segments.

EgoLife serves one ~30 s MP4 per clip, so a 1-hour window is ~120 downloads.
Clips are cached, concatenated into ``segment_minutes`` buckets, and written as
``data/<dataset_id>/video.mp4`` plus ``source_metadata.json``. The segment's
real wall-clock start is stamped there, which is what lets the memory store
order days correctly.

    uv run python scripts/egolife_fetch.py --days 1-7
    uv run python scripts/egolife_fetch.py --days 1 --minutes 10 --dry-run
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

from aegis.core.timeutil import to_utc_iso
from aegis.evaluation.egolife import (
    Clip,
    dataset_id,
    group_segments,
    parse_clip,
    segment_start,
    select_window,
)

API = "https://huggingface.co/api/datasets/lmms-lab/EgoLife/tree/main"
RESOLVE = "https://huggingface.co/datasets/lmms-lab/EgoLife/resolve/main"


def parse_days(text: str) -> list[int]:
    days: set[int] = set()
    for part in text.split(","):
        part = part.strip()
        if "-" in part:
            low, high = part.split("-", 1)
            days.update(range(int(low), int(high) + 1))
        elif part:
            days.add(int(part))
    return sorted(days)


def list_day(client: httpx.Client, participant: str, day: int) -> list[Clip]:
    response = client.get(f"{API}/{participant}/DAY{day}?recursive=true")
    response.raise_for_status()
    clips: list[Clip] = []
    for item in response.json():
        if item.get("type") != "file":
            continue
        parsed = parse_clip(item["path"], int(item.get("size", 0)))
        if parsed is not None and parsed[0] == day:
            clips.append(parsed[1])
    return sorted(clips, key=lambda clip: clip.stamp)


def download(client: httpx.Client, clip: Clip, cache: Path) -> Path:
    destination = cache / clip.path
    if destination.exists() and destination.stat().st_size == clip.size_bytes:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".part")
    with client.stream("GET", f"{RESOLVE}/{clip.path}") as response:
        response.raise_for_status()
        with temporary.open("wb") as handle:
            for chunk in response.iter_bytes(1 << 20):
                handle.write(chunk)
    temporary.replace(destination)
    return destination


def concat(files: list[Path], output: Path, width: int, height: int, fps: int) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    listing = output.parent / "clips.txt"
    listing.write_text(
        "".join(f"file '{path.resolve()}'\n" for path in files), encoding="utf-8"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(listing),
            "-vf",
            f"scale={width}:{height}:flags=lanczos",
            "-r",
            str(fps),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-an",
            str(output),
        ],
        check=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--participant", default="A1_JAKE")
    parser.add_argument("--days", default="1-7")
    parser.add_argument("--start", default="12:00", help="window start, HH:MM")
    parser.add_argument("--minutes", type=int, default=60)
    parser.add_argument("--segment-minutes", type=int, default=5)
    parser.add_argument("--base-date", default="2026-01-05", help="wall clock of DAY1")
    parser.add_argument("--out", type=Path, default=Path("data"))
    parser.add_argument("--cache", type=Path, default=Path("data/_egolife_clips"))
    parser.add_argument("--width", type=int, default=704)
    parser.add_argument("--height", type=int, default=704)
    parser.add_argument("--fps", type=int, default=5)
    parser.add_argument("--jobs", type=int, default=6, help="parallel downloads")
    parser.add_argument("--force", action="store_true", help="re-cut existing segments")
    parser.add_argument("--dry-run", action="store_true", help="plan only")
    parser.add_argument(
        "--qa",
        action="store_true",
        help="also download the EgoLifeQA file to evaluation/annotations/",
    )
    args = parser.parse_args(argv)

    days = parse_days(args.days)
    if args.qa:
        target = (
            Path("evaluation") / "annotations" / f"egolife_qa_{args.participant}.json"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        url = f"{RESOLVE}/EgoLifeQA/EgoLifeQA_{args.participant}.json"
        with httpx.Client(follow_redirects=True, timeout=60) as client:
            target.write_bytes(client.get(url).raise_for_status().content)
        print(f"QA -> {target}")

    with (
        httpx.Client(follow_redirects=True, timeout=120) as client,
        ThreadPoolExecutor(max_workers=args.jobs) as pool,
    ):
        for day in days:
            clips = select_window(
                list_day(client, args.participant, day), args.start, args.minutes
            )
            segments = group_segments(
                clips, args.start, args.segment_minutes, min_clips=3
            )
            print(
                f"DAY{day}: {len(clips)} clips in {args.start}+{args.minutes}m "
                f"-> {len(segments)} segments"
            )
            for index, segment in enumerate(segments):
                name = dataset_id(day, index)
                start = segment_start(day, segment[0].stamp, args.base_date)
                video = args.out / name / "video.mp4"
                size_mb = sum(clip.size_bytes for clip in segment) / 1048576
                print(
                    f"  {name}: {len(segment)} clips, {size_mb:.0f} MB, "
                    f"from {start.isoformat()}"
                )
                if args.dry_run or (video.exists() and not args.force):
                    continue
                files = list(
                    pool.map(lambda clip: download(client, clip, args.cache), segment)
                )
                concat(files, video, args.width, args.height, args.fps)
                metadata = {
                    "dataset_id": name,
                    "source": f"EgoLife {args.participant} DAY{day} {args.start}",
                    "recorded_at": to_utc_iso(start),
                }
                (video.parent / "source_metadata.json").write_text(
                    json.dumps(metadata, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
    return 0


if __name__ == "__main__":
    sys.exit(main())
