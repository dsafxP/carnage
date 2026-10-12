"""Tests for the shared table-tab base class."""

from __future__ import annotations

import inspect
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.widgets import DataTable, LoadingIndicator

from carnage.tui.widgets.browse.browse_tab import BrowseTab
from carnage.tui.widgets.glsa_tab import GLSATab
from carnage.tui.widgets.news_tab import NewsTab
from carnage.tui.widgets.overlay_tab import OverlaysTab
from carnage.tui.widgets.table_tab import TableTab
from carnage.tui.widgets.use_tab import UseFlagsTab

_TABS = (UseFlagsTab, BrowseTab, NewsTab, GLSATab, OverlaysTab)


class _Bare(TableTab):
    """Minimal subclass used to exercise the base class itself."""

    TABLE_ID = "bare-table"
    LOADING_ID = "bare-loading"
    _SORT_KEYS: ClassVar[dict] = {"Name": lambda item: item}

    def compose(self) -> ComposeResult:
        yield LoadingIndicator(id="bare-loading")
        yield DataTable(id="bare-table")


class _Harness(App[None]):
    def compose(self) -> ComposeResult:
        yield _Bare()


async def test_show_loading_reveals_the_indicator_and_hides_the_table() -> None:
    app = _Harness()

    async with app.run_test():
        tab = app.query_one(_Bare)

        tab._show_loading()

        assert tab.loading_widget.display is True
        assert tab.table.display is False


async def test_hide_loading_puts_the_table_back() -> None:
    app = _Harness()

    async with app.run_test():
        tab = app.query_one(_Bare)

        tab._show_loading()
        tab._hide_loading()

        assert tab.loading_widget.display is False
        assert tab.table.display is True


def test_every_tab_declares_ids_its_compose_actually_defines() -> None:
    for widget_cls in _TABS:
        source = inspect.getsource(widget_cls.compose)

        assert f'id="{widget_cls.TABLE_ID}"' in source, widget_cls.__name__
        assert f'id="{widget_cls.LOADING_ID}"' in source, widget_cls.__name__


def test_subclasses_inherit_the_loading_helpers() -> None:
    for widget_cls in _TABS:
        assert widget_cls._show_loading is TableTab._show_loading, widget_cls.__name__
        assert widget_cls._hide_loading is TableTab._hide_loading, widget_cls.__name__


async def test_cycle_sort_toggles_and_rejects_unknown() -> None:
    app = _Harness()

    async with app.run_test():
        tab = app.query_one(_Bare)

        assert tab._cycle_sort("Unknown") is False
        assert tab._sort_column is None

        assert tab._cycle_sort("Name") is True
        assert (tab._sort_column, tab._sort_reverse) == ("Name", False)

        assert tab._cycle_sort("Name") is True
        assert (tab._sort_column, tab._sort_reverse) == ("Name", True)


async def test_capture_header_labels_remembers_plain_labels() -> None:
    app = _Harness()

    async with app.run_test():
        tab = app.query_one(_Bare)
        tab.table.add_columns("Name", "Description")
        tab._capture_header_labels()

        assert tab._header_labels == ["Name", "Description"]
