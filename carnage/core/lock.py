"""Single-instance lock using a Unix domain socket.

The first instance binds a socket and listens for signals from subsequent
instances. Additional instances send a signal and exit immediately.
"""

import atexit
import os
import socket
import struct
import threading
from collections.abc import Callable
from pathlib import Path

from platformdirs import user_runtime_path


def default_socket_path() -> Path:
    """
    Socket path inside the per-user runtime directory.

    The runtime directory is not shared between users, unlike /tmp, where a
    socket at a predictable path could be claimed by someone else to keep the
    real user from ever starting the app.
    """
    return user_runtime_path("carnage") / "carnage.lock"


def _peer_is_same_user(conn: socket.socket) -> bool:
    """Whether the connecting process belongs to this user."""
    if not hasattr(socket, "SO_PEERCRED"):
        return True  # Platform without peer credentials.

    try:
        raw = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
        _pid, uid, _gid = struct.unpack("3i", raw)
    except OSError:
        return False

    return uid == os.getuid()


class InstanceLock:
    """
    Enforces a single running instance via a Unix domain socket.

    The primary instance binds the socket and listens for signals.
    Any subsequent instance connects, sends a signal, and should exit.

    Args:
        socket_path: Path to the Unix socket file. Defaults to the per-user
            runtime directory.
        on_signal: Callback invoked on the primary instance when a
                   secondary instance attempts to start. Receives the
                   signal string sent by the secondary instance.
    """

    SIGNAL_NEW_INSTANCE = "new_instance"

    def __init__(
        self,
        socket_path: Path | None = None,
        on_signal: Callable[[str], None] | None = None,
    ) -> None:
        self.socket_path = socket_path if socket_path is not None else default_socket_path()
        self.on_signal = on_signal
        self._server: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._holds_lock = False

    def acquire(self, *, _retry: bool = True) -> bool:
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
        parent = self.socket_path.parent

        try:
            parent.mkdir(parents=True, exist_ok=True)

            if os.stat(parent).st_uid != os.getuid():
                # Someone else owns this directory, so they could hijack the
                # socket we are about to bind.
                return False
        except OSError:
            return False

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        try:
            sock.bind(str(self.socket_path))
        except OSError:
            sock.close()

            if _retry and self._is_stale():
                try:
                    self.socket_path.unlink(missing_ok=True)
                except OSError:
                    # Leftover owned by somebody else (sticky directory):
                    # nothing safe to do, give up instead of crashing.
                    return False
                return self.acquire(_retry=False)

            self._signal_primary()
            return False

        sock.listen(5)
        self._server = sock
        self._holds_lock = True
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
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        try:
            sock.connect(str(self.socket_path))
            return False  # connected fine, someone is home
        except ConnectionRefusedError:
            return True  # socket file exists but process is dead
        except OSError:
            return False  # something else, don't assume stale
        finally:
            sock.close()

    def release(self) -> None:
        """Release the lock and clean up the socket file, if we still own it."""
        if not self._holds_lock:
            # Already released: main() and atexit both call this, and the
            # second call must not unlink the socket a newer instance has
            # since bound.
            return

        self._holds_lock = False

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

            data = ""

            try:
                # Only this user's instances may ring the bell of the running
                # one; anybody who can reach the socket is otherwise ignored.
                if not _peer_is_same_user(conn):
                    continue

                data = conn.recv(256).decode(errors="replace").strip()
            except OSError:
                data = ""
            finally:
                conn.close()

            if data and self.on_signal is not None:
                try:
                    self.on_signal(data)
                except Exception:
                    # The callback runs on the listener thread: letting it
                    # raise would kill the listener for every later instance.
                    pass
