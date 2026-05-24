"""Simple subprocess wrapper with process tracking and signal support."""

import os
import signal
import subprocess
from collections.abc import Sequence
from subprocess import CompletedProcess
from typing import Any


class TrackedProcess:
    """A simple wrapper for subprocess.run that tracks the PID for later signaling."""

    _running_processes: dict[int, "TrackedProcess"] = {}

    def __init__(self, args: Sequence[str], **kwargs: Any) -> None:
        """
        Initialize a tracked process.

        Args:
            args: Command and arguments to execute
            **kwargs: Additional arguments passed to subprocess.run
        """
        self.args = list(args)
        self.kwargs = kwargs
        self._process: subprocess.Popen | None = None
        self._result: CompletedProcess | None = None

    def run(self) -> CompletedProcess:
        """
        Run the command synchronously, tracking the process.

        Returns:
            The CompletedProcess result

        Raises:
            subprocess.CalledProcessError: If the command fails and check=True is set
        """
        # Default to capturing output if not specified
        if "stdout" not in self.kwargs and "stderr" not in self.kwargs:
            self.kwargs["stdout"] = subprocess.PIPE
            self.kwargs["stderr"] = subprocess.PIPE

        # Store original preexec_fn if any
        original_preexec = self.kwargs.get("preexec_fn")

        def track_pid() -> None:
            if original_preexec:
                original_preexec()
            if self._process:
                TrackedProcess._running_processes[self._process.pid] = self

        self.kwargs["preexec_fn"] = track_pid

        timeout = self.kwargs.pop("timeout", None)

        self._process = subprocess.Popen(self.args, **self.kwargs)

        try:
            stdout, stderr = self._process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.communicate()
            raise

        returncode = self._process.returncode

        # Remove from tracking when done
        TrackedProcess._running_processes.pop(self._process.pid, None)

        self._result = CompletedProcess(
            args=self.args,
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
        )

        if self.kwargs.get("check", False) and returncode != 0:
            raise subprocess.CalledProcessError(returncode, self.args, output=stdout, stderr=stderr)

        return self._result

    @property
    def pid(self) -> int | None:
        """Get the process ID."""
        return self._process.pid if self._process else None

    @classmethod
    def terminate_all(cls, signum: int = signal.SIGTERM) -> None:
        """Send a signal to all tracked running processes."""
        for pid, _ in list(cls._running_processes.items()):
            try:
                os.kill(pid, signum)
            except ProcessLookupError:
                # Process already terminated
                cls._running_processes.pop(pid, None)
            except PermissionError:
                # Can't signal this process
                pass


def tracked_run(args: Sequence[str], **kwargs: Any) -> CompletedProcess:
    """
    Drop-in replacement for subprocess.run that tracks the process.

    Example:
        result = tracked_run(["emerge", "--moo"], capture_output=True, text=True)

        # Later, terminate all tracked processes:
        TrackedProcess.terminate_all()
    """
    proc = TrackedProcess(args, **kwargs)
    return proc.run()
