"""Basic interactions with portageq for repository path queries."""

import subprocess
from pathlib import Path
from subprocess import CompletedProcess

_gentoo_repo_path: Path | None = None


def get_gentoo_repo_path() -> Path:
    """
    Get the Gentoo repository path using portageq.

    Uses global caching to avoid repeated subprocess calls.

    Returns:
        Path object pointing to the Gentoo repository
    """
    global _gentoo_repo_path

    if _gentoo_repo_path is None:
        result: CompletedProcess[str] = subprocess.run(
            ["portageq", "get_repo_path", "/", "gentoo"],
            capture_output=True,
            text=True
        )

        if result.returncode == 0 and result.stdout.strip():
            _gentoo_repo_path = Path(result.stdout.strip())
        else:
            # Fallback to default path if portageq fails
            _gentoo_repo_path = Path("/var/db/repos/gentoo")

    return _gentoo_repo_path

def get_repos_path() -> Path:
    """
    Get the parent directory containing all repository paths.

    Returns:
        Path object pointing to the repositories parent directory
    """

    return get_gentoo_repo_path().parent