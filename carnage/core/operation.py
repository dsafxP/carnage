"""User operation execution with privilege escalation and logging."""

try:
    from desktop_notifier import DesktopNotifier
    from desktop_notifier.common import Urgency

    from carnage.core.notifications import get_notifier

    HAS_NOTIFICATIONS = True
except ImportError:
    HAS_NOTIFICATIONS = False

import asyncio
import logging
import os
import shutil
import signal
from asyncio.subprocess import Process
from collections.abc import Callable
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from platformdirs import user_log_path
from textual.app import App
from textual.worker import Worker

# Privilege escalation backends in detection priority order
_BACKENDS: list[str] = ["pkexec", "sudo", "doas"]

# Module-level registry of all currently running operations
_active_operations: list["Operation"] = []

_log = logging.getLogger("carnage.exec")
_log.propagate = False

_handler_installed: bool = False


def _ensure_log_handler() -> None:
    """Install the file handler on the carnage.exec logger once."""
    global _handler_installed

    if _handler_installed:
        return

    log_dir: Path = user_log_path("carnage", ensure_exists=True)
    timestamp = datetime.now().strftime("%Y-%m")
    log_file: Path = log_dir / f"carnage-exec-{timestamp}.log"

    handler = RotatingFileHandler(
        log_file,
        maxBytes=4 * 1024 * 1024,  # 4 MiB
        backupCount=4,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))

    _log.setLevel(logging.DEBUG)
    _log.addHandler(handler)

    _handler_installed = True


def detect_backend() -> str | None:
    """
    Detect the first available privilege escalation backend.

    Returns:
        Command string of the detected backend, or None if none found.
    """
    for backend in _BACKENDS:
        if shutil.which(backend):
            return backend
    return None


def generate_default_privilege_backend() -> str:
    """
    Resolve the privilege backend to write into a freshly generated config.

    Called once during config generation, not at runtime.

    Returns:
        Detected backend command string, or empty string if none available.
    """
    return detect_backend() or ""


async def cancel_all_operations() -> None:
    """
    Cancel all currently running operations.

    Sends SIGTERM to each operation's process group, waits up to 5 seconds,
    then force-kills any that have not exited. Also cancels their Textual workers.

    Safe to call when no operations are running.
    """
    if not _active_operations:
        return

    _log.info("Cancelling %d active operation(s).", len(_active_operations))

    # Snapshot the list - entries remove themselves from _active_operations
    # once their worker finishes, so iterate over a copy.
    ops = list(_active_operations)
    for op in ops:
        await op.cancel()


class OperationError(Exception):
    """Raised when an operation exits with a non-zero return code."""

    def __init__(self, cmd: list[str], returncode: int) -> None:
        self.cmd = cmd
        self.returncode = returncode
        super().__init__(f"Command {cmd[0]!r} exited with code {returncode}")


