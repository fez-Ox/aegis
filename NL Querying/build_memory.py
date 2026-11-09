#!/usr/bin/env python3
"""Build a memory dataset for NL querying from a video, via Modal.

Runs the existing Modal pipeline (``run_pipeline.py``) and then copies the
downloaded artifacts into ``NL Querying/outputs/<dataset_id>``, which is the
highest-priority root of the local memory transport. After this,
``smoke_test.py`` can answer questions from the freshly built scene graph.

Examples (from the repo root)::

    # GPU workspace (default)
    uv run python "NL Querying/build_memory.py"

    # Explicit video / dataset id / Modal profile
    uv run python "NL Querying/build_memory.py" \
        --video "NL Querying/sample_input_video.mp4" \
        --dataset-id nlq_sample --profile i230683

    # CPU-only Modal workspace (slower; no GPU payment method needed)
    AEGIS_GPU=cpu uv run python "NL Querying/build_memory.py"

    # Only sync artifacts that ``run_pipeline.py`` already downloaded
    uv run python "NL Querying/build_memory.py" --skip-run

Requires credentials the pipeline itself needs:

* Modal auth (``MODAL_PROFILE`` / ``~/.modal.toml``) and, for GPU functions,
  a payment method on the workspace.
* ``HF_TOKEN`` in the environment or ``.env`` for the gated VGGT-Ω weights
  (``facebook/VGGT-Omega``). The token is forwarded into the Modal secret by
  ``run_pipeline.py``.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

FOLDER_ROOT = Path(__file__).resolve().parent
REPO_ROOT = FOLDER_ROOT.parent
NLQ_OUTPUTS = FOLDER_ROOT / "outputs"
SCENE_GRAPH = Path("objects") / "r4d_scene_graph.json"


def default_video() -> Path:
    return FOLDER_ROOT / "sample_input_video.mp4"


def run_pipeline(args: argparse.Namespace) -> int:
    command = [
        sys.executable,
        "-m",
        "modal",
        "run",
        "run_pipeline.py",
        "--video",
        str(args.video.resolve()),
        "--dataset-id",
        args.dataset_id,
        "--stage",
        args.stage,
        "--config-path",
        args.config_path,
    ]
    if args.classes:
        command += ["--classes", args.classes]
    if args.sample_fps:
        command += ["--sample-fps", str(args.sample_fps)]
    if args.keyframe_stride:
        command += ["--keyframe-stride", str(args.keyframe_stride)]
    if args.vggt_model:
        command += ["--vggt-model", args.vggt_model]

    environment = dict(os.environ)
    if args.profile:
        environment["MODAL_PROFILE"] = args.profile
    if args.gpu:
        environment["AEGIS_GPU"] = args.gpu
    print("$ " + " ".join(command))
    return subprocess.run(
        command, cwd=REPO_ROOT, env=environment, check=False
    ).returncode


def sync_outputs(dataset_id: str) -> Path:
    """Copy ``outputs/<dataset>`` from the repo root into NL Querying."""
    source = REPO_ROOT / "outputs" / dataset_id
    destination = NLQ_OUTPUTS / dataset_id
    if not source.is_dir():
        raise FileNotFoundError(
            f"pipeline artifacts not found at {source}; "
            "run_pipeline.py downloads them on success"
        )
    shutil.copytree(source, destination, dirs_exist_ok=True)
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--video",
        type=Path,
        default=default_video(),
        help=f"Input video path (default: {default_video()})",
    )
    parser.add_argument(
        "--dataset-id",
        default="nlq_sample",
        help="Dataset id to create (default: nlq_sample).",
    )
    parser.add_argument(
        "--config-path", default="config/demo.yaml", help="Pipeline YAML config."
    )
    parser.add_argument(
        "--stage",
        default="all",
        choices=["all", "preprocess", "vggt", "detect", "rerun"],
        help="Pipeline stage (default: all).",
    )
    parser.add_argument("--classes", help="Comma-separated target classes.")
    parser.add_argument("--sample-fps", type=int, help="Override sample FPS.")
    parser.add_argument(
        "--keyframe-stride", type=int, help="Override VGGT keyframe stride."
    )
    parser.add_argument(
        "--vggt-model",
        help="Hugging Face repo id override for the VGGT-OMEGA checkpoint.",
    )
    parser.add_argument("--profile", help="Modal profile name (sets MODAL_PROFILE).")
    parser.add_argument(
        "--gpu",
        help="Accelerator policy: L4/T4/... or 'cpu' (sets AEGIS_GPU).",
    )
    parser.add_argument(
        "--skip-run",
        action="store_true",
        help="Skip the Modal run and only sync already-downloaded outputs.",
    )
    args = parser.parse_args(argv)

    if not args.skip_run:
        if not args.video.is_file():
            print(f"input video not found: {args.video}", file=sys.stderr)
            return 2
        returncode = run_pipeline(args)
        if returncode != 0:
            print(
                "\nPipeline failed. Common causes:\n"
                "  * no payment method on the Modal workspace (GPU functions)\n"
                "  * gated facebook/VGGT-Omega weights without HF_TOKEN\n"
                "  * AEGIS_GPU=cpu on a workspace without enough CPU memory",
                file=sys.stderr,
            )
            return returncode

    try:
        destination = sync_outputs(args.dataset_id)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    scene_graph = destination / SCENE_GRAPH
    if not scene_graph.is_file():
        print(
            f"warning: {scene_graph} is missing; the NLQ transport needs it.",
            file=sys.stderr,
        )
        return 1

    print(f"\nArtifacts staged at: {destination}")
    print("\nAsk questions from the new memory:")
    print(
        '  uv run python "NL Querying/smoke_test.py" '
        f'--dataset {args.dataset_id} --ask "where are my shoes"'
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
