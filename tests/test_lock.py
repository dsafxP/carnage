"""Tests for the single-instance lock."""

from __future__ import annotations

import socket
import time
from pathlib import Path

import carnage.core.lock as lock_module
from carnage.core.lock import InstanceLock, default_socket_path


def _wait_for(predicate, timeout: float = 5.0) -> None:
    """Poll ``predicate`` until it is true or the timeout expires."""
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, "condition never became true"
        time.sleep(0.02)


def test_default_socket_path_is_not_shared_between_users() -> None:
    from platformdirs import user_runtime_path

    assert default_socket_path() == user_runtime_path("carnage") / "carnage.lock"
    assert default_socket_path() != Path("/tmp/carnage.lock")


def test_second_instance_signals_the_first(tmp_path: Path) -> None:
    received: list[str] = []
    path = tmp_path / "carnage.lock"
    primary = InstanceLock(socket_path=path, on_signal=received.append)

    assert primary.acquire()

    try:
        secondary = InstanceLock(socket_path=path)
        assert not secondary.acquire()

        _wait_for(lambda: received == [InstanceLock.SIGNAL_NEW_INSTANCE])
    finally:
        primary.release()


def test_release_is_idempotent_and_spares_a_newer_socket(tmp_path: Path) -> None:
    path = tmp_path / "carnage.lock"
    first = InstanceLock(socket_path=path)

    assert first.acquire()
    first.release()

    second = InstanceLock(socket_path=path)
    assert second.acquire()

    try:
        # main() releases in a finally block and atexit releases again; the
        # second call must not unlink the socket the newer instance now owns.
        first.release()

        assert path.exists()
    finally:
        second.release()


def test_stale_socket_is_reclaimed(tmp_path: Path) -> None:
    path = tmp_path / "carnage.lock"

    leftover = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    leftover.bind(str(path))
    leftover.close()  # leaves the file behind with nobody listening

    lock = InstanceLock(socket_path=path)

    try:
        assert lock.acquire()
    finally:
        lock.release()

    assert not path.exists()


def test_a_directory_owned_by_someone_else_is_refused(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(lock_module.os, "getuid", lambda: 65534)

    lock = InstanceLock(socket_path=tmp_path / "carnage.lock")

    assert lock.acquire() is False


def test_listener_survives_a_failing_callback(tmp_path: Path) -> None:
    calls: list[int] = []

    def boom(_signal: str) -> None:
        calls.append(1)
        raise RuntimeError("callback exploded")

    path = tmp_path / "carnage.lock"
    primary = InstanceLock(socket_path=path, on_signal=boom)

    assert primary.acquire()

    try:
        for _ in range(3):
            secondary = InstanceLock(socket_path=path)
            assert not secondary.acquire()

        _wait_for(lambda: len(calls) >= 2)
    finally:
        primary.release()
