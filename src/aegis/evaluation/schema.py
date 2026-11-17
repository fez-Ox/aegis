"""Typed records used by the Aegis evaluation harness.

The harness deliberately keeps the on-disk schemas small and human-editable.
These dataclasses are the single in-process representation so every metric
reader agrees on defaults and normalisation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Detection:
    """One 2D object observation in one annotated frame."""

    frame_id: int
    label: str
    bbox: tuple[float, float, float, float]
    instance_id: int | None = None
    confidence: float = 1.0
    mask_path: str | None = None
    visibility: str = "visible"
    occluded: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Event:
    """A pick-up, placement, state change, or room change."""

    event_type: str
    start_time: float
    end_time: float
    object_label: str | None = None
    instance_id: int | None = None
    source_anchor: str | None = None
    destination_anchor: str | None = None
    source_room: str | None = None
    destination_room: str | None = None
    event_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class QuerySpec:
    """One question in the held-out question bank."""

    query_id: str
    query: str
    expected_found: bool = True
    expected_anchor: str | None = None
    expected_room: str | None = None
    expected_relation: str | None = None
    expected_instance_label: str | None = None
    negative: bool = False
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class PersistenceCase:
    """A labelled occlusion or relocation case for object permanence."""

    case_id: str
    query: str
    expected_instance_id: int | None = None
    expected_label: str | None = None
    expected_anchor: str | None = None
    expected_room: str | None = None
    expected_relation: str | None = None
    check_frame: int | None = None
    occlusion_start: float | None = None
    occlusion_end: float | None = None
    expect_persistent: bool = False
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class Measurement:
    """One hand-measured object in the controlled-room experiment."""

    object_id: str
    label: str
    x: float
    y: float
    z: float
    room: str | None = None
    anchor: str | None = None
    relation: str | None = None
    size_x: float | None = None
    size_y: float | None = None
    size_z: float | None = None
    predicted_instance_id: int | None = None
    frame_id: int | None = None
    notes: str | None = None

    @property
    def center(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)
