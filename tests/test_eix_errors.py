"""Tests for eix failure handling."""

from __future__ import annotations

from subprocess import CompletedProcess

import pytest

import carnage.core.eix.search as search_module
import carnage.core.eix.use as use_module


def _fake_result(stdout: str, returncode: int = 0) -> CompletedProcess[bytes]:
    return CompletedProcess(["eix"], returncode, stdout.encode(), b"")


def _fake_text_result(stdout: str, returncode: int = 0) -> CompletedProcess[str]:
    return CompletedProcess(["eix"], returncode, stdout, "")


@pytest.fixture(autouse=True)
def no_remote_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(search_module, "has_remote_cache", lambda: False)
    monkeypatch.setattr(use_module, "has_remote_cache", lambda: False)


def test_no_matches_is_not_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    # eix exits 1 when nothing matches and prints nothing at all.
    monkeypatch.setattr(search_module, "tracked_run", lambda *a, **k: _fake_result("", 1))

    assert search_module.fetch_packages_by_query(["vim"], append_cfg=False) == []


def test_non_xml_output_is_not_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(search_module, "tracked_run", lambda *a, **k: _fake_result("eix: error: broken cache"))

    assert search_module.fetch_packages_by_query(["vim"], append_cfg=False) == []


def test_valid_xml_is_still_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    xml = '<eix><category name="app-editors"><package name="vim"/></category></eix>'
    monkeypatch.setattr(search_module, "tracked_run", lambda *a, **k: _fake_result(xml))

    packages = search_module.fetch_packages_by_query(["vim"], append_cfg=False)

    assert [package.full_name for package in packages] == ["app-editors/vim"]


def test_use_flag_listing_checks_the_exit_status(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_tracked_run(*args, **kwargs):
        seen.update(kwargs)
        return _fake_text_result("flag-a\nflag-b\n")

    monkeypatch.setattr(use_module, "tracked_run", fake_tracked_run)

    assert use_module.get_all_useflags() == ["flag-a", "flag-b"]
    assert seen.get("check") is True
