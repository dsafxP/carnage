"""Tests for marking news items as read."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

import carnage.core.portage.news as news_module
from carnage.core.commands_config import CommandsConfiguration


class _RecordingOperation:
    """Stands in for Operation and captures the command it would run."""

    created: list[list[str]] = []

    def __init__(self, cmd: list[str], *, env=None, log_callback=None) -> None:
        self.cmd = cmd
        type(self).created.append(list(cmd))

    def start_in_app(self, app, *, on_complete=None) -> None:
        return None


@pytest.fixture(autouse=True)
def record_operations(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _RecordingOperation.created = []
    monkeypatch.setattr(news_module, "Operation", _RecordingOperation)
    monkeypatch.setattr(
        news_module, "get_commands_config", lambda: CommandsConfiguration(config_path=tmp_path / "commands.toml")
    )
    monkeypatch.setattr(news_module, "current_user_in_group", lambda _group: True)


def test_mark_read_identifies_the_item_by_name() -> None:
    news_module.mark_news_read(Mock(), "2024-01-15-gcc-removal")

    # eselect numbers its whole tracking set, so a number could mark a
    # different item than the one the filtered tab is showing.
    assert _RecordingOperation.created == [["eselect", "news", "read", "--quiet", "2024-01-15-gcc-removal"]]


def test_mark_read_refuses_an_unsafe_name() -> None:
    app = Mock()

    news_module.mark_news_read(app, "-evil")

    app.notify.assert_called_once_with("Refused to mark a news item with an invalid name.", severity="error")
    assert _RecordingOperation.created == []
