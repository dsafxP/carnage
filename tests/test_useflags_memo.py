"""Tests for the in-memory USE flags memo."""

from __future__ import annotations

from pathlib import Path

import pytest

import carnage.core.portage.use as use_module
from carnage.core.cache import CacheManager
from carnage.core.portage.use import UseFlag, get_or_cache_useflags


class _Config:
    use_cache_max_age = 96


@pytest.fixture(autouse=True)
def stub_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the tests off the real ~/.config/carnage directory."""
    monkeypatch.setattr(use_module, "get_config", lambda: _Config())


def _manager(tmp_path: Path) -> CacheManager:
    return CacheManager(tmp_path / "cache")


def test_second_call_skips_the_disk(tmp_path: Path, monkeypatch) -> None:
    """Decoding happens once no matter how many keystrokes follow."""
    cache = _manager(tmp_path)
    cache.set(use_module.CACHE_KEY_USEFLAGS, [{"name": "gui", "description": "Desc"}])

    reads: list[str] = []
    real_get = cache.get

    def counting_get(key: str):
        reads.append(key)
        return real_get(key)

    monkeypatch.setattr(cache, "get", counting_get)

    first = get_or_cache_useflags(cache)
    second = get_or_cache_useflags(cache)

    assert [flag.name for flag in first] == ["gui"]
    assert second is first
    assert reads == [use_module.CACHE_KEY_USEFLAGS]


def test_force_refresh_fetches_again(tmp_path: Path, monkeypatch) -> None:
    cache = _manager(tmp_path)
    cache.set(use_module.CACHE_KEY_USEFLAGS, [{"name": "gui", "description": "Desc"}])

    assert [flag.name for flag in get_or_cache_useflags(cache)] == ["gui"]

    monkeypatch.setattr(use_module, "get_all_useflags", lambda: ["ssl"])
    monkeypatch.setattr(use_module, "_parse_useflag_descriptions", lambda: {})

    refreshed = get_or_cache_useflags(cache, force_refresh=True)

    assert [flag.name for flag in refreshed] == ["ssl"]
    # The memo follows the refresh rather than the stale disk copy.
    assert [flag.name for flag in get_or_cache_useflags(cache)] == ["ssl"]


def test_memo_returns_useflag_objects(tmp_path: Path) -> None:
    cache = _manager(tmp_path)
    cache.set(use_module.CACHE_KEY_USEFLAGS, [{"name": "gui", "description": None}])

    (flag,) = get_or_cache_useflags(cache)

    assert isinstance(flag, UseFlag)
