"""Cognitive query reasoning engine for Aegis.

Provides natural language intent parsing, temporal disambiguation,
and dementia-appropriate spatial explanations based on the R4DSG memory graph.
"""

from __future__ import annotations

import re
from typing import Any, ClassVar


def room_phrase(room: str | None) -> str:
    """Grammar-aware room clause for natural explanations ("in the Kitchen")."""

    if not room:
        return ""
    if room.lower().startswith("room "):
        return f" in {room}"
    return f" in the {room}"


def _insert_room_clause(explanation: str, anchor: str, room: str | None) -> str:
    """Attach the room clause to the sentence that names the anchor.

    Keeps multi-sentence, dementia-friendly explanations readable: the room
    belongs with the location ("...inside Storage Cabinet #1 in the Entryway."),
    not tacked onto the closing reassurance.
    """

    clause = room_phrase(room)
    if not clause or not anchor:
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


class QueryReasoningEngine:
    """Disambiguates user queries and generates grounded spatial explanations."""

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

    # Words that refer to rooms rather than items; they must never leak into
    # target-item extraction (e.g. "keys in the kitchen" targets keys).
    _ROOM_IGNORE_WORDS: ClassVar[set[str]] = {
        "kitchen",
        "bedroom",
        "bathroom",
        "living",
        "dining",
        "hallway",
        "corridor",
        "hall",
        "entryway",
        "foyer",
        "office",
        "garage",
        "basement",
        "stairway",
        "staircase",
        "balcony",
        "terrace",
        "room",
    }

    ITEM_SYNONYMS: ClassVar[dict[str, list[str]]] = {
        "shoes": [
            "shoe",
            "shoes",
            "sneaker",
            "sneakers",
            "boots",
            "footwear",
            "slippers",
        ],
        "bottle": ["bottle", "water bottle", "flask", "cup", "drink", "tumbler", "mug"],
        "keys": ["key", "keys", "keychain", "car key", "house key"],
        "glasses": [
            "glasses",
            "spectacles",
            "eyewear",
            "sunglasses",
            "reading glasses",
        ],
        "cooking pot": [
            "cooking pot",
            "pot",
            "pots",
            "pan",
            "pans",
            "saucepan",
            "cookware",
        ],
        "bowl": ["bowl", "bowls", "dish", "dishes", "basin"],
        "food": ["food", "leftover", "leftovers", "meal", "snack", "groceries"],
        "clothes": [
            "clothes",
            "clothing",
            "shirt",
            "shirts",
            "pants",
            "laundry",
            "garment",
            "garments",
        ],
        "trash": [
            "trash",
            "garbage",
            "rubbish",
            "waste",
            "trash bin",
            "bin",
            "wastebasket",
        ],
        "phone": ["phone", "cell phone", "mobile phone", "smartphone"],
        "backpack": ["backpack", "bag", "bags", "handbag", "purse", "pack"],
        "laptop": ["laptop", "computer", "notebook"],
        "book": ["book", "books", "novel", "magazine"],
        "medicine": [
            "medicine",
            "medicines",
            "pills",
            "meds",
            "prescription",
            "vitamins",
        ],
    }

    PLURAL_ITEMS: ClassVar[set[str]] = {
        "shoes",
        "keys",
        "glasses",
        "clothes",
        "pants",
        "pots",
        "bowls",
        "dishes",
        "pills",
        "vitamins",
        "slippers",
        "boots",
    }

    @classmethod
    def extract_target_item(cls, query: str) -> str:
        """Extract canonical item from natural language query."""
        clean = query.strip().lower()

        # Remove room mentions first: they describe where to look, not what.
        for synonyms in cls.ROOM_KEYWORDS.values():
            for synonym in synonyms:
                clean = re.sub(r"\b" + re.escape(synonym) + r"\b", " ", clean)
        clean = re.sub(r"\brooms?\s*#?\s*\d*\b", " ", clean)
        clean = " ".join(clean.split())
        if not clean:
            return query.strip().lower()

        # 1. Exact or synonym match against known synonyms
        for canonical, synonyms in cls.ITEM_SYNONYMS.items():
            if canonical in clean:
                return canonical
            for syn in synonyms:
                if re.search(r"\b" + re.escape(syn) + r"\b", clean):
                    return canonical

        # 2. Extract meaningful tokens (stripping question stopwords)
        tokens = re.findall(r"\w+", clean)
        ignore_words = {
            "where",
            "is",
            "are",
            "my",
            "did",
            "i",
            "put",
            "leave",
            "the",
            "find",
            "show",
            "locate",
            "tell",
            "me",
            "what",
            "happened",
            "to",
            *cls._ROOM_IGNORE_WORDS,
        }
        meaningful = [t for t in tokens if t not in ignore_words]

        if not meaningful:
            return clean

        # Preserve multi-word target if 2 words (e.g. "cooking pot", "dirty clothes")
        if len(meaningful) >= 2:
            candidate_phrase = " ".join(meaningful[:2])
            for canonical, synonyms in cls.ITEM_SYNONYMS.items():
                if candidate_phrase in synonyms or candidate_phrase in canonical:
                    return canonical
            return candidate_phrase

        item = meaningful[0]
        # Singularize trailing 's' if not ending in 'ss'
        if (
            item.endswith("s")
            and len(item) > 3
            and not item.endswith("ss")
            and item not in {"glasses", "clothes", "shoes", "keys"}
        ):
            return item[:-1]
        return item

    @classmethod
    def extract_room_filter(cls, query: str) -> str | None:
        """Extract a room constraint from a query ("keys in the kitchen" -> "kitchen").

        Returns the canonical room keyword (lowercase) or None. Also supports
        positional references like "room 1" / "room #2", which map to the
        neutral "Room #N" labels produced by the memory layer.
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
    ) -> dict[str, Any]:
        """Formulate a dementia-tailored spatial explanation with edge-case handling.

        Handles:
        1. Occlusion & persistence: Object inside closed cabinet.
        2. State transition: Moving from floor to inside shelf.
        3. Recency & anchor reference.
        """
        label = primary_match.get("label", target_item)
        anchor = primary_match.get("anchor_label", "the designated room anchor")
        relation = primary_match.get("relation", "near")
        is_active_view = primary_match.get("is_active_view", True)
        dist_m = primary_match.get("relative_distance", 0.1)

        # Check if there was an earlier state change in events
        transition_found = False
        prior_state = ""
        for ev in reversed(events):
            if (
                label.split("[")[0].strip() in ev.get("object", "")
                and ev.get("source_relation")
                and ev.get("destination_relation")
            ):
                prior_state = ev.get("source_relation")
                transition_found = True
                break

        # Grammar agreement for singular vs plural items
        is_plural = (
            target_item in cls.PLURAL_ITEMS
            or target_item.endswith("s")
            or "pair" in label.lower()
        )
        is_are = "are" if is_plural else "is"
        they_it = "they are" if is_plural else "it is"
        them_it = "them" if is_plural else "it"

        # Generate dementia-reassuring text (WCAG & cognitive accessibility)
        if relation == "inside":
            if not is_active_view:
                explanation = (
                    f"Your {target_item} {is_are} safely put away inside {anchor}. "
                    f"Even though {they_it} currently out of direct view behind the closed compartment, "
                    f"Aegis remembers {they_it} securely stored inside."
                )
            else:
                explanation = f"Your {target_item} {is_are} inside {anchor}."
        elif relation == "carried_by_user" or primary_match.get("is_in_hand", False):
            if not is_active_view:
                explanation = (
                    f"You recently picked up your {target_item}. "
                    f"Even though {they_it} currently obstructed by your hands or body, "
                    f"Aegis tracks that you are carrying {them_it} right now."
                )
            else:
                explanation = f"You are currently holding and carrying your {target_item} in your hands."
        elif relation == "on_surface":
            if not is_active_view:
                explanation = (
                    f"Your {target_item} {is_are} sitting on {anchor}. "
                    f"Even though {they_it} currently out of direct view, "
                    f"Aegis remembers {them_it} remains safely on {anchor}."
                )
            else:
                explanation = (
                    f"Your {target_item} {is_are} currently resting on {anchor}."
                )
        elif relation == "on_floor":
            explanation = (
                f"Your {target_item} {is_are} on the floor right near {anchor}."
            )
        elif relation == "moving_towards":
            explanation = f"Your {target_item} {is_are} near {anchor}."
        else:
            explanation = (
                f"Your {target_item} {is_are} located at {anchor} ({relation})."
            )

        edge_case = "active_visibility"
        if relation == "carried_by_user" or primary_match.get("is_in_hand", False):
            edge_case = "in_hand_obstruction_persistence"
        elif not is_active_view:
            edge_case = "occlusion_object_permanence"

        room_label = primary_match.get("room_label")
        explanation = _insert_room_clause(explanation, str(anchor), room_label)

        return {
            "canonical_item": target_item,
            "instance_label": label,
            "anchor_label": anchor,
            "room_label": room_label,
            "relation": relation,
            "relative_distance_m": round(float(dist_m), 2) if dist_m else 0.1,
            "is_persistent_memory": not is_active_view,
            "transition_history": prior_state if transition_found else None,
            "explanation": explanation,
            "edge_case_handled": edge_case,
        }