class Operation:
    """
    An async user-facing operation with logging to the carnage log file.

    The full command (including privilege escalation and environment) should be
    built by CommandsConfiguration before being passed here.

    Note: if the command is run through a privilege-escalation wrapper (pkexec,
    sudo, doas), that wrapper may itself sanitize or drop environment variables

    Args:
        cmd: Full command and arguments to execute (already includes privilege escalation)
        env: Extra environment variables to merge on top of the parent environment
        log_callback: Optional callback for streaming output

    Example::
        command = commands_config.get_command("emerge.install", args=["app-editors/vim"])
        op = Operation(command.full_cmd, env=command.env)
        await op.run()
    """

    def __init__(
        self,
        cmd: list[str],
        *,
        env: dict[str, str] | None = None,
        log_callback: Callable[[bytes], None] | None = None,
    ) -> None:
        self.cmd = cmd
        self.env = env
        self._log_callback = log_callback
        self._process: Process | None = None
        self._worker: Worker | None = None  # type: ignore[type-arg]

        _ensure_log_handler()

    async def run(self) -> int:
        """
        Execute the operation asynchronously, streaming output to the log.

        Returns:
            The process return code.

        Raises:
            OperationError: If the process exits with a non-zero return code.
        """
        start = datetime.now()

        _log.info("START %s", " ".join(self.cmd))

        # Send command header to log callback
        if self._log_callback:
            # Wrap in ANSI grey/dim codes
            cmd_str = " ".join(self.cmd)
            grey_cmd = f"[dim]$ {cmd_str}[/]\n"
            self._log_callback(grey_cmd.encode())

        # Merge any extra environment variables on top of the parent process's
        subprocess_env = {**os.environ, **(self.env or {})}

        process: Process = await asyncio.create_subprocess_exec(
            *self.cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,  # merge stderr into stdout
            env=subprocess_env,  # Inherit parent env, with overrides merged in
            start_new_session=True,  # Isolate the child in its own process group
        )
        self._process = process

        # Stream output lines as they arrive rather than buffering.
        assert process.stdout is not None
        async for raw_line in process.stdout:
            line = raw_line.decode(errors="replace").rstrip()

            # print(line)
            _log.debug("%s", line)

            if self._log_callback:
                self._log_callback(raw_line)

        await process.wait()

        elapsed = (datetime.now() - start).total_seconds()
        returncode: int = process.returncode  # type: ignore[assignment]

        # Send exit code footer to log callback
        if self._log_callback:
            exit_msg = f"\n[{'dim' if returncode == 0 else 'red'}]Exited with code: {returncode}[/]\n"
            self._log_callback(exit_msg.encode())

        if returncode == 0:
            _log.info("END %s | exit 0 | %.1fs", self.cmd[0], elapsed)
        else:
            _log.warning("END %s | exit %d | %.1fs", self.cmd[0], returncode, elapsed)
            raise OperationError(self.cmd, returncode)

        return returncode

    async def cancel(self) -> None:
        """
        Cancel this operation.

        Sends SIGTERM to the process group so that privilege-escalation wrappers
        (pkexec, sudo, doas) forward the signal to the child. Waits up to 5 seconds
        for a clean exit, then sends SIGKILL. Also cancels the Textual worker if one
        was started via start_in_app().
        """
        # Cancel the Textual worker first so the coroutine stops reading stdout
        # and does not race with us killing the process.
        if self._worker is not None:
            self._worker.cancel()

        if self._process is None or self._process.returncode is not None:
            return  # Already finished — nothing to do.

        pid = self._process.pid
        _log.info("Cancelling operation %s (pid=%d)", self.cmd[0], pid)

        try:
            pgid = os.getpgid(pid)
            os.killpg(pgid, signal.SIGTERM)
        except ProcessLookupError:
            return  # Process already gone.
        except PermissionError:
            # Can't signal the process group (e.g. pkexec owns it); fall back to
            # terminating the wrapper directly and hope the child follows.
            _log.warning("Cannot signal process group for pid=%d; falling back to terminate()", pid)
            self._process.terminate()

        try:
            await asyncio.wait_for(self._process.wait(), timeout=5.0)
        except TimeoutError:
            _log.warning("Process pid=%d did not exit after SIGTERM; sending SIGKILL", pid)
            try:
                pgid = os.getpgid(pid)
                os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass

        self._process = None

    def start_in_app(self, app: App, *, on_complete: Callable[[bool], None] | None = None) -> None:
        """
        Start this operation as a Textual worker.

        - Prevents concurrent operations via app.blocked.
        - Shows notifications on success/error.
        - The worker runs exclusively (only one operation at a time).

        Args:
            app: The App instance
            on_complete: Optional callback when operation finishes (receives success bool)
        """

        # Check if the app has a blocked attribute
        has_blocked = hasattr(app, "blocked")

        if has_blocked:
            if app.blocked:  # type: ignore
                app.notify("An operation is already running.", severity="warning")
                return

            app.blocked = True  # type: ignore

        _active_operations.append(self)

        async def _worker() -> None:
            success = False

            try:
                await self.run()
                success = True
            except OperationError as e:
                app.notify(f"Command failed (exit {e.returncode}): {e.cmd[0]}", severity="error")
            except asyncio.CancelledError:
                _log.info("Operation cancelled: %s", self.cmd[0])
                if self._log_callback:
                    self._log_callback(b"\n[dim]Operation cancelled.[/]\n")
            except Exception as e:
                _log.exception("Unexpected error in operation worker")

                app.notify(f"Internal error: {e}", severity="error")
            finally:
                # Deregister from the active operations list
                try:
                    _active_operations.remove(self)
                except ValueError:
                    pass

                # Unblock BEFORE calling on_complete and success notification
                if has_blocked:
                    app.blocked = False  # type: ignore

            # Now call the callback and success notification (if applicable)
            if on_complete:
                on_complete(success)

            can_notify: bool = HAS_NOTIFICATIONS and not app.app_focus

            if can_notify:
                notifier: DesktopNotifier = get_notifier()  # type: ignore

                await notifier.send(
                    title="Operation completed!",
                    message=f"Command finished: {' '.join(self.cmd)}",
                    urgency=Urgency.Normal if success else Urgency.Critical,
                )

            # if success:
            #    app.notify(f"Command finished successfully: {self.cmd[0]}", severity="information")

        self._worker = app.run_worker(_worker(), exclusive=True)
