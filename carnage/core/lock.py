"""Single-instance lock using a Unix domain socket.

The first instance binds a socket and listens for signals from subsequent
instances. Additional instances send a signal and exit immediately.
"""

import atexit
import socket
import threading
from collections.abc import Callable
from pathlib import Path

_DEFAULT_SOCKET_PATH = Path("/tmp/carnage.lock")


class InstanceLock:
    """
    Enforces a single running instance via a Unix domain socket.

    The primary instance binds the socket and listens for signals.
    Any subsequent instance connects, sends a signal, and should exit.

    Args:
        socket_path: Path to the Unix socket file.
        on_signal: Callback invoked on the primary instance when a
                   secondary instance attempts to start. Receives the
                   signal string sent by the secondary instance.
    """

    SIGNAL_NEW_INSTANCE = "new_instance"

    def __init__(
        self,
        socket_path: Path = _DEFAULT_SOCKET_PATH,
        on_signal: Callable[[str], None] | None = None,
    ) -> None:
        self.socket_path = socket_path
        self.on_signal = on_signal
        self._server: socket.socket | None = None
        self._thread: threading.Thread | None = None

    def acquire(self) -> bool:
        """
        Attempt to acquire the instance lock.

        If the lock is free, binds the socket, starts the listener
        thread, and returns True.

        If another instance holds the lock, sends it a signal and
        returns False. If the socket is stale (process dead), cleans
        it up and retries once.

        Returns:
            True if this is the primary instance, False otherwise.
        """
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        try:
            sock.bind(str(self.socket_path))
        except OSError:
            sock.close()
            if self._is_stale():
                self.socket_path.unlink(missing_ok=True)
                return self.acquire()
            self._signal_primary()
            return False

        sock.listen(5)
        self._server = sock
        self._thread = threading.Thread(
            target=self._listen,
            daemon=True,
            name="carnage-instance-lock",
        )
        self._thread.start()
        atexit.register(self.release)
        return True

    def _is_stale(self) -> bool:
        """Check if the socket file exists but no process is listening."""
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(str(self.socket_path))
            sock.close()
            return False  # connected fine, someone is home
        except ConnectionRefusedError:
            return True  # socket file exists but process is dead
        except OSError:
            return False  # something else, don't assume stale

    def release(self) -> None:
        """Release the lock and clean up the socket file."""
        if self._server is not None:
            try:
                self._server.close()
            except OSError:
                pass
            self._server = None

        try:
            self.socket_path.unlink(missing_ok=True)
        except OSError:
            pass

    def _signal_primary(self) -> None:
        """Connect to the primary instance and send a signal."""
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(str(self.socket_path))
            sock.sendall(self.SIGNAL_NEW_INSTANCE.encode())
            sock.close()
        except OSError:
            # Primary may have died between our bind attempt and now;
            # nothing useful to do.
            pass

    def _listen(self) -> None:
        """Listen for signals from secondary instances."""
        while self._server is not None:
            try:
                conn, _ = self._server.accept()
            except OSError:
                break

            try:
                data = conn.recv(256).decode(errors="replace").strip()
            except OSError:
                data = ""
            finally:
                conn.close()

            if data and self.on_signal is not None:
                self.on_signal(data)
