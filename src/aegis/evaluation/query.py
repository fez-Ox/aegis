"""Query, persistence, and ablation scoring for the R4DSG memory.

The query path intentionally reuses the same matching and reasoning helpers as
the FastAPI gateway.  That keeps the evaluation honest: a score reflects the
production answer logic, not a separate "evaluation-only" query engine.
"""

from __future__ import annotations

import copy
import time
from collections.abc import Sequence
from typing import Any

import numpy as np

from aegis.evaluation.metrics import normalise_label, normalise_room, wilson_interval
from aegis.evaluation.schema import PersistenceCase, QuerySpec


def answer_query(
    graph: dict[str, Any],
    query: str,
    dataset_id: str = "evaluation",
) -> dict[str, Any]:
    """Answer one query against an in-memory scene graph.

    This mirrors ``aegis.remote.api.query_memory`` but accepts a graph object
    directly so the same question can be asked of ablated or compacted
    memories.
    """

    from aegis.memory.reasoning import QueryReasoningEngine
    from aegis.remote.api import _matches_query, find_latest_objects_state

    latest_states = find_latest_objects_state(graph)
    events = graph.get("events", [])
    canonical_item = QueryReasoningEngine.extract_target_item(query)
    room_filter = QueryReasoningEngine.extract_room_filter(query)

    matches = [
        state
        for state in latest_states.values()
        if _matches_query(state, canonical_item, query)
    ]
    if not matches:
        available = sorted(
            {
                state.get("label", "")
                for state in latest_states.values()
                if state.get("label")
            }
        )
        reason = f"I couldn't locate any '{query}' in {dataset_id}."
        if available:
            reason += f" Available items in {dataset_id}: {', '.join(available)}."
        return {
            "query": query,
            "found": False,
            "item": None,
            "instance_label": None,
            "instance_id": None,
            "anchor_id": None,
            "anchor_label": None,
            "room_id": None,
            "room_label": None,
            "relation": None,
            "location_summary": reason,
            "explanation": reason,
            "is_persistent_memory": False,
            "last_seen_timestamp_s": None,
        }

    if room_filter:
        room_filter_clean = " ".join(room_filter.split())
        room_matches = [
            match
            for match in matches
            if room_filter_clean in str(match.get("room_label", "")).lower()
        ]
        if not room_matches:
            known_rooms = sorted(
                {
                    str(match.get("room_label"))
                    for match in matches
                    if match.get("room_label")
                }
            )
            reason = (
                f"I couldn't find any '{canonical_item}' in the {room_filter_clean}."
            )
            if known_rooms:
                reason += f" It was last seen in {', '.join(known_rooms)}."
            return {
                "query": query,
                "found": False,
                "item": query,
                "instance_label": None,
                "instance_id": None,
                "anchor_id": None,
                "anchor_label": None,
                "room_id": None,
                "room_label": None,
                "relation": None,
                "location_summary": reason,
                "explanation": reason,
                "is_persistent_memory": False,
                "last_seen_timestamp_s": None,
            }
        matches = room_matches

    def sort_key(state: dict[str, Any]) -> tuple[int, int, float]:
        label = state.get("label", "").lower()
        exact_match = int(
            canonical_item.lower() in label or query.lower().strip() in label
        )
        is_active = 1 if "active" in label else 0
        timestamp = float(state.get("last_seen_timestamp", 0.0))
        return (exact_match, is_active, timestamp)

    matches.sort(key=sort_key, reverse=True)
    primary = matches[0]
    reasoning = QueryReasoningEngine.reason_spatio_temporal_state(
        canonical_item, primary, events
    )
    return {
        "query": query,
        "found": True,
        "item": query,
        "instance_label": primary.get("label"),
        "instance_id": primary.get("instance_id"),
        "anchor_id": primary.get("anchor_id"),
        "anchor_label": reasoning["anchor_label"],
        "room_id": primary.get("room_id"),
        "room_label": primary.get("room_label"),
        "relation": reasoning["relation"],
        "location_summary": reasoning["explanation"],
        "explanation": reasoning["explanation"],
        "is_persistent_memory": reasoning["is_persistent_memory"],
        "last_seen_timestamp_s": primary.get("last_seen_timestamp"),
    }


