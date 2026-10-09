"""Tests for lazy command line parsing (``carnage.core.args``)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from carnage.core.args import get_config_path, get_css_path, parse_args, reset_args


def test_empty_argv_yields_defaults() -> None:
    reset_args()
    parse_args([])

    assert get_config_path() is None
    assert get_css_path().name == "custom.tcss"


def test_config_and_css_paths_come_from_argv() -> None:
    reset_args()
    parse_args(["--config", "/tmp/custom.toml", "--css", "/tmp/custom.tcss"])

    assert get_config_path() == Path("/tmp/custom.toml")
    assert get_css_path() == Path("/tmp/custom.tcss")


def test_unknown_flag_exits_with_error() -> None:
    reset_args()

    with pytest.raises(SystemExit) as exc_info:
        parse_args(["--nope"])

    assert exc_info.value.code == 2


def test_parsing_happens_only_once() -> None:
    reset_args()
    parse_args(["--config", "/tmp/first.toml"])
    parse_args(["--config", "/tmp/second.toml"])

    assert get_config_path() == Path("/tmp/first.toml")


def test_import_does_not_read_sys_argv() -> None:
    """Importing the package must not run argparse over the interpreter's argv."""
    result = subprocess.run(
        [sys.executable, "-c", "import carnage.core.args", "--definitely-not-a-flag"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
