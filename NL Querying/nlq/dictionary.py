"""Closed-vocabulary dictionary for the hybrid NLQ system (Path C design).

Decision (2026-11): the dominant path is **hybrid with a very large
dictionary** - NOT an open-vocabulary parser. Every slot the engine accepts
must resolve to a dictionary entry; unknown vocabularies go through an
explicit clarification/abstention or the (still absent) LLM fallback instead
of being guessed at.

This file is the skeleton of that dictionary:

* seeds itself from the battle-tested synonym tables in
  ``aegis.memory.reasoning.QueryReasoningEngine`` (same source of truth as
  the deployed ``/api/v1/query`` endpoint), with a small embedded fallback;
* grows via ``add_item`` / JSON ``(de)serialization`` so the table can be
  extended towards "very large" without code changes in the engine.

Anything marked TODO(NLQ) is intentionally left for the filling-in phase
(see AGENT-DOC_ToDos.md M3 and AGENT-DOC_context.md section 7).
"""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Seed vocabulary (fallback copy; replaced by the aegis tables when importable)
# ---------------------------------------------------------------------------
FALLBACK_ITEM_SYNONYMS: dict[str, list[str]] = {
    "shoes": ["shoe", "shoes", "sneaker", "sneakers", "boots", "footwear", "slippers"],
    "bottle": ["bottle", "water bottle", "flask", "cup", "drink"],
    "keys": ["key", "keys", "keychain", "car key", "house key"],
    "glasses": ["glasses", "spectacles", "eyewear", "sunglasses"],
    "cooking pot": ["cooking pot", "pot", "pots", "pan", "pans", "saucepan"],
    "bowl": ["bowl", "bowls", "dish", "dishes", "basin"],
    "phone": ["phone", "cell phone", "mobile phone", "smartphone"],
    "laptop": ["laptop", "computer", "notebook"],
    "book": ["book", "books", "novel", "magazine"],
    "medicine": ["medicine", "medicines", "pills", "meds", "prescription"],
    "backpack": ["backpack", "bag", "handbag", "purse"],
    "clothes": ["clothes", "clothing", "shirt", "pants", "laundry"],
    "trash": ["trash", "garbage", "rubbish", "waste", "bin"],
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

# Words that describe *where to look* / question scaffolding, never the
# target item itself.
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
    }
)

# Generated vocabulary lives next to this module so every entry point
# (smoke test, tests, future API) picks it up without configuration.
DEFAULT_DICTIONARY_PATH = Path(__file__).with_name("dictionary.json")
DICTIONARY_SCHEMA_VERSION = 1


@dataclass
class Slots:
    """Result of a dictionary parse of one user query."""

    item: str | None = None  # canonical dictionary item, e.g. "shoes"
    room: str | None = None  # canonical room, e.g. "kitchen"
    item_raw: str = ""  # unknown leftover noun phrase (for gate)


