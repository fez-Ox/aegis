"""Tests for generic answer-confidence calibration and abstention (P1.2)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from aegis.core.config import ConfidenceConfig, RankingConfig
from aegis.memory.reasoning import calibrated_confidence, rank_candidates

NOW = datetime(2026, 1, 11, 12, 59, tzinfo=UTC)


def state(**extra):
    base = {
        "instance_id": 1,
        "label": "Mug #1",
        "canonical": "mug",
        "room_id": 1,
        "room_label": "Kitchen",
        "anchor_id": 1,
        "anchor_label": "Counter #1",
        "relation": "on_surface",
        "relation_certain": True,
        "confidence": 0.9,
        "last_seen_wallclock": "2026-01-11T12:00:00+00:00",
        "observation_count": 5,
        "evidence_id": 7,
    }
    base.update(extra)
    return base


def test_calibration_factors_are_bounded_and_explained() -> None:
    result = calibrated_confidence(state(), NOW)
    assert 0.0 <= result["score"] <= 1.0
    assert result["reason"] is None
    assert result["detection"] == 0.9
    assert result["identity"] == 1.0
    assert result["support"] == 1.0
    assert 0.0 < result["recency"] <= 1.0


def test_uncertain_relation_vetoes_a_direct_answer() -> None:
    result = calibrated_confidence(state(relation_certain=False), NOW)
    assert result["score"] == 0.0
    assert result["reason"] == "low_confidence"

    softer = calibrated_confidence(
        state(relation_certain=False),
        NOW,
        replace(ConfidenceConfig(), uncertain_identity=0.5),
    )
    assert softer["reason"] is None


def test_stale_and_low_evidence_are_distinguished() -> None:
    stale = calibrated_confidence(
        state(last_seen_wallclock="2026-01-01T12:00:00+00:00"), NOW
    )
    assert stale["reason"] == "stale"

    weak = calibrated_confidence(state(confidence=0.05), NOW)
    assert weak["reason"] == "low_confidence"

    unsupported = calibrated_confidence(state(observation_count=0), NOW)
    assert unsupported["score"] == 0.0
    assert unsupported["reason"] == "low_confidence"


def test_missing_optional_fields_are_neutral() -> None:
    minimal = {
        "canonical": "mug",
        "label": "Mug #1",
        "confidence": 0.8,
        "last_seen_timestamp": 3.0,
    }
    result = calibrated_confidence(minimal, NOW)
    assert result["reason"] is None
    assert result["score"] > 0.0


def test_rank_candidates_exposes_calibration_and_abstains() -> None:
    ranked = rank_candidates([state()], "mug", now=NOW)
    assert ranked["resolution_mode"] == "direct"
    assert (
        ranked["candidates"][0]["confidence"]
        == calibrated_confidence(state(), NOW)["score"]
    )
    assert "confidence_factors" in ranked["candidates"][0]

    ranked = rank_candidates([state(relation_certain=False)], "mug", now=NOW)
    assert ranked["resolution_mode"] == "abstain"
    assert ranked["abstain_reason"] == "low_confidence"
    assert ranked["is_ambiguous"] is False


def test_no_candidates_still_reports_not_found() -> None:
    result = rank_candidates([], "mug", now=NOW)
    assert result["resolution_mode"] == "not_found"
    assert result["abstain_reason"] is None


def test_reference_time_uses_memory_timeline() -> None:
    from aegis.memory.reasoning import reference_time

    states = [state(last_seen_wallclock="2026-01-07T12:00:00+00:00")]
    assert reference_time(states) == datetime(2026, 1, 7, 12, tzinfo=UTC)
    assert rank_candidates(states, "mug")["resolution_mode"] == "direct"


def test_calibration_is_monotonic_in_evidence_quality() -> None:
    def score(**extra):
        return calibrated_confidence(state(**extra), NOW)["score"]

    assert score(confidence=0.9) > score(confidence=0.3)
    assert score(relation_certain=True) > score(relation_certain=False)
    assert score(observation_count=10) >= score(observation_count=1)
    recent = score(last_seen_wallclock="2026-01-11T12:30:00+00:00")
    old = score(last_seen_wallclock="2026-01-10T12:00:00+00:00")
    assert recent > old
    for value in (
        score(),
        score(confidence=0.0),
        score(last_seen_wallclock="2020-01-01T00:00:00+00:00"),
        score(relation_certain=False, observation_count=0),
    ):
        assert 0.0 <= value <= 1.0


def test_config_validation() -> None:
    try:
        replace(ConfidenceConfig(), abstain_below=1.5)
    except ValueError:
        pass
    else:
        raise AssertionError("abstain_below > 1 must be rejected")
    assert RankingConfig().candidate_limit == 3
