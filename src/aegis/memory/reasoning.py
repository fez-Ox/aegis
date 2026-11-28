"""Query parsing and answer wording for the memory API.

Answers are at most two short sentences and never claim more than the
memory holds: an object out of view is "last seen" somewhere, and an
uncertain relation says so. Item names, synonyms and plural grammar come
from the vocabulary (:mod:`aegis.core.vocabulary`).
"""

from __future__ import annotations

import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

from aegis.core.config import ConfidenceConfig, RankingConfig
from aegis.core.timeutil import parse_iso, to_utc_iso, utc_now
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


# Coarse, culture-neutral clock buckets for human cues. They are generic
# language mappings, not dataset-specific rules.
COARSE_WINDOWS: dict[str, tuple[int, int]] = {
    "this morning": (6, 12),
    "this afternoon": (12, 17),
    "this evening": (17, 22),
    "tonight": (17, 23),
    "last night": (0, 6),
}

ACTIVITY_WINDOWS: dict[str, tuple[int, int]] = {
    "after breakfast": (9, 12),
    "after lunch": (13, 16),
    "after dinner": (19, 23),
}

# Generic English descriptors, not dataset-specific. A stored visual caption
# is matched against these when a patient says e.g. "the blue mug".
VISUAL_TRAITS: dict[str, tuple[str, ...]] = {
    "blue": ("blue",),
    "red": ("red",),
    "green": ("green",),
    "white": ("white",),
    "black": ("black",),
    "yellow": ("yellow",),
    "brown": ("brown",),
    "large": ("large", "big"),
    "small": ("small", "little", "tiny"),
    "metal": ("metal", "metallic"),
    "plastic": ("plastic",),
    "ceramic": ("ceramic",),
    "leather": ("leather",),
}

_DAYS_AGO_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
}


@dataclass(frozen=True, slots=True)
class QueryCues:
    """Human-scale constraints parsed from a natural query."""

    room: str | None = None
    days_ago: int | None = None
    window_start: str | None = None
    window_end: str | None = None
    activity: str | None = None
    visual_terms: tuple[str, ...] = ()


def _day_bounds(moment: datetime) -> tuple[datetime, datetime]:
    start = moment.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def parse_query_cues(query: str, now: datetime | None = None) -> QueryCues:
    """Parse room, coarse time, and routine cues without exact timestamps.

    "yesterday", "two days ago", "this morning", "after lunch", and "just now"
    become UTC windows relative to ``now``.  Exact day/clock strings are left
    to the T4 oracle; they are never required from the patient.
    """

    moment = now or utc_now()
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    text = " ".join(query.strip().lower().split())
    room = QueryReasoningEngine.extract_room_filter(query)

    days_ago: int | None = None
    if "yesterday" in text:
        days_ago = 1
    elif "today" in text:
        days_ago = 0
    elif "last week" in text:
        days_ago = 7
    else:
        match = re.search(r"\b(\d+)\s+days?\s+ago\b", text)
        if match:
            days_ago = int(match.group(1))
        else:
            for word, value in _DAYS_AGO_WORDS.items():
                if re.search(rf"\b{word}\s+days?\s+ago\b", text):
                    days_ago = value
                    break

    activity = next((key for key in ACTIVITY_WINDOWS if key in text), None)
    start: datetime | None = None
    end: datetime | None = None
    if days_ago is not None:
        start, end = _day_bounds(moment - timedelta(days=days_ago))
    elif activity is not None:
        low, high = ACTIVITY_WINDOWS[activity]
        start = moment.replace(hour=low, minute=0, second=0, microsecond=0)
        end = moment.replace(hour=high, minute=0, second=0, microsecond=0)
    else:
        for phrase, (low, high) in COARSE_WINDOWS.items():
            if phrase in text:
                start = moment.replace(hour=low, minute=0, second=0, microsecond=0)
                end = moment.replace(hour=high, minute=0, second=0, microsecond=0)
                break
    if "just now" in text:
        start, end = moment - timedelta(minutes=30), moment

    visual_terms = tuple(
        trait
        for trait, words in VISUAL_TRAITS.items()
        if any(re.search(rf"\b{re.escape(word)}\b", text) for word in words)
    )
    return QueryCues(
        room=room,
        days_ago=days_ago,
        window_start=to_utc_iso(start) if start else None,
        window_end=to_utc_iso(end) if end else None,
        activity=activity,
        visual_terms=visual_terms,
    )


def _recency(value: Any, moment: datetime, half_life_hours: float) -> float:
    if not value:
        return 0.0
    try:
        age_hours = max(0.0, (moment - parse_iso(str(value))).total_seconds() / 3600.0)
    except ValueError:
        return 0.0
    return 0.5 ** (age_hours / half_life_hours)


def reference_time(states: Sequence[dict[str, Any]]) -> datetime:
    """Latest evidence time, so historical datasets are not 'stale' by default.

    An explicit query time always wins; this is only the fallback when the
    caller asks "now" against a memory captured days or weeks ago.
    """
    stamps: list[datetime] = []
    for state in states:
        seen = state.get("last_seen_wallclock")
        if not seen:
            continue
        try:
            parsed = parse_iso(str(seen))
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        stamps.append(parsed)
    return max(stamps) if stamps else utc_now()


