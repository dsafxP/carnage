"""Shared fixtures for the carnage test suite."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

import carnage.core.commands_config as commands_config_module
import carnage.core.config as config_module
import carnage.core.process as process_module
from carnage.core.args import parse_args, reset_args


def _reset_state() -> None:
    """Drop every module-level global that would otherwise leak across tests."""
    # Install an inert command line first, so lazily-read arguments never fall
    # back to pytest's own sys.argv, which argparse would reject as unknown.
    reset_args()
    parse_args([])

    config_module._config_instance = None
    commands_config_module._commands_instance = None
    process_module.TrackedProcess._running_processes.clear()


@pytest.fixture(autouse=True)
def isolated_state() -> Iterator[None]:
    """Give every test a clean set of module-level singletons."""
    _reset_state()
    yield
    _reset_state()


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    """Path to a ``carnage.toml`` inside a throwaway directory."""
    return tmp_path / "carnage.toml"


@pytest.fixture
def commands_file(tmp_path: Path) -> Path:
    """Path to a ``commands.toml`` inside a throwaway directory."""
    return tmp_path / "commands.toml"
