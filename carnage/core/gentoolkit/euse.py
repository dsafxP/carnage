"""Utilities for managing USE flags with euse."""

from collections.abc import Callable

from textual.app import App

from carnage.core.commands_config import get_commands_config
from carnage.core.operation import Operation


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
    cmd_config = get_commands_config()
    command = cmd_config.get_command("euse.enable", args=[package_atom, " ".join(flags)], default_privilege=True)

    op = Operation(
        command.full_cmd,
        env=command.env,
        log_callback=app.screen.log_operation_output,  # type: ignore
    )
    op.start_in_app(app, on_complete=on_complete)


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
    cmd_config = get_commands_config()
    command = cmd_config.get_command("euse.disable", args=[package_atom, " ".join(flags)], default_privilege=True)

    op = Operation(
        command.full_cmd,
        env=command.env,
        log_callback=app.screen.log_operation_output,  # type: ignore
    )
    op.start_in_app(app, on_complete=on_complete)
