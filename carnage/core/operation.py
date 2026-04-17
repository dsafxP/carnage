"""User operation execution with privilege escalation and logging."""

import asyncio
import logging
import shlex
import shutil
from asyncio.subprocess import Process
from collections.abc import Callable
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from platformdirs import user_log_path
from textual.app import App

from carnage.core.config import Configuration, get_config

# Privilege escalation backends in detection priority order
_BACKENDS: list[str] = ["pkexec", "sudo", "doas"]

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


class OperationError(Exception):
    """Raised when an operation exits with a non-zero return code."""

    def __init__(self, cmd: list[str], returncode: int) -> None:
        self.cmd = cmd
        self.returncode = returncode
        super().__init__(f"Command {cmd[0]!r} exited with code {returncode}")


class Operation:
    """
    An async user-facing operation with optional privilege escalation
    and logging to the carnage log file.

    Intended for all user-initiated Portage and eix state-modifying
    commands (emerge, depclean, eix-update, overlay sync, etc.).
    Not intended for app-internal queries such as eix searches.

    Args:
        cmd:       Command and arguments to execute.
        privilege: Whether to prepend the configured privilege backend.
                   Defaults to False.

    Raises:
        OperationError: If the process exits with a non-zero return code.

    Example::

        op = Operation(["emerge", "app-editors/vim"], privilege=True)
        await op.run()
    """

    def __init__(self, cmd: list[str], *, privilege: bool = False) -> None:
        self.cmd = cmd
        self.privilege = privilege

        _ensure_log_handler()

    def _build_cmd(self) -> list[str]:
        """
        Resolve the full argv, prepending the privilege backend if requested.

        Returns:
            Full command as an argv list.
        """
        if not self.privilege:
            return self.cmd

        config: Configuration = get_config()
        backend_str: str = config.privilege_backend.strip()

        if not backend_str:
            # No backend configured — run without escalation.
            return self.cmd

        return [*shlex.split(backend_str), *self.cmd]

    async def run(self) -> int:
        """
        Execute the operation asynchronously, streaming output to the log.

        Returns:
            The process return code.

        Raises:
            OperationError: If the process exits with a non-zero return code.
        """
        full_cmd = self._build_cmd()
        start = datetime.now()

        _log.info("START %s", " ".join(full_cmd))

        process: Process = await asyncio.create_subprocess_exec(
            *full_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,  # merge stderr into stdout
        )

        # Stream output lines as they arrive rather than buffering.
        assert process.stdout is not None
        async for raw_line in process.stdout:
            line = raw_line.decode(errors="replace").rstrip()

            # print(line)
            _log.debug("%s", line)

        await process.wait()

        elapsed = (datetime.now() - start).total_seconds()
        returncode: int = process.returncode  # type: ignore[assignment]

        if returncode == 0:
            _log.info("END %s | exit 0 | %.1fs", full_cmd[0], elapsed)
        else:
            _log.warning("END %s | exit %d | %.1fs", full_cmd[0], returncode, elapsed)
            raise OperationError(full_cmd, returncode)

        return returncode

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
                if hasattr(app, "notify"):
                    app.notify("An operation is already running.", severity="warning")
                return

            app.blocked = True  # type: ignore

        async def _worker() -> None:
            success = False

            try:
                await self.run()
                success = True
            except OperationError as e:
                app.notify(f"Command failed (exit {e.returncode}): {e.cmd[0]}", severity="error")
            except Exception as e:
                _log.exception("Unexpected error in operation worker")

                app.notify(f"Internal error: {e}", severity="error")
            finally:
                # Unblock BEFORE calling on_complete and success notification
                if has_blocked:
                    app.blocked = False  # type: ignore

            # Now call the callback and success notification (if applicable)
            if on_complete:
                on_complete(success)

            if success and hasattr(app, "notify"):
                app.notify(f"Command finished successfully: {self.cmd[0]}", severity="information")

        app.run_worker(_worker(), exclusive=True)
