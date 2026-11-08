"""Hybrid NLQ engine skeleton (Path C: deterministic retrieval + LLM escape).

Contract with the rest of the project (AGENT-DOC_context.md section 7):

* Input:  one user question as text (typed, or speech-to-text at the client;
  the engine is agnostic - it never sees audio).
* Output: text answer, grounded strictly in the memory fetched through
  ``comm.AegisCommClient``, or a clean, honest abstention.
* The **very large dictionary** is the primary understanding mechanism
  (``nlq.dictionary.DictionaryIndex``); an LLM is used only as an escape
  hatch for vocabulary/intent the dictionary cannot resolve.

Invariants encoded here (never violate):
    1. No evidence -> abstain; never fabricate a location (FR5.5/SC6).
    2. Dataset isolation: one memory view per question (established rule).
    3. Dementia-friendly phrasing: short sentences, plain words (NFR-U2).
    4. The LLM never writes the answer: it may only map an unknown phrase to
       a *validated* dictionary item/intent, after which the deterministic
       evidence path runs. Hallucinated locations cannot reach the user.

TODO(NLQ) map to AGENT-DOC_ToDos.md milestone 3:
    - M3.2 temporal/activity intents (TEMPORAL/ACTIVITY return honest
      "not yet tracked" abstentions for now).
    - M3.3 freshness/stale reporting (real "time ago").
    - M3.4 calibrated confidence + abstention threshold.
    - M3.5 evidence references (observation id, frame crop URLs).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .dictionary import DictionaryIndex, Slots

try:  # folder-style usage ("NL Querying" root on sys.path)
    from comm.client import AegisCommClient
    from comm.llm import LLMClient, LLMError
except ImportError:  # package-style usage (folder moved under src/)
    from ..comm.client import AegisCommClient
    from ..comm.llm import LLMClient, LLMError

# Objects the wearer is currently holding (relation vocabulary is fixed).
IN_HAND_RELATION = "carried_by_user"

PLURAL_ITEMS: frozenset[str] = frozenset(
    {"shoes", "keys", "glasses", "clothes", "pills", "boots", "slippers", "pots"}
)

LLM_SYSTEM_PROMPT = """\
You map one care-recipient question onto a fixed household memory vocabulary.
Reply with ONE JSON object and nothing else:
{"intent": "locate|temporal|activity|unsupported", "item": string|null,
 "room": string|null, "confidence": number}

Hard rules:
- "locate" asks WHERE; "temporal" asks WHEN; "activity" asks WHAT the person
  did.
- "item" MUST be exactly one string from canonical_items or tracked_labels.
  Never copy a slang word the user used. Map it to the closest canonical item.
- "room" must be null unless the question explicitly mentions that room.
- If nothing fits: {"intent": "unsupported", "item": null, "room": null,
  "confidence": 0}.
- Never invent an item, room, anchor, or location.

Examples (the memory context changes; the mapping style does not):
Q: "where are my kicks"      -> {"intent": "locate", "item": "shoes",
                                 "room": null, "confidence": 0.9}
Q: "where is my water flask" -> {"intent": "locate", "item": "bottle",
                                 "room": null, "confidence": 0.9}
Q: "where are my shades"     -> {"intent": "locate", "item": "glasses",
                                 "room": null, "confidence": 0.9}
Q: "where is my hoverboard"  -> {"intent": "unsupported", "item": null,
                                 "room": null, "confidence": 0}
