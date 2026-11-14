"""Provenance header written at the top of every evaluation result file."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=False
    ).stdout.strip()


def run_header(
    *,
    config_path: str | None,
    laptop: str,
    phone: str,
    gpu: str = "",
    operator: str = "",
) -> dict[str, Any]:
    """Commit, config hash, model ids and hardware for one measurement."""

    if not laptop or not phone:
        raise SystemExit("--laptop and --phone are required for recorded evidence")
    model_ids: dict[str, str] = {}
    config_sha = None
    if config_path:
        from aegis.core.config import load_config

        config = load_config(config_path)
        config_sha = hashlib.sha256(Path(config_path).read_bytes()).hexdigest()
        model_ids = {
            "vggt": config.vggt.model_id,
            "detector": config.perception.detector_model,
            "sam2": config.sam2.model_id,
        }
    return {
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain", "--untracked-files=no")),
        "config_path": config_path,
        "config_sha256": config_sha,
        "model_ids": model_ids,
        "hardware": {"laptop": laptop, "phone": phone, "gpu": gpu},
        "recorded_at": datetime.now(UTC).isoformat(),
        "operator": operator,
    }


def write_result(path: Path, header: dict[str, Any], result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"header": header, "result": result}, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    if header.get("git_dirty"):
        print(
            "WARNING: working tree has uncommitted changes; this result is not valid evidence"
        )
    print(f"wrote {path}")


def add_common_arguments(parser: Any) -> None:
    parser.add_argument("--laptop", required=True, help="Laptop model / CPU")
    parser.add_argument(
        "--phone", required=True, help="Phone model and Android version"
    )
    parser.add_argument(
        "--gpu", default="", help="GPU used (Modal L4 for pipeline runs)"
    )
    parser.add_argument("--operator", default="")
    parser.add_argument("--config-path", default=None)
    parser.add_argument("--out", type=Path, default=None)