# ---------------------------------------------------------------------------
# Query scoring
# ---------------------------------------------------------------------------


def _relation_matches(
    expected: str | None,
    actual: str | None,
    aliases: dict[str, str] | None,
) -> bool:
    if not expected:
        return True
    if not actual:
        return False
    alias_map = {
        "on": "on_surface",
        "on top": "on_surface",
        "carried": "carried_by_user",
        "floor": "on_floor",
    }
    alias_map.update(aliases or {})
    expected_clean = alias_map.get(expected.lower().strip(), expected.lower().strip())
    actual_clean = alias_map.get(actual.lower().strip(), actual.lower().strip())
    return expected_clean == actual_clean


def _expected_fields_match(
    answer: dict[str, Any],
    query: QuerySpec,
    *,
    aliases: dict[str, str] | None,
    relation_aliases: dict[str, str] | None,
) -> tuple[bool, str | None]:
    if not answer.get("found"):
        return False, "not_found"
    if query.expected_instance_label:
        expected = normalise_label(query.expected_instance_label, aliases)
        actual = normalise_label(answer.get("instance_label"), aliases)
        if expected != actual:
            return False, f"instance_label expected {expected!r}, got {actual!r}"
    if query.expected_anchor:
        expected = normalise_label(query.expected_anchor, aliases)
        actual = normalise_label(answer.get("anchor_label"), aliases)
        if expected != actual:
            return False, f"anchor expected {expected!r}, got {actual!r}"
    if query.expected_room:
        expected = normalise_room(query.expected_room, aliases)
        actual = normalise_room(answer.get("room_label"), aliases)
        if expected != actual:
            return False, f"room expected {expected!r}, got {actual!r}"
    if query.expected_relation and not _relation_matches(
        query.expected_relation, answer.get("relation"), relation_aliases
    ):
        return (
            False,
            f"relation expected {query.expected_relation!r}, got {answer.get('relation')!r}",
        )
    return True, None


