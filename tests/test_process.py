"""Tests for subprocess tracking (``carnage.core.process``)."""

from __future__ import annotations

import os
import subprocess
import threading
import time

import pytest

from carnage.core.process import TrackedProcess, tracked_run


def _process_dies(pid: int) -> bool:
    """Return whether a PID no longer exists."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return False


def _wait_for(predicate, timeout: float = 5.0) -> None:
    """Poll ``predicate`` until it is true or the timeout expires."""
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, "condition never became true"
        time.sleep(0.02)


def test_registry_tracks_a_running_process() -> None:
    """The PID is registered while communicate() blocks and dropped afterwards."""
    proc = TrackedProcess(["sleep", "30"])
    thread = threading.Thread(target=proc.run)
    thread.start()

    _wait_for(lambda: proc.pid is not None and proc.pid in TrackedProcess._running_processes)

    pid = proc.pid
    assert pid is not None
    assert TrackedProcess._running_processes[pid] is proc

    TrackedProcess.terminate_all()
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert TrackedProcess._running_processes == {}


def test_terminate_all_kills_a_running_process() -> None:
    """terminate_all() reaches a child that is still starting up."""
    proc = TrackedProcess(["sleep", "30"])
    thread = threading.Thread(target=proc.run)
    thread.start()

    _wait_for(lambda: proc.pid is not None and proc.pid in TrackedProcess._running_processes)
    pid = proc.pid
    assert pid is not None

    survivors = TrackedProcess.terminate_all()
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert survivors == []
    assert _process_dies(pid)
    assert TrackedProcess._running_processes == {}


def test_terminate_all_escalates_to_sigkill() -> None:
    """A child that ignores SIGTERM is killed by the escalation."""
    proc = TrackedProcess(["sh", "-c", "trap '' TERM; sleep 30"])
    thread = threading.Thread(target=proc.run)
    thread.start()

    _wait_for(lambda: proc.pid is not None and proc.pid in TrackedProcess._running_processes)
    pid = proc.pid
    assert pid is not None

    # grace=0 makes no room for the (ignored) SIGTERM to be observed.
    survivors = TrackedProcess.terminate_all(grace=0)
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert survivors == []
    _wait_for(lambda: _process_dies(pid))
    assert TrackedProcess._running_processes == {}


def test_check_true_raises_called_process_error() -> None:
    """check=True is intercepted instead of being forwarded to Popen."""
    with pytest.raises(subprocess.CalledProcessError) as exc_info:
        tracked_run(["sh", "-c", "exit 3"], check=True)

    assert exc_info.value.returncode == 3


def test_check_true_passes_on_success() -> None:
    result = tracked_run(["sh", "-c", "exit 0"], check=True, text=True, capture_output=True)

    assert result.returncode == 0


def test_check_false_returns_the_failure() -> None:
    result = tracked_run(["sh", "-c", "exit 3"])

    assert result.returncode == 3


def test_input_is_piped_to_the_process() -> None:
    result = tracked_run(["cat"], input="hello", text=True, check=True)

    assert result.returncode == 0
    assert result.stdout == "hello"


def test_timeout_kills_the_process_and_untracks_it() -> None:
    with pytest.raises(subprocess.TimeoutExpired):
        tracked_run(["sleep", "30"], timeout=0.2)

    assert TrackedProcess._running_processes == {}


def test_capture_output_conflicts_with_explicit_streams() -> None:
    with pytest.raises(ValueError):
        tracked_run(["cat"], capture_output=True, stdout=1)
