"""Utilities for cleaning the package and distfile cache with eclean."""

from carnage.core.privilege import run_privileged


def eclean_dist() -> tuple[int, str, str]:
    """
    Clean obsolete distfiles using eclean-dist.

    Wraps: eclean-dist

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    return run_privileged(["eclean-dist"])


def eclean_pkg() -> tuple[int, str, str]:
    """
    Clean obsolete binary packages using eclean-pkg.

    Wraps: eclean-pkg

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    return run_privileged(["eclean-pkg"])