@dataclass
class DictionaryIndex:
    """The closed-vocabulary lookup tables used by the hybrid engine."""

    item_synonyms: dict[str, list[str]] = field(default_factory=dict)
    room_keywords: dict[str, list[str]] = field(default_factory=dict)

    # -- construction -----------------------------------------------------
    @classmethod
    def seeded(cls) -> DictionaryIndex:
        """Build from the deployed aegis tables plus the generated file.

        The generated ``dictionary.json`` (scripts/build_dictionary.py) is
        merged on top of the live aegis tables, so freshly added synonym
        tables and generated vocabularies both take part in lookup.
        """
        try:
            from aegis.memory.reasoning import QueryReasoningEngine

            items = {
                key: list(value)
                for key, value in QueryReasoningEngine.ITEM_SYNONYMS.items()
            }
            rooms = {
                key: list(value)
                for key, value in QueryReasoningEngine.ROOM_KEYWORDS.items()
            }
        except ImportError:  # pragma: no cover - offline skeleton use
            items = {k: list(v) for k, v in FALLBACK_ITEM_SYNONYMS.items()}
            rooms = {k: list(v) for k, v in FALLBACK_ROOM_KEYWORDS.items()}
        index = cls(item_synonyms=items, room_keywords=rooms)
        if DEFAULT_DICTIONARY_PATH.is_file():
            # The generated file is authoritative: it is the curated closed
            # vocabulary, and may deliberately reassign a legacy alias (for
            # example, ``cup`` moves from ``bottle`` to ``cup``).
            index.merge(cls.load(DEFAULT_DICTIONARY_PATH), reassign=True)
        return index

    # -- growth -----------------------------------------------------------
    def add_item(
        self, canonical: str, synonyms: list[str], *, reassign: bool = False
    ) -> None:
        """Add or extend one item entry (the dictionary growth hook).

        With ``reassign=True`` the new entry becomes the owner of each
        synonym: the alias is removed from any other canonical entry. This
        lets the curated home vocabulary repair legacy aliases without
        deleting the legacy tables. A canonical's own name is never removed
        from itself; exact canonical names also win in ``lookup_item``.
        """
        existing = self.item_synonyms.setdefault(canonical, [])
        for synonym in [canonical, *synonyms]:
            if reassign:
                for other, other_synonyms in self.item_synonyms.items():
                    if other == canonical or synonym == other:
                        continue
                    while synonym in other_synonyms:
                        other_synonyms.remove(synonym)
            if synonym not in existing:
                existing.append(synonym)

    def add_room(self, canonical: str, synonyms: list[str]) -> None:
        existing = self.room_keywords.setdefault(canonical, [])
        for synonym in synonyms + [canonical]:
            if synonym not in existing:
                existing.append(synonym)

    def merge(
        self, other: DictionaryIndex, *, reassign: bool = False
    ) -> DictionaryIndex:
        """Union another index into this one (in place) and return self."""
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
        """Load a JSON dictionary; tolerates the older two-key schema."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        index = cls()
        for canonical, synonyms in data.get("item_synonyms", {}).items():
            index.add_item(canonical, list(synonyms))
        for canonical, synonyms in data.get("room_keywords", {}).items():
            index.add_room(canonical, list(synonyms))
        return index

    # -- queries ----------------------------------------------------------
    def _known_vocabulary(self) -> list[str]:
        vocab: list[str] = list(self.item_synonyms)
        for synonyms in self.item_synonyms.values():
            vocab.extend(synonyms)
        return sorted(set(vocab))

    def lookup_item(self, query: str) -> Slots:
        """Parse the item slot from natural language, dictionary-gated.

        Room words are stripped first (they describe where to look), then
        long synonyms are preferred over short ones ("water bottle" wins
        over "bottle").
        """
        clean = " ".join(str(query).lower().split())
        clean = re.sub(r"[^\w\s]", " ", clean)

        # Strip room mentions first.
        for canonical, synonyms in self.room_keywords.items():
            for synonym in [canonical, *synonyms]:
                clean = re.sub(r"\b" + re.escape(synonym) + r"\b", " ", clean)
        clean = " ".join(clean.split())

        # Longest phrase synonyms first; at equal length an exact canonical
        # name wins over another entry's alias.
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

        # Unknown noun phrase -> keep raw tokens for gate/clarification.
        tokens = [
            token for token in re.findall(r"\w+", clean) if token not in STOPWORDS
        ]
        return Slots(item=None, room=self.lookup_room(query), item_raw=" ".join(tokens))

    def lookup_room(self, query: str) -> str | None:
        """Canonical room constraint or None ("keys in the kitchen")."""
        clean = " ".join(str(query).lower().split())
        for canonical, synonyms in self.room_keywords.items():
            for synonym in [canonical, *synonyms]:
                if re.search(r"\b" + re.escape(synonym) + r"\b", clean):
                    return canonical
        return None

    def suggestions_for(self, unknown: str, limit: int = 3) -> list[str]:
        """Closest known dictionary entries for an unknown phrase."""
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
        # When nothing is close, return empty: the engine falls back to an
        # honest clarification ("I don't know this word") instead of
        # parroting the user's phrase back as a pseudo-suggestion.
        return sorted(set(canonicalised))[:limit]
