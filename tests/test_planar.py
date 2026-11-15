"""Tests for floor-plane polygon helpers."""

from __future__ import annotations

import math

import pytest

from aegis.geometry.planar import (
    clip_convex,
    convex_hull,
    distance_point_to_polygon,
    oriented_rectangle,
    overlap_fraction,
    point_in_convex,
    polygon_area,
)

UNIT = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]


def test_hull_drops_interior_points() -> None:
    hull = convex_hull([*UNIT, (0.5, 0.5)])
    assert sorted(hull) == sorted(UNIT)


def test_area_of_unit_square() -> None:
    assert polygon_area(UNIT) == pytest.approx(1.0)
    assert polygon_area(UNIT[:2]) == 0.0


def test_clip_of_offset_squares() -> None:
    shifted = [(x + 0.5, y) for x, y in UNIT]
    assert polygon_area(clip_convex(UNIT, shifted)) == pytest.approx(0.5)


def test_overlap_fraction_contained_and_disjoint() -> None:
    small = [(0.25, 0.25), (0.75, 0.25), (0.75, 0.75), (0.25, 0.75)]
    assert overlap_fraction(small, UNIT) == pytest.approx(1.0)
    far = [(x + 5.0, y) for x, y in UNIT]
    assert overlap_fraction(far, UNIT) == 0.0


def test_point_in_convex_and_distance() -> None:
    assert point_in_convex((0.5, 0.5), UNIT)
    assert not point_in_convex((1.5, 0.5), UNIT)
    assert distance_point_to_polygon((2.0, 0.5), UNIT) == pytest.approx(1.0)
    assert distance_point_to_polygon((0.5, 0.5), UNIT) == 0.0


def test_oriented_rectangle_at_quarter_turn_swaps_extents() -> None:
    corners = oriented_rectangle((0.0, 0.0), 2.0, 1.0, math.pi / 2)
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    assert max(xs) - min(xs) == pytest.approx(1.0)
    assert max(ys) - min(ys) == pytest.approx(2.0)
    assert polygon_area(corners) == pytest.approx(2.0)
