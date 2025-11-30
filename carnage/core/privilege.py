"""Privilege escalation utilities."""

import shutil
import subprocess
from subprocess import CompletedProcess

from carnage.core.config import Configuration, get_config

# Available privilege escalation backends
BACKENDS: dict[str, str] = {
    "pkexec": "pkexec",
    "sudo": "sudo",
    "doas": "doas",
}


def detect_backend() -> str | None:
    """
    Detect available privilege escalation backend.

    Returns:
        The first available backend name, or None if none found.
    """
    for backend, cmd in BACKENDS.items():
        if shutil.which(cmd):
            return backend
    return None


def get_configured_backend() -> str | None:
    """
    Get privilege backend from configuration or auto-detect.

    Returns:
        Configured backend name, auto-detected backend, or None
    """
    config: Configuration = get_config()
    backend_str: str = config.privilege_backend.lower()

    print(backend_str)

    # Handle auto-detection
    if backend_str == "auto":
        return detect_backend()

    # Handle 'none' explicitly
    if backend_str == "none":
        return None

    # Validate configured backend
    if backend_str in BACKENDS:
        return backend_str

    # Invalid backend in config, fall back to auto-detection
    return detect_backend()


def run_privileged(
        cmd: list[str],
        backend: str | None = None,
        use_terminal: bool | None = None
) -> tuple[int, str, str]:
    """
    Run a command with privilege escalation.

    Args:
        cmd: Command and arguments to run.
        backend: Specific backend to use (e.g., 'sudo', 'pkexec').
                 If None, use configured backend.
        use_terminal: Whether to run the command in a terminal.
                      If None, defaults to True if terminal is configured.

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    if backend is None:
        backend = get_configured_backend()

    config: Configuration = get_config()
    terminal_cmd: list[str] = config.terminal

    # Determine if we should use terminal
    if use_terminal is None:
        use_terminal = bool(terminal_cmd)  # Use terminal if configured

    full_cmd: list[str] = cmd

    # Apply privilege escalation if backend is available
    if backend and backend in BACKENDS:
        full_cmd = [BACKENDS[backend]] + cmd

    # Apply terminal if requested and configured
    if use_terminal and terminal_cmd:
        full_cmd = terminal_cmd + full_cmd

    result: CompletedProcess[str] = subprocess.run(
        full_cmd,
        capture_output=True,
        text=True
    )

    return result.returncode, result.stdout, result.stderr