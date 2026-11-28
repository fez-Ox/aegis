"""UTC timestamp helpers with one fixed text format.

Every stored wall-clock value uses ``YYYY-MM-DDTHH:MM:SS.ffffff+00:00`` so
that string comparison is chronological (used by SQLite queries).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


def parse_iso(value: str) -> datetime:
    """Parse an ISO-8601 timestamp that carries a timezone."""

    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp has no timezone: {value!r}")
    return parsed


def to_utc_iso(value: datetime | str) -> str:
    """Normalise a datetime (or ISO string) to the fixed UTC text format."""

    moment = parse_iso(value) if isinstance(value, str) else value
    if moment.tzinfo is None:
        raise ValueError("datetime has no timezone")
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")


def shift_iso(value: str, seconds: float) -> str:
    """Return ``value + seconds`` in the fixed UTC format."""

    return to_utc_iso(parse_iso(value) + timedelta(seconds=float(seconds)))


def utc_now() -> datetime:
    return datetime.now(UTC)


def time_ago(value: str | datetime | None, now: datetime | None = None) -> str | None:
    """Plain-language freshness from a wall-clock timestamp.

    Buckets are generic and conservative: an uncertain or missing timestamp
    yields ``None`` rather than a fabricated "just now". Future timestamps
    (clock skew) are clamped to "just now".
    """
    if value is None:
        return None
    try:
        seen = parse_iso(str(value)) if isinstance(value, str) else value
    except ValueError:
        return None
    if seen.tzinfo is None:
        return None
    moment = now or utc_now()
    seconds = (moment - seen).total_seconds()
    if seconds < 120:
        return "just now"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes} minutes ago"
    hours = int(seconds // 3600)
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = int(seconds // 86400)
    if days == 1:
        return "yesterday"
    if days < 7:
        return f"{days} days ago"
    return "over a week ago"
