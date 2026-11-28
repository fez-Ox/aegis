"""The single rule-based NLQ answer engine.

It answers from one memory view only, composes every answer from a template,
and abstains honestly when the memory has no evidence. There is no LLM on the
mandatory path and the engine never writes a location it did not read from a
state. Intents ``temporal`` and ``activity`` are explicit, honest stubs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from aegis.memory.reasoning import calibrated_confidence, reference_time

from .dictionary import DictionaryIndex

IN_HAND = "carried_by_user"
PLURAL = frozenset({"shoes", "keys", "glasses", "clothes", "pants", "boots"})


class Intent(str, Enum):
    LOCATE = "locate"
    TEMPORAL = "temporal"
    ACTIVITY = "activity"
    UNKNOWN = "unknown"


@dataclass
class AskResult:
    question: str
    intent: str
    status: str
    answer: str
    abstained: bool = False
    abstain_reason: str | None = None
    instance_label: str | None = None
    anchor_label: str | None = None
    room_label: str | None = None
    relation: str | None = None
    confidence: float | None = None
    last_seen_timestamp: float | None = None
    last_seen_wallclock: str | None = None
    suggestions: list[str] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    other_instances: list[str] = field(default_factory=list)
    dataset_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "intent": self.intent,
            "status": self.status,
            "answer": self.answer,
            "abstained": self.abstained,
            "abstain_reason": self.abstain_reason,
            "instance_label": self.instance_label,
            "anchor_label": self.anchor_label,
            "room_label": self.room_label,
            "relation": self.relation,
            "confidence": self.confidence,
            "last_seen_timestamp": self.last_seen_timestamp,
            "last_seen_wallclock": self.last_seen_wallclock,
            "suggestions": self.suggestions,
            "evidence": self.evidence,
            "other_instances": self.other_instances,
            "dataset_id": self.dataset_id,
        }


def memory_view_from_repo(repo: Any) -> dict[str, Any]:
    """Adapt a `MemoryRepository` to the engine's memory-view contract."""
    states = repo.latest_states()
    return {
        "dataset_id": getattr(repo, "dataset_id", None),
        "latest_objects": list(states.values())
        if isinstance(states, dict)
        else list(states),
        "anchors": repo.anchors(),
        "rooms": repo.rooms(),
        "events": repo.events(),
        "timeline_frames": repo.keyframe_count(),
    }


def memory_view_from_graph(
    graph: dict[str, Any], dataset_id: str | None = None
) -> dict[str, Any]:
    """Adapt a raw scene-graph JSON dict to the memory-view contract."""
    from aegis.memory.repository import latest_states_from_graph

    states = latest_states_from_graph(graph)
    return {
        "dataset_id": dataset_id or graph.get("dataset_id"),
        "latest_objects": list(states.values()),
        "anchors": graph.get("anchors", []),
        "rooms": graph.get("rooms", []),
        "events": graph.get("events", []),
        "timeline_frames": len(graph.get("timeline", {})),
    }


