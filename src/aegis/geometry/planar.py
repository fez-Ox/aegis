"""2D polygon helpers for floor-plane reasoning.

Points are ``(h1, h2)`` coordinates in a gravity frame's floor plane (see
:meth:`aegis.geometry.gravity.GravityFrame.horizontal`). Polygons are convex
and counter-clockwise unless stated otherwise.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

Point = tuple[float, float]


def _cross(origin: Point, a: Point, b: Point) -> float:
    return (a[0] - origin[0]) * (b[1] - origin[1]) - (a[1] - origin[1]) * (
        b[0] - origin[0]
    )


def convex_hull(points: Sequence[Point]) -> list[Point]:
    """Andrew's monotone chain convex hull (counter-clockwise)."""

    unique = sorted({(float(p[0]), float(p[1])) for p in points})
    if len(unique) <= 2:
        return unique
    lower: list[Point] = []
    for point in unique:
        while len(lower) >= 2 and _cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper: list[Point] = []
    for point in reversed(unique):
        while len(upper) >= 2 and _cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def polygon_area(polygon: Sequence[Point]) -> float:
    """Absolute shoelace area; 0 for fewer than three points."""

    if len(polygon) < 3:
        return 0.0
    total = 0.0
    for index, (ax, ay) in enumerate(polygon):
        bx, by = polygon[(index + 1) % len(polygon)]
        total += ax * by - bx * ay
    return abs(total) / 2.0


def point_in_convex(point: Point, polygon: Sequence[Point], eps: float = 1e-9) -> bool:
    """Inside-or-on-boundary test for a counter-clockwise convex polygon."""

    if len(polygon) < 3:
        return False
    px, py = point
    for index, (ax, ay) in enumerate(polygon):
        bx, by = polygon[(index + 1) % len(polygon)]
        if (bx - ax) * (py - ay) - (by - ay) * (px - ax) < -eps:
            return False
    return True


def clip_convex(subject: Sequence[Point], clip: Sequence[Point]) -> list[Point]:
    """Sutherland–Hodgman intersection of two convex CCW polygons."""

    if len(subject) < 3 or len(clip) < 3:
        return []
    output: list[Point] = [tuple(p) for p in subject]  # type: ignore[misc]
    for index, edge_start in enumerate(clip):
        edge_end = clip[(index + 1) % len(clip)]
        if not output:
            break
        current = output
        output = []

        def inside(p: Point, a: Point = edge_start, b: Point = edge_end) -> bool:
            return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (
                p[0] - a[0]
            ) >= -1e-12

        def intersection(
            p: Point, q: Point, a: Point = edge_start, b: Point = edge_end
        ) -> Point:
            dx1, dy1 = q[0] - p[0], q[1] - p[1]
            dx2, dy2 = b[0] - a[0], b[1] - a[1]
            denominator = dx1 * dy2 - dy1 * dx2
            if abs(denominator) < 1e-15:
                return q
            t = ((a[0] - p[0]) * dy2 - (a[1] - p[1]) * dx2) / denominator
            return (p[0] + t * dx1, p[1] + t * dy1)

        for position, point in enumerate(current):
            previous = current[position - 1]
            if inside(point):
                if not inside(previous):
                    output.append(intersection(previous, point))
                output.append(point)
            elif inside(previous):
                output.append(intersection(previous, point))
    return output


def overlap_fraction(subject: Sequence[Point], clip: Sequence[Point]) -> float:
    """Share of ``subject``'s area that lies inside ``clip`` (0 when degenerate)."""

    area = polygon_area(subject)
    if area <= 0:
        return 0.0
    return min(1.0, polygon_area(clip_convex(subject, clip)) / area)


def _distance_to_segment(point: Point, a: Point, b: Point) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length_sq = dx * dx + dy * dy
    if length_sq <= 0:
        return math.hypot(point[0] - a[0], point[1] - a[1])
    t = ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    return math.hypot(point[0] - (a[0] + t * dx), point[1] - (a[1] + t * dy))


def distance_point_to_polygon(point: Point, polygon: Sequence[Point]) -> float:
    """0 inside the polygon, else the distance to its nearest edge."""

    if not polygon:
        return math.inf
    if len(polygon) == 1:
        return math.hypot(point[0] - polygon[0][0], point[1] - polygon[0][1])
    if len(polygon) >= 3 and point_in_convex(point, polygon):
        return 0.0
    edges = len(polygon) if len(polygon) >= 3 else 1
    return min(
        _distance_to_segment(point, polygon[i], polygon[(i + 1) % len(polygon)])
        for i in range(edges)
    )


def oriented_rectangle(
    center: Point, length: float, width: float, yaw: float
) -> list[Point]:
    """Four CCW corners of a rectangle with ``length`` along ``yaw``."""

    cos_y, sin_y = math.cos(yaw), math.sin(yaw)
    half_l, half_w = length / 2.0, width / 2.0
    corners = (
        (-half_l, -half_w),
        (half_l, -half_w),
        (half_l, half_w),
        (-half_l, half_w),
    )
    return [
        (center[0] + a * cos_y - b * sin_y, center[1] + a * sin_y + b * cos_y)
        for a, b in corners
    ]


def centroid(polygon: Sequence[Point]) -> Point:
    """Vertex mean (adequate for small convex footprints)."""

    if not polygon:
        return (0.0, 0.0)
    return (
        sum(p[0] for p in polygon) / len(polygon),
        sum(p[1] for p in polygon) / len(polygon),
    )
