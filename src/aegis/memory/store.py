"""Durable per-home memory store (SQLite, one file per home).

A *session* is one processed dataset (a video or a live segment). Its scene
graph is session-local; the home store accumulates sessions and keeps stable
ids for rooms, anchors and objects. It stores state runs (one row per stable
placement), not frames, so it grows with changes in the home, not with
recording time. History is append-only across sessions; only a re-ingest of
the same session replaces that session's rows.

All SQL lives in this module. Timestamps are UTC ISO-8601 text in the fixed
format of :mod:`aegis.core.timeutil`, so text order is time order.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any

from aegis.core.paths import validate_dataset_id
from aegis.core.timeutil import parse_iso, to_utc_iso, utc_now

SCHEMA_VERSION = 1
DEFAULT_STORE_ROOT = "outputs/_homes"

_SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE room (
  room_id       INTEGER PRIMARY KEY,
  label         TEXT NOT NULL,
  room_type     TEXT NOT NULL,
  label_source  TEXT NOT NULL CHECK (label_source IN ('auto','caregiver')),
  signature     TEXT NOT NULL,
  session_count INTEGER NOT NULL DEFAULT 1,
  last_seen_session TEXT,
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL
);

CREATE TABLE session (
  session_id         TEXT PRIMARY KEY,
  started_at         TEXT NOT NULL,
  ended_at           TEXT NOT NULL,
  time_source        TEXT NOT NULL CHECK (time_source IN ('capture','recorded_at','ingest')),
  ingested_at        TEXT NOT NULL,
  graph_sha256       TEXT NOT NULL,
  keyframe_count     INTEGER NOT NULL,
  gravity_confidence REAL,
  last_wearer_room_id INTEGER REFERENCES room(room_id)
);

CREATE TABLE anchor (
  anchor_id     INTEGER PRIMARY KEY,
  canonical     TEXT NOT NULL,
  label         TEXT NOT NULL,
  ordinal       INTEGER NOT NULL,
  room_id       INTEGER REFERENCES room(room_id),
  home_x        REAL,
  home_y        REAL,
  match_quality TEXT NOT NULL DEFAULT 'new'
    CHECK (match_quality IN ('unique','aligned','resident','ordinal','new')),
  observations  INTEGER NOT NULL DEFAULT 0,
  last_seen_session TEXT,
  UNIQUE (canonical, ordinal)
);

CREATE TABLE instance (
  instance_id   INTEGER PRIMARY KEY,
  canonical     TEXT NOT NULL,
  label         TEXT NOT NULL,
  importance    TEXT NOT NULL,
  appearance    TEXT,
  created_at    TEXT NOT NULL,
  observation_count INTEGER NOT NULL DEFAULT 0,
  last_relation TEXT,
  last_relation_certain INTEGER,
  last_anchor_id INTEGER REFERENCES anchor(anchor_id),
  last_room_id  INTEGER REFERENCES room(room_id),
  last_seen_at  TEXT,
  last_confidence REAL,
  last_height   REAL,
  last_run_id   INTEGER,
  last_session_id TEXT,
  last_evidence_id INTEGER
);

CREATE TABLE state_run (
  run_id        INTEGER PRIMARY KEY,
  instance_id   INTEGER NOT NULL REFERENCES instance(instance_id),
  session_id    TEXT NOT NULL REFERENCES session(session_id),
  relation      TEXT NOT NULL,
  relation_certain INTEGER NOT NULL,
  anchor_id     INTEGER REFERENCES anchor(anchor_id),
  room_id       INTEGER REFERENCES room(room_id),
  start_at      TEXT NOT NULL,
  end_at        TEXT NOT NULL,
  observation_count INTEGER NOT NULL,
  confidence    REAL NOT NULL,
  height_above_floor REAL,
  center_x REAL, center_y REAL, center_z REAL,
  evidence_id   INTEGER
);
CREATE INDEX state_run_instance_end ON state_run(instance_id, end_at);
CREATE INDEX state_run_end ON state_run(end_at);
CREATE INDEX state_run_session ON state_run(session_id);

CREATE TABLE activity (
  activity_id INTEGER PRIMARY KEY,
  session_id  TEXT NOT NULL REFERENCES session(session_id),
  room_id     INTEGER REFERENCES room(room_id),
  start_at    TEXT NOT NULL,
  end_at      TEXT NOT NULL,
  event_count INTEGER NOT NULL,
  summary     TEXT NOT NULL
);
CREATE INDEX activity_end ON activity(end_at);

CREATE TABLE event (
  event_id      INTEGER PRIMARY KEY,
  session_id    TEXT NOT NULL REFERENCES session(session_id),
  event_type    TEXT NOT NULL,
  instance_id   INTEGER REFERENCES instance(instance_id),
  from_relation TEXT, to_relation TEXT,
  from_anchor_id INTEGER, to_anchor_id INTEGER,
  from_room_id INTEGER, to_room_id INTEGER,
  start_at      TEXT NOT NULL,
  end_at        TEXT NOT NULL,
  confidence    REAL,
  activity_id   INTEGER,
  evidence_id   INTEGER
);
CREATE INDEX event_end ON event(end_at);
CREATE INDEX event_session ON event(session_id);

CREATE TABLE room_visit (
  visit_id   INTEGER PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES session(session_id),
  room_id    INTEGER REFERENCES room(room_id),
  start_at   TEXT NOT NULL,
  end_at     TEXT NOT NULL
);
CREATE INDEX room_visit_end ON room_visit(end_at);

CREATE TABLE evidence (
  evidence_id INTEGER PRIMARY KEY,
  session_id  TEXT NOT NULL REFERENCES session(session_id),
  instance_id INTEGER NOT NULL REFERENCES instance(instance_id),
  path        TEXT NOT NULL,
  captured_at TEXT NOT NULL,
  frame_id    INTEGER,
  width INTEGER, height INTEGER, bytes INTEGER
);

CREATE TABLE summary (
  summary_id   INTEGER PRIMARY KEY,
  level        TEXT NOT NULL CHECK (level IN ('day','week','month')),
  period_start TEXT NOT NULL,
  period_end   TEXT NOT NULL,
  kind         TEXT NOT NULL CHECK (kind IN ('object','activity')),
  subject_key  TEXT NOT NULL,
  text         TEXT NOT NULL,
  sidecar      TEXT NOT NULL,
  created_at   TEXT NOT NULL,
  UNIQUE (level, period_start, kind, subject_key)
);
CREATE INDEX summary_period ON summary(period_start);

CREATE TABLE compaction_log (
  id INTEGER PRIMARY KEY,
  ran_at TEXT NOT NULL,
  day TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('ok','failed','skipped')),
  runs_deleted INTEGER NOT NULL DEFAULT 0,
  events_deleted INTEGER NOT NULL DEFAULT 0,
  summaries_written INTEGER NOT NULL DEFAULT 0,
  detail TEXT
);
"""

