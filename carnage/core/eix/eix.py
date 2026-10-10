"""Basic interactions with eix for package management."""

import shutil
import subprocess

from carnage.core.process import tracked_run

_remote_cache_available: bool | None = None
_cache_available: bool | None = None


def invalidate_cache() -> None:
    """Forget the cached has_cache() answer so it is probed again."""
    global _cache_available

    _cache_available = None


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

    Uses global caching to avoid repeated subprocess calls.

    Returns:
        True if cache exists, False otherwise (including when eix could not be
        run at all)
    """
    global _cache_available

    if _cache_available is None:
        try:
            result = tracked_run(["eix", "-Qq0"], text=True)
        except (subprocess.SubprocessError, OSError):
            result = None

        # A probe that could not run counts as "no cache", same as the remote
        # probe below. Both are invalidated after the matching update command.
        _cache_available = result is not None and result.returncode == 0

    return _cache_available


def count_matches(stdout: bytes) -> int:
    """
    Count matches in the output of an ``eix --format 1`` query.

    That format emits exactly one ``1`` byte per match and nothing else, so
    counting those bytes is what the callers want. Anything else on stdout - a
    banner, a warning - would silently turn into a wrong package count, so it
    is reported as an error instead.

    Args:
        stdout: Raw stdout of the query

    Returns:
        Number of matches, or -1 when the output is not in the expected format
    """
    if set(stdout) - {ord("1"), ord("\n"), ord("\r"), ord(" "), ord("\t")}:
        return -1

    return stdout.count(b"1")


def invalidate_remote_cache() -> None:
    """Forget the cached has_remote_cache() answer so it is probed again."""
    global _remote_cache_available

    _remote_cache_available = None


def has_remote_cache() -> bool:
    """
    Check if eix remote cache exists and is valid.

    Uses global caching to avoid repeated subprocess calls.

    Returns:
        True if remote cache exists, False otherwise
    """
    global _remote_cache_available

    if _remote_cache_available is None:
        try:
            result = tracked_run(["eix", "-QRq0"], text=True)
        except (subprocess.SubprocessError, OSError):
            result = None

        # A probe that could not run counts as "no remote cache": the non -R
        # commands are always safe, and the answer is invalidated again after
        # the next eix-remote update.
        _remote_cache_available = result is not None and result.returncode == 0

    return _remote_cache_available
