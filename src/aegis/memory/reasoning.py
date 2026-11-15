"""Query parsing and answer wording for the memory API.

Answers are at most two short sentences and never claim more than the
memory holds: an object out of view is "last seen" somewhere, and an
uncertain relation says so. Item names, synonyms and plural grammar come
from the vocabulary (:mod:`aegis.core.vocabulary`).
"""

from __future__ import annotations

import re
from typing import Any, ClassVar

from aegis.core.vocabulary import Vocabulary, default_vocabulary

UNCERTAIN_SENTENCE = "I'm not fully sure about the exact spot."

# Relation -> phrase placed before an anchor name ("on Desk #1").
RELATION_PHRASES: dict[str, str] = {
    "inside": "inside",
    "on_surface": "on",
    "on_top": "on",
    "under": "under",
    "above": "above",
    "next_to": "next to",
    "on_floor": "on the floor beside",
    "near": "near",
    "moving_towards": "near",
}


def room_phrase(room: str | None) -> str:
    """Grammar-aware room clause for natural explanations ("in the Kitchen")."""

    if not room:
        return ""
    if room.lower().startswith("room "):
        return f" in {room}"
    return f" in the {room}"


def _insert_room_clause(explanation: str, anchor: str, room: str | None) -> str:
    """Attach the room clause to the sentence that names the anchor.

    The room belongs with the location ("...inside Storage Cabinet #1 in the
    Entryway."), and is skipped when the anchor already names the room.
    """

    clause = room_phrase(room)
    if not clause or not anchor or room is None:
        return explanation
    if room.lower() in str(anchor).lower():
        return explanation

    anchor_pos = explanation.find(str(anchor))
    if anchor_pos >= 0:
        period_pos = explanation.find(".", anchor_pos)
        if period_pos >= 0:
            return explanation[:period_pos] + clause + explanation[period_pos:]
    stripped = explanation.rstrip(".")
    return f"{stripped}{clause}." if stripped else explanation


def _location_sentence(
    item: str,
    relation: str,
    anchor: str | None,
    room: str | None,
    *,
    in_view: bool,
    plural: bool,
) -> str:
    present = "are" if plural else "is"
    past = "were" if plural else "was"
    verb = present if in_view else f"{past} last seen"

    if relation == "carried_by_user":
        if in_view:
            return f"You are holding your {item}."
        return f"You were last seen carrying your {item}."
    if relation == "in_room" or (anchor is None and relation != "on_floor"):
        if room:
            return f"Your {item} {verb}{room_phrase(room)}."
        pronoun = "they are" if plural else "it is"
        return f"I have seen your {item}, but I can't tell where {pronoun}."
    if relation == "on_floor" and anchor is None:
        return f"Your {item} {verb} on the floor{room_phrase(room)}."
    phrase = RELATION_PHRASES.get(relation, "near")
    sentence = f"Your {item} {verb} {phrase} {anchor}."
    return _insert_room_clause(sentence, str(anchor), room)


