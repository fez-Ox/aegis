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
        "shoes": ["shoe", "sneaker", "sneakers", "boots", "footwear"],
        "bottle": ["bottle", "water bottle", "flask", "cup", "drink", "tumbler"],
        "keys": ["key", "keychain", "car key", "house key"],
        "glasses": ["glasses", "spectacles", "eyewear", "sunglasses"],
        "medicine": ["medicine", "pills", "meds", "prescription", "vitamins"],
    }

    @classmethod
    def extract_target_item(cls, query: str) -> str:
        """Extract canonical item from natural language query."""
        clean = query.strip().lower()

        for canonical, synonyms in cls.ITEM_SYNONYMS.items():
            if canonical in clean:
                return canonical
            for syn in synonyms:
                if re.search(r"\b" + re.escape(syn) + r"\b", clean):
                    return canonical

        # Fallback to single word if query is brief
        tokens = re.findall(r"\w+", clean)
        ignore_words = {
            "where",
            "is",
            "my",
            "are",
            "did",
            "i",
            "put",
            "leave",
            "the",
            "find",
            "show",
        }
        meaningful = [t for t in tokens if t not in ignore_words]
        return meaningful[0] if meaningful else clean

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

        # Generate dementia-reassuring text (WCAG & cognitive accessibility)
        if relation == "inside":
            if not is_active_view:
                explanation = (
                    f"Your {target_item} are safely put away inside {anchor}. "
                    f"Even though they are currently out of view behind the closed shelf, "
                    f"Aegis remembers they are securely stored inside."
                )
            else:
                explanation = f"Your {target_item} are inside {anchor}."
        elif relation == "carried_by_user" or primary_match.get("is_in_hand", False):
            if not is_active_view:
                explanation = (
                    f"You recently picked up your {target_item}. "
                    f"Even though they are currently obstructed by your hands or body, "
                    f"Aegis tracks that you are carrying them right now."
                )
            else:
                explanation = f"You are currently holding and carrying your {target_item} in your hands."
        elif relation == "on_surface":
            if not is_active_view:
                explanation = (
                    f"Your {target_item} is sitting on {anchor}. "
                    f"Even though it is currently out of direct view, "
                    f"Aegis remembers it remains safely on {anchor}."
                )
            else:
                explanation = f"Your {target_item} is currently resting on {anchor}."
        elif relation == "on_floor":
            explanation = f"Your {target_item} are on the floor right near {anchor}."
        elif relation == "moving_towards":
            explanation = f"Your {target_item} are near {anchor}."
        else:
            explanation = f"Your {target_item} are located at {anchor} ({relation})."

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
