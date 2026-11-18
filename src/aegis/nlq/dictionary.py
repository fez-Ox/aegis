"""Closed-vocabulary dictionary for the single Aegis NLQ engine.

Every item/room slot accepted by the engine must resolve to this dictionary.
The generated ``data/dictionary.json`` (525 canonical items / ~1,630 aliases /
20 rooms) is authoritative and merges on top of the legacy tables in
``aegis.memory.reasoning`` / ``aegis.core.vocabulary``.
"""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

FALLBACK_ITEM_SYNONYMS: dict[str, list[str]] = {
    "shoes": ["shoe", "shoes", "sneaker", "sneakers", "boots", "footwear", "slippers"],
    "bottle": ["bottle", "water bottle", "flask", "drink"],
    "keys": ["key", "keys", "keychain", "car key", "house key"],
    "glasses": ["glasses", "spectacles", "eyewear", "sunglasses"],
    "cell phone": ["phone", "cell phone", "mobile phone", "smartphone"],
    "laptop": ["laptop", "computer", "notebook"],
    "book": ["book", "books", "novel", "magazine"],
    "medicine": ["medicine", "medicines", "pills", "meds", "prescription"],
    "clothes": ["clothes", "clothing", "shirt", "pants", "laundry"],
}

FALLBACK_ROOM_KEYWORDS: dict[str, list[str]] = {
    "kitchen": ["kitchen"],
    "bedroom": ["bedroom", "bed room"],
    "living room": ["living room", "lounge"],
    "bathroom": ["bathroom", "washroom"],
    "dining room": ["dining room", "dining"],
    "hallway": ["hallway", "corridor", "hall"],
    "entryway": ["entryway", "foyer", "entrance hall"],
    "office": ["office", "study room"],
}

STOPWORDS: frozenset[str] = frozenset(
    {
        "where",
        "is",
        "are",
        "my",
        "me",
        "mine",
        "find",
        "show",
        "locate",
        "tell",
        "did",
        "do",
        "i",
        "the",
        "a",
        "an",
        "to",
        "at",
        "put",
        "leave",
        "left",
        "when",
        "what",
        "happened",
        "last",
        "see",
        "in",
        "it",
        "that",
        "there",
        "was",
        "were",
        "of",
        "for",
        "on",
        "about",
    }
)

DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_DICTIONARY_PATH = DATA_DIR / "dictionary.json"
DICTIONARY_SCHEMA_VERSION = 1


@dataclass
class Slots:
    """Result of parsing one user question against the closed vocabulary."""

    item: str | None = None
    room: str | None = None
    item_raw: str = ""


