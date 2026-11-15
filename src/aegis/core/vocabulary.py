"""Single source of truth for object labels, roles, prompts and query synonyms.

``config/vocabulary.yaml`` decides, for every label the detector can emit,
whether it is a personal object, an anchor (furniture), a room landmark or a
hand. Detector prompts, anchor/landmark sets, label normalisation and query
synonym matching are all generated from it.

Modal images ship only Python sources, so workers receive the vocabulary
inside the runtime configuration (``RuntimeConfig.vocabulary``) instead of
reading the YAML file.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

ROLES = ("object", "anchor", "landmark", "hand")
IMPORTANCE_LEVELS = ("normal", "high")
_ANCHOR_ONLY_FLAGS = ("container", "support_surface", "open_underneath")


def normalise_label(label: str) -> str:
    """Lower-case, replace ``_`` with a space, collapse whitespace and strip."""

    return " ".join(str(label).replace("_", " ").lower().split())


@dataclass(frozen=True, slots=True)
class VocabEntry:
    """One canonical label and everything the system knows about it."""

    id: str
    display: str
    prompts: tuple[str, ...]
    synonyms: tuple[str, ...] = ()
    role: str = "object"
    plural: bool = False
    importance: str = "normal"
    max_extent: float | None = None
    room_type: str | None = None
    container: bool = False
    support_surface: bool = False
    open_underneath: bool = False
    known: bool = True

    def as_mapping(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "display": self.display,
            "prompts": list(self.prompts),
            "synonyms": list(self.synonyms),
            "role": self.role,
            "plural": self.plural,
            "importance": self.importance,
            "max_extent": self.max_extent,
            "room_type": self.room_type,
            "container": self.container,
            "support_surface": self.support_surface,
            "open_underneath": self.open_underneath,
        }


def _entry_from_mapping(raw: Mapping[str, Any]) -> VocabEntry:
    if not isinstance(raw, Mapping):
        raise TypeError("vocabulary entries must be mappings")
    if "id" not in raw:
        raise ValueError("vocabulary entry is missing 'id'")
    entry_id = str(raw["id"])
    prompts = raw.get("prompts")
    if not isinstance(prompts, Sequence) or isinstance(prompts, (str, bytes)):
        raise TypeError(f"vocabulary entry {entry_id!r}: prompts must be a list")
    synonyms = raw.get("synonyms") or []
    if not isinstance(synonyms, Sequence) or isinstance(synonyms, (str, bytes)):
        raise TypeError(f"vocabulary entry {entry_id!r}: synonyms must be a list")
    max_extent = raw.get("max_extent")
    room_type = raw.get("room_type")
    return VocabEntry(
        id=entry_id,
        display=str(raw.get("display") or entry_id.title()),
        prompts=tuple(str(p) for p in prompts),
        synonyms=tuple(str(s) for s in synonyms),
        role=str(raw.get("role", "object")),
        plural=bool(raw.get("plural", False)),
        importance=str(raw.get("importance", "normal")),
        max_extent=None if max_extent is None else float(max_extent),
        room_type=None if room_type is None else str(room_type),
        container=bool(raw.get("container", False)),
        support_surface=bool(raw.get("support_surface", False)),
        open_underneath=bool(raw.get("open_underneath", False)),
    )


class Vocabulary:
    """Validated lookup tables built from vocabulary entries."""

    def __init__(self, entries: Sequence[VocabEntry]) -> None:
        if not entries:
            raise ValueError("vocabulary must contain at least one entry")
        self._entries: tuple[VocabEntry, ...] = tuple(entries)
        self._by_id: dict[str, VocabEntry] = {}
        self._by_prompt: dict[str, VocabEntry] = {}
        self._warned: set[str] = set()

        for entry in self._entries:
            name = entry.id
            if name != normalise_label(name) or not name:
                raise ValueError(f"vocabulary id {name!r} is not normalised")
            if name in self._by_id:
                raise ValueError(f"duplicate vocabulary id {name!r}")
            if entry.role not in ROLES:
                raise ValueError(
                    f"vocabulary entry {name!r}: unknown role {entry.role!r}"
                )
            if entry.importance not in IMPORTANCE_LEVELS:
                raise ValueError(
                    f"vocabulary entry {name!r}: unknown importance {entry.importance!r}"
                )
            if not entry.prompts:
                raise ValueError(
                    f"vocabulary entry {name!r}: prompts must not be empty"
                )
            if entry.max_extent is not None and entry.max_extent <= 0:
                raise ValueError(
                    f"vocabulary entry {name!r}: max_extent must be positive"
                )
            if entry.role != "anchor":
                for flag in _ANCHOR_ONLY_FLAGS:
                    if getattr(entry, flag):
                        raise ValueError(
                            f"vocabulary entry {name!r}: {flag} is only valid for anchors"
                        )
            for phrase in (*entry.prompts, *entry.synonyms):
                if phrase != normalise_label(phrase) or not phrase:
                    raise ValueError(
                        f"vocabulary entry {name!r}: phrase {phrase!r} is not normalised"
                    )
            self._by_id[name] = entry

        for entry in self._entries:
            for prompt in entry.prompts:
                owner = self._by_prompt.get(prompt)
                if owner is not None and owner.id != entry.id:
                    raise ValueError(
                        f"prompt {prompt!r} belongs to both {owner.id!r} and {entry.id!r}"
                    )
                other = self._by_id.get(prompt)
                if other is not None and other.id != entry.id:
                    raise ValueError(
                        f"prompt {prompt!r} of {entry.id!r} is the id of {other.id!r}"
                    )
                self._by_prompt[prompt] = entry

        for entry in self._entries:
            for synonym in entry.synonyms:
                owner = self._by_prompt.get(synonym) or self._by_id.get(synonym)
                if owner is not None and owner.id != entry.id:
                    raise ValueError(
                        f"synonym {synonym!r} of {entry.id!r} is a label of {owner.id!r}"
                    )

        # Query phrases: object entries only, longest phrase first.
        phrases: list[tuple[str, VocabEntry]] = []
        for entry in self._entries:
            if entry.role != "object":
                continue
            for phrase in dict.fromkeys((entry.id, *entry.prompts, *entry.synonyms)):
                phrases.append((phrase, entry))
        phrases.sort(key=lambda item: (-len(item[0]), item[0]))
        self._query_phrases = [
            (re.compile(r"\b" + re.escape(phrase) + r"\b"), phrase, entry)
            for phrase, entry in phrases
        ]

    # ------------------------------------------------------------ building
    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> Vocabulary:
        if not isinstance(raw, Mapping):
            raise TypeError("vocabulary must be a mapping")
        entries_raw = raw.get("entries")
        if not isinstance(entries_raw, Sequence) or isinstance(
            entries_raw, (str, bytes)
        ):
            raise TypeError("vocabulary.entries must be a list")
        return cls([_entry_from_mapping(item) for item in entries_raw])

    @classmethod
    def load(cls, path: str | Path) -> Vocabulary:
        with Path(path).open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}
        return cls.from_mapping(raw)

    def to_mapping(self) -> dict[str, Any]:
        return {
            "version": 1,
            "entries": [entry.as_mapping() for entry in self._entries],
        }

    # ------------------------------------------------------------- lookups
    def entries(self) -> tuple[VocabEntry, ...]:
        return self._entries

    def entry(self, label: str) -> VocabEntry:
        """Return the entry for a raw label; unknown labels become objects."""

        normalised = normalise_label(label)
        found = self._by_id.get(normalised) or self._by_prompt.get(normalised)
        if found is not None:
            return found
        if normalised not in self._warned:
            self._warned.add(normalised)
            logger.warning(
                "label %r is not in the vocabulary; treated as an object", label
            )
        return VocabEntry(
            id=normalised,
            display=normalised.title(),
            prompts=(normalised,),
            role="object",
            known=False,
        )

    def canonical(self, label: str) -> str:
        return self.entry(label).id

    def role(self, label: str) -> str:
        return self.entry(label).role

    def display(self, label: str) -> str:
        return self.entry(label).display

    def room_type(self, label: str) -> str | None:
        return self.entry(label).room_type

    def detector_prompts(self) -> tuple[str, ...]:
        prompts: list[str] = []
        for entry in self._entries:
            prompts.extend(entry.prompts)
        return tuple(dict.fromkeys(prompts))

    def resolve_query(self, text: str) -> VocabEntry | None:
        """Return the object entry named in ``text`` (longest phrase wins)."""

        normalised = normalise_label(text)
        if not normalised:
            return None
        variants = [normalised]
        words = normalised.split()
        stripped = " ".join(
            word[:-1]
            if len(word) > 3 and word.endswith("s") and not word.endswith("ss")
            else word
            for word in words
        )
        plural = " ".join(word if word.endswith("s") else word + "s" for word in words)
        for variant in (stripped, plural):
            if variant not in variants:
                variants.append(variant)

        # Phrases are sorted longest first, so the first hit is the longest.
        for pattern, _phrase, entry in self._query_phrases:
            if any(pattern.search(variant) for variant in variants):
                return entry
        return None


def default_vocabulary_path() -> Path:
    override = os.environ.get("AEGIS_VOCABULARY_FILE")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[3] / "config" / "vocabulary.yaml"


@lru_cache(maxsize=1)
def default_vocabulary() -> Vocabulary:
    """Load the repository vocabulary file (local runs and tests only)."""

    path = default_vocabulary_path()
    if not path.is_file():
        raise FileNotFoundError(
            f"vocabulary file not found at {path}; remote workers must receive the "
            "vocabulary inside the runtime config (RuntimeConfig.vocabulary)"
        )
    return Vocabulary.load(path)