class AnswerEngine:
    def __init__(self, dictionary: DictionaryIndex | None = None) -> None:
        self.dictionary = dictionary or DictionaryIndex.seeded()

    def classify_intent(self, question: str) -> Intent:
        q = question.lower()
        if re.search(r"\b(when|what time|how long ago|at what time)\b", q):
            return Intent.TEMPORAL
        if re.search(r"\b(what did|what have|what was|what happened|activities)\b", q):
            return Intent.ACTIVITY
        if re.search(r"\b(where|find|locate|show)\b", q):
            return Intent.LOCATE
        slots = self.dictionary.lookup_item(q)
        if slots.item or slots.item_raw:
            return Intent.LOCATE
        return Intent.UNKNOWN

    def ask(self, question: str, memory: dict[str, Any]) -> AskResult:
        q = " ".join(str(question).split())
        if not q:
            return self._abstain(
                q, Intent.UNKNOWN, "empty_query", "Please type a question."
            )
        intent = self.classify_intent(q)
        if intent is Intent.TEMPORAL:
            return self._abstain(
                q,
                intent,
                "temporal_handler_not_implemented",
                "I can't answer time questions about this memory yet. Ask me where something is.",
            )
        if intent is Intent.ACTIVITY:
            return self._abstain(
                q,
                intent,
                "activity_handler_not_implemented",
                "I don't track activities yet. Ask me where something is.",
            )
        if intent is Intent.UNKNOWN:
            return self._abstain(
                q, intent, "unknown_intent", "I don't understand that question yet."
            )
        return self._answer_locate(q, memory)

    # -- location answers --------------------------------------------------
    def _answer_locate(self, q: str, memory: dict[str, Any]) -> AskResult:
        slots = self.dictionary.lookup_item(q)
        if not slots.item:
            suggestions = self.dictionary.suggestions_for(slots.item_raw)
            return self._abstain(
                q,
                Intent.LOCATE,
                "item_not_in_dictionary",
                "I don't know that word. Try: " + ", ".join(suggestions)
                if suggestions
                else "I don't know that word. Try another object name.",
                suggestions=suggestions,
            )

        states = [s for s in memory.get("latest_objects", []) if isinstance(s, dict)]
        candidates = [
            s
            for s in states
            if (s.get("canonical") or self.dictionary.canonical_of(s.get("label", "")))
            == slots.item
        ]
        if not candidates:
            known = sorted(
                {
                    str(s.get("label", "")).split("#")[0].strip()
                    for s in states
                    if s.get("label")
                }
            )[:3]
            hint = f" I remember: {', '.join(known)}." if known else ""
            return self._abstain(
                q,
                Intent.LOCATE,
                "not_observed_in_memory",
                f"I haven't seen your {slots.item}.{hint}",
            )

        if slots.room:
            filtered = [
                s
                for s in candidates
                if slots.room in str(s.get("room_label") or "").lower()
                or slots.room in str(s.get("anchor_label") or "").lower()
            ]
            if not filtered:
                return self._abstain(
                    q,
                    Intent.LOCATE,
                    "no_match_in_room",
                    f"I couldn't find your {slots.item} in the {slots.room}.",
                )
            candidates = filtered

        candidates.sort(
            key=lambda s: (
                bool(s.get("is_active_view")),
                float(s.get("last_seen_timestamp") or 0.0),
                str(s.get("last_seen_wallclock") or ""),
            ),
            reverse=True,
        )
        primary = candidates[0]
        assessment = calibrated_confidence(primary, reference_time(states))
        if assessment["reason"] is not None:
            reason = assessment["reason"]
            return self._abstain(
                q,
                Intent.LOCATE,
                reason,
                {
                    "never_observed": "I have no reliable memory of that item.",
                    "stale": "I only have old information about that item.",
                    "low_confidence": "I'm not confident enough to say where that is.",
                }.get(reason, "I'm not confident enough to say where that is."),
            )
        answer = self._compose(slots.item, primary)
        evidence = [
            {
                "observation_id": f"state:{primary.get('instance_id', 'unknown')}",
                "description": (
                    f"{primary.get('label', slots.item)} seen "
                    f"{self._place(primary)}{self._room_clause(primary)}."
                ),
                "observed_at": primary.get("last_seen_wallclock"),
                "anchor_label": primary.get("anchor_label"),
                "room_label": primary.get("room_label"),
                "crop_url": primary.get("crop_url"),
            }
        ]
        result = AskResult(
            question=q,
            intent=Intent.LOCATE.value,
            status="answered",
            answer=answer,
            instance_label=primary.get("label"),
            anchor_label=primary.get("anchor_label"),
            room_label=primary.get("room_label"),
            relation=primary.get("relation"),
            confidence=assessment["score"],
            last_seen_timestamp=primary.get("last_seen_timestamp"),
            last_seen_wallclock=primary.get("last_seen_wallclock"),
            other_instances=[str(s.get("label")) for s in candidates[1:]],
            evidence=evidence,
            dataset_id=memory.get("dataset_id"),
        )
        # At most two sentences, always.
        result.answer = self._cap(result.answer)
        return result

    def _compose(self, item: str, state: dict[str, Any]) -> str:
        name = item.replace("_", " ")
        plural = item in PLURAL
        active = bool(state.get("is_active_view"))
        if active:
            verb = "are" if plural else "is"
        else:
            verb = "were" if plural else "was"
        relation = state.get("relation") or "in_room"
        if relation == IN_HAND:
            place = "being carried"
            if active:
                sentence = f"You {verb} holding your {name}"
            else:
                sentence = f"You were last seen carrying your {name}"
        else:
            place = self._place(state)
            sentence = f"Your {name} {verb} {'last seen ' if not active else ''}{place}"
        sentence += self._room_clause(state) + "."
        if not active:
            sentence += " Aegis remembers it there, even out of direct view."
        elif state.get("relation_certain") is False:
            sentence += " I'm not fully sure about the exact spot."
        return sentence

    @staticmethod
    def _place(state: dict[str, Any]) -> str:
        relation = state.get("relation") or "in_room"
        anchor = state.get("anchor_label")
        phrases = {
            "inside": "inside",
            "on_surface": "on",
            "under": "under",
            "above": "above",
            "next_to": "next to",
            "near": "near",
        }
        if relation in phrases and anchor:
            return f"{phrases[relation]} {anchor}"
        if relation == "on_floor":
            return f"on the floor beside {anchor}" if anchor else "on the floor"
        if anchor:
            return f"near {anchor}"
        return "where I can't pin down the exact spot"

    @staticmethod
    def _room_clause(state: dict[str, Any]) -> str:
        room = state.get("room_label")
        if not room:
            return ""
        text = str(room)
        if re.match(r"room\s*#", text, re.IGNORECASE):
            return f" in {text}"
        return f" in the {text}"

    @staticmethod
    def _cap(text: str) -> str:
        sentences = [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]
        return " ".join(sentences[:2])

    def _abstain(
        self,
        q: str,
        intent: Intent,
        reason: str,
        answer: str,
        **extra: Any,
    ) -> AskResult:
        return AskResult(
            question=q,
            intent=intent.value,
            status=reason,
            answer=answer,
            abstained=True,
            abstain_reason=reason,
            **extra,
        )
