"""Utilities for managing packages with emerge."""

from .privilege import run_privileged


def emerge_install(package_atom: str) -> tuple[int, str, str]:
    """
    Install a package using emerge.

    Wraps: emerge -q --color=n <package_atom>

    Args:
        package_atom: Package atom to install (e.g., "app-editors/vim")

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    return run_privileged(["emerge", "-q", "--nospinner", "--color=n", package_atom])


def emerge_uninstall(package_atom: str) -> tuple[int, str, str]:
    """
    Uninstall a package using emerge.

    Wraps: emerge -q --color=n --depclean <package_atom>

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


def emerge_update_world() -> tuple[int, str, str]:
    """
    Update @world (system upgrade).

    Wraps: emerge -q --color=n --update --deep --newuse @world

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    return run_privileged([
        "emerge", "-q", "--color=n", "--nospinner",
        "--update", "--deep", "--newuse", "@world"
    ])