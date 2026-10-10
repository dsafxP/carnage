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


def test_useflag_details_render_packages() -> None:
    """The join-based builder must render exactly what the loop did."""
    from carnage.core.eix.search import Package

    packages = [
        Package(category="app-editors", name="vim", description=None, homepage=None, licenses=[], versions=[]),
        Package(category="app-editors", name="nano", description=None, homepage=None, licenses=[], versions=[]),
    ]

    details = UseFlagsTab._format_useflag_details(UseFlag(name="gui", description="Desc"), 2, packages)

    assert details == (
        "[r]gui[/]\n\nDesc\n\n[b]Packages:[/] 2\n[b]Packages with this flag:[/]\n"
        "  • app-editors/vim\n  • app-editors/nano\n"
    )

    empty = UseFlagsTab._format_useflag_details(UseFlag(name="gui", description=None), 0, [])

    assert empty == "[r]gui[/]\n\n[b]Packages:[/] 0\n[red]No packages found with this flag[/]\n"


async def test_browse_table_draws_before_marks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rows appear from the search; the repo-missing marks land afterwards."""
    from textual.coordinate import Coordinate

    from carnage.core.eix.search import Package, PackageVersion

    def _package(name: str) -> Package:
        version = PackageVersion(
            id="1.0",
            eapi="8",
            repository="gentoo",
            virtual=False,
            installed=False,
            install_date=None,
            install_eapi=None,
            src_uri=None,
            iuse=[],
            iuse_default=[],
            required_use=None,
            depend=None,
            rdepend=None,
            bdepend=None,
            pdepend=None,
            idepend=None,
            masks=[],
            unmasks=[],
            properties=[],
            restricts=[],
            use_enabled=[],
            use_disabled=[],
        )
        return Package(
            category="app-editors", name=name, description="d", homepage=None, licenses=[], versions=[version]
        )

    packages = [_package("here"), _package("ghost")]
    monkeypatch.setattr(browse_tab_module, "search_packages", lambda query: packages)
    monkeypatch.setattr(browse_tab_module, "_exists_in_repo", lambda package: package.name != "ghost")

    async with _BrowseTabHarness().run_test() as pilot:
        tab = pilot.app.query_one(BrowseTab)
        tab._current_search = "e"
        tab._perform_search("e")
        await pilot.pause(0.5)

        assert len(tab.packages) == 2
        assert tab._missing_packages == frozenset({"app-editors/ghost"})
        assert "✗" not in str(tab.table.get_cell_at(Coordinate(0, 0)))
        assert "✗" in str(tab.table.get_cell_at(Coordinate(1, 0)))


async def test_reselecting_the_same_use_flag_is_a_noop() -> None:
    """Clicking the displayed flag again must not re-run its eix subprocess."""
    from textual.widgets import DataTable

    async with _UseTabHarness().run_test() as pilot:
        tab = pilot.app.query_one(UseFlagsTab)
        tab._populate_table([UseFlag(name="gui", description=None)])
        await pilot.pause(0.1)

        table = tab.query_one("#useflags-table", DataTable)
        key = table._row_locations.get_key(0)
        assert key is not None

        def select() -> None:
            tab.on_data_table_row_selected(DataTable.RowSelected(data_table=table, cursor_row=0, row_key=key))

        calls: list[str] = []
        tab._load_useflag_details = lambda useflag: calls.append(useflag.name)  # type: ignore[method-assign]

        select()
        await pilot.pause(0.3)
        select()
        await pilot.pause(0.3)

        assert calls == ["gui"]