"""


class Intent(str, Enum):
    """The intent set the deterministic side of the hybrid understands."""

    LOCATE = "locate"  # "where is my shoes?"
    TEMPORAL = "temporal"  # "when did I last see my glasses?"
    ACTIVITY = "activity"  # "what did I do this morning?"
    UNKNOWN = "unknown"


@dataclass
class AskResult:
    """Everything the answering contract exposes, transport-independent."""

    query: str
    intent: Intent
    found: bool = False
    abstained: bool = False
    abstain_reason: str | None = None
    answer_text: str = ""
    item: str | None = None
    instance_label: str | None = None
    anchor_label: str | None = None
    room_label: str | None = None
    relation: str | None = None
    last_seen_timestamp: float | None = None
    other_instances: list[dict[str, Any]] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    llm_used: bool = False
    # TODO(NLQ M3.5): evidence refs (observation id, frame_id, crop_url).
    # TODO(NLQ M3.4): calibrated confidence + abstention threshold.

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "intent": self.intent.value,
            "found": self.found,
            "abstained": self.abstained,
            "abstain_reason": self.abstain_reason,
            "answer_text": self.answer_text,
            "item": self.item,
            "instance_label": self.instance_label,
            "anchor_label": self.anchor_label,
            "room_label": self.room_label,
            "relation": self.relation,
            "last_seen_timestamp": self.last_seen_timestamp,
            "other_instances": self.other_instances,
            "suggestions": self.suggestions,
            "llm_used": self.llm_used,
        }


class HybridNLQEngine:
    """Dictionary-first question answering over the scene-graph memory."""

    def __init__(
        self,
        client: AegisCommClient | None = None,
        dictionary: DictionaryIndex | None = None,
        llm: LLMClient | None | str = "auto",
    ) -> None:
        self.client = client or AegisCommClient()
        self.dictionary = dictionary or DictionaryIndex.seeded()
        # "auto" auto-configures from env/key file; None disables the escape
        # hatch (used by offline tests); any client object is used as-is.
        if llm == "auto":
            self.llm: LLMClient | None = LLMClient.from_env_if_configured()
        elif llm is None:
            self.llm = None
        else:
            self.llm = llm  # type: ignore[assignment]
        self.last_llm_error: str | None = None
        # UC-03 postcondition: log every query + resolved evidence.
        self._query_log: list[AskResult] = []
        # TODO(NLQ): persist the query log instead of keeping it in memory.

    def llm_status(self) -> dict[str, Any]:
        """Key-free LLM configuration for smoke tests and operator logs."""
        status = (
            self.llm.status()
            if self.llm is not None
            else {"available": False, "base_url": None, "model": None}
        )
        status["last_error"] = self.last_llm_error
        return status

    # ------------------------------------------------------------------
    # Intent classification (deterministic side of the hybrid)
    # ------------------------------------------------------------------
    def classify_intent(self, query: str) -> Intent:
        """Rule-based intent classifier; free-form falls to UNKNOWN/LLM."""
        clean = " ".join(str(query).lower().strip().split())
        if not clean:
            return Intent.UNKNOWN
        if re.search(r"\bwhere\b", clean):
            return Intent.LOCATE
        if re.search(r"\bwhen\b", clean) or re.search(
            r"\blast\s+(see|saw|time)\b", clean
        ):
            return Intent.TEMPORAL
        if re.search(r"\bwhat\s+(did|have)\s+i\b|\bhappened\b", clean):
            return Intent.ACTIVITY
        # Bare item queries ("shoes") count as locate-style lookups.
        if re.fullmatch(r"[a-z][a-z\s']*", clean):
            return Intent.LOCATE
        return Intent.UNKNOWN

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def ask(self, query: str, dataset_id: str) -> AskResult:
        """Answer one question from one dataset's memory."""
        intent = self.classify_intent(query)
        handler: Callable[[HybridNLQEngine, str, str], AskResult] = {
            Intent.LOCATE: HybridNLQEngine._answer_locate,
            Intent.TEMPORAL: HybridNLQEngine._answer_temporal,
            Intent.ACTIVITY: HybridNLQEngine._answer_activity,
            Intent.UNKNOWN: HybridNLQEngine._answer_unknown,
        }[intent]
        result = handler(self, query, dataset_id)
        self._query_log.append(result)
        return result

    def query_log(self) -> list[dict[str, Any]]:
        return [row.to_dict() for row in self._query_log]

    # ------------------------------------------------------------------
    # LOCATE
    # ------------------------------------------------------------------
    def _answer_locate(self, query: str, dataset_id: str) -> AskResult:
        slots = self.dictionary.lookup_item(query)
        if slots.item is not None:
            return self._locate_item(query, dataset_id, slots.item, slots.room)
        # Unknown vocabulary: let the escape hatch map it to a validated item
        # before falling back to a clarification.
        fallback = self._llm_fallback(query, dataset_id)
        if fallback is not None and fallback["intent"] == "locate":
            return self._locate_item(
                query,
                dataset_id,
                fallback["item"],
                fallback.get("room"),
                llm_used=True,
            )
        return self._abstain_unknown_item(query, slots)

    def _locate_item(
        self,
        query: str,
        dataset_id: str,
        item: str,
        room: str | None = None,
        *,
        llm_used: bool = False,
    ) -> AskResult:
        """Evidence path shared by the dictionary and the LLM escape hatch."""
        memory = self.client.load_memory(dataset_id)
        matches = self._match_instances(item, memory["latest_objects"])
        if room:
            matches = [
                match
                for match in matches
                if room in str(match.get("room_label", "")).lower()
                or room in str(match.get("anchor_label", "")).lower()
            ]
        if not matches:
            result = self._abstain_no_match(query, Slots(item=item, room=room), memory)
            result.llm_used = llm_used
            return result

        ranked = self._rank_matches(item, matches)
        primary = ranked[0]
        return AskResult(
            query=query,
            intent=Intent.LOCATE,
            found=True,
            item=item,
            instance_label=primary.get("label"),
            anchor_label=primary.get("anchor_label"),
            room_label=primary.get("room_label"),
            relation=primary.get("relation"),
            last_seen_timestamp=primary.get("last_seen_timestamp"),
            other_instances=[
                {
                    "instance_id": match.get("instance_id"),
                    "label": match.get("label"),
                    "anchor": match.get("anchor_label"),
                    "relation": match.get("relation"),
                }
                for match in ranked[1:]
            ],
            answer_text=self._compose_statement(item, primary),
            llm_used=llm_used,
        )

    # ------------------------------------------------------------------
    # TEMPORAL / ACTIVITY (stubs - M3.2)
    # ------------------------------------------------------------------
    def _answer_temporal(self, query: str, dataset_id: str) -> AskResult:
        return AskResult(
            query=query,
            intent=Intent.TEMPORAL,
            abstained=True,
            abstain_reason="temporal_handler_not_implemented",
            # Honest abstention: never fabricate a temporal answer.
            answer_text=(
                "I can't answer time questions about this memory yet. "
                "I can still tell you where things are now."
            ),
        )

    def _answer_activity(self, query: str, dataset_id: str) -> AskResult:
        return AskResult(
            query=query,
            intent=Intent.ACTIVITY,
            abstained=True,
            abstain_reason="activity_handler_not_implemented",
            answer_text="I don't track activities yet, so I can't answer that.",
        )

    # ------------------------------------------------------------------
    # UNKNOWN -> LLM escape hatch (evidence-gated)
    # ------------------------------------------------------------------
    def _answer_unknown(self, query: str, dataset_id: str) -> AskResult:
        """Resolve unknown vocabulary/intent, then run the evidence path.

        The LLM only *classifies*: it may map the phrase to a dictionary item
        or a tracked label. The answer text itself always comes from the
        deterministic handlers, so a hallucinated location cannot leak out.
        """
        fallback = self._llm_fallback(query, dataset_id)
        if fallback is None:
            return AskResult(
                query=query,
                intent=Intent.UNKNOWN,
                abstained=True,
                abstain_reason="unknown_intent_no_llm_fallback",
                answer_text=(
                    "I don't understand that question yet. "
                    "Try asking where something is, like 'where are my keys'."
                ),
            )

        intent = fallback["intent"]
        if intent == "locate":
            return self._locate_item(
                query,
                dataset_id,
                fallback["item"],
                fallback.get("room"),
                llm_used=True,
            )
        handler: Callable[[HybridNLQEngine, str, str], AskResult] = {
            "temporal": HybridNLQEngine._answer_temporal,
            "activity": HybridNLQEngine._answer_activity,
        }[intent]
        result = handler(self, query, dataset_id)
        result.llm_used = True
        return result

    def _llm_fallback(self, query: str, dataset_id: str) -> dict[str, Any] | None:
        """Ask the LLM to map the phrase onto the validated vocabulary.

        Returns ``{"intent", "item", "room"}`` or ``None``. Never raises on
        network/parse failure: the caller degrades to an honest abstention.
        """
        if self.llm is None or not getattr(self.llm, "available", False):
            return None
        memory = self.client.load_memory(dataset_id)
        canonical = sorted(self.dictionary.item_synonyms)
        labels = sorted(self._base_labels(memory["latest_objects"]))
        rooms = sorted(
            {
                str(room.get("label", "")).strip().lower()
                for room in memory["rooms"]
                if room.get("label")
            }
        )
        context = {
            "canonical_items": canonical,
            "tracked_labels": labels,
            "rooms": rooms,
        }
        messages = [
            {"role": "system", "content": LLM_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {"question": query, "memory": context}, ensure_ascii=True
                ),
            },
        ]
        try:
            decision = self.llm.chat_json(messages, max_tokens=200)
        except LLMError as exc:
            self.last_llm_error = str(exc)
            return None
        self.last_llm_error = None
        validated = self._validate_llm_decision(decision, canonical, labels, rooms)
        # Small models sometimes copy a room out of the memory context even
        # when the user never named one. Only keep a room constraint that is
        # actually present in the question.
        if validated and validated.get("room"):
            room_key = str(validated["room"]).lower().replace("#", "").strip()
            if room_key and room_key not in query.lower().replace("#", ""):
                validated["room"] = None
        return validated

    @staticmethod
    def _base_labels(latest_objects: list[dict[str, Any]]) -> set[str]:
        labels: set[str] = set()
        for obj in latest_objects:
            label = str(obj.get("label", "")).lower()
            base = label.split("#")[0].split("[")[0].strip()
            if base:
                labels.add(base)
        return labels

    @staticmethod
    def _validate_llm_decision(
        decision: dict[str, Any],
        canonical: list[str],
        labels: list[str],
        rooms: list[str],
    ) -> dict[str, Any] | None:
        """Reject anything the memory/dictionary cannot ground."""
        intent = str(decision.get("intent", "")).strip().lower()
        raw_item = decision.get("item")
        raw_room = decision.get("room")
        item = str(raw_item).strip().lower() if raw_item else None
        room = str(raw_room).strip().lower() if raw_room else None

        if item:
            item = HybridNLQEngine._canonicalise_llm_item(item, canonical, labels)
        if room and room not in rooms:
            room = None
        if intent not in {"locate", "temporal", "activity"}:
            return None
        if intent == "locate" and not item:
            return None
        return {"intent": intent, "item": item, "room": room}

    @staticmethod
    def _canonicalise_llm_item(
        item: str, canonical: list[str], labels: list[str]
    ) -> str | None:
        if item in canonical:
            return item
        # Light singular/plural normalisation before giving up.
        for variant in (f"{item}s", item[:-1] if item.endswith("s") else ""):
            if variant and variant in canonical:
                return variant
        for label in labels:
            if item == label or re.search(r"\b" + re.escape(item) + r"\b", label):
                return label
        return None

    # ------------------------------------------------------------------
    # Abstentions (invariant: no evidence -> explicit uncertainty)
    # ------------------------------------------------------------------
    def _abstain_unknown_item(self, query: str, slots: Slots) -> AskResult:
        raw = slots.item_raw or query.strip().lower()
        suggestions = self.dictionary.suggestions_for(raw)
        text = f"I'm not sure what '{raw}' is."
        if suggestions:
            text += f" Did you mean: {', '.join(suggestions)}?"
        else:
            text += " Say it differently, or ask a caregiver to name it."
        return AskResult(
            query=query,
            intent=Intent.LOCATE,
            abstained=True,
            abstain_reason="item_not_in_dictionary",
            item=raw,
            suggestions=suggestions,
            answer_text=text,
        )

    def _abstain_no_match(
        self, query: str, slots: Slots, memory: dict[str, Any]
    ) -> AskResult:
        # TODO(NLQ M3.4): distinguish "never observed" from "stale" here.
        bases = sorted(
            {
                str(obj.get("label", "")).split("#")[0].split("[")[0].strip().lower()
                for obj in memory["latest_objects"]
                if obj.get("label")
            }
            - {""}
        )
        hint = f" I do remember {', '.join(bases[:3])}." if bases else ""
        return AskResult(
            query=query,
            intent=Intent.LOCATE,
            found=False,
            abstained=True,
            item=slots.item,
            abstain_reason="not_observed_in_memory",
            answer_text=f"I couldn't find your {slots.item} in this memory.{hint}",
        )

    # ------------------------------------------------------------------
    # Matching, ranking, composition
    # ------------------------------------------------------------------
    def _match_instances(
        self, canonical_item: str, latest_objects: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Match latest states against one dictionary item.

        TODO(NLQ): parity-check with ``aegis.remote.api._matches_query``;
        union both matchers when porting the dictionary to deployment scale.
        """
        canon = canonical_item.lower()
        synonyms = [canon, *self.dictionary.item_synonyms.get(canon, [])]
        matches = []
        for obj in latest_objects:
            label = str(obj.get("label", "")).lower()
            base = label.split("#")[0].split("[")[0].strip()
            if any(synonym == base or synonym in label for synonym in synonyms):
                matches.append(obj)
        return matches

    def _rank_matches(
        self, canonical_item: str, matches: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Exact label > currently-active pair > most recent observation."""

        def sort_key(obj: dict[str, Any]) -> tuple[int, int, float]:
            label = str(obj.get("label", "")).lower()
            exact = 1 if canonical_item.lower() in label else 0
            is_active = 1 if "active" in label else 0
            timestamp = float(obj.get("last_seen_timestamp", 0.0))
            return exact, is_active, timestamp

        return sorted(matches, key=sort_key, reverse=True)

    def _compose_statement(self, item: str, state: dict[str, Any]) -> str:
        """Grounded <= 2-sentence template (mirrors reasoning.py tone)."""
        is_plural = item in PLURAL_ITEMS or (
            item.endswith("s") and not item.endswith("ss")
        )
        is_are = "are" if is_plural else "is"
        them_it = "them" if is_plural else "it"
        anchor = str(state.get("anchor_label", "your usual spot"))
        relation = str(state.get("relation", "near"))
        in_hand = bool(state.get("is_in_hand")) or relation == IN_HAND_RELATION
        clause = self._room_clause(state.get("room_label"), anchor)

        if in_hand:
            statement = f"Your {item} {is_are} in your hands right now."
        elif relation == "inside":
            statement = f"Your {item} {is_are} inside {anchor}{clause}."
        elif relation == "on_surface":
            statement = f"Your {item} {is_are} sitting on {anchor}{clause}."
        elif relation == "on_floor":
            statement = f"Your {item} {is_are} on the floor near {anchor}."
        else:
            statement = f"Your {item} {is_are} near {anchor}{clause}."

        if not state.get("is_active_view", True) and not in_hand:
            statement += f" Aegis remembers {them_it} there, even out of direct view."
        return statement

    @staticmethod
    def _room_clause(room: Any, anchor: str) -> str:
        room_label = str(room) if room else ""
        if not room_label or room_label.lower() in anchor.lower():
            return ""
        if room_label.lower().startswith("room "):
            return f" in {room_label}"
        return f" in the {room_label}"