class QueryReasoningEngine:
    """Parses user queries and words answers from a memory state."""

    ROOM_KEYWORDS: ClassVar[dict[str, list[str]]] = {
        "kitchen": ["kitchen"],
        "bedroom": ["bedroom", "bed room"],
        "living room": ["living room", "lounge"],
        "bathroom": ["bathroom", "washroom"],
        "dining room": ["dining room", "dining"],
        "hallway": ["hallway", "corridor", "hall"],
        "entryway": ["entryway", "foyer", "entrance hall"],
        "office": ["office", "study room"],
        "garage": ["garage"],
        "basement": ["basement"],
        "stairway": ["stairway", "staircase"],
        "balcony": ["balcony", "terrace"],
        "storage room": ["storage room", "utility room"],
    }

    STOP_WORDS: ClassVar[set[str]] = {
        "where",
        "is",
        "are",
        "my",
        "did",
        "i",
        "put",
        "leave",
        "left",
        "the",
        "find",
        "show",
        "locate",
        "tell",
        "me",
        "what",
        "happened",
        "to",
        "in",
        "on",
        "a",
        "an",
        "of",
        "somewhere",
        "room",
    }

    @classmethod
    def strip_room_words(cls, query: str) -> str:
        """Remove room mentions: they say where to look, not what."""

        clean = " ".join(query.strip().lower().split())
        for synonyms in cls.ROOM_KEYWORDS.values():
            for synonym in synonyms:
                clean = re.sub(r"\b" + re.escape(synonym) + r"\b", " ", clean)
        clean = re.sub(r"\brooms?\s*#?\s*\d*\b", " ", clean)
        return " ".join(clean.split())

    @classmethod
    def item_phrase(cls, query: str) -> str:
        """The query without room words and stop words ("garbage bag")."""

        tokens = re.findall(r"[\w']+", cls.strip_room_words(query))
        return " ".join(t for t in tokens if t not in cls.STOP_WORDS)

    @classmethod
    def extract_target_item(
        cls, query: str, vocabulary: Vocabulary | None = None
    ) -> str:
        """Canonical vocabulary id of the queried item, else the item phrase."""

        vocab = vocabulary or default_vocabulary()
        stripped = cls.strip_room_words(query)
        entry = vocab.resolve_query(stripped)
        if entry is not None:
            return entry.id
        return cls.item_phrase(query) or stripped or query.strip().lower()

    @classmethod
    def extract_room_filter(cls, query: str) -> str | None:
        """Room constraint of a query ("keys in the kitchen" -> "kitchen").

        Positional references ("room 1", "room #2") map to neutral labels.
        """

        clean = " ".join(query.strip().lower().split())
        positional = re.search(r"\brooms?\s*#?\s*(\d+)\b", clean)
        if positional:
            return f"room #{positional.group(1)}"
        for canonical, synonyms in cls.ROOM_KEYWORDS.items():
            if canonical in clean:
                return canonical
            for synonym in synonyms:
                if re.search(r"\b" + re.escape(synonym) + r"\b", clean):
                    return canonical
        return None

    @classmethod
    def reason_spatio_temporal_state(
        cls,
        target_item: str,
        primary_match: dict[str, Any],
        events: list[dict[str, Any]],
        *,
        plural: bool | None = None,
        vocabulary: Vocabulary | None = None,
    ) -> dict[str, Any]:
        """Word the answer for one memory state (at most two sentences)."""

        vocab = vocabulary or default_vocabulary()
        if plural is None:
            plural = vocab.entry(target_item).plural
        label = primary_match.get("label", target_item)
        anchor = primary_match.get("anchor_label")
        relation = primary_match.get("relation") or "in_room"
        in_view = bool(primary_match.get("is_active_view", False))
        certain = primary_match.get("relation_certain")
        certain = True if certain is None else bool(certain)
        room_label = primary_match.get("room_label")
        distance = primary_match.get("relative_distance")

        explanation = _location_sentence(
            target_item, relation, anchor, room_label, in_view=in_view, plural=plural
        )
        if not certain and relation != "carried_by_user":
            explanation = f"{explanation} {UNCERTAIN_SENTENCE}"

        base_label = str(label).split("[")[0].split("#")[0].strip()
        prior_state = None
        for event in reversed(events):
            if (
                base_label
                and base_label in str(event.get("object", ""))
                and event.get("source_relation")
                and event.get("destination_relation")
            ):
                prior_state = event.get("source_relation")
                break

        edge_case = "active_visibility"
        if relation == "carried_by_user":
            edge_case = "in_hand_obstruction_persistence"
        elif not in_view:
            edge_case = "occlusion_object_permanence"

        return {
            "canonical_item": target_item,
            "instance_label": label,
            "anchor_label": anchor,
            "room_label": room_label,
            "relation": relation,
            "relation_certain": certain,
            "relative_distance_m": round(float(distance), 2) if distance else None,
            "is_persistent_memory": not in_view,
            "transition_history": prior_state,
            "explanation": explanation,
            "edge_case_handled": edge_case,
        }


def event_summary(event: dict[str, Any]) -> str:
    """One plain sentence describing a timeline event."""

    obj = event.get("object") or "Object"
    kind = event.get("event_type") or "state_change"
    src_anchor = event.get("source_anchor")
    dst_anchor = event.get("destination_anchor")
    src_room = event.get("source_room")
    dst_room = event.get("destination_room")
    dst_relation = event.get("destination_relation")
    room = room_phrase(dst_room)

    if kind == "room_change":
        if src_room:
            return f"You moved from {_room_name(src_room)} to {_room_name(dst_room)}."
        return f"You arrived in {_room_name(dst_room)}."
    if kind == "pickup":
        if src_anchor:
            return f"{obj} was picked up from {src_anchor}."
        return f"{obj} was picked up."
    if kind == "placement":
        if dst_anchor:
            phrase = RELATION_PHRASES.get(str(dst_relation), "near")
            return f"{obj} was placed {phrase} {dst_anchor}{room}."
        if dst_relation == "on_floor":
            return f"{obj} was put on the floor{room}."
        return f"{obj} was put down{room}."
    if kind == "anchor_change" or (
        src_anchor and dst_anchor and src_anchor != dst_anchor
    ):
        return f"{obj} moved from {src_anchor} to {dst_anchor}{room}."
    if dst_relation == "carried_by_user":
        return f"{obj} is being carried{room}."
    if dst_anchor:
        phrase = RELATION_PHRASES.get(str(dst_relation), "near")
        return f"{obj} is now {phrase} {dst_anchor}{room}."
    if dst_relation == "on_floor":
        return f"{obj} is now on the floor{room}."
    return f"{obj} changed place{room}."


def _room_name(room: str | None) -> str:
    if not room:
        return "another room"
    if room.lower().startswith("room "):
        return room
    return f"the {room}"