@dataclass
class DictionaryIndex:
    """Lookup tables used by :class:`aegis.nlq.engine.AnswerEngine`."""

    item_synonyms: dict[str, list[str]] = field(default_factory=dict)
    room_keywords: dict[str, list[str]] = field(default_factory=dict)

    @classmethod
    def seeded(cls) -> DictionaryIndex:
        items: dict[str, list[str]] = {}
        rooms: dict[str, list[str]] = {}
        try:
            from aegis.core.vocabulary import default_vocabulary

            for entry in default_vocabulary().entries():
                if entry.synonyms and entry.role in {"object", "anchor"}:
                    items[entry.id] = list(entry.synonyms)
            from aegis.memory.reasoning import QueryReasoningEngine

            rooms = {
                key: list(value)
                for key, value in QueryReasoningEngine.ROOM_KEYWORDS.items()
            }
        except (ImportError, FileNotFoundError):  # pragma: no cover - offline use
            items = {key: list(value) for key, value in FALLBACK_ITEM_SYNONYMS.items()}
            rooms = {key: list(value) for key, value in FALLBACK_ROOM_KEYWORDS.items()}
        index = cls(item_synonyms=items, room_keywords=rooms)
        if DEFAULT_DICTIONARY_PATH.is_file():
            index.merge(cls.load(DEFAULT_DICTIONARY_PATH), reassign=True)
        return index

    def add_item(
        self, canonical: str, synonyms: list[str], *, reassign: bool = False
    ) -> None:
        existing = self.item_synonyms.setdefault(canonical, [])
        for synonym in [canonical, *synonyms]:
            if reassign:
                to_demote: list[str] = []
                for other, other_synonyms in self.item_synonyms.items():
                    if other == canonical:
                        continue
                    while synonym in other_synonyms:
                        other_synonyms.remove(synonym)
                    if synonym == other and synonym != canonical:
                        to_demote.append(other)
                for key in to_demote:
                    del self.item_synonyms[key]
            if synonym not in existing:
                existing.append(synonym)

    def add_room(self, canonical: str, synonyms: list[str]) -> None:
        existing = self.room_keywords.setdefault(canonical, [])
        for synonym in [*synonyms, canonical]:
            if synonym not in existing:
                existing.append(synonym)

    def merge(
        self, other: DictionaryIndex, *, reassign: bool = False
    ) -> DictionaryIndex:
        for canonical, synonyms in other.item_synonyms.items():
            self.add_item(canonical, list(synonyms), reassign=reassign)
        for canonical, synonyms in other.room_keywords.items():
            self.add_room(canonical, list(synonyms))
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": DICTIONARY_SCHEMA_VERSION,
            "item_synonyms": self.item_synonyms,
            "room_keywords": self.room_keywords,
        }

    def save(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8"
        )
        return target

    @classmethod
    def load(cls, path: str | Path) -> DictionaryIndex:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        index = cls()
        for canonical, synonyms in data.get("item_synonyms", {}).items():
            index.add_item(canonical, list(synonyms))
        for canonical, synonyms in data.get("room_keywords", {}).items():
            index.add_room(canonical, list(synonyms))
        return index

    def canonical_of(self, label: str) -> str | None:
        """Resolve a stored scene label (e.g. 'Shoes #1') to a canonical item."""
        base = re.sub(r"\s*[#\[].*$", "", str(label)).strip().lower()
        if not base:
            return None
        for canonical, synonyms in self.item_synonyms.items():
            phrases = [canonical, *synonyms]
            if any(
                re.search(r"\b" + re.escape(p) + r"\b", base)
                for p in sorted(phrases, key=len, reverse=True)
            ):
                return canonical
        return None

    def _known_vocabulary(self) -> list[str]:
        vocab: list[str] = list(self.item_synonyms)
        for synonyms in self.item_synonyms.values():
            vocab.extend(synonyms)
        return sorted(set(vocab))

    def lookup_item(self, query: str) -> Slots:
        clean = " ".join(str(query).lower().split())
        clean = re.sub(r"[^\w\s]", " ", clean)
        for canonical, synonyms in self.room_keywords.items():
            for synonym in [canonical, *synonyms]:
                clean = re.sub(r"\b" + re.escape(synonym) + r"\b", " ", clean)
        clean = " ".join(clean.split())
        candidates = sorted(
            (
                (canon, syn)
                for canon, syns in self.item_synonyms.items()
                for syn in [canon, *syns]
            ),
            key=lambda pair: (len(pair[1]), pair[0] == pair[1]),
            reverse=True,
        )
        for canonical, synonym in candidates:
            if re.search(r"\b" + re.escape(synonym) + r"\b", clean):
                return Slots(item=canonical, room=self.lookup_room(query))
        tokens = [
            token for token in re.findall(r"\w+", clean) if token not in STOPWORDS
        ]
        return Slots(item=None, room=self.lookup_room(query), item_raw=" ".join(tokens))

    def lookup_room(self, query: str) -> str | None:
        clean = " ".join(str(query).lower().split())
        for canonical, synonyms in self.room_keywords.items():
            for synonym in [canonical, *synonyms]:
                if re.search(r"\b" + re.escape(synonym) + r"\b", clean):
                    return canonical
        return None

    def suggestions_for(self, unknown: str, limit: int = 3) -> list[str]:
        if not unknown:
            return []
        matches = difflib.get_close_matches(
            unknown, self._known_vocabulary(), n=limit, cutoff=0.55
        )
        canonicalised: list[str] = []
        for match in matches:
            for canonical, synonyms in self.item_synonyms.items():
                if match == canonical or match in synonyms:
                    canonicalised.append(canonical)
                    break
        return sorted(set(canonicalised))[:limit]
