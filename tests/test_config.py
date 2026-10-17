"""Tests for the shared runtime configuration contract."""

from pathlib import Path

import pytest

from aegis.core.config import RuntimeConfig, config_to_dict, load_config
from aegis.core.paths import dataset_paths, validate_dataset_id


def test_example_config_loads() -> None:
    config = load_config(Path("config/demo.yaml"))

    assert config.video.sample_fps == 15
    assert config.depth.mode == "metric"
    assert config.storage.data_mount == "/data"
    assert config.vggt.model_id == "facebook/VGGT-Omega"
    assert config.sam2.model_id == "facebook/sam2-hiera-large"
    assert config_to_dict(config)["pose"]["stride"] == 1


def test_room_memory_config_defaults_and_overrides() -> None:
    config = RuntimeConfig.from_mapping({})
    assert config.memory.rooms.enabled is True
    assert config.memory.rooms.zone_link_radius == 1.5
    assert config.memory.rooms.min_zone_keyframes == 3

    custom = RuntimeConfig.from_mapping(
        {
            "memory": {
                "rooms": {
                    "enabled": False,
                    "zone_link_radius": 2.0,
                    "min_zone_keyframes": 5,
                }
            }
        }
    )
    assert custom.memory.rooms.enabled is False
    assert custom.memory.rooms.zone_link_radius == 2.0
    assert custom.memory.rooms.min_zone_keyframes == 5


def test_room_memory_config_rejects_invalid_thresholds() -> None:
    with pytest.raises(ValueError):
        RuntimeConfig.from_mapping({"memory": {"rooms": {"zone_link_radius": 0.0}}})
    with pytest.raises(ValueError):
        RuntimeConfig.from_mapping({"memory": {"rooms": {"min_zone_keyframes": 0}}})


def test_dataset_paths_are_canonical() -> None:
    config = RuntimeConfig.from_mapping({})
    paths = dataset_paths(config, "demo01")

    assert paths.frames == Path("/data/demo01/frames")
    assert paths.rerun_recording == Path("/data/demo01/outputs/viewer/demo.rrd")


def test_dataset_id_cannot_escape_mount() -> None:
    with pytest.raises(ValueError):
        validate_dataset_id("../private")
