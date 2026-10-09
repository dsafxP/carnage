"""Tests for the environment handed to commands (W1)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from carnage.core.commands_config import CommandsConfiguration
from carnage.core.operation import Operation

RUN0_OVERRIDES = """
privilege_backend = ["run0"]

[emerge.uninstall]
command = ["emerge", "-vc", "--nospinner", "--", "$1"]
privilege = true
environment = { CLEAN_DELAY = "0" }
"""

PKEXEC_OVERRIDES = RUN0_OVERRIDES.replace('["run0"]', '["pkexec"]')


@pytest.mark.skipif(os.geteuid() == 0, reason="privilege escalation is skipped when already root")
def test_run0_receives_configured_environment_as_setenv(commands_file: Path) -> None:
    """run0 builds its environment from the service manager, not from env=."""
    commands_file.parent.mkdir(parents=True, exist_ok=True)
    commands_file.write_text(RUN0_OVERRIDES, encoding="utf-8")

    command = CommandsConfiguration(config_path=commands_file).get_command(
        "emerge.uninstall", args=["app-editors/vim"], default_privilege=True
    )

    assert command.full_cmd[:3] == ["run0", "--setenv=CLEAN_DELAY=0", "emerge"]
    assert command.full_cmd[-1] == "app-editors/vim"


@pytest.mark.skipif(os.geteuid() == 0, reason="privilege escalation is skipped when already root")
def test_other_backends_are_not_given_setenv(commands_file: Path) -> None:
    commands_file.parent.mkdir(parents=True, exist_ok=True)
    commands_file.write_text(PKEXEC_OVERRIDES, encoding="utf-8")

    command = CommandsConfiguration(config_path=commands_file).get_command(
        "emerge.uninstall", args=["app-editors/vim"], default_privilege=True
    )

    assert command.full_cmd[:2] == ["pkexec", "emerge"]
    assert not any(arg.startswith("--setenv=") for arg in command.full_cmd)


async def test_inherited_code_loading_variables_are_stripped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LD_PRELOAD", "/tmp/evil.so")
    monkeypatch.setenv("PYTHONPATH", "/tmp/evil-pkg")

    received: list[bytes] = []
    op = Operation(
        ["sh", "-c", 'printf %s "${LD_PRELOAD-unset}:${PYTHONPATH-unset}"'],
        log_callback=received.append,
    )

    assert await op.run() == 0
    assert b"unset:unset" in b"".join(received)


async def test_explicit_command_environment_is_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYTHONPATH", "/tmp/inherited")

    received: list[bytes] = []
    op = Operation(
        ["sh", "-c", 'printf %s "$PYTHONPATH"'],
        env={"PYTHONPATH": "/explicit"},
        log_callback=received.append,
    )

    assert await op.run() == 0
    assert b"/explicit" in b"".join(received)
