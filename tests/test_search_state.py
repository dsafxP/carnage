"""Tests for the debounced search state in the tab widgets."""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App, ComposeResult

import carnage.tui.widgets.browse.browse_tab as browse_tab_module
import carnage.tui.widgets.use_tab as use_tab_module
from carnage.core.cache import CacheManager
from carnage.core.portage.use import UseFlag
from carnage.tui.widgets.browse.browse_tab import BrowseTab
from carnage.tui.widgets.use_tab import UseFlagsTab


class _Config:
    """Stand-in for Configuration so the tests never touch the real file."""

    use_minimum_characters = 3
    browse_minimum_characters = 3


class _UseTabHarness(App[None]):
    def compose(self) -> ComposeResult:
        yield UseFlagsTab()


class _BrowseTabHarness(App[None]):
    def compose(self) -> ComposeResult:
        yield BrowseTab()


@pytest.fixture(autouse=True)
def isolated_widget_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(use_tab_module, "get_config", lambda: _Config())
    monkeypatch.setattr(use_tab_module, "get_cache_manager", lambda: CacheManager(tmp_path / "cache"))
    monkeypatch.setattr(browse_tab_module, "get_config", lambda: _Config())


async def test_clearing_the_query_drops_the_pending_debounce(monkeypatch: pytest.MonkeyPatch) -> None:
    performed: list[str] = []
    monkeypatch.setattr(UseFlagsTab, "_perform_search", lambda self, query: performed.append(query))

    async with _UseTabHarness().run_test() as pilot:
        tab = pilot.app.query_one(UseFlagsTab)

        tab.search_useflags("vim")
        assert tab._search_timer is not None

        # Below the minimum length: this clears the table and must also drop
        # the debounce that was scheduled for what was typed before.
        tab.search_useflags("vi")

        assert tab._search_timer is None
        assert tab._current_search == ""

        await pilot.pause(0.5)  # longer than the 0.3s debounce

        assert performed == []


async def test_clearing_hides_the_loading_indicator(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(UseFlagsTab, "_perform_search", lambda self, query: None)

    async with _UseTabHarness().run_test() as pilot:
        tab = pilot.app.query_one(UseFlagsTab)
        loading = tab.query_one("#useflags-loading")

        tab.search_useflags("vim")
        loading.display = True  # as an in-flight search would have left it

        tab.search_useflags("vi")

        assert loading.display is False


async def test_a_worker_for_a_stale_query_does_not_run(monkeypatch: pytest.MonkeyPatch) -> None:
    queried: list[str] = []
    monkeypatch.setattr(use_tab_module, "get_or_cache_useflags", lambda _cm: queried.append("ran") or [])

    async with _UseTabHarness().run_test() as pilot:
        tab = pilot.app.query_one(UseFlagsTab)

        # What _clear_table leaves behind: no live query for this worker.
        tab._current_search = ""
        tab._perform_search("vim")
        await pilot.pause(0.3)

        assert queried == []
        assert tab.filtered_useflags == []


async def test_a_worker_for_the_live_query_populates_and_unblocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        use_tab_module,
        "get_or_cache_useflags",
        lambda _cm: [UseFlag(name="vim", description="Vi IMproved")],
    )

    async with _UseTabHarness().run_test() as pilot:
        tab = pilot.app.query_one(UseFlagsTab)

        tab._current_search = "vim"
        tab._perform_search("vim")
        await pilot.pause(0.3)

        assert [flag.name for flag in tab.filtered_useflags] == ["vim"]
        assert tab.query_one("#useflags-loading").display is False
        assert tab.query_one("#useflags-table").display is True


async def test_clearing_drops_the_pending_package_debounce(monkeypatch: pytest.MonkeyPatch) -> None:
    queried: list[str] = []
    monkeypatch.setattr(browse_tab_module, "search_packages", lambda query: queried.append(query))

    async with _BrowseTabHarness().run_test() as pilot:
        tab = pilot.app.query_one(BrowseTab)

        tab.search_packages("vim")
        assert tab._search_timer is not None

        tab.search_packages("vi")

        assert tab._search_timer is None
        assert tab._current_search == ""
        assert tab._cancel_search is True

        await pilot.pause(0.5)

        assert queried == []
