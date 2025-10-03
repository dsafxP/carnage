"""Privilege escalation utilities."""

import shutil
import subprocess
from enum import Enum
from subprocess import CompletedProcess


class PrivilegeBackend(Enum):
    """Available privilege escalation backends."""
    PKEXEC = "pkexec"
    SUDO = "sudo"
    DOAS = "doas"
    RUN0 = "run0"
    NONE = "none"


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
        (PrivilegeBackend.RUN0, "run0"),
    ]

    for backend, cmd in backends:
        if shutil.which(cmd):
            return backend

    return PrivilegeBackend.NONE


def run_privileged(
        cmd: list[str],
        backend: PrivilegeBackend | None = None
) -> tuple[int, str, str]:
    """
    Run a command with privilege escalation.

    Args:
        cmd: Command and arguments to run.
        backend: Specific backend to use. If None, auto-detect.

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    if backend is None:
        backend = detect_backend()

    if backend == PrivilegeBackend.NONE:
        # Run without escalation, will likely fail
        full_cmd: list[str] = cmd
    elif backend == PrivilegeBackend.PKEXEC:
        full_cmd = ["pkexec"] + cmd
    elif backend == PrivilegeBackend.SUDO:
        full_cmd = ["sudo"] + cmd
    elif backend == PrivilegeBackend.DOAS:
        full_cmd = ["doas"] + cmd
    elif backend == PrivilegeBackend.RUN0:
        full_cmd = ["run0"] + cmd
    else:
        full_cmd = cmd

    result: CompletedProcess[str] = subprocess.run(
        full_cmd,
        capture_output=True,
        text=True
    )

    return result.returncode, result.stdout, result.stderr


def get_backend_name(backend: PrivilegeBackend | None = None) -> str:
    """
    Get the name of the privilege escalation backend.

    Args:
        backend: Specific backend to check. If None, auto-detect.

    Returns:
        Name of the backend as a string.
    """
    if backend is None:
        backend = detect_backend()

    return backend.value