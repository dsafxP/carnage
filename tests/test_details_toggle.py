"""Tests for the hideable detail panes."""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App, ComposeResult
from textual.widgets import DataTable, LoadingIndicator, Static

import carnage.tui.widgets.overlay_tab as overlay_tab_module
import carnage.tui.widgets.use_tab as use_tab_module
from carnage.core.cache import CacheManager
from carnage.core.eix.search import Package, PackageVersion
from carnage.core.portage.overlays import (
    Overlay,
    OverlayQuality,
    OverlayStatus,
    Owner,
    Source,
    SourceType,
)
from carnage.core.portage.use import UseFlag
from carnage.tui.widgets.browse.browse_tab import BrowseTab
from carnage.tui.widgets.glsa_tab import GLSATab
from carnage.tui.widgets.news_tab import NewsTab
from carnage.tui.widgets.overlay_tab import OverlaysTab
from carnage.tui.widgets.table_tab import TableTab
from carnage.tui.widgets.use_tab import UseFlagsTab


class _DetailBare(TableTab):
    """Minimal sortable-free tab with a detail pane."""

    TABLE_ID = "bare-table"
    LOADING_ID = "bare-loading"
    DETAIL_ID = "bare-detail"

    def compose(self) -> ComposeResult:
        yield LoadingIndicator(id="bare-loading")
        yield DataTable(id="bare-table")
        yield Static("", id="bare-detail")


class _BareHarness(App[None]):
    def compose(self) -> ComposeResult:
        yield _DetailBare()


async def test_toggle_flips_the_detail_pane() -> None:
    app = _BareHarness()

    async with app.run_test() as pilot:
        tab = app.query_one(_DetailBare)
        assert tab.details.display is True

        tab.hide_details()
        assert tab.details.display is False

        tab.toggle_details()
        assert tab.details.display is True

        tab.toggle_details()
        assert tab.details.display is False

        await pilot.pause(0.1)


async def test_hiding_returns_focus_to_the_table() -> None:
    app = _BareHarness()

    async with app.run_test() as pilot:
        tab = app.query_one(_DetailBare)
        tab.details.focus()
        await pilot.pause(0.1)

        tab.hide_details()

        assert tab.details.display is False
        assert app.focused is tab.table


class _Config:
    skip_package_counting = True
    ignore_warnings = True
    use_minimum_characters = 3
    browse_minimum_characters = 3


@pytest.fixture(autouse=True)
def isolated_tabs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(use_tab_module, "get_config", lambda: _Config())
    monkeypatch.setattr(use_tab_module, "get_cache_manager", lambda: CacheManager(tmp_path / "cache"))
    monkeypatch.setattr(overlay_tab_module, "get_config", lambda: _Config())
    monkeypatch.setattr(overlay_tab_module, "get_cache_manager", lambda: CacheManager(tmp_path / "cache"))
    monkeypatch.setattr(overlay_tab_module, "is_found", lambda: False)
    monkeypatch.setattr(OverlaysTab, "load_overlays", lambda self: None)
    monkeypatch.setattr(GLSATab, "load_glsas", lambda self: None)
    monkeypatch.setattr(NewsTab, "load_news", lambda self: None)


def _overlay(name: str) -> Overlay:
    return Overlay(
        name=name,
        description="A test overlay",
        homepage=None,
        owner=Owner(name="Alice", email="a@example.invalid", owner_type="person"),
        sources=[Source(source_type=SourceType.GIT, url="https://example.invalid/repo")],
        feeds=[],
        quality=OverlayQuality.CORE,
        status=OverlayStatus.UNOFFICIAL,
        installed=False,
        package_count=3,
    )


