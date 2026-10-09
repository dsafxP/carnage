"""Utilities for managing USE flags with euse."""

from collections.abc import Callable

from textual.app import App

from carnage.core.commands_config import is_valid_atom
from carnage.core.operation import start_operation


def _reject_unsafe_atom(app: App, package_atom: str) -> bool:
    """Refuse to build an euse command from an atom getopt could read as an option."""
    if is_valid_atom(package_atom):
        return False

    # Deliberately not echoing the value: it is untrusted and notify renders markup.
    app.notify("Refused to run euse with an invalid package atom.", severity="error")
    return True


def euse_enable(
    app: App, flags: list[str], package_atom: str, on_complete: Callable[[bool], None] | None = None
) -> None:
    """
    Enable a USE flag for a specific package.

    Args:
        app: The Textual App instance
        flags: USE flags to enable (e.g., ["test", "apidoc"])
        package_atom: Package atom (e.g., "sys-apps/portage")
        on_complete: Optional callback when operation finishes (receives success bool)
    """
    if _reject_unsafe_atom(app, package_atom):
        return

    start_operation(
        app,
        "euse.enable",
        args=[package_atom, " ".join(flags)],
        default_privilege=True,
        on_complete=on_complete,
    )


def euse_disable(
    app: App, flags: list[str], package_atom: str, on_complete: Callable[[bool], None] | None = None
) -> None:
    """
    Disable a USE flag for a specific package.

    Args:
        app: The Textual App instance
        flags: USE flags to disable (e.g., ["test", "apidoc"])
        package_atom: Package atom (e.g., "sys-apps/portage")
        on_complete: Optional callback when operation finishes (receives success bool)
    """
    if _reject_unsafe_atom(app, package_atom):
        return

    start_operation(
        app,
        "euse.disable",
        args=[package_atom, " ".join(flags)],
        default_privilege=True,
        on_complete=on_complete,
    )
