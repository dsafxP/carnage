"""Tests for the hardening of subprocess, cache and fetch paths."""

from __future__ import annotations

import os
from pathlib import Path
from typing import ClassVar

import pytest

import carnage.core.portage.overlays as overlays_module
import carnage.core.process as process_module
from carnage.core.cache import CacheManager
from carnage.core.process import tracked_run


class _RecordingProcess:
    """Stands in for TrackedProcess and records the kwargs it would receive."""

    seen: ClassVar[dict[str, object]] = {}

    def __init__(self, args, **kwargs) -> None:
        type(self).seen = dict(kwargs)

    def run(self):
        return "result"


def test_tracked_run_supplies_a_default_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(process_module, "TrackedProcess", _RecordingProcess)

    assert tracked_run(["eix", "-Qq0"]) == "result"
    assert _RecordingProcess.seen["timeout"] == process_module.DEFAULT_TIMEOUT


def test_an_explicit_timeout_wins_over_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(process_module, "TrackedProcess", _RecordingProcess)

    tracked_run(["eix", "-Qq0"], timeout=5)

    assert _RecordingProcess.seen["timeout"] == 5


def test_cache_entries_are_readable_and_leave_no_temp_files(tmp_path: Path) -> None:
    cache = CacheManager(tmp_path / "cache")

    cache.set("overlays_data", [{"name": "gentoo"}])

    assert cache.get("overlays_data") == [{"name": "gentoo"}]
    assert cache.get_age("overlays_data") is not None
    assert not list((tmp_path / "cache").glob("*.tmp"))


def test_a_fresh_cache_directory_is_private(tmp_path: Path) -> None:
    directory = tmp_path / "cache"

    CacheManager(directory)

    assert os.stat(directory).st_mode & 0o777 == 0o700


class _Config:
    overlay_source = "https://example.invalid/repositories.xml"


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self, size: int = -1) -> bytes:
        return self._payload if size < 0 else self._payload[:size]

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc) -> bool:
        return False


def _stub_network(monkeypatch: pytest.MonkeyPatch, payload: bytes) -> None:
    monkeypatch.setattr(overlays_module, "get_config", lambda: _Config())
    monkeypatch.setattr(
        overlays_module.urllib.request,
        "urlopen",
        lambda *args, **kwargs: _FakeResponse(payload),
    )


def test_oversized_overlay_source_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_network(monkeypatch, b"x" * (overlays_module._MAX_SOURCE_BYTES + 1))

    with pytest.raises(ValueError):
        overlays_module.fetch("https://example.invalid/repositories.xml")


def test_a_valid_overlay_document_still_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    xml = (
        b'<?xml version="1.0"?><overlayconfig>'
        b'<repo quality="core" status="official"><name>gentoo</name>'
        b'<owner type="person"><name>Alice</name><email>a@example.invalid</email></owner>'
        b'<source type="rsync">https://example.invalid/repo</source></repo></overlayconfig>'
    )
    _stub_network(monkeypatch, xml)

    overlays = overlays_module.fetch("https://example.invalid/repositories.xml")

    assert [overlay.name for overlay in overlays] == ["gentoo"]


def test_malformed_overlay_document_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    # recover mode used to swallow this and return half a list.
    _stub_network(monkeypatch, b"<?xml version='1.0'?><overlayconfig><repo><name>trunc")

    with pytest.raises(overlays_module.etree.ParseError):
        overlays_module.fetch("https://example.invalid/repositories.xml")
