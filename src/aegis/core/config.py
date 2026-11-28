"""Configuration loading for the Modal-first Aegis pipeline."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from aegis.core.vocabulary import Vocabulary, default_vocabulary


@lru_cache(maxsize=8)
def _vocabulary_from_key(key: str) -> Vocabulary:
    import json

    return Vocabulary.from_mapping(json.loads(key))


def _vocabulary_from_mapping(raw: Mapping[str, Any]) -> Vocabulary:
    import json

    return _vocabulary_from_key(json.dumps(raw, sort_keys=True, default=list))


def _section(cls: type[Any], value: Any, name: str) -> Any:
    """Build a flat frozen config dataclass from a mapping.

    Each field is converted to the type of its default value; unknown keys are
    rejected so a misspelt setting fails loudly instead of being ignored.
    """

    from dataclasses import MISSING, fields

    raw = _mapping(value, name)
    known = {item.name: item for item in fields(cls)}
    unknown = sorted(set(raw) - set(known))
    if unknown:
        raise ValueError(f"{name}: unknown setting(s) {', '.join(unknown)}")
    kwargs: dict[str, Any] = {}
    for key, item in known.items():
        if key not in raw:
            continue
        default = item.default if item.default is not MISSING else None
        raw_value = raw[key]
        if raw_value is None:
            kwargs[key] = None
        elif isinstance(default, bool):
            kwargs[key] = bool(raw_value)
        elif isinstance(default, int):
            kwargs[key] = int(raw_value)
        elif isinstance(default, float):
            kwargs[key] = float(raw_value)
        elif isinstance(default, str):
            kwargs[key] = str(raw_value)
        else:
            kwargs[key] = raw_value
    return cls(**kwargs)


def _home_id(value: str) -> str:
    import re

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value):
        raise ValueError(
            "memory.home_id may contain only letters, digits, '.', '_', '-'"
        )
    return value


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    return value


def _pair(value: Any, name: str) -> tuple[int, int] | None:
    if value is None:
        return None
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TypeError(f"{name} must contain two numbers")
    if len(value) != 2:
        raise ValueError(f"{name} must contain exactly two numbers")
    result = (int(value[0]), int(value[1]))
    if result[0] <= 0 or result[1] <= 0:
        raise ValueError(f"{name} values must be positive")
    return result


def _quad(value: Any, name: str) -> tuple[float, float, float, float] | None:
    if value is None:
        return None
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TypeError(f"{name} must contain four numbers")
    if len(value) != 4:
        raise ValueError(f"{name} must contain exactly four numbers")
    result = tuple(float(item) for item in value)
    if result[0] <= 0 or result[1] <= 0:
        raise ValueError(f"{name} focal lengths must be positive")
    return result  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class StorageConfig:
    """Names and mount points for Modal persistent storage."""

    data_volume: str = "aegis-poc-data"
    model_cache_volume: str = "aegis-model-cache"
    data_mount: str = "/data"
    model_mount: str = "/models"


@dataclass(frozen=True, slots=True)
class VideoConfig:
    """Input video normalization settings."""

    filename: str = "video.mp4"
    sample_fps: float = 5.0
    width: int = 960
    height: int = 540


@dataclass(frozen=True, slots=True)
class CameraConfig:
    """Camera calibration settings for batch-video preprocessing.

    VGGT-Ω estimates intrinsics itself; these settings only decide which
    intrinsics are written to the dataset metadata. ``self_calibrated`` is
    accepted for older configs and behaves like ``provided``.

    ``calibration_mode`` controls how missing intrinsics are handled. The
    default requires a supplied calibration file or configured intrinsics;
    self-calibration and approximate intrinsics are explicit alternatives.
    """

    calibration_filename: str = "calib.txt"
    intrinsics: tuple[float, float, float, float] | None = None
    intrinsics_resolution: tuple[int, int] | None = None
    calibration_mode: str = "provided"
    allow_approximate: bool = False


@dataclass(frozen=True, slots=True)
class VisualizationConfig:
    """Rerun recording settings."""

    log_video: bool = True
    video_stride: int = 1
    point_radius: float = 0.01
    camera_radius: float = 0.04


@dataclass(frozen=True, slots=True)
class VggtConfig:
    """VGGT-Ω feed-forward 3D reconstruction settings."""

    model_id: str = "facebook/VGGT-Omega"
    # Every run so far used 512 with the vggt_omega_1b_512 checkpoint.
    image_size: int = 512
    keyframe_stride: int = 6
    dtype: str = "bfloat16"
    # Hard limit per reconstruction; long captures are split into segments.
    max_keyframes: int = 120
    # Keep per-keyframe pointmaps after the detect stage (debugging only).
    keep_pointmaps: bool = False


@dataclass(frozen=True, slots=True)
class Sam2Config:
    """SAM 2 instance segmentation and tracking settings."""

    model_id: str = "facebook/sam2-hiera-large"
    prompt_confidence_threshold: float = 0.35
    multimask_output: bool = False
    # always: refine every box; fallback: only when the detector's own mask
    # is missing or covers < min_mask_area_ratio of its box; off: never.
    mode: str = "fallback"
    min_mask_area_ratio: float = 0.15


@dataclass(frozen=True, slots=True)
class PerceptionConfig:
    """2D/3D object perception and tracking settings.

    YOLOE is the default because it produces open-vocabulary masks directly;
    YOLO-World remains available as a detector-only fallback.
    """

    detector_backend: str = "yoloe"
    detector_model: str = "yoloe-11l-seg.pt"
    # SAM3 promptable concept segmentation (batched text prompts per frame).
    sam3_model: str = "facebook/sam3"
    sam3_default_threshold: float = 0.8
    sam3_class_thresholds: dict[str, float] = field(
        default_factory=lambda: {"shoes": 0.5, "hand": 0.4}
    )
    target_classes: tuple[str, ...] = (
        "shoes",
        "shoe",
        "cabinet",
        "shelf",
        "table",
        "desk",
        "chair",
        "door",
        "mug",
        "bottle",
        "keys",
        "backpack",
        "box",
    )
    confidence_threshold: float = 0.2
    iou_threshold: float = 0.45
    min_points_in_box: int = 15
    track_max_gap: int = 3
    # Keep a lightweight appearance memory after a short-term track expires.
    # This is deliberately bounded; it is not a global identity database.
    reid_max_gap: int = 30
    reid_appearance_threshold: float = 0.35
    track_smoothing: float = 0.65
    hand_contact_iou_threshold: float = 0.10
    hand_contact_max_distance: float = 0.35
    # Same-label boxes overlapping more than this are duplicates.
    duplicate_iou: float = 0.5
    max_detections_per_frame: int = 30
    batch_size: int = 8
    # hsv (colour histogram) or dino (DINOv2 embedding) for dormant re-ID.
    reid_backend: str = "hsv"
    reid_embedding_threshold: float = 0.35


@dataclass(frozen=True, slots=True)
class RoomMemoryConfig:
    """Room-level spatial memory settings (top level of the memory hierarchy)."""

    enabled: bool = True
    # Floor-plane distance at which two keyframe positions join one room zone.
    zone_link_radius: float = 2.5
    # Minimum keyframes a trajectory zone needs before it becomes a room.
    min_zone_keyframes: int = 3
    # A room type needs several distinct, confident landmark instances before
    # it overrides the neutral "Room #N" label; one stray "stove" detection
    # must not type a whole laundry area as a kitchen.
    landmark_min_votes: int = 2
    landmark_min_confidence: float = 0.8
    landmark_distinct_instances: bool = True


@dataclass(frozen=True, slots=True)
class KeyframeConfig:
    """Live keyframe selection criteria (FR2.1).

    A frame is kept only when it is bright enough, sharp enough, and visually
    different from the last accepted frame. ``max_interval_seconds`` forces a
    keyframe after a quiet period so a static scene is still represented.
    """

    enabled: bool = True
    min_sharpness: float = 15.0
    min_brightness: float = 20.0
    max_brightness: float = 245.0
    min_visual_change: float = 0.008
    max_interval_seconds: float = 2.0

    def __post_init__(self) -> None:
        if self.min_sharpness < 0:
            raise ValueError("live.keyframe.min_sharpness must be non-negative")
        if not 0 <= self.min_brightness < self.max_brightness <= 255:
            raise ValueError(
                "live.keyframe brightness bounds must satisfy "
                "0 <= min_brightness < max_brightness <= 255"
            )
        if not 0 <= self.min_visual_change <= 1:
            raise ValueError("live.keyframe.min_visual_change must be in [0, 1]")
        if self.max_interval_seconds <= 0:
            raise ValueError("live.keyframe.max_interval_seconds must be positive")


@dataclass(frozen=True, slots=True)
class LiveCaptureConfig:
    """Live FR1/FR2 capture defaults loaded from the runtime YAML."""

    sample_fps: float = 2.0
    max_duration_seconds: float = 600.0
    reconnect_interval_seconds: float = 3.0
    reconnect_timeout_seconds: float = 30.0
    buffer_capacity: int = 30
    checkpoint_every: int = 1
    # Frames per promoted segment (0 = one dataset for the whole capture).
    segment_frames: int = 120
    keyframe: KeyframeConfig = field(default_factory=KeyframeConfig)

    def __post_init__(self) -> None:
        if self.sample_fps <= 0:
            raise ValueError("live.sample_fps must be positive")
        if self.max_duration_seconds < 0:
            raise ValueError("live.max_duration_seconds must be non-negative")
        if self.reconnect_interval_seconds < 0:
            raise ValueError("live.reconnect_interval_seconds must be non-negative")
        if self.reconnect_timeout_seconds < 0:
            raise ValueError("live.reconnect_timeout_seconds must be non-negative")
        if self.buffer_capacity <= 0:
            raise ValueError("live.buffer_capacity must be positive")
        if self.checkpoint_every <= 0:
            raise ValueError("live.checkpoint_every must be positive")
        if self.segment_frames < 0:
            raise ValueError("live.segment_frames must be non-negative")


@dataclass(frozen=True, slots=True)
class GravityConfig:
    """Per-session gravity estimation (up direction and floor height)."""

    enabled: bool = True
    # Below this confidence, vertical relations (under/above/on_floor) are not
    # asserted and thresholds are not rescaled.
    min_confidence: float = 0.5
    # Typical height of a chest-held phone, in reconstruction units.
    assumed_camera_height: float = 1.4
    ransac_iterations: int = 500

    def __post_init__(self) -> None:
        if not 0 < self.min_confidence <= 1:
            raise ValueError("memory.gravity.min_confidence must be in (0, 1]")
        if self.assumed_camera_height <= 0:
            raise ValueError("memory.gravity.assumed_camera_height must be positive")
        if self.ransac_iterations < 50:
            raise ValueError("memory.gravity.ransac_iterations must be at least 50")


@dataclass(frozen=True, slots=True)
class MemoryBuildConfig:
    """Thresholds of the per-session memory builder.

    Distances are multiplied by the session scale unit
    (:meth:`aegis.geometry.gravity.GravityFrame.unit`).
    """

    anchor_cluster_radius: float = 0.40
    association_radius: float = 0.45
    appearance_threshold: float = 0.35
    # An instance is confirmed (gets memory) after this many observations.
    min_observations: int = 2
    # A new state must be seen this many times in a row to replace the old.
    min_run_observations: int = 2
    # A single final observation may still commit a state above this
    # detection confidence when its relation is certain.
    trailing_single_confidence: float = 0.5
    vertical_tolerance: float = 0.15

    def __post_init__(self) -> None:
        if (
            self.anchor_cluster_radius <= 0
            or self.association_radius <= 0
            or not 0 < self.appearance_threshold <= 1
            or self.min_observations < 1
            or self.min_run_observations < 1
            or not 0 <= self.trailing_single_confidence <= 1
            or self.vertical_tolerance <= 0
        ):
            raise ValueError("memory.build values are outside their valid ranges")


@dataclass(frozen=True, slots=True)
class RankingConfig:
    """Explainable candidate ranking for ambiguous class-level queries.

    Defaults follow ``w_vip > w_act > w_disp > w_rec``: an enrolled personal
    item outranks a recently handled object, which outranks a displaced object,
    which outranks a passive sighting.  The cue term is a small boost, not a
    hard override; room cues are filtered by the caller.
    """

    candidate_limit: int = 3
    ambiguity_margin: float = 0.08
    recency_half_life_hours: float = 24.0
    w_vip: float = 1.0
    w_act: float = 0.45
    w_disp: float = 0.25
    w_rec: float = 0.20
    w_cue: float = 0.10
    w_visual: float = 0.10
    # Place-evidence priors for "where" answers. Both are generic: a state with
    # no anchor or a carried object cannot ground a specific place.
    anchorless_penalty: float = 0.0
    carried_penalty: float = 0.0
    require_anchor_for_direct: bool = False

    def __post_init__(self) -> None:
        if self.candidate_limit < 1:
            raise ValueError("memory.ranking.candidate_limit must be at least 1")
        if not 0 <= self.ambiguity_margin <= 1:
            raise ValueError("memory.ranking.ambiguity_margin must be in [0, 1]")
        if self.recency_half_life_hours <= 0:
            raise ValueError("memory.ranking.recency_half_life_hours must be positive")
        weights = (
            self.w_vip,
            self.w_act,
            self.w_disp,
            self.w_rec,
            self.w_cue,
            self.w_visual,
        )
        if any(weight < 0 for weight in weights):
            raise ValueError("memory.ranking weights must be non-negative")
        if not self.w_vip > self.w_act > self.w_disp > self.w_rec:
            raise ValueError(
                "memory.ranking weights must satisfy w_vip > w_act > w_disp > w_rec"
            )
        if not 0 <= self.anchorless_penalty <= 1:
            raise ValueError("memory.ranking.anchorless_penalty must be in [0, 1]")
        if not 0 <= self.carried_penalty <= 1:
            raise ValueError("memory.ranking.carried_penalty must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class ConfidenceConfig:
    """Generic confidence calibration and abstention for answer ranking.

    The final score is raw detection confidence multiplied by penalising
    identity, support and recency factors. Neutral factors are exactly 1.0, so
    they cannot inflate a weak detection; any factor of 0 vetoes the answer.
    Weights are category-independent: no per-object or per-dataset settings.
    """

    w_identity: float = 0.2
    w_support: float = 0.2
    w_recency: float = 0.2
    # A candidate with fewer observations than this is only partially trusted.
    support_saturation: float = 3.0
    # Half-life (hours) used only by the confidence recency factor.
    confidence_half_life_hours: float = 24.0
    # Answers below this calibrated confidence abstain instead of guessing.
    abstain_below: float = 0.35
    # Older evidence than this cannot support a direct answer.
    stale_after_hours: float = 168.0
    # An uncertain relation cannot ground a direct answer: measured on the
    # frozen 17-query EgoLife bank, this cut wrong confident answers 5 -> 2
    # without regressing any ask-day slice.
    uncertain_identity: float = 0.0

    def __post_init__(self) -> None:
        weights = (self.w_identity, self.w_support, self.w_recency)
        if any(not 0 <= weight <= 1 for weight in weights):
            raise ValueError("memory.confidence weights must be in [0, 1]")
        if self.support_saturation <= 0:
            raise ValueError("memory.confidence.support_saturation must be positive")
        if self.confidence_half_life_hours <= 0:
            raise ValueError(
                "memory.confidence.confidence_half_life_hours must be positive"
            )
        if not 0 <= self.abstain_below <= 1:
            raise ValueError("memory.confidence.abstain_below must be in [0, 1]")
        if self.stale_after_hours <= 0:
            raise ValueError("memory.confidence.stale_after_hours must be positive")
        if not 0 <= self.uncertain_identity <= 1:
            raise ValueError("memory.confidence.uncertain_identity must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class EvidenceConfig:
    """Object-only evidence crops kept after raw frames are purged.

    Keeping them past the 24-hour raw-frame rule is decision #9 and must be
    confirmed with the supervisor; ``enabled: false`` turns them off.
    """

    enabled: bool = True
    max_side: int = 320
    quality: int = 85

    def __post_init__(self) -> None:
        if self.max_side < 32 or not 1 <= self.quality <= 100:
            raise ValueError("memory.evidence values are outside their valid ranges")


@dataclass(frozen=True, slots=True)
class RetentionConfig:
    """Tiered retention: full detail for ``hot_days``, then text summaries."""

    hot_days: int = 3
    # Vocabulary entries with importance: high keep detail longer.
    important_hot_days: int = 7
    # Calendar days of summaries (IANA zone name).
    timezone: str = "Asia/Karachi"
    # Keep the crop behind each object's last-known state after compaction.
    keep_last_evidence: bool = True
    weekly_rollup_after_days: int = 30
    monthly_rollup_after_days: int = 365

    def __post_init__(self) -> None:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        if self.hot_days < 1 or self.important_hot_days < self.hot_days:
            raise ValueError(
                "memory.retention needs hot_days >= 1 and important_hot_days >= hot_days"
            )
        if not 0 < self.weekly_rollup_after_days < self.monthly_rollup_after_days:
            raise ValueError("memory.retention roll-up thresholds are inconsistent")
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(
                f"memory.retention.timezone {self.timezone!r} is unknown"
            ) from exc


@dataclass(frozen=True, slots=True)
class MemoryConfig:
    """Spatio-temporal memory construction settings."""

    rooms: RoomMemoryConfig = field(default_factory=RoomMemoryConfig)
    gravity: GravityConfig = field(default_factory=GravityConfig)
    build: MemoryBuildConfig = field(default_factory=MemoryBuildConfig)
    ranking: RankingConfig = field(default_factory=RankingConfig)
    confidence: ConfidenceConfig = field(default_factory=ConfidenceConfig)
    evidence: EvidenceConfig = field(default_factory=EvidenceConfig)
    retention: RetentionConfig = field(default_factory=RetentionConfig)
    # Durable per-home memory (laptop side): <store_root>/<home_id>/memory.db
    home_id: str = "home01"
    store_root: str = "outputs/_homes"


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """Complete configuration passed from the local orchestrator to Modal.

    ``vocabulary`` holds the serialised vocabulary (``Vocabulary.to_mapping``)
    so that remote workers, which do not ship the YAML file, get the same
    label roles as local code. Use :meth:`vocab` to obtain the object.
    """

    storage: StorageConfig = field(default_factory=StorageConfig)
    video: VideoConfig = field(default_factory=VideoConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)
    vggt: VggtConfig = field(default_factory=VggtConfig)
    sam2: Sam2Config = field(default_factory=Sam2Config)
    perception: PerceptionConfig = field(default_factory=PerceptionConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    live: LiveCaptureConfig = field(default_factory=LiveCaptureConfig)
    visualization: VisualizationConfig = field(default_factory=VisualizationConfig)
    vocabulary: Mapping[str, Any] = field(default_factory=dict)

    def vocab(self) -> Vocabulary:
        """Return the vocabulary carried in the config, else the repository file."""

        if self.vocabulary:
            return _vocabulary_from_mapping(self.vocabulary)
        return default_vocabulary()

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> RuntimeConfig:
        """Build and validate a runtime configuration from a nested mapping."""

        storage_raw = _mapping(raw.get("storage"), "storage")
        video_raw = _mapping(raw.get("video"), "video")
        camera_raw = _mapping(raw.get("camera"), "camera")
        vggt_raw = _mapping(raw.get("vggt"), "vggt")
        sam2_raw = _mapping(raw.get("sam2"), "sam2")
        perception_raw = _mapping(raw.get("perception"), "perception")
        memory_raw = _mapping(raw.get("memory"), "memory")
        live_raw = _mapping(raw.get("live"), "live")
        visualization_raw = _mapping(raw.get("visualization"), "visualization")

        storage_defaults = StorageConfig()
        video_defaults = VideoConfig()
        camera_defaults = CameraConfig()
        vggt_defaults = VggtConfig()
        sam2_defaults = Sam2Config()
        perception_defaults = PerceptionConfig()
        memory_defaults = MemoryConfig()
        live_defaults = LiveCaptureConfig()
        visualization_defaults = VisualizationConfig()

        video = VideoConfig(
            filename=str(video_raw.get("filename", video_defaults.filename)),
            sample_fps=float(video_raw.get("sample_fps", video_defaults.sample_fps)),
            width=int(video_raw.get("width", video_defaults.width)),
            height=int(video_raw.get("height", video_defaults.height)),
        )
        if video.sample_fps <= 0 or video.width <= 0 or video.height <= 0:
            raise ValueError("video sample_fps and dimensions must be positive")

        configured_allow_approximate = bool(
            camera_raw.get("allow_approximate", camera_defaults.allow_approximate)
        )
        configured_mode = camera_raw.get("calibration_mode")
        calibration_mode = (
            str(configured_mode).lower()
            if configured_mode is not None
            else ("approximate" if configured_allow_approximate else "provided")
        )
        if calibration_mode not in {"provided", "self_calibrated", "approximate"}:
            raise ValueError(
                "camera.calibration_mode must be 'provided', 'self_calibrated', "
                "or 'approximate'"
            )
        if calibration_mode != "approximate" and configured_allow_approximate:
            raise ValueError(
                "camera.allow_approximate is only valid with "
                "camera.calibration_mode='approximate'"
            )
        camera = CameraConfig(
            calibration_filename=str(
                camera_raw.get(
                    "calibration_filename", camera_defaults.calibration_filename
                )
            ),
            intrinsics=_quad(camera_raw.get("intrinsics"), "camera.intrinsics"),
            intrinsics_resolution=_pair(
                camera_raw.get("intrinsics_resolution"),
                "camera.intrinsics_resolution",
            ),
            calibration_mode=calibration_mode,
            allow_approximate=calibration_mode == "approximate",
        )
        vggt = VggtConfig(
            model_id=str(vggt_raw.get("model_id", vggt_defaults.model_id)),
            image_size=int(vggt_raw.get("image_size", vggt_defaults.image_size)),
            keyframe_stride=int(
                vggt_raw.get("keyframe_stride", vggt_defaults.keyframe_stride)
            ),
            dtype=str(vggt_raw.get("dtype", vggt_defaults.dtype)),
            max_keyframes=int(
                vggt_raw.get("max_keyframes", vggt_defaults.max_keyframes)
            ),
            keep_pointmaps=bool(
                vggt_raw.get("keep_pointmaps", vggt_defaults.keep_pointmaps)
            ),
        )
        if vggt.keyframe_stride <= 0 or vggt.image_size <= 0 or vggt.max_keyframes < 2:
            raise ValueError("vggt settings must be positive (max_keyframes >= 2)")
        if vggt.dtype not in {"bfloat16", "float16", "float32"}:
            raise ValueError("vggt.dtype must be 'bfloat16', 'float16' or 'float32'")

        sam2 = Sam2Config(
            model_id=str(sam2_raw.get("model_id", sam2_defaults.model_id)),
            prompt_confidence_threshold=float(
                sam2_raw.get(
                    "prompt_confidence_threshold",
                    sam2_defaults.prompt_confidence_threshold,
                )
            ),
            multimask_output=bool(
                sam2_raw.get("multimask_output", sam2_defaults.multimask_output)
            ),
            mode=str(sam2_raw.get("mode", sam2_defaults.mode)).lower(),
            min_mask_area_ratio=float(
                sam2_raw.get("min_mask_area_ratio", sam2_defaults.min_mask_area_ratio)
            ),
        )
        if sam2.mode not in {"always", "fallback", "off"}:
            raise ValueError("sam2.mode must be 'always', 'fallback' or 'off'")
        if not 0.0 <= sam2.min_mask_area_ratio <= 1.0:
            raise ValueError("sam2.min_mask_area_ratio must be in [0, 1]")

        vocabulary_raw = raw.get("vocabulary") or {}
        if not isinstance(vocabulary_raw, Mapping):
            raise TypeError("vocabulary must be a mapping")
        if vocabulary_raw:
            # Validate early so a broken vocabulary fails before any Modal call.
            _vocabulary_from_mapping(vocabulary_raw)

        target_classes_raw = perception_raw.get("target_classes")
        if target_classes_raw is None and vocabulary_raw:
            target_classes_raw = list(
                _vocabulary_from_mapping(vocabulary_raw).detector_prompts()
            )
        if target_classes_raw is not None:
            if not isinstance(target_classes_raw, Sequence) or isinstance(
                target_classes_raw, (str, bytes)
            ):
                raise TypeError(
                    "perception.target_classes must be a sequence of strings"
                )
            target_classes = tuple(str(item) for item in target_classes_raw)
        else:
            target_classes = perception_defaults.target_classes

        perception = PerceptionConfig(
            detector_backend=str(
                perception_raw.get(
                    "detector_backend", perception_defaults.detector_backend
                )
            ).lower(),
            detector_model=str(
                perception_raw.get("detector_model", perception_defaults.detector_model)
            ),
            sam3_model=str(
                perception_raw.get("sam3_model", perception_defaults.sam3_model)
            ),
            sam3_default_threshold=float(
                perception_raw.get(
                    "sam3_default_threshold", perception_defaults.sam3_default_threshold
                )
            ),
            sam3_class_thresholds={
                str(key): float(value)
                for key, value in (
                    perception_raw.get(
                        "sam3_class_thresholds",
                        perception_defaults.sam3_class_thresholds,
                    )
                    or {}
                ).items()
            },
            target_classes=target_classes,
            confidence_threshold=float(
                perception_raw.get(
                    "confidence_threshold", perception_defaults.confidence_threshold
                )
            ),
            iou_threshold=float(
                perception_raw.get("iou_threshold", perception_defaults.iou_threshold)
            ),
            min_points_in_box=int(
                perception_raw.get(
                    "min_points_in_box", perception_defaults.min_points_in_box
                )
            ),
            track_max_gap=int(
                perception_raw.get("track_max_gap", perception_defaults.track_max_gap)
            ),
            reid_max_gap=int(
                perception_raw.get("reid_max_gap", perception_defaults.reid_max_gap)
            ),
            reid_appearance_threshold=float(
                perception_raw.get(
                    "reid_appearance_threshold",
                    perception_defaults.reid_appearance_threshold,
                )
            ),
            track_smoothing=float(
                perception_raw.get(
                    "track_smoothing", perception_defaults.track_smoothing
                )
            ),
            hand_contact_iou_threshold=float(
                perception_raw.get(
                    "hand_contact_iou_threshold",
                    perception_defaults.hand_contact_iou_threshold,
                )
            ),
            hand_contact_max_distance=float(
                perception_raw.get(
                    "hand_contact_max_distance",
                    perception_defaults.hand_contact_max_distance,
                )
            ),
            duplicate_iou=float(
                perception_raw.get("duplicate_iou", perception_defaults.duplicate_iou)
            ),
            max_detections_per_frame=int(
                perception_raw.get(
                    "max_detections_per_frame",
                    perception_defaults.max_detections_per_frame,
                )
            ),
            batch_size=int(
                perception_raw.get("batch_size", perception_defaults.batch_size)
            ),
            reid_backend=str(
                perception_raw.get("reid_backend", perception_defaults.reid_backend)
            ).lower(),
            reid_embedding_threshold=float(
                perception_raw.get(
                    "reid_embedding_threshold",
                    perception_defaults.reid_embedding_threshold,
                )
            ),
        )
        if perception.reid_backend not in {"hsv", "dino"}:
            raise ValueError("perception.reid_backend must be 'hsv' or 'dino'")
        if (
            not 0.0 < perception.duplicate_iou <= 1.0
            or perception.max_detections_per_frame < 1
            or perception.batch_size < 1
            or not 0.0 < perception.reid_embedding_threshold <= 2.0
        ):
            raise ValueError("perception detection limits are out of valid range")

        if perception.detector_backend not in {"yoloe", "yolo_world", "sam3"}:
            raise ValueError(
                "perception.detector_backend must be 'yoloe', 'yolo_world' or 'sam3'"
            )
        if not 0.0 <= perception.sam3_default_threshold <= 1.0 or any(
            not 0.0 <= value <= 1.0
            for value in perception.sam3_class_thresholds.values()
        ):
            raise ValueError("perception.sam3 thresholds must be in [0, 1]")

        if (
            perception.confidence_threshold <= 0
            or perception.confidence_threshold > 1.0
            or perception.iou_threshold <= 0
            or perception.iou_threshold > 1.0
            or perception.min_points_in_box <= 0
            or perception.track_max_gap < 0
            or perception.reid_max_gap < perception.track_max_gap
            or perception.reid_appearance_threshold <= 0.0
            or perception.reid_appearance_threshold > 1.0
            or perception.track_smoothing < 0.0
            or perception.track_smoothing >= 1.0
        ):
            raise ValueError("perception parameters are out of valid range")

        visualization = VisualizationConfig(
            log_video=bool(
                visualization_raw.get("log_video", visualization_defaults.log_video)
            ),
            video_stride=int(
                visualization_raw.get(
                    "video_stride", visualization_defaults.video_stride
                )
            ),
            point_radius=float(
                visualization_raw.get(
                    "point_radius", visualization_defaults.point_radius
                )
            ),
            camera_radius=float(
                visualization_raw.get(
                    "camera_radius", visualization_defaults.camera_radius
                )
            ),
        )
        if (
            visualization.video_stride <= 0
            or visualization.point_radius <= 0
            or visualization.camera_radius <= 0
        ):
            raise ValueError("visualization values must be positive")

        rooms_defaults = memory_defaults.rooms
        rooms_raw = _mapping(memory_raw.get("rooms"), "memory.rooms")
        rooms = RoomMemoryConfig(
            enabled=bool(rooms_raw.get("enabled", rooms_defaults.enabled)),
            zone_link_radius=float(
                rooms_raw.get("zone_link_radius", rooms_defaults.zone_link_radius)
            ),
            min_zone_keyframes=int(
                rooms_raw.get("min_zone_keyframes", rooms_defaults.min_zone_keyframes)
            ),
        )
        if rooms.zone_link_radius <= 0 or rooms.min_zone_keyframes < 1:
            raise ValueError("memory.rooms thresholds are outside their valid ranges")

        keyframe_defaults = live_defaults.keyframe
        keyframe_raw = _mapping(live_raw.get("keyframe"), "live.keyframe")
        keyframe = KeyframeConfig(
            enabled=bool(keyframe_raw.get("enabled", keyframe_defaults.enabled)),
            min_sharpness=float(
                keyframe_raw.get("min_sharpness", keyframe_defaults.min_sharpness)
            ),
            min_brightness=float(
                keyframe_raw.get("min_brightness", keyframe_defaults.min_brightness)
            ),
            max_brightness=float(
                keyframe_raw.get("max_brightness", keyframe_defaults.max_brightness)
            ),
            min_visual_change=float(
                keyframe_raw.get(
                    "min_visual_change", keyframe_defaults.min_visual_change
                )
            ),
            max_interval_seconds=float(
                keyframe_raw.get(
                    "max_interval_seconds", keyframe_defaults.max_interval_seconds
                )
            ),
        )
        live = LiveCaptureConfig(
            sample_fps=float(live_raw.get("sample_fps", live_defaults.sample_fps)),
            max_duration_seconds=float(
                live_raw.get("max_duration_seconds", live_defaults.max_duration_seconds)
            ),
            reconnect_interval_seconds=float(
                live_raw.get(
                    "reconnect_interval_seconds",
                    live_defaults.reconnect_interval_seconds,
                )
            ),
            reconnect_timeout_seconds=float(
                live_raw.get(
                    "reconnect_timeout_seconds",
                    live_defaults.reconnect_timeout_seconds,
                )
            ),
            buffer_capacity=int(
                live_raw.get("buffer_capacity", live_defaults.buffer_capacity)
            ),
            checkpoint_every=int(
                live_raw.get("checkpoint_every", live_defaults.checkpoint_every)
            ),
            segment_frames=int(
                live_raw.get("segment_frames", live_defaults.segment_frames)
            ),
            keyframe=keyframe,
        )

        return cls(
            storage=StorageConfig(
                data_volume=str(
                    storage_raw.get("data_volume", storage_defaults.data_volume)
                ),
                model_cache_volume=str(
                    storage_raw.get(
                        "model_cache_volume", storage_defaults.model_cache_volume
                    )
                ),
                data_mount=str(
                    storage_raw.get("data_mount", storage_defaults.data_mount)
                ),
                model_mount=str(
                    storage_raw.get("model_mount", storage_defaults.model_mount)
                ),
            ),
            video=video,
            camera=camera,
            vggt=vggt,
            sam2=sam2,
            perception=perception,
            memory=MemoryConfig(
                rooms=rooms,
                gravity=_section(
                    GravityConfig, memory_raw.get("gravity"), "memory.gravity"
                ),
                build=_section(
                    MemoryBuildConfig, memory_raw.get("build"), "memory.build"
                ),
                ranking=_section(
                    RankingConfig, memory_raw.get("ranking"), "memory.ranking"
                ),
                confidence=_section(
                    ConfidenceConfig,
                    memory_raw.get("confidence"),
                    "memory.confidence",
                ),
                evidence=_section(
                    EvidenceConfig, memory_raw.get("evidence"), "memory.evidence"
                ),
                retention=_section(
                    RetentionConfig, memory_raw.get("retention"), "memory.retention"
                ),
                home_id=_home_id(str(memory_raw.get("home_id", "home01"))),
                store_root=str(memory_raw.get("store_root", "outputs/_homes")),
            ),
            live=live,
            visualization=visualization,
            vocabulary=dict(vocabulary_raw),
        )


def load_config(path: str | Path) -> RuntimeConfig:
    """Load a YAML runtime configuration from ``path``.

    The vocabulary file named by the optional top-level ``vocabulary_file`` key
    (default ``vocabulary.yaml``, relative to the config file) is loaded and
    embedded so it travels to remote workers with the rest of the config.
    """

    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    if not isinstance(raw, Mapping):
        raise TypeError("configuration root must be a mapping")
    raw = dict(raw)
    if not raw.get("vocabulary"):
        vocabulary_name = str(raw.get("vocabulary_file") or "vocabulary.yaml")
        vocabulary_path = Path(vocabulary_name)
        if not vocabulary_path.is_absolute():
            vocabulary_path = config_path.parent / vocabulary_path
        raw["vocabulary"] = Vocabulary.load(vocabulary_path).to_mapping()
    return RuntimeConfig.from_mapping(raw)


def config_to_dict(config: RuntimeConfig) -> dict[str, Any]:
    """Convert a runtime configuration to a Modal-serializable dictionary."""

    return asdict(config)
