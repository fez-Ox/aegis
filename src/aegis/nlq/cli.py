"""``aegis-ask`` — the single terminal entry point for asking Aegis memory."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

from .dictionary import DictionaryIndex
from .engine import AnswerEngine, memory_view_from_graph

REPO_ROOT = Path(__file__).resolve().parents[3]
LOCAL_ROOTS = (
    REPO_ROOT / "outputs",
    REPO_ROOT / "sample_outputs",
    REPO_ROOT / "tests" / "fixtures",
)


def load_graph(dataset_id: str) -> dict[str, Any]:
    for root in LOCAL_ROOTS:
        path = root / dataset_id / "objects" / "r4d_scene_graph.json"
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    raise FileNotFoundError(
        f"No scene graph for {dataset_id!r} in: "
        + ", ".join(str(root) for root in LOCAL_ROOTS)
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aegis-ask", description="Ask Aegis memory a question"
    )
    parser.add_argument(
        "question", nargs="+", help="the question, e.g. 'where are my keys'"
    )
    parser.add_argument("--dataset-id", default=os.getenv("AEGIS_DATASET_ID", "demo01"))
    parser.add_argument(
        "--transport",
        choices=("local", "http"),
        default=os.getenv("AEGIS_COMM_TRANSPORT")
        or ("http" if os.getenv("AEGIS_MODAL_BASE_URL") else "local"),
        help="local reads a downloaded graph; http asks the Modal API",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("AEGIS_MODAL_BASE_URL", "http://127.0.0.1:8000"),
        help="base URL of the Aegis API (Modal HTTPS URL in production)",
    )
    args = parser.parse_args(argv)
    question = " ".join(args.question)

    if args.transport == "local":
        try:
            graph = load_graph(args.dataset_id)
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            print(f"No local memory for {args.dataset_id!r}: {exc}", file=sys.stderr)
            return 2
        result = AnswerEngine(DictionaryIndex.seeded()).ask(
            question, memory_view_from_graph(graph, args.dataset_id)
        )
        payload = result.to_dict()
    else:
        try:
            response = httpx.get(
                f"{args.base_url.rstrip('/')}/api/v1/ask",
                params={"text": question, "dataset_id": args.dataset_id},
                timeout=15.0,
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            print(f"Can't reach Aegis memory: {exc}", file=sys.stderr)
            return 2

    print(payload.get("answer", ""))
    if payload.get("abstained"):
        reason = payload.get("abstain_reason")
        print(f"[abstained: {reason}]" if reason else "[abstained]")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
