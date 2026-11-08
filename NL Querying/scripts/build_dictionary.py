#!/usr/bin/env python3
"""Generate ``nlq/dictionary.json`` from every vocabulary source in the repo.

Sources merged (all optional, missing ones are skipped):

1. ``aegis.memory.reasoning.QueryReasoningEngine`` synonym/room tables - the
   same tables the deployed ``/api/v1/query`` endpoint uses.
2. ``run_pipeline.COMPREHENSIVE_INDOOR_CLASSES`` (read via ``ast`` so importing
   Modal is never required).
3. ``config/demo.yaml`` ``perception.target_classes``.
4. Object/anchor labels actually present in scene graphs under
   ``NL Querying/outputs``, ``sample_outputs``, ``outputs`` and
   ``tests/fixtures`` - so the dictionary covers what the pipeline sees.

Run from the repo root::

    uv run python "NL Querying/scripts/build_dictionary.py"
    uv run python "NL Querying/scripts/build_dictionary.py" --dry-run

The generated file is merged *on top of* the live aegis tables at engine
start-up, so it only ever adds vocabulary; it never removes a synonym.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

FOLDER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = FOLDER_ROOT.parent
if str(FOLDER_ROOT) not in sys.path:
    sys.path.insert(0, str(FOLDER_ROOT))
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from nlq.dictionary import (
    DEFAULT_DICTIONARY_PATH,
    DICTIONARY_SCHEMA_VERSION,
    FALLBACK_ITEM_SYNONYMS,
    FALLBACK_ROOM_KEYWORDS,
    DictionaryIndex,
)

GRAPH_ROOTS: tuple[Path, ...] = (
    FOLDER_ROOT / "outputs",
    REPO_ROOT / "sample_outputs",
    REPO_ROOT / "outputs",
    REPO_ROOT / "tests" / "fixtures",
)

# Labels that describe the camera wearer or a body part, not a household item.
SKIP_LABELS: frozenset[str] = frozenset(
    {"hand", "human hand", "camera wearer", "person", "user"}
)

# Plurals that must not be singularised by naive trailing-s removal.
IRREGULAR_PLURALS: frozenset[str] = frozenset(
    {"glasses", "clothes", "keys", "pants", "shorts", "scissors", "stairs"}
)


def load_aegis_tables() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Synonyms/rooms from the deployed reasoning engine, with fallback."""
    try:
        from aegis.memory.reasoning import QueryReasoningEngine

        items = {k: list(v) for k, v in QueryReasoningEngine.ITEM_SYNONYMS.items()}
        rooms = {k: list(v) for k, v in QueryReasoningEngine.ROOM_KEYWORDS.items()}
        return items, rooms
    except ImportError:  # pragma: no cover - sandbox without aegis on path
        items = {k: list(v) for k, v in FALLBACK_ITEM_SYNONYMS.items()}
        rooms = {k: list(v) for k, v in FALLBACK_ROOM_KEYWORDS.items()}
        return items, rooms


def load_pipeline_classes() -> list[str]:
    """Read ``COMPREHENSIVE_INDOOR_CLASSES`` without importing Modal."""
    source = (REPO_ROOT / "run_pipeline.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if (
                isinstance(target, ast.Name)
                and target.id == "COMPREHENSIVE_INDOOR_CLASSES"
            ):
                value = ast.literal_eval(node.value)
                return [str(entry) for entry in value]
    return []


def load_config_classes() -> list[str]:
    """``perception.target_classes`` from config/demo.yaml."""
    config_path = REPO_ROOT / "config" / "demo.yaml"
    if not config_path.is_file():
        return []
    import yaml

    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    classes = (config.get("perception") or {}).get("target_classes") or []
    return [str(entry) for entry in classes]


def normalise_label(raw: str) -> str | None:
    """``Garbage Bag #1 [Left]`` -> ``garbage bag``; drop room noise."""
    text = str(raw).lower()
    text = text.split("#")[0]
    text = re.sub(r"\[[^\]]*\]", " ", text)
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    text = " ".join(text.replace("-", " ").split())
    if not text or text in SKIP_LABELS:
        return None
    if re.fullmatch(r"room\s*\d*", text):
        return None
    return text


