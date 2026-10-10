"""Tests for activation-driven deferred tab loads."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Input, TabbedContent, TabPane

import carnage.tui.screens.main_screen as main_screen_module
import carnage.tui.widgets.glsa_tab as glsa_tab_module
import carnage.tui.widgets.overlay_tab as overlay_tab_module
from carnage.core.cache import CacheManager
from carnage.tui.screens.main_screen import MainScreen
from carnage.tui.widgets.glsa_tab import GLSATab
from carnage.tui.widgets.overlay_tab import OverlaysTab


class _Config:
    skip_package_counting = True
    ignore_warnings = True
    compact_mode = False
    automatic_pane = False


class _Harness(App[None]):
    blocked = False

    def compose(self) -> ComposeResult:
        yield MainScreen()


@pytest.fixture(autouse=True)
def env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(main_screen_module, "get_config", lambda: _Config())
    monkeypatch.setattr(main_screen_module, "is_found", lambda: True)
    monkeypatch.setattr(main_screen_module, "has_cache", lambda: True)
    monkeypatch.setattr(overlay_tab_module, "get_config", lambda: _Config())
    monkeypatch.setattr(overlay_tab_module, "get_cache_manager", lambda: CacheManager(tmp_path / "cache"))
    monkeypatch.setattr(glsa_tab_module, "get_config", lambda: _Config())


async def test_switching_to_overlays_starts_its_load_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """The activation event carries the prefixed button id, not the pane id."""
    calls: list[str] = []
    monkeypatch.setattr(OverlaysTab, "load_overlays", lambda self: calls.append("overlays"))
    monkeypatch.setattr(GLSATab, "load_glsas", lambda self: calls.append("glsas"))

    app = _Harness()
    async with app.run_test() as pilot:
        tabs = app.query_one(TabbedContent)
        tabs.active = "news"
        await pilot.pause(0.3)
        calls.clear()

        # Simulate a fresh visit: the mount-time ensure may already have run
        # for a restored tab.
        tabs.query_one("#overlays", TabPane).query_one(OverlaysTab)._loaded = False

        tabs.active = "overlays"
        await pilot.pause(0.3)

        assert calls == ["overlays"]

        tabs.active = "news"
        await pilot.pause(0.3)
        tabs.active = "overlays"
        await pilot.pause(0.3)

        assert calls == ["overlays"]


async def test_switching_to_glsas_starts_its_load(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(GLSATab, "load_glsas", lambda self: calls.append("glsas"))

    app = _Harness()
    async with app.run_test() as pilot:
        tabs = app.query_one(TabbedContent)
        tabs.active = "news"
        await pilot.pause(0.3)
        calls.clear()

        tabs.active = "glsas"
        await pilot.pause(0.3)

        assert calls == ["glsas"]
        assert tabs.query_one("#glsas", TabPane).query_one(GLSATab)._loaded is True


async def test_activation_still_updates_the_search_bar() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        tabs = app.query_one(TabbedContent)
        search = app.query_one("#search-input", Input)

        tabs.active = "overlays"
        await pilot.pause(0.3)

        assert search.placeholder == "Search overlays ..."
        assert search.disabled is False
