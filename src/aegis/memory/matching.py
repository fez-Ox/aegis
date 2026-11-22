"""Cross-session matching of rooms, anchors and objects (pure functions).

Each session has its own world origin, so positions from two sessions are
not comparable directly. Matching therefore uses symbolic evidence first
(room signatures, anchor type, where objects were left) and geometry only
after a 2D similarity transform has been estimated from anchors that
matched unambiguously.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

import numpy as np

from aegis.memory.association import appearance_distance

Point = tuple[float, float]


# ---------------------------------------------------------------------- rooms
@dataclass(frozen=True, slots=True)
class RoomInfo:
    room_id: int
    room_type: str
    signature: frozenset[str] = frozenset()


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def match_rooms(
    session_rooms: Sequence[RoomInfo],
    home_rooms: Sequence[RoomInfo],
    *,
    continuity: tuple[int, int] | None = None,
    min_similarity: float = 0.5,
    min_margin: float = 0.05,
    min_overlap: int = 1,
) -> dict[int, int | None]:
    """Map session room ids to home room ids (None = create a new room).

    1. Continuity: a session that starts within seconds of the previous one
       starts in the room the wearer was last in.
    2. Signature: Jaccard similarity of landmark/anchor signatures, same room
       type when both are typed, with a margin over the runner-up. The margin
       is tight because noisy detectors rarely give a large gap; a larger one
       made every session create new rooms. A minimum shared-label count
       stops a single common landmark from matching unrelated rooms.
    3. A single remaining bare room matches the single remaining bare home
       room. Matches are one-to-one across the session.
    """

    result: dict[int, int | None] = {room.room_id: None for room in session_rooms}
    used: set[int] = set()
    home_by_id = {room.room_id: room for room in home_rooms}
    session_by_id = {room.room_id: room for room in session_rooms}

    def compatible(a: RoomInfo, b: RoomInfo) -> bool:
        return (
            a.room_type == "Room" or b.room_type == "Room" or a.room_type == b.room_type
        )

    # Signature evidence first: it is the strongest cue.
    proposals: list[tuple[float, int, int]] = []
    for room in session_rooms:
        if not room.signature:
            continue
        scores = []
        for home in home_rooms:
            if not home.signature:
                continue
            typed = room.room_type != "Room" and home.room_type != "Room"
            if typed and room.room_type != home.room_type:
                continue
            if len(room.signature & home.signature) < min_overlap:
                continue
            scores.append((_jaccard(room.signature, home.signature), home.room_id))
        if not scores:
            continue
        scores.sort(reverse=True)
        best, home_id = scores[0]
        runner_up = scores[1][0] if len(scores) > 1 else 0.0
        if best >= min_similarity and best - runner_up >= min_margin:
            proposals.append((best, room.room_id, home_id))
    for _score, room_id, home_id in sorted(proposals, reverse=True):
        if home_id in used or result[room_id] is not None:
            continue
        result[room_id] = home_id
        used.add(home_id)

    # Continuity: a back-to-back session starts where the wearer was, unless
    # the evidence above placed that room elsewhere or the types disagree.
    if continuity is not None:
        session_room, home_room = continuity
        if (
            session_room in result
            and result[session_room] is None
            and home_room in home_by_id
            and home_room not in used
            and compatible(session_by_id[session_room], home_by_id[home_room])
        ):
            result[session_room] = home_room
            used.add(home_room)

    bare_session = [
        r for r in session_rooms if result[r.room_id] is None and not r.signature
    ]
    unassigned_session = [r for r in session_rooms if result[r.room_id] is None]
    bare_home = [h for h in home_rooms if h.room_id not in used and not h.signature]
    if len(unassigned_session) == 1 and len(bare_session) == 1 and len(bare_home) == 1:
        result[bare_session[0].room_id] = bare_home[0].room_id
    return result


# -------------------------------------------------------------------- anchors
@dataclass(frozen=True, slots=True)
class AnchorInfo:
    anchor_id: int
    canonical: str
    room_id: int | None
    position: Point | None = None
    residents: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class Similarity2D:
    """``home = scale * R(theta) @ session + translation``."""

    scale: float
    theta: float
    translation: Point

    def apply(self, point: Point) -> Point:
        c, s = math.cos(self.theta), math.sin(self.theta)
        x, y = point
        return (
            self.scale * (c * x - s * y) + self.translation[0],
            self.scale * (s * x + c * y) + self.translation[1],
        )


def estimate_similarity(
    source: Sequence[Point], target: Sequence[Point]
) -> Similarity2D | None:
    """Umeyama similarity (no reflection) from >= 2 correspondences."""

    if len(source) < 2 or len(source) != len(target):
        return None
    src = np.asarray(source, dtype=np.float64)
    dst = np.asarray(target, dtype=np.float64)
    mu_s, mu_d = src.mean(axis=0), dst.mean(axis=0)
    xs, xd = src - mu_s, dst - mu_d
    var_s = float((xs**2).sum() / len(src))
    if var_s < 1e-12:
        return None
    cov = xd.T @ xs / len(src)
    u, singular, vt = np.linalg.svd(cov)
    d = np.eye(2)
    if np.linalg.det(u) * np.linalg.det(vt) < 0:
        d[1, 1] = -1.0
    rotation = u @ d @ vt
    scale = float(np.trace(np.diag(singular) @ d) / var_s)
    translation = mu_d - scale * rotation @ mu_s
    theta = math.atan2(rotation[1, 0], rotation[0, 0])
    return Similarity2D(scale, theta, (float(translation[0]), float(translation[1])))


@dataclass
class AnchorMatchResult:
    mapping: dict[int, tuple[int | None, str]] = field(default_factory=dict)
    transform: Similarity2D | None = None


def match_anchors(
    session_anchors: Sequence[AnchorInfo],
    home_anchors: Sequence[AnchorInfo],
    room_map: Mapping[int, int | None],
    *,
    max_residual_fraction: float = 0.25,
) -> AnchorMatchResult:
    """Map session anchors to home anchors with a quality label per match."""

    result = AnchorMatchResult()

    def group_key(anchor: AnchorInfo, *, session: bool) -> tuple[str, int | None]:
        if not session:
            return anchor.canonical, anchor.room_id
        if anchor.room_id is None:
            return anchor.canonical, None
        return anchor.canonical, room_map.get(anchor.room_id)

    session_groups: dict[tuple[str, int | None], list[AnchorInfo]] = {}
    for anchor in session_anchors:
        session_groups.setdefault(group_key(anchor, session=True), []).append(anchor)
    home_groups: dict[tuple[str, int | None], list[AnchorInfo]] = {}
    for anchor in home_anchors:
        home_groups.setdefault(group_key(anchor, session=False), []).append(anchor)

    def unmatched(key) -> tuple[list[AnchorInfo], list[AnchorInfo]]:
        used_home = {h for h, _q in result.mapping.values() if h is not None}
        sessions = [
            a for a in session_groups.get(key, []) if a.anchor_id not in result.mapping
        ]
        homes = [a for a in home_groups.get(key, []) if a.anchor_id not in used_home]
        return sessions, homes

    # 1. Unique by type within the room.
    for key in session_groups:
        if key[1] is None:
            continue
        sessions, homes = unmatched(key)
        if len(sessions) == 1 and len(homes) == 1:
            result.mapping[sessions[0].anchor_id] = (homes[0].anchor_id, "unique")

    # 2. Aligned by a similarity transform from the unique matches.
    home_by_id = {a.anchor_id: a for a in home_anchors}
    pairs = [
        (s.position, home_by_id[h].position)
        for s in session_anchors
        if s.anchor_id in result.mapping
        for h, _q in [result.mapping[s.anchor_id]]
        if h is not None
        and s.position is not None
        and home_by_id[h].position is not None
    ]
    transform = estimate_similarity([p[0] for p in pairs], [p[1] for p in pairs])
    if transform is not None and len(pairs) >= 3:
        residuals = [math.dist(transform.apply(src), dst) for src, dst in pairs]
        spread = np.mean(
            [math.dist(a[1], b[1]) for i, a in enumerate(pairs) for b in pairs[i + 1 :]]
        )
        rms = math.sqrt(sum(r * r for r in residuals) / len(residuals))
        if spread <= 0 or rms > max_residual_fraction * spread:
            transform = None
    result.transform = transform
    if transform is not None:
        for key in session_groups:
            sessions, homes = unmatched(key)
            homes = [h for h in homes if h.position is not None]
            candidates = sorted(
                (
                    (math.dist(transform.apply(s.position), h.position), s, h)
                    for s in sessions
                    if s.position is not None
                    for h in homes
                ),
                key=lambda item: item[0],
            )
            taken_s: set[int] = set()
            taken_h: set[int] = set()
            for distance, s, h in candidates:
                if s.anchor_id in taken_s or h.anchor_id in taken_h:
                    continue
                others = [
                    d
                    for d, s2, h2 in candidates
                    if s2.anchor_id == s.anchor_id
                    and h2.anchor_id != h.anchor_id
                    and h2.anchor_id not in taken_h
                ]
                if others and distance >= 0.5 * min(others):
                    continue
                result.mapping[s.anchor_id] = (h.anchor_id, "aligned")
                taken_s.add(s.anchor_id)
                taken_h.add(h.anchor_id)

    # 3. Residents: what rests on the anchor identifies it.
    for key in session_groups:
        sessions, homes = unmatched(key)
        for s in sessions:
            if not s.residents:
                continue
            overlaps = [(len(s.residents & h.residents), h) for h in homes]
            top = max((count for count, _h in overlaps), default=0)
            winners = [h for count, h in overlaps if count == top]
            if top >= 1 and len(winners) == 1:
                result.mapping[s.anchor_id] = (winners[0].anchor_id, "resident")
                homes = [h for h in homes if h.anchor_id != winners[0].anchor_id]

    # 4. Ordinal: equal counts left, pair in id order (flagged as weak).
    for key in session_groups:
        if key[1] is None:
            continue
        sessions, homes = unmatched(key)
        if sessions and len(sessions) == len(homes):
            for s, h in zip(
                sorted(sessions, key=lambda a: a.anchor_id),
                sorted(homes, key=lambda a: a.anchor_id),
                strict=True,
            ):
                result.mapping[s.anchor_id] = (h.anchor_id, "ordinal")

    # 5. Everything else is new.
    for anchor in session_anchors:
        result.mapping.setdefault(anchor.anchor_id, (None, "new"))
    return result


# ------------------------------------------------------------------ instances
@dataclass(frozen=True, slots=True)
class InstanceInfo:
    instance_id: int
    canonical: str
    relation: str | None = None
    anchor_id: int | None = None
    appearance: tuple[float, ...] | None = None


def match_instances(
    session_instances: Sequence[InstanceInfo],
    home_instances: Sequence[InstanceInfo],
    anchor_map: Callable[[int | None], int | None],
    *,
    appearance_threshold: float = 0.35,
    appearance_margin: float = 0.1,
) -> dict[int, int | None]:
    """Map session instances (state = first run) to home instances (last-known).

    Tiers, one-to-one per class: same place as last known; carried across a
    segment boundary; the only object of its class; appearance with a margin.
    """

    result: dict[int, int | None] = {}
    by_class: dict[str, list[InstanceInfo]] = {}
    for inst in session_instances:
        by_class.setdefault(inst.canonical, []).append(inst)

    for canonical, sessions in by_class.items():
        homes = [h for h in home_instances if h.canonical == canonical]
        used: set[int] = set()

        def assign(
            session: InstanceInfo, home: InstanceInfo, used: set[int] = used
        ) -> None:
            result[session.instance_id] = home.instance_id
            used.add(home.instance_id)

        def free(
            homes: list[InstanceInfo] = homes, used: set[int] = used
        ) -> list[InstanceInfo]:
            return [h for h in homes if h.instance_id not in used]

        def pending(sessions: list[InstanceInfo] = sessions) -> list[InstanceInfo]:
            return [s for s in sessions if s.instance_id not in result]

        # 1. Location continuity.
        for s in sorted(pending(), key=lambda i: i.instance_id):
            mapped_anchor = anchor_map(s.anchor_id)
            if s.relation is None or (
                s.relation == "in_room" and mapped_anchor is None
            ):
                continue
            if s.relation == "carried_by_user":
                continue
            same = [
                h
                for h in free()
                if h.relation == s.relation
                and h.anchor_id == mapped_anchor
                and mapped_anchor is not None
            ]
            if not same:
                continue
            if len(same) > 1 and s.appearance is not None:
                scored = [
                    (appearance_distance(h.appearance, s.appearance), h.instance_id, h)
                    for h in same
                ]
                with_score = [item for item in scored if item[0] is not None]
                if with_score:
                    assign(s, min(with_score, key=lambda item: (item[0], item[1]))[2])
                    continue
            assign(s, min(same, key=lambda h: h.instance_id))

        # 2. Carried across a segment boundary.
        for s in pending():
            if s.relation != "carried_by_user":
                continue
            carried = [h for h in free() if h.relation == "carried_by_user"]
            if len(carried) == 1:
                assign(s, carried[0])

        # 3. The only one of its class on both sides.
        if len(pending()) == 1 and len(free()) == 1:
            assign(pending()[0], free()[0])

        # 4. Appearance with a margin over the runner-up.
        for s in pending():
            scored = sorted(
                (d, h.instance_id, h)
                for h in free()
                if (d := appearance_distance(h.appearance, s.appearance)) is not None
            )
            if not scored or scored[0][0] > appearance_threshold:
                continue
            if len(scored) > 1 and scored[1][0] - scored[0][0] < appearance_margin:
                continue
            assign(s, scored[0][2])

        for s in sessions:
            result.setdefault(s.instance_id, None)
    return result
