"""Personal-object registry: the instances a patient calls "mine".

Caregivers enroll an existing instance id and may attach the alias the patient
actually uses, its vocabulary class, where it usually lives, and a reference
crop.  Records live in the home store's ``meta`` table, so no schema change is
needed.  The original list-of-ids format still loads; enrollment rewrites it as
a keyed record.  Enrollment by instance id is invalidated by a full store
re-ingest, which is the accepted limit until a patient-facing flow exists.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

PERSONAL_ITEMS_KEY = "personal_items"

_DETAIL_FIELDS = frozenset(
    {"alias", "canonical_class", "usual_anchor", "usual_room", "visual_crop"}
)


@dataclass(frozen=True, slots=True)
class PersonalItem:
    """One enrolled personal object and the cues a caregiver attached to it."""

    instance_id: int
    alias: str | None = None
    canonical_class: str | None = None
    usual_anchor: str | None = None
    usual_room: str | None = None
    visual_crop: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            **{
                name: getattr(self, name)
                for name in sorted(_DETAIL_FIELDS)
                if getattr(self, name) is not None
            },
        }


def _read_raw(store: Any) -> Any:
    row = store.one("SELECT value FROM meta WHERE key = ?", (PERSONAL_ITEMS_KEY,))
    if row is None:
        return []
    try:
        return json.loads(row["value"])
    except (TypeError, ValueError):
        return []


def enrolled_items(store: Any) -> list[PersonalItem]:
    """Enrolled items for this home; malformed data means none."""

    raw = _read_raw(store)
    items: list[PersonalItem] = []
    if isinstance(raw, dict):
        for key, value in raw.items():
            try:
                instance_id = int(key)
            except (TypeError, ValueError):
                continue
            details = value if isinstance(value, dict) else {}
            items.append(
                PersonalItem(
                    instance_id=instance_id,
                    **{
                        name: details[name]
                        for name in _DETAIL_FIELDS
                        if details.get(name) is not None
                    },
                )
            )
    elif isinstance(raw, list):
        for value in raw:
            try:
                items.append(PersonalItem(int(value)))
            except (TypeError, ValueError):
                continue
    return sorted(items, key=lambda item: item.instance_id)


def enrolled_instances(store: Any) -> list[int]:
    """Enrolled instance ids for this home."""

    return [item.instance_id for item in enrolled_items(store)]


def enroll(
    store: Any,
    instance_id: int,
    *,
    alias: str | None = None,
    canonical_class: str | None = None,
    usual_anchor: str | None = None,
    usual_room: str | None = None,
    visual_crop: str | None = None,
) -> list[PersonalItem]:
    """Add or update one enrolled instance and return the registry."""

    row = store.one(
        "SELECT canonical FROM instance WHERE instance_id = ?", (instance_id,)
    )
    if row is None:
        raise ValueError(f"no instance {instance_id} in {store.home_id}")
    existing = {item.instance_id: item for item in enrolled_items(store)}
    previous = existing.get(instance_id, PersonalItem(instance_id=instance_id))
    updates = {
        "alias": alias,
        "canonical_class": canonical_class or row["canonical"],
        "usual_anchor": usual_anchor,
        "usual_room": usual_room,
        "visual_crop": visual_crop,
    }
    existing[instance_id] = PersonalItem(
        instance_id=instance_id,
        **{
            name: value if value is not None else getattr(previous, name)
            for name, value in updates.items()
        },
    )
    payload = {str(key): item.as_dict() for key, item in sorted(existing.items())}
    store.execute(
        "INSERT INTO meta(key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (PERSONAL_ITEMS_KEY, json.dumps(payload)),
    )
    return enrolled_items(store)


def _normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()


def aliases(store: Any) -> list[tuple[str, int]]:
    """Normalised alias -> instance id, longest alias first."""

    pairs = [
        (_normalise(item.alias), item.instance_id)
        for item in enrolled_items(store)
        if item.alias
    ]
    return sorted(
        ((phrase, instance_id) for phrase, instance_id in pairs if phrase),
        key=lambda pair: -len(pair[0]),
    )


def resolve_alias(store: Any, query: str) -> int | None:
    """Instance id named by a patient's alias ("dad's cup"), if any."""

    text = f" {_normalise(query)} "
    for phrase, instance_id in aliases(store):
        if re.search(rf"\b{re.escape(phrase)}\b", text):
            return instance_id
    return None


def personal_ids_for_query(
    store: Any, query: str, canonical: str | None = None
) -> list[int]:
    """Instances a query refers to, by alias or by enrolled class."""

    matched = resolve_alias(store, query)
    ids = {matched} if matched is not None else set()
    if canonical:
        ids.update(
            item.instance_id
            for item in enrolled_items(store)
            if item.canonical_class == canonical
        )
    return sorted(ids)
