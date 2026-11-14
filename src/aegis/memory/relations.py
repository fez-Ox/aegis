"""Object-to-anchor spatial relations in the gravity frame.

An object's relation to furniture is decided from two things only:

* how much of the object's floor-plane footprint lies over the anchor's
  footprint, and
* the vertical order of the object's bottom/top and the anchor's support
  surface, bottom and top (elevations along the session's up vector).

Tolerances are relative to object and anchor size, so they do not depend
on the uncalibrated reconstruction scale. When the gravity frame is not
reliable, vertical claims (under, above, on the floor) are not made.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from aegis.core.models import BoundingBox3D
from aegis.geometry.gravity import GravityFrame
from aegis.geometry.planar import (
    centroid,
    distance_point_to_polygon,
    oriented_rectangle,
    overlap_fraction,
    polygon_area,
)

RELATIONS = (
    "inside",
    "on_surface",
    "under",
    "above",
    "next_to",
    "on_floor",
    "near",
    "in_room",
    "carried_by_user",
)
PLACED_RELATIONS = frozenset(
    {"inside", "on_surface", "under", "above", "next_to", "on_floor", "near", "in_room"}
)
VERTICAL_RELATIONS = frozenset({"under", "above", "on_floor"})


@dataclass(frozen=True, slots=True)
class Footprint3D:
    """A floor-plane polygon plus a vertical extent (elevations)."""

    polygon: tuple[tuple[float, float], ...]
    up_min: float
    up_max: float
    support_up: float | None = None


@dataclass(frozen=True, slots=True)
class AnchorShape:
    anchor_id: int
    footprint: Footprint3D
    container: bool = False
    support_surface: bool = False
    open_underneath: bool = False


@dataclass(frozen=True, slots=True)
class RelationResult:
    relation: str
    anchor_id: int | None
    certain: bool
    overlap: float = 0.0
    gap: float = math.inf


def box_footprint(box: BoundingBox3D, gravity: GravityFrame) -> Footprint3D:
    """Footprint of a gravity-aligned box (see :class:`BoundingBox3D`)."""

    center = gravity.horizontal(box.center)
    polygon = oriented_rectangle(center, box.size[0], box.size[1], box.yaw or 0.0)
    if box.up_min is not None and box.up_max is not None:
        up_min, up_max = float(box.up_min), float(box.up_max)
    else:
        elevation = gravity.elevation(box.center)
        up_min = elevation - box.size[2] / 2.0
        up_max = elevation + box.size[2] / 2.0
    return Footprint3D(
        polygon=tuple(polygon),
        up_min=up_min,
        up_max=up_max,
        support_up=box.support_up,
    )


_PRIORITY = {
    ("inside", True): 6,
    ("on_surface", True): 6,
    ("under", True): 5,
    ("on_floor", True): 4,
    ("next_to", True): 3,
    ("above", True): 2,
    ("on_surface", False): 2,
    ("near", False): 1,
}


def _over_anchor(obj: Footprint3D, anchor: AnchorShape, tol: float) -> tuple[str, bool]:
    """Relation of an object whose footprint lies mostly over ``anchor``."""

    a = anchor.footprint
    middle = 0.5 * (obj.up_min + obj.up_max)
    surface = a.support_up if a.support_up is not None else a.up_max
    if obj.up_min > a.up_max + tol:
        return "above", True
    if anchor.container:
        if middle > a.up_max:
            return "on_surface", True
        if a.up_min - tol <= middle <= a.up_max:
            return "inside", True
        return "near", False
    if abs(obj.up_min - surface) <= tol:
        return "on_surface", True
    if obj.up_min > surface + tol:
        return "on_surface", False
    if anchor.open_underneath and obj.up_max <= surface - tol:
        return "under", True
    return "near", False


def classify_relation(
    obj: Footprint3D,
    anchors: Sequence[AnchorShape],
    gravity: GravityFrame,
    *,
    min_gravity_confidence: float = 0.5,
    vertical_tolerance: float = 0.15,
    overlap_threshold: float = 0.5,
    floor_tolerance_fraction: float = 0.06,
) -> RelationResult:
    """Classify the relation of one object to the surrounding anchors."""

    height = max(obj.up_max - obj.up_min, 1e-6)
    reliable = gravity.is_reliable(min_gravity_confidence)
    if gravity.camera_height is not None and gravity.camera_height > 0:
        floor_tol = floor_tolerance_fraction * gravity.camera_height
    else:
        floor_tol = 0.5 * height
    on_floor = (
        reliable
        and gravity.floor_offset is not None
        and (obj.up_min - gravity.floor_offset) <= floor_tol
    )
    centre = centroid(obj.polygon)

    candidates: list[tuple[int, float, float, RelationResult]] = []
    nearest: tuple[float, float, AnchorShape] | None = None
    for anchor in anchors:
        a = anchor.footprint
        overlap = overlap_fraction(obj.polygon, a.polygon)
        gap = distance_point_to_polygon(centre, a.polygon)
        span = max(a.up_max - a.up_min, 1e-6)
        tol = vertical_tolerance * max(span, height)
        reach = 0.5 * math.sqrt(max(polygon_area(a.polygon), 0.0))
        if nearest is None or gap < nearest[0]:
            nearest = (gap, reach, anchor)

        if overlap >= overlap_threshold:
            relation, certain = _over_anchor(obj, anchor, tol)
        elif gap <= reach:
            relation, certain = ("on_floor" if on_floor else "next_to"), True
        else:
            continue
        result = RelationResult(relation, anchor.anchor_id, certain, overlap, gap)
        priority = _PRIORITY.get((relation, certain), 1)
        candidates.append((priority, overlap, -gap, result))

    if candidates:
        chosen = max(candidates, key=lambda item: (item[0], item[1], item[2]))[3]
    elif on_floor:
        anchor_id = None
        if nearest is not None and nearest[0] <= 3.0 * nearest[1]:
            anchor_id = nearest[2].anchor_id
        chosen = RelationResult("on_floor", anchor_id, True)
    elif nearest is not None and nearest[0] <= 3.0 * nearest[1]:
        chosen = RelationResult("near", nearest[2].anchor_id, False, 0.0, nearest[0])
    else:
        chosen = RelationResult("in_room", None, True)

    if not reliable:
        if chosen.relation in VERTICAL_RELATIONS:
            if chosen.anchor_id is None:
                return RelationResult("in_room", None, False)
            return RelationResult(
                "near", chosen.anchor_id, False, chosen.overlap, chosen.gap
            )
        if chosen.relation in {"inside", "on_surface", "next_to"}:
            return RelationResult(
                chosen.relation, chosen.anchor_id, False, chosen.overlap, chosen.gap
            )
    return chosen
