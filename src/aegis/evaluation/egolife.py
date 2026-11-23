"""EgoLife 7-day memory evaluation: window selection and scoring (pure).

EgoLife stores one ~30 s clip per file, named ``DAY1_A1_JAKE_11094208.mp4``
(day, participant, HHMMSS, frame index), so a day window is a sorted slice of
clip names -- planning a run needs no video decoding.

The point of the protocol is *intervening observation*: each day contributes a
contiguous window, the windows are ingested in chronological order, and a query
on day N may only use what was ingested by day N. See
``scripts/egolife_eval.py`` for the runner and ``docs/egolife.md`` for the
protocol and its limits.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from aegis.core.timeutil import parse_iso
from aegis.evaluation.metrics import (
    ambiguity_f1,
    cue_filter_precision,
    evidence_crop_rate,
    false_confidence_rate,
    mrr,
    recall_at_k,
    reciprocal_rank,
    temporal_index_accuracy,
)
from aegis.memory.reasoning import QueryCues, parse_query_cues, rank_candidates

_CLIP = re.compile(r"^DAY(?P<day>\d+)_(?P<who>[A-Z0-9]+_[A-Z]+)_(?P<stamp>\d{8})\.mp4$")

# state_at() resolves the closest episode within this many seconds of the cue.
_T4_TOLERANCE_S = 180.0


@dataclass(frozen=True, slots=True)
class Clip:
    """One EgoLife clip: a relative path and its HHMMSS wall-clock stamp."""

    path: str
    stamp: str
    size_bytes: int = 0


@dataclass(frozen=True, slots=True)
class Query:
    """One frozen memory query and its expected answer."""

    id: str
    item: str
    asked_day: int
    asked_at: str | None = None
    expect_present: bool = True
    expect_room: str | None = None
    expect_anchor: str | None = None
    # Accepted anchor nouns, e.g. ("table", "desk"). Written from the caption
    # annotation, never from the system's own label, so scoring stays blind.
    expect_place: Sequence[str] | None = None
    # Caption timestamp that established the ground truth, for provenance.
    observed_at: str | None = None
    note: str | None = None
    # Optional tier metadata from the frozen sidecar. Legacy annotations keep
    # the T2 defaults, so old loaders and tests are unaffected.
    tier: str = "T2"
    cue_prompt: str | None = None
    ambiguity_expected: bool | None = None
    # T1 enrollment ground truth; T4 optional independent time window.
    t1_prompt: str | None = None
    t1_expected_instance_id: int | None = None
    expected_time_window: tuple[str, str] | None = None


def place_of(anchor_label: str | None) -> str | None:
    """``"Dining Table #3"`` -> ``"dining table"``."""

    if not anchor_label:
        return None
    return anchor_label.split("#")[0].strip().lower()


def parse_clip(path: str, size_bytes: int = 0) -> tuple[int, Clip] | None:
    """Return ``(day, clip)`` for an EgoLife clip path, else ``None``."""

    match = _CLIP.match(path.rsplit("/", 1)[-1])
    if match is None:
        return None
    return int(match["day"]), Clip(path, match["stamp"][:6], size_bytes)


def hhmmss_to_seconds(text: str) -> int:
    """``"11:30"`` or ``"11:30:00"`` -> seconds since midnight."""

    parts = [int(part) for part in text.split(":")]
    while len(parts) < 3:
        parts.append(0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def clip_second(clip: Clip) -> int:
    return hhmmss_to_seconds(f"{clip.stamp[:2]}:{clip.stamp[2:4]}:{clip.stamp[4:6]}")


def select_window(clips: Iterable[Clip], start: str, minutes: int) -> list[Clip]:
    """Clips starting inside ``[start, start + minutes)``, in time order."""

    low = hhmmss_to_seconds(start)
    high = low + minutes * 60
    return sorted(
        (c for c in clips if low <= clip_second(c) < high), key=lambda c: c.stamp
    )


def group_segments(
    clips: Sequence[Clip], start: str, segment_minutes: int, min_clips: int = 1
) -> list[list[Clip]]:
    """Split an ordered window into contiguous fixed-length buckets.

    Buckets with fewer than ``min_clips`` clips are dropped: a partial first
    bucket (EgoLife days start mid-bucket) reconstructs too few keyframes to
    give a trustworthy room.
    """

    low = hhmmss_to_seconds(start)
    width = segment_minutes * 60
    buckets: dict[int, list[Clip]] = {}
    for clip in clips:
        buckets.setdefault((clip_second(clip) - low) // width, []).append(clip)
    return [buckets[key] for key in sorted(buckets) if len(buckets[key]) >= min_clips]


def dataset_id(day: int, segment: int) -> str:
    """Stable dataset id for one segment; also the Modal Volume prefix."""

    return f"egolife_d{day}_s{segment:02d}"


def segment_start(day: int, first_stamp: str, base_date: str) -> datetime:
    """Wall clock of a segment's first clip. DAY1 begins at ``base_date``.

    The nominal bucket start is not used: a day's recording can begin mid
    bucket, and ``recorded_at`` is the clock of frame zero.
    """

    origin = datetime.fromisoformat(base_date).replace(tzinfo=UTC)
    seconds = hhmmss_to_seconds(
        f"{first_stamp[:2]}:{first_stamp[2:4]}:{first_stamp[4:6]}"
    )
    return origin + timedelta(days=day - 1, seconds=seconds)


def find_state(
    states: Iterable[dict[str, Any]], item: str, canonical: str | None = None
) -> dict[str, Any] | None:
    """Best latest-state row for a free-text item (most recently seen wins)."""

    text = item.strip().lower()
    hits = [
        state
        for state in states
        if (canonical and state.get("canonical") == canonical)
        or text in str(state.get("label", "")).lower()
    ]
    if not hits:
        return None
    return max(hits, key=lambda state: str(state.get("last_seen_wallclock") or ""))


def score_query(query: Query, state: dict[str, Any] | None) -> dict[str, Any]:
    """Score one query. ``state=None`` means the system found nothing."""

    result: dict[str, Any] = {
        "id": query.id,
        "item": query.item,
        "asked_day": query.asked_day,
        "found": state is not None,
    }
    if state is None:
        result.update(
            present_ok=not query.expect_present,
            room_ok=None,
            anchor_ok=None,
            place_ok=False if query.expect_place else None,
        )
        return result
    place = place_of(state.get("anchor_label"))
    result.update(
        present_ok=query.expect_present,
        room=state.get("room_label"),
        anchor=state.get("anchor_label"),
        place=place,
        last_seen=state.get("last_seen_wallclock"),
        room_ok=(
            None
            if query.expect_room is None
            else state.get("room_label") == query.expect_room
        ),
        anchor_ok=(
            None
            if query.expect_anchor is None
            else state.get("anchor_label") == query.expect_anchor
        ),
        place_ok=(
            None
            if query.expect_place is None
            else place is not None and any(noun in place for noun in query.expect_place)
        ),
    )
    return result


def summarise(scores: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-query scores into the headline rates."""

    def rate(key: str) -> dict[str, Any]:
        values = [bool(score[key]) for score in scores if score.get(key) is not None]
        correct = sum(values)
        return {
            "correct": correct,
            "n": len(values),
            "accuracy": round(correct / len(values), 4) if values else None,
        }

    return {
        "n": len(scores),
        "present": rate("present_ok"),
        "place": rate("place_ok"),
        "room": rate("room_ok"),
        "anchor": rate("anchor_ok"),
    }