def collect_graph_terms() -> Counter[str]:
    """Object and anchor labels seen in real scene-graph artifacts."""
    terms: Counter[str] = Counter()
    seen_files: set[Path] = set()
    for root in GRAPH_ROOTS:
        if not root.is_dir():
            continue
        candidates = list(root.glob("*/objects/r4d_scene_graph.json"))
        candidates += list(root.glob("*/r4d_scene_graph.json"))
        for path in candidates:
            if path in seen_files:
                continue
            seen_files.add(path)
            try:
                graph = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            for section in ("anchors", "events", "timeline"):
                for entry in _iter_entries(graph.get(section)):
                    for key in (
                        "label",
                        "anchor_label",
                        "object",
                        "source_anchor",
                        "destination_anchor",
                    ):
                        label = normalise_label(entry.get(key) or "")
                        if label:
                            terms[label] += 1
    return terms


def _iter_entries(section: Any) -> list[dict[str, Any]]:
    if isinstance(section, list):
        return [entry for entry in section if isinstance(entry, dict)]
    if isinstance(section, dict):
        entries: list[dict[str, Any]] = []
        for value in section.values():
            if isinstance(value, list):
                entries.extend(entry for entry in value if isinstance(entry, dict))
        return entries
    return []


def plural_variants(phrase: str) -> list[str]:
    """Safe plural forms (never naive singularisation of -ss words)."""
    if not phrase or phrase.endswith("s"):
        return []
    if phrase.endswith("y") and len(phrase) > 1:
        return [phrase[:-1] + "ies"]
    return [phrase + "s"]


def find_canonical(index: DictionaryIndex, phrase: str) -> str | None:
    if phrase in index.item_synonyms:
        return phrase
    for canonical, synonyms in index.item_synonyms.items():
        if phrase in synonyms:
            return canonical
    return None


def add_phrase(index: DictionaryIndex, phrase: str) -> str:
    """Add one phrase, reusing an existing canonical entry when possible."""
    canonical = find_canonical(index, phrase)
    if canonical is not None:
        index.add_item(canonical, [phrase])
        return canonical
    index.add_item(phrase, plural_variants(phrase))
    return phrase


def build_index() -> tuple[DictionaryIndex, dict[str, int]]:
    items, rooms = load_aegis_tables()
    index = DictionaryIndex(item_synonyms=items, room_keywords=rooms)
    counts: Counter[str] = Counter()

    for phrase in load_pipeline_classes():
        phrase = normalise_label(phrase) or ""
        if phrase:
            add_phrase(index, phrase)
            counts["pipeline_classes"] += 1

    for phrase in load_config_classes():
        phrase = normalise_label(phrase) or ""
        if phrase:
            add_phrase(index, phrase)
            counts["config_classes"] += 1

    for phrase in collect_graph_terms():
        add_phrase(index, phrase)
        counts["scene_graph_labels"] += 1

    # Give every canonical entry its safe plural form as well.
    for canonical in list(index.item_synonyms):
        if canonical.endswith("s") and canonical not in IRREGULAR_PLURALS:
            singular = canonical[:-1]
            if singular and singular not in index.item_synonyms:
                index.add_item(canonical, [singular])
        index.add_item(canonical, plural_variants(canonical))
    return index, dict(counts)


def write_index(index: DictionaryIndex, path: Path, counts: dict[str, int]) -> Path:
    payload: dict[str, Any] = index.to_dict()
    payload["generated_at"] = datetime.now(UTC).isoformat()
    payload["sources"] = counts
    payload["schema"] = DICTIONARY_SCHEMA_VERSION
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_DICTIONARY_PATH,
        help=f"Output JSON path (default: {DEFAULT_DICTIONARY_PATH})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print statistics without writing the dictionary file.",
    )
    args = parser.parse_args(argv)

    index, counts = build_index()
    synonym_count = sum(len(value) for value in index.item_synonyms.values())
    print(f"canonical items : {len(index.item_synonyms)}")
    print(f"synonyms        : {synonym_count}")
    print(f"room keywords   : {len(index.room_keywords)}")
    print(f"sources         : {counts or {'aegis_reasoning_tables': 1}}")
    for sample in ("shoes", "keys", "bottle", "garbage bag", "storage cabinet"):
        if sample in index.item_synonyms:
            print(f"  {sample}: {', '.join(index.item_synonyms[sample])}")

    if args.dry_run:
        print("dry run: dictionary not written")
        return 0
    target = write_index(index, args.out, counts)
    print(f"wrote {target} ({target.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
