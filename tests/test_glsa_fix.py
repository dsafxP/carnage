"""Tests for how GLSA fixes are passed to glsa-check."""

from __future__ import annotations

from pathlib import Path

import pytest

from carnage.core.commands_config import CommandsConfiguration


@pytest.fixture
def config(commands_file: Path) -> CommandsConfiguration:
    return CommandsConfiguration(config_path=commands_file)


def test_several_glsa_ids_become_several_operands(config: CommandsConfiguration) -> None:
    command = config.get_command("glsa.fix", args=["GLSA-2024-0001", "GLSA-2024-0002"], default_privilege=True)

    assert command.cmd == ["glsa-check", "-vf", "--", "GLSA-2024-0001", "GLSA-2024-0002"]


def test_a_single_glsa_id_still_works(config: CommandsConfiguration) -> None:
    command = config.get_command("glsa.fix", args=["GLSA-2024-0001"], default_privilege=True)

    assert command.cmd == ["glsa-check", "-vf", "--", "GLSA-2024-0001"]


def test_ids_are_never_joined_into_one_token(config: CommandsConfiguration) -> None:
    command = config.get_command("glsa.fix", args=["GLSA-1", "GLSA-2", "GLSA-3"], default_privilege=True)

    assert not any(" " in arg for arg in command.cmd)
