"""Tests for the operation log fast path."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import carnage.tui.screens.main_screen as main_screen_module


def test_log_output_reuses_the_resolved_pane(monkeypatch) -> None:
    """One DOM lookup total, no matter how many lines stream through."""
    monkeypatch.setattr(main_screen_module, "get_config", lambda: SimpleNamespace(automatic_pane=False))

    screen = main_screen_module.MainScreen()
    pane = Mock()
    queries: list[str] = []

    def fake_query_one(selector: str, _type: object = None) -> Mock:
        queries.append(selector)
        return pane

    monkeypatch.setattr(screen, "query_one", fake_query_one)

    screen.log_operation_output(b"first\n")
    screen.log_operation_output(b"second\n")

    assert queries == ["#operation-log"]
    assert pane.write.call_count == 2
    assert screen._log_pane is pane


def test_log_output_auto_shows_the_pane(monkeypatch) -> None:
    monkeypatch.setattr(main_screen_module, "get_config", lambda: SimpleNamespace(automatic_pane=True))

    screen = main_screen_module.MainScreen()
    pane = Mock()
    pane.display = False
    monkeypatch.setattr(screen, "query_one", lambda selector, _type=None: pane)

    screen.log_operation_output(b"hi\n")

    assert pane.display
    pane.write.assert_called_once()
