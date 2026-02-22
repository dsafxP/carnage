"""Utilities for managing USE flags with euse."""

from carnage.core.privilege import run_privileged


def euse_enable(flags: list[str], package_atom: str | None = None) -> tuple[int, str, str]:
    """
    Enable a USE flag globally or for a specific package.

    Wraps: euse [-p <package_atom>] -E <flag>

    Args:
        flags: USE flags to enable (e.g., ["test", "apidoc"])
        package_atom: If given, apply only to this package (e.g., "sys-apps/portage")

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    cmd: list[str] = ["euse"]

    if package_atom:
        cmd += ["-p", package_atom]

    cmd += ["-E"] + flags
    return run_privileged(cmd, use_terminal=False)


def euse_disable(flags: list[str], package_atom: str | None = None) -> tuple[int, str, str]:
    """
    Disable a USE flag globally or for a specific package.

    Wraps: euse [-p <package_atom>] -D <flag>

    Args:
        flags: USE flags to disable (e.g., ["test", "apidoc"])
        package_atom: If given, apply only to this package (e.g., "sys-apps/portage")

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    cmd: list[str] = ["euse"]

    if package_atom:
        cmd += ["-p", package_atom]

    cmd += ["-D"] + flags
    return run_privileged(cmd, use_terminal=False)


def euse_remove(flags: list[str], package_atom: str | None = None) -> tuple[int, str, str]:
    """
    Remove all references to a USE flag, reverting to default.

    Wraps: euse [-p <package_atom>] -R <flag>

    Args:
        flags: USE flags to remove (e.g., ["test", "apidoc"])
        package_atom: If given, apply only to this package (e.g., "sys-apps/portage")

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    cmd: list[str] = ["euse"]

    if package_atom:
        cmd += ["-p", package_atom]

    cmd += ["-R"] + flags
    return run_privileged(cmd, use_terminal=False)