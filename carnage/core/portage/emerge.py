"""Utilities for managing packages with emerge."""

import os
import subprocess
from collections.abc import Callable

from textual.app import App

from carnage.core.commands_config import get_commands_config, is_valid_atom
from carnage.core.operation import start_operation
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
    log = app.screen.log_operation_output  # type: ignore

    def _predict() -> None:
        """Write the merge-time prediction to the log. Purely informational."""
        try:
            qlop_command = cmd_config.get_command("qlop.prediction", args=[package_atom])
            result = tracked_run(
                qlop_command.full_cmd,
                env={**os.environ, **qlop_command.env},
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            # qlop is optional: missing, broken or hanging must not stop us.
            return

        if result.stdout.strip():
            app.call_from_thread(log, result.stdout)
            app.call_from_thread(log, b"\n")

    # Keep it off the event loop: a slow qlop would otherwise freeze the UI for
    # up to the 5s timeout before emerge gets a chance to start.
    app.run_worker(
        _predict,
        thread=True,
        group="qlop-prediction",
        exclusive=True,
        exit_on_error=False,
    )

    start_operation(app, "emerge.install", args=[package_atom], default_privilege=True, on_complete=on_complete)


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

    start_operation(app, "emerge.uninstall", args=[package_atom], default_privilege=True, on_complete=on_complete)


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

    start_operation(app, "emerge.deselect", args=[package_atom], default_privilege=True, on_complete=on_complete)


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

    start_operation(app, "emerge.noreplace", args=[package_atom], default_privilege=True, on_complete=on_complete)
