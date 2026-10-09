"""Simple subprocess wrapper with process tracking and signal support."""

import os
import signal
import subprocess
import time
from collections.abc import Sequence
from subprocess import CompletedProcess
from typing import Any

# Upper bound applied to every tracked subprocess that does not name its own.
DEFAULT_TIMEOUT = 30.0


def _is_alive(pid: int) -> bool:
    """Return whether a process still exists."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Exists, but belongs to someone else.
        return True
    return True


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

        # subprocess.run() accepts a handful of convenience kwargs (capture_output,
        # input, timeout, check) that subprocess.Popen does not understand - run()
        # consumes them internally before constructing its own Popen. Since we
        # construct Popen ourselves (to keep a handle on the process for
        # tracking/signaling), we have to translate or intercept these the same way,
        # rather than forwarding everything straight through to Popen.
        if self.kwargs.pop("capture_output", False):
            if "stdout" in self.kwargs and self.kwargs["stdout"] is not subprocess.PIPE:
                raise ValueError("stdout and stderr arguments may not be used with capture_output.")
            if "stderr" in self.kwargs and self.kwargs["stderr"] is not subprocess.PIPE:
                raise ValueError("stdout and stderr arguments may not be used with capture_output.")
            self.kwargs["stdout"] = subprocess.PIPE
            self.kwargs["stderr"] = subprocess.PIPE

        run_input = self.kwargs.pop("input", None)
        if run_input is not None:
            if "stdin" in self.kwargs:
                raise ValueError("stdin and input arguments may not both be used.")
            self.kwargs["stdin"] = subprocess.PIPE

        check = bool(self.kwargs.pop("check", False))

        timeout = self.kwargs.pop("timeout", None)

        self._process = subprocess.Popen(self.args, **self.kwargs)

        # Register in this process, not in the child: the forked child would only
        # ever see a discarded copy of the registry (and self._process is not
        # assigned until Popen returns). The entry lives exactly as long as the
        # communicate() below, so a concurrent terminate_all() can reach it.
        TrackedProcess._running_processes[self._process.pid] = self

        try:
            stdout, stderr = self._process.communicate(input=run_input, timeout=timeout)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.communicate()
            raise
        finally:
            TrackedProcess._running_processes.pop(self._process.pid, None)

        returncode = self._process.returncode

        self._result = CompletedProcess(
            args=self.args,
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
        )

        if check and returncode != 0:
            raise subprocess.CalledProcessError(returncode, self.args, output=stdout, stderr=stderr)

        return self._result

    @property
    def pid(self) -> int | None:
        """Get the process ID."""
        return self._process.pid if self._process else None

    @classmethod
    def terminate_all(cls, signum: int = signal.SIGTERM, grace: float = 0.5) -> list[int]:
        """
        Signal every tracked process, escalating to SIGKILL for the survivors.

        Args:
            signum: Signal to send first.
            grace: Seconds to wait for the processes to exit before escalating.

        Returns:
            The PIDs that survived because they refused to be signaled.
        """
        pids = list(cls._running_processes)

        for pid in pids:
            try:
                os.kill(pid, signum)
            except ProcessLookupError:
                # Process already terminated
                cls._running_processes.pop(pid, None)
            except PermissionError:
                # Can't signal this process
                pass

        deadline = time.monotonic() + grace
        pending = [pid for pid in pids if _is_alive(pid)]

        while pending and time.monotonic() < deadline:
            pending = [pid for pid in pending if _is_alive(pid)]
            if pending:
                time.sleep(0.02)

        survivors: list[int] = []

        for pid in pending:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                cls._running_processes.pop(pid, None)
            except PermissionError:
                survivors.append(pid)

        return survivors


def tracked_run(args: Sequence[str], **kwargs: Any) -> CompletedProcess:
    """
    Drop-in replacement for subprocess.run that tracks the process.

    Every call gets DEFAULT_TIMEOUT unless it names one: communicate() cannot
    be interrupted, so without a bound a stuck query would pin whichever
    thread made the call forever.

    Example:
        result = tracked_run(["emerge", "--moo"], capture_output=True, text=True)

        # Later, terminate all tracked processes:
        TrackedProcess.terminate_all()
    """
    kwargs.setdefault("timeout", DEFAULT_TIMEOUT)

    proc = TrackedProcess(args, **kwargs)
    return proc.run()
