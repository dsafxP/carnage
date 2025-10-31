"""USE flag functionality using eix."""

import os
import subprocess
from subprocess import CompletedProcess
from typing import List

from carnage.core.eix import has_remote_cache


def get_all_useflags() -> List[str]:
    """
    Get all available USE flags from eix.

    Tries with remote cache first (-R flag), falls back to local only.

    Returns:
        List of USE flag names

    Raises:
        subprocess.CalledProcessError: If eix command fails with both attempts
    """
    # Build command based on remote cache availability
    if has_remote_cache():
        cmd: list[str] = ["eix", "-R", "--print-all-useflags"]
    else:
        cmd = ["eix", "--print-all-useflags"]

    result: CompletedProcess[str] = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=True
    )

    # Parse output - one USE flag per line
    raw_useflags: List[str] = []
    for line in result.stdout.strip().split('\n'):
        raw_useflags.append(line)

    # Clean and filter USE flags
    cleaned_useflags: List[str] = []
    seen_flags: set[str] = set()

    for flag in raw_useflags:
        # Remove special characters from start and end
        # Common special chars: + ! ? * (used as modifiers in eix output)
        cleaned_flag: str = flag

        # Remove leading special characters
        while cleaned_flag and cleaned_flag[0] in '+!?*':
            cleaned_flag = cleaned_flag[1:]

        # Remove trailing special characters
        while cleaned_flag and cleaned_flag[-1] in '+!?*':
            cleaned_flag = cleaned_flag[:-1]

        # Skip if nothing left after cleaning
        if not cleaned_flag:
            continue

        # Skip flags that are only numbers or still contain only special chars
        if not any(c.isalnum() for c in cleaned_flag):
            continue

        # Add to result if not already seen (avoid duplicates)
        if cleaned_flag not in seen_flags:
            seen_flags.add(cleaned_flag)
            cleaned_useflags.append(cleaned_flag)

    return cleaned_useflags


def get_package_count_for_useflag(useflag: str) -> int:
    """
    Get the number of packages that have a specific USE flag.

    Args:
        useflag: USE flag name to count packages for

    Returns:
        Number of packages with this USE flag, or -1 if error occurs
    """
    # Set environment to disable limits
    env: dict[str, str] = os.environ.copy()
    env["EIX_LIMIT"] = "0"

    # Build command based on remote cache availability
    if has_remote_cache():
        cmd: list[str] = ["eix", "-RQ*", "--format", "1", "--use", useflag]
    else:
        cmd = ["eix", "-Q*", "--format", "1", "--use", useflag]

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
        return -1