"""Tests for the log pane's scoped clear binding."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Input

from carnage.tui.widgets.operation_log import OperationLog


class _Harness(App[None]):
    def compose(self) -> ComposeResult:
        yield Input(id="search-input")
        yield OperationLog(id="operation-log")


async def test_delete_clears_the_focused_log() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        log = app.query_one("#operation-log", OperationLog)
        log.write("first")
        log.write("second")
        assert len(log.lines) == 2

        log.focus()
        await pilot.pause(0.1)
        await pilot.press("delete")
        await pilot.pause(0.1)

        assert len(log.lines) == 0


async def test_delete_elsewhere_leaves_the_log_alone() -> None:
    """The binding is widget-scoped, not screen-wide."""
    app = _Harness()
    async with app.run_test() as pilot:
        log = app.query_one("#operation-log", OperationLog)
        log.write("first")
        assert len(log.lines) == 1

        app.query_one("#search-input", Input).focus()
        await pilot.pause(0.1)
        await pilot.press("delete")
        await pilot.pause(0.1)

        assert len(log.lines) == 1
