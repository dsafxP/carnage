"""Tests for command overrides (``carnage.core.commands_config``)."""

from __future__ import annotations

from pathlib import Path

import pytest

import carnage.core.operation as operation_module
from carnage.core.commands_config import CommandsConfiguration


@pytest.fixture(autouse=True)
def detected_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make privilege backend detection deterministic."""
    monkeypatch.setattr(operation_module, "generate_default_privilege_backend", lambda: "run0")


def test_fresh_install_generates_and_reads_back_overrides(commands_file: Path) -> None:
    """The generated file used to be ignored, so detection ran again next start."""
    config = CommandsConfiguration(config_path=commands_file)

    assert commands_file.exists()
    assert config.load_error is None
    assert config._config
    assert config.privilege_backend == ["run0"]


def test_missing_privilege_backend_key_falls_back_to_detection(commands_file: Path) -> None:
    commands_file.parent.mkdir(parents=True, exist_ok=True)
    commands_file.write_text("# no privilege_backend key here\n", encoding="utf-8")

    config = CommandsConfiguration(config_path=commands_file)

    assert config.privilege_backend == ["run0"]


def test_empty_privilege_backend_is_respected(commands_file: Path) -> None:
    """An explicit empty list still means "no escalation tool configured"."""
    commands_file.parent.mkdir(parents=True, exist_ok=True)
    commands_file.write_text("privilege_backend = []\n", encoding="utf-8")

    config = CommandsConfiguration(config_path=commands_file)

    assert config.privilege_backend == []


def test_malformed_overrides_file_reports_the_failure(commands_file: Path) -> None:
    commands_file.parent.mkdir(parents=True, exist_ok=True)
    commands_file.write_text("privilege_backend = [unterminated\n", encoding="utf-8")

    config = CommandsConfiguration(config_path=commands_file)

    assert config.load_error is not None
    assert commands_file.name in config.load_error
    assert config._config == {}


def test_overrides_are_used_when_building_a_command(commands_file: Path) -> None:
    commands_file.parent.mkdir(parents=True, exist_ok=True)
    commands_file.write_text(
        '[eix.search]\ncommand = ["-Qf", "3"]\n',
        encoding="utf-8",
    )

    config = CommandsConfiguration(config_path=commands_file)
    command = config.get_command("eix.search")

    assert command.is_overridden
    assert command.raw_cmd == ["-Qf", "3"]


def test_missing_command_falls_back_to_internal_default(commands_file: Path) -> None:
    config = CommandsConfiguration(config_path=commands_file)
    command = config.get_command("eix.search")

    assert not command.is_overridden
    assert command.raw_cmd
