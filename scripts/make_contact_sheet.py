"""Build a labelled contact sheet of a video for manual room annotation."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument("--width", type=int, default=320)
    args = parser.parse_args()

    duration = float(
        subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=nw=1:nk=1",
                str(args.video),
            ],
            text=True,
        ).strip()
    )
    interval = max(0.1, duration / args.count)
    columns = 4
    rows = (args.count + columns - 1) // columns
    filter_chain = (
        f"fps=1/{interval:.4f},scale={args.width}:-2,"
        f"drawtext=text='t=%{{pts\\:hms}}':fontsize=16:fontcolor=white:"
        f"box=1:boxcolor=black@0.7:boxborderw=3:x=4:y=4,"
        f"tile={columns}x{rows}:padding=4:margin=4"
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(args.video),
            "-vf",
            filter_chain,
            "-frames:v",
            "1",
            str(args.out),
        ],
        check=True,
    )
    print(f"Wrote {args.out} ({duration:.1f}s, every {interval:.1f}s)")


if __name__ == "__main__":
    main()
