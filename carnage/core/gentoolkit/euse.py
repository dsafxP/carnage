"""Utilities for managing USE flags with euse."""

from carnage.core.privilege import run_privileged


def euse_enable(flag: str, package_atom: str | None = None) -> tuple[int, str, str]:
    """
    Enable a USE flag globally or for a specific package.

    Wraps: euse [-p <package_atom>] -E <flag>

    Args:
        flag: USE flag to enable (e.g., "debug")
        package_atom: If given, apply only to this package (e.g., "net-misc/ucarp")

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    cmd: list[str] = ["euse"]

    if package_atom:
        cmd += ["-p", package_atom]

    cmd += ["-E", flag]
    return run_privileged(cmd, use_terminal=False)


def euse_disable(flag: str, package_atom: str | None = None) -> tuple[int, str, str]:
    """
    Disable a USE flag globally or for a specific package.

    Wraps: euse [-p <package_atom>] -D <flag>

    Args:
        flag: USE flag to disable (e.g., "debug")
        package_atom: If given, apply only to this package (e.g., "net-misc/ucarp")

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    cmd: list[str] = ["euse"]

    if package_atom:
        cmd += ["-p", package_atom]

    cmd += ["-D", flag]
    return run_privileged(cmd, use_terminal=False)


def euse_remove(flag: str, package_atom: str | None = None) -> tuple[int, str, str]:
    """
    Remove all references to a USE flag, reverting to default.

    Wraps: euse [-p <package_atom>] -R <flag>

    Args:
        flag: USE flag to remove (e.g., "debug")
        package_atom: If given, apply only to this package (e.g., "net-misc/ucarp")

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    cmd: list[str] = ["euse"]

    if package_atom:
        cmd += ["-p", package_atom]

    cmd += ["-R", flag]
    return run_privileged(cmd, use_terminal=False)