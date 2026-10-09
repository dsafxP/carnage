"""Utilities for managing packages with emerge."""

from collections.abc import Callable

from textual.app import App

from carnage.core.commands_config import get_commands_config, is_valid_atom
from carnage.core.operation import Operation
from carnage.core.process import tracked_run


def _reject_unsafe_atom(app: App, package_atom: str) -> bool:
    """Refuse to build an emerge command from an atom getopt could read as an option."""
    if is_valid_atom(package_atom):
        return False

    # Deliberately not echoing the value: it is untrusted and notify renders markup.
    app.notify("Refused to run emerge with an invalid package atom.", severity="error")
    return True


def emerge_install(app: App, package_atom: str, on_complete: Callable[[bool], None] | None = None) -> None:
    """
    Install a package using emerge.

    Args:
        app: The Textual App instance
        package_atom: Package atom to install (e.g., "app-editors/vim")
        on_complete: Optional callback when operation finishes (receives success bool)
    """
    if _reject_unsafe_atom(app, package_atom):
        return

    cmd_config = get_commands_config()

    try:
        qlop_command = cmd_config.get_command("qlop.prediction", args=[package_atom])
        result = tracked_run(qlop_command.full_cmd, env=qlop_command.env, timeout=5)

        if result.stdout.strip():
            log = app.screen.log_operation_output  # type: ignore
            log(result.stdout)
            log(b"\n")
    except Exception:
        pass

    command = cmd_config.get_command("emerge.install", args=[package_atom], default_privilege=True)

    op = Operation(
        command.full_cmd,
        env=command.env,
        log_callback=app.screen.log_operation_output,  # type: ignore
    )
    op.start_in_app(app, on_complete=on_complete)


def emerge_uninstall(app: App, package_atom: str, on_complete: Callable[[bool], None] | None = None) -> None:
    """
    Uninstall a package using emerge.

    Args:
        app: The Textual App instance
        package_atom: Package atom to uninstall (e.g., "app-editors/vim")
        on_complete: Optional callback when operation finishes (receives success bool)
    """
    if _reject_unsafe_atom(app, package_atom):
        return

    cmd_config = get_commands_config()
    command = cmd_config.get_command("emerge.uninstall", args=[package_atom], default_privilege=True)

    op = Operation(
        command.full_cmd,
        env=command.env,
        log_callback=app.screen.log_operation_output,  # type: ignore
    )
    op.start_in_app(app, on_complete=on_complete)


def emerge_deselect(app: App, package_atom: str, on_complete: Callable[[bool], None] | None = None) -> None:
    """
    Remove package from world file using emerge.

    Args:
        app: The Textual App instance
        package_atom: Package atom to remove from world file (e.g., "app-editors/vim")
        on_complete: Optional callback when operation finishes (receives success bool)
    """
    if _reject_unsafe_atom(app, package_atom):
        return

    cmd_config = get_commands_config()
    command = cmd_config.get_command("emerge.deselect", args=[package_atom], default_privilege=True)

    op = Operation(
        command.full_cmd,
        env=command.env,
        log_callback=app.screen.log_operation_output,  # type: ignore
    )
    op.start_in_app(app, on_complete=on_complete)


def emerge_noreplace(app: App, package_atom: str, on_complete: Callable[[bool], None] | None = None) -> None:
    """
    Add package to world file using emerge.

    Args:
        app: The Textual App instance
        package_atom: Package atom to add to world file (e.g., "app-editors/vim")
        on_complete: Optional callback when operation finishes (receives success bool)
    """
    if _reject_unsafe_atom(app, package_atom):
        return

    cmd_config = get_commands_config()
    command = cmd_config.get_command("emerge.noreplace", args=[package_atom], default_privilege=True)

    op = Operation(
        command.full_cmd,
        env=command.env,
        log_callback=app.screen.log_operation_output,  # type: ignore
    )
    op.start_in_app(app, on_complete=on_complete)
