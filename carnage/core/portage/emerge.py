"""Utilities for managing packages with emerge."""

from carnage.core.privilege import run_privileged


def emerge_install(package_atom: str) -> tuple[int, str, str]:
    """
    Install a package using emerge.

    Wraps: emerge -q --nospinner --color=n <package_atom>

    Args:
        package_atom: Package atom to install (e.g., "app-editors/vim")

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    return run_privileged(["emerge", "-q", "--nospinner", "--color=n", package_atom])


def emerge_uninstall(package_atom: str) -> tuple[int, str, str]:
    """
    Uninstall a package using emerge.

    Wraps: emerge -q --color=n --nospinner --depclean <package_atom>

    Args:
        package_atom: Package atom to uninstall (e.g., "app-editors/vim")

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    return run_privileged(["emerge",  "-q", "--nospinner","--color=n", "--depclean", package_atom])


def emerge_sync() -> tuple[int, str, str]:
    """
    Sync portage tree using emerge.

    Wraps: emerge --sync --quiet

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    return run_privileged(["emerge", "--sync", "--quiet"])


def emerge_deselect(package_atom: str) -> tuple[int, str, str]:
    """
    Remove package from world file using emerge.

    Wraps: emerge -W <package_atom>

    Args:
        package_atom: Package atom to remove from world file (e.g., "app-editors/vim")

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    return run_privileged(["emerge", "-W", package_atom])


def emerge_noreplace(package_atom: str) -> tuple[int, str, str]:
    """
    Add package to world file using emerge.

    Wraps: emerge -n <package_atom>

    Args:
        package_atom: Package atom to add to world file (e.g., "app-editors/vim")

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    return run_privileged(["emerge", "-n", package_atom])