"""Independent scoring metrics for the Aegis evaluation suite.

The implementations are deliberately plain NumPy/stdlib so the harness has no
hidden dependency on the same libraries used to build the pipeline.  Each
metric returns JSON-serialisable dictionaries and keeps failure examples so a
panel can inspect *why* a score was earned, not only the score itself.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from aegis.evaluation.schema import Detection, Event

_INSTANCE_SUFFIX = re.compile(r"\s*#\s*\d+\s*$")
_BRACKET_SUFFIX = re.compile(r"\s*\[[^\]]*\]\s*$")


# ---------------------------------------------------------------------------
# Normalisation and small helpers
# ---------------------------------------------------------------------------


def normalise_label(label: str | None, aliases: dict[str, str] | None = None) -> str:
    """Canonicalise a class label for matching.

    Removes memory-instance suffixes such as ``#1`` and ``[Active Pair]`` so
    ``Shoes #1`` and ``shoes`` compare equal.  A user-supplied alias map can
    collapse open-vocabulary synonyms (``trash can`` -> ``trash bin``).
    """

    if label is None:
        return ""
    text = " ".join(str(label).lower().strip().split())
    text = _BRACKET_SUFFIX.sub("", text)
    text = _INSTANCE_SUFFIX.sub("", text).strip()
    aliases = aliases or {}
    return aliases.get(text, text)


def normalise_anchor(label: str | None, aliases: dict[str, str] | None = None) -> str:
    """Canonicalise an anchor label, discarding its instance number."""

    if label is None:
        return ""
    text = " ".join(str(label).lower().strip().split())
    text = _INSTANCE_SUFFIX.sub("", text).strip()
    aliases = aliases or {}
    return aliases.get(text, text)


def normalise_room(label: str | None, aliases: dict[str, str] | None = None) -> str:
    """Canonicalise a room label, keeping neutral ``Room #N`` labels distinct."""

    if label is None:
        return ""
    text = " ".join(str(label).lower().strip().split())
    aliases = aliases or {}
    return aliases.get(text, text)


