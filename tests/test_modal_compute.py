"""Ensure Modal VGGT/perception workers keep explicit CPU/GPU sizing."""

from aegis.remote.modal_app import CPU_ONLY, GPU_TYPE, _compute


def test_compute_cpu_fallback_uses_sixteen_cores() -> None:
    vggt = _compute(24576, 40960)
    perception = _compute(16384, 40960)
    if CPU_ONLY:
        assert vggt == {"cpu": 16.0, "memory": 40960}
        assert perception == {"cpu": 16.0, "memory": 40960}
        return
    assert vggt == {"gpu": GPU_TYPE, "memory": 24576}
    assert perception == {"gpu": GPU_TYPE, "memory": 16384}
