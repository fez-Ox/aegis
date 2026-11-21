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

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from aegis.core.timeutil import parse_iso

_CLIP = re.compile(r"^DAY(?P<day>\d+)_(?P<who>[A-Z0-9]+_[A-Z]+)_(?P<stamp>\d{8})\.mp4$")


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
