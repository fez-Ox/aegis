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


def _retention(config_path: str | None):
    if config_path:
        return load_config(config_path).memory.retention
    from aegis.core.config import RetentionConfig

    return RetentionConfig()


def _matching(config_path: str | None):
    if config_path:
        return load_config(config_path).memory.matching
    from aegis.core.config import MatchingConfig

    return MatchingConfig()


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
    for name in ("ingest", "show", "size", "compact", "enroll"):
        command = sub.add_parser(name)
        command.add_argument("--home-id", default=None)
        command.add_argument("--store-root", default=None)
        command.add_argument("--config-path", default=None)
        if name == "ingest":
            command.add_argument("graph", type=Path, help="r4d_scene_graph.json (v2)")
        if name == "compact":
            command.add_argument("--now", default=None, help="ISO time (default: now)")
        if name == "enroll":
            command.add_argument("--instance", type=int, required=True)
            command.add_argument("--alias", help="What the patient calls this item")
            command.add_argument(
                "--class", dest="canonical_class", help="Vocabulary class"
            )
            command.add_argument("--usual-anchor")
            command.add_argument("--usual-room")
            command.add_argument("--visual-crop", help="Reference crop path or URL")
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
                retention=_retention(args.config_path),
                matching=_matching(args.config_path),
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
        elif args.command == "enroll":
            from aegis.memory.personal import enroll

            items = enroll(
                store,
                args.instance,
                alias=args.alias,
                canonical_class=args.canonical_class,
                usual_anchor=args.usual_anchor,
                usual_room=args.usual_room,
                visual_crop=args.visual_crop,
            )
            print(json.dumps({"personal_items": [item.as_dict() for item in items]}))
        elif args.command == "compact":
            from aegis.core.timeutil import parse_iso, utc_now
            from aegis.memory.compaction import compact, rollup

            moment = parse_iso(args.now) if args.now else utc_now()
            retention = _retention(args.config_path)
            result = compact(store, now=moment, config=retention)
            rolled = rollup(store, now=moment, config=retention)
            print(json.dumps({**result.__dict__, "rollups": rolled}, indent=2))
        else:
            print(
                json.dumps({"bytes": store.db_size_bytes(), **store.counts()}, indent=2)
            )
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