def labels_match(
    first: str | None,
    second: str | None,
    aliases: dict[str, str] | None = None,
) -> bool:
    """Compare labels after normalisation; an empty expectation is a wildcard."""

    if not first or not second:
        return False
    return normalise_label(first, aliases) == normalise_label(second, aliases)


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a proportion.

    Panel reports should show uncertainty, especially for small samples.  The
    Wilson interval behaves sensibly at 0% and 100%, unlike the textbook
    normal approximation.
    """

    if total <= 0:
        return (0.0, 1.0)
    p = successes / total
    denominator = 1.0 + z * z / total
    centre = (p + z * z / (2.0 * total)) / denominator
    margin = (
        z
        * math.sqrt(p * (1.0 - p) / total + z * z / (4.0 * total * total))
        / denominator
    )
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def bbox_iou(first: Sequence[float], second: Sequence[float]) -> float:
    """Intersection-over-union for two ``[x1, y1, x2, y2]`` boxes."""

    ax1, ay1, ax2, ay2 = (float(v) for v in first)
    bx1, by1, bx2, by2 = (float(v) for v in second)
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_width = max(0.0, inter_x2 - inter_x1)
    inter_height = max(0.0, inter_y2 - inter_y1)
    intersection = inter_width * inter_height
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - intersection
    return intersection / union if union > 0 else 0.0


def mask_iou(first_path: str | Path, second_path: str | Path) -> float | None:
    """IoU for two binary mask images, returning ``None`` when unreadable."""

    try:
        import cv2  # local import keeps the core harness import cheap
    except ImportError:  # pragma: no cover - opencv is a project dependency
        return None
    first = cv2.imread(str(first_path), cv2.IMREAD_GRAYSCALE)
    second = cv2.imread(str(second_path), cv2.IMREAD_GRAYSCALE)
    if first is None or second is None:
        return None
    if first.shape != second.shape:
        second = cv2.resize(
            second, (first.shape[1], first.shape[0]), interpolation=cv2.INTER_NEAREST
        )
    first_binary = first > 0
    second_binary = second > 0
    union = np.logical_or(first_binary, second_binary).sum()
    if union == 0:
        return 0.0
    return float(np.logical_and(first_binary, second_binary).sum() / union)


def linear_sum_assignment(cost: np.ndarray) -> list[int]:
    """Minimum-cost assignment for a rectangular matrix (pure Python Hungarian).

    Returns a list of column indices, one per row, or ``-1`` when a row is
    unassigned.  Used for identity matching and controlled-room pairing, both
    of which must work without SciPy.
    """

    matrix = np.asarray(cost, dtype=np.float64)
    if matrix.ndim != 2:
        raise ValueError("cost matrix must be two-dimensional")
    rows, columns = matrix.shape
    if rows == 0 or columns == 0:
        return [-1] * rows
    transposed = rows > columns
    if transposed:
        matrix = matrix.T
        rows, columns = columns, rows

    # Hungarian algorithm with potentials, 1-indexed internally.
    u = [0.0] * (rows + 1)
    v = [0.0] * (columns + 1)
    p = [0] * (columns + 1)
    way = [0] * (columns + 1)
    for i in range(1, rows + 1):
        p[0] = i
        j0 = 0
        minv = [math.inf] * (columns + 1)
        used = [False] * (columns + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = math.inf
            j1 = 0
            for j in range(1, columns + 1):
                if used[j]:
                    continue
                current = matrix[i0 - 1, j - 1] - u[i0] - v[j]
                if current < minv[j]:
                    minv[j] = current
                    way[j] = j0
                if minv[j] < delta:
                    delta = minv[j]
                    j1 = j
            for j in range(columns + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break

    assignment = [-1] * rows
    for j in range(1, columns + 1):
        if p[j] != 0:
            assignment[p[j] - 1] = j - 1
    if transposed:
        original = [-1] * columns
        for row, column in enumerate(assignment):
            if column >= 0:
                original[column] = row
        return original
    return assignment


# ---------------------------------------------------------------------------
# Detection evaluation
# ---------------------------------------------------------------------------


def _canonical_aliases(aliases: dict[str, str] | None) -> dict[str, str]:
    if not aliases:
        return {}
    return {
        normalise_label(key): normalise_label(value) for key, value in aliases.items()
    }


def _filter_detections(
    detections: Iterable[Detection],
    *,
    aliases: dict[str, str] | None,
    exclude_labels: set[str] | None,
) -> list[Detection]:
    excluded = {normalise_label(label, aliases) for label in (exclude_labels or set())}
    return [
        detection
        for detection in detections
        if normalise_label(detection.label, aliases) not in excluded
    ]


def _group_by_frame(detections: Iterable[Detection]) -> dict[int, list[Detection]]:
    grouped: dict[int, list[Detection]] = defaultdict(list)
    for detection in detections:
        grouped[int(detection.frame_id)].append(detection)
    return grouped


def _match_frame(
    ground_truth: Sequence[Detection],
    predictions: Sequence[Detection],
    *,
    iou_threshold: float,
    aliases: dict[str, str] | None,
    class_agnostic: bool,
) -> tuple[list[tuple[Detection, Detection, float]], list[Detection], list[Detection]]:
    candidates: list[tuple[float, int, int]] = []
    for gt_index, gt in enumerate(ground_truth):
        for pred_index, pred in enumerate(predictions):
            if not class_agnostic and normalise_label(
                gt.label, aliases
            ) != normalise_label(pred.label, aliases):
                continue
            overlap = bbox_iou(gt.bbox, pred.bbox)
            if overlap >= iou_threshold:
                candidates.append((overlap, gt_index, pred_index))
    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))

    used_gt: set[int] = set()
    used_pred: set[int] = set()
    matches: list[tuple[Detection, Detection, float]] = []
    for overlap, gt_index, pred_index in candidates:
        if gt_index in used_gt or pred_index in used_pred:
            continue
        used_gt.add(gt_index)
        used_pred.add(pred_index)
        matches.append((ground_truth[gt_index], predictions[pred_index], overlap))
    false_negatives = [
        gt for index, gt in enumerate(ground_truth) if index not in used_gt
    ]
    false_positives = [
        pred for index, pred in enumerate(predictions) if index not in used_pred
    ]
    return matches, false_positives, false_negatives


def _detection_summary(
    matches: Sequence[tuple[Detection, Detection, float]],
    false_positives: Sequence[Detection],
    false_negatives: Sequence[Detection],
    ground_truth_count: int,
    prediction_count: int,
) -> dict[str, Any]:
    true_positives = len(matches)
    precision = (
        true_positives / (true_positives + len(false_positives))
        if (true_positives + len(false_positives)) > 0
        else 0.0
    )
    recall = (
        true_positives / (true_positives + len(false_negatives))
        if (true_positives + len(false_negatives)) > 0
        else 0.0
    )
    f1 = (
        2.0 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    return {
        "counts": {
            "ground_truth": ground_truth_count,
            "predictions": prediction_count,
            "true_positives": true_positives,
            "false_positives": len(false_positives),
            "false_negatives": len(false_negatives),
        },
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "precision_ci": wilson_interval(
            true_positives, true_positives + len(false_positives)
        ),
        "recall_ci": wilson_interval(
            true_positives, true_positives + len(false_negatives)
        ),
    }


def _average_precision(
    ground_truth: Sequence[Detection],
    predictions: Sequence[Detection],
    *,
    label: str,
    iou_threshold: float,
    aliases: dict[str, str] | None,
) -> float | None:
    gt_by_frame = _group_by_frame(
        gt for gt in ground_truth if normalise_label(gt.label, aliases) == label
    )
    class_predictions = [
        pred for pred in predictions if normalise_label(pred.label, aliases) == label
    ]
    if not gt_by_frame or not class_predictions:
        return None
    class_predictions.sort(
        key=lambda pred: (-pred.confidence, pred.frame_id, pred.bbox[0])
    )
    matched: dict[int, set[int]] = defaultdict(set)
    true_positive_flags: list[int] = []
    for pred in class_predictions:
        candidates: list[tuple[float, int]] = []
        for index, gt in enumerate(gt_by_frame.get(pred.frame_id, [])):
            if index in matched[pred.frame_id]:
                continue
            overlap = bbox_iou(gt.bbox, pred.bbox)
            if overlap >= iou_threshold:
                candidates.append((overlap, index))
        if candidates:
            candidates.sort(reverse=True)
            matched[pred.frame_id].add(candidates[0][1])
            true_positive_flags.append(1)
        else:
            true_positive_flags.append(0)

    total_gt = sum(len(items) for items in gt_by_frame.values())
    cumulative_tp = 0
    cumulative_fp = 0
    recalls: list[float] = []
    precisions: list[float] = []
    for flag in true_positive_flags:
        if flag:
            cumulative_tp += 1
        else:
            cumulative_fp += 1
        recalls.append(cumulative_tp / total_gt)
        precisions.append(cumulative_tp / max(cumulative_tp + cumulative_fp, 1))

    # All-point interpolated AP, matching the standard VOC-style definition.
    ap = 0.0
    previous_recall = 0.0
    for recall, precision in zip(recalls, precisions, strict=True):
        if recall > previous_recall:
            ap += (recall - previous_recall) * precision
            previous_recall = recall
    return float(ap)


def evaluate_detection(
    ground_truth: Sequence[Detection],
    predictions: Sequence[Detection],
    *,
    iou_threshold: float = 0.5,
    aliases: dict[str, str] | None = None,
    class_agnostic: bool = False,
    exclude_labels: set[str] | None = None,
    mask_iou_threshold: float = 0.5,
) -> dict[str, Any]:
    """Score 2D boxes (and masks when available) against annotations."""

    aliases = _canonical_aliases(aliases)
    gts = _filter_detections(
        ground_truth, aliases=aliases, exclude_labels=exclude_labels
    )
    preds = _filter_detections(
        predictions, aliases=aliases, exclude_labels=exclude_labels
    )
    gt_by_frame = _group_by_frame(gts)
    pred_by_frame = _group_by_frame(preds)

    all_matches: list[tuple[Detection, Detection, float]] = []
    false_positives: list[Detection] = []
    false_negatives: list[Detection] = []
    for frame_id in sorted(set(gt_by_frame) | set(pred_by_frame)):
        matches, frame_fp, frame_fn = _match_frame(
            gt_by_frame.get(frame_id, []),
            pred_by_frame.get(frame_id, []),
            iou_threshold=iou_threshold,
            aliases=aliases,
            class_agnostic=class_agnostic,
        )
        all_matches.extend(matches)
        false_positives.extend(frame_fp)
        false_negatives.extend(frame_fn)

    overall = _detection_summary(
        all_matches, false_positives, false_negatives, len(gts), len(preds)
    )

    class_names = sorted(
        {normalise_label(gt.label, aliases) for gt in gts}
        | {normalise_label(pred.label, aliases) for pred in preds}
    )
    per_class: dict[str, Any] = {}
    ap_values: list[float] = []
    gt_class_names = sorted({normalise_label(gt.label, aliases) for gt in gts})
    for label in class_names:
        class_gts = [gt for gt in gts if normalise_label(gt.label, aliases) == label]
        class_preds = [
            pred for pred in preds if normalise_label(pred.label, aliases) == label
        ]
        class_gt_by_frame = _group_by_frame(class_gts)
        class_pred_by_frame = _group_by_frame(class_preds)
        class_matches: list[tuple[Detection, Detection, float]] = []
        class_fp: list[Detection] = []
        class_fn: list[Detection] = []
        for frame_id in sorted(set(class_gt_by_frame) | set(class_pred_by_frame)):
            matches, frame_fp, frame_fn = _match_frame(
                class_gt_by_frame.get(frame_id, []),
                class_pred_by_frame.get(frame_id, []),
                iou_threshold=iou_threshold,
                aliases=aliases,
                class_agnostic=False,
            )
            class_matches.extend(matches)
            class_fp.extend(frame_fp)
            class_fn.extend(frame_fn)
        summary = _detection_summary(
            class_matches, class_fp, class_fn, len(class_gts), len(class_preds)
        )
        ap = _average_precision(
            gts,
            preds,
            label=label,
            iou_threshold=iou_threshold,
            aliases=aliases,
        )
        summary["average_precision"] = ap
        if label in gt_class_names and ap is not None:
            ap_values.append(ap)
        per_class[label] = summary

    macro_labels = [
        label
        for label in gt_class_names
        if per_class[label]["counts"]["ground_truth"] > 0
    ]
    macro_precision = (
        float(np.mean([per_class[label]["precision"] for label in macro_labels]))
        if macro_labels
        else 0.0
    )
    macro_recall = (
        float(np.mean([per_class[label]["recall"] for label in macro_labels]))
        if macro_labels
        else 0.0
    )
    macro_f1 = (
        float(np.mean([per_class[label]["f1"] for label in macro_labels]))
        if macro_labels
        else 0.0
    )

    mask_matches: list[dict[str, Any]] = []
    for gt, pred, overlap in all_matches:
        if not gt.mask_path or not pred.mask_path:
            continue
        score = mask_iou(gt.mask_path, pred.mask_path)
        if score is None:
            continue
        mask_matches.append(
            {
                "frame_id": gt.frame_id,
                "label": normalise_label(gt.label, aliases),
                "instance_id": gt.instance_id,
                "mask_iou": score,
                "box_iou": overlap,
                "passed": score >= mask_iou_threshold,
            }
        )

    if mask_matches:
        mask_values = [item["mask_iou"] for item in mask_matches]
        mask_summary = {
            "available": True,
            "count": len(mask_matches),
            "mean_iou": float(np.mean(mask_values)),
            "median_iou": float(np.median(mask_values)),
            "fraction_at_or_above_threshold": float(
                np.mean([item["passed"] for item in mask_matches])
            ),
            "threshold": mask_iou_threshold,
        }
    else:
        mask_summary = {
            "available": False,
            "count": 0,
            "mean_iou": None,
            "median_iou": None,
            "fraction_at_or_above_threshold": None,
            "threshold": mask_iou_threshold,
            "note": "No matched boxes had both GT and predicted masks.",
        }

    return {
        "available": True,
        **overall,
        "iou_threshold": iou_threshold,
        "class_agnostic": class_agnostic,
        "macro_precision": macro_precision,
        "macro_recall": macro_recall,
        "macro_f1": macro_f1,
        "mean_average_precision": (float(np.mean(ap_values)) if ap_values else None),
        "per_class": per_class,
        "mask_iou": mask_summary,
        "mask_matches": mask_matches[:50],
        "matches": [
            _match_record(gt, pred, overlap) for gt, pred, overlap in all_matches[:50]
        ],
        "false_positives": [
            _detection_record(detection) for detection in false_positives[:50]
        ],
        "false_negatives": [
            _detection_record(detection) for detection in false_negatives[:50]
        ],
        "counts": {
            **overall["counts"],
            "false_positives": len(false_positives),
            "false_negatives": len(false_negatives),
        },
    }


def _detection_record(detection: Detection) -> dict[str, Any]:
    return {
        "frame_id": detection.frame_id,
        "label": detection.label,
        "bbox": list(detection.bbox),
        "instance_id": detection.instance_id,
        "confidence": detection.confidence,
        "mask_path": detection.mask_path,
        "visibility": detection.visibility,
        "occluded": detection.occluded,
    }


def _match_record(gt: Detection, pred: Detection, overlap: float) -> dict[str, Any]:
    return {
        "frame_id": gt.frame_id,
        "label": gt.label,
        "instance_id": gt.instance_id,
        "predicted_label": pred.label,
        "predicted_instance_id": pred.instance_id,
        "iou": overlap,
        "gt_bbox": list(gt.bbox),
        "predicted_bbox": list(pred.bbox),
    }


# ---------------------------------------------------------------------------
# Tracking evaluation
# ---------------------------------------------------------------------------


def evaluate_tracking(
    ground_truth: Sequence[Detection],
    predictions: Sequence[Detection],
    *,
    iou_threshold: float = 0.5,
    aliases: dict[str, str] | None = None,
    exclude_labels: set[str] | None = None,
) -> dict[str, Any]:
    """Score identity preservation with IDF1, ID switches, and fragmentation.

    HOTA is intentionally *not* approximated here.  The harness exports enough
    information for TrackEval if the full HOTA family is required; reporting a
    home-made approximation would undermine the credibility of the suite.
    """

    aliases = _canonical_aliases(aliases)
    gts = [
        detection
        for detection in _filter_detections(
            ground_truth, aliases=aliases, exclude_labels=exclude_labels
        )
        if detection.instance_id is not None
    ]
    preds = [
        detection
        for detection in _filter_detections(
            predictions, aliases=aliases, exclude_labels=exclude_labels
        )
        if detection.instance_id is not None
    ]
    if not gts or not preds:
        return {
            "available": False,
            "reason": "Tracking needs instance_id values on GT and predicted detections.",
        }

    gt_by_frame = _group_by_frame(gts)
    pred_by_frame = _group_by_frame(preds)
    matches_by_frame: dict[int, list[tuple[Detection, Detection, float]]] = {}
    total_fp = 0
    total_fn = 0
    for frame_id in sorted(set(gt_by_frame) | set(pred_by_frame)):
        matches, frame_fp, frame_fn = _match_frame(
            gt_by_frame.get(frame_id, []),
            pred_by_frame.get(frame_id, []),
            iou_threshold=iou_threshold,
            aliases=aliases,
            class_agnostic=False,
        )
        matches_by_frame[frame_id] = matches
        total_fp += len(frame_fp)
        total_fn += len(frame_fn)

    gt_ids = sorted({int(gt.instance_id) for gt in gts})
    pred_ids = sorted({int(pred.instance_id) for pred in preds})
    gt_index = {identifier: index for index, identifier in enumerate(gt_ids)}
    pred_index = {identifier: index for index, identifier in enumerate(pred_ids)}
    counts = np.zeros((len(gt_ids), len(pred_ids)), dtype=np.float64)
    gt_to_pred_sequence: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for frame_id, matches in matches_by_frame.items():
        for gt, pred, _ in matches:
            row = gt_index[int(gt.instance_id)]
            column = pred_index[int(pred.instance_id)]
            counts[row, column] += 1
            gt_to_pred_sequence[int(gt.instance_id)].append(
                (frame_id, int(pred.instance_id))
            )

    assignment = linear_sum_assignment(-counts)
    idtp = sum(
        counts[row, column] for row, column in enumerate(assignment) if column >= 0
    )
    total_gt = len(gts)
    total_pred = len(preds)
    idfp = total_pred - idtp
    idfn = total_gt - idtp
    idf1 = (
        2.0 * idtp / (2.0 * idtp + idfp + idfn)
        if (2.0 * idtp + idfp + idfn) > 0
        else 0.0
    )

    id_switches = 0
    fragmentation = 0
    track_lengths: list[int] = []
    mostly_tracked = 0
    all_frames = sorted(set(gt_by_frame) | set(pred_by_frame))
    for gt_identifier in gt_ids:
        sequence = sorted(gt_to_pred_sequence.get(gt_identifier, []))
        track_lengths.append(len(sequence))
        previous_pred: int | None = None
        for _, pred_identifier in sequence:
            if previous_pred is not None and pred_identifier != previous_pred:
                id_switches += 1
            previous_pred = pred_identifier

        track_frames = sorted(
            gt.frame_id for gt in gts if int(gt.instance_id) == gt_identifier
        )
        if not track_frames:
            continue
        first_frame, last_frame = track_frames[0], track_frames[-1]
        matched_frames = {frame_id for frame_id, _ in sequence}
        span = [frame for frame in all_frames if first_frame <= frame <= last_frame]
        was_matched = False
        segments = 0
        for frame in span:
            is_matched = frame in matched_frames
            if is_matched and not was_matched:
                segments += 1
            was_matched = is_matched
        fragmentation += max(0, segments - 1)
        if len(matched_frames) / len(track_frames) >= 0.8:
            mostly_tracked += 1

    mota = 1.0 - (total_fn + total_fp + id_switches) / total_gt if total_gt else 0.0
    return {
        "available": True,
        "iou_threshold": iou_threshold,
        "counts": {
            "ground_truth_detections": total_gt,
            "predicted_detections": total_pred,
            "gt_tracks": len(gt_ids),
            "predicted_tracks": len(pred_ids),
            "id_true_positives": int(idtp),
            "id_false_positives": int(idfp),
            "id_false_negatives": int(idfn),
            "id_switches": id_switches,
            "fragmentation": fragmentation,
        },
        "idf1": float(idf1),
        "mota": float(mota),
        "id_switches": id_switches,
        "fragmentation": fragmentation,
        "mostly_tracked_ratio": mostly_tracked / len(gt_ids) if gt_ids else 0.0,
        "mean_gt_track_length": (
            float(np.mean(track_lengths)) if track_lengths else 0.0
        ),
        "note": "HOTA is not approximated; export MOT files for TrackEval.",
    }


# ---------------------------------------------------------------------------
# Event evaluation
# ---------------------------------------------------------------------------


def _event_type_matches(
    gt_type: str,
    pred_type: str,
    aliases: dict[str, str] | None,
) -> bool:
    gt = gt_type.lower().strip()
    pred = pred_type.lower().strip()
    if gt == pred:
        return True
    aliases = aliases or {}
    return aliases.get(gt, gt) == aliases.get(pred, pred)


def _event_time_matches(gt: Event, pred: Event, tolerance_s: float) -> bool:
    if abs(gt.start_time - gt.end_time) < 1e-9:
        return (
            pred.start_time - tolerance_s
            <= gt.start_time
            <= pred.end_time + tolerance_s
        )
    return (
        abs(pred.start_time - gt.start_time) <= tolerance_s
        and abs(pred.end_time - gt.end_time) <= tolerance_s
    )


def _event_object_matches(
    gt: Event, pred: Event, aliases: dict[str, str] | None
) -> bool:
    if gt.object_label and not pred.object_label:
        return False
    if gt.object_label and pred.object_label:
        return normalise_label(gt.object_label, aliases) == normalise_label(
            pred.object_label, aliases
        )
    if gt.instance_id is not None and pred.instance_id is not None:
        return gt.instance_id == pred.instance_id
    return True


def _event_anchor_matches(
    expected: str | None,
    actual: str | None,
    aliases: dict[str, str] | None,
) -> bool:
    if not expected:
        return True
    if not actual:
        return False
    return normalise_anchor(expected, aliases) == normalise_anchor(actual, aliases)


def _event_room_matches(
    expected: str | None,
    actual: str | None,
    aliases: dict[str, str] | None,
) -> bool:
    if not expected:
        return True
    if not actual:
        return False
    return normalise_room(expected, aliases) == normalise_room(actual, aliases)


def evaluate_events(
    ground_truth: Sequence[Event],
    predictions: Sequence[Event],
    *,
    tolerance_s: float = 1.0,
    aliases: dict[str, str] | None = None,
    event_type_aliases: dict[str, str] | None = None,
    match_anchors: bool = True,
    match_rooms: bool = True,
    event_types: set[str] | None = None,
) -> dict[str, Any]:
    """Match events one-to-one with a boundary tolerance, then score P/R/F1."""

    aliases = _canonical_aliases(aliases)
    if event_types:
        allowed = {event_type.lower() for event_type in event_types}
        gts = [event for event in ground_truth if event.event_type.lower() in allowed]
        preds = [event for event in predictions if event.event_type.lower() in allowed]
    else:
        gts = list(ground_truth)
        preds = list(predictions)

    unmatched_pred = set(range(len(preds)))
    matches: list[dict[str, Any]] = []
    false_negatives: list[Event] = []
    for gt in sorted(gts, key=lambda event: event.start_time):
        candidates: list[tuple[float, int]] = []
        for pred_index in unmatched_pred:
            pred = preds[pred_index]
            if not _event_type_matches(
                gt.event_type, pred.event_type, event_type_aliases
            ):
                continue
            if not _event_time_matches(gt, pred, tolerance_s):
                continue
            if not _event_object_matches(gt, pred, aliases):
                continue
            if match_anchors and not (
                _event_anchor_matches(gt.source_anchor, pred.source_anchor, aliases)
                and _event_anchor_matches(
                    gt.destination_anchor, pred.destination_anchor, aliases
                )
            ):
                continue
            if match_rooms and not (
                _event_room_matches(gt.source_room, pred.source_room, aliases)
                and _event_room_matches(
                    gt.destination_room, pred.destination_room, aliases
                )
            ):
                continue
            time_distance = abs(pred.start_time - gt.start_time) + abs(
                pred.end_time - gt.end_time
            )
            candidates.append((time_distance, pred_index))
        if candidates:
            candidates.sort()
            _, pred_index = candidates[0]
            unmatched_pred.remove(pred_index)
            pred = preds[pred_index]
            matches.append(
                {
                    "ground_truth": _event_record(gt),
                    "prediction": _event_record(pred),
                    "time_error_s": abs(pred.start_time - gt.start_time),
                }
            )
        else:
            false_negatives.append(gt)

    false_positives = [preds[index] for index in sorted(unmatched_pred)]
    true_positives = len(matches)
    precision = (
        true_positives / (true_positives + len(false_positives))
        if (true_positives + len(false_positives)) > 0
        else 0.0
    )
    recall = (
        true_positives / (true_positives + len(false_negatives))
        if (true_positives + len(false_negatives)) > 0
        else 0.0
    )
    f1 = (
        2.0 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    return {
        "available": bool(gts or preds),
        "tolerance_s": tolerance_s,
        "counts": {
            "ground_truth": len(gts),
            "predictions": len(preds),
            "true_positives": true_positives,
            "false_positives": len(false_positives),
            "false_negatives": len(false_negatives),
        },
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "precision_ci": wilson_interval(
            true_positives, true_positives + len(false_positives)
        ),
        "recall_ci": wilson_interval(
            true_positives, true_positives + len(false_negatives)
        ),
        "matches": matches,
        "false_positives": [_event_record(event) for event in false_positives],
        "false_negatives": [_event_record(event) for event in false_negatives],
    }


def _event_record(event: Event) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "object": event.object_label,
        "instance_id": event.instance_id,
        "start_time": event.start_time,
        "end_time": event.end_time,
        "source_anchor": event.source_anchor,
        "destination_anchor": event.destination_anchor,
        "source_room": event.source_room,
        "destination_room": event.destination_room,
    }


# ---------------------------------------------------------------------------
# Room evaluation
# ---------------------------------------------------------------------------


def _room_region(room: dict[str, Any]) -> Any:
    from aegis.memory.rooms import RoomRegion

    footprint_raw = room.get("footprint", [])
    if not footprint_raw and room.get("polygon_xz"):
        y = float(room.get("centroid", [0.0, 0.0, 0.0])[1])
        footprint_raw = [[float(x), y, float(z)] for x, z in room["polygon_xz"]]
    footprint = [tuple(float(value) for value in point) for point in footprint_raw]
    centroid_raw = room.get("centroid")
    if centroid_raw is None:
        if footprint:
            centroid = tuple(
                float(np.mean([point[axis] for point in footprint]))
                for axis in range(3)
            )
        else:
            centroid = (0.0, 0.0, 0.0)
    else:
        centroid = tuple(float(value) for value in centroid_raw)
    return RoomRegion(
        room_id=int(room.get("room_id", 0)),
        label=str(room.get("label", f"Room #{room.get('room_id', 0)}")),
        room_type=str(room.get("room_type", "Room")),
        centroid=centroid,
        footprint=footprint,
    )


def _point_in_polygon(
    point: tuple[float, float], polygon: Sequence[tuple[float, float]]
) -> bool:
    if len(polygon) < 3:
        return False
    x, y = point
    inside = False
    j = len(polygon) - 1
    for i, (xi, yi) in enumerate(polygon):
        xj, yj = polygon[j]
        intersects = (yi > y) != (yj > y) and x < (
            (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def _contains_point(room: Any, point: Sequence[float]) -> bool:
    footprint = [(float(p[0]), float(p[2])) for p in getattr(room, "footprint", [])]
    return _point_in_polygon((float(point[0]), float(point[2])), footprint)


def _room_mapping(
    frame_room_pairs: Sequence[tuple[int, int, int | None]],
) -> tuple[dict[int, int], np.ndarray]:
    """Map predicted room IDs onto GT room IDs by maximum frame agreement."""

    gt_ids = sorted({gt for _, gt, _ in frame_room_pairs})
    pred_ids = sorted({pred for _, _, pred in frame_room_pairs if pred is not None})
    counts = np.zeros((len(gt_ids), len(pred_ids)), dtype=np.float64)
    gt_index = {value: index for index, value in enumerate(gt_ids)}
    pred_index = {value: index for index, value in enumerate(pred_ids)}
    for _, gt, pred in frame_room_pairs:
        if pred is not None:
            counts[gt_index[gt], pred_index[pred]] += 1
    assignment = linear_sum_assignment(-counts)
    mapping = {
        pred_ids[column]: gt_ids[row]
        for row, column in enumerate(assignment)
        if column >= 0 and counts[row, column] > 0
    }
    return mapping, counts


def evaluate_rooms(
    graph: dict[str, Any],
    annotations: dict[str, Any],
    poses: Sequence[dict[str, Any]] | dict[str, Any],
    *,
    tolerance_s: float = 1.0,
    aliases: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Score room regions, per-keyframe room assignment, and room changes."""

    from aegis.memory.rooms import parse_camera_positions, room_for_point

    aliases = _canonical_aliases(aliases)
    gt_room_records = annotations.get("rooms", [])
    gt_rooms = {int(room["room_id"]): room for room in gt_room_records}
    gt_regions = [_room_region(room) for room in gt_room_records]
    pred_regions = [_room_region(room) for room in graph.get("rooms", [])]

    # Resolve per-frame GT labels/IDs.
    gt_frames: dict[int, int] = {}
    missing_room_ids = 0
    for record in annotations.get("frame_rooms", []):
        frame_id = int(record["frame_id"])
        if record.get("room_id") is not None:
            gt_frames[frame_id] = int(record["room_id"])
            continue
        label = record.get("label") or record.get("room")
        matches = [
            room_id
            for room_id, room in gt_rooms.items()
            if normalise_room(room.get("label"), aliases)
            == normalise_room(label, aliases)
        ]
        if matches:
            gt_frames[frame_id] = matches[0]
        else:
            missing_room_ids += 1

    positions = {
        frame_id: position for frame_id, _, position in parse_camera_positions(poses)
    }
    missing_poses = [frame_id for frame_id in gt_frames if frame_id not in positions]
    frame_pairs: list[tuple[int, int, int | None]] = []
    for frame_id, gt_room_id in sorted(gt_frames.items()):
        position = positions.get(frame_id)
        if position is None:
            continue
        predicted = room_for_point(position, pred_regions) if pred_regions else None
        frame_pairs.append(
            (frame_id, gt_room_id, predicted.room_id if predicted else None)
        )

    mapping, _contingency = _room_mapping(frame_pairs)
    correct = sum(
        1 for _, gt, pred in frame_pairs if pred is not None and mapping.get(pred) == gt
    )
    accuracy = correct / len(frame_pairs) if frame_pairs else 0.0

    per_gt_room: dict[str, Any] = {}
    for room_id, room in gt_rooms.items():
        relevant = [pair for pair in frame_pairs if pair[1] == room_id]
        hits = sum(
            1
            for _, gt, pred in relevant
            if pred is not None and mapping.get(pred) == gt
        )
        label = str(room.get("label", f"Room #{room_id}"))
        per_gt_room[label] = {
            "room_id": room_id,
            "frames": len(relevant),
            "correct": hits,
            "accuracy": hits / len(relevant) if relevant else None,
        }

    # Confusion matrix after mapping.
    confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for _, gt, pred in frame_pairs:
        gt_label = str(gt_rooms.get(gt, {}).get("label", f"Room #{gt}"))
        pred_label = (
            str(
                gt_rooms.get(mapping.get(pred, -1), {}).get(
                    "label", f"unmapped predicted room #{pred}"
                )
            )
            if pred is not None
            else "unassigned"
        )
        confusion[gt_label][pred_label] += 1

    # Hydra-style region containment precision/recall.
    region_hits: list[dict[str, Any]] = []
    typed_hits: list[dict[str, Any]] = []
    if gt_regions and pred_regions and all(region.footprint for region in gt_regions):
        for gt_room in gt_regions:
            containing = [
                pred for pred in pred_regions if _contains_point(pred, gt_room.centroid)
            ]
            hit = bool(containing)
            typed = any(
                normalise_room(pred.label, aliases)
                == normalise_room(gt_room.label, aliases)
                or pred.label.lower().startswith("room #")
                for pred in containing
            )
            region_hits.append(
                {
                    "room": gt_room.label,
                    "contained": hit,
                    "predicted_rooms": [pred.label for pred in containing],
                }
            )
            typed_hits.append({"room": gt_room.label, "typed_hit": typed})
        region_recall = float(np.mean([item["contained"] for item in region_hits]))
        typed_region_recall = float(np.mean([item["typed_hit"] for item in typed_hits]))

        pred_region_hits: list[bool] = []
        for pred_room in pred_regions:
            pred_centroid = pred_room.centroid
            pred_region_hits.append(
                any(_contains_point(gt_room, pred_centroid) for gt_room in gt_regions)
            )
        region_precision = float(np.mean(pred_region_hits))
        region_metrics: dict[str, Any] = {
            "available": True,
            "region_recall": region_recall,
            "typed_region_recall": typed_region_recall,
            "region_precision": region_precision,
            "per_gt_room": region_hits,
        }
    else:
        region_metrics = {
            "available": False,
            "reason": "GT footprints or predicted footprints are missing.",
        }

    # Room-change events, mapped onto GT labels before matching.
    gt_changes = annotations.get("room_changes", [])
    gt_events: list[Event] = []
    for index, change in enumerate(gt_changes):
        start = float(change.get("timestamp", change.get("start_time", 0.0)))
        end = float(change.get("end_time", start))
        from_id = change.get("from_room_id")
        to_id = change.get("to_room_id")
        from_label = (
            str(gt_rooms[int(from_id)].get("label"))
            if from_id is not None and int(from_id) in gt_rooms
            else change.get("from_room")
        )
        to_label = (
            str(gt_rooms[int(to_id)].get("label"))
            if to_id is not None and int(to_id) in gt_rooms
            else change.get("to_room")
        )
        gt_events.append(
            Event(
                event_type="room_change",
                start_time=start,
                end_time=end,
                source_room=str(from_label) if from_label else None,
                destination_room=str(to_label) if to_label else None,
                event_id=str(change.get("event_id", f"room_change_{index + 1}")),
            )
        )

    pred_label_to_gt: dict[str, str] = {}
    for pred_room in pred_regions:
        mapped_gt = mapping.get(pred_room.room_id)
        if mapped_gt is not None and mapped_gt in gt_rooms:
            pred_label_to_gt[normalise_room(pred_room.label, aliases)] = str(
                gt_rooms[mapped_gt].get("label")
            )
    pred_events: list[Event] = []
    for index, event in enumerate(graph.get("events", [])):
        if str(event.get("event_type", "")).lower() != "room_change":
            continue
        start = float(event.get("start_time", 0.0))
        end = float(event.get("end_time", start))
        source = event.get("source_room")
        destination = event.get("destination_room")
        if source:
            source = pred_label_to_gt.get(normalise_room(source, aliases), str(source))
        if destination:
            destination = pred_label_to_gt.get(
                normalise_room(destination, aliases), str(destination)
            )
        pred_events.append(
            Event(
                event_type="room_change",
                start_time=start,
                end_time=end,
                source_room=str(source) if source else None,
                destination_room=str(destination) if destination else None,
                event_id=str(event.get("event_id", f"pred_room_change_{index + 1}")),
            )
        )

    room_change_metrics = evaluate_events(
        gt_events,
        pred_events,
        tolerance_s=tolerance_s,
        aliases=aliases,
        match_anchors=False,
        match_rooms=True,
    )
    if not gt_events:
        room_change_metrics["available"] = False

    return {
        "available": bool(frame_pairs),
        "counts": {
            "evaluated_frames": len(frame_pairs),
            "gt_rooms": len(gt_rooms),
            "predicted_rooms": len(pred_regions),
            "missing_poses": len(missing_poses),
            "missing_room_ids": missing_room_ids,
        },
        "accuracy": accuracy,
        "accuracy_ci": wilson_interval(correct, len(frame_pairs)),
        "predicted_to_gt_room": {
            str(key): value for key, value in sorted(mapping.items())
        },
        "per_gt_room": per_gt_room,
        "confusion": {gt: dict(pred_counts) for gt, pred_counts in confusion.items()},
        "regions": region_metrics,
        "room_change": room_change_metrics,
        "frames": [
            {
                "frame_id": frame_id,
                "gt_room_id": gt,
                "predicted_room_id": pred,
                "predicted_gt_room_id": mapping.get(pred) if pred is not None else None,
                "correct": pred is not None and mapping.get(pred) == gt,
            }
            for frame_id, gt, pred in frame_pairs
        ],
    }
