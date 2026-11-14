"""State runs: one row per stable object state, plus the events between them.

An object that rests on a shelf for an hour is one run, not one entry per
keyframe. A new state replaces the current one only after it has been seen
``min_run_observations`` times in a row, so a single misclassified frame
does not create a move.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any

import numpy as np

from aegis.core.config import MemoryBuildConfig
from aegis.core.models import BoundingBox3D
from aegis.geometry.gravity import GravityFrame

CARRIED = "carried_by_user"
State = tuple[str, int | None]


@dataclass(frozen=True, slots=True)
class Observation:
    frame_id: int
    timestamp: float
    instance_id: int
    box: BoundingBox3D
    relation: str
    anchor_id: int | None
    certain: bool
    hand_cue: bool

    @property
    def state(self) -> State:
        if self.hand_cue:
            return (CARRIED, None)
        return (self.relation, self.anchor_id)

    @property
    def state_certain(self) -> bool:
        return True if self.hand_cue else self.certain


@dataclass
class StateRun:
    instance_id: int
    relation: str
    anchor_id: int | None
    room_id: int | None
    start_frame: int
    end_frame: int
    start_time: float
    end_time: float
    observation_count: int
    confidence: float
    certain: bool
    center: tuple[float, float, float]
    height_above_floor: float | None
    best_frame: int
    best_bbox_2d: tuple[float, float, float, float]
    observations: list[Observation] = field(default_factory=list, repr=False)

    def as_dict(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "relation": self.relation,
            "relation_certain": self.certain,
            "anchor_id": self.anchor_id,
            "room_id": self.room_id,
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "observation_count": self.observation_count,
            "confidence": self.confidence,
            "center": list(self.center),
            "height_above_floor": self.height_above_floor,
            "best_frame": self.best_frame,
            "best_bbox_2d": list(self.best_bbox_2d),
        }


def is_hand_cue(box: BoundingBox3D) -> bool:
    return bool(box.is_in_hand or box.spatial_state == "in_hand")


def _segments(
    observations: Sequence[Observation], config: MemoryBuildConfig
) -> list[tuple[int, int, State]]:
    """Debounced ``(first_index, last_index, state)`` segments."""

    states = [obs.state for obs in observations]
    n = len(states)
    segments: list[tuple[int, int, State]] = []
    current = states[0]
    run_start = 0
    pending: State | None = None
    pending_start = 0
    pending_count = 0
    for i in range(1, n):
        if states[i] == current:
            pending, pending_count = None, 0
        elif pending is not None and states[i] == pending:
            pending_count += 1
        else:
            pending, pending_start, pending_count = states[i], i, 1
        if pending is not None and pending_count >= config.min_run_observations:
            segments.append((run_start, pending_start - 1, current))
            current, run_start = pending, pending_start
            pending, pending_count = None, 0

    last = observations[-1]
    if (
        pending is not None
        and pending_start == n - 1
        and last.box.confidence >= config.trailing_single_confidence
        and (last.state_certain and last.state[0] != "near")
        and n - 1 > run_start
    ):
        segments.append((run_start, n - 2, current))
        segments.append((n - 1, n - 1, pending))
    else:
        segments.append((run_start, n - 1, current))
    return segments


def _height_above_floor(box: BoundingBox3D, gravity: GravityFrame) -> float | None:
    if gravity.floor_offset is None:
        return None
    bottom = box.up_min
    if bottom is None:
        bottom = gravity.elevation(box.center) - box.size[2] / 2.0
    return float(bottom - gravity.floor_offset)


def build_state_runs(
    observations: Sequence[Observation],
    *,
    settings: MemoryBuildConfig | None = None,
    gravity: GravityFrame | None = None,
    room_of: Callable[[StateRun], int | None] | None = None,
) -> dict[int, list[StateRun]]:
    """Group observations into debounced runs, per instance in time order."""

    config = settings or MemoryBuildConfig()
    frame = gravity or GravityFrame.assumed()
    by_instance: dict[int, list[Observation]] = {}
    for obs in observations:
        by_instance.setdefault(obs.instance_id, []).append(obs)

    runs: dict[int, list[StateRun]] = {}
    for instance_id, items in sorted(by_instance.items()):
        ordered = sorted(items, key=lambda o: (o.timestamp, o.frame_id))
        if len(ordered) < config.min_observations:
            continue
        instance_runs: list[StateRun] = []
        for first, last, state in _segments(ordered, config):
            members = ordered[first : last + 1]
            matching = [obs for obs in members if obs.state == state] or members
            best = max(matching, key=lambda o: o.box.confidence)
            certain = all(obs.state_certain for obs in matching)
            confidence = float(np.mean([obs.box.confidence for obs in members]))
            heights = [
                h
                for h in (_height_above_floor(o.box, frame) for o in matching)
                if h is not None
            ]
            run = StateRun(
                instance_id=instance_id,
                relation=state[0],
                anchor_id=state[1],
                room_id=None,
                start_frame=members[0].frame_id,
                end_frame=members[-1].frame_id,
                start_time=members[0].timestamp,
                end_time=members[-1].timestamp,
                observation_count=len(members),
                confidence=round(confidence * (1.0 if certain else 0.6), 4),
                certain=certain,
                center=tuple(
                    float(v)
                    for v in np.median([o.box.center for o in matching], axis=0)
                ),
                height_above_floor=float(np.median(heights)) if heights else None,
                best_frame=best.frame_id,
                best_bbox_2d=tuple(float(v) for v in best.box.bbox_2d),
                observations=list(members),
            )
            if room_of is not None:
                run.room_id = room_of(run)
            instance_runs.append(run)
        runs[instance_id] = instance_runs
    return runs


def _event_type(previous: StateRun, current: StateRun) -> str:
    if current.relation == CARRIED:
        return "pickup"
    if previous.relation == CARRIED:
        return "placement"
    if previous.anchor_id != current.anchor_id:
        return "anchor_change"
    return "state_change"


def build_events(
    runs_by_instance: Mapping[int, Sequence[StateRun]],
    *,
    names: Mapping[int, str],
    anchor_labels: Mapping[int, str],
    room_labels: Mapping[int, str],
    wallclock: Callable[[int], str | None],
) -> list[dict[str, Any]]:
    """One event per change between consecutive runs of an instance.

    Hook (Milestone 3, todo 3.7 / M8): a vision-language model may caption
    the evidence crop here, once per event, and cache the caption on the run.
    Never per frame.
    """

    events: list[dict[str, Any]] = []
    for instance_id, runs in runs_by_instance.items():
        for previous, current in pairwise(runs):
            events.append(
                {
                    "event_id": "",
                    "event_type": _event_type(previous, current),
                    "instance_id": instance_id,
                    "object": names.get(instance_id, f"Object #{instance_id}"),
                    "source_anchor": anchor_labels.get(previous.anchor_id),
                    "destination_anchor": anchor_labels.get(current.anchor_id),
                    "source_anchor_id": previous.anchor_id,
                    "destination_anchor_id": current.anchor_id,
                    "source_room": room_labels.get(previous.room_id),
                    "destination_room": room_labels.get(current.room_id),
                    "source_room_id": previous.room_id,
                    "destination_room_id": current.room_id,
                    "source_relation": previous.relation,
                    "destination_relation": current.relation,
                    "start_time": previous.end_time,
                    "end_time": current.start_time,
                    "start_wallclock": wallclock(previous.end_frame),
                    "end_wallclock": wallclock(current.start_frame),
                    "source_frame": previous.end_frame,
                    "destination_frame": current.start_frame,
                    "stable_observations": current.observation_count,
                    "relative_displacement": float(
                        np.linalg.norm(
                            np.asarray(current.center) - np.asarray(previous.center)
                        )
                    ),
                    "evidence_frames": list(
                        dict.fromkeys(
                            [
                                previous.start_frame,
                                previous.end_frame,
                                current.start_frame,
                                current.end_frame,
                            ]
                        )
                    ),
                    "confidence": min(previous.confidence, current.confidence),
                }
            )
    return events