TABLES = (
    "session",
    "room",
    "anchor",
    "instance",
    "state_run",
    "event",
    "room_visit",
    "activity",
    "evidence",
    "summary",
    "compaction_log",
)


def resolve_store_root(store_root: str | Path | None = None) -> Path:
    if store_root is not None:
        return Path(store_root)
    return Path(os.environ.get("AEGIS_STORE_ROOT", DEFAULT_STORE_ROOT))


def home_dir(home_id: str, store_root: str | Path | None = None) -> Path:
    return resolve_store_root(store_root) / validate_dataset_id(home_id)


def now_iso() -> str:
    return to_utc_iso(utc_now())


# Distinguishes "caller supplied None" from "caller omitted this field" in
# _state_dict; as-of rows legitimately have NULL anchors and relations.
_MISSING = object()


def _epoch(value: Any) -> float | None:
    """Epoch seconds for a stored ISO timestamp, or None when unusable."""

    if not value:
        return None
    try:
        return parse_iso(str(value)).timestamp()
    except ValueError:
        return None


# Correlated features shared by latest_states() and states_as_of(). They keep
# the ranking inputs in one query instead of one round-trip per instance.
_INSTANCE_FEATURES = """
    (SELECT MAX(e.end_at) FROM event e
       WHERE e.instance_id = i.instance_id
         AND e.event_type IN ('placement', 'anchor_change', 'moved_while_unobserved')
    ) AS last_moved_at,
    (SELECT COUNT(*) FROM event e
       WHERE e.instance_id = i.instance_id AND e.event_type = 'placement'
    ) AS placement_count,
    (SELECT COUNT(*) FROM event e
       WHERE e.instance_id = i.instance_id AND e.event_type = 'pickup'
    ) AS pickup_count,
    (SELECT MIN(sr.start_at) FROM state_run sr
       WHERE sr.instance_id = i.instance_id
    ) AS first_seen_at,
    (SELECT sr.room_id FROM state_run sr
       WHERE sr.instance_id = i.instance_id
       ORDER BY sr.start_at, sr.run_id LIMIT 1
    ) AS first_room_id,
    (SELECT sr.anchor_id FROM state_run sr
       WHERE sr.instance_id = i.instance_id
       ORDER BY sr.start_at, sr.run_id LIMIT 1
    ) AS first_anchor_id
"""