def _latency_summary(values: Sequence[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "p50_ms": None, "p95_ms": None, "max_ms": None}
    array = np.asarray(values, dtype=np.float64)
    return {
        "count": int(array.size),
        "p50_ms": float(np.percentile(array, 50)),
        "p95_ms": float(np.percentile(array, 95)),
        "max_ms": float(np.max(array)),
        "mean_ms": float(np.mean(array)),
    }


def evaluate_queries(
    graph: dict[str, Any],
    queries: Sequence[QuerySpec],
    *,
    dataset_id: str = "evaluation",
    query_mode: str = "graph",
    aliases: dict[str, str] | None = None,
    relation_aliases: dict[str, str] | None = None,
    client: Any = None,
) -> dict[str, Any]:
    """Score the question bank, including latency and false-found rates."""

    if query_mode not in {"graph", "api"}:
        raise ValueError("query_mode must be 'graph' or 'api'")

    if query_mode == "api" and client is None:
        from fastapi.testclient import TestClient

        from aegis.remote.api import app

        client = TestClient(app)

    results: list[dict[str, Any]] = []
    latencies: list[float] = []
    for query in queries:
        start = time.perf_counter()
        if query_mode == "api":
            response = client.get(
                "/api/v1/query", params={"item": query.query, "dataset_id": dataset_id}
            )
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            if response.status_code != 200:
                answer = {
                    "found": False,
                    "error": f"HTTP {response.status_code}: {response.text[:200]}",
                }
            else:
                answer = response.json()
        else:
            answer = answer_query(graph, query.query, dataset_id)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
        latencies.append(elapsed_ms)

        found = bool(answer.get("found", False))
        found_correct = found == query.expected_found
        fields_correct, reason = _expected_fields_match(
            answer,
            query,
            aliases=aliases,
            relation_aliases=relation_aliases,
        )
        grounded_correct = not found if not query.expected_found else fields_correct
        false_found = (not query.expected_found) and found
        false_not_found = query.expected_found and not found
        if not grounded_correct and reason is None:
            reason = "unexpected_found" if false_found else "not_found"
        results.append(
            {
                "query_id": query.query_id,
                "query": query.query,
                "expected_found": query.expected_found,
                "actual_found": found,
                "found_correct": found_correct,
                "grounded_correct": grounded_correct,
                "failure_reason": None if grounded_correct else reason,
                "expected": {
                    "anchor": query.expected_anchor,
                    "room": query.expected_room,
                    "relation": query.expected_relation,
                    "instance_label": query.expected_instance_label,
                },
                "actual": {
                    "instance_label": answer.get("instance_label"),
                    "anchor": answer.get("anchor_label"),
                    "room": answer.get("room_label"),
                    "relation": answer.get("relation"),
                    "location_summary": answer.get("location_summary"),
                },
                "latency_ms": elapsed_ms,
            }
        )

    total = len(results)
    answered_correctly = sum(1 for result in results if result["grounded_correct"])
    found_correct = sum(1 for result in results if result["found_correct"])
    false_found = sum(
        1
        for result in results
        if not result["expected_found"] and result["actual_found"]
    )
    false_not_found = sum(
        1
        for result in results
        if result["expected_found"] and not result["actual_found"]
    )
    return {
        "available": True,
        "query_mode": query_mode,
        "counts": {
            "total": total,
            "grounded_correct": answered_correctly,
            "found_correct": found_correct,
            "false_found": false_found,
            "false_not_found": false_not_found,
        },
        "answer_accuracy": answered_correctly / total if total else 0.0,
        "answer_accuracy_ci": wilson_interval(answered_correctly, total),
        "found_accuracy": found_correct / total if total else 0.0,
        "false_found_rate": false_found / total if total else 0.0,
        "false_not_found_rate": false_not_found / total if total else 0.0,
        "latency": _latency_summary(latencies),
        "queries": results,
        "failures": [result for result in results if not result["grounded_correct"]],
    }


# ---------------------------------------------------------------------------
# Persistence / object permanence
# ---------------------------------------------------------------------------


def timeline_frames(graph: dict[str, Any]) -> list[int]:
    try:
        return sorted(int(frame) for frame in graph.get("timeline", {}))
    except (TypeError, ValueError):
        return sorted(graph.get("timeline", {}), key=str)


def frame_timestamp(graph: dict[str, Any], frame_id: int) -> float:
    entries = graph.get("timeline", {}).get(str(frame_id), [])
    if entries:
        return float(entries[0].get("timestamp", 0.0))
    entries = graph.get("timeline", {}).get(frame_id, [])
    if entries:
        return float(entries[0].get("timestamp", 0.0))
    return 0.0


def graph_at_frame(graph: dict[str, Any], frame_id: int) -> dict[str, Any]:
    """Return a graph slice containing only memory known at ``frame_id``."""

    frames = timeline_frames(graph)
    if not frames:
        return copy.deepcopy(graph)
    resolved = max((frame for frame in frames if frame <= frame_id), default=frames[0])
    timestamp = frame_timestamp(graph, resolved)
    sliced = {
        "dataset_id": graph.get("dataset_id", "evaluation"),
        "anchors": copy.deepcopy(graph.get("anchors", [])),
        "rooms": copy.deepcopy(graph.get("rooms", [])),
        "timeline": {
            str(resolved): copy.deepcopy(graph["timeline"].get(str(resolved), []))
        },
        "events": copy.deepcopy(
            [
                event
                for event in graph.get("events", [])
                if float(event.get("start_time", 0.0)) <= timestamp + 1e-9
            ]
        ),
    }
    return sliced


def _find_entry(
    graph: dict[str, Any],
    *,
    frame_id: int,
    instance_id: int | None,
    label: str | None,
    aliases: dict[str, str] | None,
) -> tuple[int | None, dict[str, Any] | None]:
    frames = timeline_frames(graph)
    candidates = [frame for frame in frames if frame <= frame_id] or frames
    for frame in reversed(candidates):
        entries = graph.get("timeline", {}).get(str(frame), [])
        for entry in entries:
            if instance_id is not None:
                if entry.get("instance_id") == instance_id:
                    return frame, entry
                continue
            expected = normalise_label(label, aliases) if label else ""
            if expected and normalise_label(entry.get("label"), aliases) == expected:
                return frame, entry
    return None, None


def _state_matches(
    entry: dict[str, Any],
    case: PersistenceCase,
    *,
    aliases: dict[str, str] | None,
    relation_aliases: dict[str, str] | None,
) -> tuple[bool, str | None]:
    if case.expected_label:
        expected = normalise_label(case.expected_label, aliases)
        actual = normalise_label(entry.get("label"), aliases)
        if expected != actual:
            return False, f"label expected {expected!r}, got {actual!r}"
    if (
        case.expected_instance_id is not None
        and entry.get("instance_id") != case.expected_instance_id
    ):
        return False, "wrong_instance_id"
    if case.expected_anchor:
        expected = normalise_label(case.expected_anchor, aliases)
        actual = normalise_label(entry.get("anchor_label"), aliases)
        if expected != actual:
            return False, f"anchor expected {expected!r}, got {actual!r}"
    if case.expected_room:
        expected = normalise_room(case.expected_room, aliases)
        actual = normalise_room(entry.get("room_label"), aliases)
        if expected != actual:
            return False, f"room expected {expected!r}, got {actual!r}"
    if case.expected_relation and not _relation_matches(
        case.expected_relation, entry.get("relation"), relation_aliases
    ):
        return False, f"relation expected {case.expected_relation!r}"
    if case.expect_persistent and entry.get("is_active_view"):
        return False, "expected_persistent_memory_but_entry_is_active"
    return True, None


def evaluate_persistence(
    graph: dict[str, Any],
    cases: Sequence[PersistenceCase],
    *,
    aliases: dict[str, str] | None = None,
    relation_aliases: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Score whether occluded/relocated objects stay queryable and correctly located."""

    results: list[dict[str, Any]] = []
    state_correct = 0
    query_correct = 0
    identity_correct = 0
    false_merges = 0
    for case in cases:
        frames = timeline_frames(graph)
        if case.check_frame is not None:
            check_frame = case.check_frame
        elif case.occlusion_end is not None:
            eligible = [
                frame
                for frame in frames
                if frame_timestamp(graph, frame) >= case.occlusion_end - 1e-6
            ]
            check_frame = eligible[0] if eligible else (frames[-1] if frames else 0)
        else:
            check_frame = frames[-1] if frames else 0

        resolved_frame, entry = _find_entry(
            graph,
            frame_id=check_frame,
            instance_id=case.expected_instance_id,
            label=case.expected_label or case.query,
            aliases=aliases,
        )
        if entry is None:
            results.append(
                {
                    "case_id": case.case_id,
                    "query": case.query,
                    "check_frame": check_frame,
                    "resolved_frame": None,
                    "state_correct": False,
                    "query_correct": False,
                    "identity_correct": False,
                    "failure_reason": "no_memory_entry",
                }
            )
            continue

        state_ok, state_reason = _state_matches(
            entry,
            case,
            aliases=aliases,
            relation_aliases=relation_aliases,
        )
        state_correct += int(state_ok)
        if case.expected_instance_id is not None:
            identity_ok = entry.get("instance_id") == case.expected_instance_id
            identity_correct += int(identity_ok)
        else:
            identity_ok = True
            identity_correct += 1
        if case.expected_label:
            merged = normalise_label(entry.get("label"), aliases) != normalise_label(
                case.expected_label, aliases
            )
            false_merges += int(merged)

        answer = answer_query(
            graph_at_frame(graph, check_frame),
            case.query,
            graph.get("dataset_id", "evaluation"),
        )
        query_ok, query_reason = _expected_fields_match(
            answer,
            QuerySpec(
                query_id=case.case_id,
                query=case.query,
                expected_found=True,
                expected_anchor=case.expected_anchor,
                expected_room=case.expected_room,
                expected_relation=case.expected_relation,
                expected_instance_label=case.expected_label,
            ),
            aliases=aliases,
            relation_aliases=relation_aliases,
        )
        query_correct += int(query_ok)
        failure_reason = state_reason or query_reason
        results.append(
            {
                "case_id": case.case_id,
                "query": case.query,
                "check_frame": check_frame,
                "resolved_frame": resolved_frame,
                "state_correct": state_ok,
                "query_correct": query_ok,
                "identity_correct": identity_ok,
                "expected": {
                    "instance_id": case.expected_instance_id,
                    "label": case.expected_label,
                    "anchor": case.expected_anchor,
                    "room": case.expected_room,
                    "relation": case.expected_relation,
                },
                "actual": {
                    "instance_id": entry.get("instance_id"),
                    "label": entry.get("label"),
                    "anchor": entry.get("anchor_label"),
                    "room": entry.get("room_label"),
                    "relation": entry.get("relation"),
                    "is_active_view": entry.get("is_active_view"),
                    "last_seen_timestamp": entry.get("last_seen_timestamp"),
                },
                "failure_reason": None if (state_ok and query_ok) else failure_reason,
            }
        )

    total = len(cases)
    return {
        "available": bool(cases),
        "counts": {
            "total": total,
            "state_correct": state_correct,
            "query_correct": query_correct,
            "identity_correct": identity_correct,
            "false_merges": false_merges,
        },
        "state_recall": state_correct / total if total else 0.0,
        "state_recall_ci": wilson_interval(state_correct, total),
        "query_recall": query_correct / total if total else 0.0,
        "query_recall_ci": wilson_interval(query_correct, total),
        "identity_consistency": identity_correct / total if total else 0.0,
        "false_merge_rate": false_merges / total if total else 0.0,
        "cases": results,
        "failures": [
            result
            for result in results
            if not (result["state_correct"] and result["query_correct"])
        ],
    }


# ---------------------------------------------------------------------------
# Ablations and leakage
# ---------------------------------------------------------------------------


def apply_ablation(graph: dict[str, Any], name: str) -> dict[str, Any]:
    """Return a copy of the graph with one memory component disabled."""

    if name in {"full", "none", ""}:
        return copy.deepcopy(graph)

    ablated = copy.deepcopy(graph)
    if name == "no_rooms":
        ablated["rooms"] = []
        for anchor in ablated.get("anchors", []):
            anchor.pop("room_id", None)
            anchor.pop("room_label", None)
        for entries in ablated.get("timeline", {}).values():
            for entry in entries:
                entry.pop("room_id", None)
                entry.pop("room_label", None)
        for event in ablated.get("events", []):
            event.pop("source_room", None)
            event.pop("destination_room", None)
        return ablated

    if name == "no_events":
        ablated["events"] = []
        return ablated

    if name == "no_persistence":
        filtered_timeline = {}
        for frame, entries in ablated.get("timeline", {}).items():
            active = [entry for entry in entries if entry.get("is_active_view", True)]
            if active:
                filtered_timeline[frame] = active
        ablated["timeline"] = filtered_timeline
        ablated["events"] = []
        return ablated

    if name == "no_memory":
        frames = timeline_frames(ablated)
        if not frames:
            ablated["timeline"] = {}
            ablated["events"] = []
            return ablated
        last_frame = frames[-1]
        active = [
            entry
            for entry in ablated.get("timeline", {}).get(str(last_frame), [])
            if entry.get("is_active_view", True)
        ]
        ablated["timeline"] = {str(last_frame): active} if active else {}
        ablated["events"] = []
        return ablated

    raise ValueError(f"Unknown ablation {name!r}")


def evaluate_ablations(
    graph: dict[str, Any],
    queries: Sequence[QuerySpec],
    cases: Sequence[PersistenceCase],
    *,
    aliases: dict[str, str] | None = None,
    relation_aliases: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Compare full memory against no-persistence, no-memory, and no-rooms."""

    results: dict[str, Any] = {}
    for name in ("full", "no_persistence", "no_memory", "no_rooms"):
        transformed = apply_ablation(graph, name)
        query_result = evaluate_queries(
            transformed,
            queries,
            dataset_id=graph.get("dataset_id", "evaluation"),
            aliases=aliases,
            relation_aliases=relation_aliases,
        )
        persistence_result = evaluate_persistence(
            transformed,
            cases,
            aliases=aliases,
            relation_aliases=relation_aliases,
        )
        results[name] = {
            "answer_accuracy": query_result["answer_accuracy"],
            "answer_accuracy_ci": query_result["answer_accuracy_ci"],
            "found_accuracy": query_result["found_accuracy"],
            "false_found": query_result["counts"]["false_found"],
            "false_not_found": query_result["counts"]["false_not_found"],
            "persistence_state_recall": persistence_result["state_recall"],
            "persistence_query_recall": persistence_result["query_recall"],
            "identity_consistency": persistence_result["identity_consistency"],
        }
    return results


def _synonym_groups() -> dict[str, set[str]]:
    from aegis.memory.reasoning import QueryReasoningEngine

    groups: dict[str, set[str]] = {}
    for canonical, synonyms in QueryReasoningEngine.ITEM_SYNONYMS.items():
        group = {normalise_label(canonical)} | {
            normalise_label(synonym) for synonym in synonyms
        }
        groups[canonical] = group
    return groups


def _label_group(label: str, groups: dict[str, set[str]]) -> set[str]:
    normalised = normalise_label(label)
    for group in groups.values():
        if normalised in group:
            return group
    return {normalised}


def evaluate_leakage(
    graphs: dict[str, dict[str, Any]],
    *,
    aliases: dict[str, str] | None = None,
    extra_probes: Sequence[str] = (),
) -> dict[str, Any]:
    """Check that each dataset answers only from its own memory.

    For every pair of datasets, query the target with labels that are unique
    to the source.  A found answer is leakage.  Synonym groups are respected so
    ``bottle`` in one dataset is not counted as leakage when the target has
    ``water bottle``.
    """

    groups = _synonym_groups()
    cases = 0
    leaks: list[dict[str, Any]] = []
    per_dataset: dict[str, Any] = {}
    for target_id, target_graph in graphs.items():
        target_labels: set[str] = set()
        for state in _latest_states(target_graph):
            target_labels.add(normalise_label(state.get("label"), aliases))
        target_groups: set[str] = set()
        for label in target_labels:
            target_groups.update(_label_group(label, groups))

        probes: set[str] = set()
        for source_id, source_graph in graphs.items():
            if source_id == target_id:
                continue
            for state in _latest_states(source_graph):
                label = normalise_label(state.get("label"), aliases)
                if not label or label in target_labels:
                    continue
                if _label_group(label, groups) & target_groups:
                    continue
                probes.add(label)
        for probe in extra_probes:
            if normalise_label(probe, aliases) not in target_labels:
                probes.add(normalise_label(probe, aliases))

        dataset_cases = 0
        dataset_leaks = 0
        for probe in sorted(probes):
            dataset_cases += 1
            answer = answer_query(target_graph, probe, target_id)
            if answer.get("found"):
                dataset_leaks += 1
                leaks.append(
                    {
                        "target_dataset": target_id,
                        "probe": probe,
                        "answer": {
                            "instance_label": answer.get("instance_label"),
                            "anchor": answer.get("anchor_label"),
                            "summary": answer.get("location_summary"),
                        },
                    }
                )
        cases += dataset_cases
        per_dataset[target_id] = {
            "probes": dataset_cases,
            "leaks": dataset_leaks,
            "leakage_rate": dataset_leaks / dataset_cases if dataset_cases else 0.0,
        }
    return {
        "cases": cases,
        "leaks": len(leaks),
        "leakage_rate": len(leaks) / cases if cases else 0.0,
        "per_dataset": per_dataset,
        "examples": leaks[:20],
    }


def _latest_states(graph: dict[str, Any]) -> list[dict[str, Any]]:
    from aegis.remote.api import find_latest_objects_state

    return list(find_latest_objects_state(graph).values())
