"""Tests for batched overlay package counting."""

from __future__ import annotations

from subprocess import CompletedProcess

import pytest

import carnage.core.eix.overlay as overlay_module
from carnage.core.eix.overlay import get_all_package_counts

XML = """<?xml version="1.0" encoding="UTF-8"?>
<eixdump version="16">
  <category name="app-editors">
    <package name="vim"><version id="9.0" repository="gentoo"/></package>
    <package name="neovim">
      <version id="0.1" repository="gentoo"/>
      <version id="0.2" repository="guru"/>
    </package>
    <package name="only-remote"><version id="1.0" repository="guru"/></package>
    <package name="virtualized"><version id="1.0" virtual="1" repository="guru"/></package>
    <package name="unlisted"><version id="2.0"/></package>
  </category>
</eixdump>
"""


@pytest.fixture(autouse=True)
def caches_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(overlay_module, "has_remote_cache", lambda: False)
    monkeypatch.setattr(overlay_module, "has_cache", lambda: True)


def _run(cmd: list[str], **kwargs) -> CompletedProcess[bytes]:
    assert cmd == ["eix", "--xml", "*"]
    assert kwargs["env"]["EIX_LIMIT"] == "0"
    return CompletedProcess(cmd, 0, XML.encode(), b"")


def test_counts_group_exclusive_packages(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(overlay_module, "tracked_run", _run)

    counts = get_all_package_counts()

    assert counts == {"gentoo": 2, "guru": 2}


def test_virtual_versions_count_like_the_rest(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remote-only versions carry a repository like everything else."""
    monkeypatch.setattr(overlay_module, "tracked_run", _run)

    counts = get_all_package_counts()

    assert counts is not None
    assert counts["guru"] == 2  # only-remote and virtualized


def test_missing_repository_means_gentoo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(overlay_module, "tracked_run", _run)

    counts = get_all_package_counts()

    assert counts is not None
    assert counts["gentoo"] == 2  # vim and unlisted


def test_absent_overlays_are_not_listed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(overlay_module, "tracked_run", _run)

    counts = get_all_package_counts()

    assert counts is not None
    assert "no-such-overlay" not in counts


def test_no_cache_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(overlay_module, "has_remote_cache", lambda: False)
    monkeypatch.setattr(overlay_module, "has_cache", lambda: False)

    def boom(*args: object, **kwargs: object) -> CompletedProcess[bytes]:
        raise AssertionError("eix must not run without a cache")

    monkeypatch.setattr(overlay_module, "tracked_run", boom)

    assert get_all_package_counts() is None


def test_remote_cache_selects_the_remote_query(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs) -> CompletedProcess[bytes]:
        seen.append(cmd)
        return CompletedProcess(cmd, 0, b"<eixdump/>", b"")

    monkeypatch.setattr(overlay_module, "has_remote_cache", lambda: True)
    monkeypatch.setattr(overlay_module, "tracked_run", fake_run)

    assert get_all_package_counts() == {}
    assert seen == [["eix", "-R", "--xml", "*"]]
