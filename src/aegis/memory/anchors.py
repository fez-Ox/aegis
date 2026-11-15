"""Spatial anchors: stable furniture that objects are located relative to."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from aegis.core.models import BoundingBox3D
from aegis.core.vocabulary import Vocabulary, default_vocabulary
from aegis.geometry.gravity import GravityFrame
from aegis.geometry.planar import convex_hull
from aegis.memory.relations import AnchorShape, Footprint3D, box_footprint


@dataclass
class SpatialAnchor:
    """A stable 3D environmental anchor (cabinet, desk, bed, ...)."""

    anchor_id: int
    label: str
    center: tuple[float, float, float]
    size: tuple[float, float, float]
    observations_count: int = 1
    room_id: int | None = None
    room_label: str | None = None
    canonical: str = ""
    rotation: tuple[float, float, float, float] | None = None
    yaw: float | None = None
    footprint: list[tuple[float, float]] = field(default_factory=list)
    up_min: float | None = None
    up_max: float | None = None
    support_up: float | None = None

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "anchor_id": self.anchor_id,
            "label": self.label,
            "center": list(self.center),
            "size": list(self.size),
            "observations_count": self.observations_count,
        }
        if self.room_id is not None:
            data["room_id"] = self.room_id
        if self.room_label is not None:
            data["room_label"] = self.room_label
        if self.canonical:
            data["canonical"] = self.canonical
        if self.rotation is not None:
            data["rotation"] = list(self.rotation)
        if self.yaw is not None:
            data["yaw"] = self.yaw
        if self.footprint:
            data["footprint"] = [list(point) for point in self.footprint]
        for name in ("up_min", "up_max", "support_up"):
            value = getattr(self, name)
            if value is not None:
                data[name] = value
        return data


def extract_spatial_anchors(
    boxes_3d: Sequence[BoundingBox3D],
    cluster_threshold: float = 0.40,
    *,
    vocabulary: Vocabulary | None = None,
    gravity: GravityFrame | None = None,
    unit: float = 1.0,
) -> list[SpatialAnchor]:
    """Cluster recurring furniture observations into anchors.

    Returns an empty list when no furniture was observed; an anchor is never
    invented.
    """

    vocab = vocabulary or default_vocabulary()
    frame = gravity or GravityFrame.assumed()
    radius = cluster_threshold * unit

    groups: dict[str, list[BoundingBox3D]] = {}
    for box in boxes_3d:
        if vocab.role(box.label) == "anchor":
            groups.setdefault(vocab.canonical(box.label), []).append(box)
    if not groups:
        return []

    anchors: list[SpatialAnchor] = []
    anchor_idx = 1
    for canonical, group in sorted(groups.items()):
        clusters: list[list[BoundingBox3D]] = []
        for box in group:
            center = np.asarray(box.center, dtype=np.float64)
            for cluster in clusters:
                mean = np.mean([b.center for b in cluster], axis=0)
                if np.linalg.norm(center - mean) < radius:
                    cluster.append(box)
                    break
            else:
                clusters.append([box])

        # Drop single-frame noise when repeated observations exist.
        valid = [cluster for cluster in clusters if len(cluster) >= 2] or clusters
        for cluster in valid:
            extents = np.asarray([max(b.size) for b in cluster], dtype=np.float64)
            median_extent = float(np.median(extents))
            members = [
                b for b in cluster if max(b.size) <= 2.0 * median_extent
            ] or cluster
            centers = np.asarray([b.center for b in members], dtype=np.float64)
            median_center = np.median(centers, axis=0)
            medoid = members[
                int(np.argmin(np.linalg.norm(centers - median_center, axis=1)))
            ]

            footprints = [box_footprint(b, frame) for b in members]
            corners = [point for fp in footprints for point in fp.polygon]
            supports = [b.support_up for b in members if b.support_up is not None]
            anchors.append(
                SpatialAnchor(
                    anchor_id=anchor_idx,
                    label=f"{vocab.display(canonical)} #{anchor_idx}",
                    center=tuple(float(v) for v in median_center),
                    size=tuple(float(v) for v in medoid.size),
                    observations_count=len(cluster),
                    canonical=canonical,
                    rotation=medoid.rotation,
                    yaw=medoid.yaw,
                    footprint=convex_hull(corners),
                    up_min=float(np.percentile([fp.up_min for fp in footprints], 15)),
                    up_max=float(np.percentile([fp.up_max for fp in footprints], 85)),
                    support_up=float(np.median(supports)) if supports else None,
                )
            )
            anchor_idx += 1
    return anchors


def anchor_shape(anchor: SpatialAnchor, vocabulary: Vocabulary) -> AnchorShape:
    """Geometry and affordances of an anchor for relation classification."""

    entry = vocabulary.entry(anchor.canonical or anchor.label.split("#")[0])
    up_min = anchor.up_min if anchor.up_min is not None else 0.0
    up_max = anchor.up_max if anchor.up_max is not None else up_min
    return AnchorShape(
        anchor_id=anchor.anchor_id,
        footprint=Footprint3D(
            polygon=tuple(anchor.footprint),
            up_min=up_min,
            up_max=up_max,
            support_up=anchor.support_up,
        ),
        container=entry.container,
        support_surface=entry.support_surface,
        open_underneath=entry.open_underneath,
    )
