"""Tests for the Option C readiness scorer and Ego4D-style temporal scoring."""

from __future__ import annotations

import pytest

from aegis.evaluation.option_c import (
    BoxObservation,
    NLQAnnotation,
    NLQPrediction,
    adapter_contract,
    score_nlq,
    score_readiness,
    score_vq2d,
    temporal_iou,
)


def test_temporal_iou_exact_partial_and_disjoint() -> None:
    assert temporal_iou((1.0, 3.0), (1.0, 3.0)) == pytest.approx(1.0)
    assert temporal_iou((1.0, 3.0), (2.0, 4.0)) == pytest.approx(1 / 3)
    assert temporal_iou((1.0, 2.0), (5.0, 6.0)) == 0.0
    assert temporal_iou((3.0, 1.0), (1.0, 3.0)) == pytest.approx(1.0)


def test_score_nlq_recall_at_thresholds() -> None:
    annotations = [
        NLQAnnotation("q1", "where are my shoes", 1.0, 3.0),
        NLQAnnotation("q2", "when did i sit down", 10.0, 14.0),
        NLQAnnotation("q3", "where is the bottle", 20.0, 25.0),
    ]
    predictions = [
        NLQPrediction("q1", 1.0, 3.0),  # IoU 1.0
        NLQPrediction("q2", 10.0, 12.0),  # IoU 0.5
        # q3 is missing entirely.
    ]
    result = score_nlq(annotations, predictions, thresholds=(0.3, 0.5, 0.7))
    assert result["counts"]["queries"] == 3
    assert result["counts"]["missing_predictions"] == 1
    assert result["recall_at"]["0.3"] == pytest.approx(2 / 3)
    assert result["recall_at"]["0.5"] == pytest.approx(2 / 3)
    assert result["recall_at"]["0.7"] == pytest.approx(1 / 3)
    assert result["mean_temporal_iou"] == pytest.approx(0.5)
    assert result["queries"][2]["prediction"] is None


def test_score_vq2d_matches_boxes_by_time() -> None:
    ground_truth = [
        BoxObservation(0.0, (0.0, 0.0, 10.0, 10.0)),
        BoxObservation(1.0, (20.0, 20.0, 30.0, 30.0)),
    ]
    predictions = [
        BoxObservation(0.1, (0.0, 0.0, 10.0, 10.0)),
        BoxObservation(1.2, (20.0, 20.0, 30.0, 30.0)),
    ]
    result = score_vq2d(ground_truth, predictions, time_tolerance_s=0.25)
    assert result["presence_rate"] == pytest.approx(1.0)
    assert result["mean_iou"] == pytest.approx(1.0)
    assert result["fraction_at_or_above_threshold"] == pytest.approx(1.0)

    late = score_vq2d(
        ground_truth,
        [BoxObservation(5.0, (0.0, 0.0, 10.0, 10.0))],
        time_tolerance_s=0.25,
    )
    assert late["presence_rate"] == pytest.approx(0.0)


def test_readiness_decisions_are_monotonic() -> None:
    from aegis.evaluation.option_c import DEFAULT_FACTS

    all_true = {fact.key: True for fact in DEFAULT_FACTS}
    go = score_readiness(all_true)
    assert go["decision"] == "go"
    assert go["readiness_score"] == pytest.approx(100.0)
    assert go["blockers_missing"] == []

    none = score_readiness({})
    assert none["decision"] == "no_go"
    assert none["readiness_score"] == pytest.approx(0.0)
    assert len(none["blockers_missing"]) == 4

    # Every non-blocker is satisfied, plus the licence blocker. The remaining
    # data/engineering blockers keep the decision at conditional-go.
    partial_facts = {
        fact.key: (not fact.blocker) or fact.key == "license_approved"
        for fact in DEFAULT_FACTS
    }
    partial = score_readiness(partial_facts)
    assert partial["decision"] == "conditional_go"
    assert partial["blockers_missing"] == [
        "video_subset_downloaded",
        "annotations_downloaded",
        "adapter_implemented",
    ]


def test_unknown_readiness_fact_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown readiness facts"):
        score_readiness({"made_up_fact": True})


def test_adapter_contract_states_official_parity_requirement() -> None:
    contract = adapter_contract()
    assert contract["scoring"]["official_parity_required"]
    assert "test split" in " ".join(contract["must_not_do"])
    assert contract["clip_record"]["required"][0] == "clip_uid"
