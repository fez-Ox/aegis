"""Cognitive query reasoning engine for Aegis.

Provides natural language intent parsing, temporal disambiguation,
and dementia-appropriate spatial explanations based on the R4DSG memory graph.
"""

from __future__ import annotations

import re
from typing import Any, ClassVar


class QueryReasoningEngine:
    """Disambiguates user queries and generates grounded spatial explanations."""

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

        return {
            "canonical_item": target_item,
            "instance_label": label,
            "anchor_label": anchor,
            "relation": relation,
            "relative_distance_m": round(float(dist_m), 2) if dist_m else 0.1,
            "is_persistent_memory": not is_active_view,
            "transition_history": prior_state if transition_found else None,
            "explanation": explanation,
            "edge_case_handled": edge_case,
        }
