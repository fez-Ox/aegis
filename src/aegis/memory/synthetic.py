"""Deterministic synthetic sessions for storage-growth measurements.

These graphs are **synthetic** (no video behind them). They exercise the real
ingest and compaction code so that store size can be plotted over many
simulated days (AC-07) without recording days of video. Every object has a
unique label so that identity matching is not what is being measured.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import numpy as np

from aegis.core.timeutil import shift_iso, to_utc_iso

ROOM_TYPES = ("Kitchen", "Bedroom", "Living Room", "Bathroom", "Dining Room")
ANCHOR_TYPES = ("desk", "drawer", "storage cabinet", "nightstand")


@dataclass
class SyntheticHome:
    objects: int = 100
    changes_per_day: int = 1000
    sessions_per_day: int = 144
    hours_per_day: float = 12.0
    seed: int = 0

    def __post_init__(self) -> None:
        self.rng = np.random.default_rng(self.seed)
        self.anchor_count = len(ROOM_TYPES) * len(ANCHOR_TYPES)
        self.place = {
            obj: int(self.rng.integers(1, self.anchor_count + 1))
            for obj in range(1, self.objects + 1)
        }

    def _room_of(self, anchor_id: int) -> int:
        return (anchor_id - 1) // len(ANCHOR_TYPES) + 1

    def _structure(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        rooms = [
            {
                "room_id": index + 1,
                "label": room_type,
                "room_type": room_type,
                "evidence_labels": [f"{room_type} landmark"],
            }
            for index, room_type in enumerate(ROOM_TYPES)
        ]
        anchors = []
        for room_index in range(len(ROOM_TYPES)):
            for type_index, canonical in enumerate(ANCHOR_TYPES):
                anchor_id = room_index * len(ANCHOR_TYPES) + type_index + 1
                anchors.append(
                    {
                        "anchor_id": anchor_id,
                        "canonical": canonical,
                        "label": f"{canonical.title()} #{anchor_id}",
                        "room_id": room_index + 1,
                        "center": [float(type_index), 0.0, float(room_index * 10)],
                        "size": [1.0, 1.0, 1.0],
                    }
                )
        return rooms, anchors

    def sessions(self, day: date) -> Iterator[dict[str, Any]]:
        """Session graphs (schema v2) covering ``hours_per_day`` of ``day``."""

        rooms, anchors = self._structure()
        day_start = datetime(day.year, day.month, day.day, 6, 0, tzinfo=UTC)
        duration = self.hours_per_day * 3600.0 / self.sessions_per_day
        changes = np.array_split(
            self.rng.integers(1, self.objects + 1, size=self.changes_per_day),
            self.sessions_per_day,
        )
        for index in range(self.sessions_per_day):
            start = to_utc_iso(day_start + timedelta(seconds=index * duration))
            moved = {int(o) for o in changes[index]}
            seen = moved | {
                int(o)
                for o in self.rng.integers(
                    1, self.objects + 1, size=max(1, self.objects // 20)
                )
            }
            runs, latest, events = [], [], []
            for obj in sorted(seen):
                label = f"Object {obj} #{obj}"
                if obj in moved:
                    new_place = int(self.rng.integers(1, self.anchor_count + 1))
                    old_place = self.place[obj]
                    self.place[obj] = new_place
                    segments = [
                        ("carried_by_user", None, self._room_of(old_place), 0.2, 0.4),
                        ("on_surface", new_place, self._room_of(new_place), 0.6, 0.9),
                    ]
                else:
                    place = self.place[obj]
                    segments = [("on_surface", place, self._room_of(place), 0.1, 0.9)]
                object_runs = []
                for relation, anchor_id, room_id, f0, f1 in segments:
                    t0, t1 = f0 * duration, f1 * duration
                    object_runs.append(
                        {
                            "instance_id": obj,
                            "relation": relation,
                            "relation_certain": True,
                            "anchor_id": anchor_id,
                            "room_id": room_id,
                            "start_time": t0,
                            "end_time": t1,
                            "start_wallclock": shift_iso(start, t0),
                            "end_wallclock": shift_iso(start, t1),
                            "observation_count": 3,
                            "confidence": 0.9,
                            "center": [0.0, 0.0, 0.0],
                            "height_above_floor": None,
                        }
                    )
                runs.extend(object_runs)
                if len(object_runs) == 2:
                    first, second = object_runs
                    events.append(
                        {
                            "event_type": "placement",
                            "instance_id": obj,
                            "object": label,
                            "source_relation": first["relation"],
                            "destination_relation": second["relation"],
                            "source_anchor_id": None,
                            "destination_anchor_id": second["anchor_id"],
                            "source_room_id": first["room_id"],
                            "destination_room_id": second["room_id"],
                            "start_time": first["end_time"],
                            "end_time": second["start_time"],
                            "start_wallclock": first["end_wallclock"],
                            "end_wallclock": second["start_wallclock"],
                            "confidence": 0.9,
                        }
                    )
                latest.append(
                    {
                        "instance_id": obj,
                        "label": label,
                        "canonical": f"object {obj}",
                        "relation": object_runs[-1]["relation"],
                        "anchor_id": object_runs[-1]["anchor_id"],
                        "room_id": object_runs[-1]["room_id"],
                        "appearance": None,
                        "confidence": 0.9,
                    }
                )
            visit_room = int(self.rng.integers(1, len(ROOM_TYPES) + 1))
            yield {
                "schema_version": 2,
                "dataset_id": f"syn_{day.isoformat()}_{index:04d}",
                "session": {
                    "dataset_id": f"syn_{day.isoformat()}_{index:04d}",
                    "started_at": start,
                    "ended_at": shift_iso(start, duration),
                    "time_source": "capture",
                    "keyframe_count": int(duration * 0.5),
                    "duration_seconds": duration,
                    "first_timestamp": 0.0,
                },
                "gravity": {
                    "up": [0.0, -1.0, 0.0],
                    "source": "assumed",
                    "confidence": 0.0,
                },
                "anchors": anchors,
                "rooms": rooms,
                "state_runs": runs,
                "latest_states": latest,
                "events": events,
                "room_visits": [
                    {
                        "room_id": visit_room,
                        "start_time": 0.0,
                        "end_time": duration,
                        "start_wallclock": start,
                        "end_wallclock": shift_iso(start, duration),
                    }
                ],
            }
