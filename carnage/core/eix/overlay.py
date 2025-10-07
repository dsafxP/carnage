"""Interactions with eix for overlay-specific operations."""

import os
import subprocess
from subprocess import CompletedProcess


def get_package_count(overlay: str) -> int:
    """
    Get the number of packages in a specific overlay.

    Tries: eix -RQ -# --in-overlay <overlay>
    Fallback: eix -Q -# --in-overlay <overlay>

    Args:
        overlay: The overlay name to count packages from

    Returns:
        Number of packages in the overlay, or 0 if error occurs
    """
    # Set environment to disable limits
    env: dict[str, str] = os.environ.copy()
    env["EIX_LIMIT"] = "0"

    # Try with remote cache first (eix -RQ)
    try:
        result: CompletedProcess[str] = subprocess.run(
            ["eix", "-RQ", "-#", "--in-overlay", overlay],
            capture_output=True,
            text=True,
            env=env
        )

        if result.returncode == 0:
            # Each line represents one package
            count = result.stdout.count('\n')
            if count > 0:
                return count
    except (subprocess.SubprocessError, OSError):
        pass

    # Fallback to local cache only (eix -Q)
    try:
        result: CompletedProcess[str] = subprocess.run(
            ["eix", "-Q", "-#", "--in-overlay", overlay],
            capture_output=True,
            text=True,
            env=env
        )

        if result.returncode == 0:
            # Each line represents one package
            return result.stdout.count('\n')
        else:
            return 0
    except (subprocess.SubprocessError, OSError):
        return 0