def calibrated_confidence(
    state: dict[str, Any],
    moment: datetime,
    config: ConfidenceConfig | None = None,
) -> dict[str, Any]:
    """Turn raw detection confidence into an evidence-aware answer score.

    A weighted geometric mean of detection, identity, support and recency keeps
    the result in [0, 1] and lets any weak factor veto a direct answer. The
    returned ``reason`` distinguishes never-observed, stale and low-confidence
    states instead of collapsing them into one "not found".
    """
    cfg = config or ConfidenceConfig()
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)

    def unit(value: Any) -> float:
        try:
            return min(1.0, max(0.0, float(value)))
        except (TypeError, ValueError):
            return 0.0

    # Missing fields are neutral, not punitive: graph-only states legitimately
    # lack wall-clock time and evidence ids, while durable store states have
    # them. Only present evidence can lower the score.
    raw_confidence = state.get("confidence")
    detection = 1.0 if raw_confidence is None else unit(raw_confidence)
    identity = (
        1.0 if state.get("relation_certain") is not False else cfg.uncertain_identity
    )
    if "observation_count" in state:
        try:
            observations = max(0, int(state.get("observation_count") or 0))
        except (TypeError, ValueError):
            observations = 1
    else:
        observations = 1
    support = 1.0 if observations >= 1 else cfg.uncertain_identity

    seen = state.get("last_seen_wallclock")
    age_hours: float | None = None
    if seen:
        try:
            age_hours = max(
                0.0, (moment - parse_iso(str(seen))).total_seconds() / 3600.0
            )
        except ValueError:
            age_hours = None
    elif "last_seen_relative" in state:
        # Session graphs have no wall clock; their relative times are measured
        # against the newest evidence in the same session.
        try:
            seen_relative = float(state["last_seen_relative"])
            reference = float(state.get("reference_relative", seen_relative))
            age_hours = max(0.0, (reference - seen_relative) / 3600.0)
        except (TypeError, ValueError):
            age_hours = None
    recency = (
        1.0
        if age_hours is None
        else 0.5 ** (age_hours / cfg.confidence_half_life_hours)
    )

    # Neutral factors are 1.0, so a weak detection is never inflated by
    # uninformative identity/support/recency fields.
    score = (
        detection
        * identity**cfg.w_identity
        * support**cfg.w_support
        * recency**cfg.w_recency
    )

    reason: str | None = None
    if age_hours is not None and age_hours > cfg.stale_after_hours:
        reason = "stale"
    elif score < cfg.abstain_below:
        reason = "low_confidence"

    return {
        "score": round(float(score), 6),
        "reason": reason,
        "detection": round(detection, 6),
        "identity": round(identity, 6),
        "support": round(support, 6),
        "recency": round(recency, 6),
        "age_hours": None if age_hours is None else round(age_hours, 3),
    }


def _in_window(value: Any, cues: QueryCues | None) -> bool:
    if not cues or not cues.window_start or not cues.window_end or not value:
        return False
    stamp = str(value)
    return cues.window_start <= stamp < cues.window_end


