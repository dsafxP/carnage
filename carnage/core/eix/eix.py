"""Basic interactions with eix for package management."""

import shutil
import subprocess
from subprocess import CompletedProcess

_remote_cache_available: bool | None = None

def is_found() -> bool:
    """
    Check if eix is installed and available.

    Returns:
        True if eix is found, False otherwise
    """
    return shutil.which("eix") is not None


def has_cache() -> bool:
    """
    Check if eix cache exists and is valid.

    Returns:
        True if cache exists, False otherwise
    """
    result: CompletedProcess[str] = subprocess.run(
        ["eix", "-Qq0"],
        capture_output=True,
        text=True
    )
    return result.returncode == 0


def has_remote_cache() -> bool:
    """
    Check if eix remote cache exists and is valid.

    Uses global caching to avoid repeated subprocess calls.

    Returns:
        True if remote cache exists, False otherwise
    """
    global _remote_cache_available

    if _remote_cache_available is None:
        result: CompletedProcess[str] = subprocess.run(
            ["eix", "-QRq0"],
            capture_output=True,
            text=True
        )
        _remote_cache_available = result.returncode == 0

    return _remote_cache_available


def has_protobuf_support() -> bool:
    """
    Check if eix was compiled with protobuf support.

    Returns:
        True if protobuf support is available, False otherwise
    """
    result: CompletedProcess[str] = subprocess.run(
        ["eix", "-Qq0", "--proto"],
        capture_output=True,
        text=True
    )
    return result.returncode == 0

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

    Note: Requires root privileges if remote cache does not exist.
          If the cache exists, runs without privilege escalation.

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    if has_remote_cache():
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
