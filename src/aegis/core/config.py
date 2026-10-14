"""Configuration loading for the Modal-first Aegis pipeline."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_DROID_WEIGHTS_URL = (
    "https://drive.google.com/uc?id=1PpqVt1H4maBa_GbPJp4NwxRsd9jk-elh"
)
DEFAULT_DROID_CALIB_WEIGHTS_URL = (
    "https://raw.githubusercontent.com/boschresearch/DroidCalib/main/droidcalib.pth"
)


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
    """Camera calibration settings used by DROID-SLAM and lifting.

    ``calibration_mode`` controls how missing intrinsics are handled. The
    default requires a supplied calibration file or configured intrinsics;
    self-calibration and approximate intrinsics are explicit alternatives.
    """

    calibration_filename: str = "calib.txt"
    intrinsics: tuple[float, float, float, float] | None = None
    intrinsics_resolution: tuple[int, int] | None = None
    calibration_mode: str = "provided"
    allow_approximate: bool = False
    self_calibration_weights_filename: str = "droidcalib.pth"
    self_calibration_weights_url: str = DEFAULT_DROID_CALIB_WEIGHTS_URL
    self_calibration_camera_model: str = "pinhole"
    self_calibration_stride: int = 1
    self_calibration_max_frames: int = 0
    self_calibration_width: int = 517
    self_calibration_height: int = 384


@dataclass(frozen=True, slots=True)
class DepthConfig:
    """Depth Anything V2 inference settings."""

    model_id: str = "depth-anything/Depth-Anything-V2-Metric-Indoor-Small-hf"
    mode: str = "metric"
    batch_size: int = 2
    fp16: bool = True


@dataclass(frozen=True, slots=True)
class PoseConfig:
    """DROID-SLAM inference settings."""

    weights_filename: str = "droid.pth"
    weights_url: str = DEFAULT_DROID_WEIGHTS_URL
    stride: int = 1
    buffer: int = 512
    filter_thresh: float = 2.4
    beta: float = 0.3
    frontend_thresh: float = 16.0
    frontend_window: int = 25
    frontend_radius: int = 2
    frontend_nms: int = 1
    backend_thresh: float = 22.0
    backend_radius: int = 2
    backend_nms: int = 3
    asynchronous: bool = False


@dataclass(frozen=True, slots=True)
class GeometryConfig:
    """Point-cloud construction settings."""

    max_points_per_frame: int = 5000
    max_total_points: int = 150000
    depth_min: float = 0.1
    depth_max: float = 20.0
    depth_scale: float = 1.0
    pose_scale: float = 1.0


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
    image_size: int = 518
    keyframe_stride: int = 6
    batch_size: int = 1
    dtype: str = "bfloat16"


@dataclass(frozen=True, slots=True)
class Sam2Config:
    """SAM 2 instance segmentation and tracking settings."""

    model_id: str = "facebook/sam2-hiera-large"
    prompt_confidence_threshold: float = 0.35
    multimask_output: bool = False


@dataclass(frozen=True, slots=True)
class PerceptionConfig:
    """2D/3D object perception and tracking settings.

    YOLOE is the default because it produces open-vocabulary masks directly;
    YOLO-World remains available as a detector-only fallback.
    """

    detector_backend: str = "yoloe"
    detector_model: str = "yoloe-11l-seg.pt"
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


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """Complete configuration passed from the local orchestrator to Modal."""

    storage: StorageConfig = field(default_factory=StorageConfig)
    video: VideoConfig = field(default_factory=VideoConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)
    depth: DepthConfig = field(default_factory=DepthConfig)
    pose: PoseConfig = field(default_factory=PoseConfig)
    vggt: VggtConfig = field(default_factory=VggtConfig)
    sam2: Sam2Config = field(default_factory=Sam2Config)
    perception: PerceptionConfig = field(default_factory=PerceptionConfig)
    geometry: GeometryConfig = field(default_factory=GeometryConfig)
    visualization: VisualizationConfig = field(default_factory=VisualizationConfig)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> RuntimeConfig:
        """Build and validate a runtime configuration from a nested mapping."""

        storage_raw = _mapping(raw.get("storage"), "storage")
        video_raw = _mapping(raw.get("video"), "video")
        camera_raw = _mapping(raw.get("camera"), "camera")
        depth_raw = _mapping(raw.get("depth"), "depth")
        pose_raw = _mapping(raw.get("pose"), "pose")
        vggt_raw = _mapping(raw.get("vggt"), "vggt")
        sam2_raw = _mapping(raw.get("sam2"), "sam2")
        perception_raw = _mapping(raw.get("perception"), "perception")
        geometry_raw = _mapping(raw.get("geometry"), "geometry")
        visualization_raw = _mapping(raw.get("visualization"), "visualization")

        storage_defaults = StorageConfig()
        video_defaults = VideoConfig()
        camera_defaults = CameraConfig()
        depth_defaults = DepthConfig()
        pose_defaults = PoseConfig()
        vggt_defaults = VggtConfig()
        sam2_defaults = Sam2Config()
        perception_defaults = PerceptionConfig()
        geometry_defaults = GeometryConfig()
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
            self_calibration_weights_filename=str(
                camera_raw.get(
                    "self_calibration_weights_filename",
                    camera_defaults.self_calibration_weights_filename,
                )
            ),
            self_calibration_weights_url=str(
                camera_raw.get(
                    "self_calibration_weights_url",
                    camera_defaults.self_calibration_weights_url,
                )
            ),
            self_calibration_camera_model=str(
                camera_raw.get(
                    "self_calibration_camera_model",
                    camera_defaults.self_calibration_camera_model,
                )
            ).lower(),
            self_calibration_stride=int(
                camera_raw.get(
                    "self_calibration_stride", camera_defaults.self_calibration_stride
                )
            ),
            self_calibration_max_frames=int(
                camera_raw.get(
                    "self_calibration_max_frames",
                    camera_defaults.self_calibration_max_frames,
                )
            ),
            self_calibration_width=int(
                camera_raw.get(
                    "self_calibration_width", camera_defaults.self_calibration_width
                )
            ),
            self_calibration_height=int(
                camera_raw.get(
                    "self_calibration_height", camera_defaults.self_calibration_height
                )
            ),
        )
        if camera.self_calibration_camera_model not in {"pinhole", "focal", "mei"}:
            raise ValueError(
                "camera.self_calibration_camera_model must be 'pinhole', 'focal', "
                "or 'mei'"
            )
        if (
            camera.self_calibration_stride <= 0
            or camera.self_calibration_max_frames < 0
            or camera.self_calibration_width <= 0
            or camera.self_calibration_height <= 0
        ):
            raise ValueError("self-calibration settings are outside their valid ranges")

        depth = DepthConfig(
            model_id=str(depth_raw.get("model_id", depth_defaults.model_id)),
            mode=str(depth_raw.get("mode", depth_defaults.mode)).lower(),
            batch_size=int(depth_raw.get("batch_size", depth_defaults.batch_size)),
            fp16=bool(depth_raw.get("fp16", depth_defaults.fp16)),
        )
        if depth.mode not in {"metric", "relative"}:
            raise ValueError("depth.mode must be either 'metric' or 'relative'")
        if depth.batch_size <= 0:
            raise ValueError("depth.batch_size must be positive")

        pose = PoseConfig(
            weights_filename=str(
                pose_raw.get("weights_filename", pose_defaults.weights_filename)
            ),
            weights_url=str(pose_raw.get("weights_url", pose_defaults.weights_url)),
            stride=int(pose_raw.get("stride", pose_defaults.stride)),
            buffer=int(pose_raw.get("buffer", pose_defaults.buffer)),
            filter_thresh=float(
                pose_raw.get("filter_thresh", pose_defaults.filter_thresh)
            ),
            beta=float(pose_raw.get("beta", pose_defaults.beta)),
            frontend_thresh=float(
                pose_raw.get("frontend_thresh", pose_defaults.frontend_thresh)
            ),
            frontend_window=int(
                pose_raw.get("frontend_window", pose_defaults.frontend_window)
            ),
            frontend_radius=int(
                pose_raw.get("frontend_radius", pose_defaults.frontend_radius)
            ),
            frontend_nms=int(pose_raw.get("frontend_nms", pose_defaults.frontend_nms)),
            backend_thresh=float(
                pose_raw.get("backend_thresh", pose_defaults.backend_thresh)
            ),
            backend_radius=int(
                pose_raw.get("backend_radius", pose_defaults.backend_radius)
            ),
            backend_nms=int(pose_raw.get("backend_nms", pose_defaults.backend_nms)),
            asynchronous=bool(pose_raw.get("asynchronous", pose_defaults.asynchronous)),
        )
        if pose.stride <= 0 or pose.buffer <= 0:
            raise ValueError("pose stride and buffer must be positive")

        vggt = VggtConfig(
            model_id=str(vggt_raw.get("model_id", vggt_defaults.model_id)),
            image_size=int(vggt_raw.get("image_size", vggt_defaults.image_size)),
            keyframe_stride=int(
                vggt_raw.get("keyframe_stride", vggt_defaults.keyframe_stride)
            ),
            batch_size=int(vggt_raw.get("batch_size", vggt_defaults.batch_size)),
            dtype=str(vggt_raw.get("dtype", vggt_defaults.dtype)),
        )
        if vggt.keyframe_stride <= 0 or vggt.image_size <= 0:
            raise ValueError("vggt settings must be positive")

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
        )

        target_classes_raw = perception_raw.get("target_classes")
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
        )

        if perception.detector_backend not in {"yoloe", "yolo_world"}:
            raise ValueError(
                "perception.detector_backend must be 'yoloe' or 'yolo_world'"
            )

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

        geometry = GeometryConfig(
            max_points_per_frame=int(
                geometry_raw.get(
                    "max_points_per_frame", geometry_defaults.max_points_per_frame
                )
            ),
            max_total_points=int(
                geometry_raw.get("max_total_points", geometry_defaults.max_total_points)
            ),
            depth_min=float(geometry_raw.get("depth_min", geometry_defaults.depth_min)),
            depth_max=float(geometry_raw.get("depth_max", geometry_defaults.depth_max)),
            depth_scale=float(
                geometry_raw.get("depth_scale", geometry_defaults.depth_scale)
            ),
            pose_scale=float(
                geometry_raw.get("pose_scale", geometry_defaults.pose_scale)
            ),
        )
        if (
            geometry.max_points_per_frame <= 0
            or geometry.max_total_points <= 0
            or geometry.depth_min <= 0
            or geometry.depth_max <= geometry.depth_min
            or geometry.depth_scale <= 0
            or geometry.pose_scale <= 0
        ):
            raise ValueError("geometry values are outside their valid ranges")

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
            depth=depth,
            pose=pose,
            vggt=vggt,
            sam2=sam2,
            perception=perception,
            geometry=geometry,
            visualization=visualization,
        )


def load_config(path: str | Path) -> RuntimeConfig:
    """Load a YAML runtime configuration from ``path``."""

    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    if not isinstance(raw, Mapping):
        raise TypeError("configuration root must be a mapping")
    return RuntimeConfig.from_mapping(raw)


def config_to_dict(config: RuntimeConfig) -> dict[str, Any]:
    """Convert a runtime configuration to a Modal-serializable dictionary."""

    return asdict(config)