def rank_candidates(
    states: Sequence[dict[str, Any]],
    target: str,
    *,
    mode: str = "full",
    now: datetime | None = None,
    cues: QueryCues | None = None,
    config: RankingConfig | None = None,
    personal_ids: Collection[int] = (),
    confidence_config: ConfidenceConfig | None = None,
) -> dict[str, Any]:
    """Rank same-class candidates and decide whether to answer or ask.

    ``recency_only`` is the old baseline.  ``salience`` adds interaction and
    displacement.  ``full`` adds the personal registry and fuzzy cue boost.
    Every component is returned so a panel can see why a candidate won.
    """

    if mode not in {"recency_only", "salience", "full"}:
        raise ValueError("ranker mode must be recency_only, salience, or full")
    cfg = config or RankingConfig()
    moment = now or reference_time(states)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)

    text = target.strip().lower()
    hits = [
        state
        for state in states
        if str(state.get("canonical") or "").lower() == text
        or (
            not state.get("canonical") and text in str(state.get("label") or "").lower()
        )
    ]
    if cues and cues.room:
        hits = [
            state
            for state in hits
            if cues.room in str(state.get("room_label") or "").lower()
        ]

    personal = set(personal_ids)
    visual_terms = cues.visual_terms if (mode == "full" and cues) else ()
    scored: list[dict[str, Any]] = []
    for state in hits:
        recency = _recency(
            state.get("last_seen_wallclock"), moment, cfg.recency_half_life_hours
        )
        interaction = (
            _recency(
                state.get("last_moved_wallclock"), moment, cfg.recency_half_life_hours
            )
            if int(state.get("placement_count") or 0) > 0
            else 0.0
        )
        moved_room = state.get("first_room_id") is not None and state.get(
            "room_id"
        ) != state.get("first_room_id")
        moved_anchor = state.get("first_anchor_id") is not None and state.get(
            "anchor_id"
        ) != state.get("first_anchor_id")
        displacement = 1.0 if moved_room or moved_anchor else 0.0
        vip = 1.0 if state.get("instance_id") in personal else 0.0
        cue = (
            1.0
            if mode == "full"
            and _in_window(
                state.get("last_moved_wallclock") or state.get("last_seen_wallclock"),
                cues,
            )
            else 0.0
        )
        caption = str(
            state.get("visual_caption") or state.get("visual_tag") or ""
        ).lower()
        visual = (
            1.0
            if visual_terms and any(term in caption for term in visual_terms)
            else 0.0
        )

        if mode == "recency_only":
            total = recency
        elif mode == "salience":
            total = (
                cfg.w_act * interaction
                + cfg.w_disp * displacement
                + cfg.w_rec * recency
            )
        else:
            total = (
                cfg.w_vip * vip
                + cfg.w_act * interaction
                + cfg.w_disp * displacement
                + cfg.w_rec * recency
                + cfg.w_cue * cue
                + cfg.w_visual * visual
            )

        calibrated = calibrated_confidence(state, moment, confidence_config)
        scored.append(
            {
                "instance_id": state.get("instance_id"),
                "object_id": state.get("instance_id"),
                "label": state.get("label"),
                "class_label": state.get("canonical") or state.get("label"),
                "visual_tag": state.get("visual_caption") or state.get("visual_tag"),
                "canonical": state.get("canonical"),
                "room_id": state.get("room_id"),
                "room_label": state.get("room_label"),
                "anchor_id": state.get("anchor_id"),
                "anchor_label": state.get("anchor_label"),
                "relation": state.get("relation"),
                "relation_certain": state.get("relation_certain"),
                "confidence": calibrated["score"],
                "confidence_factors": {
                    key: calibrated[key]
                    for key in (
                        "detection",
                        "identity",
                        "support",
                        "recency",
                        "age_hours",
                    )
                },
                "abstain_reason": calibrated["reason"],
                "last_seen_relative": state.get("last_seen_relative"),
                "reference_relative": state.get("reference_relative"),
                "last_seen_at": state.get("last_seen_wallclock"),
                "last_moved_at": state.get("last_moved_wallclock"),
                "placement_count": int(state.get("placement_count") or 0),
                "pickup_count": int(state.get("pickup_count") or 0),
                "observation_count": int(state.get("observation_count") or 0),
                "evidence_id": state.get("evidence_id"),
                "evidence_ref": state.get("evidence_id"),
                "last_seen_ts": state.get("last_seen_wallclock"),
                "last_moved_ts": state.get("last_moved_wallclock"),
                "score": round(float(total), 6),
                "rank_score": round(float(total), 6),
                "score_breakdown": {
                    "vip": round(vip, 6),
                    "interaction": round(interaction, 6),
                    "displacement": round(displacement, 6),
                    "recency": round(recency, 6),
                    "cue": round(cue, 6),
                    "visual": round(visual, 6),
                    "total": round(float(total), 6),
                },
            }
        )

    scored.sort(
        key=lambda item: (item["score"], str(item["last_seen_at"] or "")),
        reverse=True,
    )
    # Three photos of the same table do not help a patient choose. Keep only
    # the best-scoring instance per distinct place.
    distinct: list[dict[str, Any]] = []
    seen_places: set[tuple[Any, Any]] = set()
    for item in scored:
        place = (
            item["anchor_id"],
            item["room_id"] if item["anchor_id"] is None else None,
        )
        if place in seen_places:
            continue
        seen_places.add(place)
        distinct.append(item)
    candidates = distinct[: cfg.candidate_limit]

    is_ambiguous = False
    reason = None
    if len(candidates) >= 2 and candidates[0]["score"] > 0:
        first, second = candidates[0], candidates[1]
        same_place = (
            first["anchor_id"] is not None and first["anchor_id"] == second["anchor_id"]
        ) or (
            first["anchor_id"] is None
            and second["anchor_id"] is None
            and first["room_id"] == second["room_id"]
        )
        if (
            not same_place
            and abs(first["score"] - second["score"]) < cfg.ambiguity_margin
        ):
            is_ambiguous = True
            reason = "multiple_active_instances_same_class"

    abstain_reason = candidates[0]["abstain_reason"] if candidates else None
    if not candidates:
        resolution = "not_found"
    elif is_ambiguous:
        # Recognition over recall: when several real instances compete, show
        # their photos instead of hiding them behind a generic abstention.
        resolution = "disambiguate"
    elif abstain_reason is not None:
        resolution = "abstain"
    else:
        resolution = "direct"
    return {
        "target": target,
        "resolution_mode": resolution,
        "is_ambiguous": is_ambiguous,
        "ambiguity_reason": reason,
        "abstain_reason": abstain_reason,
        "candidates": candidates,
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
