"""Tests for the memoized eix remote-cache probe."""

from __future__ import annotations

from subprocess import CompletedProcess

import pytest

import carnage.core.eix.eix as eix_module


def test_remote_cache_is_probed_once_until_invalidated(monkeypatch: pytest.MonkeyPatch) -> None:
    returncodes = iter([0, 1])

    def fake_tracked_run(*args, **kwargs) -> CompletedProcess[int]:
        # StopIteration here would mean the memo was bypassed.
        return CompletedProcess(["eix"], next(returncodes))

    monkeypatch.setattr(eix_module, "tracked_run", fake_tracked_run)

    assert eix_module.has_remote_cache() is True
    assert eix_module.has_remote_cache() is True

    eix_module.invalidate_remote_cache()

    assert eix_module.has_remote_cache() is False
