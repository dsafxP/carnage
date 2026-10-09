"""Tests for operation lifecycle and cancellation (``carnage.core.operation``)."""

from __future__ import annotations

import asyncio
import os
from unittest.mock import Mock

import pytest

import carnage.core.commands_config as commands_config_module
import carnage.core.operation as operation_module
from carnage.core.operation import Operation, OperationError, cancel_all_operations, start_operation


async def _start(op: Operation) -> asyncio.Task:
    """Start ``op.run()`` and wait until the child process exists."""
    task = asyncio.create_task(op.run())
    deadline = asyncio.get_running_loop().time() + 5

    while op._process is None:
        assert asyncio.get_running_loop().time() < deadline, "child never started"
        await asyncio.sleep(0.01)

    return task


async def _wait_for_dead(pid: int) -> None:
    """Wait until a PID no longer exists."""
    deadline = asyncio.get_running_loop().time() + 5

    while True:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        assert asyncio.get_running_loop().time() < deadline, "child never died"
        await asyncio.sleep(0.02)


async def test_cancel_stops_a_running_child() -> None:
    op = Operation(["sleep", "30"])
    task = await _start(op)

    pid = op._process.pid if op._process else None
    assert pid is not None

    assert await op.cancel() is True
    assert op._process is None

    with pytest.raises(OperationError):
        await task

    await _wait_for_dead(pid)


async def test_cancel_of_a_finished_operation_succeeds() -> None:
    op = Operation(["sh", "-c", "exit 0"])

    await op.run()

    assert await op.cancel() is True


async def test_cancel_without_a_process_succeeds() -> None:
    op = Operation(["sleep", "30"])

    assert await op.cancel() is True


async def test_terminate_child_kills_the_child_without_an_await_point() -> None:
    """The safety net used from the worker's exception handlers is synchronous."""
    op = Operation(["sleep", "30"])
    task = await _start(op)

    pid = op._process.pid if op._process else None
    assert pid is not None

    op._terminate_child()

    with pytest.raises(OperationError):
        await task

    await _wait_for_dead(pid)


async def test_cancel_all_without_operations_returns_no_survivors() -> None:
    assert await cancel_all_operations() == []


async def test_cancel_all_reports_a_confirmed_stop() -> None:
    op = Operation(["sleep", "30"])
    task = await _start(op)
    operation_module._active_operations.append(op)

    try:
        survivors = await cancel_all_operations()
    finally:
        if op in operation_module._active_operations:
            operation_module._active_operations.remove(op)

    assert survivors == []

    with pytest.raises(OperationError):
        await task


def test_start_operation_builds_the_configured_command(monkeypatch, tmp_path) -> None:
    """The helper has to reach get_command() without touching the real config."""
    recorded: dict[str, object] = {}

    class _Recorder:
        def __init__(self, cmd: list[str], *, env=None, log_callback=None) -> None:
            recorded["cmd"] = cmd
            recorded["env"] = env
            recorded["log_callback"] = log_callback

        def start_in_app(self, app, *, on_complete=None) -> None:
            recorded["on_complete"] = on_complete

    monkeypatch.setattr(operation_module, "Operation", _Recorder)
    monkeypatch.setattr(
        commands_config_module,
        "get_commands_config",
        lambda: commands_config_module.CommandsConfiguration(config_path=tmp_path / "commands.toml"),
    )

    app = Mock()
    on_complete = Mock()

    start_operation(app, "emerge.install", args=["app-editors/vim"], default_privilege=True, on_complete=on_complete)

    argv = recorded["cmd"]
    assert isinstance(argv, list)

    # full_cmd carries whatever privilege backend was detected for this host.
    if argv and argv[0] in {"run0", "pkexec", "sudo", "doas"}:
        argv = argv[1:]

    assert argv == ["emerge", "-v", "--nospinner", "--", "app-editors/vim"]
    assert recorded["on_complete"] is on_complete
    # The log sink is resolved instead of typed onto the screen attribute.
    assert recorded["log_callback"] is not None


async def test_run_raises_for_a_failing_command() -> None:
    op = Operation(["sh", "-c", "exit 3"])

    with pytest.raises(OperationError) as exc_info:
        await op.run()

    assert exc_info.value.returncode == 3


async def test_run_streams_output_to_the_callback() -> None:
    received: list[bytes] = []
    op = Operation(["sh", "-c", "echo hello"], log_callback=received.append)

    assert await op.run() == 0
    assert b"hello\n" in received
