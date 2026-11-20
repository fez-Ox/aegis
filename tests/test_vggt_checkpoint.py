"""The VGGT checkpoint download must survive a gated-repo refusal.

A Hugging Face token can be valid and still be denied: the account has to be
on the gated repo's authorized list. The same weights are public in a mirror,
so the worker falls back instead of failing a warmed-up GPU run.
"""

from __future__ import annotations

import sys
import types

import pytest

from aegis.geometry import vggt_runner


class FakeGatedRepoError(Exception):
    """Stand-in for ``huggingface_hub.errors.GatedRepoError``."""


def _install_fake_hub(monkeypatch, calls: list[str], denied: set[str]) -> None:
    hub = types.ModuleType("huggingface_hub")
    errors = types.ModuleType("huggingface_hub.errors")
    errors.GatedRepoError = FakeGatedRepoError

    def hf_hub_download(*, repo_id, filename, token=None, cache_dir=None):
        calls.append(repo_id)
        if repo_id in denied:
            raise FakeGatedRepoError(f"403 for {repo_id}")
        return f"/cache/{repo_id}/{filename}"

    hub.hf_hub_download = hf_hub_download
    hub.errors = errors
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)
    monkeypatch.setitem(sys.modules, "huggingface_hub.errors", errors)


def test_gated_repo_falls_back_to_the_public_mirror(monkeypatch):
    calls: list[str] = []
    _install_fake_hub(monkeypatch, calls, denied={"facebook/VGGT-Omega"})

    path = vggt_runner.download_checkpoint("facebook/VGGT-Omega", hf_token="hf_x")

    assert (
        path == f"/cache/{vggt_runner.FALLBACK_REPO}/{vggt_runner.CHECKPOINT_FILENAME}"
    )
    assert calls == ["facebook/VGGT-Omega", vggt_runner.FALLBACK_REPO]


def test_authorized_repo_is_used_directly(monkeypatch):
    calls: list[str] = []
    _install_fake_hub(monkeypatch, calls, denied=set())

    vggt_runner.download_checkpoint("facebook/VGGT-Omega", hf_token="hf_x")

    assert calls == ["facebook/VGGT-Omega"]


def test_denied_mirror_is_not_retried_forever(monkeypatch):
    calls: list[str] = []
    _install_fake_hub(monkeypatch, calls, denied={vggt_runner.FALLBACK_REPO})

    with pytest.raises(FakeGatedRepoError):
        vggt_runner.download_checkpoint(vggt_runner.FALLBACK_REPO)

    assert calls == [vggt_runner.FALLBACK_REPO]
