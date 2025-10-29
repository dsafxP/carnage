"""Interactions with eix for overlay-specific operations."""

import os
import subprocess
from subprocess import CompletedProcess

from . import has_remote_cache


def get_package_count(overlay: str) -> int:
    """
    Get the number of packages in a specific overlay.

    Args:
        overlay: The overlay name to count packages from

    Returns:
        Number of packages in the overlay, or -1 if error occurs
    """
    # Set environment to disable limits
    env: dict[str, str] = os.environ.copy()
    env["EIX_LIMIT"] = "0"

    # Build command based on remote cache availability
    if has_remote_cache():
        cmd: list[str] = ["eix", "-RQ*", "--format", "1", "--only-in-overlay", overlay]
    else:
        cmd = ["eix", "-Q*", "--format", "1", "--only-in-overlay", overlay]

    try:
        result: CompletedProcess[bytes] = subprocess.run(
            cmd,
            capture_output=True,
            env=env
        )

        if result.returncode == 0:
            return len(result.stdout)
        else:
            return 0
    except (subprocess.SubprocessError, OSError):
        return -2
