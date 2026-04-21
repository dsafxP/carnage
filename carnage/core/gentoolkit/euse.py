"""Utilities for managing USE flags with euse."""

from collections.abc import Callable

from textual.app import App

from carnage.core.operation import Operation


def euse_enable(
    app: App, flags: list[str], package_atom: str | None = None, on_complete: Callable[[bool], None] | None = None
) -> None:
    """
    Enable a USE flag globally or for a specific package.

    Wraps: euse [-p <package_atom>] -E <flag>

    Args:
        app: The Textual App instance
        flags: USE flags to enable (e.g., ["test", "apidoc"])
        package_atom: If given, apply only to this package (e.g., "sys-apps/portage")
        on_complete: Optional callback when operation finishes (receives success bool)
    """
    cmd: list[str] = ["euse"]

    if package_atom:
        cmd += ["-p", package_atom]

    cmd += ["-E"] + flags

    op = Operation(
        cmd,
        privilege=True,
        log_callback=app.screen.log_operation_output,  # type: ignore
    )
    op.start_in_app(app, on_complete=on_complete)


def euse_disable(
    app: App, flags: list[str], package_atom: str | None = None, on_complete: Callable[[bool], None] | None = None
) -> None:
    """
    Disable a USE flag globally or for a specific package.

    Wraps: euse [-p <package_atom>] -D <flag>

    Args:
        app: The Textual App instance
        flags: USE flags to disable (e.g., ["test", "apidoc"])
        package_atom: If given, apply only to this package (e.g., "sys-apps/portage")
        on_complete: Optional callback when operation finishes (receives success bool)
    """
    cmd: list[str] = ["euse"]

    if package_atom:
        cmd += ["-p", package_atom]

    cmd += ["-D"] + flags

    op = Operation(
        cmd,
        privilege=True,
        log_callback=app.screen.log_operation_output,  # type: ignore
    )
    op.start_in_app(app, on_complete=on_complete)


def euse_remove(
    app: App, flags: list[str], package_atom: str | None = None, on_complete: Callable[[bool], None] | None = None
) -> None:
    """
    Remove all references to a USE flag, reverting to default.

    Wraps: euse [-p <package_atom>] -R <flag>

    Args:
        app: The Textual App instance
        flags: USE flags to remove (e.g., ["test", "apidoc"])
        package_atom: If given, apply only to this package (e.g., "sys-apps/portage")
        on_complete: Optional callback when operation finishes (receives success bool)
    """
    cmd: list[str] = ["euse"]

    if package_atom:
        cmd += ["-p", package_atom]

    cmd += ["-R"] + flags

    op = Operation(
        cmd,
        privilege=True,
        log_callback=app.screen.log_operation_output,  # type: ignore
    )
    op.start_in_app(app, on_complete=on_complete)