def _package_version(version_id: str) -> PackageVersion:
    return PackageVersion(
        id=version_id,
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


def _package() -> Package:
    return Package(
        category="app-editors",
        name="vim",
        description="d",
        homepage=None,
        licenses=[],
        versions=[_package_version("9.0.0")],
    )


def _news_item(index: int):
    from carnage.core.portage.news import News

    return News(index=index, name=f"item-{index}", date="2024-01-15", title="Title", read=False)


def _glsa(glsa_id: str):
    from carnage.core.portage.glsas import GLSA

    return GLSA(
        id=glsa_id,
        title="Title",
        synopsis="syn",
        product="product",
        announced=None,
        revised=None,
        revision_count="01",
        bugs=[],
        access=None,
        background=None,
        description="desc",
        impact="impact",
        impact_type="normal",
        workaround=None,
        resolutions=[],
        affected_packages=[],
        references=[],
    )


class _UseHarness(App[None]):
    def compose(self) -> ComposeResult:
        yield UseFlagsTab()


class _OverlaysHarness(App[None]):
    blocked = False

    def compose(self) -> ComposeResult:
        yield OverlaysTab()


class _NewsHarness(App[None]):
    blocked = False

    def compose(self) -> ComposeResult:
        yield NewsTab()


class _GlsaHarness(App[None]):
    blocked = False

    def compose(self) -> ComposeResult:
        yield GLSATab()


class _BrowseHarness(App[None]):
    blocked = False

    def compose(self) -> ComposeResult:
        yield BrowseTab()


def _row_event(table: DataTable, row: int) -> DataTable.RowSelected:
    key = table._row_locations.get_key(row)
    assert key is not None
    return DataTable.RowSelected(data_table=table, cursor_row=row, row_key=key)


async def test_details_start_hidden() -> None:
    for harness, tab_cls, detail_id in [
        (_UseHarness, UseFlagsTab, "useflags-content-scroll"),
        (_OverlaysHarness, OverlaysTab, "overlays-detail"),
        (_NewsHarness, NewsTab, "news-detail"),
        (_GlsaHarness, GLSATab, "glsa-detail"),
        (_BrowseHarness, BrowseTab, "browse-detail"),
    ]:
        async with harness().run_test() as pilot:
            await pilot.pause(0.2)
            tab = pilot.app.query_one(tab_cls)
            assert tab.query_one(f"#{detail_id}").display is False


async def test_use_selection_reveals_details(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(UseFlagsTab, "_load_useflag_details", lambda self, useflag: None)

    async with _UseHarness().run_test() as pilot:
        tab = pilot.app.query_one(UseFlagsTab)
        tab._populate_table([UseFlag(name="gui", description=None)])
        await pilot.pause(0.1)

        table = tab.query_one("#useflags-table", DataTable)
        assert tab.query_one("#useflags-content-scroll").display is False

        tab.on_data_table_row_selected(_row_event(table, 0))

        assert tab.query_one("#useflags-content-scroll").display is True


async def test_use_clear_hides_details_again(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(UseFlagsTab, "_load_useflag_details", lambda self, useflag: None)

    async with _UseHarness().run_test() as pilot:
        tab = pilot.app.query_one(UseFlagsTab)
        tab._populate_table([UseFlag(name="gui", description=None)])
        await pilot.pause(0.1)

        table = tab.query_one("#useflags-table", DataTable)
        tab.on_data_table_row_selected(_row_event(table, 0))
        assert tab.query_one("#useflags-content-scroll").display is True

        tab._clear_table()

        assert tab.query_one("#useflags-content-scroll").display is False


async def test_overlay_selection_reveals_details() -> None:
    async with _OverlaysHarness().run_test() as pilot:
        tab = pilot.app.query_one(OverlaysTab)
        tab.overlays = [_overlay("alpha")]
        tab.filtered_overlays = list(tab.overlays)
        tab._populate_table()
        await pilot.pause(0.1)

        table = tab.query_one("#overlays-table", DataTable)
        assert tab.query_one("#overlays-detail").display is False

        tab.on_data_table_row_selected(_row_event(table, 0))

        assert tab.query_one("#overlays-detail").display is True


async def test_news_selection_reveals_details() -> None:
    async with _NewsHarness().run_test() as pilot:
        tab = pilot.app.query_one(NewsTab)
        tab._populate_table([_news_item(1)])
        await pilot.pause(0.1)

        table = tab.query_one("#news-table", DataTable)
        assert tab.query_one("#news-detail").display is False

        tab.on_data_table_row_selected(_row_event(table, 0))

        assert tab.query_one("#news-detail").display is True


async def test_glsa_selection_reveals_details() -> None:
    async with _GlsaHarness().run_test() as pilot:
        tab = pilot.app.query_one(GLSATab)
        tab._populate_table([_glsa("GLSA-2024-0001")])
        await pilot.pause(0.1)

        table = tab.query_one("#glsa-table", DataTable)
        assert tab.query_one("#glsa-detail").display is False

        tab.on_data_table_row_selected(_row_event(table, 0))

        assert tab.query_one("#glsa-detail").display is True


async def test_browse_selection_reveals_details() -> None:
    async with _BrowseHarness().run_test() as pilot:
        tab = pilot.app.query_one(BrowseTab)
        tab._populate_table([_package()], frozenset())
        await pilot.pause(0.1)

        table = tab.query_one("#browse-table", DataTable)
        assert tab.query_one("#browse-detail").display is False

        tab.on_data_table_row_selected(_row_event(table, 0))
        await pilot.pause(2.0)

        assert tab.query_one("#browse-detail").display is True


async def test_browse_clear_hides_details_again() -> None:
    async with _BrowseHarness().run_test() as pilot:
        tab = pilot.app.query_one(BrowseTab)
        tab._populate_table([_package()], frozenset())
        await pilot.pause(0.1)

        table = tab.query_one("#browse-table", DataTable)
        tab.on_data_table_row_selected(_row_event(table, 0))
        await pilot.pause(2.0)
        assert tab.query_one("#browse-detail").display is True

        tab._clear_table()

        assert tab.query_one("#browse-detail").display is False