def latest_recent_run(
    runs: Iterable[dict[str, Any]], cutoff_iso: str
) -> dict[str, Any] | None:
    """Newest state run ending at or after ``cutoff_iso``.

    Backs the "last 24 h only" ablation: same object identity, but evidence
    older than the cutoff is discarded. Fixed-format UTC text sorts as time.
    """

    recent = [run for run in runs if str(run.get("end_at", "")) >= cutoff_iso]
    return max(recent, key=lambda run: str(run["end_at"])) if recent else None


def snapshot(store: Any) -> dict[str, Any]:
    """Store size and anchor match quality at the end of a day."""

    anchors = [dict(row) for row in store.anchors()]
    quality: dict[str, int] = {}
    for anchor in anchors:
        key = str(anchor["match_quality"])
        quality[key] = quality.get(key, 0) + 1
    return {
        "counts": store.counts(),
        "anchor_match_quality": quality,
        "rooms": [row["label"] for row in store.rooms()],
    }


def recent_state(
    store: Any, state: dict[str, Any], cutoff_iso: str
) -> dict[str, Any] | None:
    """The same object, but only using evidence from the last ``cutoff`` window."""

    runs = [dict(row) for row in store.runs_for_instance(state["instance_id"])]
    run = latest_recent_run(runs, cutoff_iso)
    if run is None:
        return None
    anchors = {row["anchor_id"]: row["label"] for row in store.anchors()}
    rooms = {row["room_id"]: row["label"] for row in store.rooms()}
    return {
        **state,
        "anchor_label": anchors.get(run.get("anchor_id")),
        "room_label": rooms.get(run.get("room_id")),
        "last_seen_wallclock": run.get("end_at"),
    }