class HomeStore:
    """One home's SQLite memory. Thread-safe through a single lock."""

    def __init__(self, home_id: str, path: Path) -> None:
        self.home_id = home_id
        self.path = path
        self.dir = path.parent
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            str(path), check_same_thread=False, isolation_level=None
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        version = int(self._conn.execute("PRAGMA user_version").fetchone()[0])
        if version == 0:
            self._conn.executescript(_SCHEMA)
            self._conn.execute(f"PRAGMA user_version={SCHEMA_VERSION:d}")
            created = now_iso()
            self._conn.executemany(
                "INSERT INTO meta(key, value) VALUES (?, ?)",
                [("home_id", home_id), ("created_at", created)],
            )
        elif version > SCHEMA_VERSION:
            self._conn.close()
            raise RuntimeError(
                f"memory store {path} has schema version {version}; this code "
                f"supports up to {SCHEMA_VERSION}"
            )

    # -------------------------------------------------------------- basics
    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Atomic block; everything inside rolls back on an exception."""

        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            self._conn.execute("COMMIT")

    def query(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return list(self._conn.execute(sql, params).fetchall())

    def one(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(sql, params).fetchone()

    def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        """Run one statement; returns lastrowid."""

        with self._lock:
            cursor = self._conn.execute(sql, params)
            return int(cursor.lastrowid or 0)

    def insert(self, table: str, values: dict[str, Any]) -> int:
        if table not in TABLES:
            raise ValueError(f"unknown table {table}")
        columns = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        return self.execute(
            f"INSERT INTO {table} ({columns}) VALUES ({marks})", list(values.values())
        )

    def update(
        self, table: str, key: str, key_value: Any, values: dict[str, Any]
    ) -> None:
        if table not in TABLES:
            raise ValueError(f"unknown table {table}")
        assignments = ", ".join(f"{column} = ?" for column in values)
        self.execute(
            f"UPDATE {table} SET {assignments} WHERE {key} = ?",
            [*values.values(), key_value],
        )

    # ---------------------------------------------------------- inventory
    def sessions(self) -> list[sqlite3.Row]:
        return self.query("SELECT * FROM session ORDER BY ended_at")

    def get_session(self, session_id: str) -> sqlite3.Row | None:
        return self.one("SELECT * FROM session WHERE session_id = ?", (session_id,))

    def rooms(self) -> list[sqlite3.Row]:
        return self.query("SELECT * FROM room ORDER BY room_id")

    def anchors(self) -> list[sqlite3.Row]:
        return self.query("SELECT * FROM anchor ORDER BY anchor_id")

    def instances(self) -> list[sqlite3.Row]:
        return self.query("SELECT * FROM instance ORDER BY instance_id")

    def runs_for_instance(self, instance_id: int) -> list[sqlite3.Row]:
        return self.query(
            "SELECT * FROM state_run WHERE instance_id = ? ORDER BY end_at, run_id",
            (instance_id,),
        )

    def counts(self) -> dict[str, int]:
        return {
            table: int(self.one(f"SELECT COUNT(*) FROM {table}")[0]) for table in TABLES
        }

    def db_size_bytes(self) -> int:
        with self._lock:
            self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        return self.path.stat().st_size

    # ------------------------------------------------------- maintenance
    def delete_session_rows(self, session_id: str) -> set[int]:
        """Remove one session's runs, events, visits, activities and evidence."""

        affected = {
            int(row[0])
            for row in self.query(
                "SELECT DISTINCT instance_id FROM state_run WHERE session_id = ?",
                (session_id,),
            )
        }
        for row in self.query(
            "SELECT path FROM evidence WHERE session_id = ?", (session_id,)
        ):
            (self.dir / str(row["path"])).unlink(missing_ok=True)
        for table in ("evidence", "activity", "event", "room_visit", "state_run"):
            self.execute(f"DELETE FROM {table} WHERE session_id = ?", (session_id,))
        self.execute("DELETE FROM session WHERE session_id = ?", (session_id,))
        return affected

    def recompute_last_known(self, instance_id: int) -> None:
        """Last-known state of an instance from its newest remaining run."""

        run = self.one(
            "SELECT * FROM state_run WHERE instance_id = ? "
            "ORDER BY end_at DESC, run_id DESC LIMIT 1",
            (instance_id,),
        )
        if run is None:
            self.update(
                "instance",
                "instance_id",
                instance_id,
                {
                    "last_relation": None,
                    "last_relation_certain": None,
                    "last_anchor_id": None,
                    "last_room_id": None,
                    "last_seen_at": None,
                    "last_confidence": None,
                    "last_height": None,
                    "last_run_id": None,
                    "last_session_id": None,
                    "last_evidence_id": None,
                },
            )
            return
        self.update(
            "instance",
            "instance_id",
            instance_id,
            {
                "last_relation": run["relation"],
                "last_relation_certain": run["relation_certain"],
                "last_anchor_id": run["anchor_id"],
                "last_room_id": run["room_id"],
                "last_seen_at": run["end_at"],
                "last_confidence": run["confidence"],
                "last_height": run["height_above_floor"],
                "last_run_id": run["run_id"],
                "last_session_id": run["session_id"],
                "last_evidence_id": run["evidence_id"],
            },
        )

    # ------------------------------------------------------------ reads
    def activities(
        self, start: str | None = None, end: str | None = None
    ) -> list[dict[str, Any]]:
        """Activities with room names and their event ids, oldest first."""

        where, params = _range_clause("a.end_at", start, end)
        rows = self.query(
            f"""
            SELECT a.*, r.label AS room_label
            FROM activity a LEFT JOIN room r ON r.room_id = a.room_id
            {where}
            ORDER BY a.start_at, a.activity_id
            """,
            params,
        )
        result = []
        for row in rows:
            event_ids = [
                f"event_{e[0]:06d}"
                for e in self.query(
                    "SELECT event_id FROM event WHERE activity_id = ? ORDER BY end_at",
                    (row["activity_id"],),
                )
            ]
            result.append(
                {
                    "activity_id": row["activity_id"],
                    "room_id": row["room_id"],
                    "room_label": row["room_label"],
                    "start_at": row["start_at"],
                    "end_at": row["end_at"],
                    "event_count": row["event_count"],
                    "summary": row["summary"],
                    "events": event_ids,
                    "tier": "detailed",
                }
            )
        return result

    def summaries(
        self, start: str | None = None, end: str | None = None
    ) -> list[dict[str, Any]]:
        """Summarised history whose period overlaps [start, end] (dates)."""

        clauses, params = [], []
        if start is not None:
            clauses.append("period_end >= ?")
            params.append(start[:10])
        if end is not None:
            clauses.append("period_start <= ?")
            params.append(end[:10])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.query(
            f"SELECT * FROM summary {where} ORDER BY period_start, kind, subject_key",
            params,
        )
        return [
            {
                "summary_id": row["summary_id"],
                "level": row["level"],
                "period_start": row["period_start"],
                "period_end": row["period_end"],
                "kind": row["kind"],
                "subject_key": row["subject_key"],
                "text": row["text"],
                "sidecar": json.loads(row["sidecar"]),
                "tier": "summarised",
            }
            for row in rows
        ]

    def latest_states(self) -> list[dict[str, Any]]:
        """Last-known state of every object, with names and ranking features."""

        rows = self.query(
            f"""
            SELECT i.*, a.label AS anchor_label, r.label AS room_label,
                   {_INSTANCE_FEATURES}
            FROM instance i
            LEFT JOIN anchor a ON a.anchor_id = i.last_anchor_id
            LEFT JOIN room r ON r.room_id = i.last_room_id
            WHERE i.last_relation IS NOT NULL
            ORDER BY i.instance_id
            """
        )
        return [self._state_dict(row, row["last_seen_at"]) for row in rows]

    def states_as_of(
        self, as_of: str, *, since: str | None = None
    ) -> list[dict[str, Any]]:
        """Every object's latest state whose run began at or before ``as_of``.

        ``since`` additionally keeps only runs with evidence at or after that
        time, which is a real recency-limited memory: an instance last seen
        before the cutoff disappears entirely instead of falling back to an
        older run of the same instance.
        """

        cutoff = to_utc_iso(as_of)
        since_clause = ""
        params: list[Any] = [cutoff]
        if since is not None:
            since_clause = "AND sr.end_at >= ?"
            params.append(to_utc_iso(since))
        rows = self.query(
            f"""
            WITH ranked AS (
              SELECT sr.*,
                     ROW_NUMBER() OVER (
                       PARTITION BY sr.instance_id
                       ORDER BY sr.start_at DESC, sr.run_id DESC
                     ) AS rn
              FROM state_run sr
              WHERE sr.start_at <= ? {since_clause}
            )
            SELECT ranked.*, i.label AS instance_label, i.canonical,
                   i.importance, a.label AS anchor_label,
                   r.label AS room_label, {_INSTANCE_FEATURES}
            FROM ranked
            JOIN instance i ON i.instance_id = ranked.instance_id
            LEFT JOIN anchor a ON a.anchor_id = ranked.anchor_id
            LEFT JOIN room r ON r.room_id = ranked.room_id
            WHERE ranked.rn = 1
            ORDER BY ranked.instance_id
            """,
            params,
        )
        return [
            self._state_dict(
                row,
                row["end_at"],
                label=row["instance_label"],
                relation=row["relation"],
                certain=bool(row["relation_certain"]),
                anchor_id=row["anchor_id"],
                room_id=row["room_id"],
                confidence=row["confidence"],
                height=row["height_above_floor"],
                evidence_id=row["evidence_id"],
            )
            for row in rows
        ]

    def state_at(
        self, canonical: str, at: str, *, tolerance_s: float = 180.0
    ) -> dict[str, Any] | None:
        """The run of ``canonical`` closest to ``at`` within the tolerance.

        Used by the exact-episodic (T4) oracle: it resolves a reference from a
        timestamp alone, without using the query's expected place.
        """

        moment = parse_iso(at)
        low = to_utc_iso(moment - timedelta(seconds=tolerance_s))
        high = to_utc_iso(moment + timedelta(seconds=tolerance_s))
        rows = self.query(
            f"""
            SELECT sr.*, i.label AS instance_label, i.canonical,
                   i.importance, a.label AS anchor_label,
                   r.label AS room_label, {_INSTANCE_FEATURES}
            FROM state_run sr
            JOIN instance i ON i.instance_id = sr.instance_id
            LEFT JOIN anchor a ON a.anchor_id = sr.anchor_id
            LEFT JOIN room r ON r.room_id = sr.room_id
            WHERE i.canonical = ? AND sr.end_at >= ? AND sr.start_at <= ?
            """,
            (canonical, low, high),
        )
        if not rows:
            return None
        row = min(
            rows,
            key=lambda item: abs(
                (parse_iso(item["start_at"]) - moment).total_seconds()
            ),
        )
        state = self._state_dict(
            row,
            row["end_at"],
            label=row["instance_label"],
            relation=row["relation"],
            certain=bool(row["relation_certain"]),
            anchor_id=row["anchor_id"],
            room_id=row["room_id"],
            confidence=row["confidence"],
            height=row["height_above_floor"],
            evidence_id=row["evidence_id"],
        )
        state["delta_seconds"] = round(
            (parse_iso(row["start_at"]) - moment).total_seconds(), 3
        )
        return state

    def _state_dict(
        self,
        row: sqlite3.Row,
        last_seen: str | None,
        *,
        label: str | None | object = _MISSING,
        relation: str | None | object = _MISSING,
        certain: bool | None | object = _MISSING,
        anchor_id: int | None | object = _MISSING,
        room_id: int | None | object = _MISSING,
        confidence: float | None | object = _MISSING,
        height: float | None | object = _MISSING,
        evidence_id: int | None | object = _MISSING,
    ) -> dict[str, Any]:
        """One JSON-safe state row from a latest or as-of query."""

        def field(name: str, override: object) -> Any:
            return override if override is not _MISSING else row[name]

        moved = field("last_moved_at", _MISSING)
        return {
            "instance_id": row["instance_id"],
            "label": field("label", label),
            "canonical": row["canonical"],
            "relation": field("last_relation", relation),
            "relation_certain": bool(field("last_relation_certain", certain)),
            "anchor_id": field("last_anchor_id", anchor_id),
            "anchor_label": row["anchor_label"],
            "room_id": field("last_room_id", room_id),
            "room_label": row["room_label"],
            "last_seen_wallclock": last_seen,
            "run_start_wallclock": dict(row).get("start_at"),
            "last_seen_timestamp": _epoch(last_seen),
            "last_moved_wallclock": moved,
            "last_moved_timestamp": _epoch(moved),
            "placement_count": int(row["placement_count"] or 0),
            "pickup_count": int(row["pickup_count"] or 0),
            "observation_count": int(row["observation_count"] or 0),
            "first_seen_wallclock": row["first_seen_at"],
            "first_room_id": row["first_room_id"],
            "first_anchor_id": row["first_anchor_id"],
            "confidence": field("last_confidence", confidence),
            "height_above_floor": field("last_height", height),
            "is_active_view": False,
            "evidence_id": field("last_evidence_id", evidence_id),
        }

    def events(
        self, start: str | None = None, end: str | None = None
    ) -> list[dict[str, Any]]:
        """Events (detailed tier) with names resolved, ordered by end time."""

        clauses, params = [], []
        if start is not None:
            clauses.append("e.end_at >= ?")
            params.append(to_utc_iso(start))
        if end is not None:
            clauses.append("e.end_at <= ?")
            params.append(to_utc_iso(end))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.query(
            f"""
            SELECT e.*, i.label AS object_label,
                   fa.label AS from_anchor_label, ta.label AS to_anchor_label,
                   fr.label AS from_room_label, tr.label AS to_room_label
            FROM event e
            LEFT JOIN instance i ON i.instance_id = e.instance_id
            LEFT JOIN anchor fa ON fa.anchor_id = e.from_anchor_id
            LEFT JOIN anchor ta ON ta.anchor_id = e.to_anchor_id
            LEFT JOIN room fr ON fr.room_id = e.from_room_id
            LEFT JOIN room tr ON tr.room_id = e.to_room_id
            {where}
            ORDER BY e.end_at, e.event_id
            """,
            params,
        )
        return [
            {
                "event_id": f"event_{row['event_id']:06d}",
                "event_type": row["event_type"],
                "instance_id": row["instance_id"],
                "object": row["object_label"] or "Camera Wearer",
                "source_relation": row["from_relation"],
                "destination_relation": row["to_relation"],
                "source_anchor": row["from_anchor_label"],
                "destination_anchor": row["to_anchor_label"],
                "source_anchor_id": row["from_anchor_id"],
                "destination_anchor_id": row["to_anchor_id"],
                "source_room": row["from_room_label"],
                "destination_room": row["to_room_label"],
                "source_room_id": row["from_room_id"],
                "destination_room_id": row["to_room_id"],
                "start_wallclock": row["start_at"],
                "end_wallclock": row["end_at"],
                "confidence": row["confidence"],
                "activity_id": row["activity_id"],
                "session_id": row["session_id"],
            }
            for row in rows
        ]


def _range_clause(
    column: str, start: str | None, end: str | None
) -> tuple[str, list[str]]:
    clauses, params = [], []
    if start is not None:
        clauses.append(f"{column} >= ?")
        params.append(to_utc_iso(start))
    if end is not None:
        clauses.append(f"{column} <= ?")
        params.append(to_utc_iso(end))
    return (f"WHERE {' AND '.join(clauses)}" if clauses else ""), params


def open_store(home_id: str, store_root: str | Path | None = None) -> HomeStore:
    """Open (creating if needed) the store of one home.

    This is the only place a database connection is created, so encryption
    at rest (Milestone 4) can replace ``sqlite3`` here.
    """

    directory = home_dir(home_id, store_root)
    directory.mkdir(parents=True, exist_ok=True)
    store = HomeStore(home_id, directory / "memory.db")
    if not store.rooms():
        # Restore caregiver room names when the database was lost or reset.
        from aegis.memory.home_registry import load_registry, seed_store_from_registry

        seed_store_from_registry(store, load_registry(home_id, directory.parent))
    return store


def dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True)
