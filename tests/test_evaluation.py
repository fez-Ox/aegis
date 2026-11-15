"""Tests for the event scoring helpers."""

from aegis.evaluation import match_events, precision_recall


def test_match_events_is_one_to_one_within_tolerance() -> None:
    assert match_events([1.0, 1.2, 5.0], [1.1, 4.0], tolerance=0.5) == 1
    assert match_events([1.0, 2.0], [1.0, 2.0], tolerance=0.1) == 2


def test_precision_recall_arithmetic() -> None:
    result = precision_recall([1.0, 3.0, 9.0], [1.0, 3.5, 6.0, 10.0], tolerance=1.0)
    assert result["matches"] == 3
    assert result["precision"] == 1.0
    assert result["recall"] == 0.75
    assert result["f1"] == round(2 * 0.75 / 1.75, 4)
    assert precision_recall([], [], tolerance=1.0)["recall"] == 1.0


def test_room_metrics_perfect_and_late_transition() -> None:
    from aegis.evaluation import room_metrics

    truth = [
        {"name": "Kitchen", "intervals": [[0.0, 10.0]]},
        {"name": "Hall", "intervals": [[10.0, 20.0]]},
    ]
    keyframes = [(float(t), 1 if t < 10 else 2) for t in range(20)]
    perfect = room_metrics(keyframes, truth, [10.0], [10.0])
    assert perfect["segmentation_accuracy"] == 1.0
    assert perfect["region_precision"] == 1.0
    assert perfect["region_recall"] == 1.0
    assert perfect["room_change"]["f1"] == 1.0
    late = room_metrics(keyframes, truth, [12.5], [10.0])
    assert late["room_change"]["f1"] == 0.0


def test_placement_accuracy_and_duplicates() -> None:
    from aegis.evaluation import placement_accuracy

    states = [
        {
            "canonical": "keys",
            "relation": "under",
            "anchor_label": "Bed #1",
            "last_seen_wallclock": "2",
        },
        {
            "canonical": "keys",
            "relation": "on_surface",
            "anchor_label": "Desk #1",
            "last_seen_wallclock": "1",
        },
        {
            "canonical": "mug",
            "relation": "inside",
            "anchor_label": "Drawer #2",
            "last_seen_wallclock": "1",
        },
    ]
    truth = [
        {"object": "keys", "anchor": "bed", "relation": "under"},
        {"object": "mug", "anchor": "desk", "relation": "on_surface"},
    ]
    result = placement_accuracy(states, truth)
    assert result["correct"] == 1
    assert result["accuracy"] == 0.5
    assert result["duplicate_rate"] == 0.5


def test_keyframe_hits_and_ordered_matches() -> None:
    from aegis.evaluation import keyframe_hits, ordered_matches

    hits = keyframe_hits([1.0, 5.5, 20.0], [0.5, 5.0, 10.0, 19.0, 30.0])
    assert hits["detected"] == 3
    assert hits["pass"] is False
    predicted = [
        ("Keys #1", "pickup", 5.0),
        ("Keys #1", "placement", 9.0),
        ("Mug #2", "pickup", 12.0),
    ]
    truth = [
        ("Keys", "pickup", 5.5),
        ("Keys", "placement", 9.2),
        ("Mug", "pickup", 20.0),
    ]
    assert ordered_matches(predicted, truth, tolerance=1.0) == 2


def test_summarise_live_session(tmp_path) -> None:
    from datetime import UTC, datetime, timedelta

    import numpy as np

    from aegis.evaluation import summarise_live_session
    from aegis.ingestion.live_storage import LiveSessionWriter

    base = datetime(2026, 11, 15, 9, tzinfo=UTC)
    writer = LiveSessionWriter(
        tmp_path,
        "soak",
        {
            "schema_version": 2,
            "source_id": "phone",
            "source_protocol": "fixture",
            "sample_rate_target_hz": 2.0,
        },
    )
    for step in range(6):
        if step == 3:
            writer.record_gap(
                gap_start=base + timedelta(seconds=1.6),
                gap_end=base + timedelta(seconds=11.4),
                reason="disconnect",
            )
        offset = step * 0.5 + (10.0 if step >= 3 else 0.0)
        writer.write(
            np.zeros((8, 8, 3), dtype=np.uint8),
            received_at=base + timedelta(seconds=offset),
            source_id="phone",
            sample_rate=2.0,
            source_protocol="fixture",
        )
    writer.close(status="completed", ended_at=base + timedelta(seconds=13.0))
    summary = summarise_live_session(writer.session_dir)
    assert summary["frames_kept"] == 6
    assert summary["gaps_by_reason"]["disconnect"]["count"] == 1
    assert summary["disconnects"][0]["resume_seconds"] == 9.9
    assert summary["max_interval_seconds"] == 10.5
