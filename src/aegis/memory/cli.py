"""``aegis-memory``: ingest session graphs into a home store and inspect it."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from aegis.core.config import load_config
from aegis.memory.ingest import ingest_session
from aegis.memory.store import open_store


def _vocabulary(config_path: str | None):
    if config_path:
        return load_config(config_path).vocab()
    from aegis.core.vocabulary import default_vocabulary

    return default_vocabulary()


def _home(args) -> str:
    if args.home_id:
        return args.home_id
    if args.config_path:
        return load_config(args.config_path).memory.home_id
    return "home01"


def _store_root(args) -> str | None:
    if args.store_root:
        return args.store_root
    if args.config_path:
        return load_config(args.config_path).memory.store_root
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aegis-memory", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("ingest", "show", "size"):
        command = sub.add_parser(name)
        command.add_argument("--home-id", default=None)
        command.add_argument("--store-root", default=None)
        command.add_argument("--config-path", default=None)
        if name == "ingest":
            command.add_argument("graph", type=Path, help="r4d_scene_graph.json (v2)")
    args = parser.parse_args(argv)

    store = open_store(_home(args), _store_root(args))
    try:
        if args.command == "ingest":
            graph = json.loads(args.graph.read_text(encoding="utf-8"))
            report = ingest_session(
                store,
                graph,
                vocabulary=_vocabulary(args.config_path),
                evidence_root=args.graph.parent,
            )
            print(json.dumps(report.as_dict(), indent=2))
        elif args.command == "show":
            for room in store.rooms():
                print(
                    f"room {room['room_id']}: {room['label']} ({room['label_source']})"
                )
            for anchor in store.anchors():
                print(
                    f"anchor {anchor['anchor_id']}: {anchor['label']} "
                    f"room={anchor['room_id']} match={anchor['match_quality']}"
                )
            for state in store.latest_states():
                print(
                    f"{state['label']}: {state['relation']} "
                    f"{state['anchor_label'] or '-'} in {state['room_label'] or '-'} "
                    f"at {state['last_seen_wallclock']}"
                )
        else:
            print(
                json.dumps({"bytes": store.db_size_bytes(), **store.counts()}, indent=2)
            )
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
