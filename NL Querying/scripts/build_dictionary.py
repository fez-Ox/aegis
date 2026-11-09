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

HOME_VOCABULARY_PATH = FOLDER_ROOT / "nlq" / "home_vocabulary.json"

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


def load_home_vocabulary() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Load the curated closed home vocabulary.

    Categories are organisational only; the same canonical item may appear
    in more than one room (for example ``towel`` in the bathroom and the
    bedroom), and its synonyms are merged. The curated entries are applied
    last with reassignment, so they own their aliases instead of inheriting
    legacy collisions (``cup`` no longer resolves to ``bottle``).
    """
    if not HOME_VOCABULARY_PATH.is_file():
        return {}, {}
    data = json.loads(HOME_VOCABULARY_PATH.read_text(encoding="utf-8"))
    items: dict[str, list[str]] = {}
    categories = data.get("categories") or {}
    if isinstance(categories, dict):
        for entries in categories.values():
            if not isinstance(entries, dict):
                continue
            for canonical, synonyms in entries.items():
                canon = str(canonical).strip().lower()
                if not canon:
                    continue
                bucket = items.setdefault(canon, [])
                if not isinstance(synonyms, list):
                    continue
                for synonym in synonyms:
                    clean = str(synonym).strip().lower()
                    if clean and clean not in bucket:
                        bucket.append(clean)

    rooms: dict[str, list[str]] = {}
    raw_rooms = data.get("rooms") or {}
    if isinstance(raw_rooms, dict):
        for canonical, synonyms in raw_rooms.items():
            canon = str(canonical).strip().lower()
            if not canon:
                continue
            bucket = rooms.setdefault(canon, [])
            if not isinstance(synonyms, list):
                continue
            for synonym in synonyms:
                clean = str(synonym).strip().lower()
                if clean and clean not in bucket:
                    bucket.append(clean)
    return items, rooms


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

    # Curated closed vocabulary last: it is authoritative over legacy aliases
    # such as ``cup`` -> ``bottle`` or ``pan`` -> ``cooking pot``.
    home_items, home_rooms = load_home_vocabulary()
    for canonical, synonyms in home_items.items():
        index.add_item(canonical, synonyms, reassign=True)
        counts["home_vocabulary"] += 1
    for canonical, synonyms in home_rooms.items():
        index.add_room(canonical, synonyms)
        counts["home_rooms"] += 1

    # Give every canonical entry its safe plural form as well, but never
    # steal a variant that is already a canonical item or another item's
    # alias (``glasses`` must not become a plural of ``drinking glass``).
    for canonical in list(index.item_synonyms):
        variants: list[str] = []
        if canonical.endswith("s") and canonical not in IRREGULAR_PLURALS:
            singular = canonical[:-1]
            if singular and singular not in index.item_synonyms:
                variants.append(singular)
        variants.extend(plural_variants(canonical))
        for variant in variants:
            owner = find_canonical(index, variant)
            if owner is not None and owner != canonical:
                continue
            index.add_item(canonical, [variant])
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
