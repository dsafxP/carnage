"""Privilege escalation utilities."""

import shutil
import subprocess
from enum import Enum
from subprocess import CompletedProcess

from .config import Configuration, get_config


class PrivilegeBackend(Enum):
    """Available privilege escalation backends."""
    PKEXEC = "pkexec"
    SUDO = "sudo"
    DOAS = "doas"
    NONE = "none"
    AUTO = "auto"


def detect_backend() -> PrivilegeBackend:
    """
    Detect available privilege escalation backend.

    Returns:
        The first available backend in order of preference.
    """
    backends = [
        (PrivilegeBackend.PKEXEC, "pkexec"),
        (PrivilegeBackend.SUDO, "sudo"),
        (PrivilegeBackend.DOAS, "doas"),
    ]

    for backend, cmd in backends:
        if shutil.which(cmd):
            return backend

    return PrivilegeBackend.NONE


def get_configured_backend() -> PrivilegeBackend:
    """
    Get privilege backend from configuration or auto-detect.

    Returns:
        Configured backend or auto-detected if set to 'auto'
    """
    config: Configuration = get_config()
    backend_str: str = config.privilege_backend.lower()

    print(backend_str)

    try:
        backend = PrivilegeBackend(backend_str)
        if backend == PrivilegeBackend.AUTO:
            return detect_backend()
        return backend
    except ValueError:
        # Invalid backend in config, fall back to auto-detection
        return detect_backend()


def run_privileged(
        cmd: list[str],
        backend: PrivilegeBackend | None = None
) -> tuple[int, str, str]:
    """
    Run a command with privilege escalation.

    Args:
        cmd: Command and arguments to run.
        backend: Specific backend to use. If None, use configured backend.

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    if backend is None:
        backend = get_configured_backend()

    full_cmd: list[str] = cmd

    if backend == PrivilegeBackend.PKEXEC:
        full_cmd = ["pkexec"] + cmd
    elif backend == PrivilegeBackend.SUDO:
        full_cmd = ["sudo"] + cmd
    elif backend == PrivilegeBackend.DOAS:
        full_cmd = ["doas"] + cmd

    result: CompletedProcess[str] = subprocess.run(
        full_cmd,
        capture_output=True,
        text=True
    )

    return result.returncode, result.stdout, result.stderr