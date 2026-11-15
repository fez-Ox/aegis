"""Session-level instance association: which boxes are the same object.

The same rules apply to every object class. Evidence, in order: the
detector's track id, 3D proximity and appearance, and finally a relocation
rule when only one object of that class is known.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from aegis.core.config import MemoryBuildConfig
from aegis.core.models import BoundingBox3D
from aegis.core.vocabulary import Vocabulary


@dataclass
class InstanceTrack:
    instance_id: int
    canonical: str
    display_name: str
    center: tuple[float, float, float]
    track_id: int
    appearance: tuple[float, ...] | None
    count: int
    last_frame: int


def appearance_distance(
    first: tuple[float, ...] | None,
    second: tuple[float, ...] | None,
) -> float | None:
    """Half L1 distance between normalised histograms (0 = identical)."""

    if first is None or second is None or len(first) != len(second):
        return None
    return float(0.5 * sum(abs(a - b) for a, b in zip(first, second, strict=True)))


def associate_instances(
    boxes: Sequence[BoundingBox3D],
    *,
    vocabulary: Vocabulary,
    unit: float = 1.0,
    settings: MemoryBuildConfig | None = None,
) -> tuple[dict[int, int], dict[int, InstanceTrack]]:
    """Assign a session instance id to every object box.

    Returns ``(box_index -> instance_id, instance_id -> InstanceTrack)``.
    Two boxes of one frame never share an instance.
    """

    config = settings or MemoryBuildConfig()
    radius = config.association_radius * unit
    order = sorted(
        range(len(boxes)),
        key=lambda i: (boxes[i].timestamp, boxes[i].frame_id, -boxes[i].confidence),
    )
    assignment: dict[int, int] = {}
    instances: dict[int, InstanceTrack] = {}
    used_in_frame: dict[int, set[int]] = {}

    for index in order:
        box = boxes[index]
        canonical = vocabulary.canonical(box.label)
        taken = used_in_frame.setdefault(box.frame_id, set())
        candidates = [
            track
            for track in instances.values()
            if track.canonical == canonical and track.instance_id not in taken
        ]
        center = np.asarray(box.center, dtype=np.float64)

        chosen: InstanceTrack | None = next(
            (t for t in candidates if t.track_id == box.track_id), None
        )
        if chosen is None:
            scored: list[tuple[float, int, InstanceTrack]] = []
            for track in candidates:
                distance = float(np.linalg.norm(center - np.asarray(track.center)))
                look = appearance_distance(track.appearance, box.appearance)
                if distance <= radius or (
                    look is not None and look <= config.appearance_threshold
                ):
                    score = min(distance / radius, 2.0) + (look or 0.0)
                    scored.append((score, track.instance_id, track))
            if scored:
                chosen = min(scored, key=lambda item: (item[0], item[1]))[2]
        if chosen is None:
            same_class = [t for t in instances.values() if t.canonical == canonical]
            if len(same_class) == 1 and same_class[0].instance_id not in taken:
                chosen = same_class[0]

        if chosen is None:
            instance_id = max(instances, default=0) + 1
            chosen = InstanceTrack(
                instance_id=instance_id,
                canonical=canonical,
                display_name=f"{vocabulary.display(canonical)} #{instance_id}",
                center=tuple(float(v) for v in box.center),
                track_id=box.track_id,
                appearance=box.appearance,
                count=0,
                last_frame=box.frame_id,
            )
            instances[instance_id] = chosen

        chosen.center = tuple(float(v) for v in box.center)
        chosen.track_id = box.track_id
        if box.appearance is not None:
            chosen.appearance = box.appearance
        chosen.count += 1
        chosen.last_frame = box.frame_id
        taken.add(chosen.instance_id)
        assignment[index] = chosen.instance_id
    return assignment, instances