def score_bank(store: Any, queries: Sequence[Query], vocabulary: Any) -> dict[str, Any]:
    """Score every query twice: full history, and the last 24 hours only."""

    states = store.latest_states()
    full: list[dict[str, Any]] = []
    recent: list[dict[str, Any]] = []
    for query in queries:
        entry = vocabulary.resolve_query(query.item) if vocabulary else None
        canonical = entry.id if entry else None
        state = find_state(states, query.item, canonical)
        full.append(score_query(query, state))
        if state is None or not query.asked_at:
            recent.append(score_query(query, None))
            continue
        cutoff = (parse_iso(query.asked_at) - timedelta(hours=24)).isoformat()
        recent.append(score_query(query, recent_state(store, state, cutoff)))
    return {"full": full, "last_24h": recent}


# ---------------------------------------------------------------------------
# Tiered, as-of scoring with candidate-aware answers
# ---------------------------------------------------------------------------


def load_tier_sidecar(path: str | Path, bank_path: str | Path) -> dict[str, Any]:
    """Load the frozen tier annotations, refusing a mutated query bank."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    expected = payload.get("bank_sha256")
    if expected:
        actual = hashlib.sha256(Path(bank_path).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(
                "tier sidecar was annotated against a different query bank; "
                f"expected {expected}, got {actual}"
            )
    return payload


def apply_tier_annotations(
    queries: Sequence[Query], sidecar: dict[str, Any]
) -> list[Query]:
    """Expand the frozen bank into non-overlapping T1–T4 rows using the sidecar.

    The bank stays a set of class-level T2 questions.  The sidecar adds an
    independent ambiguity label, optional enrollment ground truth (T1), and
    mechanically derived fuzzy-time (T3) and exact-timestamp (T4) variants, so
    no tier's ground truth is written into the bank file itself.
    """

    annotations = sidecar.get("annotations", {})
    expanded: list[Query] = []
    for query in queries:
        annotation = annotations.get(query.id, {})
        if str(annotation.get("tier", "")).upper().startswith("T1"):
            expanded.append(
                replace(
                    query,
                    id=f"{query.id}__t1",
                    tier="T1",
                    t1_prompt=annotation.get("t1_prompt"),
                    t1_expected_instance_id=annotation.get("t1_expected_instance_id"),
                )
            )
            continue
        expanded.append(
            replace(
                query,
                tier="T2",
                ambiguity_expected=annotation.get(
                    "ambiguity_expected", query.ambiguity_expected
                ),
            )
        )
        cue_prompt = annotation.get("t3_prompt")
        if cue_prompt:
            expanded.append(
                replace(
                    query,
                    id=f"{query.id}__t3",
                    tier="T3",
                    cue_prompt=cue_prompt,
                    ambiguity_expected=None,
                )
            )
        if annotation.get("t4_prompt") and query.observed_at:
            expanded.append(
                replace(
                    query,
                    id=f"{query.id}__t4",
                    tier="T4",
                    ambiguity_expected=None,
                    expected_time_window=(
                        tuple(annotation["expected_time_window"])
                        if annotation.get("expected_time_window")
                        else None
                    ),
                )
            )
    return expanded


def _cues_match_state(state: dict[str, Any], cues: QueryCues | None) -> bool:
    """Whether a state's most recent move falls in a fuzzy time window."""

    if not cues or not cues.window_start or not cues.window_end:
        return True
    stamp = state.get("last_moved_wallclock") or state.get("last_seen_wallclock")
    if not stamp:
        return False
    text = str(stamp)
    return cues.window_start <= text < cues.window_end


def _state_matches_place(state: dict[str, Any], expected: Sequence[str]) -> bool:
    """Whether a retained state's place matches the annotated ground truth."""

    place = place_of(state.get("anchor_label")) or ""
    room = str(state.get("room_label") or "").lower()
    return any(noun in place or noun in room for noun in expected)


def _place_candidates(candidates: Sequence[dict[str, Any]]) -> list[str]:
    return [
        place_of(candidate.get("anchor_label"))
        or str(candidate.get("room_label") or "").lower().strip()
        for candidate in candidates
    ]


