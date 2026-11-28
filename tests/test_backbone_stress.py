"""Stress tests for the query backbone across all datasets and edge inputs."""

from __future__ import annotations

import json
import math
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from aegis.core.config import ConfidenceConfig, RankingConfig
from aegis.memory.reasoning import rank_candidates
from aegis.memory.repository import latest_states_from_graph
from aegis.remote.api import app

DATASETS = (
    "demo01_sam3",
    "demo_pots_sam3",
    "demo03_sam3",
    "demo04_sam3",
    "demo05_sam3",
)
QUERIES = (
    "shoes",
    "cooking pot",
    "clothes",
    "basket",
    "bottle",
    "plate",
    "toilet",
    "my mug",
    "shoes in the kitchen",
    "the red mug",
    "",
    "   ",
    "a completely unknown object",
    "objeto inexistente",
    "物品",
)
VALID_MODES = {"direct", "disambiguate", "abstain", "not_found", None}


def graphs() -> dict[str, list[dict[str, Any]]]:
    result = {}
    for dataset_id in DATASETS:
        path = Path("outputs") / dataset_id / "objects" / "r4d_scene_graph.json"
        if not path.exists():
            continue
        graph = json.loads(path.read_text())
        result[dataset_id] = list(latest_states_from_graph(graph).values())
    return result


def test_all_dataset_query_endpoints() -> None:
    client = TestClient(app)
    for dataset_id in DATASETS:
        for query in QUERIES:
            response = client.get(
                "/api/v1/query", params={"item": query, "dataset_id": dataset_id}
            )
            assert response.status_code == 200, (dataset_id, query)
            body = response.json()
            assert isinstance(body["found"], bool)
            assert body.get("resolution_mode") in VALID_MODES
            assert len(body.get("candidates", [])) <= 3
            confidence = body.get("confidence")
            assert confidence is None or (
                math.isfinite(confidence) and 0.0 <= confidence <= 1.0
            )


def test_all_dataset_ask_endpoints() -> None:
    client = TestClient(app)
    for dataset_id in DATASETS:
        for query in QUERIES[:10]:
            response = client.get(
                "/api/v1/ask", params={"text": query, "dataset_id": dataset_id}
            )
            assert response.status_code == 200, (dataset_id, query)
            body = response.json()
            assert isinstance(body["abstained"], bool)
            assert isinstance(body["answer"], str)
            confidence = body.get("confidence")
            assert confidence is None or 0.0 <= confidence <= 1.0


def test_ranker_modes_and_configs_finite_on_every_dataset() -> None:
    configs = (
        (RankingConfig(), ConfidenceConfig()),
        (RankingConfig(), replace(ConfidenceConfig(), uncertain_identity=0.0)),
        (
            replace(
                RankingConfig(),
                anchorless_penalty=0.5,
                carried_penalty=0.5,
                require_anchor_for_direct=True,
            ),
            ConfidenceConfig(),
        ),
    )
    for states in graphs().values():
        for ranking_config, confidence_config in configs:
            for mode in ("recency_only", "salience", "full"):
                for query in ("shoes", "cooking pot", "clothes", "toilet"):
                    ranked = rank_candidates(
                        states,
                        query,
                        mode=mode,
                        config=ranking_config,
                        confidence_config=confidence_config,
                    )
                    assert ranked["resolution_mode"] in VALID_MODES - {None}
                    for candidate in ranked["candidates"]:
                        assert math.isfinite(candidate["score"])
                        assert 0.0 <= candidate["confidence"] <= 1.0


def test_graph_enrichment_is_deterministic_and_bounded() -> None:
    for dataset_id, states in graphs().items():
        assert states
        for state in states:
            assert isinstance(state.get("observation_count", 0), int)
            seen = state.get("last_seen_wallclock")
            assert seen is None or isinstance(seen, str)
            ref = state.get("reference_relative")
            assert ref is None or ref >= 0
        again = graphs()[dataset_id]
        assert [s.get("instance_id") for s in states] == [
            s.get("instance_id") for s in again
        ]


def test_empty_and_malformed_graphs_do_not_crash() -> None:
    empty = latest_states_from_graph(
        {
            "latest_states": [],
            "state_runs": [],
            "events": [],
        }
    )
    assert empty == {}
    assert rank_candidates([], "shoes")["resolution_mode"] == "not_found"

    malformed = latest_states_from_graph(
        {
            "latest_states": [
                {"instance_id": 1, "canonical": "mug", "label": "Mug #1"},
                {"instance_id": 2, "label": "Broken"},
                {"not_an_instance": 3},
            ],
            "state_runs": [{"instance_id": 1, "end_time": "bad"}],
            "events": [{"instance_id": 1, "event_type": "placement"}],
        }
    )
    assert set(malformed) == {1, 2}
    ranked = rank_candidates(list(malformed.values()), "mug")
    assert ranked["resolution_mode"] in VALID_MODES - {None}


def test_v1_timeline_graph_still_readable() -> None:
    graph = {
        "timeline": {
            "0": [{"instance_id": 1, "label": "Shoes #1", "canonical": "shoes"}],
            "1": [{"instance_id": 1, "label": "Shoes #1", "canonical": "shoes"}],
        }
    }
    states = latest_states_from_graph(graph)
    assert set(states) == {1}
    assert states[1]["label"] == "Shoes #1"


@pytest.mark.parametrize("bad", ["", "   ", "\x00", "a" * 5000])
def test_pathological_query_strings(bad: str) -> None:
    ranked = rank_candidates([], bad)
    assert ranked["resolution_mode"] == "not_found"
