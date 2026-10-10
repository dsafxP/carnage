"""Tests for deferred tab loading."""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App, ComposeResult

import carnage.tui.widgets.glsa_tab as glsa_tab_module
import carnage.tui.widgets.overlay_tab as overlay_tab_module
from carnage.core.cache import CacheManager
from carnage.tui.widgets.glsa_tab import GLSATab
from carnage.tui.widgets.overlay_tab import OverlaysTab


class _Config:
    skip_package_counting = True
    ignore_warnings = True


class _OverlaysHarness(App[None]):
    blocked = False

    def compose(self) -> ComposeResult:
        yield OverlaysTab()


class _GlsaHarness(App[None]):
    blocked = False

    def compose(self) -> ComposeResult:
        yield GLSATab()


@pytest.fixture(autouse=True)
def no_real_backends(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(overlay_tab_module, "get_config", lambda: _Config())
    monkeypatch.setattr(overlay_tab_module, "get_cache_manager", lambda: CacheManager(tmp_path / "cache"))
    monkeypatch.setattr(overlay_tab_module, "is_found", lambda: False)
    # Silence the GLSA warning path, which needs a TabbedContent ancestor.
    monkeypatch.setattr(glsa_tab_module, "get_config", lambda: _Config())


async def test_overlays_mount_starts_no_load_but_ensure_does_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(OverlaysTab, "load_overlays", lambda self: calls.append("load"))

    async with _OverlaysHarness().run_test() as pilot:
        tab = pilot.app.query_one(OverlaysTab)
        await pilot.pause(0.3)

        assert calls == []
        # No load runs, so no spinner either: the table sits visible.
        assert tab.query_one("#overlays-loading").display is False
        assert tab.query_one("#overlays-table").display is True

        tab.ensure_loaded()
        tab.ensure_loaded()

        assert calls == ["load"]


async def test_overlays_failed_start_stays_unloaded(monkeypatch: pytest.MonkeyPatch) -> None:
    """A worker that never starts must not park the tab as loaded."""

    def boom(self: OverlaysTab) -> None:
        raise RuntimeError("no workers here")

    monkeypatch.setattr(OverlaysTab, "load_overlays", boom)

    async with _OverlaysHarness().run_test() as pilot:
        tab = pilot.app.query_one(OverlaysTab)
        tab.ensure_loaded()
        await pilot.pause(0.1)

        assert tab._loaded is False
        assert tab.query_one("#overlays-loading").display is False


async def test_overlays_failed_load_retries_on_revisit(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed load clears the flag so the next activation tries again."""
    attempts: list[str] = []

    def failing_fetch(_cache_manager: object) -> list:
        attempts.append("fetch")
        raise RuntimeError("net down")

    monkeypatch.setattr(overlay_tab_module, "get_or_cache", failing_fetch)

    async with _OverlaysHarness().run_test() as pilot:
        tab = pilot.app.query_one(OverlaysTab)
        tab.ensure_loaded()
        await pilot.pause(0.5)

        assert attempts == ["fetch"]
        assert tab._loaded is False
        assert tab.query_one("#overlays-loading").display is False

        tab.ensure_loaded()
        await pilot.pause(0.5)

        assert attempts == ["fetch", "fetch"]


async def test_glsa_mount_starts_no_load_but_ensure_does_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(GLSATab, "load_glsas", lambda self: calls.append("load"))

    async with _GlsaHarness().run_test() as pilot:
        tab = pilot.app.query_one(GLSATab)
        await pilot.pause(0.3)

        assert calls == []
        assert tab.query_one("#glsa-loading").display is False
        assert tab.query_one("#glsa-table").display is True

        tab.ensure_loaded()
        tab.ensure_loaded()

        assert calls == ["load"]