def _score_ranked_query(
    query: Query,
    states: Sequence[dict[str, Any]],
    vocabulary: Any,
    *,
    mode: str,
    now: datetime | None,
    personal_ids: Sequence[int],
) -> dict[str, Any]:
    """Score one T2/T3 query with the production ranker."""

    prompt = query.cue_prompt if query.tier == "T3" and query.cue_prompt else query.item
    cues = parse_query_cues(prompt, now=now)
    in_window = [state for state in states if _cues_match_state(state, cues)]
    # A cue with no matching evidence falls back to the full snapshot rather
    # than manufacturing a "not found" from missing event data.
    effective_states = in_window or list(states)
    entry = vocabulary.resolve_query(query.item) if vocabulary else None
    target = entry.id if entry else query.item
    ranking = rank_candidates(
        effective_states,
        target,
        mode=mode,
        now=now,
        cues=cues,
        personal_ids=personal_ids,
    )
    candidates = ranking["candidates"]
    places = _place_candidates(candidates)
    expected = list(query.expect_place or [])
    top1_correct = bool(candidates) and any(noun in places[0] for noun in expected)
    crop_rate = evidence_crop_rate(candidates)
    has_window = bool(cues.window_start and cues.window_end)
    precision = (
        round(
            sum(_state_matches_place(s, expected) for s in in_window) / len(in_window),
            4,
        )
        if has_window and in_window and expected
        else None
    )
    return {
        "id": query.id,
        "item": query.item,
        "tier": query.tier,
        "prompt": prompt,
        "asked_at": query.asked_at,
        "resolution_mode": ranking["resolution_mode"],
        "is_ambiguous": ranking["is_ambiguous"],
        "ambiguity_reason": ranking["ambiguity_reason"],
        "ambiguity_expected": query.ambiguity_expected,
        "candidates": candidates,
        "found": bool(candidates),
        "present_ok": bool(candidates) == query.expect_present,
        "top1_correct": top1_correct,
        "top1_place": places[0] if places else None,
        "recall_at_3": recall_at_k(places, expected, k=3),
        "mrr": reciprocal_rank(places, expected),
        "crop_rate": crop_rate,
        "cue_filter_precision": precision,
    }


def _score_oracle_query(query: Query, store: Any, vocabulary: Any) -> dict[str, Any]:
    """T4: resolve the exact placement time without using its expected place."""

    entry = vocabulary.resolve_query(query.item) if vocabulary else None
    target = entry.id if entry else query.item
    state = store.state_at(target, query.observed_at) if query.observed_at else None
    if state is None:
        return {
            "id": query.id,
            "item": query.item,
            "tier": "T4",
            "prompt": f"Where was the {query.item} at {query.observed_at}?",
            "resolution_mode": "not_found",
            "found": False,
            "present_ok": not query.expect_present,
            "top1_correct": False,
            "top1_place": None,
            "delta_seconds": None,
            "temporal_ok": False,
        }
    place = place_of(state.get("anchor_label"))
    expected = list(query.expect_place or [])
    delta = state.get("delta_seconds")
    temporal_ok = None if delta is None else abs(float(delta)) <= _T4_TOLERANCE_S
    if query.expected_time_window:
        stamp = str(state.get("last_seen_wallclock") or "")
        low, high = query.expected_time_window
        temporal_ok = bool(stamp and low <= stamp < high)
    return {
        "id": query.id,
        "item": query.item,
        "tier": "T4",
        "prompt": f"Where was the {query.item} at {query.observed_at}?",
        "resolution_mode": "direct",
        "is_ambiguous": False,
        "found": True,
        "present_ok": query.expect_present,
        "top1_correct": any(noun in place for noun in expected) if place else False,
        "top1_place": place,
        "top1_instance": state.get("label"),
        "delta_seconds": state.get("delta_seconds"),
        "temporal_ok": temporal_ok,
    }


def _score_enrolled_query(
    query: Query,
    states: Sequence[dict[str, Any]],
    vocabulary: Any,
    *,
    mode: str,
    now: datetime | None,
    personal_ids: Sequence[int],
) -> dict[str, Any]:
    """T1: the enrolled personal instance must be the top-ranked answer."""

    entry = vocabulary.resolve_query(query.item) if vocabulary else None
    target = entry.id if entry else query.item
    prompt = query.t1_prompt or query.item
    ranking = rank_candidates(
        states,
        target,
        mode=mode,
        now=now,
        cues=parse_query_cues(prompt, now=now),
        personal_ids=personal_ids,
    )
    candidates = ranking["candidates"]
    primary = candidates[0] if candidates else None
    expected = query.t1_expected_instance_id
    return {
        "id": query.id,
        "item": query.item,
        "tier": "T1",
        "prompt": prompt,
        "resolution_mode": ranking["resolution_mode"],
        "is_ambiguous": ranking["is_ambiguous"],
        "found": primary is not None,
        "present_ok": (primary is not None) == query.expect_present,
        "top1_correct": bool(
            primary and expected is not None and primary["instance_id"] == expected
        ),
        "top1_instance": primary["label"] if primary else None,
        "expected_instance_id": expected,
        "enrolled": expected in personal_ids,
        "candidates": candidates,
        "crop_rate": evidence_crop_rate(candidates),
    }


