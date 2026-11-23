"""Go / no-go checks for the live showcase.

Automates the local parts of ``docs/running_aegis.md`` Part B (B1, B2, B7):
toolchain, tests, Modal authentication, the Hugging Face token, the phone
stream, disk space, and the measured VGGT window used to pick
``--segment-frames``.

Everything here is local; the only network call is a single frame read from
the phone stream.

Usage:
    uv run python -m demo.preflight --stream-url http://192.168.1.23:8080/video \
        --segment-frames 60 \
        --vggt-window-result outputs/evaluation/vggt_window.json
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

PASS = "pass"
WARN = "warn"
FAIL = "fail"


@dataclass
class Check:
    name: str
    state: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _run(cmd: list[str], timeout: int = 120) -> tuple[int, str]:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, f"{type(exc).__name__}: {exc}"
    return result.returncode, (result.stdout + result.stderr).strip()


def check_python() -> Check:
    ok = sys.version_info[:2] == (3, 12)
    return Check(
        "python 3.12",
        PASS if ok else FAIL,
        ".".join(str(part) for part in sys.version_info[:3]),
    )


def check_git() -> Check:
    if not Path(".git").exists():
        return Check("git worktree", WARN, "no .git here")
    code, detail = _run(["git", "status", "--porcelain"])
    if code != 0:
        return Check("git worktree", WARN, detail)
    dirty = bool(detail.strip())
    return Check(
        "git worktree",
        WARN if dirty else PASS,
        "uncommitted changes: measurement evidence would be invalid"
        if dirty
        else "clean",
    )


def check_tests(enabled: bool) -> Check:
    if not enabled:
        return Check("pytest", WARN, "skipped (--quick)")
    code, detail = _run(["uv", "run", "pytest", "-q"], timeout=420)
    tail = "\n".join(detail.splitlines()[-3:])
    return Check("pytest", PASS if code == 0 else FAIL, tail or "no output")


def check_ruff(enabled: bool) -> Check:
    if not enabled:
        return Check("ruff", WARN, "skipped (--quick)")
    code, detail = _run(
        [
            "uvx",
            "ruff",
            "check",
            "src",
            "tests",
            "run_pipeline.py",
            "run_server.py",
            "demo",
        ],
        timeout=180,
    )
    return Check("ruff", PASS if code == 0 else FAIL, detail or "all checks passed")


def check_modal() -> Check:
    profile_code, profile = _run(["uv", "run", "modal", "profile", "current"], 90)
    secret_code, secrets = _run(["uv", "run", "modal", "secret", "list"], 90)
    volume_code, volumes = _run(["uv", "run", "modal", "volume", "list"], 90)
    problems: list[str] = []
    if profile_code != 0:
        problems.append("profile command failed")
    if secret_code != 0:
        problems.append("secret list command failed")
    if volume_code != 0:
        problems.append("volume list command failed")
    if "aegis-secrets" not in secrets:
        problems.append("aegis-secrets missing")
    for volume in ("aegis-poc-data", "aegis-model-cache"):
        if volume not in volumes:
            problems.append(f"{volume} missing")
    if problems:
        return Check("modal", FAIL, "; ".join(problems))
    return Check("modal", PASS, profile.splitlines()[-1] if profile else "configured")


def check_env_file(path: Path = Path(".env")) -> Check:
    if not path.is_file():
        return Check("HF_TOKEN", FAIL, f"{path} missing")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return Check("HF_TOKEN", FAIL, str(exc))
    for line in text.splitlines():
        if line.startswith("HF_TOKEN=") and line.split("=", 1)[1].strip():
            return Check("HF_TOKEN", PASS, "set in .env (never committed)")
    return Check("HF_TOKEN", FAIL, "HF_TOKEN empty in .env")


def check_stream(url: str | None) -> Check:
    if not url:
        return Check("phone stream", FAIL, "no URL (--stream-url or AEGIS_STREAM_URL)")
    try:
        request = urllib.request.Request(
            url, headers={"User-Agent": "aegis-preflight/1"}
        )
        with urllib.request.urlopen(request, timeout=6) as response:
            chunk = response.read(128)
            status = getattr(response, "status", 200)
    except Exception as exc:  # noqa: BLE001 - report any stream failure, do not guess
        return Check("phone stream", FAIL, f"{type(exc).__name__}: {exc}")
    ok = status == 200 and bool(chunk)
    return Check(
        "phone stream", PASS if ok else FAIL, f"HTTP {status}, {len(chunk)} bytes"
    )


def check_disk(path: Path = Path(".")) -> Check:
    free_gb = shutil.disk_usage(path).free / 1024**3
    ok = free_gb >= 10
    return Check(
        "disk space", PASS if ok else WARN, f"{free_gb:.1f} GiB free (need ~10)"
    )


def check_config(path: Path, segment_frames: int) -> Check:
    if not path.is_file():
        return Check("live config", FAIL, f"{path} missing")
    try:
        from aegis.core.config import load_config

        config = load_config(str(path))
    except Exception as exc:  # noqa: BLE001
        return Check("live config", FAIL, f"{type(exc).__name__}: {exc}")
    max_keyframes = config.vggt.max_keyframes
    stride = config.vggt.keyframe_stride
    if segment_frames <= 0:
        return Check("live config", FAIL, "--segment-frames must be positive")
    if segment_frames > max_keyframes:
        return Check(
            "segment size",
            FAIL,
            f"{segment_frames} > vggt.max_keyframes {max_keyframes}; "
            "lower --segment-frames or raise the config value",
        )
    return Check(
        "segment size",
        PASS,
        f"{segment_frames} frames/segment, stride={stride}, max_keyframes={max_keyframes}",
    )


def check_vggt_window(path: Path | None, segment_frames: int) -> Check:
    if path is None or not path.is_file():
        return Check(
            "VGGT window",
            WARN,
            "no measurement result; run scripts/measure_vggt_window.py and save its JSON",
        )
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
        recommended = int(result["recommended_max_keyframes"])
    except (OSError, KeyError, TypeError, ValueError) as exc:
        return Check("VGGT window", WARN, f"unreadable result: {exc}")
    ok = recommended >= segment_frames
    return Check(
        "VGGT window",
        PASS if ok else WARN,
        f"recommended_max_keyframes={recommended}, requested {segment_frames}",
    )


def check_rerun() -> Check:
    code, detail = _run(
        [
            "uv",
            "run",
            "--group",
            "viewer",
            "python",
            "-c",
            "import rerun; print(rerun.__version__)",
        ],
        180,
    )
    return Check("rerun viewer", PASS if code == 0 else WARN, detail or "available")


def check_flutter() -> Check:
    if shutil.which("flutter"):
        return Check("flutter", PASS, "on PATH")
    return Check("flutter", WARN, "not installed locally; CI is the app's only check")


def run_checks(
    *,
    stream_url: str | None,
    config_path: Path,
    segment_frames: int,
    vggt_window: Path | None,
    quick: bool,
) -> list[Check]:
    return [
        check_python(),
        check_git(),
        check_tests(not quick),
        check_ruff(not quick),
        check_modal(),
        check_env_file(),
        check_stream(stream_url),
        check_disk(),
        check_config(config_path, segment_frames),
        check_vggt_window(vggt_window, segment_frames),
        check_rerun(),
        check_flutter(),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stream-url", default=os.getenv("AEGIS_STREAM_URL"))
    parser.add_argument("--config-path", type=Path, default=Path("config/live.yaml"))
    parser.add_argument(
        "--segment-frames",
        type=int,
        default=None,
        help="frames per segment (default: value in demo/demo.conf, else 60)",
    )
    parser.add_argument(
        "--vggt-window-result",
        type=Path,
        default=Path("outputs/evaluation/vggt_window.json"),
        help="result written by demo/calibrate.py (default: outputs/evaluation/vggt_window.json)",
    )
    parser.add_argument("--quick", action="store_true", help="skip pytest and ruff")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = parser.parse_args(argv)

    segment_frames = args.segment_frames
    if segment_frames is None:
        segment_frames = 60
        conf = Path("demo/demo.conf")
        if conf.is_file():
            for line in conf.read_text(encoding="utf-8").splitlines():
                if line.startswith("SEGMENT_FRAMES="):
                    try:
                        segment_frames = int(line.split("=", 1)[1])
                    except ValueError:
                        pass

    checks = run_checks(
        stream_url=args.stream_url,
        config_path=args.config_path,
        segment_frames=segment_frames,
        vggt_window=args.vggt_window_result,
        quick=args.quick,
    )
    if args.json:
        print(json.dumps([item.as_dict() for item in checks], indent=2))
    else:
        print("=" * 78)
        print("  AEGIS LIVE DEMO — PREFLIGHT")
        print("=" * 78)
        for item in checks:
            print(f"  [{item.state.upper():<4}] {item.name:<16} {item.detail}")
        print("=" * 78)
        failures = [item.name for item in checks if item.state == FAIL]
        warnings = [item.name for item in checks if item.state == WARN]
        print("  GO" if not failures else f"  NO-GO: {', '.join(failures)}")
        if warnings:
            print(f"  Warnings: {', '.join(warnings)}")
        print(
            "  Budget reminder: L4 $0.000222/s; ~$2 total expected, $5 workspace cap."
        )
        print("=" * 78)
    return 1 if any(item.state == FAIL for item in checks) else 0


if __name__ == "__main__":
    sys.exit(main())
