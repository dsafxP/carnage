"""Utilities for managing packages with emerge."""

from collections.abc import Callable

from textual.app import App

from carnage.core.operation import Operation


def emerge_install(app: App, package_atom: str, on_complete: Callable[[bool], None] | None = None) -> None:
    """
    Install a package using emerge.

    Wraps: emerge <package_atom>

    Args:
        app: The Textual App instance
        package_atom: Package atom to install (e.g., "app-editors/vim")
        on_complete: Optional callback when operation finishes (receives success bool)
    """
    op = Operation(
        ["emerge", "-v", "--nospinner", package_atom],
        privilege=True,
        log_callback=app.screen.log_operation_output,  # type: ignore
    )
    op.start_in_app(app, on_complete=on_complete)


def emerge_uninstall(app: App, package_atom: str, on_complete: Callable[[bool], None] | None = None) -> None:
    """
    Uninstall a package using emerge.

    Wraps: emerge --depclean <package_atom>

    Args:
        app: The Textual App instance
        package_atom: Package atom to uninstall (e.g., "app-editors/vim")
        on_complete: Optional callback when operation finishes (receives success bool)
    """
    # Set CLEAN_DELAY=0 to skip the 5-second delay before depclean
    env = {"CLEAN_DELAY": "0"}

    op = Operation(
        ["emerge", "-v", "--nospinner", "--depclean", package_atom],
        privilege=True,
        env=env,
        log_callback=app.screen.log_operation_output,  # type: ignore
    )
    op.start_in_app(app, on_complete=on_complete)


def emerge_deselect(app: App, package_atom: str, on_complete: Callable[[bool], None] | None = None) -> None:
    """
    Remove package from world file using emerge.

    Wraps: emerge --deselect <package_atom>

    Args:
        app: The Textual App instance
        package_atom: Package atom to remove from world file (e.g., "app-editors/vim")
        on_complete: Optional callback when operation finishes (receives success bool)
    """
    op = Operation(
        ["emerge", "--deselect", package_atom],
        privilege=True,
        log_callback=app.screen.log_operation_output,  # type: ignore
    )
    op.start_in_app(app, on_complete=on_complete)


def emerge_noreplace(app: App, package_atom: str, on_complete: Callable[[bool], None] | None = None) -> None:
    """
    Add package to world file using emerge.

    Wraps: emerge --noreplace <package_atom>

    Args:
        app: The Textual App instance
        package_atom: Package atom to add to world file (e.g., "app-editors/vim")
        on_complete: Optional callback when operation finishes (receives success bool)
    """
    op = Operation(
        ["emerge", "--noreplace", package_atom],
        privilege=True,
        log_callback=app.screen.log_operation_output,  # type: ignore
    )
    op.start_in_app(app, on_complete=on_complete)