def _snapshot(
    query: Query, store: Any, legacy_24h: bool
) -> tuple[list[dict[str, Any]], datetime | None]:
    if query.asked_at:
        since = None
        if legacy_24h:
            since = (parse_iso(query.asked_at) - timedelta(hours=24)).isoformat()
        return store.states_as_of(query.asked_at, since=since), parse_iso(
            query.asked_at
        )
    return store.latest_states(), None


def score_tiered_bank(
    store: Any,
    queries: Sequence[Query],
    vocabulary: Any,
    *,
    mode: str = "full",
    personal_ids: Sequence[int] = (),
    legacy_24h: bool = False,
) -> dict[str, Any]:
    """Score T1–T4 as of each query's ``asked_at``.

    T1 needs an enrolled instance id in the annotation; without it the query is
    NOT RUN rather than a silent zero. ``legacy_24h`` replaces the snapshot with
    a real recency-limited one: every instance whose evidence ended before
    ``asked_at - 24 h`` is removed, so the ranker can choose differently.
    """

    results: dict[str, list[dict[str, Any]]] = {"T1": [], "T2": [], "T3": [], "T4": []}
    for query in queries:
        if query.tier == "T4":
            results["T4"].append(_score_oracle_query(query, store, vocabulary))
            continue
        if query.tier == "T1":
            if query.t1_expected_instance_id is None:
                continue
            states, now = _snapshot(query, store, legacy_24h)
            results["T1"].append(
                _score_enrolled_query(
                    query,
                    states,
                    vocabulary,
                    mode=mode,
                    now=now,
                    personal_ids=personal_ids,
                )
            )
            continue
        if query.tier not in {"T2", "T3"}:
            continue
        states, now = _snapshot(query, store, legacy_24h)
        results[query.tier].append(
            _score_ranked_query(
                query,
                states,
                vocabulary,
                mode=mode,
                now=now,
                personal_ids=personal_ids,
            )
        )
    return results


def summarise_tier(results: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate one tier's candidate metrics, marking unmeasured items."""

    def rate(key: str) -> dict[str, Any]:
        values = [bool(item[key]) for item in results if item.get(key) is not None]
        correct = sum(values)
        return {
            "correct": correct,
            "n": len(values),
            "accuracy": round(correct / len(values), 4) if values else None,
        }

    def mean(key: str) -> float | None:
        values = [float(item[key]) for item in results if item.get(key) is not None]
        return round(sum(values) / len(values), 4) if values else None

    expected = [item.get("ambiguity_expected") for item in results]
    predicted = [item.get("is_ambiguous") for item in results]
    if any(value is not None for value in expected) and all(
        value is not None for value in predicted
    ):
        ambiguity = ambiguity_f1(
            [bool(value) for value in expected], [bool(value) for value in predicted]
        )
    else:
        ambiguity = "NOT RUN: no independent ambiguity labels"

    if any(item.get("resolution_mode") == "direct" for item in results):
        false_confidence = false_confidence_rate(results)
    else:
        false_confidence = "NOT RUN: no direct answers"

    return {
        "n": len(results),
        "present": rate("present_ok"),
        "top1": rate("top1_correct"),
        "recall_at_3": mean("recall_at_3"),
        "mrr": mrr(results),
        "ambiguity_f1": ambiguity,
        "false_confidence": false_confidence,
        "crop_rate": mean("crop_rate"),
        "cue_filter_precision": cue_filter_precision(results),
        "temporal_index": temporal_index_accuracy(results),
        "direct": flag_direct(results),
    }


def flag_direct(results: Sequence[dict[str, Any]]) -> dict[str, int]:
    """Count answer modes so a report can show abstention and triage rates."""

    counts: dict[str, int] = {}
    for item in results:
        mode = str(item.get("resolution_mode") or "unknown")
        counts[mode] = counts.get(mode, 0) + 1
    return counts
