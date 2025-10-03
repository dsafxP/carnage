"""Basic interactions with eix for package management."""

import subprocess
from pathlib import Path
from subprocess import CompletedProcess


def eix_update() -> tuple[int, str, str]:
    """
    Update the eix cache.

    Wraps: eix-update

    Note: Does not require root privileges.

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    result: CompletedProcess[str] = subprocess.run(
        ["eix-update"],
        capture_output=True,
        text=True
    )

    return result.returncode, result.stdout, result.stderr


def eix_remote_update() -> tuple[int, str, str]:
    """
    Update the eix remote cache for packages not in local repositories.

    Wraps: eix-remote update

    Note: Requires root privileges if /var/cache/eix/remote.eix does not exist.
          If the cache file exists, runs without privilege escalation.

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    remote_cache = Path("/var/cache/eix/remote.eix")

    if remote_cache.exists():
        # Cache exists, no root needed
        result: CompletedProcess[str] = subprocess.run(
            ["eix-remote", "update"],
            capture_output=True,
            text=True
        )
        return result.returncode, result.stdout, result.stderr
    else:
        # Cache doesn't exist, needs root to create
        from ..privilege import run_privileged
        return run_privileged(["eix-remote", "update"])