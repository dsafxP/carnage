"""Tests for marking news items as read."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

import carnage.core.portage.news as news_module
from carnage.core.commands_config import CommandsConfiguration

_started: list[list[str]] = []


@pytest.fixture(autouse=True)
def record_operations(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Capture the command each mark-as-read would run, argv and all."""
    config = CommandsConfiguration(config_path=tmp_path / "commands.toml")

    def record(app, command_id, *, args=None, default_privilege=False, on_complete=None) -> None:
        command = config.get_command(command_id, args=args, default_privilege=default_privilege)
        _started.append(list(command.cmd))

    _started.clear()
    monkeypatch.setattr(news_module, "start_operation", record)
    monkeypatch.setattr(news_module, "current_user_in_group", lambda _group: True)


def test_mark_read_identifies_the_item_by_name() -> None:
    news_module.mark_news_read(Mock(), "2024-01-15-gcc-removal")

    # eselect numbers its whole tracking set, so a number could mark a
    # different item than the one the filtered tab is showing.
    assert _started == [["eselect", "news", "read", "--quiet", "2024-01-15-gcc-removal"]]


def test_mark_all_read_keeps_its_special_operand() -> None:
    news_module.mark_all_news_read(Mock())

    assert _started == [["eselect", "news", "read", "--quiet", "all"]]


def test_mark_read_refuses_an_unsafe_name() -> None:
    app = Mock()

    news_module.mark_news_read(app, "-evil")

    app.notify.assert_called_once_with("Refused to mark a news item with an invalid name.", severity="error")
    assert _started == []
