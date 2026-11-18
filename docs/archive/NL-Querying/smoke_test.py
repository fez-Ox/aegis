#!/usr/bin/env python3
"""Smoke-test / CLI for NL Querying communication with the Aegis memory.

Runable from the repo root with the project's uv environment::

    # Offline against sample_outputs / fixtures (no Modal needed)
    uv run python "NL Querying/smoke_test.py" --dataset demo04

    # Same, plus one engine question end-to-end
    uv run python "NL Querying/smoke_test.py" --dataset Demo06-Self \
        --ask "where is my water bottle"

    # Against the deployed Modal endpoint (see comm/modal_serve.py)
    export AEGIS_COMM_TRANSPORT=modal
    export AEGIS_MODAL_BASE_URL=https://<workspace>--aegis-memory-api-serve-memory-api.modal.run
    uv run python "NL Querying/smoke_test.py" --transport modal

Exit code is 0 when every executed check passes; 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Folder name contains a space, so it is not importable as a package:
# bootstrap our own package root onto sys.path.
FOLDER_ROOT = Path(__file__).resolve().parent
if str(FOLDER_ROOT) not in sys.path:
    sys.path.insert(0, str(FOLDER_ROOT))

from comm.client import AegisCommClient
from comm.transports import TransportError, create_source
from nlq.engine import HybridNLQEngine


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--transport",
        choices=["auto", "local", "modal"],
        default="auto",
        help="Communication channel override (default: env/auto).",
    )
    parser.add_argument("--base-url", help="Modal endpoint base URL override.")
    parser.add_argument(
        "--dataset",
        default=None,
        help="Dataset id to inspect (default: first available).",
    )
    parser.add_argument(
        "--ask",
        default=None,
        help="Optional natural-language question answered by the NLQ engine.",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable the LLM escape hatch (dictionary-only answering).",
    )
    args = parser.parse_args(argv)

    checks: dict[str, object] = {}
    try:
        source = create_source(transport=args.transport, base_url=args.base_url)
        client = AegisCommClient(source=source)

        health = client.health()
        checks["health"] = health

        datasets = client.list_datasets()
        checks["available_datasets"] = datasets

        dataset = args.dataset or (datasets[0] if datasets else None)
        if dataset is None:
            print("FAIL: no datasets discoverable at the active transport.")
            return 1
        checks["dataset"] = client.scene_summary(dataset)

        engine = HybridNLQEngine(client=client, llm=None if args.no_llm else "auto")
        checks["llm"] = engine.llm_status()
        print(json.dumps(checks, indent=2))

        if args.ask:
            result = engine.ask(args.ask, dataset)
            print("\nNLQ answer:")
            print(json.dumps(result.to_dict(), indent=2))
            print(f"\n>>> {result.answer_text}")
        return 0
    except TransportError as exc:
        print(f"communication failure: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
